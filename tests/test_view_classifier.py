from PIL import Image


def _green_image():
    return Image.new("RGB", (256, 144), (34, 139, 34))


def test_heuristic_runs_offline():
    from src.clipper.view_classifier import HeuristicViewClassifier
    from src.clipper.schemas import VIEW_LABELS
    r = HeuristicViewClassifier().classify([_green_image(), _green_image()])
    assert r.view_class in VIEW_LABELS
    assert 0.0 <= r.confidence <= 1.0
    assert set(r.scores.keys()) == set(VIEW_LABELS)
    assert r.backend.startswith("heuristic")


def test_prompts_cover_all_labels():
    from src.clipper.view_classifier import PROMPTS
    from src.clipper.schemas import VIEW_LABELS
    assert set(PROMPTS.keys()) == set(VIEW_LABELS)
    for v in VIEW_LABELS:
        assert len(PROMPTS[v]) >= 2
        for t in PROMPTS[v]:
            low = t.lower()
            # prompts must be framing-based, never identity-based
            assert "ohtani" not in low and "skenes" not in low and "jersey number" not in low
