# ── EsaSim block ──────────────────────────────────────────────────────
# Soft body model (skin inside) (ws-soft-body-model-skin-inside) · version 5 · worker block, Python: def run(ctx)
# Turns segmented anatomy into a soft-tissue model the 3D view simulates in real time: organs that sag, sway and push each other under gravity, held by a fixed skeleton and contained by the skin (metaba
# Workspace: Gianluca De Novi's workspace · Author: Gianluca De Novi
# Saved: 2026-11-27
#
# Inputs   ctx.inputs["id"] is a list of files: .path .name .size .read_text() .read_json()
#   labels      Files (gz, nii, nrrd, mha) Labels · several · Masks, one file per structure, in each case's segmentations/ folder
#   scans       Files (gz, nii, nrrd, mha) Scans · several · optional · The CT of each case, for the skin (the body's outline)
#   tissues     Table (csv)               Tissues · several · optional · Optional: tissue, match (words of structure names, separated by ;), E (Pa), density (kg/m3), damping
# Outputs  ctx.output("id", "name.ext") is the path to write; ctx.write_json / ctx.write_text
#   model       Files (json)              Soft body · <case>/<case>_softbody.json (esasim.softbody/1): bodies of spheres, links, tissues, the skin and its surface
#   table       Table (csv)               Structures · softbody.csv: case, structure, tissue, fixed, spheres, bone_links, volume_ml, mass_g, E_pa, density
#   telemetry   Live telemetry            ctx.telemetry("channel", data) while it runs
# Settings ctx.params["key"]
#   structures  text      Soft structures = ""
#   spheres     number    Spheres per structure = 40
#   bone_spheres number    Spheres per bone = 0
#   chest_wall  bool      Close the chest wall = true
#   coverage    number    Coverage (%) = 85
#   skin        bool      Skin = true
#   skin_spacing number    Skin spacing (mm) = 40
#   body_hu     number    Body threshold (HU) = -300
#   physics     bool      Physics = true
# Runs on  Any worker. Return a dict to fill the "result" output.
# Packages numpy, scipy, scikit-image, trimesh, fast-simplification, SimpleITK (installed by the worker with pip when missing)
# EsaSim rewrites these lines from the block's definition each time it is saved: change the definition, not them.
# ── end of EsaSim block header ────────────────────────────────────────

"""Soft body model: the anatomy of a case as a soft-tissue model for real-time simulation, following the metaball method
of Gianluca De Novi, PhD (PhD thesis "Soft Tissue Modeling for Virtual Reality Surgery Simulator with Haptic Feedback", University
of Bologna, 2011, https://amsdottorato.unibo.it/id/eprint/3702/1/DeNovi_Gianluca_tesi.pdf): each structure's volume is approximated by a tree of spheres
(medial axis approximation), the sphere centres are particles joined by elastic links, and the skeleton is fixed. A skin
layer, from the body's outline in the CT, contains the organs. The 3D view simulates it under gravity."""
import csv
import fnmatch
import json
import os
import time

EXT = (".nii.gz", ".nii", ".nrrd", ".nhdr", ".mha", ".mhd")
MASK_DIRS = ("segmentations", "segmentation", "masks", "mask", "labels", "label")
SKELETON = ("vertebra", "rib_", "sternum", "skull", "femur", "humerus", "scapula", "clavicula", "clavicle", "hip_", "sacrum", "costal",
            "bone", "patella", "tibia", "fibula", "ulna", "radius", "mandible")
