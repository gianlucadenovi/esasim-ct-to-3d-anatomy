# ── EsaSim block ──────────────────────────────────────────────────────
# Soft body model (skin inside) (ws-soft-body-model-skin-inside) · version 17 · worker block, Python: def run(ctx)
# Turns segmented anatomy into a soft-tissue model the 3D view simulates in real time: organs that sag, sway and push each other under gravity, held by a fixed skeleton and contained by the skin (metaba
# Workspace: Gianluca De Novi's workspace · Author: Gianluca De Novi
# Saved: 2026-11-28
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
SKIN_FACES = 250000                                                 # triangles of the skin drawn (detail of the body's outline)
UP = 1                                                              # the skin traced this many times finer than the scan's pixels (2: 4x the memory)
PAD_SHARE = 0.05                                                    # the pad's band: pixels with a thin line in this share of the slices or more
CLEFT_HU = 40.0                                                     # a fold's line: this much darker than the skin on both sides (HU)


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


# ── Unwrapping the skin, for painting (hair maps in the 3D view) ─────────────────────────────────────────────────────
# Cut along a seam down the back (and down the back of each leg that reaches the edge of the scan), the caps where the
# scan cuts the body left out, then laid flat in one piece on a rectangle: the top opening across the top, the two sides
# of the seam on the left and the right, the legs (or the bottom opening) along the bottom; the inside by a harmonic map
# with mean-value weights, then stretch-minimising passes. No fold-over; the body upright, its front in the middle, its
# right on the left as seen facing it. Only numpy and scipy.
def _uw_edges(F):
    import numpy as np
    e = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    return np.sort(e, axis=1)


def _uw_seam(P, F, log, open_loops=None):
    """The seam: a tree of edges down the back joining the openings of the skin. Model frame: y up (head), z to the front."""
    import numpy as np
    from scipy import sparse
    from scipy.sparse import csgraph
    n = len(P)
    E = np.unique(_uw_edges(F), axis=0)
    L = np.linalg.norm(P[E[:, 0]] - P[E[:, 1]], axis=1)
    # how far to the front each vertex is, for its height (0: the back, 1: the front)
    y, z = P[:, 1], P[:, 2]
    bins = np.clip(((y - y.min()) / 0.02).astype(int), 0, None)
    zmin = np.full(bins.max() + 1, np.inf); zmax = np.full(bins.max() + 1, -np.inf)
    np.minimum.at(zmin, bins, z); np.maximum.at(zmax, bins, z)
    front = (z - zmin[bins]) / np.maximum(1e-6, zmax[bins] - zmin[bins])
    w = L * (0.02 + 40.0 * (0.5 * (front[E[:, 0]] + front[E[:, 1]])) ** 2)   # walking along the back is cheap
    G = sparse.coo_matrix((np.concatenate([w, w]), (np.concatenate([E[:, 0], E[:, 1]]), np.concatenate([E[:, 1], E[:, 0]]))), shape=(n, n)).tocsr()
    # the openings of the skin (the scan's cut, caps left out): each one's backmost vertex is an end of the seam
    if open_loops:
        pts = [int(lp[np.argmin(front[lp])]) for lp in open_loops]
        pts.sort(key=lambda v: -P[v, 1])                         # the top one first
    else:
        pts = [int(np.argmax(y)), int(np.argmin(y))]
    log("Unwrap: seam down the back, joining %d opening(s) of the skin (where the scan cuts the body)." % len(open_loops or []))
    seam = set()
    tree = {pts[0]}
    for p in pts[1:]:
        d, pred, _src = csgraph.dijkstra(G, directed=False, indices=list(tree), return_predecessors=True, min_only=True)
        if not np.isfinite(d[p]):
            continue
        v = p
        while v not in tree and v >= 0:
            u = pred[v]
            if u < 0:
                break
            seam.add((min(u, v), max(u, v))); tree.add(v); v = u
        tree.add(p)
    return seam, front


def _uw_split(P, F, orig, which):
    """Vertices where the faces around them fall into groups joined only through the vertex (pinches): one copy each."""
    import numpy as np
    which = set(int(v) for v in which)
    if not which:
        return P, F, orig
    vf = {}
    for fi, f in enumerate(F):
        for v in f:
            if v in which:
                vf.setdefault(int(v), []).append(fi)
    newP, neworig, nxt = [P], [orig], len(P)
    F = F.copy()
    for v, faces in vf.items():
        parent = {f: f for f in faces}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]; x = parent[x]
            return x
        byw = {}
        for fi in faces:
            for w in F[fi]:
                if w != v:
                    byw.setdefault(int(w), []).append(fi)
        for fs in byw.values():
            for f2 in fs[1:]:
                ra, rb = find(fs[0]), find(f2)
                if ra != rb:
                    parent[ra] = rb
        groups = {}
        for fi in faces:
            groups.setdefault(find(fi), []).append(fi)
        for gi, fs in enumerate(groups.values()):
            if gi == 0:
                continue
            for fi in fs:
                F[fi][F[fi] == v] = nxt
            newP.append(P[v:v + 1]); neworig.append(orig[v:v + 1]); nxt += 1
    return np.concatenate(newP), F, np.concatenate(neworig)


