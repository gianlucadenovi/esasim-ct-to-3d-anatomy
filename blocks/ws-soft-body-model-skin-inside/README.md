# Soft body model (skin inside)

Turns segmented anatomy into a soft-tissue model the 3D view simulates in real time: organs that sag, sway and push each other under gravity, held by a fixed skeleton and contained by the skin (metaba

Connect the masks of each case (segmentations/ folders, as in the TotalSegmentator dataset) and its CT scan. Following the metaball soft-tissue method of Gianluca De Novi, PhD (PhD thesis, University of Bologna, 2011: https://amsdottorato.unibo.it/id/eprint/3702/1/DeNovi_Gianluca_tesi.pdf), each structure's volume (soft structures of 1 ml or more, as in Labels to 3D models: smaller slivers have no surface to move) is approximated by a tree of spheres (medial axis approximation: the deepest point not yet covered, with its distance to the surface as radius, until Coverage is reached); the sphere centres are particles with mass (each structure weighs its density times its real volume, from its mask, and its spheres share that mass in proportion to their volumes; the skin weighs a 3 mm layer over the body's outline), joined by elastic links with damping: inside each structure (touching spheres, and a second ring that keeps its shape), between structures that touch (connective tissue), and to the skeleton, which is fixed and not subject to gravity (each bone with as many spheres as it needs to be covered; between neighbouring ribs, costal cartilages and sternum, a chest wall of fixed spheres stands for the intercostal muscles, which are not segmented, so the lungs cannot slip out between the ribs); muscles are tied to the bones where they meet them (origins and insertions: each muscle sphere that touches a bone, or comes within 6 mm, by stiff elastic links to up to 4 bone spheres). The skin is the body's outline in the CT (above Body threshold): points every Skin spacing, joined to each other and to what lies under them, fixed where the scan cuts the body. Each structure gets a tissue class with a stiffness (Young's modulus) and a density: liver, spleen, pancreas, kidney, thyroid and muscle as measured in healthy people by shear-wave elastography (Viceconti et al., World J Radiol 2025; Arda et al., AJR 2011), the others from the orders of magnitude in the literature; a Tissues table (tissue, match, E, density, damping) changes them. Connect the model and the anatomy of Labels to 3D models to a 3D view: the organs move under gravity as you turn the body, and can be pulled. A plausible demo, not a validated simulation: not for clinical use.

An [EsaSim](https://esacode.com/) blueprint block: it runs on a worker, in Python (`backend.py`, `def run(ctx)`).

| | |
|---|---|
| Block | `ws-soft-body-model-skin-inside` · version 3 |
| Workspace | Gianluca De Novi's workspace |
| Author | Gianluca De Novi |
| Runs on | Any worker |

## Inputs

| Port | Type | Description |
|---|---|---|
| `labels` Labels | Files (gz, nii, nrrd, mha) | Masks, one file per structure, in each case's segmentations/ folder Several connections. |
| `scans` Scans | Files (gz, nii, nrrd, mha) | The CT of each case, for the skin (the body's outline) Several connections. Optional. |
| `tissues` Tissues | Table (csv) | Optional: tissue, match (words of structure names, separated by ;), E (Pa), density (kg/m3), damping Several connections. Optional. |

## Outputs

| Port | Type | Description |
|---|---|---|
| `model` Soft body | Files (json) | <case>/<case>_softbody.json (esasim.softbody/1): bodies of spheres, links, tissues, the skin and its surface |
| `table` Structures | Table (csv) | softbody.csv: case, structure, tissue, fixed, spheres, bone_links, volume_ml, mass_g, E_pa, density |

## Settings

| Key | Type | Default | Description |
|---|---|---|---|
| `structures` Soft structures | text | `""` | Names of the structures that move (liver, kidney_*, colon…), separated by commas; empty: all. The skeleton is always there, fixed |
| `spheres` Spheres per structure | number | `40` | More: finer shapes, slower simulation |
| `bone_spheres` Spheres per bone | number | `0` | 0 (automatic): as many as each bone needs to be covered (ribs and costal cartilages included), at most 800. A number: at most that many per bone; fewer leave gaps the organs can slip through |
| `chest_wall` Close the chest wall | bool | `true` | The intercostal muscles are not segmented: fixed spheres fill the gaps between neighbouring ribs, costal cartilages and sternum, so the lungs cannot slip out between the ribs |
| `coverage` Coverage (%) | number | `85` | Spheres are added until they cover this share of each structure |
| `skin` Skin | bool | `true` | A skin layer, from the body's outline in the CT, that contains the organs |
| `skin_spacing` Skin spacing (mm) | number | `40` |  |
| `body_hu` Body threshold (HU) | number | `-300` | CT values above it are the body (air is about -1000, fat about -100) |

## Use it in EsaSim

In a workspace, open **Projects > Blocks > New block**, choose this kind of block, copy the ports and settings above and paste the code; or ask an AI assistant connected to EsaSim (MCP) to create it from this folder.
