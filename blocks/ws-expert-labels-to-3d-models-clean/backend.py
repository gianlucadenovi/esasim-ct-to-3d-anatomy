# ── EsaSim block ──────────────────────────────────────────────────────
# Expert labels to 3D models (clean) (ws-expert-labels-to-3d-models-clean) · version 2 · worker block, Python: def run(ctx)
# Turns labelled volumes (a CT segmentation, any label map or masks) into a clean 3D model per structure: one coloured GLB scene per case for the 3D view, and STL files for 3D printing.
# Workspace: Gianluca De Novi's workspace · Author: Gianluca De Novi
# Saved: 2026-11-27
#
# Inputs   ctx.inputs["id"] is a list of files: .path .name .size .read_text() .read_json()
#   labels      Files (gz, nii, nrrd, nhdr, mha, mhd) Labels · several · A label map per case, or masks (one file per structure) in a folder such as segmentations/
#   names       Table (csv, tsv)          Names · several · optional · For label maps: id, name (and group, color as #rrggbb)
# Outputs  ctx.output("id", "name.ext") is the path to write; ctx.write_json / ctx.write_text
#   models      Files (glb)               3D scenes · <case>/<case>_anatomy.glb: every structure of the case, named, coloured and grouped, for the 3D view
#   stl         Files (stl)               STL for printing · <case>/<structure>.stl, in millimetres
#   table       Table (csv)               Models · models.csv: case, structure, group, volume_ml, triangles, pieces, watertight, open_edges, color, note (ready to print or why not)
#   telemetry   Live telemetry            ctx.telemetry("channel", data) while it runs
# Settings ctx.params["key"]
#   structures  text      Structures = ""
#   min_ml      number    Smallest (ml) = 1
#   smooth      number    Smoothing = 15
#   triangles   number    Triangles = 20000
#   scene_triangles number    Scene triangles = 300000
#   step        number    Step (voxels) = 1
#   largest     bool      Largest piece only = false
#   formats     select    Formats = "glb + stl" of glb + stl | glb | stl
# Runs on  Any worker. Return a dict to fill the "result" output.
# Packages numpy, scipy, scikit-image, trimesh, fast-simplification, SimpleITK (installed by the worker with pip when missing)
# EsaSim rewrites these lines from the block's definition each time it is saved: change the definition, not them.
# ── end of EsaSim block header ────────────────────────────────────────

"""Labels to 3D models: label volumes (one number per structure) or masks (one file per structure) become a clean 3D
model per structure: marching cubes, smoothing, fewer triangles, checked for holes. One GLB scene per case (named,
coloured, grouped: skeleton, organs, vessels…) for the 3D view, and an STL per structure for printing, in millimetres."""
import csv
import fnmatch
import hashlib
import os
import time

EXT = (".nii.gz", ".nii", ".nrrd", ".nhdr", ".mha", ".mhd")
MASK_DIRS = ("segmentations", "segmentation", "masks", "mask", "labels", "label")

# Groups and colours by name (the TotalSegmentator names and the usual anatomical words); a names table can set both.
GROUPS = [
    ("vessels", ("aorta", "artery", "arteries", "vein", "vena", "trunk", "portal", "iliac_vena", "pulmonary_vein", "venous", "vessel", "sinus")),
    ("heart", ("heart", "atrial", "atrium", "ventricle", "myocardium")),
    ("skeleton", ("vertebra", "rib_", "sternum", "skull", "femur", "humerus", "scapula", "clavicula", "clavicle", "hip_", "sacrum", "costal", "bone", "patella", "tibia", "fibula", "ulna", "radius", "mandible", "spine")),
    ("lungs and airways", ("lung", "trachea", "bronch", "airway")),
    ("muscles", ("gluteus", "iliopsoas", "autochthon", "muscle", "psoas")),
    ("organs", ("liver", "spleen", "kidney", "pancreas", "stomach", "gallbladder", "adrenal", "bladder", "prostate", "esophagus",
                "colon", "bowel", "duodenum", "thyroid", "brain", "spinal_cord", "uterus", "ovary", "rectum", "cyst", "tumor", "lesion")),
]
COLOURS = [
    ("portal", "#7d4bc9"), ("pulmonary_vein", "#c0504d"), ("pulmonary_artery", "#4f6fd1"), ("aorta", "#d1363a"), ("artery", "#d1363a"),
    ("vena", "#3a5fcd"), ("vein", "#3a5fcd"), ("trunk", "#d1363a"), ("heart", "#b02a30"), ("atrial", "#b8484d"),
    ("lung", "#f2a6b3"), ("trachea", "#cfe0ef"), ("bronch", "#cfe0ef"), ("liver", "#8b2e22"), ("spleen", "#7a2a5a"),
    ("kidney_cyst", "#e8e2a0"), ("kidney", "#a0453a"), ("pancreas", "#e3b26b"), ("stomach", "#d98a7a"), ("gallbladder", "#4f8f3a"),
    ("adrenal", "#e0a040"), ("duodenum", "#e0a58f"), ("small_bowel", "#e3ae98"), ("colon", "#c98a6b"), ("esophagus", "#d9907a"),
    ("bladder", "#e5d36b"), ("prostate", "#c58ab0"), ("thyroid", "#b85c7a"), ("brain", "#e8c3b9"), ("spinal_cord", "#f0e68c"),
    ("costal", "#d8e4e8"), ("vertebra", "#ece2cc"), ("rib", "#e8dcc4"), ("skull", "#ece2cc"), ("sacrum", "#ece2cc"), ("hip", "#e8dcc4"),
    ("femur", "#e8dcc4"), ("humerus", "#e8dcc4"), ("scapula", "#e8dcc4"), ("clavic", "#e8dcc4"), ("sternum", "#e8dcc4"),
    ("gluteus", "#b5553f"), ("iliopsoas", "#a8503a"), ("autochthon", "#b0583f"), ("muscle", "#b5553f"),
]
SEE_THROUGH = ("lung", "skin", "body", "subcutaneous", "fat")