def _uw_cut(P, F, seam):
    """Duplicate the vertices along the seam: on each side of it, the faces get their own copy."""
    import numpy as np
    F = F.copy()
    sv = {}
    for a, b in seam:
        sv.setdefault(a, []).append(b); sv.setdefault(b, []).append(a)
    vf = {}
    for fi, f in enumerate(F):
        for v in f:
            if v in sv:
                vf.setdefault(v, []).append(fi)
    newP = [P]
    nxt = len(P)
    orig = list(range(len(P)))
    for v, faces in vf.items():
        # faces around v that share a non-seam edge through v are on the same side
        parent = {f: f for f in faces}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]; x = parent[x]
            return x
        byedge = {}
        for fi in faces:
            for w in F[fi]:
                if w == v:
                    continue
                e = (min(v, w), max(v, w))
                if e in seam:
                    continue
                byedge.setdefault(w, []).append(fi)
        for w, fs in byedge.items():
            for f2 in fs[1:]:
                ra, rb = find(fs[0]), find(f2)
                if ra != rb:
                    parent[ra] = rb
        groups = {}
        for fi in faces:
            groups.setdefault(find(fi), []).append(fi)
        for gi, (_, fs) in enumerate(sorted(groups.items())):
            if gi == 0:
                continue
            for fi in fs:
                F[fi][F[fi] == v] = nxt
            newP.append(P[v:v + 1]); orig.append(v); nxt += 1
    return np.concatenate(newP), F, np.array(orig)


def _uw_lscm(P, F, pin):
    """Least-squares conformal map, two vertices pinned (when the skin has no opening)."""
    import numpy as np
    from scipy import sparse
    from scipy.sparse.linalg import spsolve
    n = len(P)
    a, b, c = P[F[:, 0]], P[F[:, 1]], P[F[:, 2]]
    e1 = b - a; e2 = c - a
    nrm = np.cross(e1, e2); area2 = np.linalg.norm(nrm, axis=1)
    ok = area2 > 1e-14
    x1 = np.linalg.norm(e1, axis=1)
    ex = e1 / np.maximum(1e-12, x1)[:, None]
    ey = np.cross(nrm / np.maximum(1e-14, area2)[:, None], ex)
    x2 = np.einsum('ij,ij->i', e2, ex); y2 = np.einsum('ij,ij->i', e2, ey)
    X = np.stack([np.zeros_like(x1), x1, x2], 1); Y = np.stack([np.zeros_like(x1), np.zeros_like(x1), y2], 1)
    s = 1.0 / np.sqrt(np.maximum(1e-14, area2))
    rows, cols, vals = [], [], []
    m = len(F)
    for j in range(3):
        k1, k2 = (j + 1) % 3, (j + 2) % 3
        wr = (X[:, k2] - X[:, k1]) * s; wi = (Y[:, k2] - Y[:, k1]) * s
        vj = F[:, j]
        t = np.arange(m)
        rows += [2 * t, 2 * t, 2 * t + 1, 2 * t + 1]
        cols += [vj, n + vj, vj, n + vj]
        vals += [wr * ok, -wi * ok, wi * ok, wr * ok]
    A = sparse.coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(2 * m, 2 * n)).tocsc()
    fixed = np.array([pin[0], pin[1], n + pin[0], n + pin[1]])
    fixval = np.array([0.0, 0.0, 0.0, 1.0])
    free = np.setdiff1d(np.arange(2 * n), fixed)
    Af, Ap = A[:, free], A[:, fixed]
    rhs = -(Ap @ fixval)
    M = (Af.T @ Af).tocsc()
    M = M + sparse.identity(M.shape[0], format='csc') * (1e-9 * float(M.diagonal().mean()))
    x = spsolve(M, Af.T @ rhs)
    out = np.zeros(2 * n); out[free] = x; out[fixed] = fixval
    return np.stack([out[:n], out[n:]], 1)