# Tissue classes: Young's modulus E (Pa), density (kg/m3), damping ratio. Where an in-vivo measurement of healthy tissue
# exists, E follows it (shear-wave ultrasound elastography, which reports Young's modulus in kPa):
#   liver 3.9-4.7 kPa, spleen 19.4-23.0 kPa, pancreas 5.2-7.6 kPa: Viceconti N. et al., World J Radiol 2025;17(11):111651
#   kidney (renal cortex) 5.0 kPa, thyroid 11.0 kPa, relaxed muscle 10.4-11.1 kPa: Arda K. et al., AJR 2011 (532-536)
# (a study of the same method found the spleen far softer, 2.9 kPa: values differ between devices and studies).
# Others are orders of magnitude from the literature: brain 1-3 kPa, inflated lung a few kPa, passive heart muscle tens of
# kPa, artery walls hundreds of kPa. Elastography measures small deformations of living tissue: the model uses the values
# as they are, so organs differ from each other as measured; the motion stays plausible, not validated.
TISSUES = [
    ("vessel", ("aorta", "artery", "arteries", "vena", "vein", "trunk", "portal"), 300000, 1060, 0.5),
    ("heart", ("heart", "atrial", "myocardium"), 30000, 1060, 0.5),
    ("lung", ("lung",), 3000, 300, 0.6),
    ("airway", ("trachea", "bronch"), 100000, 1000, 0.5),
    ("liver", ("liver",), 4500, 1060, 0.45),
    ("spleen", ("spleen",), 20000, 1054, 0.45),
    ("kidney", ("kidney",), 5000, 1050, 0.45),
    ("pancreas", ("pancreas",), 6000, 1045, 0.5),
    ("thyroid", ("thyroid",), 11000, 1050, 0.5),
    ("hollow organ", ("stomach", "bowel", "colon", "duodenum", "esophagus", "rectum"), 3000, 1040, 0.55),
    ("sac", ("gallbladder", "bladder", "cyst"), 2000, 1020, 0.6),
    ("gland", ("adrenal", "prostate"), 6000, 1050, 0.5),
    ("nerve", ("spinal_cord", "brain"), 2000, 1040, 0.6),
    ("muscle", ("gluteus", "iliopsoas", "autochthon", "muscle", "psoas"), 11000, 1060, 0.5),
    ("soft tissue", ("",), 5000, 1050, 0.5),
]
LINK_E = {"connective": 1500, "anchor": 8000, "skin": 40000, "subcutaneous": 3000, "attachment": 30000}
KINDS = ["body", "cross", "connective", "anchor", "skin", "subcutaneous", "attachment"]
ATTACH_MM = 6.0                                                     # a muscle's sphere is attached to the bones it touches or nearly touches (within this gap)
ATTACH_MOST = 4                                                     # to at most this many bone spheres
BONE_MOST = 800                                                     # spheres per bone at most, when set to automatic
BONE_MIN_MM = 2.0                                                   # bones: no sphere smaller than this (the last crumbs of coverage)
RIBCAGE = ("rib_", "costal", "sternum")                             # the chest wall is closed between these
WALL_GAP_MM = 45.0                                                  # neighbouring ribs closer than this are joined by a wall of spheres
MIN_ML = 1.0                                                        # soft structures smaller than this are left out
SKIN_MM = 3.0                                                       # skin thickness (epidermis and dermis), for its mass
SKIN_DENSITY = 1100.0


