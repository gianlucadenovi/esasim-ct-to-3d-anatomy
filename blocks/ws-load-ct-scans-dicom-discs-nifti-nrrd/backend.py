# ── EsaSim block ──────────────────────────────────────────────────────
# Load CT scans (DICOM discs, NIfTI, NRRD, MHA) (ws-load-ct-scans-dicom-discs-nifti-nrrd) · version 2 · worker block, Python: def run(ctx)
# Turns any CT source (a CD/DVD export with DICOMDIR, DICOM/ and IHE_PDI/, loose DICOM, NIfTI, NRRD, MHA, zips) into one volume per case, <case>/ct.nii.gz: series grouped by their DICOM IDs, copies read
# Workspace: Gianluca De Novi's workspace · Author: Gianluca De Novi
# Saved: 2026-11-27
#
# Inputs   ctx.inputs["id"] is a list of files: .path .name .size .read_text() .read_json()
#   files       Files                     Files · several · optional · Source Files wired in: the scans, in any layout (DICOM folders, NIfTI/NRRD/MHA, zips)
# Outputs  ctx.output("id", "name.ext") is the path to write; ctx.write_json / ctx.write_text
#   cases       Files (gz)                Scans · <case>/ct.nii.gz, one per scan chosen, in HU
#   series      Table (csv)               Series · series.csv: every series found (study, number, description, modality, images, slice thickness, coverage, folders) and what happened to it
#   telemetry   Live telemetry            ctx.telemetry("channel", data) while it runs
# Settings ctx.params["key"]
#   source      select    Source = "Files wired in" of Files wired in | Folder on the worker | Upload from the View
#   folder      text      Folder on the worker = ""
#   series      select    Series = "The best CT series of each study" of The best CT series of each study | Every CT series |…
#   only        text      Series to load = ""
#   modalities  text      Modalities = "CT"
#   min_images  number    Fewest images = 20
#   wait_minutes number    Wait for the upload (minutes) = 30
# Runs on  Any worker. Return a dict to fill the "result" output.
# Packages pydicom, SimpleITK, numpy (installed by the worker with pip when missing)
# EsaSim rewrites these lines from the block's definition each time it is saved: change the definition, not them.
# ── end of EsaSim block header ────────────────────────────────────────

"""Load CT scans: turns whatever holds the scans (a CD/DVD export with DICOMDIR, DICOM/ and IHE_PDI/ folders, loose DICOM
files, NIfTI / NRRD / MHA volumes, zips of any of these) into one volume per case, <case>/ct.nii.gz, ready for the
segmentation and for every block that reads expert labels.

DICOM is grouped by its Series Instance UID, wherever the files are: a series split over several folders is one scan,
and the same image found twice (the IHE_PDI copy of a disc) is read once. Localisers, dose reports, structured reports
and other non-image series are skipped, and of the scans left the chosen ones are written: the best CT series of each
study (thin slices covering the most of the body), every series, or the ones named. Pixels are read with GDCM, so
compressed transfer syntaxes (JPEG, JPEG-LS, JPEG 2000, RLE) work, and are written in Hounsfield units. No patient tag
is copied: the NIfTI holds pixels and geometry only, and cases are named after the series (S3_Abdomen_1.5_B30f).

The scans come from the files wired in (a Dataset block, a download), from a folder on the worker, or from the
browser: with Source "Upload from the View", the block waits for the files the Load a CT view sends (channel ct-load)
and tells it how far it got (telemetry channel ct_load)."""
import base64
import csv
import gzip
import json
import os
import re
import shutil
import time
import zipfile

VOL_EXT = (".nii.gz", ".nii", ".nrrd", ".nhdr", ".mha", ".mhd")
NOT_DICOM = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".ico", ".htm", ".html", ".css", ".js", ".pdf", ".txt", ".xml",
             ".xsl", ".xsd", ".inf", ".ini", ".exe", ".dll", ".ttf", ".csv", ".json", ".md", ".mp4", ".avi", ".wmv",
             ".raw", ".zraw", ".nii.gz", ".nii", ".nrrd", ".nhdr", ".mha", ".mhd", ".zip", ".part", ".log", ".cab",
             ".msi", ".swf", ".jar", ".class", ".sys", ".lnk", ".url", ".dat")
