import json

import cv2
import numpy as np


def _write_mp4(path, n_colors=2):
    colors = [(0, 255, 0), (30, 30, 30)][:n_colors]
    w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 10, (160, 120))
    for c in colors:
        for _ in range(10):
            w.write(np.full((120, 160, 3), c, dtype=np.uint8))
    w.release()


def test_pipeline_outputs_contract(tmp_path):
    from src.clipper.pipeline import run_pipeline
    v = str(tmp_path / "v.mp4")
    _write_mp4(v)
    out = str(tmp_path / "run1")
    m = run_pipeline(v, out, prefer_clip=False)
    for f in ["shots.json", "candidates.json", "manifest.json",
              "diagnostics/scores.csv"]:
        assert (tmp_path / "run1" / f).exists()
    shots = json.loads((tmp_path / "run1" / "shots.json").read_text())
    cands = json.loads((tmp_path / "run1" / "candidates.json").read_text())
    assert m["counts"]["total_shots"] == len(shots) == 2
    # production: candidates subset of shots, only center_field_good
    assert all(c["view_class"] == "center_field_good" for c in cands)
    assert all(c["accepted_for_pitch_detection"] for c in cands)
    assert all((s["view_class"] == "center_field_good") == s["accepted_for_pitch_detection"]
               for s in shots)
