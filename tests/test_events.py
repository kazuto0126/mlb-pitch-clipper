"""M2 event-logic tests on synthetic motion tracks (no video needed)."""
import sys

sys.path.insert(0, ".")

from src.clipper.events import localize
from src.clipper.motion import MotionTrack


def _track(vals, t0=0.0, dt=0.1):
    n = len(vals)
    ts = [round(t0 + i * dt, 3) for i in range(n)]
    return MotionTrack(ts, list(vals), list(vals), 10.0)


def test_complete_pattern_accepted():
    # 1s quiet, ~1.5s active with peak, 1s settle
    vals = [0.1] * 10 + [0.4, 0.6, 0.8, 0.7, 0.6, 0.55] + [0.35] * 9 + [0.1] * 10
    evs, rejs = localize("s001", 0.0, 4.4, _track(vals, dt=0.1))
    assert len(evs) == 1 and not rejs
    e = evs[0]
    assert e.complete and e.reject_reason is None
    assert e.clip_start < e.motion_onset < e.motion_peak < e.settle_time < e.clip_end
    assert e.clip_start >= 0.0 and e.clip_end <= 4.4


def test_start_cut_rejected():
    # opens hot: no prepared interval
    vals = [0.7] * 12 + [0.2] * 10
    evs, rejs = localize("s002", 0.0, 2.2, _track(vals, dt=0.1))
    assert not evs
    assert rejs and rejs[0].reject_reason == "start_incomplete"


def test_end_cut_rejected():
    # quiet + active, but motion runs into the cut (no settle)
    vals = [0.1] * 10 + [0.6] * 12
    evs, rejs = localize("s003", 0.0, 2.2, _track(vals, dt=0.1))
    assert not evs
    assert rejs and rejs[0].reject_reason == "end_incomplete"


def test_noise_no_event():
    # small blips only, never sustained HIGH
    vals = [0.1] * 8 + [0.35] * 3 + [0.1] * 8 + [0.4] * 2 + [0.1] * 10
    evs, rejs = localize("s004", 0.0, 3.1, _track(vals, dt=0.1))
    assert not evs
    assert rejs and rejs[0].reject_reason in ("no_complete_pitch", "ambiguous_motion")


def test_lead_transition_artifact_skipped():
    # cut artifact spike in first 0.4s, then genuine full pattern
    vals = [0.5, 0.4, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1,
            0.5, 0.7, 0.9, 0.8, 0.7, 0.6, 0.5, 0.45, 0.4, 0.35, 0.2, 0.1,
            0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1]
    evs, rejs = localize("s006", 0.0, 3.2, _track(vals, dt=0.1))
    assert len(evs) == 1 and not rejs
    assert evs[0].motion_onset >= 0.4


def test_hot_throughout_is_start_incomplete():
    vals = [0.6] * 25
    evs, rejs = localize("s007", 0.0, 2.5, _track(vals, dt=0.1))
    assert not evs
    assert rejs and rejs[0].reject_reason == "start_incomplete"


def _twoshot_mp4(tmp_path):
    import cv2
    import numpy as np
    p = str(tmp_path / "twoshot.mp4")
    w = cv2.VideoWriter(p, cv2.VideoWriter_fourcc(*"mp4v"), 10, (160, 120))
    for _ in range(10):
        w.write(np.full((120, 160, 3), (0, 255, 0), dtype=np.uint8))
    for _ in range(10):
        w.write(np.full((120, 160, 3), (30, 30, 30), dtype=np.uint8))
    w.release()
    return p


def test_hist_corr_same_vs_cut(tmp_path):
    from src.clipper.motion import grab_frame, hist_corr
    p = _twoshot_mp4(tmp_path)
    a, b, c = grab_frame(p, 0.3), grab_frame(p, 0.5), grab_frame(p, 1.5)
    assert hist_corr(a, b) > 0.9
    assert hist_corr(a, c) < 0.45


def test_continuity_ok_catches_mid_window_cut(tmp_path):
    from src.clipper.run_m2 import continuity_ok
    p = _twoshot_mp4(tmp_path)
    ok, _ = continuity_ok(p, 0.1, 0.2, peak=0.5, clip_end=0.8)
    assert ok is True
    ok, corr = continuity_ok(p, 0.1, 0.2, peak=1.5, clip_end=1.8)
    assert ok is False and corr < 0.45