def run(ctx):
    import numpy as np
    import SimpleITK as sitk
    p = ctx.params
    pats = [x.strip().lower() for x in str(p.get("structures") or "").split(",") if x.strip()]
    most = max(4, int(p.get("spheres") or 40))
    bone_most = int(p.get("bone_spheres") or 0)                      # 0: as many as each bone needs to be covered
    bone_most = BONE_MOST if bone_most <= 0 else max(2, bone_most)
    wall_on = bool(p.get("chest_wall", True))
    coverage = float(p.get("coverage") or 85) / 100.0
    skin_on = bool(p.get("skin", True))
    skin_mm = max(8.0, float(p.get("skin_spacing") or 40))
    hu = float(p.get("body_hu") if p.get("body_hu") is not None else -300)
    tissues = read_tissues(ctx.inputs.get("tissues", []))
    files, seen = [], set()
    for f in ctx.inputs.get("labels", []) + ctx.inputs.get("scans", []):     # the same files may come on both inputs
        if f.name.lower().endswith(EXT) and os.path.abspath(f.path) not in seen:
            seen.add(os.path.abspath(f.path))
            files.append(f)
    if not files:
        raise RuntimeError("No labels: connect the masks of each case (segmentations/ folders) or label maps, and the CT scans for the skin.")
    cases = {}
    for f in files:
        parts = rel_of(f).split("/")
        folder = parts[:-1]
        if folder and folder[-1].lower() in MASK_DIRS:
            cases.setdefault("/".join(folder[:-1]) or folder[-1], {"masks": [], "scans": []})["masks"].append(f)
        else:
            cases.setdefault("/".join(folder) or stem(parts[-1]), {"masks": [], "scans": []})["scans"].append(f)
    t0, out_rows = time.time(), []
    for case in sorted(cases):
        c = cases[case]
        if not c["masks"]:
            continue
        cid = case.rsplit("/", 1)[-1]
        ref, bodies, small = None, [], []
        for f in sorted(c["masks"], key=lambda g: g.name):
            name = stem(f.name)
            img = sitk.ReadImage(f.path)
            a = sitk.GetArrayFromImage(img) > 0
            if not a.any():
                continue
            if ref is None:
                ref = img
            bone = any(k in name.lower() for k in SKELETON)
            if not bone and pats and not any(fnmatch.fnmatch(name.lower(), x) for x in pats):
                continue
            t = tissue_of(name, tissues)
            ml = float(a.sum()) * float(np.prod(img.GetSpacing())) / 1000.0
            if not bone and ml < MIN_ML:                                 # a sliver (a structure the scan cuts off): no surface to move, and too light to simulate well
                small.append("%s (%.2g ml)" % (name, ml))
                continue
            sph = sphere_tree(a, img, bone_most if bone else most, max(coverage, 0.97) if bone else coverage, 1 if bone else 2, BONE_MIN_MM if bone else 0.0)
            if not sph:
                continue
            # the structure's real volume (its voxels), and its mass: density x volume, shared by its spheres in
            # proportion to their volumes (the 3D view does this), so the spheres weigh what the organ weighs
            rho = 1900.0 if bone else float(t[3])
            bodies.append({"name": name, "fixed": bone, "tissue": "bone" if bone else t[0], "spheres": sph,
                           "volume_ml": round(ml, 1), "mass_kg": round(rho * ml * 1e-6, 6)})
            ctx.progress(80.0 * len(bodies) / max(1, len(c["masks"])), "%s: %s" % (cid, name))
        if small:
            ctx.log("%s: left out, smaller than %g ml (as in Labels to 3D models): %s." % (cid, MIN_ML, ", ".join(small)))
        if not bodies:
            continue
        nb = [b for b in bodies if b["fixed"]]
        if nb:
            ctx.log("%s: %d bones, %d spheres (%s)." % (cid, len(nb), sum(len(b["spheres"]) for b in nb),
                    ", ".join("%s %d" % (b["name"], len(b["spheres"])) for b in sorted(nb, key=lambda b: -len(b["spheres"]))[:6])))
        if wall_on:
            wall = chest_wall(bodies)
            if wall:
                bodies.append(wall)
                ctx.log("%s: the chest wall between the ribs (intercostal muscles, not segmented) closed by %d fixed spheres: the lungs cannot slip out between the ribs." % (cid, len(wall["spheres"])))
        skin = None
        scans = [f for f in c["scans"] if is_scan(f.path)]
        if skin_on and scans:
            skin = skin_shell(sitk.ReadImage(scans[0].path), hu, skin_mm, ctx.log)
        model = assemble(bodies, skin, tissues)
        model["case"] = cid
        model["physics"] = bool(p.get("physics", True))
        path = ctx.output("model", "%s/%s_softbody.json" % (cid, cid))
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(model, fh, separators=(",", ":"))
        soft = [b for b in model["bodies"] if not b["fixed"]]
        ctx.log("%s: mass of the soft tissue %.1f kg (organs %.1f kg, skin %.1f kg); each sphere weighs its share of its structure, in proportion to its volume." % (
            cid, sum(b["mass_kg"] for b in soft), sum(b["mass_kg"] for b in soft if b["name"] != "skin"), sum(b["mass_kg"] for b in soft if b["name"] == "skin")))
        n_sph = sum(len(b["spheres"]) for b in model["bodies"])
        ctx.log("%s: %d soft structures, %d fixed (skeleton)%s; %d spheres, %d links (%.1f MB)." % (
            cid, len(soft) - (1 if skin else 0), len(model["bodies"]) - len(soft), ", a skin of %d points" % len(skin["points"]) if skin else "",
            n_sph, len(model["links"]), os.path.getsize(path) / 1e6))
        ka = KINDS.index("attachment")
        bone_links = {}
        for l in model["links"]:
            if l[3] == ka:
                for e in (l[0], l[1]):
                    bi = next(k for k, b in enumerate(model["bodies"]) if b["first"] <= e < b["first"] + len(b["spheres"]))
                    bone_links[bi] = bone_links.get(bi, 0) + 1
        musc = [b["name"] for k, b in enumerate(model["bodies"]) if not b["fixed"] and bone_links.get(k)]
        ctx.log("%s: %d links tie the muscles to the bones where they meet (%s)." % (cid, model.get("attachments", 0), ", ".join(musc) or "no muscle touches a bone"))
        for k, b in enumerate(model["bodies"]):
            out_rows.append({"case": cid, "structure": b["name"], "tissue": b["tissue"], "fixed": "yes" if b["fixed"] else "",
                             "spheres": len(b["spheres"]), "bone_links": bone_links.get(k, 0), "volume_ml": b.get("volume_ml", ""),
                             "mass_g": round(b["mass_kg"] * 1000.0, 1) if b.get("mass_kg") is not None else "", "E_pa": model["tissues"].get(b["tissue"], {}).get("E", ""),
                             "density": model["tissues"].get(b["tissue"], {}).get("density", "")})
    if not out_rows:
        raise RuntimeError("No structure: connect masks in segmentations/ folders (or check Structures).")
    with open(ctx.output("table", "softbody.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)
    return {"structures": len(out_rows), "seconds": round(time.time() - t0, 1)}


def sphere_tree(mask, img, most, coverage, step, min_mm=0.0):
    """Spheres filling a structure: the deepest point of what is not yet covered, with the radius of its distance to the
    surface, again and again (a medial axis approximation), until most of the volume is covered."""
    import numpy as np
    from scipy import ndimage
    sp = np.array(img.GetSpacing(), float)[::-1]                    # (z, y, x) mm
    sl = ndimage.find_objects(mask.astype(np.uint8))[0]
    m = mask[sl][::step, ::step, ::step]
    if m.sum() < 4:
        m = mask[sl]
        step = 1
    vsp = sp * step
    dt = ndimage.distance_transform_edt(m, sampling=vsp)
    left = dt.copy()
    total = float(m.sum())
    covered = np.zeros(m.shape, bool)
    ncov = 0
    zz, yy, xx = [np.arange(n) * s for n, s in zip(m.shape, vsp)]
    out = []
    min_r = max(float(vsp.min()) * 0.8, min_mm)
    while len(out) < most:
        i = int(np.argmax(left))
        r = float(dt.flat[i])
        if r < min_r or left.flat[i] <= 0:
            break
        z, y, x = np.unravel_index(i, m.shape)
        cz, cy, cx = zz[z], yy[y], xx[x]
        rr = r * 1.15                                               # spheres overlap a little: a continuous body
        lo = [max(0, int((c - rr) / s)) for c, s in zip((cz, cy, cx), vsp)]
        hi = [min(n, int((c + rr) / s) + 2) for c, s, n in zip((cz, cy, cx), vsp, m.shape)]
        d2 = ((zz[lo[0]:hi[0], None, None] - cz) ** 2 + (yy[None, lo[1]:hi[1], None] - cy) ** 2 + (xx[None, None, lo[2]:hi[2]] - cx) ** 2)
        inside = d2 <= rr * rr
        box = covered[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]]
        new = inside & m[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]] & ~box
        ncov += int(new.sum())                                       # counted where it changes, not over the whole volume each time
        box |= new
        left[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]][inside] = 0
        ijk = (np.array([z, y, x], float) * step + [s.start for s in sl])[::-1]
        out.append((ijk, r))
        if ncov >= coverage * total:
            break
    return [to_gltf(img, ijk) + [round(r / 1000.0, 4)] for ijk, r in out]