MASK_DIRS = ("segmentations", "segmentation", "masks", "mask", "labels", "label")
IMAGE_SOPS = {
    "1.2.840.10008.5.1.4.1.1.2": "CT", "1.2.840.10008.5.1.4.1.1.2.1": "CT", "1.2.840.10008.5.1.4.1.1.2.2": "CT",
    "1.2.840.10008.5.1.4.1.1.4": "MR", "1.2.840.10008.5.1.4.1.1.4.1": "MR", "1.2.840.10008.5.1.4.1.1.4.4": "MR",
    "1.2.840.10008.5.1.4.1.1.128": "PT", "1.2.840.10008.5.1.4.1.1.130": "PT",
}
TAGS = ["SOPClassUID", "SOPInstanceUID", "StudyInstanceUID", "SeriesInstanceUID", "Modality", "SeriesNumber",
        "SeriesDescription", "ImageType", "ImageOrientationPatient", "ImagePositionPatient", "Rows", "Columns",
        "SliceThickness", "PixelSpacing", "NumberOfFrames", "InstanceNumber", "BodyPartExamined", "ConvolutionKernel"]
CHANNEL, TELE = "ct-load", "ct_load"
SOURCES = ("Files wired in", "Folder on the worker", "Upload from the View")
CHOICES = ("The best CT series of each study", "Every CT series", "Only these series")


def run(ctx):
    p = ctx.params
    source = str(p.get("source") or SOURCES[0])
    t0 = time.time()
    tell(ctx, "starting", source=source)
    if source == "Upload from the View":
        root = receive(ctx, int(float(p.get("wait_minutes") or 30) * 60))
        items = walk(root, "")
    elif source == "Folder on the worker":
        folder = str(p.get("folder") or "").strip().strip('"')
        if not folder:
            raise RuntimeError("Source is Folder on the worker, but Folder is empty: give the folder's full path as the "
                               "worker sees it (such as D:\\CT2013 or /data/ct/CT2013).")
        if not os.path.isdir(folder):
            raise RuntimeError("The folder %s does not exist on this worker (%s). Check the path, and that the run goes "
                               "to the machine that holds it." % (folder, os.environ.get("COMPUTERNAME") or os.uname()[1]))
        items = walk(folder, "")
        ctx.log("Reading %d files under %s." % (len(items), folder))
    else:
        items = [(f.path, rel_of(f)) for f in ctx.inputs.get("files", [])]
        if not items:
            raise RuntimeError("Source is Files wired in, but no files are wired: connect a Dataset block (or a download) "
                               "to Files, or choose another Source.")
    items = unzip_all(ctx, items)
    found = analyse(ctx, items)
    chosen = choose(ctx, found, p)
    tell(ctx, "reading", series=public(found))
    cases = write_cases(ctx, chosen, found)
    write_table(ctx, found)
    if not cases:
        why = "; ".join("%s: %s" % (s["label"], s["why"]) for s in found["series"][:8]) or "no DICOM image or volume"
        tell(ctx, "error", series=public(found), error="No scan to segment")
        raise RuntimeError("No scan to segment among %d files (%s)." % (len(items), why))
    tell(ctx, "done", series=public(found), cases=cases)
    return {"cases": len(cases), "series_found": len(found["series"]), "files": len(items),
            "seconds": round(time.time() - t0, 1)}


# ── where the files are ──────────────────────────────────────────────────────────────────────────────────────────
def walk(root, prefix):
    out = []
    for d, dirs, files in os.walk(root):
        dirs.sort()
        for n in sorted(files):
            path = os.path.join(d, n)
            rel = os.path.relpath(path, root).replace("\\", "/")
            out.append((path, (prefix + "/" + rel) if prefix else rel))
    return out


