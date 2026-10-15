# CT Anatomy Explorer

A free teaching website for CT anatomy. On public CT scans, two outlines are shown for each organ: one drawn by experts and one made by an AI model (VISTA-3D, from MONAI). The two outlines can be compared, and each organ can be learned with a short note.

> **Educational use only.** Not for diagnosis or any clinical decision.

**Open the website:** https://gunargrithvick.github.io/ct-anatomy-explorer/

## What it does

| Feature | Details |
|---|---|
| 12 organs | liver, spleen, pancreas, right and left kidney, gallbladder, stomach, aorta, inferior vena cava, oesophagus, duodenum, urinary bladder |
| Three views of the masks | **Expert** (reference), **AI** (VISTA-3D) and **Compare** (agree / AI-only / missed) |
| Scan viewer | axial, coronal, sagittal and 3D; CT windows for abdomen, lung and bone; radiology orientation |
| Teaching aids | tick organs on or off; click an organ name to jump to it; read the organ under the cursor |
| Numbers | Dice overlap and volumes (mL) per organ, plus automatic warnings for likely bugs |
| Downloads | CT copy, expert masks, full-resolution AI masks, scores (CSV), label key |

## Repository layout

```
docs/                 the website (GitHub Pages serves this folder)
  index.html, app.js, app.css
  vendor/niivue.umd.js  NiiVue viewer library (BSD-2-Clause, kept here so the site has no outside dependencies)
  data/               the 5 scans, the outlines and cases.json
notebooks/            ct_anatomy_explorer_kaggle.ipynb  - runs the AI pipeline on a free Kaggle GPU
pipeline/             the same pipeline as Python modules (for a rented GPU or a lab PC)
tools/build_notebook.py   rebuilds the notebook after editing pipeline/
tests/test_pipeline.py    quick checks, no GPU needed
guide/INTERN_GUIDE.md     day-by-day plan for the team
```

## Quick start

**1. Run the AI pipeline (Kaggle, free GPU).**
Kaggle → *Create* → *New Notebook* → *File* → *Import Notebook* → upload `notebooks/ct_anatomy_explorer_kaggle.ipynb`.
In *Session options* turn on **GPU T4 x2** and **Internet**. Run the cells in order. The last cell creates
`outputs/web_data.zip`.

**2. Put the results into the website.**
Delete `docs/data/`, then unzip `web_data.zip` inside `docs/` (it contains a fresh `data/` folder).
To keep only your best scans: `python tools/select_cases.py docs/data <id1> <id2> ...`

**3. Publish.** On GitHub: *Settings* → *Pages* → *Deploy from a branch* → branch `main`, folder `/docs` → *Save*.
After a minute or two the site is live at `https://<your-account>.github.io/<repo-name>/`.

**Preview on your own computer:**

```bash
python -m http.server -d docs 8000      # then open http://localhost:8000
```

(Opening `index.html` by double-clicking does not work, because browsers block loading the scan files that way.)

**Run the pipeline on a rented GPU (e.g. NVIDIA Brev) instead of Kaggle:**

```bash
pip install "monai==1.6.1" nibabel pytorch-ignite einops fire huggingface_hub requests scipy matplotlib
python -m pipeline.run_all --n-cases 10 --n-web 5      # results in outputs/, zip in outputs/web_data.zip
python tests/test_pipeline.py                          # quick self-check
```

## Results

Results for 5 CT scans shown on the website, v0.5, 14 Oct 2026.
Dice: 1.00 = the AI outline and the expert outline are the same; 0 = no overlap.

