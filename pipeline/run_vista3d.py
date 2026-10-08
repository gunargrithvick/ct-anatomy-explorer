"""Run the MONAI VISTA-3D bundle on selected CT scans (12 organ prompts).

Each scan runs in its own `python -m monai.bundle run` process, so one failure
(or an out-of-memory error) does not stop the whole batch, and a re-run skips
scans that are already done. Results go to <work_dir>/ai_raw/<case_id>.nii.gz
with VISTA-3D label ids as voxel values (e.g. liver = 1, spleen = 3).
"""
from __future__ import annotations

import csv
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from .organs import VISTA_PROMPTS

BUNDLE_REPO = "MONAI/vista3d"          # Hugging Face repo of the MONAI bundle (includes weights)
BUNDLE_REVISION = "0.5.11"             # tested version; falls back to the latest if missing
WEIGHTS_URL = "https://developer.download.nvidia.com/assets/Clara/monai/tutorials/model_zoo/model_vista3d.pt"


def ensure_bundle(bundle_dir: str | Path) -> Path:
    """Download the VISTA-3D bundle (configs, scripts and ~870 MB weights) once."""
    bundle_dir = Path(bundle_dir)
    cfg = bundle_dir / "configs" / "inference.json"
    weights = bundle_dir / "models" / "model.pt"
    if cfg.exists() and weights.exists() and weights.stat().st_size > 500e6:
        print(f"VISTA-3D bundle ready in {bundle_dir}")
        return bundle_dir
    bundle_dir.mkdir(parents=True, exist_ok=True)
    try:
        from huggingface_hub import snapshot_download
        print(f"Downloading VISTA-3D bundle from Hugging Face ({BUNDLE_REPO}) ...")
        try:
            snapshot_download(repo_id=BUNDLE_REPO, revision=BUNDLE_REVISION, local_dir=str(bundle_dir))
        except Exception:
            print(f"  version {BUNDLE_REVISION} not found, using the latest version")
            snapshot_download(repo_id=BUNDLE_REPO, local_dir=str(bundle_dir))
    except Exception as e:  # noqa: BLE001
        print(f"Hugging Face download failed: {e}")
    if cfg.exists() and not (weights.exists() and weights.stat().st_size > 500e6):
        print("Weights missing; downloading model.pt from NVIDIA ...")
        import requests
        weights.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(WEIGHTS_URL, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(weights, "wb") as f:
                for block in r.iter_content(1 << 20):
                    f.write(block)
    if not (cfg.exists() and weights.exists()):
        raise RuntimeError("Could not get the VISTA-3D bundle. Check that Internet is ON in the notebook settings.")
    print(f"VISTA-3D bundle ready in {bundle_dir}")
    return bundle_dir


def _gpu_used_mb() -> int | None:
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10)
        return int(out.stdout.strip().splitlines()[0])
    except Exception:  # noqa: BLE001
        return None


