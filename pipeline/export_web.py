"""Make small, web-ready copies of each case for the NiiVue viewer.

For every case it writes into <web_dir>/<case_id>/:
    ct.nii.gz          CT, cropped to the body, resampled (default 2 mm), int16
    reference.nii.gz   expert masks, values 1..12, same grid as ct.nii.gz
    ai.nii.gz          VISTA-3D masks, values 1..12, same grid (if available)
    ai_fullres.nii.gz  VISTA-3D masks on the ORIGINAL CT grid (for download)
    metrics.csv        per-organ Dice and volumes
and a manifest <web_dir>/cases.json that the viewer reads.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import shutil
from pathlib import Path

import nibabel as nib
import numpy as np
from nibabel.processing import resample_from_to, resample_to_output
from scipy import ndimage as ndi

from .organs import COMPARE, ORGANS, organ_table
from .evaluate import ai_labels, reference_labels

CT_WINDOW = (-160, 240)  # abdomen window used as the default display


def _bbox(mask: np.ndarray, min_count: int = 20, margin: int = 4) -> list[slice]:
    sl = []
    for ax in range(3):
        other = tuple(a for a in range(3) if a != ax)
        counts = mask.sum(axis=other)
        idx = np.flatnonzero(counts >= min_count)
        if idx.size == 0:
            idx = np.array([0, mask.shape[ax] - 1])
        sl.append(slice(max(int(idx[0]) - margin, 0), min(int(idx[-1]) + margin + 1, mask.shape[ax])))
    return sl


def _union(a: list[slice], b: list[slice]) -> list[slice]:
    return [slice(min(x.start, y.start), max(x.stop, y.stop)) for x, y in zip(a, b)]


def _interior_points(labels: np.ndarray, affine: np.ndarray) -> dict[str, list[float]]:
    """For each organ, the voxel farthest from its edge (distance transform), in world mm."""
    out = {}
    for o, sl in zip(ORGANS, ndi.find_objects(labels, max_label=len(ORGANS))):
        if sl is None:
            continue
        m = np.pad(labels[sl] == o.index, 1)
        d = ndi.distance_transform_edt(m)[1:-1, 1:-1, 1:-1]
        k = np.unravel_index(int(np.argmax(d)), d.shape)
        vox = [s.start + int(kk) for s, kk in zip(sl, k)]
        mm = affine @ np.array([*vox, 1.0])
        out[o.key] = [round(float(v), 1) for v in mm[:3]]
    return out


def _save_labels(data: np.ndarray, like: nib.Nifti1Image, path: Path) -> None:
    img = nib.Nifti1Image(data.astype(np.uint8), like.affine)
    img.header.set_intent("label")
    img.header.set_xyzt_units("mm")
    nib.save(img, str(path))


def export_case(case_id: str, case_dir: str | Path, web_dir: str | Path, work_dir: str | Path,
                spacing_mm: float = 2.0) -> dict:
    case_dir, web_dir, work_dir = Path(case_dir), Path(web_dir), Path(work_dir)
    out = web_dir / case_id
    out.mkdir(parents=True, exist_ok=True)

    ref, ct = reference_labels(case_dir)
    ai_path = work_dir / "ai_raw" / f"{case_id}.nii.gz"
    ai = ai_labels(ai_path, ct)[0] if ai_path.exists() else None

    # 1) reorient to RAS so all cases open the same way
    ct_c = nib.as_closest_canonical(ct)
    ref_c = nib.as_closest_canonical(nib.Nifti1Image(ref, ct.affine))
    ai_c = nib.as_closest_canonical(nib.Nifti1Image(ai, ct.affine)) if ai is not None else None

    # 2) crop to the body (plus every labelled voxel, so no organ is ever cut)
    arr = np.asarray(ct_c.dataobj, dtype=np.float32)
    box = _bbox(arr > -500)
    lab_any = np.asarray(ref_c.dataobj) > 0
    if ai_c is not None:
        lab_any |= np.asarray(ai_c.dataobj) > 0
    if lab_any.any():
        box = _union(box, _bbox(lab_any, min_count=1, margin=4))
    del arr
    ct_crop = ct_c.slicer[box[0], box[1], box[2]]

    # 3) resample to a lighter grid (never finer than the original)
    zooms = [float(z) for z in ct_crop.header.get_zooms()[:3]]
    target = [max(spacing_mm, z) for z in zooms]
    ct_web = resample_to_output(ct_crop, voxel_sizes=target, order=1, mode="constant", cval=-1024)
    ct_data = np.clip(np.rint(np.asarray(ct_web.dataobj)), -1024, 3071).astype(np.int16)
    ct_img = nib.Nifti1Image(ct_data, ct_web.affine)
    ct_img.header["cal_min"], ct_img.header["cal_max"] = CT_WINDOW
    ct_img.header.set_xyzt_units("mm")
    nib.save(ct_img, str(out / "ct.nii.gz"))

    def to_web(lab_img):
        crop = lab_img.slicer[box[0], box[1], box[2]]
        return np.asarray(resample_from_to(crop, ct_img, order=0, mode="constant", cval=0).dataobj)

    ref_web = to_web(ref_c)
    _save_labels(ref_web, ct_img, out / "reference.nii.gz")
    files = {"ct": f"{case_id}/ct.nii.gz", "reference": f"{case_id}/reference.nii.gz"}
    ai_web = None
    if ai_c is not None:
        ai_web = to_web(ai_c)
        _save_labels(ai_web, ct_img, out / "ai.nii.gz")
        _save_labels(ai, ct, out / "ai_fullres.nii.gz")
        files["ai"] = f"{case_id}/ai.nii.gz"
        files["ai_fullres"] = f"{case_id}/ai_fullres.nii.gz"

    # one point deep inside each organ (world mm), so the viewer can jump there when a name is clicked.
    # (A plain centre of mass can fall outside curved organs such as the pancreas.)
    focus = {}
    for src in (ref_web, ai_web):
        if src is not None:
            for key, mm in _interior_points(src, ct_img.affine).items():
                focus.setdefault(key, mm)

    metrics_file = work_dir / "metrics" / f"{case_id}.json"
    metrics = json.loads(metrics_file.read_text()) if metrics_file.exists() else None
    if metrics:
        with open(out / "metrics.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["organ", "dice", "expert_ml", "ai_ml", "difference_pct"])
            for m in metrics["organs"].values():
                w.writerow([m["name"], m["dice"], m["vol_ref_ml"], m["vol_ai_ml"], m["vol_diff_pct"]])
        files["metrics_csv"] = f"{case_id}/metrics.csv"

    sizes = {k: round((web_dir / v).stat().st_size / 1e6, 2) for k, v in files.items()}
    return {
        "id": case_id,
        "files": files,
        "size_mb": sizes,
        "web_spacing_mm": [round(t, 2) for t in target],
        "focus_mm": focus,
        "metrics": metrics,
    }


def export_cases(case_ids: list[str], cases: dict[str, Path], web_dir: str | Path, work_dir: str | Path,
                 meta: dict[str, dict] | None = None, spacing_mm: float = 2.0, title_prefix: str = "Case",
                 extra: dict | None = None) -> Path:
    """Export several cases and write cases.json (the viewer's manifest)."""
    from .dataset import describe

    web_dir, work_dir = Path(web_dir), Path(work_dir)
    web_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for n, cid in enumerate(case_ids, 1):
        e = export_case(cid, cases[cid], web_dir, work_dir, spacing_mm)
        m = (meta or {}).get(cid, {})
        e["title"] = f"{title_prefix} {n}"
        e["description"] = describe(m)
        e["pathology"] = m.get("pathology", "")
        entries.append(e)
        big = [k for k, v in e["size_mb"].items() if v > 25]
        print(f"  {cid}: " + ", ".join(f"{k} {v} MB" for k, v in e["size_mb"].items())
              + ("   <-- larger than 25 MB, consider --web-spacing 2.5" if big else ""))

    manifest = {
        "app": "CT Anatomy Explorer",
        "version": "0.5",
        "generated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "model": "VISTA-3D (MONAI bundle 'vista3d', label prompts for 12 organs)",
        "dataset": "TotalSegmentator small subset v2.0.1 (Wasserthal et al., Radiology: AI 2023), CC BY 4.0",
        "ct_window": list(CT_WINDOW),
        "organs": organ_table(),
        "compare": {str(k): {"name": v[0], "color": list(v[1])} for k, v in COMPARE.items()},
        "cases": entries,
    }
    if extra:
        manifest.update(extra)
    (web_dir / "cases.json").write_text(json.dumps(manifest, indent=1))
    print(f"Manifest written: {web_dir/'cases.json'} ({len(entries)} cases)")
    return web_dir / "cases.json"


def zip_web_data(web_dir: str | Path, zip_base: str | Path) -> Path:
    """Zip the web data folder so it can be downloaded in one click."""
    return Path(shutil.make_archive(str(zip_base), "zip", root_dir=str(Path(web_dir).parent),
                                    base_dir=Path(web_dir).name))
