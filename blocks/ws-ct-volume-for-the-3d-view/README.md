# CT volume for the 3D view

Resamples a CT scan into the 3D models' own frame (as Labels to 3D models writes them) as a compact volume, so the 3D view can show the real CT on a cut.

Wire the scans (the same files the Labels to 3D models block reads: masks are skipped) and connect Volume to the 3D view's Scene input next to the models. Each case gives <case>/<case>_ct.ctvol: the CT resampled on a grid aligned with the glTF frame of <case>_anatomy.glb (x = patient's left, y = up, z = towards the face, metres), at most Size voxels on its longest side, 8-bit (0 outside the body; 1 to 255 = −1024 to +1536 HU), compressed. The 3D view paints it on the cut plane with a soft-tissue, bone or lung window.

An [EsaSim](https://esacode.com/) blueprint block: it runs on a worker, in Python (`backend.py`, `def run(ctx)`).

| | |
|---|---|
| Block | `ws-ct-volume-for-the-3d-view` · version 3 |
| Workspace | Gianluca De Novi's workspace |
| Author | Gianluca De Novi |
| Runs on | Any worker |

## Inputs

| Port | Type | Description |
|---|---|---|
| `scans` Scans | Files (gz, nii, nrrd, mha, mhd) | CT volumes (NIfTI, NRRD, MHA); masks in segmentations/ folders are skipped Several connections. |

## Outputs

| Port | Type | Description |
|---|---|---|
| `volume` Volume | Files (ctvol) | <case>/<case>_ct.ctvol for the 3D view's cut |

## Settings

| Key | Type | Default | Description |
|---|---|---|---|
| `file` Scan file name | text | `"ct.nii.gz"` | Which file of each case is the CT (a pattern such as *.nii.gz works); empty: any scan that is not a mask |
| `size` Size (voxels on the longest side) | number | `256` | 256 is about 1.5 to 2.5 mm per voxel for a trunk: a sharp slice, a few MB |

## Use it in EsaSim

In a workspace, open **Projects > Blocks > New block**, choose this kind of block, copy the ports and settings above and paste the code; or ask an AI assistant connected to EsaSim (MCP) to create it from this folder.
