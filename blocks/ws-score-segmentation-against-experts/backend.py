# ── EsaSim block ──────────────────────────────────────────────────────
# Score segmentation against experts (ws-score-segmentation-against-experts) · version 1 · worker block, Python: def run(ctx)
# Compares automatic masks with expert masks of the same cases, structure by structure: Dice, volumes and their difference, and a mean per group.
# Workspace: Gianluca De Novi's workspace · Author: Gianluca De Novi
# Saved: 2026-11-27
#
# Inputs   ctx.inputs["id"] is a list of files: .path .name .size .read_text() .read_json()
#   auto        Files (gz, nii, nrrd, mha) Automatic · several · <case>/segmentations/<structure>.nii.gz from the network
#   experts     Files (gz, nii, nrrd, mha) Experts · several · <case>/segmentations/<structure>.nii.gz drawn by experts
# Outputs  ctx.output("id", "name.ext") is the path to write; ctx.write_json / ctx.write_text
#   table       Table (csv)               Score per structure · score.csv: case, structure, group, dice, expert_ml, auto_ml, volume_diff_pct, note
#   summary     Metrics (json)            Summary · summary.json: mean and median Dice, overall and per group
#   telemetry   Live telemetry            ctx.telemetry("channel", data) while it runs
# Settings ctx.params["key"]
#   min_ml      number    Smallest (ml) = 0.5
# Runs on  Any worker. Return a dict to fill the "result" output.
# Packages numpy, SimpleITK (installed by the worker with pip when missing)
# EsaSim rewrites these lines from the block's definition each time it is saved: change the definition, not them.
# ── end of EsaSim block header ────────────────────────────────────────

"""Score segmentation against experts: Dice and volume per structure, for every case both sides have."""
import csv
import json
import os

EXT = (".nii.gz", ".nii", ".nrrd", ".mha")
MASK_DIRS = ("segmentations", "segmentation", "masks", "mask", "labels", "label")
GROUPS = [
    ("vessels", ("aorta", "artery", "arteries", "vein", "vena", "trunk", "portal", "venous", "vessel", "sinus")),
    ("heart", ("heart", "atrial", "atrium", "ventricle", "myocardium")),
    ("skeleton", ("vertebra", "rib_", "sternum", "skull", "femur", "humerus", "scapula", "clavicula", "hip_", "sacrum", "costal", "bone")),
    ("lungs and airways", ("lung", "trachea", "bronch", "airway")),
    ("muscles", ("gluteus", "iliopsoas", "autochthon", "muscle", "psoas")),
]


def run(ctx):
    import numpy as np
    import SimpleITK as sitk
    min_ml = float(ctx.params.get("min_ml") if ctx.params.get("min_ml") is not None else 0.5)
    auto, expert = masks_of(ctx.inputs.get("auto", [])), masks_of(ctx.inputs.get("experts", []))
    cases = sorted(set(auto) & set(expert))
    if not cases:
        raise RuntimeError("No case on both sides: automatic cases %s, expert cases %s (they are matched by folder name)."
                           % (sorted(auto)[:5], sorted(expert)[:5]))
    rows = []
    for ci, case in enumerate(cases):
        names = sorted(set(auto[case]) | set(expert[case]))
        for i, name in enumerate(names):
            a_img = sitk.ReadImage(auto[case][name]) if name in auto[case] else None
            e_img = sitk.ReadImage(expert[case][name]) if name in expert[case] else None
            ref = e_img or a_img
            vox_ml = float(np.prod(ref.GetSpacing())) / 1000.0
            A = sitk.GetArrayFromImage(a_img) > 0 if a_img is not None else None
            E = sitk.GetArrayFromImage(e_img) > 0 if e_img is not None else None
            if A is not None and E is not None and A.shape != E.shape:
                rows.append(row(case, name, None, E.sum() * vox_ml, A.sum() * vox_ml, "different grids: not compared"))
                continue
            a_n = int(A.sum()) if A is not None else 0
            e_n = int(E.sum()) if E is not None else 0
            if max(a_n, e_n) * vox_ml < min_ml:
                continue
            inter = int(np.logical_and(A, E).sum()) if (A is not None and E is not None) else 0
            dice = 2.0 * inter / (a_n + e_n) if (a_n + e_n) else None
            note = "" if (a_n and e_n) else ("only the network found it" if a_n else "the network missed it")
            rows.append(row(case, name, dice, e_n * vox_ml, a_n * vox_ml, note))
            if i % 10 == 0:
                ctx.progress(100.0 * (ci + i / max(1, len(names))) / len(cases), "%s: %s" % (case, name))
    with open(ctx.output("table", "score.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["case", "structure", "group", "dice", "expert_ml", "auto_ml", "volume_diff_pct", "note"])
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["case"], r["dice"] if r["dice"] != "" else 2)))
    d = [r["dice"] for r in rows if r["dice"] != ""]
    summary = {"cases": len(cases), "structures": len(d),
               "mean_dice": round(float(np.mean(d)), 4) if d else None,
               "median_dice": round(float(np.median(d)), 4) if d else None,
               "dice_over_0_9": sum(1 for x in d if x >= 0.9), "missed": sum(1 for r in rows if r["note"] == "the network missed it")}
    for g in sorted({r["group"] for r in rows}):
        gd = [r["dice"] for r in rows if r["group"] == g and r["dice"] != ""]
        if gd:
            summary["mean_dice_" + g.replace(" ", "_")] = round(float(np.mean(gd)), 4)
    ctx.write_json("summary", "summary.json", summary)
    ctx.log("Mean Dice %.3f, median %.3f over %d structures of %d case(s)." % (
        summary["mean_dice"] or 0, summary["median_dice"] or 0, len(d), len(cases)))
    return summary


def row(case, name, dice, e_ml, a_ml, note):
    low = name.lower()
    group = next((g for g, keys in GROUPS if any(k in low for k in keys)), "organs")
    diff = round(100.0 * (a_ml - e_ml) / e_ml, 1) if e_ml else ""
    return {"case": case, "structure": name, "group": group, "dice": round(dice, 4) if dice is not None else "",
            "expert_ml": round(float(e_ml), 2), "auto_ml": round(float(a_ml), 2), "volume_diff_pct": diff, "note": note}


def masks_of(files):
    out = {}
    for f in files:
        parts = rel_of(f).split("/")
        if len(parts) < 3 or parts[-2].lower() not in MASK_DIRS or not f.name.lower().endswith(EXT):
            continue
        name = f.name
        for e in EXT:
            if name.lower().endswith(e):
                name = name[: -len(e)]
                break
        out.setdefault(parts[-3], {})[name] = f.path
    return out


def rel_of(f):
    if getattr(f, "rel", None):
        return f.rel.replace("\\", "/")
    path = (f.path or "").replace("\\", "/")
    key = "/outputs/%s/" % (getattr(f, "from_port", "") or "")
    i = path.rfind(key)
    return path[i + len(key):] if getattr(f, "from_port", None) and i >= 0 else f.name
