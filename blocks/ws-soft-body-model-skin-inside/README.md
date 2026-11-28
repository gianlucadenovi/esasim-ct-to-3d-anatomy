# Soft body model (skin inside)

Turns segmented anatomy into a soft-tissue model the 3D view simulates in real time: organs that sag, sway and push each other under gravity, held by a fixed skeleton and contained by the skin (metaba

An [EsaSim](https://esacode.com/) blueprint block: it runs on a worker, in Python (`backend.py`, `def run(ctx)`).

| | |
|---|---|
| Block | `ws-soft-body-model-skin-inside` · version 19 |
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
| `physics` Physics | bool | `true` | Off: the 3D view shows the anatomy with its skin as in the scan, without the soft-tissue simulation (no gravity, pull or poke) |

## Use it in EsaSim

In a workspace, open **Projects > Blocks > New block**, choose this kind of block, copy the ports and settings above and paste the code; or ask an AI assistant connected to EsaSim (MCP) to create it from this folder.
