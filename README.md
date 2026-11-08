<div align="center">

<!-- Banner: upload a picture named banner.png under Data › Readme pictures (a screenshot of the 3D view works well), then: ![CT to 3D anatomy](pictures/banner.png) -->

# CT to 3D anatomy

**From a CT scan to coloured 3D models of every organ, bone and vessel.**

Open the anatomy in the browser, hide and show structures, cut through them, and download STL files ready for a 3D printer.

![type](https://img.shields.io/badge/type-Medical%20%26%20healthcare-blue) ![language](https://img.shields.io/badge/language-Python-3776AB) ![runs on](https://img.shields.io/badge/runs%20on-CPU-6f42c1) ![data](https://img.shields.io/badge/data-CC%20BY%204.0-green) [![made with](https://img.shields.io/badge/made%20with-EsaSim-0b7285)](https://esacode.com/)

</div>

> **For research and teaching only.** Not a medical device: not for diagnosis, treatment or any clinical decision.

## Overview

A CT scan is a stack of grey slices. This project turns it into a 3D model per structure (organs, bones, vessels, muscles), coloured as anatomy atlases do and grouped so you can show the skeleton alone, the organs, or the vessels. Each model is checked (pieces, holes, watertight), so the table says which ones are ready to print.

The first flow uses CT scans that come with **expert segmentations** (the TotalSegmentator dataset): the 3D models are built from the experts' labels. Next flows add the segmentation network (TotalSegmentator on CPU, NVIDIA or Tenstorrent), a score of the network against the experts, and DICOM scans straight from a scanner, anonymised first.

## Flows

- **1 · CT to 3D anatomy (expert labels)**: three cases of the TotalSegmentator dataset read out of the online archive, checked, shown as slices with the anatomy over them, and turned into 3D models.

## What you need

- A machine with the EsaSim worker (Project › Compute). Any machine: no GPU is needed for this flow.
- Internet access on that machine: the cases are read from Zenodo the first time and kept in its cache.
- Python packages, installed by the worker the first time: `SimpleITK`, `numpy`, `scipy`, `scikit-image`, `trimesh`, `fast-simplification`, `pillow`, `requests`.
- No account or key.

## How to run it

1. Under **Compute**, check that a machine is available for this project.
2. Open **1 · CT to 3D anatomy** under **Blueprint**. To change the cases, set **Cases** of the download block: a number (taken at random, repeatably) or names such as `s0011, s0040`.
3. Press **Run**. The first run reads each case (about 30 MB) out of the dataset's archive; the next runs use the cache.
4. Open the **View**: the slices of each scan with the anatomy coloured over them, the 3D anatomy, and the table of models.

## What you get

- **3D anatomy**: one scene per case. In the Parts list, show or hide each group or structure, find one by name; point at a model to see its name; cut through with a plane (across, front to back, side to side).
- **Slices**: axial, coronal and sagittal slices of each scan, with the structures coloured over them.
- **Models table**: every structure with its volume (ml), its triangles, and whether it is ready to print.
- **STL files**, in millimetres, one per structure, under **Results** (they stay on the machine until you download them).

## Data and licences

- **TotalSegmentator dataset v2.0.1, small subset** (102 CT scans with segmentations of 117 structures), [Zenodo record 10047263](https://zenodo.org/records/10047263), licence **CC BY 4.0**. Wasserthal J., Breit H.-C., Meyer M.T., et al. *TotalSegmentator: Robust Segmentation of 104 Anatomic Structures in CT Images.* Radiology: Artificial Intelligence 2023; 5(5): e230024. The scans are anonymised by their publishers.
- The code of the blocks is EsaSim's. The segmentation network of the next flows (TotalSegmentator) is used with its open tasks only, under the Apache-2.0 licence.

## Notes

- The 3D scene of a case is lightened to about 300,000 triangles so it opens quickly in the browser; the STL files keep every triangle.
- Thin structures (small vessels, ribs) can break into pieces at the scan's resolution: the table says so.
- If the data server does not send parts of files, the first run downloads the whole archive (3.2 GB) once.

<!-- esasim: files of the project -->

---

An [EsaSim](https://esacode.com/) project of the workspace Gianluca De Novi's workspace (Medical & healthcare).

### Blueprints in this repository

- [1 · CT to 3D anatomy (expert labels)](blueprints/1-ct-to-3d-anatomy-expert-labels.json) · 7 blocks · version 2

Keys pasted in blocks (secret settings) are not saved here. Datasets, results and the team stay in EsaSim.
