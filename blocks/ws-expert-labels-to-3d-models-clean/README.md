# Expert labels to 3D models (clean)

Turns labelled volumes (a CT segmentation, any label map or masks) into a clean 3D model per structure: one coloured GLB scene per case for the 3D view, and STL files for 3D printing.

Connect label volumes (NIfTI, NRRD or MHA): a label map per case, where each number is a structure (names from a table: id, name, and optionally group and color), or masks, one file per structure in a folder such as segmentations/ (the file name is the structure, as in the TotalSegmentator dataset). Scans connected by mistake (a CT) are recognised and skipped. Each structure becomes a surface (marching cubes on a slightly softened mask), smoothed without shrinking (Taubin), reduced to at most Triangles, closed at the edges of the scan, and checked: pieces, open edges, watertight, so the table says which models are ready to print. Models are in the patient's frame, in millimetres in STL and metres in GLB (head up, face towards you), grouped as skeleton, organs, vessels, heart, lungs and airways, muscles, and coloured as anatomy atlases do (lungs see-through). Structures picks some by name or group: liver, kidney_*, vessels, skeleton. The 3D scene of a case is kept under Scene triangles (and stored compactly) so it reaches EsaSim and opens quickly; the STL files keep the full detail. Runs on any worker; a full TotalSegmentator case (about 100 structures) takes a minute or two.

An [EsaSim](https://esacode.com/) blueprint block: it runs on a worker, in Python (`backend.py`, `def run(ctx)`).

| | |
|---|---|
| Block | `ws-expert-labels-to-3d-models-clean` · version 2 |
| Workspace | Gianluca De Novi's workspace |
| Author | Gianluca De Novi |
| Runs on | Any worker |

## Inputs

| Port | Type | Description |
|---|---|---|
| `labels` Labels | Files (gz, nii, nrrd, nhdr, mha, mhd) | A label map per case, or masks (one file per structure) in a folder such as segmentations/ Several connections. |
| `names` Names | Table (csv, tsv) | For label maps: id, name (and group, color as #rrggbb) Several connections. Optional. |

## Outputs

| Port | Type | Description |
|---|---|---|
| `models` 3D scenes | Files (glb) | <case>/<case>_anatomy.glb: every structure of the case, named, coloured and grouped, for the 3D view |
| `stl` STL for printing | Files (stl) | <case>/<structure>.stl, in millimetres |
| `table` Models | Table (csv) | models.csv: case, structure, group, volume_ml, triangles, pieces, watertight, open_edges, color, note (ready to print or why not) |

## Settings

| Key | Type | Default | Description |
|---|---|---|---|
| `structures` Structures | text | `""` | Names or groups, separated by commas (liver, kidney_*, vessels, skeleton); empty: all |
| `min_ml` Smallest (ml) | number | `1` | Structures smaller than this are listed but not built |
| `smooth` Smoothing | number | `15` | Rounds of smoothing that keep the volume (Taubin); 0: the voxels' steps stay |
| `triangles` Triangles | number | `20000` | Most triangles per structure (fewer: a lighter scene); 0: no limit |
| `scene_triangles` Scene triangles | number | `300000` | Most triangles in a case's 3D scene (about 3.5 MB at 300,000, so it opens in the browser); the STL files are not reduced. 0: no limit |
| `step` Step (voxels) | number | `1` | 2 or more: coarser surfaces, built faster |
| `largest` Largest piece only | bool | `false` | Drop small islands of each structure (not for structures made of pieces) |
| `formats` Formats | select | `"glb + stl"` |  |

## Use it in EsaSim

In a workspace, open **Projects > Blocks > New block**, choose this kind of block, copy the ports and settings above and paste the code; or ask an AI assistant connected to EsaSim (MCP) to create it from this folder.
