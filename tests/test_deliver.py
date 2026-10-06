"""Hand-off tests (contract v2): one MP4 + JSON per pitch, padded bounds
inside the shot and away from neighbouring pitches, file-derived video
facts, honest checks, atomic index, immutability, run-chain wiring."""
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

sys.path.insert(0, ".")

SHOTS = [{"shot_id": "s000", "start": 0.0, "end": 10.0},
         {"shot_id": "s001", "start": 10.0, "end": 20.0}]
EVENTS = [  # two pitches in s000, one near the start of s001
    {"event_id": "p001", "source_shot_id": "s000", "clip_start": 2.0, "motion_onset": 3.0,
     "motion_peak": 3.5, "settle_time": 4.5, "clip_end": 4.9},
    {"event_id": "p002", "source_shot_id": "s000", "clip_start": 5.0, "motion_onset": 6.0,
     "motion_peak": 6.5, "settle_time": 7.5, "clip_end": 7.9},
    {"event_id": "p003", "source_shot_id": "s001", "clip_start": 10.2, "motion_onset": 11.0,
     "motion_peak": 11.5, "settle_time": 12.5, "clip_end": 12.9},
]


def _fake_run(base: Path, vid="vid1", run_id="RID"):
    root = base / "out" / "test-pitcher" / run_id
    sdir = root / "sources" / vid
    (sdir / "intermediate").mkdir(parents=True)
    w = cv2.VideoWriter(str(sdir / "intermediate" / "normalized.mp4"),
                        cv2.VideoWriter_fourcc(*"mp4v"), 10, (160, 120))
    for i in range(200):  # 20 s @ 10 fps, brightness encodes time
        w.write(np.full((120, 160, 3), i % 250, dtype=np.uint8))
    w.release()
    (sdir / "shots.json").write_text(json.dumps(SHOTS), encoding="utf-8")
    (sdir / "events.json").write_text(json.dumps(EVENTS), encoding="utf-8")
    kept = [{"clip_id": e["event_id"], "clip_start": e["clip_start"], "clip_end": e["clip_end"]}
            for e in EVENTS]
    (sdir / "dedup.json").write_text(json.dumps({"kept": kept, "removed": []}), encoding="utf-8")
    (root / "Test_Pitcher_2025.mp4").write_bytes(b"merged")
    man = {"status": "ok", "video_id": vid, "pitcher_name": "Test Pitcher",
           "final_path": "Test_Pitcher_2025.mp4", "final_clip_count": 3,
           "game_year": 2025, "game_year_confidence": "low", "source_title": "t",
           "source_url": "http://x", "channel": "c", "source_type": "every_pitch",
           "quality_warning": False, "warnings": []}
    return root, man


def test_pitch_bounds_pad_inside_shot_and_between_pitches():
    from src.clipper.production.deliver import pitch_bounds
    shot0, shot1 = SHOTS
    same0 = EVENTS[:2]
    # p001: 2s pre-roll; end stops 0.3s before p002's onset
    assert pitch_bounds(EVENTS[0], shot0, same0) == (1.0, 5.7)
    # p002: start stops 0.3s after p001 settles; 1.5s post-roll
    assert pitch_bounds(EVENTS[1], shot0, same0) == (4.8, 9.0)
    # p003: pre-roll clamped to the shot start (+0.1s edge)
    assert pitch_bounds(EVENTS[2], shot1, [EVENTS[2]]) == (10.1, 14.0)


def test_pitch_bounds_never_shorter_than_m2_clip():
    from src.clipper.production.deliver import pitch_bounds
    e = dict(EVENTS[0], clip_start=0.05)  # M2 clip already starts at the cut
    assert pitch_bounds(e, SHOTS[0], [e])[0] == 0.05


def test_batch_files_facts_and_checks(tmp_path):
    from src.clipper.production.deliver import deliver_source
    root, man = _fake_run(tmp_path)
    dest = tmp_path / "handoff"
    line = deliver_source(root, man, str(dest), "test-pitcher", "RID", throws="R")
    bdir = dest / "test-pitcher" / "RID_vid1"
    batch = json.loads((bdir / "batch.json").read_text(encoding="utf-8"))
    assert batch["contract_version"] == 2 and batch["pitch_count"] == 3
    assert batch["viewing_video"] == "viewing/Test_Pitcher_2025.mp4"
    p1 = json.loads((bdir / "RID_vid1_p01.json").read_text(encoding="utf-8"))
    mp4 = bdir / p1["video_file"]
    assert p1["sha256"] == hashlib.sha256(mp4.read_bytes()).hexdigest()
    assert p1["throws"] == "R" and p1["view"] == "rear_centerfield_broadcast"
    v = p1["video"]
    assert v["fps"] == "10/1" and v["constant_frame_rate"] and v["square_pixels"]
    assert abs(v["frame_count"] - 47) <= 1 and v["container_start_time_sec"] < 0.05
    assert v["frame_time_rule"].startswith("t = frame_index / fps_float")
    assert (p1["source"]["start_sec"], p1["source"]["end_sec"]) == (1.0, 5.7)
    assert p1["pipeline_anchors_sec"]["motion_onset"] == 2.0  # 3.0 - 1.0
    assert p1["game"]["season"] == "unknown"  # low-confidence year is not a season
    assert p1["checks"]["pitcher_identity"]["status"] == "not_verified"
    assert "pitcher_identity" in p1["requires_human_review"]
    assert "single_motion_event" not in p1["requires_human_review"]
    assert "pitch_delivery_visible" in p1["requires_human_review"]
    assert (dest / "CONTRACT.md").read_text(encoding="utf-8").startswith("# 交付規格")
    idx = [json.loads(l) for l in (dest / "index.jsonl").read_text(encoding="utf-8").splitlines()]
    assert idx == [line] and line["pitch_count"] == 3
    assert not list(dest.rglob("*.tmp")) and not list(dest.rglob("*.tmp.*"))


