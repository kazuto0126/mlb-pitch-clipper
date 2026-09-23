"""M4 tests: sampling, failure isolation, metrics, competition, decisions."""
import sys

sys.path.insert(0, ".")


def test_plan_segments_spread():
    from src.clipper.acquisition.preview_acquire import plan_segments
    plans = plan_segments(1800.0)
    assert len(plans) == 5
    starts = [p.start for p in plans]
    # near 10/30/50/70/90% of 30 min
    assert abs(starts[0] - 170) < 5 and abs(starts[2] - 890) < 5
    assert abs(starts[4] - 1610) < 5
    assert all(p.duration == 20.0 for p in plans)


def test_plan_segments_short_video():
    from src.clipper.acquisition.preview_acquire import plan_segments
    assert len(plan_segments(100.0)) == 3
    one = plan_segments(40.0)
    assert len(one) == 1 and one[0].duration == 20.0
    unk = plan_segments(None)
    assert len(unk) == 3


def test_section_failure_never_crashes_gate():
    from src.clipper.acquisition.preview_acquire import acquire_preview_segments

    def boom(url, start, dur, dest):
        raise RuntimeError("no network")

    plans = acquire_preview_segments("http://x", 600.0, "/tmp/never",
                                     downloader=boom)
    assert len(plans) == 5
    assert all(p.method == "failed" for p in plans)


def test_metrics_formulas():
    from src.clipper.acquisition.schemas import compute_metrics
    m = compute_metrics(cf_candidates=10, shots=20, complete=3, rejected=7,
                        by_reason={"shot_discontinuity": 2,
                                   "end_incomplete": 5}, preview_sec=100.0)
    assert m["complete_event_yield"] == 0.3
    assert m["complete_events_per_minute"] == 1.8
    assert m["incomplete_rate"] == 0.7
    assert m["discontinuity_rate"] == 0.1
    z = compute_metrics(0, 0, 0, 0, {}, 0.0)
    assert z["complete_event_yield"] == 0.0 and z["complete_events_per_minute"] == 0.0


def test_zero_cf_and_zero_events_reject():
    from src.clipper.acquisition.gate import decide
    from src.clipper.acquisition.schemas import SourcePreview
    r = decide(SourcePreview(center_field_shots=0, preview_status="ok"))
    assert r.preview_decision == "reject"
    r2 = decide(SourcePreview(center_field_shots=8, center_field_ratio=0.2,
                              m2_complete_events=0, complete_event_yield=0.0,
                              incomplete_rate=1.0, discontinuity_rate=0.5,
                              preview_status="ok"))
    assert r2.preview_decision == "reject"


def test_competition_context():
    from src.clipper.discovery.competition import classify_competition as cc
    assert cc("EVERY PITCH in the 2023 World Baseball Classic", channel="MLB") == "non_mlb"
    assert cc("Full Outing vs Giants", channel="MLB") == "mlb"
    assert cc("Bullpen session day 3", channel="Fan") == "non_mlb"
    assert cc("NPB highlights reel") == "non_mlb"
    assert cc("Some random compilation", channel="Random") == "unknown"


def test_wbc_excluded_from_production():
    from src.clipper.acquisition.gate import decide
    from src.clipper.acquisition.schemas import SourcePreview
    r = decide(SourcePreview(center_field_shots=10, m2_complete_events=5,
                             complete_event_yield=0.5, discontinuity_rate=0.0,
                             competition_context="non_mlb", preview_status="ok"))
    assert r.preview_decision == "reject"


def test_decision_deterministic_and_unknown_cap():
    from src.clipper.acquisition.gate import decide
    from src.clipper.acquisition.schemas import SourcePreview
    good = dict(center_field_shots=10, center_field_ratio=0.6,
                m2_complete_events=4, complete_event_yield=0.4,
                incomplete_rate=0.6, discontinuity_rate=0.05,
                preview_status="ok", competition_context="mlb")
    assert decide(SourcePreview(**good)).preview_decision == "recommended"
    assert decide(SourcePreview(**good)).preview_decision == \
        decide(SourcePreview(**good)).preview_decision
    unk = dict(good, competition_context="unknown")
    assert decide(SourcePreview(**unk)).preview_decision == "borderline"


def test_manifest_schema_keys():
    from src.clipper.acquisition.schemas import SourcePreview
    d = SourcePreview(video_id="v", competition_context="mlb").to_dict()
    for k in ["video_id", "metadata_score", "competition_context",
              "preview_duration_sec", "center_field_ratio",
              "complete_events_per_minute", "complete_event_yield",
              "incomplete_rate", "discontinuity_rate", "edge_skipped_shots",
              "preview_decision", "reasons"]:
        assert k in d, k


def test_preview_source_sets_competition_without_network(tmp_path):
    from src.clipper.acquisition.gate import preview_source

    def boom(url, start, dur, dest):
        raise RuntimeError("offline")

    cand = {"video_id": "v", "title": "EVERY PITCH in the 2023 WBC",
            "channel": "MLB", "url": "http://x", "source_type": "every_pitch",
            "suitability": {"final_score": 0.9}, "duration": 3000}
    rep = preview_source(cand, str(tmp_path / "src"), downloader=boom)
    assert rep.competition_context == "non_mlb"
    assert rep.preview_status == "failed"
    assert rep.preview_decision == "reject"