def unzip_all(ctx, items):
    out = []
    for path, rel in items:
        if rel.lower().endswith(".zip") and zipfile.is_zipfile(path):
            dest = os.path.join(ctx.folder, "unzipped", safe(os.path.basename(rel)[:-4]))
            with zipfile.ZipFile(path) as z:
                for m in z.infolist():
                    target = os.path.normpath(os.path.join(dest, m.filename))
                    if not target.startswith(os.path.normpath(dest)) or m.is_dir():
                        continue                                    # (no paths out of the folder)
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with z.open(m) as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst)
            inner = walk(dest, rel[:-4])
            ctx.log("%s: %d files unpacked." % (rel, len(inner)))
            out.extend(inner)
        else:
            out.append((path, rel))
    return out


# ── what they hold ───────────────────────────────────────────────────────────────────────────────────────────────
def analyse(ctx, items):
    """{"series": [...], "volumes": [...], "other": n}: DICOM grouped by series (each image once), and volume files."""
    import pydicom
    series, seen, volumes, other, n = {}, set(), [], 0, len(items)
    for i, (path, rel) in enumerate(items):
        low = rel.lower()
        parts = low.split("/")
        if i % 200 == 0:
            ctx.progress(30.0 * i / max(1, n), "Looking at the files (%d of %d)" % (i, n))
            tell(ctx, "looking", done=i, total=n)
        if any(x in MASK_DIRS for x in parts[:-1]):
            continue
        if low.endswith(VOL_EXT):
            volumes.append((path, rel))
            continue
        if low.endswith(NOT_DICOM) or os.path.basename(low) == "dicomdir":
            other += 1
            continue
        try:
            ds = pydicom.dcmread(path, stop_before_pixels=True, specific_tags=TAGS, force=True)
        except Exception:
            other += 1
            continue
        sop, uid = str(ds.get("SOPClassUID", "")), str(ds.get("SeriesInstanceUID", ""))
        inst = str(ds.get("SOPInstanceUID", ""))
        if not uid or not inst:
            other += 1                                               # not a DICOM image (DICOMDIR, a stray file)
            continue
        if inst in seen:
            continue                                                 # the same image again (IHE_PDI's copy)
        seen.add(inst)
        s = series.get(uid)
        if s is None:
            s = series[uid] = {
                "uid": uid, "study": str(ds.get("StudyInstanceUID", "")), "number": num(ds.get("SeriesNumber"), 0),
                "desc": str(ds.get("SeriesDescription", "") or ""), "modality": str(ds.get("Modality", "") or ""),
                "sop": sop, "kind": IMAGE_SOPS.get(sop, ""), "image_type": "\\".join(map(str, ds.get("ImageType", []) or [])),
                "thick": num(ds.get("SliceThickness"), 0.0), "pixel": [num(x, 0.0) for x in (ds.get("PixelSpacing") or [])],
                "kernel": str(ds.get("ConvolutionKernel", "") or ""), "files": [], "folders": set()}
        frames = int(num(ds.get("NumberOfFrames"), 1) or 1)
        s["files"].append({"path": path, "ipp": [num(x, 0.0) for x in (ds.get("ImagePositionPatient") or [])],
                           "iop": [round(num(x, 0.0), 3) for x in (ds.get("ImageOrientationPatient") or [])],
                           "size": (int(num(ds.get("Rows"), 0)), int(num(ds.get("Columns"), 0))), "frames": frames,
                           "inst": int(num(ds.get("InstanceNumber"), 0))})
        s["folders"].add(os.path.dirname(rel))
    studies = []
    for s in series.values():
        if s["study"] not in studies:
            studies.append(s["study"])
    out = sorted(series.values(), key=lambda s: (studies.index(s["study"]), s["number"], s["desc"]))
    for s in out:
        geometry(s)
        s["study_n"] = studies.index(s["study"]) + 1
    ctx.log("%d files: %d DICOM series in %d stud%s, %d volume file(s), %d other file(s) (pictures, pages, DICOMDIR…)." % (
        n, len(out), len(studies), "y" if len(studies) == 1 else "ies", len(volumes), other))
    return {"series": out, "volumes": volumes, "studies": len(studies), "other": other}


