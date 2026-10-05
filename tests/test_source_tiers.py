"""M7.3 tests: tiered source fallback (recommended -> borderline ->
insufficient-evidence), full-run yield acceptance, zero-CF robustness."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, ".")


def _rep(vid, decision, evidence=None, cf=3, events=0, comp="mlb", status="ok"):
    return {"video_id": vid, "preview_decision": decision, "evidence_state": evidence,
            "center_field_shots": cf, "m2_complete_events": events,
            "competition_context": comp, "preview_status": status}


def _src(vid, score=0.5):
    return {"video_id": vid, "url": f"http://x/{vid}", "suitability": {"final_score": score}}


def test_tiers_order_and_vetoes():
    from run import pick_sources
    selected = [_src(v) for v in ("rec", "bord", "ins", "bad", "zero", "nonmlb", "fail")]
    reports = [
        _rep("rec", "recommended", "sufficient_good", events=3),
        _rep("bord", "borderline", "sufficient_good", events=1),
        _rep("ins", "reject", "insufficient", cf=4),
        _rep("bad", "reject", "sufficient_bad", cf=9),        # evidence of bad
        _rep("zero", "reject", "insufficient", cf=0),         # no CF at all
        _rep("nonmlb", "reject", "insufficient", comp="non_mlb"),
        _rep("fail", "reject", "insufficient", status="failed"),
    ]
    pool, mode = pick_sources(selected, reports)
    # sufficient_bad is the last-resort tier (M7.4); zero-CF / non-MLB /
    # failed previews are never tried
    assert [s["video_id"] for s in pool] == ["rec", "bord", "ins", "bad"]
    assert [s["source_selection_mode"] for s in pool] == [
        "recommended", "borderline_fallback", "insufficient_evidence_fallback",
        "bad_evidence_fallback"]
    assert mode == "recommended"


def test_every_tier_requires_few_clips():
    from run import pick_sources
    from src.clipper.production.manifest import FEW_CLIPS
    selected = [_src(v) for v in ("rec", "bord_ev", "bord_cf", "ins", "bad")]
    reports = [_rep("rec", "recommended", "sufficient_good", events=2),
               _rep("bord_ev", "borderline", "sufficient_good", events=1),
               _rep("bord_cf", "borderline", "sufficient_bad", cf=8, events=0),
               _rep("ins", "reject", "insufficient", cf=4),
               _rep("bad", "reject", "sufficient_bad", cf=9)]
    pool, _ = pick_sources(selected, reports)
    assert len(pool) == 5
    assert all(s["min_final_clips"] == FEW_CLIPS for s in pool)


def test_bad_evidence_fallback_warning():
    from src.clipper.production.manifest import build_warnings
    _, w = build_warnings({"source_selection_mode": "bad_evidence_fallback",
                           "game_year": 2025, "game_year_confidence": "high"})
    assert any("preview judged source bad" in s for s in w)


def test_insufficient_tier_ordered_by_preview_cf_then_score():
    from run import pick_sources
    selected = [_src("a", 0.9), _src("b", 0.1), _src("c", 0.5)]
    reports = [_rep("a", "reject", "insufficient", cf=1),
               _rep("b", "reject", "insufficient", cf=6),
               _rep("c", "reject", "insufficient", cf=6)]
    pool, mode = pick_sources(selected, reports)
    assert [s["video_id"] for s in pool] == ["c", "b", "a"]
    assert mode == "insufficient_evidence_fallback"


def _stub_stages(monkeypatch, n_events, n_cands=1):
    from src.clipper.production import run_source
    calls = {"m2": 0}

    def m1(src, out, prefer_clip=True):
        Path(out).mkdir(parents=True, exist_ok=True)
        (Path(out) / "shots.json").write_text(json.dumps(
            [{"accepted_for_pitch_detection": True}] * max(n_cands, 1)), encoding="utf-8")
        (Path(out) / "candidates.json").write_text(json.dumps([{}] * n_cands), encoding="utf-8")

    def m2(out, video=None):
        calls["m2"] += 1
        assert n_cands > 0, "M2 must not run without candidates"
        (Path(out) / "events.json").write_text(json.dumps(
            [{"event_id": f"e{i}", "clip_start": 10.0 * i, "clip_end": 10.0 * i + 3}
             for i in range(n_events)]), encoding="utf-8")
        (Path(out) / "rejected_events.json").write_text("[]", encoding="utf-8")

    def merge(paths, out):
        Path(out).write_bytes(b"mp4")
        return {"ok": True, "duration": 3.0 * len(paths), "codec_info": "h264", "fps": 30.0}

    monkeypatch.setattr(run_source, "normalize_media", lambda s, d: {"ok": True, "method": "x"})
    monkeypatch.setattr(run_source, "run_m1", m1)
    monkeypatch.setattr(run_source, "run_m2", m2)
    monkeypatch.setattr(run_source, "extract_clip",
                        lambda src, s, e, dest: {"ok": True, "duration": e - s})
    monkeypatch.setattr(run_source, "dedup_clips", lambda c: {"kept": c, "removed": []})
    monkeypatch.setattr(run_source, "merge_clips", merge)
    return calls


def _produce(tmp_path, **kw):
    from src.clipper.production.run_source import produce_source
    run_dir = tmp_path / "run"
    man = produce_source("Test Pitcher", {"video_id": "v", "url": "http://x", "title": "t",
                                          "game_year": 2025, "game_year_confidence": "high",
                                          "source_selection_mode": kw.pop("mode", "recommended")},
                         str(run_dir / "sources" / "v"), set(),
                         downloader=lambda u, o, m=None: {"ok": True, "method": "fake"}, **kw)
    return man, run_dir


def test_low_yield_rejected_when_minimum_required(tmp_path, monkeypatch):
    _stub_stages(monkeypatch, n_events=2)
    man, run_dir = _produce(tmp_path, min_final_clips=3,
                            mode="insufficient_evidence_fallback")
    assert man["status"] == "low-yield" and man["final_clip_count"] == 2
    assert "final_path" not in man and not list(run_dir.glob("*.mp4"))
    assert any("required; source not used" in w for w in man["warnings"])
    assert any("insufficient preview evidence" in w for w in man["warnings"])


def test_minimum_met_or_default_produces(tmp_path, monkeypatch):
    _stub_stages(monkeypatch, n_events=3)
    man, run_dir = _produce(tmp_path, min_final_clips=3)
    assert man["status"] == "ok" and (run_dir / man["final_path"]).exists()


def test_default_minimum_keeps_single_clip_behavior(tmp_path, monkeypatch):
    _stub_stages(monkeypatch, n_events=1)
    man, _ = _produce(tmp_path)
    assert man["status"] == "ok" and man["final_clip_count"] == 1


def test_zero_cf_candidates_is_no_usable_clips_not_crash(tmp_path, monkeypatch):
    calls = _stub_stages(monkeypatch, n_events=0, n_cands=0)
    man, _ = _produce(tmp_path)
    assert man["status"] == "no-usable-clips" and calls["m2"] == 0
    assert man["center_field_candidates"] == 0 and man["complete_events"] == 0


def test_full_game_and_non_mlb_never_produce(monkeypatch):
    import run
    monkeypatch.setattr(run, "classify_competition",
                        lambda t, d, c: "non_mlb" if "WBC" in t else "mlb")
    assert run.production_exclusion({"title": "x", "source_type": "full_game"}) \
        .startswith("full_game")
    assert run.production_exclusion({"title": "WBC final", "source_type": "every_pitch"}) \
        == "non_mlb"
    for t in ("every_pitch", "full_start", "full_outing", "pitching_highlights"):
        assert run.production_exclusion({"title": "x", "source_type": t}) is None


def test_run_chain_refills_after_exclusions(tmp_path, monkeypatch):
    import run
    selected = [dict(_src("game"), source_type="full_game", title="FULL GAME"),
                dict(_src("a"), source_type="every_pitch", title="a"),
                dict(_src("b"), source_type="full_start", title="b"),
                dict(_src("c"), source_type="every_pitch", title="c"),
                dict(_src("d"), source_type="every_pitch", title="d")]
    asked, previewed = {}, {}

    def fake_discovery(name, out_root, top_n, run_id):
        asked["top_n"] = top_n
        d = Path(out_root) / "d"
        d.mkdir(parents=True, exist_ok=True)
        (d / "selected_sources.json").write_text(json.dumps(selected[:top_n]), encoding="utf-8")
        return {"out_dir": str(d)}

    def fake_preview(slug, sel_path, out_root, max_sources, run_id):
        previewed["ids"] = [s["video_id"] for s in json.loads(Path(sel_path).read_text(encoding="utf-8"))]
        d = Path(out_root) / "p"
        d.mkdir(parents=True, exist_ok=True)
        (d / "source_preview_report.json").write_text("[]", encoding="utf-8")
        return {"out_dir": str(d)}

    monkeypatch.setattr(run, "run_discovery", fake_discovery)
    monkeypatch.setattr(run, "run_preview", fake_preview)
    monkeypatch.setattr(run, "classify_competition", lambda *a: "mlb")
    root = tmp_path / "out" / "p" / "rid"
    (root / "sources").mkdir(parents=True)
    run._run_chain(SimpleNamespace(pitcher="P", top_n=3, max_sources=3, year=None,
                                   out_root=str(tmp_path / "out")), "rid", root)
    m = json.loads((root / "run_manifest.json").read_text(encoding="utf-8"))
    assert asked["top_n"] == 6
    assert previewed["ids"] == ["a", "b", "c"]  # full game dropped, refilled
    assert list(m["discovery"]["excluded"]) == ["game"]


def test_run_chain_falls_through_tiers_and_enforces_minimum(tmp_path, monkeypatch):
    import run
    selected = [_src("bord"), _src("ins_low"), _src("ins_good")]
    reports = [_rep("bord", "borderline", "sufficient_bad", cf=8),
               _rep("ins_low", "reject", "insufficient", cf=5),
               _rep("ins_good", "reject", "insufficient", cf=2)]

    def fake_discovery(name, out_root, top_n, run_id):
        d = Path(out_root) / "d"
        d.mkdir(parents=True, exist_ok=True)
        (d / "selected_sources.json").write_text(json.dumps(selected), encoding="utf-8")
        return {"out_dir": str(d)}

    def fake_preview(slug, sel_path, out_root, max_sources, run_id):
        d = Path(out_root) / "p"
        d.mkdir(parents=True, exist_ok=True)
        (d / "source_preview_report.json").write_text(json.dumps(reports), encoding="utf-8")
        return {"out_dir": str(d)}

    yields = {"bord": ("no-usable-clips", 0), "ins_low": ("low-yield", 2),
              "ins_good": ("ok", 4)}
    seen = []

    def fake_produce(pitcher, cand, sdir, taken, min_final_clips=1):
        seen.append((cand["video_id"], min_final_clips))
        st, n = yields[cand["video_id"]]
        man = {"video_id": cand["video_id"], "status": st, "final_clip_count": n,
               "source_selection_mode": cand["source_selection_mode"]}
        if st == "ok":
            man["final_path"] = "Test_Pitcher_2025.mp4"
        return man

    monkeypatch.setattr(run, "run_discovery", fake_discovery)
    monkeypatch.setattr(run, "run_preview", fake_preview)
    monkeypatch.setattr(run, "produce_source", fake_produce)
    monkeypatch.setattr(run, "classify_competition", lambda *a: "mlb")
    root = tmp_path / "out" / "test-pitcher" / "rid"
    (root / "sources").mkdir(parents=True)
    args = SimpleNamespace(pitcher="Test Pitcher", top_n=3, max_sources=3, year=None,
                           out_root=str(tmp_path / "out"))
    run._run_chain(args, "rid", root)
    m = json.loads((root / "run_manifest.json").read_text(encoding="utf-8"))
    # borderline first; it and the insufficient tier saw no preview event,
    # so each must reach FEW_CLIPS (3) in the full run
    assert seen == [("bord", 3), ("ins_low", 3), ("ins_good", 3)]
    assert m["status"] == "ok" and m["finals"] == ["Test_Pitcher_2025.mp4"]
    assert m["source_selection_mode"] == "insufficient_evidence_fallback"
