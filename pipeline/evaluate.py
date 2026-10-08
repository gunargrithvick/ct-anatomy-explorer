"""Compare VISTA-3D masks with the expert reference masks.

For every organ: Dice overlap, volumes (mL) and voxel counts of agreement,
AI-only (extra) and missed. Also runs two automatic sanity checks that catch the
most common silent bugs: a label-number mix-up and a left/right kidney swap.
Scores are *agreement with reference labels*, not proof of clinical accuracy
(VISTA-3D was trained on large public CT collections that may overlap with this data).
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import nibabel as nib
import numpy as np
from nibabel.processing import resample_from_to

from .organs import BY_KEY, BY_INDEX, N_ORGANS, ORGANS, VISTA_TO_INDEX


def reference_labels(case_dir: str | Path) -> tuple[np.ndarray, nib.Nifti1Image]:
    """Combine the 12 expert masks into one label map (values 1..12) on the CT grid."""
    case_dir = Path(case_dir)
    ct = nib.load(str(case_dir / "ct.nii.gz"))
    lab = np.zeros(ct.shape[:3], np.uint8)
    for o in ORGANS:
        p = case_dir / "segmentations" / f"{o.key}.nii.gz"
        if p.exists():
            lab[np.asarray(nib.load(str(p)).dataobj) > 0] = o.index
    return lab, ct


def ai_labels(ai_path: str | Path, ct: nib.Nifti1Image) -> tuple[np.ndarray, list[str]]:
    """Load a VISTA-3D output and convert its label ids to our 1..12 values on the CT grid."""
    notes = []
    img = nib.load(str(ai_path))
    data = np.asarray(img.dataobj)
    if data.ndim == 4:
        data = data[..., 0]
    if data.shape != ct.shape[:3] or not np.allclose(img.affine, ct.affine, atol=1e-2):
        notes.append("AI mask grid differed from the CT grid and was resampled (nearest neighbour)")
        img = resample_from_to(nib.Nifti1Image(data.astype(np.float32), img.affine), (ct.shape[:3], ct.affine), order=0)
        data = np.asarray(img.dataobj)
    data = np.clip(np.rint(data), 0, 255).astype(np.uint8)
    lut = np.zeros(256, np.uint8)
    for vid, idx in VISTA_TO_INDEX.items():
        lut[vid] = idx
    unexpected = sorted(set(np.unique(data).tolist()) - set(VISTA_TO_INDEX) - {0, 255})
    if unexpected:
        notes.append(f"unexpected label values in AI output: {unexpected[:10]}")
    return lut[data], notes


def confusion(ref: np.ndarray, ai: np.ndarray) -> np.ndarray:
    """(13 x 13) voxel counts: rows = reference label, columns = AI label (0 = background)."""
    k = N_ORGANS + 1
    combo = ref.astype(np.int64).ravel() * k + ai.astype(np.int64).ravel()
    return np.bincount(combo, minlength=k * k).reshape(k, k)


def organ_metrics(cm: np.ndarray, voxel_ml: float) -> dict:
    out = {}
    for o in ORGANS:
        i = o.index
        tp = int(cm[i, i])
        n_ref, n_ai = int(cm[i, :].sum()), int(cm[:, i].sum())
        dice = (2 * tp / (n_ref + n_ai)) if (n_ref + n_ai) else None
        v_ref, v_ai = n_ref * voxel_ml, n_ai * voxel_ml
        out[o.key] = {
            "name": o.name,
            "dice": None if dice is None else round(dice, 4),
            "vol_ref_ml": round(v_ref, 1),
            "vol_ai_ml": round(v_ai, 1),
            "vol_diff_pct": round(100 * (v_ai - v_ref) / v_ref, 1) if v_ref > 0 else None,
            "agree_vox": tp, "ai_only_vox": n_ai - tp, "missed_vox": n_ref - tp,
        }
    return out


def sanity_flags(cm: np.ndarray, metrics: dict) -> list[str]:
    """Warnings that usually mean a bug rather than a weak model."""
    flags = []
    for o in ORGANS:
        m = metrics[o.key]
        if m["vol_ref_ml"] > 0 and m["vol_ai_ml"] > 0 and (m["dice"] or 0) < 0.3:
            col = cm[1:, o.index]
            j = int(np.argmax(col)) + 1
            if j != o.index and col[j - 1] > 0:
                flags.append(f"LABEL MIX-UP? AI '{o.name}' mostly overlaps expert '{BY_INDEX[j].name}'")
            else:
                flags.append(f"Low agreement for {o.name} (Dice {m['dice']}) - check alignment")
        if m["vol_ref_ml"] > 0 and m["vol_ai_ml"] == 0:
            flags.append(f"AI found no {o.name} although the expert marked it")
    r, l = BY_KEY["kidney_right"].index, BY_KEY["kidney_left"].index
    same, cross = cm[r, r] + cm[l, l], cm[r, l] + cm[l, r]
    if cross > same and cross > 0:
        flags.append("LEFT/RIGHT SWAP? Kidneys overlap the opposite side - check orientation")
    return flags


def evaluate_case(case_id: str, case_dir: str | Path, ai_path: str | Path, work_dir: str | Path) -> dict:
    ref, ct = reference_labels(case_dir)
    ai, notes = ai_labels(ai_path, ct)
    zooms = [float(z) for z in ct.header.get_zooms()[:3]]
    voxel_ml = math.prod(zooms) / 1000.0
    cm = confusion(ref, ai)
    metrics = organ_metrics(cm, voxel_ml)
    flags = sanity_flags(cm, metrics)
    dices = [m["dice"] for m in metrics.values() if m["dice"] is not None and m["vol_ref_ml"] > 0]
    result = {
        "case_id": case_id,
        "mean_dice": round(float(np.mean(dices)), 4) if dices else None,
        "organs": metrics,
        "flags": flags,
        "notes": notes,
        "voxel_ml": voxel_ml,
        "spacing_mm": zooms,
        "shape": list(ct.shape[:3]),
    }
    out = Path(work_dir) / "metrics"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{case_id}.json").write_text(json.dumps(result, indent=1))
    return result


def evaluate_cases(case_ids: list[str], cases: dict[str, Path], work_dir: str | Path) -> list[dict]:
    work_dir = Path(work_dir)
    results, rows = [], []
    for cid in case_ids:
        ai_path = work_dir / "ai_raw" / f"{cid}.nii.gz"
        if not ai_path.exists():
            print(f"  {cid}: no AI output yet - skipped")
            continue
        r = evaluate_case(cid, cases[cid], ai_path, work_dir)
        results.append(r)
        print(f"  {cid}: mean Dice {r['mean_dice']}" + ("".join(f"\n     ! {f}" for f in r["flags"])))
        for key, m in r["organs"].items():
            rows.append({"case_id": cid, "organ": m["name"], "dice": m["dice"], "expert_ml": m["vol_ref_ml"],
                         "ai_ml": m["vol_ai_ml"], "diff_pct": m["vol_diff_pct"], "agree_vox": m["agree_vox"],
                         "ai_only_vox": m["ai_only_vox"], "missed_vox": m["missed_vox"]})
    if rows:
        with open(work_dir / "metrics_all.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"Metrics for {len(results)} scans written to {work_dir/'metrics_all.csv'}")
    return results


def qc_figure(case_id: str, case_dir: str | Path, ai_path: str | Path | None, out_png: str | Path) -> Path:
    """Side-by-side picture (CT | expert | AI) for a quick visual check. Radiological view:
    patient's right on the image's left, anterior at the top."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap

    ref, ct = reference_labels(case_dir)
    ai = ai_labels(ai_path, ct)[0] if ai_path and Path(ai_path).exists() else None
    ct_c = nib.as_closest_canonical(ct)
    to_can = lambda a: np.asarray(nib.as_closest_canonical(nib.Nifti1Image(a, ct.affine)).dataobj)  # noqa: E731
    img = np.asarray(ct_c.dataobj, dtype=np.float32)
    ref_c = to_can(ref)
    ai_c = to_can(ai) if ai is not None else None
    liver = ref_c == BY_KEY["liver"].index
    z = int(np.argmax(liver.sum(axis=(0, 1)))) if liver.any() else img.shape[2] // 2
    y = int(np.argmax((ref_c > 0).sum(axis=(0, 2)))) if ref_c.any() else img.shape[1] // 2

    colors = np.zeros((N_ORGANS + 1, 4))
    for o in ORGANS:
        colors[o.index] = [*(np.array(o.color) / 255), 0.55]
    cmap = ListedColormap(colors)
    ax_sl = lambda a: a[:, :, z].T[:, ::-1]  # noqa: E731  (rows: P->A with origin lower, cols flipped: R on left)
    co_sl = lambda a: a[:, y, :].T[:, ::-1]  # noqa: E731
    panels = [("CT", None), ("Expert (reference)", ref_c), ("AI (VISTA-3D)", ai_c)]
    fig, axes = plt.subplots(2, 3, figsize=(13, 8.5), facecolor="black")
    for col, (title, lab) in enumerate(panels):
        for row, sl in enumerate((ax_sl, co_sl)):
            ax = axes[row, col]
            ax.imshow(np.clip(sl(img), -160, 240), cmap="gray", origin="lower", interpolation="bilinear",
                      aspect=ct_c.header.get_zooms()[1] / ct_c.header.get_zooms()[0] if row == 0
                      else ct_c.header.get_zooms()[2] / ct_c.header.get_zooms()[0])
            if lab is not None:
                ax.imshow(sl(lab), cmap=cmap, vmin=0, vmax=N_ORGANS, origin="lower", interpolation="nearest",
                          aspect=ax.get_aspect())
            elif title.startswith("AI"):
                ax.text(0.5, 0.5, "no AI output yet", color="w", ha="center", transform=ax.transAxes)
            ax.set_axis_off()
            if row == 0:
                ax.set_title(title, color="w")
    fig.suptitle(f"{case_id} - axial and coronal views (R on left)", color="w")
    fig.tight_layout()
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=90, facecolor="black")
    plt.close(fig)
    return out_png
