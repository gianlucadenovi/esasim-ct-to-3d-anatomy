# ── EsaSim block ──────────────────────────────────────────────────────
# CT volume for the 3D view (ws-ct-volume-for-the-3d-view) · version 3 · worker block, Python: def run(ctx)
# Resamples a CT scan into the 3D models' own frame (as Labels to 3D models writes them) as a compact volume, so the 3D view can show the real CT on a cut.
# Workspace: Gianluca De Novi's workspace · Author: Gianluca De Novi
# Saved: 2026-11-27
#
# Inputs   ctx.inputs["id"] is a list of files: .path .name .size .read_text() .read_json()
#   scans       Files (gz, nii, nrrd, mha, mhd) Scans · several · CT volumes (NIfTI, NRRD, MHA); masks in segmentations/ folders are skipped
# Outputs  ctx.output("id", "name.ext") is the path to write; ctx.write_json / ctx.write_text
#   volume      Files (ctvol)             Volume · <case>/<case>_ct.ctvol for the 3D view's cut
#   telemetry   Live telemetry            ctx.telemetry("channel", data) while it runs
# Settings ctx.params["key"]
#   file        text      Scan file name = "ct.nii.gz"
#   size        number    Size (voxels on the longest side) = 256
# Runs on  Any worker. Return a dict to fill the "result" output.
# Packages numpy, scipy, SimpleITK (installed by the worker with pip when missing)
# EsaSim rewrites these lines from the block's definition each time it is saved: change the definition, not them.
# ── end of EsaSim block header ────────────────────────────────────────

"""CT volume for the 3D view: the scan resampled on a grid aligned with the glTF frame of the anatomy models.

Labels to 3D models writes vertices as glTF (x, y, z) = (L, S, A) in metres, from the scan's LPS millimetres:
x = L / 1000, y = S / 1000, z = -P / 1000. This block samples the CT at the centres of a regular grid in that frame,
so the 3D view can look it up with a 3D texture at any point of a model, e.g. on a cut plane.

File layout (.ctvol): b"ESCTVOL1", uint32 little-endian header length, JSON header (padded with spaces to a multiple
of 4), then the voxels: uint8, x fastest, then y, then z; zlib/gzip-compressed when header["gzip"] is true.
Header: {"dims": [nx, ny, nz], "min": [x, y, z], "max": [x, y, z]} - the grid's outer edges in metres - and the
encoding: 0 outside the body, 1..255 = HU -1024..+1536 linearly."""
import fnmatch
import gzip
import json
import math
import os
import struct
import time

MASK_DIRS = ("segmentations", "segmentation", "masks", "mask", "labels", "label")
HU_LO, HU_HI = -1024.0, 1536.0