def run_case(case_id: str, ct_path: str | Path, bundle_dir: str | Path, work_dir: str | Path,
             prompts: list[int] | None = None, timeout_s: int = 3600,
             resample_spacing: list[float] | None = None) -> dict:
    """Segment one scan. Returns a record with status, time and peak GPU memory."""
    bundle_dir, work_dir = Path(bundle_dir).resolve(), Path(work_dir).resolve()
    out_path = work_dir / "ai_raw" / f"{case_id}.nii.gz"
    if out_path.exists():
        return {"case_id": case_id, "status": "done_before", "seconds": "", "peak_gpu_mb": "", "output": str(out_path)}
    prompts = prompts or VISTA_PROMPTS

    # The bundle names outputs after the input file, and every TotalSegmentator scan is
    # called ct.nii.gz - so link each scan under a unique name first.
    inputs = work_dir / "_inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    link = inputs / f"{case_id}.nii.gz"
    if not link.exists():
        try:
            link.symlink_to(Path(ct_path).resolve())
        except OSError:
            shutil.copy(ct_path, link)
    raw_dir = work_dir / "_bundle_out"
    logs = work_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    log_path = logs / f"{case_id}.log"

    cmd = [sys.executable, "-m", "monai.bundle", "run",
           "--config_file", str(bundle_dir / "configs" / "inference.json"),
           "--meta_file", str(bundle_dir / "configs" / "metadata.json"),
           "--logging_file", str(bundle_dir / "configs" / "logging.conf"),
           "--bundle_root", str(bundle_dir),
           "--output_dir", str(raw_dir),
           "--output_dtype", "$np.uint8",
           "--input_dict", repr({"image": str(link), "label_prompt": [int(p) for p in prompts]})]
    if resample_spacing:  # only for quick tests; VISTA-3D is meant to run at 1.5 mm
        cmd += ["--resample_spacing", repr([float(s) for s in resample_spacing])]
    env = dict(os.environ, PYTHONPATH=str(bundle_dir) + os.pathsep + os.environ.get("PYTHONPATH", ""))

    base = _gpu_used_mb()
    peak = {"mb": base}
    stop = threading.Event()

    def sample():
        while not stop.is_set():
            v = _gpu_used_mb()
            if v is not None and (peak["mb"] is None or v > peak["mb"]):
                peak["mb"] = v
            stop.wait(2)

    t0 = time.time()
    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    with open(log_path, "w") as log:
        try:
            proc = subprocess.run(cmd, cwd=str(bundle_dir), env=env, stdout=log, stderr=subprocess.STDOUT,
                                  timeout=timeout_s)
            status = "ok" if proc.returncode == 0 else f"failed (exit {proc.returncode})"
        except subprocess.TimeoutExpired:
            status = "timeout"
    stop.set()
    sampler.join(timeout=5)
    seconds = round(time.time() - t0, 1)

    produced = sorted(raw_dir.glob(f"{case_id}/*_trans.nii.gz")) or sorted(raw_dir.glob(f"**/{case_id}*_trans.nii.gz"))
    if status == "ok" and produced:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(produced[0]), out_path)
        shutil.rmtree(produced[0].parent, ignore_errors=True)
    elif status == "ok":
        status = "failed (no output file)"
    peak_mb = (peak["mb"] - base) if (peak["mb"] is not None and base is not None) else ""
    rec = {"case_id": case_id, "status": status, "seconds": seconds, "peak_gpu_mb": peak_mb,
           "output": str(out_path) if out_path.exists() else "", "log": str(log_path)}
    if not status.startswith("ok"):
        tail = log_path.read_text(errors="replace").strip().splitlines()[-15:]
        rec["error"] = " | ".join(tail)[-1500:]
    return rec


def run_cases(case_ids: list[str], cases: dict[str, Path], bundle_dir: str | Path, work_dir: str | Path,
              **kw) -> list[dict]:
    """Segment several scans one after another and write inference_log.csv."""
    work_dir = Path(work_dir)
    records = []
    for i, cid in enumerate(case_ids, 1):
        print(f"[{i}/{len(case_ids)}] VISTA-3D on {cid} ...", flush=True)
        rec = run_case(cid, cases[cid] / "ct.nii.gz", bundle_dir, work_dir, **kw)
        records.append(rec)
        extra = f"  {rec['seconds']} s" if rec["seconds"] != "" else ""
        extra += f", peak GPU {rec['peak_gpu_mb']} MB" if rec.get("peak_gpu_mb") not in ("", None) else ""
        print(f"    -> {rec['status']}{extra}", flush=True)
        if rec.get("error"):
            print("    last log lines:", rec["error"][-600:])
    keys = ["case_id", "status", "seconds", "peak_gpu_mb", "output", "log", "error"]
    log_csv = work_dir / "inference_log.csv"
    old = {}
    if log_csv.exists():
        with open(log_csv) as f:
            old = {r["case_id"]: r for r in csv.DictReader(f)}
    for r in records:
        if r["status"] != "done_before" or r["case_id"] not in old:
            old[r["case_id"]] = r
    with open(log_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(old.values())
    ok = sum(1 for r in records if r["status"] in ("ok", "done_before"))
    print(f"VISTA-3D finished: {ok}/{len(records)} scans segmented. Log: {log_csv}")
    return records
