# Load CT scans (DICOM discs, NIfTI, NRRD, MHA)

Turns any CT source (a CD/DVD export with DICOMDIR, DICOM/ and IHE_PDI/, loose DICOM, NIfTI, NRRD, MHA, zips) into one volume per case, <case>/ct.nii.gz: series grouped by their DICOM IDs, copies read

Where the scans come from (Source): Files wired in (a Dataset block, a download, a zip of a disc); Folder on the worker (the full path as the worker sees it, such as D:\CT2013); Upload from the View (the Load a CT view sends the series you tick in your browser; wire this block's Live telemetry, through a Telemetry block on channel ct_load, to the view's Live input). DICOM is grouped by Series Instance UID wherever the files are, so a series split over folders is one scan and the IHE_PDI copy of a disc is read once; DICOMDIR, pictures, web pages, PDFs, localisers, dose reports and structured reports are skipped. Series: the best CT series of each study (axial, slices of 3 mm or thinner, covering the most), every CT series, or only those named (series numbers, descriptions or UIDs). Pixels are read with GDCM (compressed transfer syntaxes too) and written in Hounsfield units, 16-bit. No patient tag is copied: the NIfTI files hold pixels and geometry only; cases are named after the series (A_S3_Abdomen_1.5_B30f: study A, series 3). The Series table lists every series found and what happened to it. Wire Scans into Segment CT automatically.

An [EsaSim](https://esacode.com/) blueprint block: it runs on a worker, in Python (`backend.py`, `def run(ctx)`).

| | |
|---|---|
| Block | `ws-load-ct-scans-dicom-discs-nifti-nrrd` · version 2 |
| Workspace | Gianluca De Novi's workspace |
| Author | Gianluca De Novi |
| Runs on | Any worker |

## Inputs

| Port | Type | Description |
|---|---|---|
| `files` Files | Files | Source Files wired in: the scans, in any layout (DICOM folders, NIfTI/NRRD/MHA, zips) Several connections. Optional. |

## Outputs

| Port | Type | Description |
|---|---|---|
| `cases` Scans | Files (gz) | <case>/ct.nii.gz, one per scan chosen, in HU |
| `series` Series | Table (csv) | series.csv: every series found (study, number, description, modality, images, slice thickness, coverage, folders) and what happened to it |

## Settings

| Key | Type | Default | Description |
|---|---|---|---|
| `source` Source | select | `"Files wired in"` | Upload from the View: the run waits for the files the Load a CT view sends |
| `folder` Folder on the worker | text | `""` | Source Folder on the worker: the full path as the worker sees it (D:\CT2013, \\server\share\CT2013, /data/ct/CT2013); every file under it is looked at |
| `series` Series | select | `"The best CT series of each study"` | Best: axial, slices of 3 mm or thinner, covering the most of the body, then the thinnest |
| `only` Series to load | text | `""` | Series Only these series: numbers, descriptions (or part of them) or UIDs, separated by commas, such as 3, 5 or Abdomen 1.5 |
| `modalities` Modalities | text | `"CT"` | Kinds of scans kept, separated by commas: CT, or CT, MR (MR needs the segmentation task total_mr) |
| `min_images` Fewest images | number | `20` | Series with fewer images are left out (single images, short sequences) |
| `wait_minutes` Wait for the upload (minutes) | number | `30` | Upload from the View: how long the run waits for the files, and for each pause while they come |

## Use it in EsaSim

In a workspace, open **Projects > Blocks > New block**, choose this kind of block, copy the ports and settings above and paste the code; or ask an AI assistant connected to EsaSim (MCP) to create it from this folder.