def run(ctx):
    import numpy as np
    import SimpleITK as sitk
    from scipy import ndimage

    p = ctx.params
    pat = str(p.get("file") or "").strip().lower()
    size = int(max(64, min(512, int(p.get("size") or 256))))
    files, masks = [], {}
    for f in ctx.inputs.get("scans", []):
        rel = rel_of(f)
        parts = rel.split("/")
        if len(parts) > 1 and parts[-2].lower() in MASK_DIRS:
            if f.name.lower().endswith((".nii.gz", ".nii", ".nrrd", ".mha", ".mhd")):
                masks.setdefault(parts[-3] if len(parts) > 2 else "", []).append(f)   # the case's structures, for their colours
            continue
        if not f.name.lower().endswith((".nii.gz", ".nii", ".nrrd", ".mha", ".mhd")):
            continue
        if pat and not fnmatch.fnmatch(f.name.lower(), pat):
            continue
        files.append((f, parts))
    if not files:
        raise RuntimeError("No CT scan among the inputs (looked for %s, outside segmentation folders)." % (pat or "any scan"))
    made = []
    for n, (f, parts) in enumerate(files):
        t0 = time.time()
        case = parts[-2] if len(parts) > 1 else stem(f.name)
        img = sitk.ReadImage(f.path)
        if img.GetDimension() != 3:
            ctx.log("%s is not a 3D volume: skipped." % f.name)
            continue
        arr = sitk.GetArrayFromImage(img).astype(np.float32)            # (k, j, i)
        if arr.dtype.kind != "f" and len(np.unique(arr[::4, ::4, ::4])) < 3:
            ctx.log("%s looks like a mask: skipped." % f.name)
            continue
        sp = np.array(img.GetSpacing(), float)
        D = np.array(img.GetDirection(), float).reshape(3, 3)
        O = np.array(img.GetOrigin(), float)
        A = D @ np.diag(sp)                                              # ijk -> LPS (mm) offset
        Ainv = np.linalg.inv(A)
        ni, nj, nk = img.GetSize()
        # the scan's corners (voxel edges) in the glTF frame
        cs = np.array([[i, j, k] for i in (-0.5, ni - 0.5) for j in (-0.5, nj - 0.5) for k in (-0.5, nk - 0.5)])
        lps = O + cs @ A.T
        g = np.column_stack([lps[:, 0], lps[:, 2], -lps[:, 1]]) / 1000.0
        gmin, gmax = g.min(0), g.max(0)
        ext = gmax - gmin
        h = float(ext.max()) / size
        dims = [max(2, int(math.ceil(e / h))) for e in ext]
        gmax = gmin + np.array(dims) * h                                 # whole voxels
        nx, ny, nz = dims
        xs = gmin[0] + (np.arange(nx) + 0.5) * h
        ys = gmin[1] + (np.arange(ny) + 0.5) * h
        out = np.empty((nz, ny, nx), np.float32)
        # the structures: one label per structure (1, 2, ...) in the scan's own voxels, smaller ones over larger ones
        mlist = masks.get(case) or (masks.get("") if len(files) == 1 else None) or []
        labvol, names = None, []
        if mlist:
            labvol = np.zeros(arr.shape, np.uint8)
            sizes = [np.inf]                                             # label 0 (nothing): any structure takes it
            for mf in mlist:
                if len(names) >= 254:
                    break
                try:
                    mi = sitk.ReadImage(mf.path)
                    if mi.GetSize() != img.GetSize():
                        continue
                    m = sitk.GetArrayFromImage(mi) > 0
                    cnt = int(m.sum())
                    if not cnt:
                        continue
                    li = len(names) + 1
                    idx = np.nonzero(m)
                    cur = labvol[idx]
                    take = np.asarray(sizes, float)[cur] > cnt               # a smaller structure over a larger one
                    labvol[tuple(a[take] for a in idx)] = li
                    names.append(stem(mf.name)); sizes.append(cnt)
                except Exception:
                    pass
            if not names:
                labvol = None
            ctx.log("%s: %d structures for the colours on the cut." % (case, len(names)))
        lab = np.zeros((nz, ny, nx), np.uint8) if labvol is not None else None
        X, Y = np.meshgrid(xs, ys)                                       # (ny, nx)
        for kz in range(nz):
            Z = gmin[2] + (kz + 0.5) * h
            # glTF -> LPS (mm): L = x, P = -z, S = y
            L, P, S = X * 1000.0, np.full_like(X, -Z * 1000.0), Y * 1000.0
            pts = np.stack([L.ravel(), P.ravel(), S.ravel()], 1) - O
            ijk = pts @ Ainv.T                                           # continuous (i, j, k)
            v = ndimage.map_coordinates(arr, [ijk[:, 2], ijk[:, 1], ijk[:, 0]], order=1, mode="constant", cval=HU_LO)
            out[kz] = v.reshape(ny, nx)
            if lab is not None:                                          # the nearest voxel's structure
                ii = np.rint(ijk).astype(np.int64)
                ok = (ii[:, 0] >= 0) & (ii[:, 0] < ni) & (ii[:, 1] >= 0) & (ii[:, 1] < nj) & (ii[:, 2] >= 0) & (ii[:, 2] < nk)
                lv = np.zeros(len(ii), np.uint8)
                lv[ok] = labvol[ii[ok, 2], ii[ok, 1], ii[ok, 0]]
                lab[kz] = lv.reshape(ny, nx)
            if kz % 16 == 0:
                ctx.progress(100.0 * (n + kz / nz) / len(files), "%s: resampling %d of %d" % (case, kz, nz))
        # the body: tissue above -400 HU, the largest piece, holes (lungs, bowel gas) filled slice by slice
        body = out > -400
        body = ndimage.binary_opening(body, iterations=2)
        lab, cnt = ndimage.label(body)
        if cnt > 1:
            sizes = ndimage.sum(body, lab, range(1, cnt + 1))
            body = lab == (1 + int(np.argmax(sizes)))
        for j in range(ny):                                              # axial slices (y is up)
            body[:, j, :] = ndimage.binary_fill_holes(body[:, j, :])
        body = ndimage.binary_dilation(body, iterations=1)
        q = np.zeros(out.shape, np.uint8)
        q[body] = (1 + np.round((np.clip(out[body], HU_LO, HU_HI) - HU_LO) / (HU_HI - HU_LO) * 254)).astype(np.uint8)
        data = gzip.compress(q.tobytes(order="C"), compresslevel=6)
        ldata = gzip.compress(lab.tobytes(order="C"), compresslevel=6) if lab is not None else b""
        head = {"format": "esasim.ctvol/1", "case": case, "dims": [nx, ny, nz], "min": [round(float(x), 6) for x in gmin],
                "max": [round(float(x), 6) for x in gmax], "voxel_m": round(h, 6), "gzip": True, "data_bytes": len(data),
                "label_bytes": len(ldata), "labels": names,
                "encoding": "0 outside the body; 1..255 = HU %g..%g" % (HU_LO, HU_HI), "hu_lo": HU_LO, "hu_hi": HU_HI,
                "frame": "glTF of Labels to 3D models: x = left, y = superior, z = anterior, metres", "source": f.name}
        js = json.dumps(head, separators=(",", ":")).encode()
        js += b" " * ((4 - len(js) % 4) % 4)
        path = ctx.output("volume", "%s/%s_ct.ctvol" % (case, case))
        with open(path, "wb") as fh:
            fh.write(b"ESCTVOL1" + struct.pack("<I", len(js)) + js + data + ldata)
        mb = os.path.getsize(path) / 1e6
        ctx.log("%s: %d x %d x %d voxels of %.1f mm, %.1f%% inside the body, %.1f MB, %.0f s." % (
            case, nx, ny, nz, h * 1000, 100.0 * body.mean(), mb, time.time() - t0))
        made.append({"case": case, "dims": dims, "voxel_mm": round(h * 1000, 2), "mb": round(mb, 2)})
    if not made:
        raise RuntimeError("No CT volume could be made from the inputs.")
    return {"volumes": made}


def stem(n):
    for e in (".nii.gz", ".nii", ".nrrd", ".mha", ".mhd"):
        if n.lower().endswith(e):
            return n[: -len(e)]
    return n


def rel_of(f):
    if getattr(f, "rel", None):
        return f.rel.replace("\\", "/")
    path = (f.path or "").replace("\\", "/")
    key = "/outputs/%s/" % (getattr(f, "from_port", "") or "")
    i = path.rfind(key)
    return path[i + len(key):] if getattr(f, "from_port", None) and i >= 0 else f.name