def chest_wall(bodies):
    """The intercostal spaces are not segmented: between neighbouring ribs (and the costal cartilages and the sternum) the
    chest wall is closed by fixed spheres, from the surface of each rib sphere across the gap to its neighbour's, so the
    lungs and the organs under the ribs cannot slip out between them."""
    import numpy as np
    from scipy.spatial import cKDTree
    cage = [b for b in bodies if b["fixed"] and any(k in b["name"].lower() for k in RIBCAGE)]
    if len(cage) < 2:
        return None
    trees = [(b, cKDTree(np.array([s[:3] for s in b["spheres"]])), np.array([s[3] for s in b["spheres"]])) for b in cage]
    out, seen, maxd = [], set(), WALL_GAP_MM / 1000.0
    for bi, b in enumerate(cage):
        for s in b["spheres"]:
            c, r = np.array(s[:3]), s[3]
            near = []
            for bj, (b2, t2, r2) in enumerate(trees):
                if bj == bi:
                    continue
                d, j = t2.query(c)
                if d < maxd:
                    near.append((d, bj, j))
            for d, bj, j in sorted(near)[:2]:                           # the rib above and the rib below
                c2, rj = np.array(cage[bj]["spheres"][j][:3]), float(trees[bj][2][j])
                gap = d - r - rj
                if gap <= 0.001:
                    continue
                rf = min(max(min(r, rj), 0.004), 0.008)                  # 4 to 8 mm
                u = (c2 - c) / d
                k = int(np.ceil(gap / (1.4 * rf)))
                for m in range(1, k + 1):
                    q = c + u * (r + gap * m / (k + 1.0))
                    key = tuple(np.floor(q / (rf * 1.2)).astype(int))    # one sphere per small cell: no piles where pairs cross
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append([round(float(v), 4) for v in q] + [round(float(rf), 4)])
    if not out:
        return None
    return {"name": "chest wall (between the ribs)", "fixed": True, "tissue": "bone", "spheres": out, "volume_ml": 0.0, "mass_kg": 0.0, "virtual": True}


