"""Rebuild notebooks/ct_anatomy_explorer_kaggle.ipynb from the files in pipeline/.

The notebook carries its own copy of the pipeline code (as %%writefile cells), so it
runs on Kaggle or Colab without cloning this repository. If you change anything in
pipeline/, run:   python tools/build_notebook.py
"""
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
MODULES = ["__init__.py", "organs.py", "dataset.py", "run_vista3d.py", "evaluate.py", "export_web.py", "run_all.py"]

md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell

cells = [
    md("""# CT Anatomy Explorer – AI pipeline (Kaggle / Colab)

This notebook runs the **VISTA-3D** model (MONAI) on public CT scans from the **TotalSegmentator** dataset,
compares the AI masks with the expert masks, and prepares small files for the web viewer.

**One-time settings (Kaggle, right-hand panel → Session options):**
1. **Accelerator:** GPU T4 x2 (or GPU P100).
2. **Internet:** On. (Kaggle asks you to verify your phone number first.)

**Day 1 (Thu):** keep `N_CASES = 1` and run the cells one by one (Shift + Enter). Check the picture in Step 6.

**Before leaving on Day 1:** set `N_CASES = 10`, then click **Save Version → Save & Run All (Commit) → Save**.
Kaggle runs everything in the background; you can close the tab.

**Monday:** open the notebook → **Output** (or the saved version) → download `outputs/web_data.zip` and give it to the viewer team.

*Educational project. Not for diagnosis or clinical decisions.*"""),
    code("""# ---- Settings: the only cell you normally change ----
N_CASES = 1          # Day 1 test: 1.   Background run before the break: 10
N_WEB = 10           # scans exported for the website (pick the best 5 on Monday with tools/select_cases.py)
WEB_SPACING_MM = 2.0 # web copies are resampled to this voxel size (bigger = smaller files)"""),
    md("## Step 0 · Install MONAI and check the GPU (about 1 minute)"),
    code("""!pip install -q --no-deps monai==1.6.1
!pip install -q nibabel pytorch-ignite einops fire
import torch, monai, nibabel
print('MONAI', monai.__version__, '| PyTorch', torch.__version__, '| GPU available:', torch.cuda.is_available())
if torch.cuda.is_available():
    print('GPU:', torch.cuda.get_device_name(0), f"({torch.cuda.get_device_properties(0).total_memory/1e9:.0f} GB)")
else:
    print('WARNING: no GPU. Turn on the GPU accelerator in the notebook settings, then restart the session.')"""),
    md("## Pipeline code\nThese cells only write the pipeline files to disk. You do not need to edit them "
       "(the same code lives in the `pipeline/` folder of the GitHub repo)."),
    code("!mkdir -p pipeline"),
]
for name in MODULES:
    src = (ROOT / "pipeline" / name).read_text()
    cells.append(code(f"%%writefile pipeline/{name}\n{src}"))

cells += [
    code("""import importlib, json, sys
from pathlib import Path
import pandas as pd
from IPython.display import Image, display
import pipeline, pipeline.organs, pipeline.dataset, pipeline.run_vista3d, pipeline.evaluate, pipeline.export_web, pipeline.run_all
for m in (pipeline.organs, pipeline.dataset, pipeline.run_vista3d, pipeline.evaluate, pipeline.export_web, pipeline.run_all):
    importlib.reload(m)   # picks up edits if you re-run the cells above
from pipeline import dataset, run_vista3d, evaluate, export_web
from pipeline.run_all import default_paths
P = default_paths()
for k, v in P.items():
    print(f'{k:10s} {v}')"""),
    md("## Step 1 · Download the dataset (3.2 GB, about 5–10 minutes)\n"
       "TotalSegmentator small subset v2.0.1 from Zenodo (CC BY 4.0). Only the CT scans and the 12 organ masks are unpacked."),
    code("dataset.prepare(P['data_dir'])\ncases = dataset.find_cases(P['data_dir'])\nprint(len(cases), 'scans available')"),
    md("## Step 2 · Choose the best scans\nKeeps scans where all 12 organs are fully inside the image. "
       "The full ranking is saved as `outputs/curation.csv`."),
    code("""selected = dataset.curate(P['data_dir'], P['work_dir'], n_cases=N_CASES)
cur = pd.read_csv(P['work_dir'] / 'curation.csv')
display(cur.head(15)[['selected', 'case_id', 'organs_ok', 'description', 'shape', 'spacing_mm', 'length_mm']])"""),
    md("## Step 3 · Download the VISTA-3D model (about 870 MB)"),
    code("run_vista3d.ensure_bundle(P['bundle_dir'])"),
    md("## Step 4 · Run VISTA-3D on the selected scans\n"
       "Roughly 1–5 minutes per scan on a T4. Each scan runs separately, so one failure does not stop the rest. "
       "Time and peak GPU memory are recorded in `outputs/inference_log.csv` (write these in your Day 1 report)."),
    code("""records = run_vista3d.run_cases(selected, cases, P['bundle_dir'], P['work_dir'])
display(pd.DataFrame(records)[['case_id', 'status', 'seconds', 'peak_gpu_mb']])"""),
    md("## Step 5 · Compare AI with the expert masks\n"
       "Dice: 1.00 = identical. Lines starting with **!** are automatic warnings, e.g. a label mix-up or a "
       "left/right swap - investigate those before sharing any results."),
    code("""results = evaluate.evaluate_cases(selected, cases, P['work_dir'])
if results:
    df = pd.read_csv(P['work_dir'] / 'metrics_all.csv')
    display(df.pivot(index='organ', columns='case_id', values='dice').round(3))"""),
    md("## Step 6 · Visual check (your Day 1 proof screenshot)\nLeft to right: CT, expert masks, AI masks. "
       "Patient's right is on the left of each picture (radiology convention)."),
    code("""for cid in selected:
    ai_path = P['work_dir'] / 'ai_raw' / f'{cid}.nii.gz'
    png = evaluate.qc_figure(cid, cases[cid], ai_path, P['work_dir'] / 'qc' / f'{cid}.png')
    display(Image(filename=str(png)))"""),
    md("## Step 7 · Export files for the web viewer\nCreates `outputs/web_data.zip`. Unzip it into the repo's `docs/` "
       "folder (it contains a `data/` folder that replaces the demo data)."),
    code("""done = [c for c in selected if (P['work_dir'] / 'ai_raw' / f'{c}.nii.gz').exists()]
export_web.export_cases(done[:N_WEB], cases, P['web_dir'], P['work_dir'], dataset.read_meta(P['data_dir']),
                        spacing_mm=WEB_SPACING_MM)
z = export_web.zip_web_data(P['web_dir'], P['work_dir'] / 'web_data')
print('Download this file:', z, f'({z.stat().st_size/1e6:.1f} MB)')"""),
    md("""## Done – what to hand over
* `outputs/web_data.zip` → viewer team (unzip into `docs/`, so you get `docs/data/cases.json`).
* `outputs/qc/*.png` → post one in the group chat as the day's proof.
* `outputs/inference_log.csv`, `outputs/metrics_all.csv` → keep for the report.

**Credits:** TotalSegmentator dataset (Wasserthal et al., Radiology: AI 2023, CC BY 4.0); VISTA-3D (MONAI / NVIDIA).
Agreement scores are not a clinical validation."""),
]

nb = nbf.v4.new_notebook(cells=cells, metadata={
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"},
})
out = ROOT / "notebooks" / "ct_anatomy_explorer_kaggle.ipynb"
nbf.validate(nb)
nbf.write(nb, out)
print("wrote", out)
