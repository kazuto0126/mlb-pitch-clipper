"""M6 tests: aggregation math, div-zero, taxonomy, dedup warning."""
import sys

sys.path.insert(0, ".")


def test_ratios_and_div_zero():
    from src.clipper.production.reporting import product_ratios
    r = product_ratios({"shot_count": 100, "center_field_candidates": 50,
                        "complete_events": 10, "final_clip_count": 9,
                        "full_video_duration_sec": 1800})
    assert r["center_field_rate"] == 0.5
    assert r["complete_yield"] == 0.2
    assert r["final_yield"] == 0.18
    assert r["clips_per_source_minute"] == 0.3
    z = product_ratios({})
    assert z == {"center_field_rate": 0.0, "complete_yield": 0.0,
                 "final_yield": 0.0, "clips_per_source_minute": 0.0}


def test_failure_taxonomy():
    from src.clipper.production.reporting import classify_failure as c
    assert c({"status": "failed-download"}) == "DOWNLOAD_FAILURE"
    assert c({"competition_context": "non_mlb"}) == "SOURCE_NOT_MLB"
    assert c({"status": "ok", "shot_count": 10, "center_field_candidates": 0,
              "complete_events": 0, "final_clip_count": 0}) == "LOW_CENTER_FIELD_COVERAGE"
    assert c({"status": "ok", "shot_count": 10, "center_field_candidates": 8,
              "complete_events": 0, "final_clip_count": 0,
              "rejected_start_incomplete": 2, "rejected_end_incomplete": 2,
              "rejected_no_complete_pitch": 2,
              "full_video_duration_sec": 1200}) == "ZERO_USABLE_EVENTS"
    assert c({"status": "ok", "shot_count": 100, "center_field_candidates": 10,
              "complete_events": 0, "final_clip_count": 0,
              "rejected_start_incomplete": 0, "rejected_end_incomplete": 0,
              "rejected_no_complete_pitch": 0,
              "full_video_duration_sec": 1200}) == "LOW_CENTER_FIELD_COVERAGE"
    assert c({"status": "ok", "shot_count": 100, "center_field_candidates": 50,
              "complete_events": 2, "final_clip_count": 2,
              "rejected_start_incomplete": 30, "rejected_end_incomplete": 5,
              "rejected_no_complete_pitch": 5,
              "full_video_duration_sec": 1200}) == "HIGH_START_INCOMPLETE"
    assert c({"status": "ok", "shot_count": 100, "center_field_candidates": 50,
              "complete_events": 2, "final_clip_count": 0,
              "rejected_start_incomplete": 0, "rejected_end_incomplete": 0,
              "rejected_no_complete_pitch": 0,
              "full_video_duration_sec": 1200}) == "LOW_COMPLETE_EVENT_YIELD"


def test_dedup_warning_and_partial_run():
    from src.clipper.production.reporting import dedup_warning, build_rows
    assert dedup_warning(0, 22) is False
    assert dedup_warning(9, 21) is False
    assert dedup_warning(10, 20) is True
    assert dedup_warning(0, 0) is False
    rows = build_rows([{"pitcher": "x", "status": "failed-download"}])
    assert rows[0]["failure_taxonomy"] == "DOWNLOAD_FAILURE"
    assert rows[0]["center_field_rate"] == 0.0