def geometry(s):
    """The stack to read: the largest set of images of one orientation and size, one per position, in order."""
    import numpy as np
    files = s["files"]
    s["why"], s["usable"] = "", False
    s["images"] = sum(f["frames"] for f in files)
    if s["kind"] == "":
        s["why"] = "not an image series (%s)" % (s["modality"] or "unknown")
        return
    if "LOCALIZER" in s["image_type"].upper():
        s["why"] = "localiser (scout)"
        return
    multi = [f for f in files if f["frames"] > 1]
    if multi:                                                        # enhanced, multi-frame: one file is the volume
        f = max(multi, key=lambda f: f["frames"])
        s["stack"], s["count"], s["axial"], s["extent"], s["step"] = [f["path"]], f["frames"], True, 0.0, s["thick"]
        s["usable"] = True
        return
    groups = {}
    for f in files:
        if len(f["iop"]) == 6 and len(f["ipp"]) == 3:
            groups.setdefault((tuple(f["iop"]), f["size"]), []).append(f)
    if not groups:
        s["why"] = "no image position or orientation"
        return
    (iop, size), g = max(groups.items(), key=lambda kv: len(kv[1]))
    nrm = np.cross(np.array(iop[:3]), np.array(iop[3:]))
    for f in g:
        f["z"] = float(np.dot(np.array(f["ipp"]), nrm))
    g.sort(key=lambda f: f["z"])
    stack, last = [], None
    for f in g:                                                      # one image per position
        if last is None or abs(f["z"] - last) > 1e-3:
            stack.append(f)
            last = f["z"]
    steps = np.diff([f["z"] for f in stack]) if len(stack) > 1 else np.array([0.0])
    step = float(np.median(steps)) if len(steps) else 0.0
    s["stack"] = [f["path"] for f in stack]
    s["count"] = len(stack)
    s["step"] = round(step, 3)
    s["extent"] = round(step * (len(stack) - 1), 1)
    s["axial"] = abs(nrm[2]) > 0.9
    s["gaps"] = bool(len(steps) > 1 and step > 0 and float(steps.max()) > 1.6 * step)
    if len(groups) > 1:
        s["note"] = "%d images of another orientation or size left out" % (len(files) - len(g))
    s["usable"] = True


def choose(ctx, found, p):
    choice = str(p.get("series") or CHOICES[0])
    allowed = [m.strip().upper() for m in str(p.get("modalities") or "CT").split(",") if m.strip()]
    minimum = int(num(p.get("min_images"), 20))
    names = [x.strip().lower() for x in str(p.get("only") or "").split(",") if x.strip()]
    pool = []
    for s in found["series"]:
        if not s["usable"]:
            continue
        if s["kind"] not in allowed and s["modality"].upper() not in allowed:
            s["usable"], s["why"] = False, "%s, not %s (Modalities)" % (s["kind"] or s["modality"], "/".join(allowed))
            continue
        if s["count"] < minimum and len(s["stack"]) != 1:
            s["usable"], s["why"] = False, "only %d images (Fewest images: %d)" % (s["count"], minimum)
            continue
        pool.append(s)
    if choice == "Only these series":
        if not names:
            raise RuntimeError("Series is Only these series, but Series to load is empty: give series numbers, "
                               "descriptions or UIDs, separated by commas (the Series table of a first run lists them).")
        for s in pool:
            keys = {str(s["number"]), s["desc"].lower(), s["uid"].lower(), "s%d" % s["number"]}
            if any(n in keys or (n and n in s["desc"].lower()) for n in names):
                s["chosen"] = True
            else:
                s["why"] = "not in Series to load"
    elif choice == "Every CT series":
        for s in pool:
            s["chosen"] = True
    else:
        by_study = {}
        for s in pool:
            by_study.setdefault(s["study"], []).append(s)
        for group in by_study.values():
            best = max(group, key=score)
            best["chosen"] = True
            for s in group:
                if s is not best:
                    s["why"] = "another series of the study was chosen (%s)" % label(best, found)
    for s in found["series"]:
        s["label"] = label(s, found)
    chosen = [s for s in found["series"] if s.get("chosen")]
    for s in chosen:
        s["why"] = "loaded"
    ctx.log("Series: " + "; ".join("%s (%d images) %s" % (s["label"], s["images"], s["why"]) for s in found["series"]))
    return chosen


