import cv2
import numpy as np


def _write_mp4(path, colors_bgr, fps=10, size=(160, 120), per=10):
    w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    for c in colors_bgr:
        for _ in range(per):
            w.write(np.full((size[1], size[0], 3), c, dtype=np.uint8))
    w.release()


def test_segment_finds_hard_cuts(tmp_path):
    from src.clipper.segment import segment_shots
    p = str(tmp_path / "cuts.mp4")
    _write_mp4(p, [(0, 0, 255), (0, 255, 0), (255, 0, 0)])
    shots = segment_shots(p, sample_fps=5.0, hist_thresh=0.9)
    assert len(shots) == 3
    assert shots[0].start == 0.0
    assert abs(shots[-1].end - 3.0) < 0.3
    for s in shots:
        assert s.duration > 0.4


def test_segment_single_shot(tmp_path):
    from src.clipper.segment import segment_shots
    p = str(tmp_path / "one.mp4")
    _write_mp4(p, [(0, 255, 0)])
    shots = segment_shots(p)
    assert len(shots) == 1
