"""Quick self-checks that need no GPU and no downloads.

    python tests/test_pipeline.py      (or: pytest tests)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from pipeline.evaluate import confusion, organ_metrics, sanity_flags  # noqa: E402
from pipeline.organs import BY_KEY, ORGANS, VISTA_TO_INDEX  # noqa: E402


def test_organ_table_is_consistent():
    assert len(ORGANS) == 12
    assert len({o.index for o in ORGANS}) == 12
    assert len({o.vista_id for o in ORGANS}) == 12
    # spot checks against the VISTA-3D bundle's label list (configs/metadata.json)
    assert VISTA_TO_INDEX[1] == BY_KEY["liver"].index
    assert VISTA_TO_INDEX[3] == BY_KEY["spleen"].index
    assert VISTA_TO_INDEX[5] == BY_KEY["kidney_right"].index
    assert VISTA_TO_INDEX[14] == BY_KEY["kidney_left"].index
    assert VISTA_TO_INDEX[15] == BY_KEY["urinary_bladder"].index


def test_dice_values():
    ref = np.zeros((10, 10, 10), np.uint8)
    ref[2:6, 2:6, 2:6] = BY_KEY["liver"].index            # 64 voxels
    m = organ_metrics(confusion(ref, ref.copy()), 0.001)
    assert m["liver"]["dice"] == 1.0
    ai = np.zeros_like(ref)
    ai[2:6, 2:6, 2:4] = BY_KEY["liver"].index             # 32 voxels, all inside
    m = organ_metrics(confusion(ref, ai), 0.001)
    assert abs(m["liver"]["dice"] - 2 * 32 / (64 + 32)) < 1e-4
    assert m["liver"]["missed_vox"] == 32 and m["liver"]["ai_only_vox"] == 0
    assert m["spleen"]["dice"] is None                     # absent in both


def test_left_right_swap_is_flagged():
    r, l = BY_KEY["kidney_right"].index, BY_KEY["kidney_left"].index
    ref = np.zeros((10, 10, 10), np.uint8)
    ref[1:4, 1:4, 1:4] = r
    ref[6:9, 6:9, 6:9] = l
    ai = ref.copy()
    ai[ref == r], ai[ref == l] = l, r
    cm = confusion(ref, ai)
    flags = sanity_flags(cm, organ_metrics(cm, 0.001))
    assert any("SWAP" in f for f in flags), flags


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