def test_event_fields_have_no_body_terms():
    import json
    vals = [0.1] * 10 + [0.5, 0.6, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.35, 0.3] + [0.2] * 10
    evs, _ = localize("s005", 0.0, 3.0, _track(vals, dt=0.1))
    blob = json.dumps([e.to_dict() for e in evs]).lower()
    for banned in ["elbow", "wrist", "shoulder", "hip", "stride", "arm_slot",
                   "leg_lift", "release_mechanics", "biomech", "pose", "skeleton"]:
        assert banned not in blob


def _rel(vals, t0=0.0, dt=0.1):
    from src.clipper.events import EventParams
    p = EventParams(relative=True, high=0.45, decay_ratio=0.7,
                    min_settle=0.6, gap_bridge=0.5, min_prepared=0.8)
    return localize("rx", t0, t0 + len(vals) * dt, _track(vals, t0, dt),
                    params=p)


def test_residual_motion_after_event_does_not_block():
    # sustained delivery, decay to 0.35 floor (catcher/batter residual),
    # calm to end: must complete (M4.5 core case)
    vals = [0.1] * 10 + [0.5, 0.7, 0.9, 0.8, 0.6, 0.5] \
        + [0.38, 0.35, 0.33, 0.36, 0.34, 0.35, 0.33, 0.34]
    evs, rejs = _rel(vals)
    assert len(evs) == 1 and not rejs
    assert evs[0].clip_start < evs[0].motion_onset < evs[0].clip_end


def test_post_event_minor_movement_below_high_tolerated():
    vals = [0.1] * 10 + [0.6, 0.9, 0.7] + [0.4, 0.38, 0.41, 0.39] * 3
    evs, _ = _rel(vals)
    assert len(evs) == 1


def test_renewed_strong_motion_abandons_first_pattern():
    # full pattern then a SUSTAINED second delivery-level motion: first must
    # not complete on top of it (no event, or only the clean one)
    vals = [0.1] * 10 + [0.6, 0.9, 0.7, 0.5] + [0.2] * 2 \
        + [0.7, 0.9, 0.8, 0.7, 0.7, 0.8, 0.7, 0.6, 0.2] * 2
    evs, rejs = _rel(vals)
    # first pattern's settle (0.2s) < min_settle and renewal is sustained:
    # must not emit a completed event spanning into the renewal
    for e in evs:
        assert e.clip_end <= 2.6


def test_start_cut_still_rejected_relative():
    vals = [0.7] * 8 + [0.2] * 6 + [0.6, 0.9, 0.7] + [0.2] * 8
    evs, rejs = _rel(vals)
    # opens mid-action: may find the later pitch, but must never claim the
    # head motion as a prepared start
    for e in evs:
        assert e.motion_onset >= 0.8
    assert not evs or evs[0].motion_onset >= 0.8


def test_end_cut_still_rejected_relative():
    vals = [0.1] * 12 + [0.6, 0.9, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.68, 0.65]
    evs, rejs = _rel(vals)
    assert not evs
    assert rejs and rejs[0].reject_reason == "end_incomplete"


def test_quiet_dead_ball_remains_rejected_relative():
    vals = [0.12] * 30
    evs, rejs = _rel(vals)
    assert not evs
    assert rejs and rejs[0].reject_reason == "no_complete_pitch"


def test_relative_output_deterministic():
    vals = [0.1] * 10 + [0.6, 0.9, 0.9, 0.8, 0.7, 0.6, 0.5] \
        + [0.38, 0.35, 0.36] + [0.3] * 6
    a = _rel(vals)[0][0].to_dict()
    b = _rel(vals)[0][0].to_dict()
    assert a == b


def test_params_are_global_only():
    from src.clipper.events import EventParams
    import dataclasses
    fields = {f.name for f in dataclasses.fields(EventParams)}
    assert not ({"pitcher", "pitcher_id", "source", "broadcast"} & fields)
    assert "relative" in fields and "decay_ratio" in fields