def _uw_rect(P, F, loops_orig, orig, log):
    """The cut skin (a disk) laid on a rectangle: its top opening along the top edge, the two sides of the back seam
    along the left and right edges, the other openings (legs, the bottom) along the bottom edge; the inside by a
    harmonic map with mean-value weights (positive: no fold-over), then stretch-minimising passes."""
    import numpy as np
    from scipy import sparse
    from scipy.sparse.linalg import spsolve
    n = len(P)
    E = _uw_edges(F)
    ue, cnt = np.unique(E, axis=0, return_counts=True)
    bnd = ue[cnt == 1]
    nb = {}
    for a, b in bnd:
        nb.setdefault(a, []).append(b); nb.setdefault(b, []).append(a)
    # the longest boundary loop (the cut skin's own outline)
    seen, best = set(), []
    for s in nb:
        if s in seen:
            continue
        loop, prev, cur = [s], -1, s
        seen.add(s)
        while True:
            nx = [w for w in nb[cur] if w != prev]
            if not nx:
                break
            nxt = nx[0]
            if nxt == s or nxt in seen:
                break
            loop.append(nxt); seen.add(nxt); prev, cur = cur, nxt
        if len(loop) > len(best):
            best = loop
    walk = np.array(best)
    # which opening each outline vertex is on (none: the seam)
    top_i = int(np.argmax([P[np.isin(orig, lp)][:, 1].mean() if np.isin(orig, lp).any() else -1e9 for lp in loops_orig])) if loops_orig else -1
    kind = np.full(len(walk), 0)                                   # 0 seam, 1 top opening, 2 other openings
    for i, lp in enumerate(loops_orig):
        on = np.isin(orig[walk], lp)
        kind[on] = 1 if i == top_i else 2
    if (kind == 1).any():
        k1 = np.where(kind == 1)[0]
        st = [i for i in k1 if kind[i - 1] != 1]
        walk = np.roll(walk, -st[0]); kind = np.roll(kind, -st[0])
    seg = np.linalg.norm(np.diff(P[np.r_[walk, walk[:1]]], axis=0), axis=1)
    cum = np.r_[0, np.cumsum(seg)][:len(walk)]
    tot = seg.sum()
    ntop = int((kind == 1).sum())
    # the outline's parts: top [0, a), right seam side [a, b), bottom [b, c), left seam side [c, end)
    a = ntop
    others = np.where(kind[a:] == 2)[0]
    if len(others):
        b = a + others[0]; c = a + others[-1] + 1
    else:
        mid = a + (len(walk) - a) // 2; b = c = mid
    W = (cum[a] if a < len(walk) else tot) if ntop else tot / 4
    Hr = cum[b] - cum[a] if b > a else 0.0
    Hl = (tot - cum[c]) if c < len(walk) else 0.0
    H = max(1e-6, 0.5 * (Hr + Hl))
    uvb = np.zeros((len(walk), 2))
    for i in range(len(walk)):
        t = cum[i]
        if i < a:
            uvb[i] = (W * t / max(1e-9, cum[a] if a < len(walk) else tot), H)
        elif i < b:
            uvb[i] = (W, H * (1 - (t - cum[a]) / max(1e-9, cum[b] - cum[a])))
        elif i < c:
            uvb[i] = (W * (1 - (t - cum[b]) / max(1e-9, cum[c] - cum[b])) if c > b else 0.5 * W, 0.0)
        else:
            uvb[i] = (0.0, H * (t - cum[c]) / max(1e-9, tot - cum[c]))
    # mean-value weights, their extremes capped (sliver triangles: angles near 180 degrees, edges near 0 long)
    Eall = _uw_edges(F); lmed = float(np.median(np.linalg.norm(P[Eall[:, 0]] - P[Eall[:, 1]], axis=1)))
    rows, cols, vals = [], [], []
    for j in range(3):
        i0, i1, i2 = F[:, j], F[:, (j + 1) % 3], F[:, (j + 2) % 3]
        e1 = P[i1] - P[i0]; e2 = P[i2] - P[i0]
        l1 = np.linalg.norm(e1, axis=1); l2 = np.linalg.norm(e2, axis=1)
        cosang = np.einsum('ij,ij->i', e1, e2) / np.maximum(1e-12, l1 * l2)
        th = np.clip(np.arccos(np.clip(cosang, -1, 1)), np.radians(2), np.radians(150))
        t2 = np.tan(th / 2)
        l1 = np.maximum(l1, 0.3 * lmed); l2 = np.maximum(l2, 0.3 * lmed)
        good = (l1 > 1e-9) & (l2 > 1e-9) & np.isfinite(t2)
        rows += [i0[good], i0[good]]; cols += [i1[good], i2[good]]
        vals += [(t2 / np.maximum(1e-9, l1))[good], (t2 / np.maximum(1e-9, l2))[good]]
    W0 = sparse.coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n)).tocsr()
    isb = np.zeros(n, bool); isb[walk] = True
    free = np.where(~isb)[0]
    uv = np.zeros((n, 2)); uv[walk] = uvb
    a3 = np.linalg.norm(np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]]), axis=1) / 2
    sig_acc = np.ones(n)
    # the harmonic map, then stretch-minimising passes (Yoshizawa, Belyaev and Seidel 2004): the pull towards squeezed
    # places is weakened, so they open up (between the legs)
    for it in range(7):
        if it:
            d1 = uv[F[:, 1]] - uv[F[:, 0]]; d2 = uv[F[:, 2]] - uv[F[:, 0]]
            a2 = np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) / 2
            ratio = (a3 / max(1e-12, a3.sum())) / np.maximum(1e-12, a2 / max(1e-12, a2.sum()))
            vs = np.zeros(n); va = np.zeros(n)
            for j in range(3):
                np.add.at(vs, F[:, j], np.sqrt(ratio) * a3); np.add.at(va, F[:, j], a3)
            sig_acc = np.clip(sig_acc * np.clip(vs / np.maximum(1e-12, va), 0.2, 5.0), 1e-3, 1e3)
        Wi = W0 @ sparse.diags(1.0 / sig_acc)
        Li = (sparse.diags(np.asarray(Wi.sum(axis=1)).ravel()) - Wi).tocsr()
        Lf = Li[free][:, free].tocsc(); Lb = Li[free][:, walk]
        Lf = Lf + sparse.identity(Lf.shape[0], format='csc') * (1e-12 * float(np.abs(Lf.diagonal()).mean() or 1))
        for k in range(2):
            uv[free, k] = spsolve(Lf, -(Lb @ uvb[:, k]))
    log("Unwrap: the skin laid on a rectangle %.2f x %.2f m: the top opening across the top, the back seam on both sides, %s along the bottom." % (W, H, "the legs" if len(loops_orig) > 2 else "the bottom opening" if len(loops_orig) == 2 else "the seam"))
    return uv