def score(s):
    """The series that suits the segmentation best: axial, slices of 3 mm or thinner, covering the most, then thinner."""
    t = s["thick"] or abs(s.get("step") or 0) or 9.0
    return (bool(s.get("axial")), t <= 3.0, s.get("extent") or 0.0, -t, s["count"])


def label(s, found):
    base = "S%d_%s" % (s["number"], s["desc"]) if s["desc"] else "S%d" % s["number"]
    if found["studies"] > 1:
        base = "%s_%s" % ("ABCDEFGHIJKLMNOPQRSTUVWXYZ"[(s["study_n"] - 1) % 26], base)
    return safe(base)[:60]


# ── writing the cases ────────────────────────────────────────────────────────────────────────────────────────────
def write_cases(ctx, chosen, found):
    import SimpleITK as sitk
    import numpy as np
    cases, used = [], set()
    jobs = [("dicom", s) for s in chosen] + [("volume", v) for v in found["volumes"]]
    per_folder = {}
    for kind, v in jobs:
        if kind == "volume":
            per_folder[os.path.dirname(v[1])] = per_folder.get(os.path.dirname(v[1]), 0) + 1
    for i, (kind, v) in enumerate(jobs):
        ctx.progress(30 + 70.0 * i / max(1, len(jobs)), "Writing the scans (%d of %d)" % (i + 1, len(jobs)))
        try:
            if kind == "dicom":
                name = v["label"]
                if len(v["stack"]) == 1:
                    img = sitk.ReadImage(v["stack"][0])
                else:
                    r = sitk.ImageSeriesReader()
                    r.SetImageIO("GDCMImageIO")
                    r.SetFileNames(v["stack"])
                    img = r.Execute()
            else:
                path, rel = v
                folder = os.path.dirname(rel)
                name = safe(os.path.basename(folder) if folder and per_folder[folder] == 1 else stem(os.path.basename(rel)))
                img = sitk.ReadImage(path)
                a = sitk.GetArrayFromImage(img)[::4, ::4, ::4]
                if a.dtype.kind in "iu" and a.min() >= 0 and len(np.unique(a)) < 64:   # (a CT has air, below 0)
                    ctx.log("%s looks like a label map, not a scan: skipped." % rel)
                    continue
            if img.GetDimension() == 4 and img.GetSize()[3] == 1:
                img = img[:, :, :, 0]
            if img.GetDimension() != 3:
                ctx.log("%s is not a 3D volume: skipped." % name)
                continue
            if img.GetNumberOfComponentsPerPixel() > 1:
                ctx.log("%s is a colour image, not a scan: skipped." % name)
                continue
            lo, hi = stats(img)
            if img.GetPixelID() != sitk.sitkInt16 and lo >= -32768 and hi <= 32767:
                img = sitk.Cast(sitk.Round(img) if "float" in img.GetPixelIDTypeAsString() else img, sitk.sitkInt16)
            for k in img.GetMetaDataKeys():                          # pixels and geometry only
                img.EraseMetaData(k)
            n, j = name, 2
            while n in used:
                n, j = "%s_%d" % (name, j), j + 1
            used.add(n)
            sitk.WriteImage(img, ctx.output("cases", "%s/ct.nii.gz" % n), True)
            sp = img.GetSpacing()
            ctx.log("%s: %d x %d x %d voxels of %.2f x %.2f x %.2f mm, values %d to %d." % ((n,) + img.GetSize() + sp + (lo, hi)))
            if kind == "dicom":
                v["case"] = n
                if v.get("gaps"):
                    ctx.log("%s: the slices are not evenly spaced (missing images?): check the result." % n)
                if v["kind"] == "CT" and lo > -200:
                    ctx.log("%s: no value below %d: not in Hounsfield units? The CT on the cut and the skin expect HU." % (n, lo))
            cases.append({"case": n, "size": list(img.GetSize()), "spacing_mm": [round(x, 2) for x in sp]})
        except Exception as e:
            nm = v["label"] if kind == "dicom" else v[1]
            ctx.log("%s could not be read: %s" % (nm, e))
            if kind == "dicom":
                v["why"] = "could not be read: %s" % str(e)[:120]
    return cases


