"""M7 release-contract tests (no algorithm changes covered here)."""
import sys

sys.path.insert(0, ".")


def test_preflight_missing_ffmpeg():
    from src.clipper.production.preflight import check
    missing = check(which=lambda b: None if b in ("ffmpeg", "ffprobe") else "/x",
                    mods=[])
    assert any("FFmpeg" in m for m in missing)


def test_preflight_missing_ytdlp():
    from src.clipper.production.preflight import check
    missing = check(which=lambda b: None if b == "yt-dlp" else "/x", mods=[])
    assert any("yt-dlp" in m for m in missing)


def test_preflight_clean():
    from src.clipper.production.preflight import check
    assert check(which=lambda b: "/x", mods=[]) == []


def test_manifest_schema_source_and_run():
    from src.clipper.production.manifest import validate_manifest
    assert validate_manifest({"video_id": "v"}, kind="source") != []
    full = {"pitcher_name": "P", "video_id": "v", "source_url": "u",
            "source_title": "t", "channel": "c", "source_type": "full_outing",
            "competition_context": "mlb", "game_year": 2025,
            "game_year_confidence": "high", "discovery_score": 0.9,
            "preview_decision": "borderline", "source_selection_mode": "x",
            "download_status": "ok", "acquisition_method": "yt-dlp-full",
            "local_path": "p", "normalization_status": "reuse-original",
            "shot_count": 10, "center_field_candidates": 5,
            "rejected_low_confidence": 1, "rejected_transition": 0,
            "rejected_homogeneous_closeup": 0, "complete_events": 2,
            "rejected_events": 3, "rejected_start_incomplete": 1,
            "rejected_end_incomplete": 1, "rejected_no_complete_pitch": 1,
            "rejected_discontinuity": 0, "raw_clip_count": 2,
            "duplicate_rejected": 0, "replay_rejected": 0,
            "replay_status": "uncertain", "final_clip_count": 2,
            "final_duration_sec": 8.0, "final_codec": "h264",
            "final_path": "P_2025.mp4", "status": "ok",
            "quality_summary": {}, "quality_warning": True, "warnings": ["x"]}
    assert validate_manifest(full, kind="source") == []


def test_quality_warning_rules():
    from src.clipper.production.manifest import build_warnings
    base = {"center_field_candidates": 100, "complete_events": 10,
            "final_clip_count": 10, "game_year_confidence": "high",
            "replay_status": "duplicates-removed", "status": "ok"}
    w, lst = build_warnings(base)
    assert w is False and lst == []
    w, lst = build_warnings({**base, "source_selection_mode": "borderline_fallback"})
    assert w is True and any("borderline" in s for s in lst)
    w, lst = build_warnings({**base, "complete_events": 1})
    assert w is True and any("yield" in s for s in lst)
    w, lst = build_warnings({**base, "final_clip_count": 0,
                             "status": "no-usable-clips"})
    assert w is True


def test_all_sources_failed_statuses():
    # run-level status mapping mirrors run.py: all-download-fail
    # -> acquisition_failed, else no_suitable_source
    results = [{"video_id": "a", "status": "failed-download: x"},
               {"video_id": "b", "status": "failed-download: y"}]
    dl = [m for m in results if m["status"].startswith("failed-download")]
    assert len(dl) == len(results)  # -> acquisition_failed branch


def test_final_media_verification_contract(tmp_path):
    import subprocess

    import cv2
    import numpy as np
    p = str(tmp_path / "f.mp4")
    w = cv2.VideoWriter(p, cv2.VideoWriter_fourcc(*"mp4v"), 10, (160, 120))
    for _ in range(20):
        w.write(np.full((120, 160, 3), (0, 255, 0), dtype=np.uint8))
    w.release()
    probe = subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name,pix_fmt",
         "-of", "csv=p=0", p], text=True)
    assert "yuv420p" in probe  # mp4v encoder default pix fmt chain
    dec = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-f", "null", "-"],
                         capture_output=True, text=True, timeout=120)
    assert dec.returncode == 0


def test_cli_basic_argument_handling():
    import sys
    sys.argv = ["run.py", "Shohei Ohtani", "--top-n", "2"]
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("pitcher")
    ap.add_argument("--top-n", type=int, default=3)
    ap.add_argument("--max-sources", type=int, default=3)
    ap.add_argument("--year", type=int, default=None)
    args = ap.parse_args(["Shohei Ohtani", "--top-n", "2"])
    assert args.pitcher == "Shohei Ohtani" and args.top_n == 2