def skin_unwrap(P, F, log=print):
    """Returns (positions, faces, uv, orig): the skin cut along the seam (some vertices doubled: orig gives each one's
    vertex in P), and its flat layout in [0, 1] (the longer side 1); -1 for the caps' own vertices."""
    import numpy as np
    from scipy import sparse
    from scipy.sparse import csgraph
    P = np.asarray(P, float); F = np.asarray(F, np.int64)
    # the caps: where the scan cut the body (faces within 4 mm of its top or bottom): not skin
    y = P[:, 1]
    fy = np.stack([y[F[:, 0]], y[F[:, 1]], y[F[:, 2]]], 1)
    band = 0.004
    cap = (fy.max(1) < y.min() + band) | (fy.min(1) > y.max() - band)
    skin = ~cap
    # the openings left by the caps: loops of edges used by one skin face
    Es = _uw_edges(F[skin])
    ue, cnt = np.unique(Es, axis=0, return_counts=True)
    bnd = ue[cnt == 1]
    loops = []
    if len(bnd):
        nb = int(F.max()) + 1
        B = sparse.coo_matrix((np.ones(len(bnd)), (bnd[:, 0], bnd[:, 1])), shape=(nb, nb))
        k, lab = csgraph.connected_components(B, directed=False)
        verts = np.unique(bnd)
        for cc in np.unique(lab[verts]):
            lp = verts[lab[verts] == cc]
            if len(lp) >= 8:
                loops.append(lp)
        # (small openings, a few vertices round, are holes, not where the scan cuts the body: they stay as they are)
        if loops:
            big = max(len(lp) for lp in loops)
            loops = [lp for lp in loops if len(lp) >= 0.15 * big]
    log("Unwrap: %d cap face(s) left out (the scan's cut), %d opening(s)." % (int(cap.sum()), len(loops)))
    seam, front = _uw_seam(P, F, log, loops)
    # cut the skin faces only (the caps would join the two sides of the seam at the openings); the caps keep the
    # original vertices
    P2, Fs2, orig = _uw_cut(P, F[skin], seam)
    # pinches on the outline (two parts of an opening touching at one vertex): split, so the outline is one loop
    Eb = _uw_edges(Fs2); ue2, c2 = np.unique(Eb, axis=0, return_counts=True)
    deg = np.bincount(ue2[c2 == 1].ravel(), minlength=len(P2))
    P2, Fs2, orig = _uw_split(P2, Fs2, orig, np.where(deg > 2)[0])
    F2 = F.copy(); F2[skin] = Fs2
    used = np.unique(F2[skin])
    remap = -np.ones(len(P2), np.int64); remap[used] = np.arange(len(used))
    if loops:
        uvs = _uw_rect(P2[used], remap[F2[skin]], loops, orig[used], log)
    else:
        sv = np.array(sorted({v for e in seam for v in e})) if seam else np.array([int(np.argmax(y)), int(np.argmin(y))])
        pin = (int(sv[np.argmax(P[sv, 1])]), int(sv[np.argmin(P[sv, 1])]))
        pin = tuple(int(np.where((orig == p) & (remap >= 0))[0][0]) for p in pin)
        uvs = _uw_lscm(P2[used], remap[F2[skin]], (remap[pin[0]], remap[pin[1]]))
    uv = np.full((len(P2), 2), np.nan); uv[used] = uvs
    ok = ~np.isnan(uv[:, 0])
    if not loops:                                              # (the conformal map: turned upright, head up)
        A = np.c_[uv[ok], np.ones(int(ok.sum()))]
        g = np.linalg.lstsq(A, P[orig[ok], 1], rcond=None)[0][:2]
        ang = np.arctan2(g[0], g[1])
        c, s = np.cos(ang), np.sin(ang)
        uv = uv @ np.array([[c, s], [-s, c]])
    # the patient's right on the left, as seen facing them (model x: the patient's left)
    fr = (front[orig] > 0.6) & ok
    if fr.sum() > 10 and np.corrcoef(uv[fr, 0], P[orig][fr, 0])[0, 1] < 0:
        uv[:, 0] = -uv[:, 0]
    # the head at the top of the layout, whatever opening was taken for the top
    if ok.sum() > 10 and np.corrcoef(uv[ok, 1], P[orig[ok], 1])[0, 1] < 0:
        uv[:, 1] = -uv[:, 1]
    uv -= np.nanmin(uv, axis=0)
    uv /= max(1e-9, np.nanmax(uv))
    uv[~ok] = -1.0
    # how much the areas are stretched (1: as on the body)
    a3 = np.linalg.norm(np.cross(P2[F2[:, 1]] - P2[F2[:, 0]], P2[F2[:, 2]] - P2[F2[:, 0]]), axis=1)
    d = uv[F2[:, 1]] - uv[F2[:, 0]]; e = uv[F2[:, 2]] - uv[F2[:, 0]]
    a2 = np.abs(d[:, 0] * e[:, 1] - d[:, 1] * e[:, 0]) * skin
    r = (a2 / max(1e-12, a2.sum())) / np.maximum(1e-12, a3 / max(1e-12, a3[skin].sum()))
    okf = (a3 > 0) & skin & (r > 0)
    if okf.any():
        q = np.percentile(r[okf], [5, 50, 95])
        log("Unwrap: %d vertices (%d doubled on the seam); area scale on the layout 5%%/50%%/95%%: %.2f / %.2f / %.2f (1: as on the body)" % (len(P2), len(P2) - len(P), q[0], q[1], q[2]))
    return P2, F2, uv, orig


def strip_table(v, vsp, hu, log=print):
    """The scanner's table pad: a thin arc (a few mm) that follows the back, just under the skin, touching it here and there.
    Slice by slice: what is thin (gone after an opening of about 5 mm) and long (over 3 cm) is not the body and becomes
    air; what is thick (the body) is never touched, so where the pad lies against the back at most a mm-thin layer stays.
    The thick table further down is apart from the body and is dropped later."""
    import numpy as np
    from scipy import ndimage
    px = float(min(vsp[1], vsp[2]))
    r = max(1, int(round(2.5 / px)))
    yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
    disk = xx * xx + yy * yy <= r * r
    grow = max(1, int(round(1.0 / px)))
    tot = 0
    slices = 0
    for k in range(v.shape[0]):
        m = v[k] > hu
        if not m.any():
            continue
        thick = ndimage.binary_opening(m, structure=disk)
        thin = m & ~thick
        if not thin.any():
            continue
        lab, n = ndimage.label(thin, structure=np.ones((3, 3)))
        kill = np.zeros(n + 1, bool)
        for i, s in enumerate(ndimage.find_objects(lab), 1):
            L = max((s[0].stop - s[0].start) * vsp[1], (s[1].stop - s[1].start) * vsp[2])
            if L >= 30.0 and float((lab[s] == i).sum()) * vsp[1] * vsp[2] / L < 3.5:     # long, and under 3.5 mm thick
                kill[i] = True
        if not kill.any():
            continue
        bad = ndimage.binary_dilation(kill[lab], iterations=grow) & ~thick     # (its blurred edge, never the body)
        v[k][bad] = -1000.0
        tot += int(bad.sum())
        slices += 1
    if tot:
        log("Skin: thin arcs apart from the body taken out (the scanner's table pad), in %d of %d slices." % (slices, v.shape[0]))
    return tot


