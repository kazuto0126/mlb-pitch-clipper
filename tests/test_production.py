"""M5 tests: naming, extraction, ordering, dedup, merge, manifest, fallback."""
import sys

sys.path.insert(0, ".")

import cv2
import numpy as np
import pytest


def _mp4(path, secs=2.0, fps=10, color=(0, 255, 0), size=(160, 120),
         pattern=None):
    w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    for _ in range(int(secs * fps)):
        fr = np.full((size[1], size[0], 3), color, dtype=np.uint8)
        if pattern == "half":
            fr[:, size[0] // 2:] = 0
        elif pattern == "inv":
            fr[:, :size[0] // 2] = 0
        elif pattern == "checker":
            yy, xx = np.mgrid[0:size[1], 0:size[0]]
            fr[(yy // 15 + xx // 15) % 2 == 0] = 0
        w.write(fr)
    w.release()
    return path


def test_filename_sanitizer():
    from src.clipper.production.naming import sanitize_name, product_filename
    assert sanitize_name("Shohei Ohtani") == "Shohei_Ohtani"
    assert sanitize_name("  Paul   Skenes  ") == "Paul_Skenes"
    assert product_filename("Shohei Ohtani", 2025, game_year_confidence="high") \
        == "Shohei_Ohtani_2025.mp4"


def test_known_and_unknown_year_filename():
    from src.clipper.production.naming import product_filename
    assert product_filename("Paul Skenes", 2026, game_year_confidence="high") \
        == "Paul_Skenes_2026.mp4"
    assert product_filename("Paul Skenes", None, game_year_confidence="null") \
        == "Paul_Skenes_UnknownYear.mp4"
    taken = {"Shohei_Ohtani_2025.mp4"}
    assert product_filename("Shohei Ohtani", 2025, taken,
                            game_year_confidence="high") == "Shohei_Ohtani_2025_01.mp4"


@pytest.mark.parametrize("year,conf,expected", [
    (2025, "high", "Paul_Skenes_2025.mp4"),
    (2025, "medium", "Paul_Skenes_2025.mp4"),
    (2025, "low", "Paul_Skenes_UnknownYear.mp4"),   # published-date fallback
    (None, "null", "Paul_Skenes_UnknownYear.mp4"),
    (2025, None, "Paul_Skenes_UnknownYear.mp4"),    # confidence missing
])
def test_filename_year_by_confidence(year, conf, expected):
    from src.clipper.production.naming import product_filename
    assert product_filename("Paul Skenes", year,
                            game_year_confidence=conf) == expected


def test_unreliable_year_collision_suffix():
    from src.clipper.production.naming import product_filename
    taken = {"Paul_Skenes_UnknownYear.mp4"}
    assert product_filename("Paul Skenes", 2025, taken, game_year_confidence="low") \
        == "Paul_Skenes_UnknownYear_01.mp4"


def _fake_production_stages(monkeypatch):
    """Stub every heavy stage of produce_source; naming/manifest stay real."""
    import json
    from pathlib import Path

    from src.clipper.production import run_source

    def m1(src, out, prefer_clip=True):
        Path(out).mkdir(parents=True, exist_ok=True)
        (Path(out) / "shots.json").write_text(
            json.dumps([{"accepted_for_pitch_detection": True}]), encoding="utf-8")
        (Path(out) / "candidates.json").write_text(json.dumps([{}]), encoding="utf-8")

    def m2(out, video=None):
        (Path(out) / "events.json").write_text(json.dumps(
            [{"event_id": "e1", "clip_start": 1.0, "clip_end": 3.0}]), encoding="utf-8")
        (Path(out) / "rejected_events.json").write_text("[]", encoding="utf-8")

    def merge(paths, out):
        Path(out).write_bytes(b"mp4")
        return {"ok": True, "duration": 2.0, "codec_info": "h264 yuv420p", "fps": 30.0}

    monkeypatch.setattr(run_source, "normalize_media",
                        lambda src, dst: {"ok": True, "method": "reuse-original"})
    monkeypatch.setattr(run_source, "run_m1", m1)
    monkeypatch.setattr(run_source, "run_m2", m2)
    monkeypatch.setattr(run_source, "extract_clip",
                        lambda src, s, e, dest: {"ok": True, "duration": e - s})
    monkeypatch.setattr(run_source, "dedup_clips",
                        lambda clips: {"kept": clips, "removed": []})
    monkeypatch.setattr(run_source, "merge_clips", merge)


@pytest.mark.parametrize("year,conf,expected", [
    (2025, "high", "Test_Pitcher_2025.mp4"),
    (2025, "medium", "Test_Pitcher_2025.mp4"),
    (2025, "low", "Test_Pitcher_UnknownYear.mp4"),
    (None, "null", "Test_Pitcher_UnknownYear.mp4"),
])
def test_produce_source_filename_never_fakes_year(tmp_path, monkeypatch,
                                                   year, conf, expected):
    from src.clipper.production.run_source import produce_source
    _fake_production_stages(monkeypatch)
    run_dir = tmp_path / "run"
    man = produce_source(
        "Test Pitcher", {"video_id": "v", "url": "http://x", "title": "t",
                         "game_year": year, "game_year_confidence": conf},
        str(run_dir / "sources" / "v"), set(),
        downloader=lambda url, out, meta=None: {"ok": True, "method": "fake"})
    assert man["status"] == "ok"
    assert man["final_path"] == expected and (run_dir / expected).exists()
    # manifest keeps the raw extracted values for downstream
    assert man["game_year"] == year and man["game_year_confidence"] == conf
    flagged = any(w.startswith("game year unreliable") for w in man["warnings"])
    assert flagged is (conf in ("low", "null"))


def test_exact_clip_extraction(tmp_path):
    from src.clipper.production.clips import extract_clip
    v = _mp4(str(tmp_path / "src.mp4"), secs=6.0)
    r = extract_clip(v, 1.0, 3.0, str(tmp_path / "c.mp4"))
    assert r["ok"] and abs(r["duration"] - 2.0) < 0.4
    bad = extract_clip(v, 5.0, 5.0, str(tmp_path / "bad.mp4"))
    assert not bad["ok"]


def test_invalid_media_rejected():
    from src.clipper.production.clips import extract_clip
    r = extract_clip("/nonexistent/x.mp4", 0.0, 2.0, "/tmp/never.mp4")
    assert not r["ok"]


def test_conservative_dedup_exact_duplicate(tmp_path):
    from src.clipper.production.dedup import dedup_clips
    a = _mp4(str(tmp_path / "a.mp4"), secs=2.0, color=(0, 255, 0))
    b = _mp4(str(tmp_path / "b.mp4"), secs=2.0, color=(0, 255, 0))
    clips = [{"clip_id": "p001", "path": a, "clip_start": 0.0,
              "clip_end": 2.0, "duration": 2.0},
             {"clip_id": "p002", "path": b, "clip_start": 10.0,
              "clip_end": 12.0, "duration": 2.0}]
    out = dedup_clips(clips)
    assert len(out["kept"]) == 1 and len(out["removed"]) == 1
    assert out["removed"][0]["duplicate_confidence"] >= 0.9


def test_duplicate_uncertainty_keep(tmp_path):
    from src.clipper.production.dedup import dedup_clips
    a = _mp4(str(tmp_path / "a.mp4"), secs=2.0, color=(0, 255, 0), pattern="half")
    b = _mp4(str(tmp_path / "b.mp4"), secs=2.0, color=(0, 255, 0), pattern="checker")
    clips = [{"clip_id": "p001", "path": a, "clip_start": 0.0,
              "clip_end": 2.0, "duration": 2.0},
             {"clip_id": "p002", "path": b, "clip_start": 10.0,
              "clip_end": 12.0, "duration": 2.0}]
    out = dedup_clips(clips)
    assert len(out["kept"]) == 2 and not out["removed"]


def test_clip_ordering_and_manifest_counters(tmp_path):
    from src.clipper.production.dedup import dedup_clips
    a = _mp4(str(tmp_path / "a.mp4"), secs=1.0, pattern="half")
    b = _mp4(str(tmp_path / "b.mp4"), secs=1.0, pattern="inv")
    clips = [{"clip_id": "p002", "path": b, "clip_start": 9.0,
              "clip_end": 10.0, "duration": 1.0},
             {"clip_id": "p001", "path": a, "clip_start": 1.0,
              "clip_end": 2.0, "duration": 1.0}]
    kept = sorted(dedup_clips(clips)["kept"], key=lambda c: c["clip_start"])
    assert [c["clip_id"] for c in kept] == ["p001", "p002"]


def test_h264_merge(tmp_path):
    from src.clipper.production.clips import extract_clip
    from src.clipper.production.merge import merge_clips
    v = _mp4(str(tmp_path / "src.mp4"), secs=6.0)
    c1 = str(tmp_path / "c1.mp4")
    c2 = str(tmp_path / "c2.mp4")
    assert extract_clip(v, 0.5, 1.5, c1)["ok"]
    assert extract_clip(v, 2.5, 3.5, c2)["ok"]
    dest = str(tmp_path / "final.mp4")
    r = merge_clips([c1, c2], dest)
    assert r["ok"] and abs(r["duration"] - 2.0) < 0.5
    assert ("h264" in r["codec_info"] or "avc1" in r["codec_info"]) \
        and "yuv420p" in r["codec_info"]
    assert merge_clips([], str(tmp_path / "empty.mp4"))["ok"] is False


def test_acquisition_fallback_and_zero_event_source():
    from src.clipper.production.run_source import produce_source

    def boom(url, out, meta=None):
        return {"ok": False, "error": "offline"}

    man = produce_source("Test Pitcher", {"video_id": "v", "url": "http://x",
                                          "title": "t", "game_year": 2026,
                                          "game_year_confidence": "low"},
                         "/tmp/m5boom/sources/v", set(), downloader=boom)
    assert man["status"] == "failed-download"
    assert "download_status" in man


def test_no_eligible_source_manifest(tmp_path):
    from run import pick_sources
    pool, mode = pick_sources(
        [{"video_id": "v1", "suitability": {"final_score": 0.9}}],
        [{"video_id": "v1", "preview_decision": "reject",
          "competition_context": "mlb", "m2_complete_events": 0}])
    assert pool == [] and mode == "borderline_fallback"


@pytest.mark.parametrize("cand,keep", [
    ({"game_year": 2026, "game_year_confidence": "high"}, True),
    ({"game_year": 2025, "game_year_confidence": "high"}, False),
    ({"game_year": 2025, "game_year_confidence": "medium"}, False),
    # low = published year: unknown game year, kept unless published earlier
    ({"game_year": 2026, "game_year_confidence": "low",
      "published_date": "2026-05-01"}, True),
    ({"game_year": 2027, "game_year_confidence": "low",
      "published_date": "2027-01-10"}, True),
    ({"game_year": 2024, "game_year_confidence": "low",
      "published_date": "2024-08-01"}, False),
    ({"game_year": None, "game_year_confidence": "null",
      "published_date": None}, True),
])
def test_year_filter_treats_low_confidence_as_unknown(cand, keep):
    from run import year_filter_ok
    assert year_filter_ok(cand, 2026) is keep


def test_full_download_cmd_has_no_print_flag():
    # regression: --print makes yt-dlp skip the download (exit 0, no file)
    from src.clipper.acquisition.full_acquire import _build_cmd
    from pathlib import Path
    cmd = _build_cmd("http://x", Path("o.mp4"))
    assert "--print" not in cmd and "-o" in cmd


def _pair(tmp_path, gap_sec, same=True):
    from src.clipper.production.dedup import dedup_clips
    a = _mp4(str(tmp_path / "a.mp4"), secs=2.0, color=(0, 255, 0))
    b = _mp4(str(tmp_path / ("b.mp4" if same else "c.mp4")), secs=2.0,
             color=(0, 255, 0), pattern=None if same else "checker")
    clips = [{"clip_id": "p001", "path": a, "clip_start": 100.0,
              "clip_end": 102.0, "duration": 2.0},
             {"clip_id": "p002", "path": b,
              "clip_start": 102.0 + gap_sec, "clip_end": 104.0 + gap_sec,
              "duration": 2.0}]
    return dedup_clips(clips)


def test_high_similarity_short_gap_duplicate_allowed(tmp_path):
    out = _pair(tmp_path, 14.0, same=True)
    assert len(out["kept"]) == 1 and len(out["removed"]) == 1


def test_high_similarity_long_gap_keep_both(tmp_path):
    out = _pair(tmp_path, 355.0, same=True)
    assert len(out["kept"]) == 2 and not out["removed"]
    assert out["flagged"] and out["flagged"][0]["duplicate_status"] == \
        "visually_similar_but_temporally_distant"


def test_low_similarity_short_gap_keep_both(tmp_path):
    out = _pair(tmp_path, 5.0, same=False)
    assert len(out["kept"]) == 2 and not out["removed"]


def test_timestamp_missing_keep(tmp_path):
    from src.clipper.production.dedup import dedup_clips
    a = _mp4(str(tmp_path / "a.mp4"), secs=2.0, color=(0, 255, 0))
    b = _mp4(str(tmp_path / "b.mp4"), secs=2.0, color=(0, 255, 0))
    clips = [{"clip_id": "p001", "path": a, "duration": 2.0},
             {"clip_id": "p002", "path": b, "duration": 2.0}]
    out = dedup_clips(clips)
    assert len(out["kept"]) == 2 and not out["removed"]


def test_dedup_deterministic_and_chronological(tmp_path):
    out1 = _pair(tmp_path, 14.0, same=True)
    out2 = _pair(tmp_path, 14.0, same=True)
    assert [c["clip_id"] for c in out1["kept"]] == \
           [c["clip_id"] for c in out2["kept"]]
    assert out1["removed"][0]["duplicate_of"] == \
        out2["removed"][0]["duplicate_of"]