| Organ | Scans | Mean Dice | Lowest Dice | Mean volume difference |
|---|---|---|---|---|
| Liver | 5 | 0.98 | 0.97 | 1.6% |
| Spleen | 5 | 0.96 | 0.94 | 2.6% |
| Stomach | 5 | 0.95 | 0.93 | 4.0% |
| Right kidney | 5 | 0.95 | 0.93 | 5.6% |
| Urinary bladder | 5 | 0.94 | 0.92 | 6.9% |
| Left kidney | 5 | 0.93 | 0.86 | 8.0% |
| Inferior vena cava | 5 | 0.92 | 0.89 | 2.0% |
| Oesophagus | 5 | 0.92 | 0.91 | 2.4% |
| Aorta | 5 | 0.90 | 0.74 | 10.7% |
| Duodenum | 5 | 0.88 | 0.83 | 4.6% |
| Pancreas | 5 | 0.86 | 0.73 | 9.9% |
| Gallbladder | 5 | 0.83 | 0.77 | 13.8% |

The mean of the five scan-level mean Dice scores is 0.92. Liver had the highest mean Dice (0.98), while gallbladder had the lowest (0.83). The lowest individual organ Dice was 0.73 for pancreas. These results describe agreement with expert outlines, not clinical accuracy. The small public sample and possible overlap with model-training data limit interpretation. The website is intended for teaching anatomy only.

## How it works

1. **Data** – downloads the TotalSegmentator small subset (102 CT scans with expert-checked masks; Zenodo record 10047263).
2. **Case selection** – ranks scans by how many of the 12 organs are fully inside the image (`outputs/curation.csv`).
3. **AI** – runs the MONAI `vista3d` bundle with label prompts for the 12 organs, one scan per process.
4. **Scores** – Dice and volumes per organ; warnings for label mix-ups and left/right swaps.
5. **Export** – crops and resamples each scan (default 2 mm) so the site loads quickly; writes `cases.json`.
6. **Viewer** – a static web page using NiiVue; the comparison view is computed in the browser.

| Our value | Organ | VISTA-3D label | TotalSegmentator file |
|---:|---|---:|---|
| 1 | Liver | 1 | liver |
| 2 | Spleen | 3 | spleen |
| 3 | Pancreas | 4 | pancreas |
| 4 | Right kidney | 5 | kidney_right |
| 5 | Left kidney | 14 | kidney_left |
| 6 | Gallbladder | 10 | gallbladder |
| 7 | Stomach | 12 | stomach |
| 8 | Aorta | 6 | aorta |
| 9 | Inferior vena cava | 7 | inferior_vena_cava |
| 10 | Oesophagus | 11 | esophagus |
| 11 | Duodenum | 13 | duodenum |
| 12 | Urinary bladder | 15 | urinary_bladder |

**About the scores.** Dice measures overlap between the AI and expert masks (1.00 = identical). VISTA-3D was trained on
large public CT collections that may include scans like these, so the scores show *agreement*, not clinical accuracy.

## Credits and licences

- **CT scans and expert masks:** TotalSegmentator dataset – Wasserthal J. et al., *TotalSegmentator: Robust Segmentation
  of 104 Anatomic Structures in CT Images*, Radiology: Artificial Intelligence, 2023. Licence CC BY 4.0.
- **AI model:** VISTA-3D, MONAI Model Zoo bundle `vista3d` (MONAI Consortium / NVIDIA). Code Apache-2.0; model weights
  under the NVIDIA License, which allows non-commercial use only ("research or evaluation purposes"). Treat the AI masks
  produced here the same way, and check the licence before any commercial use.
- **Viewer:** [NiiVue](https://github.com/niivue/niivue), BSD-2-Clause (`docs/vendor/NIIVUE_LICENSE.txt`).
- **Website data:** five selected real cases from the TotalSegmentator small subset; the website uses real AI results rather than demo masks.

Built by Guna Rithvick and Ayushi N, DSU AI Factory interns.

## Versions

| Version | Date | What changed |
|---|---|---|
| v0.5 | 14 Oct 2026 | First public release: 5 scans, 12 organs, Expert / AI / Compare views, Dice and volume table, teaching notes, demo video |
| v1.0 | planned for 31 Oct 2026 | Faculty-reviewed version for teaching |