def strip_pad(v, vsp, hu, log=print):
    """The table pad's surface against the back, slice by slice, before the skin is looked for: going in from the air, a
    thin bright layer (the pad, 1-2 px), a thin darker one (the gap, 1-3 px), then bright again (the skin). Where that is
    so, the outer layer is the pad: it becomes air, so the gap opens to the air and is not filled in as body (the flat
    plate on the back). Bits of it left hanging where it leaves the skin (thin and long) go too. Only the outer 2 px of
    the body are ever touched."""
    import numpy as np
    from scipy import ndimage
    a = np.clip(v + 1000.0, 0.0, 1400.0)                     # (air 0)
    lvl = hu + 1000.0
    sp = (float(vsp[1]), float(vsp[2])); px = min(sp)
    kw = max(3, int(round(5.0 / px)) | 1)
    o1 = max(1.0, 1.5 / px) * px                             # the pad: the outer ~1.5 mm
    total = 0; nsl = 0
    for z in range(v.shape[0]):
        m = a[z] > lvl
        if m.sum() < 200:
            continue
        solid = ndimage.binary_fill_holes(m)
        d = ndimage.distance_transform_edt(solid, sampling=sp)
        pad = np.zeros_like(m)
        for g1, s1 in ((2.7, 4.4), (3.4, 5.5), (4.1, 6.7)):    # (the gap 1 to 3 px wide)
            sh = [(d > 0) & (d <= o1 + 0.01), (d > o1 + 0.01) & (d <= g1), (d > g1) & (d <= s1)]
            cnt = [ndimage.uniform_filter(s.astype(np.float32), kw) for s in sh]
            mean = [ndimage.uniform_filter(a[z] * s, kw) / np.maximum(1e-6, c) for s, c in zip(sh, cnt)]
            lo = np.minimum(mean[0], mean[2])
            pad |= sh[0] & (cnt[0] > 1e-4) & (cnt[1] > 1e-4) & (cnt[2] > 1e-4) & (mean[0] > lvl) & (mean[2] > lvl) & (mean[1] < 0.6 * lo)
        if not pad.any():
            continue
        pad = ndimage.binary_dilation(pad, iterations=1) & (d > 0) & (d <= o1 + 0.01)
        body = m & ~pad
        # what is left of it hanging from the body: thin (gone after a 1 px opening) and long (over 8 mm)
        op = ndimage.binary_opening(body, structure=np.ones((3, 3)))
        lt, nt = ndimage.label(body & ~op, structure=np.ones((3, 3)))
        drop = pad.copy()
        for i, s in enumerate(ndimage.find_objects(lt), 1):
            if max(s[0].stop - s[0].start, s[1].stop - s[1].start) * px >= 8.0:
                drop[s] |= lt[s] == i
        drop &= (d > 0) & (d <= 2.5 * px + 0.01)               # (never deeper than the outer 2-3 px)
        v[z][drop] = -1000.0
        total += int(drop.sum()); nsl += 1
    if total:
        log("Skin: the table pad's surface against the back taken off, in %d of %d slices." % (nsl, v.shape[0]))
    return total


def strip_pad_band(v, vsp, hu, log=print):
    """The table pad lies along the whole scan at nearly the same place in every slice (pressed in a little more or less by
    the body): pixels where a thin line (gone after a ~1.5 mm opening) shows in many slices are its band. In that band
    every thin line is the pad, however short (where the body touches it, it breaks into short pieces that stayed on the
    skin as slivers): they become air. The body, thick, is never touched."""
    import numpy as np
    from scipy import ndimage
    px = float(min(vsp[1], vsp[2]))
    r = max(1, int(round(1.5 / px)))
    yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
    disk = xx * xx + yy * yy <= r * r
    nz = v.shape[0]
    if nz < 10:
        return 0
    C = np.zeros(v.shape[1:], np.float32)
    thin = []
    for k in range(nz):
        m = v[k] > hu
        th = m & ~ndimage.binary_opening(m, structure=disk)
        thin.append(np.packbits(th))
        C += th
    C /= nz
    band = ndimage.binary_dilation(C >= PAD_SHARE, iterations=max(1, int(round(2.0 / px))))
    if not band.any():
        return 0
    shp = v.shape[1:]
    tot = 0; nsl = 0
    st8 = np.ones((3, 3), bool)
    for k in range(nz):
        th = np.unpackbits(thin[k])[:shp[0] * shp[1]].reshape(shp).astype(bool)
        lab, n = ndimage.label(th, structure=st8)
        if n == 0:
            continue
        cnt = ndimage.sum(np.ones(shp), lab, range(1, n + 1))
        inb = ndimage.sum(band, lab, range(1, n + 1))
        sel = np.zeros(n + 1, bool)
        sel[1:] = (inb >= 0.7 * cnt) & (cnt * px >= 3.0)
        drop = sel[lab]
        if drop.any():
            m = v[k] > hu
            thick = ndimage.binary_opening(m, structure=disk)
            drop = ndimage.binary_dilation(drop, iterations=1) & band & ~thick
            v[k][drop] = -1000.0
            tot += int(drop.sum()); nsl += 1
    if tot:
        log("Skin: the table pad's band found (where a thin line shows in %d%%+ of the slices): its pieces taken off in %d of %d slices." % (round(100 * PAD_SHARE), nsl, nz))
    return tot


