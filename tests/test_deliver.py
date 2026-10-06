"""Hand-off folder tests (contract v1): layout, atomic index, integrity,
per-clip offsets, immutability, and run-chain wiring."""
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, ".")


def _fake_run(tmp_path, vid="vid1", name="Test_Pitcher_2025.mp4"):
    root = tmp_path / "out" / "test-pitcher" / "RID"
    sdir = root / "sources" / vid
    sdir.mkdir(parents=True)
    (root / name).write_bytes(b"fake-mp4-bytes")
    kept = [{"clip_id": "p002", "clip_start": 50.0, "clip_end": 53.5, "duration": 3.5},
            {"clip_id": "p001", "clip_start": 10.0, "clip_end": 12.0, "duration": 2.0},
            {"clip_id": "p003", "clip_start": 90.0, "clip_end": 94.0, "duration": 4.0}]
    (sdir / "dedup.json").write_text(json.dumps({"kept": kept, "removed": []}), encoding="utf-8")
    man = {"status": "ok", "video_id": vid, "pitcher_name": "Test Pitcher",
           "final_path": name, "final_clip_count": 3, "final_duration_sec": 9.5,
           "game_year": 2025, "game_year_confidence": "high", "source_title": "t",
           "source_url": "http://x", "channel": "c", "source_type": "every_pitch",
           "quality_warning": False, "warnings": []}
    return root, man


def test_delivery_layout_integrity_and_offsets(tmp_path):
    from src.clipper.production.deliver import deliver_source
    root, man = _fake_run(tmp_path)
    dest = tmp_path / "handoff"
    line = deliver_source(root, man, str(dest), "test-pitcher", "RID")
    ddir = dest / "test-pitcher" / "RID_vid1"
    video = ddir / "Test_Pitcher_2025.mp4"
    rec = json.loads((ddir / "delivery.json").read_text(encoding="utf-8"))
    assert video.read_bytes() == b"fake-mp4-bytes"
    assert rec["sha256"] == hashlib.sha256(b"fake-mp4-bytes").hexdigest()
    assert rec["contract_version"] == 1 and rec["final_clip_count"] == 3
    # chronological, cumulative offsets inside the merged video
    assert [(c["start_sec"], c["end_sec"], c["source_start_sec"]) for c in rec["clips"]] == [
        (0.0, 2.0, 10.0), (2.0, 5.5, 50.0), (5.5, 9.5, 90.0)]
    idx = [json.loads(l) for l in (dest / "index.jsonl").read_text(encoding="utf-8").splitlines()]
    assert idx == [line] and line["video"] == "test-pitcher/RID_vid1/Test_Pitcher_2025.mp4"
    assert not list(dest.rglob("*.tmp"))


def test_deliveries_are_immutable_and_appended(tmp_path):
    from src.clipper.production.deliver import deliver_source
    root, man = _fake_run(tmp_path)
    dest = tmp_path / "handoff"
    deliver_source(root, man, str(dest), "test-pitcher", "RID1")
    first = (dest / "test-pitcher" / "RID1_vid1" / "delivery.json").read_text(encoding="utf-8")
    deliver_source(root, man, str(dest), "test-pitcher", "RID2")
    assert (dest / "test-pitcher" / "RID1_vid1" / "delivery.json").read_text(encoding="utf-8") == first
    ids = [json.loads(l)["delivery_id"] for l in (dest / "index.jsonl").read_text(encoding="utf-8").splitlines()]
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

    def fake_produce(pitcher, cand, sdir, taken, min_final_clips=1):
        man = _fake_run(tmp_path / f"src{len(list(tmp_path.glob('src*')))}", vid="vid1")[1]
        Path(sdir).mkdir(parents=True, exist_ok=True)
        (Path(sdir) / "dedup.json").write_text(json.dumps({"kept": [], "removed": []}),
                                               encoding="utf-8")
        (Path(sdir).parent.parent / man["final_path"]).write_bytes(b"v")
        return man

    monkeypatch.setattr(run, "run_discovery", fake_discovery)
    monkeypatch.setattr(run, "run_preview", fake_preview)
    monkeypatch.setattr(run, "produce_source", fake_produce)
    monkeypatch.setattr(run, "classify_competition", lambda *a: "mlb")
    for deliver_to in (None, str(tmp_path / "handoff")):
        root = tmp_path / "out" / "test-pitcher" / ("A" if deliver_to is None else "B")
        (root / "sources").mkdir(parents=True)
        run._run_chain(SimpleNamespace(pitcher="Test Pitcher", top_n=3, max_sources=3, year=None,
                                       out_root=str(tmp_path / "out"), deliver_to=deliver_to),
                       root.name, root)
        m = json.loads((root / "run_manifest.json").read_text(encoding="utf-8"))
        assert m["status"] == "ok"
        assert ("deliveries" in m) is (deliver_to is not None)
    assert (tmp_path / "handoff" / "index.jsonl").exists()
