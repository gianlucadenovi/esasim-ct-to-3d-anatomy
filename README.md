<div align="center">

<!-- Banner: upload a picture named banner.png under Data › Readme pictures (a screenshot of the 3D view works well), then: ![CT to 3D anatomy](pictures/banner.png) -->

# CT to 3D anatomy

**From a CT scan to coloured 3D models of every organ, bone and vessel, and soft tissue that moves under gravity.**

Open the anatomy in the browser, hide and show structures, cut through them, turn the body and watch the organs move, and download STL files ready for a 3D printer.

![type](https://img.shields.io/badge/type-Medical%20%26%20healthcare-blue) ![language](https://img.shields.io/badge/language-Python-3776AB) ![runs on](https://img.shields.io/badge/runs%20on-CPU-6f42c1) ![data](https://img.shields.io/badge/data-CC%20BY%204.0-green) [![made with](https://img.shields.io/badge/made%20with-EsaSim-0b7285)](https://esacode.com/)

</div>

> **For research and teaching only.** Not a medical device: not for diagnosis, treatment or any clinical decision.

## Overview

A CT scan is a stack of grey slices. This project turns it into a 3D model per structure (organs, bones, vessels, muscles), coloured as anatomy atlases do and grouped so you can show the skeleton alone, the organs, or the vessels. Each model is checked (pieces, holes, watertight), so the table says which ones are ready to print.

The second flow makes the anatomy soft: following the metaball soft-tissue method of Gianluca De Novi, each organ becomes a tree of spheres whose centres are particles joined by elastic links, the skeleton is fixed, and a skin layer from the body's outline contains the organs. The organs' own surfaces are kept: their vertices slide on the iso-surface of the spheres as these move. Turn the body with the mouse or a 3D mouse and the organs sag, sway and settle; pull one and its neighbours follow.

Both flows use CT scans that come with **expert segmentations** (the TotalSegmentator dataset). Next flows add the segmentation network (TotalSegmentator on CPU, NVIDIA or Tenstorrent), a score of the network against the experts, and DICOM scans straight from a scanner, anonymised first.

## Flows

- **1 · CT to 3D anatomy (expert labels)**: a case of the TotalSegmentator dataset (s1400: neck to pelvis) read out of the online archive, checked, shown as slices with the anatomy over them, and turned into 3D models.
- **2 · Soft tissue under gravity**: the same case as a soft-tissue model, simulated in the 3D view.

## What you need

- A machine with the EsaSim worker (Project › Compute). Any machine: no GPU is needed.
- Internet access on that machine: the case is read from Zenodo the first time and kept in its cache.
- Python packages, installed by the worker the first time: `SimpleITK`, `numpy`, `scipy`, `scikit-image`, `trimesh`, `fast-simplification`, `pillow`, `requests`.
- For flow 2, a computer with a recent browser: the simulation runs in the 3D view, on the computer that shows it.
- No account or key.

## How to run it

1. Under **Compute**, check that a machine is available for this project.
2. Open a flow under **Blueprint**. To change the case, set **Cases** of the download block: names such as `s1400, s0513` (the 3D view then has a list to choose one), or a number (taken at random, repeatably).
3. Press **Run**. The first run reads the case (about 30 MB) out of the dataset's archive; the next runs use the cache.
4. Open the **View**.

## What you get

- **3D anatomy**: in the Parts list, show or hide each group or structure, find one by name; point at a model to see its name; cut through with a plane (across, front to back, side to side). The list folds into a button. With a 3D mouse, the model turns in your hand.
- **Soft tissue** (flow 2), at the top of the Parts list: Gravity (0 to 3 g), Softness, Pause, Reset, and **Pull** to drag an organ. "Lying on the back is at rest" takes away the gravity the scan was taken under (the patient lay on the back), so the organs move only when the body is turned from that pose.
- **Slices**: axial, coronal and sagittal slices of the scan, with the structures coloured over them.
- **Tables**: every structure with its volume (ml), triangles and whether it is ready to print; in flow 2, its tissue, stiffness and number of spheres.
- **STL files**, in millimetres, one per structure, under **Results** (they stay on the machine until you download them).

## Data, method and licences

- **TotalSegmentator dataset v2.0.1, small subset** (102 CT scans with segmentations of 117 structures), [Zenodo record 10047263](https://zenodo.org/records/10047263), licence **CC BY 4.0**. Wasserthal J., Breit H.-C., Meyer M.T., et al. *TotalSegmentator: Robust Segmentation of 104 Anatomic Structures in CT Images.* Radiology: Artificial Intelligence 2023; 5(5): e230024. The scans are anonymised by their publishers.
- **Soft-tissue method**: De Novi G. *Soft Tissue Modeling for Virtual Reality Surgery Simulator with Haptic Feedback.* PhD thesis, Università di Bologna, 2011 ([AMS Dottorato](https://amsdottorato.unibo.it/id/eprint/3702/)). Here: sphere trees by medial axis approximation from the segmentation, spring-damper links, a fixed skeleton, a skin layer, contact between structures, and the organs' surfaces sliding on the iso-surface of their spheres (no marching cubes at run time: the surfaces come from the segmentation).
- **Tissue values** (stiffness, density, damping) are orders of magnitude from the literature on soft-tissue mechanics, the same for every patient: the motion is plausible, not measured or validated. They can be changed with a Tissues table.
- The code of the blocks is EsaSim's. The segmentation network of the next flows (TotalSegmentator) is used with its open tasks only, under the Apache-2.0 licence.

## Notes

- The 3D scene of a case is lightened to about 300,000 triangles so it opens quickly in the browser; the STL files keep every triangle.
- Thin structures (small vessels, ribs) can break into pieces at the scan's resolution: the table says so.
- The tissue that is not segmented (fat, membranes) holds each organ near its place with a soft support; the organs do not touch the skin's inner side everywhere.
- A large case can be more than a computer can simulate in real time: the view stays smooth and the tissue moves in slow motion (the Soft tissue line says how fast).

<!-- esasim: files of the project -->

---

An [EsaSim](https://esacode.com/) project of the workspace Gianluca De Novi's workspace (Medical & healthcare).

### Blueprints in this repository

- [1 · CT to 3D anatomy (expert labels)](blueprints/1-ct-to-3d-anatomy-expert-labels.json) · 7 blocks · version 2
- [2 · Soft tissue under gravity](blueprints/2-soft-tissue-under-gravity.json) · 5 blocks · version 1

Keys pasted in blocks (secret settings) are not saved here. Datasets, results and the team stay in EsaSim.