def stats(img):
    import SimpleITK as sitk
    f = sitk.MinimumMaximumImageFilter()
    f.Execute(img)
    return int(f.GetMinimum()), int(f.GetMaximum())


def write_table(ctx, found):
    fields = ["series", "study", "number", "description", "modality", "images", "slice_mm", "step_mm", "extent_mm",
              "axial", "folders", "case", "result"]
    with open(ctx.output("series", "series.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for s in found["series"]:
            w.writerow({"series": s.get("label", ""), "study": s.get("study_n", ""), "number": s["number"],
                        "description": s["desc"], "modality": s["modality"], "images": s["images"],
                        "slice_mm": s["thick"] or "", "step_mm": s.get("step", ""), "extent_mm": s.get("extent", ""),
                        "axial": "yes" if s.get("axial") else "", "folders": len(s["folders"]),
                        "case": s.get("case", ""), "result": s["why"] + ("; " + s["note"] if s.get("note") else "")})


def public(found):
    return [{"series": s.get("label", ""), "number": s["number"], "description": s["desc"], "modality": s["modality"],
             "images": s["images"], "slice_mm": s["thick"], "case": s.get("case", ""), "result": s["why"]}
            for s in found["series"]]


# ── receiving files from the Load a CT view ──────────────────────────────────────────────────────────────────────
def tell(ctx, state, **extra):
    msg = {"state": state, "t": time.time()}
    msg.update(extra)
    try:
        ctx.telemetry(TELE, msg)
    except Exception:
        pass


def receive(ctx, wait_s):
    """Takes the files the view sends: begin (how many), file (each one's path and size), put (its pieces, base64,
    gzip when gz), end; tells the view what arrived, and which files to send again (missing). Returns the folder."""
    if not hasattr(ctx, "messages"):
        raise RuntimeError("This worker cannot receive files from the view (it needs a newer EsaSim worker): put the "
                           "scans in a dataset or a worker's folder instead.")
    root = os.path.join(ctx.folder, "received")
    os.makedirs(root, exist_ok=True)
    files, session, ended, count, t_start = {}, None, False, 0, time.time()
    heard = time.time()
    beat = said = 0.0
    ctx.log("Waiting for the scans from the Load a CT view (up to %d minutes)…" % (wait_s // 60))
    ctx.progress(0, "Waiting for the scans from the View")
    while True:
        for m in ctx.messages(CHANNEL):
            heard = time.time()
            m = m.get("data", m) if isinstance(m, dict) and "data" in m and "cmd" not in m else getattr(m, "data", m)
            if isinstance(m, (bytes, str)):
                try:
                    m = json.loads(m)
                except ValueError:
                    continue
            if not isinstance(m, dict):
                continue
            cmd = m.get("cmd")
            try:
                if cmd == "begin":                                   # a new upload: how many files will come
                    session = str(m.get("session") or "")[:40]
                    files, count, ended = {}, int(m.get("count") or 0), False
                    ctx.log("The view is sending %d files (%.1f MB before compression)." % (count, float(m.get("bytes") or 0) / 1e6))
                    beat = 0
                elif cmd == "file" and str(m.get("session") or "") == session:   # one file: its path and size
                    i = int(m["i"])
                    if i not in files:
                        rel = clean_rel(m.get("rel") or m.get("name") or str(i))
                        f = files[i] = {"rel": rel, "size": int(m["size"]), "gz": bool(m.get("gz")), "got": {},
                                        "path": os.path.join(root, rel + (".gzpart" if m.get("gz") else ""))}
                        os.makedirs(os.path.dirname(f["path"]), exist_ok=True)
                        with open(f["path"], "wb") as fh:
                            fh.truncate(f["size"])
                elif cmd == "put" and str(m.get("session") or "") == session:
                    f = files.get(int(m["i"]))
                    if f is None:
                        continue
                    off, raw = int(m.get("off") or 0), base64.b64decode(m.get("data") or "")
                    if off < 0 or off + len(raw) > f["size"]:
                        continue
                    with open(f["path"], "r+b") as fh:
                        fh.seek(off)
                        fh.write(raw)
                    f["got"][off] = len(raw)
                elif cmd == "end" and str(m.get("session") or "") == session:
                    ended = True
                    beat = 0
                elif cmd == "cancel":
                    raise RuntimeError("The upload was cancelled in the view.")
                elif cmd == "hello":
                    beat = 0
            except RuntimeError:
                raise
            except Exception as e:
                ctx.log("A message could not be used: %s" % e)
        got = {i: sum(f["got"].values()) >= f["size"] for i, f in files.items()}
        for i in range(count):
            got.setdefault(i, False)                                 # announced, never declared: missing
        total = sum(f["size"] for f in files.values())
        have = sum(min(f["size"], sum(f["got"].values())) for f in files.values())
        if ended and count and all(got.values()):
            break
        now = time.time()
        if now - beat > (0.5 if session else 2.0):                  # (every 2 s while it waits, faster while files come)
            missing = [i for i, ok in got.items() if not ok] if ended else []
            tell(ctx, "receiving" if session else "waiting", session=session, files=count,
                 received=sum(got.values()), bytes=have, total=total, missing=missing[:2000])
            if session:
                ctx.progress(30.0 * sum(got.values()) / max(1, count), "Receiving: %d of %d files" % (sum(got.values()), count))
            beat = now
        if not session and now - t_start > wait_s:
            raise RuntimeError("No scans arrived from the view in %d minutes: open the View, choose the folder in "
                               "Load a CT, and press Load while the run is going." % (wait_s // 60))
        if session and now - heard > wait_s:
            raise RuntimeError("The view stopped sending (nothing for %d minutes; the page was closed?): %d of %d files "
                               "arrived. Load again." % (wait_s // 60, sum(got.values()), count))
        if session and now - said > 60:
            ctx.log("Received %d of %d files (%.0f MB)…" % (sum(got.values()), count, have / 1e6))
            said = now
        time.sleep(0.05)
    for f in files.values():                                         # unpack the compressed ones
        if f["gz"]:
            with gzip.open(f["path"], "rb") as src, open(f["path"][:-len(".gzpart")], "wb") as dst:
                shutil.copyfileobj(src, dst)
            os.remove(f["path"])
    tell(ctx, "received", session=session, files=len(files), received=len(files), bytes=total, total=total)
    ctx.log("All %d files arrived (%.1f MB)." % (len(files), total / 1e6))
    return root


def clean_rel(rel):
    parts = [safe_part(x) for x in re.split(r"[\\/]+", str(rel)) if x not in ("", ".", "..")]
    return "/".join(x for x in parts if x)[:400] or "file"


def safe_part(x):
    return re.sub(r"[^A-Za-z0-9._ -]", "_", x).strip(" .")[:120]


# ── small things ─────────────────────────────────────────────────────────────────────────────────────────────────
def num(v, default):
    try:
        if v is None or v == "":
            return default
        return type(default)(float(v)) if isinstance(default, int) else float(v)
    except (TypeError, ValueError):
        return default


def stem(n):
    for e in VOL_EXT:
        if n.lower().endswith(e):
            return n[: -len(e)]
    return n


def safe(n):
    return re.sub(r"_+", "_", "".join(ch if ch.isalnum() or ch in ".-" else "_" for ch in str(n))).strip("_")[:80] or "case"


def rel_of(f):
    if getattr(f, "rel", None):
        return f.rel.replace("\\", "/")
    path = (f.path or "").replace("\\", "/")
    key = "/outputs/%s/" % (getattr(f, "from_port", "") or "")
    i = path.rfind(key)
    return path[i + len(key):] if getattr(f, "from_port", None) and i >= 0 else f.name
