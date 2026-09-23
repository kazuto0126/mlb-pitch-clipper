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
              "confidence", "accepted_for_pitch_detection", "reject_reason"]:
        assert k in d
    assert d["duration"] == round(9.25 - 1.5, 3)
