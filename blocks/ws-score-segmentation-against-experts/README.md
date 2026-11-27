# Score segmentation against experts

Compares automatic masks with expert masks of the same cases, structure by structure: Dice, volumes and their difference, and a mean per group.

Wire the Segmented cases of Segment CT automatically into Automatic, and the dataset with expert labels (<case>/segmentations/<structure>.nii.gz) into Experts. Cases and structures are matched by name; structures only one side has are listed with Dice 0.

An [EsaSim](https://esacode.com/) blueprint block: it runs on a worker, in Python (`backend.py`, `def run(ctx)`).

| | |
|---|---|
| Block | `ws-score-segmentation-against-experts` · version 2 |
| Workspace | Gianluca De Novi's workspace |
| Author | Gianluca De Novi |
| Runs on | Any worker |

## Inputs

| Port | Type | Description |
|---|---|---|
| `auto` Automatic | Files (gz, nii, nrrd, mha) | <case>/segmentations/<structure>.nii.gz from the network Several connections. |
| `experts` Experts | Files (gz, nii, nrrd, mha) | <case>/segmentations/<structure>.nii.gz drawn by experts Several connections. |

## Outputs

| Port | Type | Description |
|---|---|---|
| `table` Score per structure | Table (csv) | score.csv: case, structure, group, dice, expert_ml, auto_ml, volume_diff_pct, note |
| `summary` Summary | Metrics (json) | summary.json: mean and median Dice, overall and per group |

## Settings

| Key | Type | Default | Description |
|---|---|---|---|
| `min_ml` Smallest (ml) | number | `0.5` | Structures smaller than this on both sides are left out (slivers at the scan's edges) |

## Use it in EsaSim

In a workspace, open **Projects > Blocks > New block**, choose this kind of block, copy the ports and settings above and paste the code; or ask an AI assistant connected to EsaSim (MCP) to create it from this folder.
