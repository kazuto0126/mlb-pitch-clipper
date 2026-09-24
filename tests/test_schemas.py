import json


def test_build_shot_production_rule():
    from src.clipper.schemas import build_shot
    s = build_shot("s001", 0.0, 5.0, "center_field_good", 0.9)
    assert s.accepted_for_pitch_detection is True
    assert s.reject_reason is None
    for label, reason in [
        ("side_fullbody_acceptable", "non_center_field_side_view_reserved"),
        ("closeup_bad", "closeup"),
        ("batter_bad", "wrong_view_batter"),
        ("field_bad", "wrong_view_field"),
        ("graphic_bad", "graphic_transition"),
        ("other_bad", "other_rejected"),
    ]:
        r = build_shot("s002", 0.0, 5.0, label, 0.8)
        assert r.accepted_for_pitch_detection is False
        assert r.reject_reason == reason


def test_shot_schema_fields(tmp_path):
    from src.clipper.schemas import build_shot
    s = build_shot("s007", 1.5, 9.25, "center_field_good", 0.77, classifier="x", scores={"a": 1})
    d = s.to_dict()
    for k in ["shot_id", "start", "end", "duration", "view_class",
              "confidence", "accepted_for_pitch_detection", "reject_reason",
              "transition_contaminated"]:
        assert k in d
    assert d["duration"] == round(9.25 - 1.5, 3)


def test_low_confidence_cf_rejected():
    from src.clipper.schemas import build_shot
    # legacy default (no gate) preserves view-only behavior
    assert build_shot("s1", 0, 5, "center_field_good", 0.37).accepted_for_pitch_detection is True
    # production gate
    r = build_shot("s1", 0, 5, "center_field_good", 0.37, min_confidence=0.5)
    assert r.accepted_for_pitch_detection is False
    assert r.reject_reason == "low_view_confidence"
    r = build_shot("s2", 0, 5, "center_field_good", 0.61, min_confidence=0.5)
    assert r.accepted_for_pitch_detection is True
    # low-confidence non-CF keeps its own reason (gate must not mask it)
    r = build_shot("s3", 0, 5, "batter_bad", 0.2, min_confidence=0.5)
    assert r.reject_reason == "wrong_view_batter"


def test_dissolve_contaminated_rejected():
    from src.clipper.schemas import build_shot
    r = build_shot("s4", 0, 5, "center_field_good", 0.85,
                   min_confidence=0.5, transition_contaminated=True)
    assert r.accepted_for_pitch_detection is False
    assert r.reject_reason == "transition_contaminated"
    assert r.transition_contaminated is True


def test_high_confidence_stable_cf_kept():
    from src.clipper.schemas import build_shot
    r = build_shot("s5", 0, 5, "center_field_good", 0.88,
                   min_confidence=0.5, transition_contaminated=False)
    assert r.accepted_for_pitch_detection is True
    assert r.reject_reason is None


def test_purity_constants_global():
    import inspect
    from src.clipper import shot_purity as sp
    assert sp.MIN_CENTER_FIELD_CONFIDENCE == 0.5
    assert sp.HOMOG_N == 5
    src = inspect.getsource(sp)
    # no pitcher/team/channel-specific logic allowed in purity rules
    for banned in ["Ohtani", "Crochet", "Miller", "Skenes", "Yamamoto",
                   "Dodgers", "WEEI", "ESPN"]:
        assert banned not in src
