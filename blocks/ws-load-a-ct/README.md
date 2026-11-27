# Load a CT

The View's loading dialog for CT scans: drop or choose a folder from your computer (a whole CD/DVD export is fine), see its series, tick the ones to segment and press Load; or give a folder on a worke

Put it on the flow's View next to the 3D anatomy. Wire the Live telemetry of the Load CT scans block, through a Telemetry block (channel ct_load), to Live. From this computer: the folder is read in your browser (only the DICOM tags that group and order images; never patient names or IDs), the series are listed with the best CT series of each study ticked, and Load starts a run and sends the ticked images, compressed, to the loader on the worker; the segmentation and the 3D models follow. From a worker's folder: the path on the worker. Wired files: the demo case, or a Dataset block wired to the loader. Settings: Loader node and Segmentation node, the node ids of those blocks in the flow (load and seg).

An [EsaSim](https://esacode.com/) blueprint block: a view that draws in the browser, in JavaScript (`frontend.js`, `function render(ctx)`).

| | |
|---|---|
| Block | `ws-load-a-ct` · version 1 |
| Workspace | Gianluca De Novi's workspace |
| Author | Gianluca De Novi |

## Inputs

| Port | Type | Description |
|---|---|---|
| `live` Live | Stream | The loader's live telemetry (channel ct_load), through a Telemetry block Several connections. Optional. |

## Settings

| Key | Type | Default | Description |
|---|---|---|---|
| `loader_node` Loader node | text | `"load"` | The node id of the Load CT scans block |
| `seg_node` Segmentation node | text | `"seg"` | The node id of the Segment CT automatically block |

## Use it in EsaSim

In a workspace, open **Projects > Blocks > New block**, choose this kind of block, copy the ports and settings above and paste the code; or ask an AI assistant connected to EsaSim (MCP) to create it from this folder.
