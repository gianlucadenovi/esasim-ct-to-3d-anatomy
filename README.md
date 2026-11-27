<!-- esasim: cover -->
![CT to 3D anatomy](assets/cover.jpg)
<!-- /esasim: cover -->

<div align="center">

<!-- Banner: upload a picture named banner.png under Data › Readme pictures (a screenshot of the 3D view works well), then: ![CT to 3D anatomy](pictures/banner.png) -->

# CT to 3D anatomy

**From a CT scan to coloured 3D models of every organ, bone and vessel, and soft tissue that moves under gravity.**

Open the anatomy in the browser, hide and show structures, cut through them and see the CT itself on the cut, turn the body and watch the organs move, and download STL files ready for a 3D printer. Bring your own CT scans: a neural network segments them for you.

![type](https://img.shields.io/badge/type-Medical%20%26%20healthcare-blue) ![language](https://img.shields.io/badge/language-Python-3776AB) ![runs on](https://img.shields.io/badge/runs%20on-CPU%20%7C%20NVIDIA-6f42c1) ![data](https://img.shields.io/badge/data-CC%20BY%204.0-green) [![made with](https://img.shields.io/badge/made%20with-EsaSim-0b7285)](https://esacode.com/)

</div>

> **For research and teaching only.** Not a medical device: not for diagnosis, treatment or any clinical decision.

## Overview

A CT scan is a stack of grey slices. This project turns it into a 3D model per structure (organs, bones, vessels, muscles), coloured as anatomy atlases do and grouped so you can show the skeleton alone, the organs, or the vessels. Each model is checked (pieces, holes, watertight), so the table says which ones are ready to print.

Cut through the anatomy with a plane and the cut face shows the **CT scan itself** at that place, in the grey levels a radiologist would see (soft tissue, bone or lung window), lined up with the models around it. The cut is fixed to the body: turn the model and the slice turns with it, so you can look at it face on from any side.

The second flow makes the anatomy soft. It follows the metaball soft-tissue method of **Gianluca De Novi, PhD** ([thesis, PDF](https://amsdottorato.unibo.it/id/eprint/3702/1/DeNovi_Gianluca_tesi.pdf)): each organ becomes a tree of spheres whose centres are particles joined by elastic links, the skeleton is fixed, and a skin layer from the body's outline contains the organs. The organs' own surfaces are kept: their vertices slide on the iso-surface of the spheres as these move. Each organ weighs what its volume of tissue weighs and has its own measured stiffness; organs collide with each other and with the bones, and a chest wall closes the gaps between the ribs; muscles are tied to the bones where they meet them. Turn the body with the mouse or a 3D mouse and the organs sag, sway and settle; pull one and its neighbours follow. Switch on **Metaballs** to see the spheres themselves move.

Where the segmentations come from:

| Flow | Segmentation | Scans |
|---|---|---|
| 1 · CT to 3D anatomy | **Expert labels**, drawn by hand, that come with the dataset | TotalSegmentator dataset only |
| 2 · Soft tissue under gravity | **Expert labels**, as flow 1 | TotalSegmentator dataset only |
| 3 · Segment any CT automatically | **Automatic**: the TotalSegmentator network segments 117 structures | **Any CT**: the dataset, or your own scans (NIfTI, NRRD, MHA or DICOM) |

Flow 3 writes its masks in the same layout as the expert labels, so the same blocks turn them into 3D models, the CT on the cut and the skin. When a dataset also has expert labels, flow 3 scores the network against them.

## Flows

### 1 · CT to 3D anatomy (expert labels)

[**Open the blueprint →**](https://esacode.com/app/projects/6/flows/18)

A case of the TotalSegmentator dataset (s1400: neck to pelvis) read out of the online archive, checked, shown as slices with the anatomy over them, and turned into 3D models you can cut through, with the CT on the cut.

| Block | What it does |
|---|---|
| **TotalSegmentator dataset (Zenodo)** | Reads the chosen cases (the CT and the experts' masks) out of the dataset's archive, kept in the machine's cache. |
| **Read and check the scans** | Checks each scan and makes the axial, coronal and sagittal previews with the structures over them. |
| **Expert labels to 3D models** | One clean, coloured model per structure: a GLB scene for the 3D view and STL files for printing. |
| **The CT, for the cut in the 3D view** | The CT resampled into the models' own frame, as a compact volume (`<case>_ct.ctvol`) the 3D view paints on the cut. |
| **3D anatomy** | The models: parts list, cut with the CT on its face, the mouse and the 3D mouse turn the model in your hand. |
| **Slices**, **The scans**, **Every model** | The previews, the scans' details, and every model's volume and whether it is ready to print. |

### 2 · Soft tissue under gravity

[**Open the blueprint →**](https://esacode.com/app/projects/6/flows/19)

The same case as a soft-tissue model, simulated in the 3D view. The cut turns with the body here too; it shows the inside of the models, since the organs move away from where the CT saw them.

### 3 · Segment any CT automatically (TotalSegmentator)

[**Open the blueprint →**](https://esacode.com/app/projects/6/flows/118)

Any CT, segmented by a neural network instead of by hand, then turned into the same 3D anatomy as flow 1. As it comes, it takes case s1400 of the dataset, so the network's result is scored against the experts' labels of the same scan. To run it on your own scans, see [Test flow 3 with your own scans](#test-flow-3-with-your-own-scans).

| Block | What it does |
|---|---|
| **CT scans** | Where the scans come from: case s1400 from Zenodo as it comes; replace it with your own dataset. |
| **Segment the CT automatically (TotalSegmentator)** | Runs the network on every scan (DICOM series are converted first, without their patient tags) and writes each case as `<case>/ct.nii.gz` + `<case>/segmentations/<structure>.nii.gz`, the layout every block after it reads. |
| **Network labels to 3D models**, **The CT, for the cut**, **The skin (no physics)** | The same blocks as flow 1, fed with the network's masks. |
| **Score the network against the experts** | Dice and volume per structure, for cases that have expert labels too; the worst structures first. |
| **Slices**, **Structures the network found**, **3D anatomy**, **Every model**, **Network vs experts** | The views. |

Settings of the segmentation block:

| Setting | Choices | Notes |
|---|---|---|
| **Task** | `total` (default), `total_mr`, `body`, `lung_vessels`, `liver_vessels`, `liver_segments`, `kidney_cysts`, `pleural_pericard_effusion`, `cerebral_bleed`, `hip_implant`, `head_glands_cavities`, `headneck_bones_vessels`, `head_muscles`, `headneck_muscles` | `total`: 117 structures of a CT. The others add detail to one region. Only TotalSegmentator's open tasks are offered. |
| **Resolution** | 1.5 mm (best), 3 mm (fast), 6 mm (fastest) | `total`, `total_mr` and `body` only. 3 mm is several times faster and fine for large organs; ribs and small vessels lose detail. |
| **Only these structures** | names separated by commas, such as `liver, spleen, kidney_left, aorta` | `total` / `total_mr` only. The network runs only on the part of the scan it needs: faster. Empty: all. |
| **Run on** | auto (default), NVIDIA GPU, CPU | auto and NVIDIA GPU send the block to a worker with an NVIDIA GPU; the run waits while none is online. CPU: any worker. |
| **Scan file name** | a pattern, such as `ct.nii.gz` or `*.nrrd` | Which volumes are the scans when a folder holds other volumes too. Empty: every volume that is not a mask or a label map. |
| **Keep empty masks** | off (default) | The network writes a mask for each structure of the task, also those outside the scan; off keeps only what it found. |

On case s1400 the network reached a mean Dice of 0.95 against the experts (median 0.97; 99 of 110 structures above 0.9; skeleton 0.97, muscles 0.98, lungs 0.97, heart 0.95, organs 0.92, vessels 0.91). TotalSegmentator was trained on this dataset, so expect lower scores on scans from elsewhere, above all for small vessels and for structures cut by the edge of the scan (vertebra C6 here, at the top of the scan: 0.56).

## Test flow 3 with your own scans

### 1. Prepare the scans

Each **case** is one CT scan. The segmentation block finds the cases by itself in any of these layouts, and they can be mixed in one dataset:

```
my-ct-scans/
├── patient01.nii.gz              ← A. one file per case: the case is "patient01"
├── patient02.nrrd
├── case07/
│   └── ct.nii.gz                 ← B. a folder per case, with one volume: the case is "case07"
├── case08/
│   ├── ct.nii.gz
│   └── segmentations/            ← optional expert labels (for the score), skipped as scans
│       ├── liver.nii.gz
│       └── kidney_left.nii.gz
└── study_0042/                   ← C. DICOM: a folder per series, the case is "study_0042"
    ├── IM0001.dcm
    ├── IM0002.dcm
    └── …
```

- **Formats:** NIfTI (`.nii`, `.nii.gz`), NRRD (`.nrrd`, `.nhdr`), MHA/MHD, or the files of DICOM series (with or without the `.dcm` extension).
- **DICOM:** put one series per folder if you can. A folder that holds several series gives one case per series (`study_0042`, `study_0042_2`…, the largest first). Series with fewer than 10 images (scouts, localisers, single images) are skipped.
- **Skipped on purpose:** anything inside a folder named `segmentations`, `segmentation`, `masks`, `mask`, `labels` or `label`, and volumes that look like label maps (whole numbers with fewer than 64 values). So a dataset that already has labels can be wired as it is.
- **A folder with several volumes** gives one case per volume, named after the file. If only one of them is the CT, set **Scan file name** (such as `ct.nii.gz`).
- **The CT should be in Hounsfield units**, as scanners write them. The meshing works on any scan, but the CT on the cut (−1024 to +1536 HU) and the skin (the body above −300 HU) assume CT values.
- **Names show up in the results:** each case is named after its file or folder, and that name appears in the tables, file names and the 3D view's list. DICOM tags are not copied, but **rename folders or files that carry a patient's name or ID before you upload them**.

**Expert labels, for the score (optional):** put them next to the CT as `<case>/segmentations/<structure>.nii.gz` (layout B), one binary mask per structure, on the same voxel grid as the CT, named as TotalSegmentator names them (`liver`, `kidney_left`, `vertebrae_L1`, `rib_left_3`… the names in the **Structures the network found** table). Structures are matched by case folder and file name; other names are listed with Dice 0.

### 2. Put the scans where a worker can read them

Choose one:

| Where | How | Good for |
|---|---|---|
| **A dataset in EsaSim storage** | Project › **Data › Datasets** › new dataset in *EsaSim storage*, then upload the files (keep the folders). | A few scans, from any computer. The files go to EsaSim's servers and are downloaded by the worker before the block starts. |
| **A dataset in a worker's folder** | Project › **Data › Datasets** › new dataset in a worker's *Storage* folder (on Server2: `C:\Users\gianl\OneDrive\Desktop\EsaSim\data\storage`), then copy the files into its folder on that machine. | Many or large scans, and **scans that must not leave your machines**: they are read in place, so the blocks run on that worker. |
| **A folder on a worker, without a dataset** | The **Files on a worker** block, with the folder's full path as the worker sees it. | A quick test on scans already on a machine. |

### 3. Wire them into flow 3

1. Open [flow 3](https://esacode.com/app/projects/6/flows/118) under **Blueprint**.
2. Delete the **CT scans** block (it downloads case s1400 from Zenodo).
3. Add your source from the block menu, **Data** category:
   - **Dataset**: choose your dataset, **Version** `latest` (or a number to repeat a run exactly). Leave **Only these files** at `*`: DICOM files often have no extension.
   - or **Files on a worker**: **Folder on the worker** = the full path, **Include subfolders** on, and **raise its limits**: they default to 500 files and 200 MB, too few for CT (one CT is often 30 to 300 MB, a DICOM series hundreds of files). For example **At most (files)** 100000 and **At most (MB in total)** 20000.
4. Connect the source's **Files** output to the **Scans** input of **Segment the CT automatically**.
5. The score:
   - **With expert labels:** also connect **Files** to the **Experts** input of **Score the network against the experts**.
   - **Without them:** delete the score block and its **Network vs experts** view. Left in the flow with nothing to compare, it fails at the end of the run.
6. Settings of **Segment the CT automatically** for a first test:
   - **Run on:** *auto* if a worker with an NVIDIA GPU is online, else *CPU*.
   - On the CPU, start with **Resolution** *3 mm (fast)*, or a few structures in **Only these structures**, or a dataset of one or two cases: at 1.5 mm a case takes about 12 to 15 minutes on the CPU.
7. Press **Run**.

### 4. Check what you get

- **The run's log, block "Segment the CT automatically":** one line per case with its size and voxel spacing; *Segmenting on the GPU: …* or *segmenting on the CPU*; then `<case>: N structures found (of 117 the task knows)`. Scans it skipped are named, with the reason.
- **Slices, with the network's anatomy over them:** the first thing to look at. The colours should lie on the organs; a mask shifted or spilled over the body shows a wrong orientation or a scan the network does not know.
- **Structures the network found:** every structure with its volume in ml. Volumes far from the usual (a liver of 300 ml, a spleen of 3 l) are worth a look.
- **3D anatomy:** one model per case, chosen from the list in the corner, with the CT on the cut.
- **Every model:** which models are ready to print.
- **Network vs experts** (with expert labels): the worst structures first. Above 0.9 is very good for organs and bones; thin vessels and structures cut by the edge of the scan score lower.
- **Results:** the masks (`<case>/segmentations/*.nii.gz`, for 3D Slicer or any other tool), the STL files and the GLB scenes. They stay on the worker until you download them.

### 5. If something goes wrong

| What you see | Why, and what to do |
|---|---|
| *No CT scan among the inputs* | The files are all inside a `segmentations`/`masks`/`labels` folder, **Scan file name** matches none of them, or the source's limits cut the files off. |
| *&lt;case&gt;: looks like a label map, not a scan: skipped* | That volume has fewer than 64 different values: it is a mask or a label map. If it really is a scan, check that it was exported in HU, not as an 8-bit picture. |
| *&lt;case&gt;: the scan could not be read* | A broken file, or a DICOM folder that is not one 3D series. Re-export it as NIfTI (3D Slicer, `dcm2niix`). |
| A DICOM folder gives no case | Its series have fewer than 10 images, or the files are not DICOM. |
| The run waits and does not start | **Run on** is *auto* or *NVIDIA GPU* and no worker with an NVIDIA GPU is online: start one, or choose *CPU*. |
| *No CUDA GPU seen by PyTorch: segmenting on the CPU* | The worker has a GPU but PyTorch cannot use it there. The run goes on, slower; the log line before it gives the PyTorch build and `CUDA_VISIBLE_DEVICES`. |
| *TotalSegmentator stopped on &lt;case&gt;* | The network's own message follows. Most often: no internet on the first run (the weights, about 1.2 GB, are downloaded once into the worker's `~/.totalsegmentator`), or not enough memory for a very large scan: try *3 mm (fast)*. |
| Masks look wrong on an MR scan | Use the `total_mr` task. The CT on the cut and the skin assume CT values and do not suit MR. |
| *No case on both sides* (score block) | The expert labels are not in `<case>/segmentations/` folders named like the cases, or the dataset has none: delete the score block. |

**A quick test without your own data:** keep the **CT scans** block and set its **Cases** to other names of the dataset or to a number (such as `3`: three cases at random, the same three each time). Every case has expert labels, so each one is scored. Remember the network learned from this dataset.

## What you need

- A machine with the EsaSim worker (Project › Compute). Flows 1 and 2: any machine, no GPU needed. Flow 3: a worker with an NVIDIA GPU for **Run on** *auto* or *NVIDIA GPU* (about 1 to 3 minutes a case), or any worker with **Run on** *CPU* (about 12 to 15 minutes a case at 1.5 mm, a few minutes at 3 mm).
- Internet access on that machine: the case is read from Zenodo the first time and kept in its cache; flow 3 also downloads the network's weights once (about 1.2 GB, into the worker's `~/.totalsegmentator`). Your own scans are never sent anywhere by the network, and TotalSegmentator's usage statistics are turned off.
- Python packages, installed by the worker the first time: `SimpleITK`, `numpy`, `scipy`, `scikit-image`, `trimesh`, `fast-simplification`, `pillow`, `requests`; for flow 3 also `TotalSegmentator` and `torch` (a CUDA build for the GPU), about 1 minute to install.
- A computer with a recent browser (WebGL 2) to open the 3D view: the CT on the cut and, in flow 2, the simulation run on the computer that shows it.
- No account or key.

## How to run it

1. Under **Compute**, check that a machine is available for this project (for flow 3 on the GPU: a machine with an NVIDIA GPU).
2. Open a flow under **Blueprint**. To change the case, set **Cases** of the download block: names such as `s1400, s0513` (the 3D view then has a list to choose one), or a number (taken at random, repeatably). In flow 3 you can wire your own scans instead: see [Test flow 3 with your own scans](#test-flow-3-with-your-own-scans).
3. Press **Run**. The first run reads the case (about 30 MB) out of the dataset's archive; the next runs use the cache. The first run of flow 3 on a worker also installs the network and downloads its weights.
4. Open the **View**.
5. To look inside: in the Parts list, choose a cut (**Cut across**, **Front to back**, **Side to side**), move it with the slider, and choose what the **Cut face** shows. Drag to turn the body until the cut faces you; **⇄** keeps the other side.

## What you get

- **3D anatomy**: each tissue has its own procedural surface under a wet coat (liver lobules, bowel folds, muscle fibres, the heart's folds and fat, the lung's air sacs, bone darker and yellowish in its hollows…); **Tissue textures** in the Parts list turns it off. In the Parts list, show or hide each group or structure, find one by name; point at a model to see its name. The list folds into a button. The mouse drag and the 3D mouse turn the model in your hand (Ctrl + drag moves it).
- **Cut with the CT on it**: a plane across, front to back or side to side, fixed to the body so it turns with it. Its face shows the scan at that place:

  | Cut face | Shows |
  |---|---|
  | **CT · soft tissue** (default) | Organs, muscle, fat and vessels (window 400 HU around 40 HU) |
  | **CT · bone** | Bone structure (window 1800 HU around 400 HU) |
  | **CT · lung** | Lung tissue and airways (window 1500 HU around −600 HU) |
  | **Inside of the models** | The models' inner surfaces, without the CT |

  Only the body is painted: the air and the table around it stay clear. The CT is resampled at about 2.7 mm per voxel for this case (**Size** on the CT block: 256 voxels on the longest side; up to 512 for a sharper slice and a larger file).
- **Soft tissue** (flow 2), at the top of the Parts list: Gravity (0 to 3 g), Softness, Damping, Pause, Reset, **Pull** to drag an organ, and **Metaballs** to see the spheres of the model move (the anatomy turns see-through around them). "Lying on the back is at rest" takes away the gravity the scan was taken under (the patient lay on the back), so the organs move only when the body is turned from that pose.
- **Slices**: axial, coronal and sagittal slices of the scan, with the structures coloured over them.
- **Tables**: every structure with its volume (ml), triangles and whether it is ready to print; in flow 2, its tissue, number of spheres, links to bone, volume (ml), mass (g), stiffness and density; in flow 3, the structures the network found (`segmentation.csv`) and the Dice of each against the experts (`score.csv`, with a `summary.json` of the means per group).
- **Masks** (flow 3), `<case>/segmentations/<structure>.nii.gz`, one per structure, with the scan as `<case>/ct.nii.gz`, under **Results**: usable in 3D Slicer or any other tool.
- **STL files**, in millimetres, one per structure, under **Results** (they stay on the machine until you download them).
- **CT volume** (`<case>_ct.ctvol`), for the 3D view: the scan in the models' frame (x to the patient's left, y up, z towards the face, metres), 8-bit, compressed (about 2 MB a case).

## Data, method and licences

- **TotalSegmentator dataset v2.0.1, small subset** (102 CT scans with segmentations of 117 structures), [Zenodo record 10047263](https://zenodo.org/records/10047263), licence **CC BY 4.0**. Wasserthal J., Breit H.-C., Meyer M.T., et al. *TotalSegmentator: Robust Segmentation of 104 Anatomic Structures in CT Images.* Radiology: Artificial Intelligence 2023; 5(5): e230024. The scans are anonymised by their publishers.
- **Segmentation network** (flow 3): [TotalSegmentator](https://github.com/wasserth/TotalSegmentator) (nnU-Net), same citation as above, Apache-2.0; only its open tasks are offered. It runs in its own process on the worker; its anonymous usage statistics are turned off by the block. DICOM series are converted to NIfTI with pixels and geometry only: no patient tags are written.
- **Soft-tissue method**: Gianluca De Novi, PhD. *Soft Tissue Modeling for Virtual Reality Surgery Simulator with Haptic Feedback.* PhD thesis, Università di Bologna, 2011 ([AMS Dottorato](https://amsdottorato.unibo.it/id/eprint/3702/), [PDF](https://amsdottorato.unibo.it/id/eprint/3702/1/DeNovi_Gianluca_tesi.pdf)). Here: sphere trees by medial axis approximation from the segmentation, spring-damper links, a fixed skeleton (each bone covered by as many spheres as it needs), a chest wall of fixed spheres between the ribs (the intercostal muscles are not segmented), a skin layer, contact between structures and with the bones, muscles tied to the bones by elastic links where they touch them, masses from each structure's real volume (shared by its spheres in proportion to their volumes), and the organs' surfaces sliding on the iso-surface of their spheres (no marching cubes at run time: the surfaces come from the segmentation).
- **Tissue values**: the stiffness of liver, spleen, pancreas, kidney, thyroid and muscle is as measured in healthy adults by shear-wave elastography ([Viceconti et al., World J Radiol 2025](https://www.wjgnet.com/1949-8470/full/v17/i11/111651.htm); [Arda et al., AJR 2011](https://avesis.ankara.edu.tr/yayin/bb4273a5-b04a-4164-ab2e-9579f52e1cfa/quantitative-assessment-of-normal-soft-tissue-elasticity-using-shear-wave-ultrasound-elastography)); the other tissues use orders of magnitude from the literature. The values are the same for every patient: the motion is plausible, not validated. A Tissues table can change them.
- The code of the blocks is EsaSim's.
- **Your own scans** are yours: check that you may use them (ethics approval, consent, data protection) before uploading them, and prefer a worker's own folder for scans that must stay on your machines.

## Notes

- The 3D scene of a case is lightened to about 300,000 triangles so it opens quickly in the browser; the STL files keep every triangle.
- Thin structures (small vessels, ribs) can break into pieces at the scan's resolution: the table says so.
- The CT on the cut is a resampled copy for viewing (8-bit, about 10 HU per grey level): fine for teaching, not for measuring densities. The body outline that keeps the air clear is found automatically; a patient table touching the body can be painted with it.
- The tissue that is not segmented (fat, membranes) holds each organ near its place with a soft support; the organs do not touch the skin's inner side everywhere.
- A large case can be more than a computer can simulate in real time: the view stays smooth and the tissue moves in slow motion (the Soft tissue line says how fast).
- The tissue textures and the CT on the cut are computed by the graphics card for every pixel; on a very old or weak graphics card, turn the textures off if the view feels slow.
- The network's masks are a first draft, not a reading: check them on the slices before relying on a model, above all on scans unlike those the network learned from (children, implants, strong contrast, cropped fields of view).
- The soft-tissue model of flow 2 can be fed with the network's masks too: in flow 2, wire the **Segmented cases** of the segmentation block into the Soft body model's **Labels** and **Scans** instead of the dataset's files.

<!-- esasim: files of the project -->

---

An [EsaSim](https://esacode.com/) project of the workspace Gianluca De Novi's workspace (Medical & healthcare).

### Blueprints in this repository

- [1 · CT to 3D anatomy (expert labels)](blueprints/1-ct-to-3d-anatomy-expert-labels.json) · 9 blocks · version 5
- [2 · Soft tissue under gravity](blueprints/2-soft-tissue-under-gravity.json) · 5 blocks · version 6
- [3 · Segment any CT automatically (TotalSegmentator)](blueprints/3-segment-any-ct-automatically-totalsegmentator.json) · 16 blocks · version 2

### Workspace blocks it uses

- [Expert labels to 3D models (clean)](blocks/ws-expert-labels-to-3d-models-clean) · version 2
- [CT volume for the 3D view](blocks/ws-ct-volume-for-the-3d-view) · version 5
- [Soft body model (skin inside)](blocks/ws-soft-body-model-skin-inside) · version 5
- [3D view (stable soft tissue)](blocks/ws-3d-view-stable-soft-tissue) · version 62
- [Load CT scans (DICOM discs, NIfTI, NRRD, MHA)](blocks/ws-load-ct-scans-dicom-discs-nifti-nrrd) · version 1
- [Segment CT automatically (TotalSegmentator)](blocks/ws-segment-ct-automatically-totalsegmen) · version 7
- [Score segmentation against experts](blocks/ws-score-segmentation-against-experts) · version 2
- [Load a CT](blocks/ws-load-a-ct) · version 1

### Assets

The files the project's views draw with (3D models, textures, sounds), in [assets/](assets/):

- [textures/esacode-logo.png](assets/textures/esacode-logo.png) · 25 KB

Keys pasted in blocks (secret settings) are not saved here, nor are the team and the results of runs.
