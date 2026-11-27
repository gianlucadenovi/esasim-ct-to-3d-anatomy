# ── EsaSim block ──────────────────────────────────────────────────────
# Segment CT automatically (TotalSegmentator) (ws-segment-ct-automatically-totalsegmen) · version 4 · worker block, Python: def run(ctx)
# Segments organs, bones, vessels and muscles in any CT (NIfTI, NRRD, MHA or DICOM series) with TotalSegmentator, and writes each case as <case>/ct.nii.gz + <case>/segmentations/<structure>.nii.gz, the
# Workspace: Gianluca De Novi's workspace · Author: Gianluca De Novi
# Saved: 2026-11-27
#
# Inputs   ctx.inputs["id"] is a list of files: .path .name .size .read_text() .read_json()
#   scans       Files (gz, nii, nrrd, nhdr, mha, mhd, dcm) Scans · several · CT volumes (NIfTI, NRRD, MHA) or the files of DICOM series; masks in segmentations/ folders are skipped
# Outputs  ctx.output("id", "name.ext") is the path to write; ctx.write_json / ctx.write_text
#   cases       Files (gz)                Segmented cases · <case>/ct.nii.gz and <case>/segmentations/<structure>.nii.gz (one mask per structure), as the TotalSegmentator dataset lays them out
#   table       Table (csv)               Structures found · segmentation.csv: case, structure, voxels, volume_ml, task, seconds
#   telemetry   Live telemetry            ctx.telemetry("channel", data) while it runs
# Settings ctx.params["key"]
#   task        select    Task = "total" of total | total_mr | body | lung_vessels | liver_vessels | liver_segments | kidney_…
#   resolution  select    Resolution = "1.5 mm (best)" of 1.5 mm (best) | 3 mm (fast) | 6 mm (fastest)
#   structures  text      Only these structures = ""
#   device      select    Run on = "auto" of auto | NVIDIA GPU | CPU
#   scan_file   text      Scan file name = ""
#   keep_empty  bool      Keep empty masks = false
# Runs on  Any worker, NVIDIA GPU. Return a dict to fill the "result" output.
# Packages torch[cuda], TotalSegmentator, SimpleITK, numpy (installed by the worker with pip when missing)
# EsaSim rewrites these lines from the block's definition each time it is saved: change the definition, not them.
# ── end of EsaSim block header ────────────────────────────────────────

"""Segment CT automatically: TotalSegmentator (nnU-Net) on each scan, written in the TotalSegmentator dataset's layout:
<case>/ct.nii.gz and <case>/segmentations/<structure>.nii.gz, so every block that reads expert labels reads these too.

Inputs may be NIfTI / NRRD / MHA volumes (a case per file, or <case>/ct.nii.gz) or DICOM series (one or more per
folder). DICOM is converted with SimpleITK (no patient tags are written into the NIfTI). The network runs in its own
Python process (nnU-Net's worker pools are reliable on Windows only under a __main__ guard); its output is streamed
to the log."""
import csv
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import time

EXT = (".nii.gz", ".nii", ".nrrd", ".nhdr", ".mha", ".mhd")
MASK_DIRS = ("segmentations", "segmentation", "masks", "mask", "labels", "label")
SIDECAR = (".raw", ".zraw", ".csv", ".json", ".txt", ".md", ".png", ".jpg", ".zip", ".xml", ".pdf")
FAST_TASKS = ("total", "total_mr", "body")
ROI_TASKS = ("total", "total_mr")

RUNNER = r'''
import inspect, json, sys
if __name__ == "__main__":
    args = json.load(open(sys.argv[1], encoding="utf-8"))
    try:
        from totalsegmentator.config import set_config_key
        set_config_key("send_usage_stats", False)
    except Exception as e:
        print("Could not turn off usage statistics: %s" % e, flush=True)
    from totalsegmentator.python_api import totalsegmentator
    ok = inspect.signature(totalsegmentator).parameters
    gone = [k for k in list(args) if k not in ok]
    for k in gone:
        args.pop(k)
    if gone:
        print("This TotalSegmentator version has no option: " + ", ".join(gone), flush=True)
    totalsegmentator(**args)
    print("TOTALSEG_DONE", flush=True)
'''


