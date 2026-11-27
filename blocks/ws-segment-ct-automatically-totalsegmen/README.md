# Segment CT automatically (TotalSegmentator)

Segments organs, bones, vessels and muscles in any CT (NIfTI, NRRD, MHA or DICOM series) with TotalSegmentator, and writes each case as <case>/ct.nii.gz + <case>/segmentations/<structure>.nii.gz, the 

Wire any CT scans into Scans: a dataset of NIfTI files (one per case, or <case>/ct.nii.gz), NRRD/MHA volumes, or the files of DICOM series (one series per folder). Masks already in segmentations/ folders and label maps are skipped, so a dataset that comes with expert labels can be wired too. Wire Cases to Expert labels to 3D models, CT volume for the 3D view, Soft body model and Read medical images exactly as the expert labels were wired: they read the same layout. The first run on a worker downloads the network's weights (about 1–2 GB for the total task) into the worker's ~/.totalsegmentator; the next runs use them. An NVIDIA GPU takes about 1–3 minutes a case at 1.5 mm; the CPU 10–30 minutes (3 mm: a few minutes). For research and teaching, not for clinical use. TotalSegmentator (Wasserthal et al., Radiology: AI 2023), Apache-2.0; only its open tasks are offered.

An [EsaSim](https://esacode.com/) blueprint block: it runs on a worker, in Python (`backend.py`, `def run(ctx)`).

| | |
|---|---|
| Block | `ws-segment-ct-automatically-totalsegmen` · version 3 |
| Workspace | Gianluca De Novi's workspace |
| Author | Gianluca De Novi |
| Runs on | Any worker, NVIDIA GPU |

## Inputs

| Port | Type | Description |
|---|---|---|
| `scans` Scans | Files (gz, nii, nrrd, nhdr, mha, mhd, dcm) | CT volumes (NIfTI, NRRD, MHA) or the files of DICOM series; masks in segmentations/ folders are skipped Several connections. |

## Outputs

| Port | Type | Description |
|---|---|---|
| `cases` Segmented cases | Files (gz) | <case>/ct.nii.gz and <case>/segmentations/<structure>.nii.gz (one mask per structure), as the TotalSegmentator dataset lays them out |
| `table` Structures found | Table (csv) | segmentation.csv: case, structure, voxels, volume_ml, task, seconds |

## Settings

| Key | Type | Default | Description |
|---|---|---|---|
| `task` Task | select | `"total"` | total: 117 structures of a CT (organs, bones, vessels, muscles); total_mr: for MR scans; the others add detail to one region |
| `resolution` Resolution | select | `"1.5 mm (best)"` | total, total_mr and body only. 3 mm is several times faster and fine for big organs; thin structures (ribs, small vessels) lose detail |
| `structures` Only these structures | text | `""` | total / total_mr: names separated by commas (liver, spleen, kidney_left, aorta…); the network then runs only on the part of the scan it needs. Empty: all |
| `device` Run on | select | `"auto"` | auto: the worker's NVIDIA GPU when PyTorch sees one, else the CPU |
| `scan_file` Scan file name | text | `""` | Which volumes are the scans (a pattern such as ct.nii.gz or *.nrrd); empty: every volume that is not a mask or a label map |
| `keep_empty` Keep empty masks | bool | `false` | The network writes a mask for every structure of the task, also those outside the scan; off: only the structures it found |

## Use it in EsaSim

In a workspace, open **Projects > Blocks > New block**, choose this kind of block, copy the ports and settings above and paste the code; or ask an AI assistant connected to EsaSim (MCP) to create it from this folder.
