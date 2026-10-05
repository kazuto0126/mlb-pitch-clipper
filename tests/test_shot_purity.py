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


def _scores(cf, runner=0.0):
    return {"center_field_good": cf, "side_fullbody_acceptable": runner,
            "closeup_bad": 0.05, "batter_bad": 0.03, "field_bad": 0.02,
            "graphic_bad": 0.01, "other_bad": 0.01}


def test_class_margin_deterministic():
    from src.clipper.shot_purity import class_margin
    s = _scores(0.557, 0.28)
    assert class_margin(s) == class_margin(s) == round(0.557 - 0.28, 4)


def test_homogeneous_closeup_rejected():
    from src.clipper.schemas import build_shot
    # s024 profile: CF 0.557, margin 0.277, edge 0.061
    r = build_shot("s", 0, 16, "center_field_good", 0.557,
                   min_confidence=0.5, homogeneous_closeup=True)
    assert r.accepted_for_pitch_detection is False
    assert r.reject_reason == "homogeneous_closeup"
    assert r.homogeneous_closeup is True


def test_true_cf_retained_despite_low_margin():
    from src.clipper.schemas import build_shot
    # s118 profile: TRUE CF, margin 0.22 but broadcast texture kept it
    r = build_shot("s", 0, 5, "center_field_good", 0.593,
                   min_confidence=0.5, homogeneous_closeup=False)
    assert r.accepted_for_pitch_detection is True


def test_high_confidence_true_cf_retained():
    from src.clipper.schemas import build_shot
    r = build_shot("s", 0, 8, "center_field_good", 0.88,
                   min_confidence=0.5, homogeneous_closeup=False)
    assert r.accepted_for_pitch_detection is True
    assert r.reject_reason is None


def test_transition_and_confidence_behavior_unchanged():
    from src.clipper.schemas import build_shot
    r = build_shot("s", 0, 5, "center_field_good", 0.37, min_confidence=0.5)
    assert r.reject_reason == "low_view_confidence"
    r = build_shot("s", 0, 5, "center_field_good", 0.65,
                   min_confidence=0.5, transition_contaminated=True)
    assert r.reject_reason == "transition_contaminated"


def test_no_pitcher_specific_logic_in_veto():
    import inspect
    from src.clipper import shot_purity as sp
    src = inspect.getsource(sp)
    for banned in ["Ohtani", "Crochet", "Miller", "Skenes", "Yamamoto",
                   "Dodgers", "WEEI", "ESPN", "face_recognition",
                   "jersey_number", "keypoint", "skeleton", "pose_",
                   "landmark"]:
        assert banned not in src


def test_indecisive_closeup_veto_ignores_texture(tmp_path):
    from src.clipper.shot_purity import assess_closeup
    # textured frame (high edge density) that the M6.4 AND rule would keep
    import cv2
    import numpy as np
    path = str(tmp_path / "busy.mp4")
    w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 10, (160, 120))
    yy, xx = np.mgrid[0:120, 0:160]
    busy = np.where(((yy // 4 + xx // 4) % 2 == 0)[..., None], 255, 0).astype(np.uint8)
    for _ in range(40):
        w.write(np.repeat(busy, 3, axis=2))
    w.release()

    def sc(cf, runner_cls, runner):
        s = {"center_field_good": cf, "side_fullbody_acceptable": 0.01,
             "closeup_bad": 0.01, "batter_bad": 0.01, "field_bad": 0.01,
             "graphic_bad": 0.01, "other_bad": 0.01}
        s[runner_cls] = runner
        return s

    # s118-like: margin 0.22 vs side view -> vetoed despite busy texture
    r = assess_closeup(path, 0.0, 4.0, sc(0.593, "side_fullbody_acceptable", 0.373))
    assert r["vetoed"] is True and r["edge"] is None
    for cls in ("batter_bad", "other_bad", "closeup_bad"):
        assert assess_closeup(path, 0.0, 4.0, sc(0.60, cls, 0.40))["vetoed"] is True
    # dim-broadcast CF: low margin vs field_bad is benign -> texture decides
    r = assess_closeup(path, 0.0, 4.0, sc(0.55, "field_bad", 0.40))
    assert r["vetoed"] is False and r["edge"] is not None
    # margin just above the new cut (s279-like 0.322) -> old rule only
    r = assess_closeup(path, 0.0, 4.0, sc(0.577, "side_fullbody_acceptable", 0.255))
    assert r["vetoed"] is False


def test_assess_closeup_veto_logic(tmp_path):
    from src.clipper.shot_purity import assess_closeup
    v = _mp4(str(tmp_path / "v.mp4"), [(4.0, (0, 255, 0))])
    # decisive margin: never vetoed regardless of texture
    r = assess_closeup(v, 0.0, 4.0, _scores(0.9, 0.05))
    assert r["vetoed"] is False and r["reason"] == "decisive CF margin"
    # uniform dark frames: low edge + low margin -> veto
    v2 = _mp4(str(tmp_path / "w.mp4"), [(4.0, (30, 30, 30))])
    r = assess_closeup(v2, 0.0, 4.0, _scores(0.4, 0.35))
    assert r["vetoed"] is True
