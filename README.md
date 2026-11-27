<!-- esasim: cover -->
![CT to 3D anatomy](assets/cover.jpg)
<!-- /esasim: cover -->

<div align="center">

<!-- Banner: upload a picture named banner.png under Data › Readme pictures (a screenshot of the 3D view works well), then: ![CT to 3D anatomy](pictures/banner.png) -->

# CT to 3D anatomy

**From a CT scan to coloured 3D models of every organ, bone and vessel, and soft tissue that moves under gravity.**

Open the anatomy in the browser, hide and show structures, cut through them and see the CT itself on the cut, turn the body and watch the organs move, and download STL files ready for a 3D printer.

![type](https://img.shields.io/badge/type-Medical%20%26%20healthcare-blue) ![language](https://img.shields.io/badge/language-Python-3776AB) ![runs on](https://img.shields.io/badge/runs%20on-CPU-6f42c1) ![data](https://img.shields.io/badge/data-CC%20BY%204.0-green) [![made with](https://img.shields.io/badge/made%20with-EsaSim-0b7285)](https://esacode.com/)

</div>

> **For research and teaching only.** Not a medical device: not for diagnosis, treatment or any clinical decision.

## Overview

A CT scan is a stack of grey slices. This project turns it into a 3D model per structure (organs, bones, vessels, muscles), coloured as anatomy atlases do and grouped so you can show the skeleton alone, the organs, or the vessels. Each model is checked (pieces, holes, watertight), so the table says which ones are ready to print.

Cut through the anatomy with a plane and the cut face shows the **CT scan itself** at that place, in the grey levels a radiologist would see (soft tissue, bone or lung window), lined up with the models around it. The cut is fixed to the body: turn the model and the slice turns with it, so you can look at it face on from any side.

The second flow makes the anatomy soft. It follows the metaball soft-tissue method of **Gianluca De Novi, PhD** ([thesis, PDF](https://amsdottorato.unibo.it/id/eprint/3702/1/DeNovi_Gianluca_tesi.pdf)): each organ becomes a tree of spheres whose centres are particles joined by elastic links, the skeleton is fixed, and a skin layer from the body's outline contains the organs. The organs' own surfaces are kept: their vertices slide on the iso-surface of the spheres as these move. Each organ weighs what its volume of tissue weighs and has its own measured stiffness; organs collide with each other and with the bones, and a chest wall closes the gaps between the ribs; muscles are tied to the bones where they meet them. Turn the body with the mouse or a 3D mouse and the organs sag, sway and settle; pull one and its neighbours follow. Switch on **Metaballs** to see the spheres themselves move.

Both flows use CT scans that come with **expert segmentations** (the TotalSegmentator dataset). Next flows add the segmentation network (TotalSegmentator on CPU, NVIDIA or Tenstorrent), a score of the network against the experts, and DICOM scans straight from a scanner, anonymised first.

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

## What you need

- A machine with the EsaSim worker (Project › Compute). Any machine: no GPU is needed.
- Internet access on that machine: the case is read from Zenodo the first time and kept in its cache.
- Python packages, installed by the worker the first time: `SimpleITK`, `numpy`, `scipy`, `scikit-image`, `trimesh`, `fast-simplification`, `pillow`, `requests`.
- A computer with a recent browser (WebGL 2) to open the 3D view: the CT on the cut and, in flow 2, the simulation run on the computer that shows it.
- No account or key.

## How to run it

1. Under **Compute**, check that a machine is available for this project.
2. Open a flow under **Blueprint**. To change the case, set **Cases** of the download block: names such as `s1400, s0513` (the 3D view then has a list to choose one), or a number (taken at random, repeatably).
3. Press **Run**. The first run reads the case (about 30 MB) out of the dataset's archive; the next runs use the cache.
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
- **Tables**: every structure with its volume (ml), triangles and whether it is ready to print; in flow 2, its tissue, number of spheres, links to bone, volume (ml), mass (g), stiffness and density.
- **STL files**, in millimetres, one per structure, under **Results** (they stay on the machine until you download them).
- **CT volume** (`<case>_ct.ctvol`), for the 3D view: the scan in the models' frame (x to the patient's left, y up, z towards the face, metres), 8-bit, compressed (about 2 MB a case).

## Data, method and licences

- **TotalSegmentator dataset v2.0.1, small subset** (102 CT scans with segmentations of 117 structures), [Zenodo record 10047263](https://zenodo.org/records/10047263), licence **CC BY 4.0**. Wasserthal J., Breit H.-C., Meyer M.T., et al. *TotalSegmentator: Robust Segmentation of 104 Anatomic Structures in CT Images.* Radiology: Artificial Intelligence 2023; 5(5): e230024. The scans are anonymised by their publishers.
- **Soft-tissue method**: Gianluca De Novi, PhD. *Soft Tissue Modeling for Virtual Reality Surgery Simulator with Haptic Feedback.* PhD thesis, Università di Bologna, 2011 ([AMS Dottorato](https://amsdottorato.unibo.it/id/eprint/3702/), [PDF](https://amsdottorato.unibo.it/id/eprint/3702/1/DeNovi_Gianluca_tesi.pdf)). Here: sphere trees by medial axis approximation from the segmentation, spring-damper links, a fixed skeleton (each bone covered by as many spheres as it needs), a chest wall of fixed spheres between the ribs (the intercostal muscles are not segmented), a skin layer, contact between structures and with the bones, muscles tied to the bones by elastic links where they touch them, masses from each structure's real volume (shared by its spheres in proportion to their volumes), and the organs' surfaces sliding on the iso-surface of their spheres (no marching cubes at run time: the surfaces come from the segmentation).
- **Tissue values**: the stiffness of liver, spleen, pancreas, kidney, thyroid and muscle is as measured in healthy adults by shear-wave elastography ([Viceconti et al., World J Radiol 2025](https://www.wjgnet.com/1949-8470/full/v17/i11/111651.htm); [Arda et al., AJR 2011](https://avesis.ankara.edu.tr/yayin/bb4273a5-b04a-4164-ab2e-9579f52e1cfa/quantitative-assessment-of-normal-soft-tissue-elasticity-using-shear-wave-ultrasound-elastography)); the other tissues use orders of magnitude from the literature. The values are the same for every patient: the motion is plausible, not validated. A Tissues table can change them.
- The code of the blocks is EsaSim's. The segmentation network of the next flows (TotalSegmentator) is used with its open tasks only, under the Apache-2.0 licence.

## Notes

- The 3D scene of a case is lightened to about 300,000 triangles so it opens quickly in the browser; the STL files keep every triangle.
- Thin structures (small vessels, ribs) can break into pieces at the scan's resolution: the table says so.
- The CT on the cut is a resampled copy for viewing (8-bit, about 10 HU per grey level): fine for teaching, not for measuring densities. The body outline that keeps the air clear is found automatically; a patient table touching the body can be painted with it.
- The tissue that is not segmented (fat, membranes) holds each organ near its place with a soft support; the organs do not touch the skin's inner side everywhere.
- A large case can be more than a computer can simulate in real time: the view stays smooth and the tissue moves in slow motion (the Soft tissue line says how fast).
- The tissue textures and the CT on the cut are computed by the graphics card for every pixel; on a very old or weak graphics card, turn the textures off if the view feels slow.

<!-- esasim: files of the project -->

---

An [EsaSim](https://esacode.com/) project of the workspace Gianluca De Novi's workspace (Medical & healthcare).

### Blueprints in this repository

- [1 · CT to 3D anatomy (expert labels)](blueprints/1-ct-to-3d-anatomy-expert-labels.json) · 9 blocks · version 5
- [2 · Soft tissue under gravity](blueprints/2-soft-tissue-under-gravity.json) · 5 blocks · version 6

### Workspace blocks it uses

- [Expert labels to 3D models (clean)](blocks/ws-expert-labels-to-3d-models-clean) · version 2
- [CT volume for the 3D view](blocks/ws-ct-volume-for-the-3d-view) · version 1
- [Soft body model (skin inside)](blocks/ws-soft-body-model-skin-inside) · version 5
- [3D view (stable soft tissue)](blocks/ws-3d-view-stable-soft-tissue) · version 57

### Assets

The files the project's views draw with (3D models, textures, sounds), in [assets/](assets/):

- [textures/esacode-logo.png](assets/textures/esacode-logo.png) · 25 KB

Keys pasted in blocks (secret settings) are not saved here, nor are the team and the results of runs.