def run(ctx):
    import numpy as np
    p = ctx.params
    pats = [x.strip().lower() for x in str(p.get("structures") or "").split(",") if x.strip()]
    min_ml = float(p.get("min_ml") if p.get("min_ml") is not None else 1)
    smooth = int(p.get("smooth") if p.get("smooth") is not None else 15)
    tri = int(p.get("triangles") or 0)
    step = max(1, int(p.get("step") or 1))
    formats = str(p.get("formats") or "glb + stl")
    largest = bool(p.get("largest", False))
    files = [f for f in ctx.inputs.get("labels", []) if f.name.lower().endswith(EXT)]
    if not files:
        raise RuntimeError("No label volumes: connect NIfTI, NRRD or MHA files (a label volume per case, or masks, one per structure).")
    names = read_names(ctx.inputs.get("names", []))

    # cases: masks are grouped by their case folder (segmentations/ belongs to the folder above it); a label volume is a case
    cases, scans, maps_in = {}, [], {}
    for f in files:
        folder = rel_of(f).split("/")[:-1]
        if not (folder and folder[-1].lower() in MASK_DIRS):
            maps_in["/".join(folder)] = maps_in.get("/".join(folder), 0) + 1
    for f in files:
        parts = rel_of(f).split("/")
        folder = parts[:-1]
        if folder and folder[-1].lower() in MASK_DIRS:          # masks: the case is the folder above segmentations/
            case, kind = "/".join(folder[:-1]) or folder[-1], "masks"
        else:                                                   # a label volume: its folder is the case (or its name)
            here = "/".join(folder)
            case, kind = (here if here and maps_in[here] == 1 else "/".join(folder + [stem(parts[-1])])), "maps"
        cases.setdefault(case, {"masks": [], "maps": []})[kind].append(f)
    rows, n_done, t0 = [], 0, time.time()
    total = sum(len(c["masks"]) or 117 * len(c["maps"]) for c in cases.values())
    for case in sorted(cases):
        c = cases[case]
        structures = []                     # (name, mask array (z, y, x) bool, image for geometry)
        for f in sorted(c["masks"], key=lambda g: g.name):
            img, arr = read(f.path)
            if arr.dtype.kind == "f" and not np.isin(np.unique(arr[::4, ::4, ::4]), (0, 1)).all():
                scans.append(rel_of(f))
                continue
            name = stem(f.name)
            if selected(name, pats) and arr.any():
                structures.append((name, arr > 0, img))
        for f in c["maps"]:
            img, arr = read(f.path)
            if arr.dtype.kind == "f" or len(np.unique(arr[::3, ::3, ::3])) > 1000:   # a scan, not labels: skipped
                scans.append(rel_of(f))
                continue
            for v in [int(x) for x in np.unique(arr) if x != 0]:
                name = names.get(v, {}).get("name") or "label_%d" % v
                if selected(name, pats):
                    structures.append((name, arr == v, img))
        if not structures:
            continue
        case_id = case.rsplit("/", 1)[-1]
        ctx.log("%s: %d structures to build." % (case_id, len(structures)))
        scene_parts = []
        for name, mask, img in structures:
            info = names_for(name, names)
            spacing = np.array(img.GetSpacing(), dtype=float)
            ml = float(mask.sum()) * float(np.prod(spacing)) / 1000.0
            row = {"case": case_id, "structure": name, "group": info["group"], "volume_ml": round(ml, 2), "color": info["color"]}
            n_done += 1
            if ml < min_ml:
                row.update({"triangles": 0, "pieces": 0, "watertight": "", "open_edges": "", "note": "smaller than %g ml: not built" % min_ml})
                rows.append(row)
                continue
            mesh = build(mask, img, step, smooth, tri, largest)
            if mesh is None:
                row.update({"triangles": 0, "pieces": 0, "watertight": "", "open_edges": "", "note": "no surface"})
                rows.append(row)
                continue
            import trimesh
            pieces = int(trimesh.graph.connected_components(mesh.face_adjacency, nodes=np.arange(len(mesh.faces)), min_len=1).__len__())
            open_edges = int(len(trimesh.grouping.group_rows(mesh.edges_sorted, require_count=1)))
            row.update({"triangles": int(len(mesh.faces)), "pieces": pieces, "watertight": "yes" if mesh.is_watertight else "no",
                        "open_edges": open_edges, "note": "ready to print" if mesh.is_watertight and pieces == 1 else
                        ("%d pieces" % pieces if mesh.is_watertight else "has holes: repair before printing")})
            rows.append(row)
            if "stl" in formats:
                mesh.export(ctx.output("stl", "%s/%s.stl" % (case_id, safe(name))))
            scene_parts.append((name, info, mesh))
            now = time.time()
            ctx.progress(100.0 * n_done / max(1, total), "%s: %s" % (case_id, name))
            ctx.telemetry("meshes", {"case": case_id, "structure": name, "done": n_done, "structures_s": round(n_done / max(1e-6, now - t0), 2)})
        budget = int(p.get("scene_triangles") or 0)
        have = sum(len(m.faces) for _, _, m in scene_parts)
        if budget and have > budget:                                   # lighter models, in proportion to their size
            k = budget / float(have)
            lighter = []
            for name, info, m in scene_parts:
                want = max(300, int(len(m.faces) * k))
                if want < len(m.faces):
                    try:
                        m = tidy(m.simplify_quadric_decimation(face_count=want))
                    except Exception:
                        pass
                lighter.append((name, info, m))
            scene_parts = lighter
            ctx.log("%s: the 3D scene is lightened from %d to %d triangles (Scene triangles); the STL files keep every triangle." % (case_id, have, sum(len(m.faces) for _, _, m in scene_parts)))
        if "glb" in formats and scene_parts:
            write_glb(ctx.output("models", "%s/%s_anatomy.glb" % (case_id, safe(case_id))), scene_parts)
        ctx.log("%s: %d models, %d triangles in all." % (case_id, len(scene_parts), sum(len(m.faces) for _, _, m in scene_parts)))
    if scans:
        ctx.log("Not labels (scans), skipped: %s%s." % (", ".join(scans[:5]), " …" if len(scans) > 5 else ""))
    if not rows:
        raise RuntimeError("No structure to build: the volumes are empty, or Structures matches none of their names.")
    fields = ["case", "structure", "group", "volume_ml", "triangles", "pieces", "watertight", "open_edges", "color", "note"]
    with open(ctx.output("table", "models.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    built = [r for r in rows if r.get("triangles")]
    return {"cases": len({r["case"] for r in rows}), "models": len(built), "ready_to_print": sum(1 for r in built if r["note"] == "ready to print"),
            "triangles": sum(r["triangles"] for r in built), "seconds": round(time.time() - t0, 1)}


def build(mask, img, step, smooth, tri, largest):
    """One structure's surface, in millimetres, in the patient's frame (as glTF wants it: y up, z towards the face)."""
    import numpy as np
    import trimesh
    from scipy import ndimage
    from skimage import measure
    if largest:
        lab, n = ndimage.label(mask)
        if n > 1:
            sizes = ndimage.sum(mask, lab, range(1, n + 1))
            mask = lab == (1 + int(np.argmax(sizes)))
    sl = ndimage.find_objects(mask.astype(np.uint8))[0]
    sub = np.pad(mask[sl], 3)                                           # closed at the edges of the scan (room for the closing)
    if min(sub.shape) < 7:
        return None
    # the labels' small gaps, forks and notches (a voxel wide) filled, so ribs, cartilages and the sternum come out whole
    sub = ndimage.binary_closing(sub, structure=ndimage.generate_binary_structure(3, 1), iterations=1)
    sub = ndimage.binary_fill_holes(sub).astype(np.float32)
    sub = ndimage.gaussian_filter(sub, 0.8)                             # a softer edge than the voxels' steps
    try:
        verts, faces, _, _ = measure.marching_cubes(sub, 0.5, step_size=step, allow_degenerate=False)
    except (ValueError, RuntimeError):
        return None
    # voxel (z, y, x) of the crop -> index (i, j, k) of the image -> physical LPS (mm) -> glTF (x = L, y = S, z = A)
    off = np.array([s.start for s in sl], dtype=float) - 3.0
    ijk = (verts + off)[:, ::-1]
    sp = np.array(img.GetSpacing(), float)
    d = np.array(img.GetDirection(), float).reshape(3, 3)
    lps = np.array(img.GetOrigin(), float) + (ijk * sp) @ d.T
    pts = np.column_stack([lps[:, 0], lps[:, 2], -lps[:, 1]]) / 1000.0          # metres, as glTF counts
    mesh = trimesh.Trimesh(pts, faces, process=True)
    mesh.remove_unreferenced_vertices()
    if smooth > 0:
        trimesh.smoothing.filter_taubin(mesh, lamb=0.5, nu=0.53, iterations=smooth)
    if tri and len(mesh.faces) > tri:
        try:
            mesh = mesh.simplify_quadric_decimation(face_count=tri)
        except Exception:
            pass                                                          # fast-simplification missing: kept as it is
    mesh = tidy(mesh)
    if mesh.volume < 0:
        mesh.invert()
    return mesh


def tidy(mesh):
    """After lightening: no degenerate or duplicate triangles, small holes filled, the triangles all wound outward."""
    import trimesh
    try:
        mesh.update_faces(mesh.nondegenerate_faces())
        mesh.update_faces(mesh.unique_faces())
        mesh.remove_unreferenced_vertices()
        mesh.merge_vertices()
        trimesh.repair.fill_holes(mesh)
    except Exception:
        pass
    trimesh.repair.fix_normals(mesh)
    return mesh


def write_glb(path, parts):
    """One scene: a node per structure under a node per group, each with its colour (lungs see-through). Positions are
    16-bit and normals 8-bit (KHR_mesh_quantization, read by three.js and most viewers): a scene of 300,000 triangles
    weighs about 3.5 MB, small enough to reach EsaSim and open in the browser."""
    import json
    import struct
    import numpy as np
    blob, views, accessors, meshes, materials, nodes, groups = bytearray(), [], [], [], [], [], {}

    def add_view(data, target, stride=None):
        while len(blob) % 4:
            blob.append(0)
        v = {"buffer": 0, "byteOffset": len(blob), "byteLength": len(data), "target": target}
        if stride:
            v["byteStride"] = stride
        blob.extend(data)
        views.append(v)
        return len(views) - 1

    for name, info, mesh in parts:
        v = np.asarray(mesh.vertices, dtype=np.float64)
        f = np.asarray(mesh.faces, dtype=np.int64)
        nrm = np.asarray(mesh.vertex_normals, dtype=np.float64)
        lo, hi = v.min(0), v.max(0)
        centre = (lo + hi) / 2.0
        half = max(1e-9, float((hi - lo).max()) / 2.0)
        q = np.round((v - centre) / half * 32767).clip(-32767, 32767).astype(np.int16)
        pos = np.zeros((len(q), 4), np.int16)
        pos[:, :3] = q
        nq = np.zeros((len(nrm), 4), np.int8)
        nq[:, :3] = np.round(nrm / np.maximum(1e-9, np.linalg.norm(nrm, axis=1, keepdims=True)) * 127).clip(-127, 127)
        idx = f.astype(np.uint16 if len(v) < 65536 else np.uint32).ravel()
        a_pos = len(accessors)
        accessors.append({"bufferView": add_view(pos.tobytes(), 34962, 8), "componentType": 5122, "count": len(q), "type": "VEC3",
                          "min": q.min(0).astype(int).tolist(), "max": q.max(0).astype(int).tolist()})
        accessors.append({"bufferView": add_view(nq.tobytes(), 34962, 4), "componentType": 5120, "normalized": True, "count": len(nq), "type": "VEC3"})
        accessors.append({"bufferView": add_view(idx.tobytes(), 34963), "componentType": 5123 if idx.dtype == np.uint16 else 5125, "count": int(idx.size), "type": "SCALAR"})
        rgb = [lin(int(info["color"][i:i + 2], 16) / 255.0) for i in (1, 3, 5)]      # glTF colours are linear
        alpha = 0.45 if any(k in name.lower() for k in SEE_THROUGH) else 1.0
        mat = {"name": name, "pbrMetallicRoughness": {"baseColorFactor": [round(c, 4) for c in rgb] + [alpha], "metallicFactor": 0.0, "roughnessFactor": 0.55}}
        if alpha < 1:
            mat.update({"alphaMode": "BLEND", "doubleSided": True})
        materials.append(mat)
        meshes.append({"name": name, "primitives": [{"attributes": {"POSITION": a_pos, "NORMAL": a_pos + 1}, "indices": a_pos + 2, "material": len(materials) - 1}]})
        s = half / 32767.0
        nodes.append({"name": name, "mesh": len(meshes) - 1, "translation": [float(x) for x in centre], "scale": [s, s, s]})
        groups.setdefault(info["group"], []).append(len(nodes) - 1)
    roots = []
    for g in sorted(groups):
        nodes.append({"name": g, "children": groups[g]})
        roots.append(len(nodes) - 1)
    while len(blob) % 4:
        blob.append(0)
    gltf = {"asset": {"version": "2.0", "generator": "EsaSim Labels to 3D models"}, "extensionsUsed": ["KHR_mesh_quantization"],
            "extensionsRequired": ["KHR_mesh_quantization"], "scene": 0, "scenes": [{"name": "anatomy", "nodes": roots}], "nodes": nodes,
            "meshes": meshes, "materials": materials, "accessors": accessors, "bufferViews": views, "buffers": [{"byteLength": len(blob)}]}
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    with open(path, "wb") as fh:
        fh.write(struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(js) + 8 + len(blob)))
        fh.write(struct.pack("<I4s", len(js), b"JSON") + js)
        fh.write(struct.pack("<I4s", len(blob), b"BIN\0") + bytes(blob))


def lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def names_for(name, names):
    low = name.lower()
    hit = next((v for v in names.values() if v.get("name", "").lower() == low), {})
    group = hit.get("group") or next((g for g, keys in GROUPS if any(k in low for k in keys)), "other")
    color = hit.get("color") or next((c for k, c in COLOURS if k in low), None)
    if not color:
        h = int(hashlib.md5(low.encode()).hexdigest()[:6], 16)
        color = "#%02x%02x%02x" % (90 + h % 140, 90 + (h >> 8) % 140, 90 + (h >> 16) % 140)
    return {"group": group, "color": color if len(color) == 7 and color.startswith("#") else "#9aa4b2"}


def read_names(tables):
    """id -> {name, group, color} from a table (id or value or label, and name; group and color optional)."""
    out = {}
    for t in tables:
        if not t.name.lower().endswith((".csv", ".tsv")):
            continue
        with open(t.path, newline="", encoding="utf-8", errors="replace") as fh:
            for r in csv.DictReader(fh, delimiter="\t" if t.name.lower().endswith(".tsv") else ","):
                r = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
                v = r.get("id") or r.get("value") or r.get("label_id") or r.get("index")
                n = r.get("name") or r.get("structure") or r.get("label")
                if v and v.lstrip("-").isdigit() and n:
                    out[int(v)] = {"name": n, "group": r.get("group", ""), "color": r.get("color", "")}
    return out


def read(path):
    import SimpleITK as sitk
    img = sitk.ReadImage(path)
    if img.GetDimension() != 3:
        raise RuntimeError("%s is not a 3D volume." % os.path.basename(path))
    return img, sitk.GetArrayFromImage(img)            # (z, y, x)


def selected(name, pats):
    if not pats:
        return True
    low = name.lower()
    g = next((g for g, keys in GROUPS if any(k in low for k in keys)), "other")
    return any(fnmatch.fnmatch(low, x) or x == g or (x.endswith("s") and x[:-1] == g) for x in pats)


def stem(n):
    for e in EXT:
        if n.lower().endswith(e):
            return n[: -len(e)]
    return n


def safe(n):
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in n)[:100] or "model"


def rel_of(f):
    if getattr(f, "rel", None):
        return f.rel
    path = (f.path or "").replace("\\", "/")
    key = "/outputs/%s/" % (f.from_port or "")
    i = path.rfind(key)
    return path[i + len(key):] if f.from_port and i >= 0 else f.name