def run(ctx):
    import numpy as np
    import SimpleITK as sitk

    p = ctx.params
    task = str(p.get("task") or "total").strip()
    res = str(p.get("resolution") or "1.5 mm (best)")
    rois = [x.strip() for x in str(p.get("structures") or "").split(",") if x.strip()]
    pat = str(p.get("scan_file") or "").strip().lower()
    keep_empty = bool(p.get("keep_empty", False))
    device = pick_device(str(p.get("device") or "auto"), ctx.log)

    cases = collect(ctx, pat)
    if not cases:
        raise RuntimeError("No CT scan among the inputs: wire NIfTI, NRRD or MHA volumes, or the files of DICOM series "
                           "(files in segmentations/ folders are masks and are skipped).")
    ctx.log("%d case(s) to segment with TotalSegmentator, task %s, %s, on the %s." % (
        len(cases), task, res, "GPU" if device.startswith("gpu") else "CPU"))

    runner = os.path.join(ctx.folder, "totalseg_runner.py")
    with open(runner, "w", encoding="utf-8") as fh:
        fh.write(RUNNER)

    rows, done, t_all = [], [], time.time()
    for n, (case, src) in enumerate(sorted(cases.items())):
        t0 = time.time()
        base = 100.0 * n / len(cases)
        ctx.progress(base, "%s: reading the scan" % case)
        ct_out = ctx.output("cases", "%s/ct.nii.gz" % case)
        try:
            img = write_ct(src, ct_out, sitk)
        except Exception as e:                                    # one bad case does not stop the others
            ctx.log("%s: the scan could not be read (%s): skipped." % (case, e))
            continue
        arr = sitk.GetArrayViewFromImage(img)
        if arr.dtype.kind in "iu" and len(np.unique(arr[::4, ::4, ::4])) < 64:
            ctx.log("%s: looks like a label map, not a scan: skipped." % case)
            os.remove(ct_out)
            continue
        ctx.log("%s: %d x %d x %d voxels of %s mm." % ((case,) + img.GetSize() + (
            " x ".join("%.2f" % s for s in img.GetSpacing()),)))

        out_dir = os.path.join(ctx.folder, "totalseg", case)
        shutil.rmtree(out_dir, ignore_errors=True)
        args = {"input": ct_out, "output": out_dir, "task": task, "device": device, "ml": False,
                "nr_thr_resamp": 1, "nr_thr_saving": 1, "quiet": False}
        if task in FAST_TASKS:
            args["fast"] = res.startswith("3")
            if res.startswith("6"):
                args["fastest"] = True
        if rois and task in ROI_TASKS:
            args["roi_subset"] = rois
        ctx.progress(base + 5.0 / len(cases), "%s: segmenting (%s)" % (case, task))
        segment(ctx, runner, args, case)

        masks = sorted(f for f in os.listdir(out_dir) if f.lower().endswith(".nii.gz")) if os.path.isdir(out_dir) else []
        if not masks:
            ctx.log("%s: the network wrote no mask." % case)
            continue
        vox_ml = float(np.prod(img.GetSpacing())) / 1000.0
        found = 0
        for i, m in enumerate(masks):
            path = os.path.join(out_dir, m)
            count = int((sitk.GetArrayViewFromImage(sitk.ReadImage(path)) > 0).sum())
            if count == 0 and not keep_empty:
                continue
            name = m[:-7]
            shutil.copyfile(path, ctx.output("cases", "%s/segmentations/%s.nii.gz" % (case, name)))
            found += count > 0
            rows.append({"case": case, "structure": name, "voxels": count, "volume_ml": round(count * vox_ml, 2),
                         "task": task, "seconds": ""})
            if i % 10 == 0:
                ctx.progress(base + (80.0 + 20.0 * i / len(masks)) / len(cases), "%s: keeping the masks" % case)
        secs = round(time.time() - t0, 1)
        for r in rows:
            if r["case"] == case:
                r["seconds"] = secs
        shutil.rmtree(out_dir, ignore_errors=True)
        ctx.log("%s: %d structures found (of %d the task knows), %.0f s." % (case, found, len(masks), secs))
        ctx.telemetry("segmentation", {"case": case, "structures": found, "seconds": secs})
        done.append(case)

    if not done:
        raise RuntimeError("No case could be segmented: see the log above.")
    with open(ctx.output("table", "segmentation.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["case", "structure", "voxels", "volume_ml", "task", "seconds"])
        w.writeheader()
        w.writerows(rows)
    return {"cases": len(done), "structures": sum(1 for r in rows if r["voxels"]), "task": task,
            "device": device, "seconds": round(time.time() - t_all, 1)}


def pick_device(choice, log):
    try:
        import torch
        cuda = bool(torch.cuda.is_available())
        name = torch.cuda.get_device_name(0) if cuda else ""
    except Exception as e:
        log("PyTorch could not be loaded here (%s): the CPU is used." % e)
        cuda, name = False, ""
    if choice == "NVIDIA GPU":
        if not cuda:
            raise RuntimeError("Run on NVIDIA GPU was chosen, but PyTorch on this worker sees no CUDA GPU "
                               "(a CPU-only PyTorch build, or no NVIDIA driver). Choose auto or CPU, or install PyTorch with CUDA.")
        return "gpu"
    if choice == "CPU" or not cuda:
        if choice == "auto":
            log("No CUDA GPU seen by PyTorch: segmenting on the CPU (slower; Resolution 3 mm helps).")
        return "cpu"
    log("Segmenting on the GPU: %s." % name)
    return "gpu"


def collect(ctx, pat):
    """case -> ("volume", path) or ("dicom", [files of one series])."""
    import SimpleITK as sitk
    vols, dicom_dirs = [], {}
    for f in ctx.inputs.get("scans", []):
        rel = rel_of(f)
        parts = rel.split("/")
        if any(x.lower() in MASK_DIRS for x in parts[:-1]):
            continue
        low = f.name.lower()
        if low.endswith(EXT):
            if pat and not fnmatch.fnmatch(low, pat):
                continue
            vols.append((f, parts))
        elif low.endswith(".dcm") or ("." not in low) or not low.endswith(SIDECAR):
            dicom_dirs.setdefault(os.path.dirname(f.path), "/".join(parts[:-1]))
    per_folder = {}
    for f, parts in vols:
        per_folder["/".join(parts[:-1])] = per_folder.get("/".join(parts[:-1]), 0) + 1
    cases = {}
    for f, parts in vols:
        folder = "/".join(parts[:-1])
        name = parts[-2] if (folder and per_folder[folder] == 1) else stem(parts[-1])
        cases[unique(safe(name), cases)] = ("volume", f.path)
    for d, relf in sorted(dicom_dirs.items()):
        try:
            ids = sitk.ImageSeriesReader.GetGDCMSeriesIDs(d) or []
        except Exception:
            ids = []
        series = []
        for sid in ids:
            names = sitk.ImageSeriesReader.GetGDCMSeriesFileNames(d, sid)
            if len(names) >= 10:                                   # a volume, not a scout or a single image
                series.append(list(names))
        base = safe(relf.rsplit("/", 1)[-1] if relf else "dicom")
        for i, names in enumerate(sorted(series, key=len, reverse=True)):
            cases[unique(base if i == 0 else "%s_%d" % (base, i + 1), cases)] = ("dicom", names)
    return cases


def write_ct(src, path, sitk):
    kind, what = src
    if kind == "volume":
        img = sitk.ReadImage(what)
        if what.lower().endswith(".nii.gz"):
            shutil.copyfile(what, path)
        else:
            sitk.WriteImage(img, path, True)
    else:
        r = sitk.ImageSeriesReader()
        r.SetFileNames(what)
        img = r.Execute()
        sitk.WriteImage(img, path, True)                           # pixels and geometry only: no patient tags
    if img.GetDimension() != 3:
        raise RuntimeError("not a 3D volume")
    return img


def segment(ctx, runner, args, case):
    cfg = os.path.join(ctx.folder, "totalseg_%s.json" % case)
    with open(cfg, "w", encoding="utf-8") as fh:
        json.dump(args, fh)
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
    # the worker installs packages in a folder of its own, on this process's sys.path: the child needs it too
    paths = [x for x in sys.path if x and os.path.isdir(x)]
    if env.get("PYTHONPATH"):
        paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(paths))
    proc = subprocess.Popen([sys.executable, runner, cfg], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            env=env, cwd=ctx.folder, text=True, encoding="utf-8", errors="replace", bufsize=1)
    tail, ok = [], False
    for line in proc.stdout:
        line = line.rstrip()
        if not line:
            continue
        if line == "TOTALSEG_DONE":
            ok = True
            continue
        tail = (tail + [line])[-25:]
        if "%|" in line and "100%" not in line:                   # progress bars: not every tick in the log
            continue
        ctx.log("%s · %s" % (case, line[:300]))
    code = proc.wait()
    if code != 0 or not ok:
        raise RuntimeError("TotalSegmentator stopped on %s (exit code %s):\n%s" % (case, code, "\n".join(tail[-12:])))


def unique(name, taken):
    n, i = name, 2
    while n in taken:
        n, i = "%s_%d" % (name, i), i + 1
    return n


def stem(n):
    for e in EXT:
        if n.lower().endswith(e):
            return n[: -len(e)]
    return n


def safe(n):
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in n)[:80] or "case"


def rel_of(f):
    if getattr(f, "rel", None):
        return f.rel.replace("\\", "/")
    path = (f.path or "").replace("\\", "/")
    key = "/outputs/%s/" % (getattr(f, "from_port", "") or "")
    i = path.rfind(key)
    return path[i + len(key):] if getattr(f, "from_port", None) and i >= 0 else f.name