def to_gltf(img, ijk):
    """Index (i, j, k) -> physical LPS (mm) -> glTF metres (x = patient left, y = head, z = front), as Labels to 3D models."""
    import numpy as np
    d = np.array(img.GetDirection(), float).reshape(3, 3)
    lps = np.array(img.GetOrigin(), float) + (np.asarray(ijk, float) * np.array(img.GetSpacing(), float)) @ d.T
    return [round(float(v) / 1000.0, 4) for v in (lps[0], lps[2], -lps[1])]


def skin_shell(ct, hu, spacing_mm, log):
    """The body's outline in the CT (above body_hu, the largest piece, holes filled): points on its surface, every
    spacing_mm, and a light surface mesh to draw. Points on the top and bottom cut of the scan are fixed: the body goes on."""
    import numpy as np
    import SimpleITK as sitk
    from scipy import ndimage
    from skimage import measure
    a = sitk.GetArrayFromImage(ct)
    sp = np.array(ct.GetSpacing(), float)[::-1]
    step = max(1, int(round(4.0 / sp.min())))                       # about 4 mm voxels are enough for the outline
    b = a[::step, ::step, ::step] > hu
    lab, n = ndimage.label(b)
    if n == 0:
        return None
    sizes = ndimage.sum(b, lab, range(1, n + 1))
    b = lab == (1 + int(np.argmax(sizes)))
    for k in range(b.shape[0]):                                      # air in the lungs and the bowel is inside the body
        b[k] = ndimage.binary_fill_holes(b[k])
    b = ndimage.binary_closing(b, iterations=2)
    vsp = sp * step
    pad = np.pad(b, 1).astype(np.float32)
    verts, faces, nrm, _ = measure.marching_cubes(ndimage.gaussian_filter(pad, 0.8), 0.5, step_size=1, allow_degenerate=False)
    ijk = ((verts - 1.0) * step)[:, ::-1]
    d = np.array(ct.GetDirection(), float).reshape(3, 3)
    lps = np.array(ct.GetOrigin(), float) + (ijk * np.array(ct.GetSpacing(), float)) @ d.T
    pts = np.column_stack([lps[:, 0], lps[:, 2], -lps[:, 1]]) / 1000.0
    # outward normals (the field's descent, from the body to the air), in the same frame
    g = (nrm / vsp)[:, ::-1] @ d.T
    nr = np.column_stack([g[:, 0], g[:, 2], -g[:, 1]])
    nr /= np.maximum(1e-9, np.linalg.norm(nr, axis=1))[:, None]
    if float(np.mean(np.sum((pts - pts.mean(axis=0)) * nr, axis=1))) < 0:
        nr = -nr
    # points every spacing_mm on the surface (a grid of cells, the point nearest each cell's centre)
    cell = spacing_mm / 1000.0
    keys = np.floor(pts / cell).astype(np.int64)
    order = np.lexsort(keys.T)
    seen, idx = set(), []
    for i in order:
        k = tuple(keys[i])
        if k not in seen:
            seen.add(k)
            idx.append(i)
    # the skin's metaballs lie inside the skin: each touches the outline from inside at its point (centre = point - normal
    # x radius); neighbours overlap (radius 0.6 x spacing), so their iso-surface follows the outline and nothing sits outside
    rad = 0.6 * spacing_mm / 1000.0
    shell = pts[idx] - nr[idx] * rad
    shell_n = nr[idx]
    zmin, zmax = (verts[:, 0].min(), verts[:, 0].max())
    cut = [bool(verts[i, 0] <= zmin + 1.5 or verts[i, 0] >= zmax - 1.5) for i in idx]
    # the mesh to draw: lighter
    import trimesh
    mesh = trimesh.Trimesh(pts, faces, process=True)
    try:
        if len(mesh.faces) > 24000:
            mesh = mesh.simplify_quadric_decimation(face_count=24000)
    except Exception:
        pass
    trimesh.repair.fix_normals(mesh)
    log("Skin: the body's outline (CT above %g HU), %d points every %g mm, %d of them on the cut of the scan (fixed)." % (hu, len(shell), spacing_mm, sum(cut)))
    area = float(mesh.area)                                          # m2 (the scan's part of the body)
    return {"points": [[round(float(v), 4) for v in q] for q in shell], "normals": [[round(float(v), 3) for v in q] for q in shell_n], "fixed": cut, "radius": round(rad, 4), "area_m2": round(area, 4),
            "mesh": {"positions": [round(float(v), 4) for v in np.asarray(mesh.vertices).ravel()], "faces": np.asarray(mesh.faces).astype(int).ravel().tolist()}}


