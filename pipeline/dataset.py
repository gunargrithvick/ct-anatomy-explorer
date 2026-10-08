"""Download the TotalSegmentator small subset and choose good demo cases.

Dataset: "Small subset of TotalSegmentator Dataset" v2.0.1 (102 CT scans,
expert-checked masks for 117 structures), Zenodo record 10047263, CC BY 4.0.
Please credit: Wasserthal J. et al., TotalSegmentator, Radiology: AI 2023.

Expected layout after extraction (searched recursively, so an extra top folder is fine):
    <data_dir>/.../s0011/ct.nii.gz
    <data_dir>/.../s0011/segmentations/liver.nii.gz  (one file per structure)
    <data_dir>/.../meta.csv                           (optional, ';' or ',' separated)
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import nibabel as nib
import numpy as np

from .organs import ORGANS

ZIP_NAME = "Totalsegmentator_dataset_small_v201.zip"
ZIP_URL = f"https://zenodo.org/records/10047263/files/{ZIP_NAME}?download=1"
ZIP_MD5 = "6b5524af4b15e6ba06ef2d700c0c73e0"

ORGAN_FILES = {f"segmentations/{o.key}.nii.gz" for o in ORGANS}


# --------------------------------------------------------------------------- download
def _download(url: str, dest: Path, chunk: int = 1 << 20) -> None:
    """Stream a large file with resume support and a simple progress print."""
    import requests  # available on Kaggle/Colab

    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    have = part.stat().st_size if part.exists() else 0
    headers = {"Range": f"bytes={have}-"} if have else {}
    with requests.get(url, stream=True, headers=headers, timeout=60) as r:
        if r.status_code == 200 and have:
            have = 0  # server ignored the range request: start again
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0)) + have
        mode = "ab" if have else "wb"
        t0, last = time.time(), -1
        with open(part, mode) as f:
            for block in r.iter_content(chunk_size=chunk):
                f.write(block)
                have += len(block)
                if total:
                    pct = int(100 * have / total)
                    if pct // 5 != last // 5:
                        last = pct
                        speed = have / max(time.time() - t0, 1e-6) / 1e6
                        print(f"  downloaded {have/1e9:5.2f} / {total/1e9:.2f} GB ({pct}%)  ~{speed:.0f} MB/s", flush=True)
    part.rename(dest)


def _md5(path: Path, chunk: int = 1 << 24) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def prepare(data_dir: str | Path, zip_path: str | Path | None = None, verify_md5: bool = True) -> Path:
    """Make sure the dataset is extracted under data_dir. Returns data_dir.

    Only ct.nii.gz, the 12 organ masks and meta.csv are extracted (much faster
    than unpacking all 117 masks per scan).
    """
    data_dir = Path(data_dir)
    marker = data_dir / ".extracted"
    if marker.exists():
        print(f"Dataset already extracted in {data_dir}")
        return data_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    zp = Path(zip_path) if zip_path else data_dir / ZIP_NAME
    if not zp.exists():
        print(f"Downloading {ZIP_NAME} (3.2 GB) from Zenodo ...")
        _download(ZIP_URL, zp)
    if verify_md5:
        print("Checking file integrity (MD5) ...")
        got = _md5(zp)
        if got != ZIP_MD5:
            raise RuntimeError(f"MD5 mismatch for {zp} (got {got}). Delete the file and download again.")

    print("Extracting CT scans, the 12 organ masks and meta.csv ...")
    n = 0
    with zipfile.ZipFile(zp) as z:
        for m in z.infolist():
            name = m.filename.replace("\\", "/")
            if name.endswith("/ct.nii.gz") or name.endswith("meta.csv") or any(name.endswith(s) for s in ORGAN_FILES):
                z.extract(m, data_dir)
                n += 1
    marker.write_text(json.dumps({"files": n, "zip": str(zp)}))
    print(f"Extracted {n} files into {data_dir}")
    return data_dir


# --------------------------------------------------------------------------- discovery
def find_cases(data_dir: str | Path) -> dict[str, Path]:
    """Map case id (folder name, e.g. 's0011') -> case folder."""
    cases = {}
    for ct in sorted(Path(data_dir).rglob("ct.nii.gz")):
        if (ct.parent / "segmentations").is_dir():
            cases[ct.parent.name] = ct.parent
    return cases


def read_meta(data_dir: str | Path) -> dict[str, dict]:
    """Read meta.csv (age, gender, study type ...) if present."""
    files = sorted(Path(data_dir).rglob("meta.csv"))
    if not files:
        return {}
    text = files[0].read_text(encoding="utf-8", errors="replace")
    delim = ";" if text.count(";") > text.count(",") else ","
    rows = csv.DictReader(text.splitlines(), delimiter=delim)
    out = {}
    for r in rows:
        r = {(k or "").strip(): (v or "").strip() for k, v in r.items()}
        if r.get("image_id"):
            out[r["image_id"]] = r
    return out


def describe(meta: dict | None) -> str:
    """Short human description, e.g. 'Female, 63 y · ct abdomen'."""
    if not meta:
        return ""
    sex = {"m": "Male", "f": "Female"}.get(meta.get("gender", "").lower(), "")
    age = meta.get("age", "")
    age = f"{int(float(age))} y" if age.replace(".", "", 1).isdigit() else ""
    study = meta.get("study_type", "")
    first = ", ".join(x for x in (sex, age) if x)
    return " · ".join(x for x in (first, study) if x)


# --------------------------------------------------------------------------- curation
def _si_axis(affine) -> int:
    codes = nib.aff2axcodes(affine)
    return next(i for i, c in enumerate(codes) if c in ("S", "I"))


def assess_case(case_id: str, case_dir: str, min_ml: float = 1.0) -> dict:
    """Check which of the 12 organs are fully visible in one scan."""
    case_dir = Path(case_dir)
    ct = nib.load(str(case_dir / "ct.nii.gz"))
    zooms = [float(z) for z in ct.header.get_zooms()[:3]]
    si = _si_axis(ct.affine)
    row = {
        "case_id": case_id,
        "shape": "x".join(str(s) for s in ct.shape[:3]),
        "spacing_mm": "x".join(f"{z:.2f}" for z in zooms),
        "slice_mm": round(zooms[si], 2),
        "length_mm": round(ct.shape[si] * zooms[si]),
        "voxels_M": round(math.prod(ct.shape[:3]) / 1e6, 1),
    }
    voxel_ml = math.prod(zooms) / 1000.0
    n_ok = 0
    for o in ORGANS:
        p = case_dir / "segmentations" / f"{o.key}.nii.gz"
        if not p.exists():
            status = "no_file"
        else:
            m = np.asarray(nib.load(str(p)).dataobj) > 0
            n = int(m.sum())
            if n == 0:
                status = "absent"
            elif n * voxel_ml < min_ml:
                status = "tiny"
            else:
                other = tuple(a for a in range(3) if a != si)
                idx = np.flatnonzero(m.any(axis=other))
                cut = idx[0] == 0 or idx[-1] == m.shape[si] - 1
                status = "cut_off" if (cut and not o.tubular) else "ok"
        row[o.key] = status
        n_ok += status == "ok"
    row["organs_ok"] = n_ok
    return row


def curate(data_dir: str | Path, work_dir: str | Path, n_cases: int = 10, min_length_mm: int = 300,
           max_voxels_M: float = 150.0, workers: int | None = None) -> list[str]:
    """Rank all scans and pick the best n_cases. Writes curation.csv and selected_cases.json."""
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    cases = find_cases(data_dir)
    meta = read_meta(data_dir)
    if not cases:
        raise RuntimeError(f"No cases found under {data_dir}. Did the download/extraction finish?")

    # quick pre-filter on the CT header only (short scans cannot contain all 12 organs)
    candidates, skipped = [], []
    for cid, cdir in cases.items():
        ct = nib.load(str(cdir / "ct.nii.gz"))
        zooms = ct.header.get_zooms()[:3]
        si = _si_axis(ct.affine)
        length = ct.shape[si] * float(zooms[si])
        vox = math.prod(ct.shape[:3]) / 1e6
        if length < min_length_mm or vox > max_voxels_M:
            skipped.append(cid)
        else:
            candidates.append(cid)
    print(f"{len(cases)} scans found; checking organ masks in {len(candidates)} long-enough scans ...")

    workers = workers or max(1, min(4, os.cpu_count() or 1))
    with ProcessPoolExecutor(max_workers=workers) as ex:
        rows = list(ex.map(assess_case, candidates, [str(cases[c]) for c in candidates]))

    for r in rows:
        m = meta.get(r["case_id"], {})
        r["description"] = describe(m)
        r["pathology"] = m.get("pathology", "")
    rows.sort(key=lambda r: (-r["organs_ok"], r["slice_mm"], r["voxels_M"], r["case_id"]))
    perfect = [r for r in rows if r["organs_ok"] == len(ORGANS)]
    chosen = (perfect + [r for r in rows if r not in perfect])[:n_cases]
    chosen_ids = [r["case_id"] for r in chosen]
    if len(perfect) < n_cases:
        print(f"Note: only {len(perfect)} scans show all {len(ORGANS)} organs fully; filling with the next best.")

    keys = ["selected", "case_id", "organs_ok", "description", "pathology", "shape", "spacing_mm",
            "slice_mm", "length_mm", "voxels_M"] + [o.key for o in ORGANS]
    with open(work_dir / "curation.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({**r, "selected": r["case_id"] in chosen_ids})
    (work_dir / "selected_cases.json").write_text(json.dumps(chosen_ids, indent=1))
    print(f"Selected {len(chosen_ids)} cases: {', '.join(chosen_ids)}  (details: {work_dir/'curation.csv'})")
    return chosen_ids