def split_contacts(v, hu, log=print):
    """Thick slices: where two parts of the body meet in one slice only (a labium against a thigh), with the air around
    the body at that very spot in the slice above and the one below, the contact is the slice's thickness, not the body:
    it becomes air, so the parts stay apart. Only where it opens onto the air around the body in that slice and reaches
    3 pixels or more into it (the outline's own pixel of jitter from slice to slice is left alone)."""
    import numpy as np
    from scipy import ndimage
    nz = v.shape[0]
    if nz < 3:
        return 0
    st8 = np.ones((3, 3), bool)

    def outside(s):
        air = s <= hu
        la, na = ndimage.label(air, structure=st8)
        edge = np.unique(np.concatenate([la[0], la[-1], la[:, 0], la[:, -1]]))
        return np.isin(la, edge[edge > 0])

    prev, cur = outside(v[0]), outside(v[1])
    tot = 0; nsl = 0
    for k in range(1, nz - 1):
        nxt = outside(v[k + 1])
        cand = prev & nxt & ~cur & (v[k] > hu)
        if cand.any():
            lab, n = ndimage.label(cand, structure=st8)
            touch = ndimage.binary_dilation(cur, structure=st8)
            keep = np.unique(lab[touch & cand]); keep = keep[keep > 0]
            if len(keep):                                             # deep (3 px or more from the air): not the outline's jitter
                dep = ndimage.distance_transform_edt(~cur)
                deep = ndimage.maximum(dep, lab, keep)
                keep = keep[np.asarray(deep) >= 3.0]
            op = np.isin(lab, keep)
            if op.any():
                v[k][op] = np.minimum(v[k][op], hu - 200.0)
                tot += int(op.sum()); nsl += 1
                cur = outside(v[k])
        prev, cur = cur, nxt
    if tot:
        log("Skin: parts of the body touching in one slice only kept apart (labia and thighs), %d pixels in %d slices." % (tot, nsl))
    return tot


def open_clefts(v, vsp, hu, log=print):
    """Folds whose two skins touch (between the labia, the buttocks, a thigh against the body): in a slice their gap is a
    line thinner than a pixel, darker than the skin on both sides but above the body threshold. Such lines (a dip of
    CLEFT_HU or more under the skin on both sides, within 2 pixels) are opened where they run on from the air around the
    body in the same slice: the fold then stays open however deep it goes. Dips that do not reach the air (noise, fat
    between muscles) are left alone."""
    import numpy as np
    from scipy import ndimage
    n = 0; nsl = 0
    st8 = np.ones((3, 3), bool)
    for k in range(v.shape[0]):
        s = v[k]
        if not (s > hu).any():
            continue
        # a dip: along some direction (across the line), skin (above hu + 250: not fat) on both sides within 2 pixels, each CLEFT_HU brighter
        p = np.pad(s, 2, mode="edge")
        H, W = s.shape
        def at(dy, dx):
            return p[2 + dy:2 + dy + H, 2 + dx:2 + dx + W]
        dip = np.zeros(s.shape, bool)
        for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
            a = np.maximum(at(dy, dx), at(2 * dy, 2 * dx))
            b = np.maximum(at(-dy, -dx), at(-2 * dy, -2 * dx))
            lo = np.minimum(a, b)
            dip |= (lo - s >= CLEFT_HU) & (lo > hu + 250.0)
        air = s <= hu
        la, na = ndimage.label(air, structure=st8)
        edge = np.unique(np.concatenate([la[0], la[-1], la[:, 0], la[:, -1]]))
        out = np.isin(la, edge[edge > 0])
        lg, ng = ndimage.label(dip | out, structure=st8)
        keep = np.unique(lg[out]); keep = keep[keep > 0]
        op = np.isin(lg, keep) & dip & ~air
        if op.any():
            s[op] = np.minimum(s[op], hu - 200.0)
            n += int(op.sum()); nsl += 1
    if n:
        log("Skin: folds whose skins touch kept open (a dark line running on from the air), %d pixels in %d slices." % (n, nsl))
    return n