def assemble(bodies, skin, tissues):
    """Spheres in one list; links inside each body (touching spheres, and a second ring for shape), between touching bodies
    (connective tissue), to the fixed skeleton (anchors), and the skin: its points joined to their neighbours, to the
    skeleton and the structures under them."""
    import numpy as np
    from scipy.spatial import cKDTree
    allb = list(bodies)
    if skin:
        area = skin.get("area_m2") or 0.0
        allb.append({"name": "skin", "fixed": False, "tissue": "skin", "spheres": [q + [skin["radius"]] for q in skin["points"]], "fixed_spheres": skin["fixed"],
                     "volume_ml": round(area * SKIN_MM * 1e3, 1), "mass_kg": round(area * SKIN_MM * 1e-3 * SKIN_DENSITY, 4)})
    P, R, B = [], [], []
    for bi, b in enumerate(allb):
        b["first"] = len(P)
        for s in b["spheres"]:
            P.append(s[:3])
            R.append(s[3])
            B.append(bi)
    P, R, B = np.array(P), np.array(R), np.array(B)
    tree = cKDTree(P)
    links, seen = [], set()

    def add(i, j, kind):
        a, b = (i, j) if i < j else (j, i)
        if a == b or (a, b) in seen:
            return
        seen.add((a, b))
        links.append([int(a), int(b), round(float(np.linalg.norm(P[a] - P[b])), 4), kind])

    rmax = float(R.max())
    fixed = np.array([allb[b]["fixed"] for b in B])
    # muscles hold on to the bones where they meet them (origins and insertions: tendons, aponeuroses): each muscle sphere
    # that touches a bone, or comes within ATTACH_MM of it, is tied to the nearest bone spheres there by a stiff elastic link
    bones = np.where(fixed)[0]
    attached = 0
    if len(bones):
        bt = cKDTree(P[bones])
        rbmax = float(R[bones].max())
        for i in range(len(P)):
            if fixed[i] or allb[B[i]].get("tissue") != "muscle":
                continue
            near = []
            for k in bt.query_ball_point(P[i], R[i] + rbmax + ATTACH_MM / 1000.0):
                j = int(bones[k])
                gap = float(np.linalg.norm(P[i] - P[j])) - R[i] - R[j]
                if gap <= ATTACH_MM / 1000.0:
                    near.append((gap, j))
            for _, j in sorted(near)[:ATTACH_MOST]:
                before = len(links)
                add(i, j, "attachment")
                attached += len(links) - before
    for i in range(len(P)):
        for j in tree.query_ball_point(P[i], R[i] + rmax * 1.7):
            if j <= i:
                continue
            d = float(np.linalg.norm(P[i] - P[j]))
            touch = R[i] + R[j]
            same = B[i] == B[j]
            if same and fixed[i]:
                continue                                              # a bone is rigid: no links inside it
            if same and d <= touch * 1.05:
                add(i, j, "body")
            elif same and d <= touch * 1.6:
                add(i, j, "cross")
            elif not same and d <= touch * 1.15:
                ni, nj = allb[B[i]]["name"], allb[B[j]]["name"]
                if fixed[i] and fixed[j]:
                    continue
                if "skin" in (ni, nj):
                    other = j if ni == "skin" else i
                    if fixed[other] or allb[B[other]].get("tissue") == "muscle":
                        add(i, j, "subcutaneous")
                elif fixed[i] or fixed[j]:
                    add(i, j, "anchor")
                else:
                    add(i, j, "connective")
    # every soft body holds together: pieces joined by their nearest spheres
    for bi, b in enumerate(allb):
        if b["fixed"]:
            continue
        n = len(b["spheres"])
        f = b["first"]
        parent = list(range(n))

        def root(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        for a_, b_, _, k in links:
            if f <= a_ < f + n and f <= b_ < f + n:
                parent[root(a_ - f)] = root(b_ - f)
        groups = {}
        for k in range(n):
            groups.setdefault(root(k), []).append(k)
        gl = list(groups.values())
        while len(gl) > 1:
            g0 = gl.pop()
            best = None
            for g in gl:
                for x in g0:
                    for y in g:
                        d = np.linalg.norm(P[f + x] - P[f + y])
                        if best is None or d < best[0]:
                            best = (d, x, y, g)
            add(f + best[1], f + best[2], "body")
            best[3].extend(g0)
    # the skin: neighbours on the surface, and down to what is under it (or the nearest bone) so it hangs on the body
    if skin:
        sk = allb[-1]
        f, n = sk["first"], len(sk["spheres"])
        sp = P[f:f + n]
        st = cKDTree(sp)
        for i in range(n):
            for j in st.query(sp[i], k=min(7, n))[1][1:]:
                add(f + i, f + int(j), "skin")
        inner = np.where(B < len(allb) - 1)[0]
        if len(inner):
            it = cKDTree(P[inner])
            bones = np.where(fixed[:len(P)] & (B < len(allb) - 1))[0]
            bt = cKDTree(P[bones]) if len(bones) else None
            for i in range(n):
                d, j = it.query(sp[i])
                add(f + i, int(inner[j]), "subcutaneous")
                if bt is not None:
                    d2, j2 = bt.query(sp[i])
                    if d2 < 0.12:
                        add(f + i, int(bones[j2]), "subcutaneous")
    table = {name: {"E": E, "density": rho, "damping": z} for name, _, E, rho, z in tissues}
    table["skin"] = {"E": LINK_E["skin"], "density": SKIN_DENSITY, "damping": 0.4}
    table["bone"] = {"E": 0, "density": 1900, "damping": 0}
    out_b = []
    for b in allb:
        o = {"name": b["name"], "tissue": b["tissue"], "fixed": bool(b["fixed"]), "first": b["first"], "spheres": b["spheres"]}
        if b.get("virtual"):
            o["virtual"] = True                                         # not segmented: no surface of its own (the chest wall)
        for k in ("volume_ml", "mass_kg"):
            if b.get(k) is not None:
                o[k] = b[k]
        if b.get("fixed_spheres"):
            o["fixed_spheres"] = [i for i, x in enumerate(b["fixed_spheres"]) if x]
        out_b.append(o)
    model = {"format": "esasim.softbody/1", "method": "Metaball soft-tissue model (Gianluca De Novi, PhD, thesis \u201cSoft Tissue Modeling for Virtual Reality Surgery Simulator with Haptic Feedback\u201d, University of Bologna, 2011, https://amsdottorato.unibo.it/id/eprint/3702/1/DeNovi_Gianluca_tesi.pdf)",
             "masses": "each structure weighs density x its volume (voxels of its mask); its spheres share that mass in proportion to their volumes (r^3)",
             "frame": "glTF metres: x = patient's left, y = head, z = front (as the anatomy GLB)",
             "tissues": table, "link_E": LINK_E, "kinds": KINDS, "attachments": attached,
             "bodies": out_b, "links": [[a, b, r, KINDS.index(k)] for a, b, r, k in links]}
    if skin:
        model["skin"] = {"body": len(out_b) - 1, "mesh": skin["mesh"], "normals": skin["normals"], "inside": True}
    return model


def tissue_of(name, tissues):
    low = name.lower()
    for t in tissues:
        if any(k and k in low for k in t[1]):
            return t
    return tissues[-1]


def read_tissues(tables):
    """The default tissue classes, changed or extended by a table: tissue, match (words of structure names), E, density, damping."""
    out = [list(t) for t in TISSUES]
    for t in tables:
        if not t.name.lower().endswith(".csv"):
            continue
        with open(t.path, newline="", encoding="utf-8", errors="replace") as fh:
            for r in csv.DictReader(fh):
                r = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
                name = r.get("tissue")
                if not name:
                    continue
                try:
                    E, rho, z = float(r.get("e") or r.get("e_pa") or 0), float(r.get("density") or 1050), float(r.get("damping") or 0.4)
                except ValueError:
                    continue
                words = tuple(x.strip().lower() for x in (r.get("match") or name).split(";") if x.strip())
                row = [name, words, E, rho, z]
                old = [i for i, x in enumerate(out) if x[0] == name]
                if old:
                    out[old[0]] = row
                else:
                    out.insert(len(out) - 1, row)
    return [tuple(x) for x in out]


def is_scan(path):
    import numpy as np
    import SimpleITK as sitk
    try:
        a = sitk.GetArrayFromImage(sitk.ReadImage(path))
        return a.ndim == 3 and len(np.unique(a[::4, ::4, ::4])) > 50
    except Exception:
        return False


def stem(n):
    for e in EXT:
        if n.lower().endswith(e):
            return n[: -len(e)]
    return n


def rel_of(f):
    if getattr(f, "rel", None):
        return f.rel
    path = (f.path or "").replace("\\", "/")
    key = "/outputs/%s/" % (f.from_port or "")
    i = path.rfind(key)
    return path[i + len(key):] if f.from_port and i >= 0 else f.name