def test_batches_are_immutable_and_appended(tmp_path):
    from src.clipper.production.deliver import deliver_source
    dest = tmp_path / "handoff"
    root1, man = _fake_run(tmp_path / "a", run_id="RID1")
    deliver_source(root1, man, str(dest), "test-pitcher", "RID1")
    first = (dest / "test-pitcher" / "RID1_vid1" / "RID1_vid1_p01.json").read_text(encoding="utf-8")
    root2, man = _fake_run(tmp_path / "b", run_id="RID2")
    deliver_source(root2, man, str(dest), "test-pitcher", "RID2")
    assert (dest / "test-pitcher" / "RID1_vid1" / "RID1_vid1_p01.json").read_text(encoding="utf-8") == first
    ids = [json.loads(l)["batch_id"] for l in (dest / "index.jsonl").read_text(encoding="utf-8").splitlines()]
    assert ids == ["RID1_vid1", "RID2_vid1"]


def test_run_chain_delivers_only_when_asked(tmp_path, monkeypatch):
    import run
    selected = [{"video_id": "vid1", "url": "http://x", "source_type": "every_pitch",
                 "title": "t", "suitability": {"final_score": 0.9}}]
    reports = [{"video_id": "vid1", "preview_decision": "recommended",
                "evidence_state": "sufficient_good", "center_field_shots": 9,
                "m2_complete_events": 3, "competition_context": "mlb", "preview_status": "ok"}]

    def fake_discovery(name, out_root, top_n, run_id):
        d = Path(out_root) / "d"
        d.mkdir(parents=True, exist_ok=True)
        (d / "selected_sources.json").write_text(json.dumps(selected), encoding="utf-8")
        return {"out_dir": str(d)}

    def fake_preview(slug, sel, out_root, max_sources, run_id):
        d = Path(out_root) / "p"
        d.mkdir(parents=True, exist_ok=True)
        (d / "source_preview_report.json").write_text(json.dumps(reports), encoding="utf-8")
        return {"out_dir": str(d)}

    built = {}

    def fake_produce(pitcher, cand, sdir, taken, min_final_clips=1):
        root, man = _fake_run(tmp_path / f"src{len(built)}")
        built[sdir] = root
        import shutil
        shutil.copytree(root / "sources" / "vid1", sdir, dirs_exist_ok=True)
        shutil.copyfile(root / man["final_path"], Path(sdir).parent.parent / man["final_path"])
        return man

    monkeypatch.setattr(run, "run_discovery", fake_discovery)
    monkeypatch.setattr(run, "run_preview", fake_preview)
    monkeypatch.setattr(run, "produce_source", fake_produce)
    monkeypatch.setattr(run, "classify_competition", lambda *a: "mlb")
    for name, deliver_to in (("A", None), ("B", str(tmp_path / "handoff"))):
        root = tmp_path / "out" / "test-pitcher" / name
        (root / "sources").mkdir(parents=True)
        run._run_chain(SimpleNamespace(pitcher="Test Pitcher", top_n=3, max_sources=3, year=None,
                                       out_root=str(tmp_path / "out"), deliver_to=deliver_to,
                                       throws="L"), name, root)
        m = json.loads((root / "run_manifest.json").read_text(encoding="utf-8"))
        assert m["status"] == "ok" and "delivery_error" not in m
        assert ("deliveries" in m) is (deliver_to is not None)
    p = json.loads((tmp_path / "handoff" / "test-pitcher" / "B_vid1" / "B_vid1_p01.json")
                   .read_text(encoding="utf-8"))
    assert p["throws"] == "L"


def test_operator_exclusion_is_recorded_and_renumbered(tmp_path, monkeypatch):
    from src.clipper.production import deliver
    from src.clipper.production.deliver import deliver_source
    monkeypatch.setattr(deliver, "MIN_BATCH_PITCHES", 2)  # fake run has only 3
    root, man = _fake_run(tmp_path)
    dest = tmp_path / "handoff"
    deliver_source(root, man, str(dest), "test-pitcher", "RID",
                   exclude={2: "catcher motion, no delivery"})
    bdir = dest / "test-pitcher" / "RID_vid1"
    batch = json.loads((bdir / "batch.json").read_text(encoding="utf-8"))
    assert batch["pitch_count"] == 2
    assert batch["excluded_by_operator"] == [{"kept_index": 2, "source_start_sec": 4.8,
                                              "source_end_sec": 9.0,
                                              "reason": "catcher motion, no delivery"}]
    p2 = json.loads((bdir / "RID_vid1_p02.json").read_text(encoding="utf-8"))
    assert p2["source"]["start_sec"] == 10.1  # former 3rd pitch, renumbered
    assert not (bdir / "RID_vid1_p03.json").exists()


def test_refuses_too_small_batch_and_rewrites(tmp_path):
    import pytest
    from src.clipper.production.deliver import deliver_source
    root, man = _fake_run(tmp_path)
    dest = tmp_path / "handoff"
    with pytest.raises(ValueError):
        deliver_source(root, man, str(dest), "test-pitcher", "RID", exclude={1: "x", 2: "y"})
    assert not (dest / "test-pitcher" / "RID_vid1").exists()
    deliver_source(root, man, str(dest), "test-pitcher", "RID")
    with pytest.raises(FileExistsError):
        deliver_source(root, man, str(dest), "test-pitcher", "RID")
    assert len((dest / "index.jsonl").read_text(encoding="utf-8").splitlines()) == 1