def skin_surface_fine(v, vsp, hu, log=print):
    """The surface, finer than the scan where it matters: each slice's outline as a signed distance (to the pixel's
    fraction where the CT crosses hu; UP times finer pixels if set), and between slices the outline morphs from one slice
    to the next every 0.6 mm or so (shape, not grey values: no step at each slice on surfaces that lie almost flat in the
    slice). Marching cubes in pieces along the body (the memory), joined exactly. Returns vertices in the indices of v
    (z, y, x) and the faces."""
    import numpy as np
    from scipy import ndimage
    from skimage import measure
    up = UP
    h = float(min(vsp[1], vsp[2])) / up                              # mm per fine pixel
    zf = max(1, min(6, int(round(vsp[0] / 0.65))))                  # fine planes per slice (2.5 mm: 4, 0.625 mm)
    CL = 30.0
    nz = v.shape[0]
    ny, nx = v.shape[1] * up, v.shape[2] * up
    S = np.empty((nz + 2, ny, nx), np.float16)
    S[0] = S[-1] = -CL                                                # the scan's first and last slices close the skin
    for k in range(nz):
        u = ndimage.zoom(v[k], up, order=3, mode="nearest", grid_mode=True) if up > 1 else v[k]
        b = u > hu
        if not b.any():
            S[k + 1] = -CL; continue
        d = (ndimage.distance_transform_edt(b) - ndimage.distance_transform_edt(~b)) * h
        d -= np.sign(d) * 0.5 * h                                     # (the outline between the pixels)
        gy, gx = np.gradient(u, h)
        g = np.hypot(gy, gx)
        lin = (u - hu) / np.maximum(g, 50.0)                          # where it crosses hu, from the grey values
        near = np.abs(d) <= 1.5 * h
        d[near] = np.clip(lin[near], -1.5 * h, 1.5 * h)
        d[0, :] = d[-1, :] = d[:, 0] = d[:, -1] = -CL                 # where the body leaves the scan's field: closed there
        S[k + 1] = np.clip(d, -CL, CL)
    V, F, nv = [], [], 0
    sig = (0, 0.6, 0.6)
    K = 6
    for a in range(0, nz + 1, K):
        b = min(nz + 1, a + K)
        planes = []
        for i in range(a, b):
            p0, p1, p2, p3 = (S[max(0, i - 1)].astype(np.float32), S[i].astype(np.float32), S[i + 1].astype(np.float32), S[min(nz + 1, i + 2)].astype(np.float32))
            for j in range(zf):
                t = j / zf
                planes.append(0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
        planes.append(S[b].astype(np.float32))
        c = np.stack(planes)
        del planes
        c = ndimage.gaussian_filter(c, sig)
        if c.max() <= 0 or c.min() >= 0:
            continue
        vv, ff, _, _ = measure.marching_cubes(c, 0.0, allow_degenerate=False)
        vv[:, 0] += a * zf
        F.append(ff + nv); V.append(vv); nv += len(vv)
        del c
    del S
    V = np.concatenate(V); F = np.concatenate(F)
    q = np.round(V * 64).astype(np.int64)                            # the planes two pieces share: the same vertices
    key = (q[:, 0] << 42) | (q[:, 1] << 21) | q[:, 2]                 # (MC puts them on the grid's edges: 1/64 tells them apart)
    del q
    _, first, inv = np.unique(key, return_index=True, return_inverse=True)
    del key
    V = V[first]; F = inv.reshape(-1)[F]
    F = F[(F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])]
    V[:, 0] = V[:, 0] / zf - 1.0
    V[:, 1:] = (V[:, 1:] + 0.5) / up - 0.5
    return V, F, zf, h


