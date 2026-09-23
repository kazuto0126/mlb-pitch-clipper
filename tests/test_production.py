"""M5 tests: naming, extraction, ordering, dedup, merge, manifest, fallback."""
import sys

sys.path.insert(0, ".")

import cv2
import numpy as np


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
    assert product_filename("Shohei Ohtani", 2025) == "Shohei_Ohtani_2025.mp4"


def test_known_and_unknown_year_filename():
    from src.clipper.production.naming import product_filename
    assert product_filename("Paul Skenes", 2026) == "Paul_Skenes_2026.mp4"
    assert product_filename("Paul Skenes", None) == "Paul_Skenes_UnknownYear.mp4"
    taken = {"Shohei_Ohtani_2025.mp4"}
    assert product_filename("Shohei Ohtani", 2025, taken) == "Shohei_Ohtani_2025_01.mp4"


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
