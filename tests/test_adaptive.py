"""M7.1 adaptive preview tests (pure policy + stubbed gate runs)."""
import sys

sys.path.insert(0, ".")


def test_sparse_evidence_triggers_expansion():
    from src.clipper.acquisition.evidence import classify_evidence
    assert classify_evidence(1, 0, 1, {})[0] == "insufficient"
    assert classify_evidence(5, 0, 3, {})[0] == "insufficient"


def test_sufficient_good_does_not_expand():
    from src.clipper.acquisition.evidence import classify_evidence
    # Yamamoto Q8Bl preview: 5 CF, 1 event
    assert classify_evidence(5, 1, 4, {})[0] == "sufficient_good"


def test_sufficient_bad_does_not_expand():
    from src.clipper.acquisition.evidence import classify_evidence
    # Skubal montage: 18 CF, 0 events, 9 start_incomplete
    st, _ = classify_evidence(18, 0, 14, {"start_incomplete": 9,
                                          "no_complete_pitch": 5})
    assert st == "sufficient_bad"


def test_expansion_timestamps_no_duplication_and_deterministic():
    from src.clipper.acquisition.preview_acquire import plan_expansion
    have = [(170.0, 190.0), (700.0, 730.0)]
    a = plan_expansion(1800.0, have, (0.20, 0.40, 0.60, 0.80))
    b = plan_expansion(1800.0, have, (0.20, 0.40, 0.60, 0.80))
    assert [(p.start, p.duration) for p in a] == [(p.start, p.duration) for p in b]
    # 710-730 overlaps have[1] (700-730) -> skipped; others kept
    assert [p.start for p in a] == [350.0, 1070.0, 1430.0]


def test_short_source_coverage_behavior():
    from src.clipper.acquisition.evidence import expansion_rounds
    assert len(expansion_rounds(660.0)) == 2  # short: rounds 2 and 3
    assert len(expansion_rounds(2600.0)) == 1  # long: round 2 only


def test_max_preview_budget_respected():
    from src.clipper.acquisition.evidence import budget_ok
    assert budget_ok(5, 100.0, 1800.0) is True
    assert budget_ok(10, 100.0, 1800.0) is False
    assert budget_ok(5, 200.0, 1800.0) is False
    assert budget_ok(5, 100.0, 200.0) is False  # 50% fraction cap
    assert budget_ok(0, 0.0, None) is True


def _stubbed_preview(monkeypatch, agg_rounds):
    """Stub frozen M1/M2 segment evaluation with canned aggregates."""
    import src.clipper.acquisition.gate as g
    calls = {"n": 0}

    def fake_eval(files, workdir, start_idx=0):
        i = calls["n"]
        calls["n"] += 1
        return agg_rounds[min(i, len(agg_rounds) - 1)]

    monkeypatch.setattr(g, "evaluate_segments", fake_eval)

    def fake_dl(url, start, dur, dest):
        from src.clipper.acquisition.schemas import PreviewSegmentPlan
        return PreviewSegmentPlan(0, start, dur,
                                  method="yt-dlp-section", file=dest)
    return fake_dl


def test_empty_candidate_segment_does_not_kill_source(tmp_path, monkeypatch):
    import json
    import src.clipper.acquisition.gate as g

    def fake_m1(video, outdir, prefer_clip=True):
        from pathlib import Path
        Path(outdir).mkdir(parents=True, exist_ok=True)
        Path(outdir, "shots.json").write_text("[]")
        Path(outdir, "candidates.json").write_text("[]")
        return {}

    monkeypatch.setattr(g, "run_m1", fake_m1)
    out = g.evaluate_segments(["a.mp4", "b.mp4"], str(tmp_path / "w"))
    assert out["shots"] == 0 and out["segments_skipped_empty"] == 2


def test_partial_segment_failure_tolerated(tmp_path, monkeypatch):
    import src.clipper.acquisition.gate as g
    agg = {"shots": 4, "candidates": 3, "complete": 1, "rejected": 2,
           "by_reason": {}, "edge_skipped": 2}
    monkeypatch.setattr(g, "evaluate_segments",
                        lambda files, w, start_idx=0: agg)

    def flaky(url, start, dur, dest):
        from src.clipper.acquisition.schemas import PreviewSegmentPlan
        if int(start) % 2:
            return PreviewSegmentPlan(0, start, dur, method="failed",
                                      error="net")
        return PreviewSegmentPlan(0, start, dur, method="yt-dlp-section",
                                  file=dest)

    cand = {"video_id": "v", "title": "X Full Outing", "channel": "MLB",
            "url": "http://x", "source_type": "full_outing",
            "suitability": {"final_score": 0.9}, "duration": 2200}
    rep = g.preview_source(cand, str(tmp_path / "s"), downloader=flaky)
    assert rep.preview_status in ("ok", "partial")
    assert rep.preview_decision in ("recommended", "borderline", "reject")


def test_sufficient_good_does_not_expand(tmp_path, monkeypatch):
    import src.clipper.acquisition.gate as g
    rich = {"shots": 10, "candidates": 5, "complete": 2, "rejected": 3,
            "by_reason": {}, "edge_skipped": 2}
    calls = {"n": 0}

    def fake_eval(files, w, start_idx=0):
        calls["n"] += 1
        return dict(rich)

    monkeypatch.setattr(g, "evaluate_segments", fake_eval)

    def fake_dl(url, start, dur, dest):
        from src.clipper.acquisition.schemas import PreviewSegmentPlan
        return PreviewSegmentPlan(0, start, dur, method="yt-dlp-section",
                                  file=dest)

    cand = {"video_id": "v", "title": "X Full Outing", "channel": "MLB",
            "url": "http://x", "source_type": "full_outing",
            "suitability": {"final_score": 0.9}, "duration": 2200}
    rep = g.preview_source(cand, str(tmp_path / "s"), downloader=fake_dl)
    assert rep.adaptive_preview_triggered is False
    assert rep.expanded_preview_segments == 0
    assert rep.evidence_state == "sufficient_good"
    assert rep.preview_segment_count == 5  # round 1 only


def test_adaptive_manifest_fields(tmp_path, monkeypatch):
    import src.clipper.acquisition.gate as g
    sparse = {"shots": 4, "candidates": 1, "complete": 0, "rejected": 1,
              "by_reason": {}, "edge_skipped": 2}
    rich = {"shots": 6, "candidates": 5, "complete": 2, "rejected": 3,
            "by_reason": {}, "edge_skipped": 2}
    monkeypatch.setattr(g, "evaluate_segments",
                        lambda files, w, start_idx=0: rich if start_idx else sparse)

    def fake_dl(url, start, dur, dest):
        from src.clipper.acquisition.schemas import PreviewSegmentPlan
        return PreviewSegmentPlan(0, start, dur, method="yt-dlp-section",
                                  file=dest)

    cand = {"video_id": "v", "title": "X", "channel": "MLB",
            "url": "http://x", "source_type": "every_pitch",
            "suitability": {"final_score": 0.8}, "duration": 660}
    rep = g.preview_source(cand, str(tmp_path / "s"), downloader=fake_dl)
    assert rep.adaptive_preview_triggered is True
    assert rep.expanded_preview_segments > 0
    assert rep.evidence_state == "sufficient_good"
    assert rep.final_preview_decision == rep.preview_decision
    assert rep.total_preview_seconds == rep.preview_duration_sec
