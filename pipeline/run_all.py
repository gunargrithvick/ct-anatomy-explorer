"""One command for the whole pipeline (handy on a rented GPU or a lab PC).

    python -m pipeline.run_all --n-cases 10 --n-web 5

Steps (each one skips work that is already done, so you can re-run safely):
    download  -> curate -> infer -> evaluate -> export
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import dataset, evaluate, export_web, run_vista3d


def default_paths() -> dict:
    """Kaggle-friendly defaults: big downloads in /tmp, results in /kaggle/working."""
    kaggle = Path("/kaggle/working").exists()
    work = Path("/kaggle/working/outputs") if kaggle else Path("outputs")
    return {
        "data_dir": Path("/tmp/totalseg") if kaggle else Path("data/totalseg"),
        "bundle_dir": Path("/tmp/bundles/vista3d") if kaggle else Path("data/bundles/vista3d"),
        "work_dir": work,
        "web_dir": work / "web_data" / "data",
    }


def main(argv=None) -> None:
    d = default_paths()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", type=Path, default=d["data_dir"])
    p.add_argument("--bundle-dir", type=Path, default=d["bundle_dir"])
    p.add_argument("--work-dir", type=Path, default=d["work_dir"])
    p.add_argument("--web-dir", type=Path, default=None, help="default: <work-dir>/web_data/data")
    p.add_argument("--zip-path", type=Path, default=None, help="use an already downloaded dataset zip")
    p.add_argument("--n-cases", type=int, default=10, help="scans to segment (demo + spares)")
    p.add_argument("--n-web", type=int, default=5, help="scans to export to the viewer")
    p.add_argument("--cases", default=None, help="comma-separated case ids (skips automatic selection)")
    p.add_argument("--steps", default="download,curate,infer,evaluate,export")
    p.add_argument("--web-spacing", type=float, default=2.0, help="mm; larger = smaller files")
    p.add_argument("--allow-cpu", action="store_true", help="run VISTA-3D without a GPU (very slow)")
    a = p.parse_args(argv)
    steps = set(a.steps.split(","))
    web_dir = a.web_dir or a.work_dir / "web_data" / "data"
    a.work_dir.mkdir(parents=True, exist_ok=True)

    if "download" in steps:
        dataset.prepare(a.data_dir, a.zip_path)
    cases = dataset.find_cases(a.data_dir)
    sel_file = a.work_dir / "selected_cases.json"
    if a.cases:
        selected = [c.strip() for c in a.cases.split(",") if c.strip()]
    elif "curate" in steps or not sel_file.exists():
        selected = dataset.curate(a.data_dir, a.work_dir, a.n_cases)
    else:
        selected = json.loads(sel_file.read_text())

    if "infer" in steps:
        import torch
        if not torch.cuda.is_available() and not a.allow_cpu:
            raise SystemExit("No GPU found. Turn on a GPU accelerator (or pass --allow-cpu to wait for hours).")
        run_vista3d.ensure_bundle(a.bundle_dir)
        run_vista3d.run_cases(selected, cases, a.bundle_dir, a.work_dir)
    if "evaluate" in steps:
        evaluate.evaluate_cases(selected, cases, a.work_dir)
        for cid in selected:
            evaluate.qc_figure(cid, cases[cid], a.work_dir / "ai_raw" / f"{cid}.nii.gz", a.work_dir / "qc" / f"{cid}.png")
    if "export" in steps:
        done = [c for c in selected if (a.work_dir / "ai_raw" / f"{c}.nii.gz").exists()]
        export_web.export_cases(done[: a.n_web], cases, web_dir, a.work_dir, dataset.read_meta(a.data_dir),
                                a.web_spacing)
        z = export_web.zip_web_data(web_dir, a.work_dir / "web_data")
        print(f"Ready to download: {z}")


if __name__ == "__main__":
    main()
