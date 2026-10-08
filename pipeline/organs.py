"""The 12 organs shown in CT Anatomy Explorer v0.5.

Every other file uses this one table, so the mapping between
  * the compact index used in our label maps (1..12),
  * the TotalSegmentator v2 file name (segmentations/<key>.nii.gz), and
  * the VISTA-3D label id (MONAI bundle `vista3d`, configs/metadata.json)
lives in exactly one place.

VISTA-3D ids were copied from the bundle's metadata.json (channel_def).
TotalSegmentator names were checked against totalsegmentator/map_to_binary.py.
If you add organs, add them here and nowhere else.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Organ:
    index: int          # value in OUR compact label maps (reference.nii.gz / ai.nii.gz)
    key: str            # TotalSegmentator v2 file name (without .nii.gz)
    name: str           # display name
    vista_id: int       # VISTA-3D label id (prompt + output value)
    color: tuple        # RGB 0-255 used by the viewer and QC figures
    tubular: bool = False  # long structures that may legitimately run out of the scan


ORGANS: list[Organ] = [
    Organ(1, "liver", "Liver", 1, (196, 98, 72)),
    Organ(2, "spleen", "Spleen", 3, (148, 103, 189)),
    Organ(3, "pancreas", "Pancreas", 4, (245, 197, 66)),
    Organ(4, "kidney_right", "Right kidney", 5, (214, 90, 140)),
    Organ(5, "kidney_left", "Left kidney", 14, (236, 139, 178)),
    Organ(6, "gallbladder", "Gallbladder", 10, (85, 168, 104)),
    Organ(7, "stomach", "Stomach", 12, (230, 150, 90)),
    Organ(8, "aorta", "Aorta", 6, (220, 40, 40), tubular=True),
    Organ(9, "inferior_vena_cava", "Inferior vena cava", 7, (60, 110, 220), tubular=True),
    Organ(10, "esophagus", "Oesophagus", 11, (199, 132, 104), tubular=True),
    Organ(11, "duodenum", "Duodenum", 13, (255, 214, 150)),
    Organ(12, "urinary_bladder", "Urinary bladder", 15, (80, 200, 220)),
]

N_ORGANS = len(ORGANS)
VISTA_PROMPTS = [o.vista_id for o in ORGANS]          # label_prompt passed to VISTA-3D
VISTA_TO_INDEX = {o.vista_id: o.index for o in ORGANS}  # VISTA-3D output value -> our index
BY_KEY = {o.key: o for o in ORGANS}
BY_INDEX = {o.index: o for o in ORGANS}

# Colours for the comparison view (Okabe-Ito palette, colour-blind safe)
COMPARE = {
    1: ("Agree (AI and expert)", (0, 158, 115)),
    2: ("AI only (extra)", (213, 94, 0)),
    3: ("Missed by AI", (0, 114, 178)),
}


def organ_table() -> list[dict]:
    """JSON-friendly organ list for the viewer manifest."""
    return [
        {"index": o.index, "key": o.key, "name": o.name, "vista_id": o.vista_id, "color": list(o.color)}
        for o in ORGANS
    ]