def skin_shell(ct, hu, spacing_mm, log):
    """The body's outline in the CT (above body_hu, the largest piece, holes filled): points on its surface, every
    spacing_mm, and a light surface mesh to draw. Points on the top and bottom cut of the scan are fixed: the body goes on."""
    import numpy as np
    import SimpleITK as sitk
    from scipy import ndimage
    from skimage import measure
    # The surface where the CT itself crosses hu, not the edge of a yes/no mask: the scanner's partial volume puts it
    # between voxels, so there are no terraces at each slice and voxel row, and the real detail stays. The body is found
    # as before (largest piece above hu, holes filled per slice): air inside it is raised (lungs, bowel), what is apart
    # from it lowered (table, blankets); only within 4 mm of the outline do the CT values decide.
    a = sitk.GetArrayFromImage(ct)
    sp = np.array(ct.GetSpacing(), float)[::-1]
    step = np.maximum(1, np.round(0.8 / sp)).astype(int)             # the scan's own pixels (down to 0.8 mm), every slice: thin slits stay open
    m0 = a[:, ::4, ::4] > hu                                         # the body's box, from a quick look
    lab, n = ndimage.label(m0)
    if n == 0:
        return None
    m0 = lab == (1 + int(np.argmax(ndimage.sum(m0, lab, range(1, n + 1)))))
    zz, yy, xx = np.nonzero(m0)
    mg = 12
    y0, y1 = max(0, 4 * int(yy.min()) - mg), min(a.shape[1], 4 * int(yy.max()) + 4 + mg)
    x0, x1 = max(0, 4 * int(xx.min()) - mg), min(a.shape[2], 4 * int(xx.max()) + 4 + mg)
    z0, z1 = int(zz.min()), int(zz.max()) + 1
    del m0, lab
    c = a[z0:z1, y0:y1, x0:x1].astype(np.float32)
    del a
    cz, cy, cx = (np.array(c.shape) // step) * step
    c = c[:cz, :cy, :cx]
    v = c.reshape(cz // step[0], step[0], cy // step[1], step[1], cx // step[2], step[2]).mean(axis=(1, 3, 5))   # block means: no aliasing
    del c
    np.clip(v, -1000.0, 400.0, out=v)
    vsp = sp * step
    try:
        strip_table(v, vsp, hu, log)                                  # the table pad under the back is not the body
    except Exception as e:
        log("Skin: the table pad could not be looked for (%s)." % e)
    try:
        strip_pad_band(v, vsp, hu, log)                               # its pieces left against the back
    except Exception as e:
        log("Skin: the table pad's band could not be looked for (%s)." % e)
    try:
        strip_pad(v, vsp, hu, log)                                    # and its surface lying against the back
    except Exception as e:
        log("Skin: the table pad's surface could not be looked for (%s)." % e)
    try:
        open_clefts(v, vsp, hu, log)                                  # folds whose skins touch stay open
    except Exception as e:
        log("Skin: the folds could not be looked into (%s)." % e)
    try:
        split_contacts(v, hu, log)                                    # parts touching in one slice only stay apart
    except Exception as e:
        log("Skin: contacts between slices could not be looked into (%s)." % e)
    try:
        strip_pad_band(v, vsp, hu, log)                               # again: what the folds just set apart from the back
        strip_table(v, vsp, hu, lambda *a: None)
    except Exception as e:
        log("Skin: the table pad's band could not be looked for (%s)." % e)
    body = v > hu
    lab, n = ndimage.label(body)
    body = lab == (1 + int(np.argmax(ndimage.sum(body, lab, range(1, n + 1)))))
    # Air inside the body (lungs, bowel) is body; air that reaches the air around the body, in 3D, stays air however deep
    # it goes into a fold (between the labia, the buttocks, thighs that touch), even where a slice encloses it
    air = ~body
    lab, n = ndimage.label(air)
    edge = np.unique(np.concatenate([lab[:, 0, :].ravel(), lab[:, -1, :].ravel(), lab[:, :, 0].ravel(), lab[:, :, -1].ravel()]))
    outside = np.isin(lab, edge[edge > 0])
    inside_air = air & ~outside
    del lab, air
    ring = ndimage.binary_dilation(inside_air, iterations=1) & ~outside
    v[ring] = np.maximum(v[ring], 400.0)                             # enclosed air (and its rim) is body
    body |= inside_air
    del ring, inside_air, outside
    r_in = max(1, int(round(4.0 / vsp[1:].min())))
    for k in range(body.shape[0]):
        inner = ndimage.binary_erosion(body[k], iterations=r_in)
        near = ndimage.binary_dilation(body[k], iterations=r_in)
        v[k][inner] = np.maximum(v[k][inner], 400.0)                 # deep inside: body
        v[k][~near] = -1000.0                                        # whatever is apart from the body is air
    del body
    # The surface, finer where it matters: outlines to a fraction of a pixel, morphing from slice to slice, the mesh then
    # lightened by how far it strays from that surface (quadrics): triangles stay small where the body is detailed (folds,
    # face, hands) and grow where it is flat (back, belly)
    V, faces, zf, hfine = skin_surface_fine(v, vsp, hu, log)
    del v
    nfine = len(faces)
    import trimesh
    ijk = (V * step + np.array([z0, y0, x0], float) + (step - 1) / 2.0)[:, ::-1]
    d = np.array(ct.GetDirection(), float).reshape(3, 3)
    lps = np.array(ct.GetOrigin(), float) + (ijk * np.array(ct.GetSpacing(), float)) @ d.T
    pts = np.column_stack([lps[:, 0], lps[:, 2], -lps[:, 1]]) / 1000.0
    del V, ijk, lps
    try:
        import fast_simplification
        if len(faces) > SKIN_FACES:
            p2, f2 = fast_simplification.simplify(pts.astype(np.float32), faces.astype(np.int64), target_reduction=1.0 - SKIN_FACES / float(len(faces)), agg=7)
            pts, faces = np.asarray(p2, float), np.asarray(f2)
    except Exception as e:
        log("Skin: not lightened by error (%s), evenly instead." % e)
        mesh = trimesh.Trimesh(pts, faces, process=False)
        mesh = mesh.simplify_quadric_decimation(face_count=SKIN_FACES)
        pts, faces = np.asarray(mesh.vertices), np.asarray(mesh.faces)
    mesh = trimesh.Trimesh(pts, faces, process=True)
    parts = mesh.split(only_watertight=False)                        # one skin: crumbs left by the folds go
    if len(parts) > 1:
        mesh = max(parts, key=lambda m: len(m.faces))
    try:                                                             # 2 light passes that keep the volume (Taubin): the last ripple
        trimesh.smoothing.filter_taubin(mesh, lamb=0.5, nu=-0.53, iterations=2)
    except Exception:
        pass
    trimesh.repair.fix_normals(mesh)
    P = np.asarray(mesh.vertices)
    nr = np.asarray(mesh.vertex_normals)
    if float(np.mean(np.sum((P - P.mean(axis=0)) * nr, axis=1))) < 0:
        nr = -nr
    # points every spacing_mm on the surface (a grid of cells, the point nearest each cell's centre)
    cell = spacing_mm / 1000.0
    keys = np.floor(P / cell).astype(np.int64)
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
    shell = P[idx] - nr[idx] * rad
    shell_n = nr[idx]
    # on the top and bottom cut of the scan: within half a slice of the first or last one (along the scan's axis)
    ax = np.array(ct.GetDirection(), float).reshape(3, 3)[:, 2]
    axv = np.array([ax[0], ax[2], -ax[1]])
    t = P @ axv
    lo, hi = float(t.min()), float(t.max())
    tol = 0.75 * float(ct.GetSpacing()[2]) * step[0] / 1000.0
    cut = [bool(t[i] <= lo + tol or t[i] >= hi - tol) for i in idx]
    verts_out, faces_out, uvs = P, np.asarray(mesh.faces), None
    try:
        verts_out, faces_out, uvs, _o = skin_unwrap(verts_out, faces_out, log)
    except Exception as e:
        log("Skin: not unwrapped for painting (%s): the hair maps cannot be painted on this case." % e)
        verts_out, faces_out, uvs = P, np.asarray(mesh.faces), None
    log("Skin: the body's outline (CT above %g HU), traced every %.2f x %.2f x %.2f mm (slices morphed into each other), %d triangles lightened to %d where it is flat; %d points every %g mm, %d of them on the cut of the scan (fixed)." % (
        hu, hfine, hfine, vsp[0] / zf, nfine, len(mesh.faces), len(shell), spacing_mm, sum(cut)))
    area = float(mesh.area)                                          # m2 (the scan's part of the body)
    return {"points": [[round(float(v), 4) for v in q] for q in shell], "normals": [[round(float(v), 3) for v in q] for q in shell_n], "fixed": cut, "radius": round(rad, 4), "area_m2": round(area, 4),
            "mesh": dict({"positions": [round(float(v), 4) for v in np.asarray(verts_out).ravel()], "faces": np.asarray(faces_out).astype(int).ravel().tolist()},
                         **({"uv": [round(float(v), 5) for v in np.asarray(uvs).ravel()]} if uvs is not None else {}))}


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
