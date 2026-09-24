"""M6.3 dissolve-guard tests (synthetic videos, deterministic)."""
import sys

sys.path.insert(0, ".")

import cv2
import numpy as np


def _mp4(path, parts, fps=10, size=(160, 120)):
    # parts: list of (seconds, BGR color)
    w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    for secs, color in parts:
        for _ in range(int(secs * fps)):
            w.write(np.full((size[1], size[0], 3), color, dtype=np.uint8))
    w.release()
    return path


def test_clear_dissolve_contaminated_rejected(tmp_path):
    from src.clipper.shot_purity import assess_homogeneity
    v = _mp4(str(tmp_path / "v.mp4"), [(2.0, (0, 255, 0)), (2.0, (30, 30, 30))])
    g = assess_homogeneity(v, 0.0, 4.0)
    assert g["contaminated"] is True


def test_stable_center_field_not_falsely_flagged(tmp_path):
    from src.clipper.shot_purity import assess_homogeneity
    v = _mp4(str(tmp_path / "v.mp4"), [(4.0, (0, 255, 0))])
    g = assess_homogeneity(v, 0.0, 4.0)
    assert g["contaminated"] is False
    assert g["min_adj"] >= 0.8 and g["edge"] >= 0.8


def test_homogeneity_deterministic(tmp_path):
    from src.clipper.shot_purity import assess_homogeneity
    v = _mp4(str(tmp_path / "v.mp4"), [(2.0, (0, 255, 0)), (2.0, (0, 200, 0))])
    assert assess_homogeneity(v, 0.0, 4.0) == assess_homogeneity(v, 0.0, 4.0)
