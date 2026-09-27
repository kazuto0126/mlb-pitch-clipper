# Downstream Contract (v0.1.0-rc1)

This project outputs condensed pitching video for a separate analysis
project. Downstream MUST depend only on this contract, never on internals
(M1 confidence, M2 temporal thresholds, CLIP scores, preview gate).

## PRIMARY: video file

```
<Pitcher_Name>_<Game_Year>.mp4
```

- H.264 / avc1, yuv420p, original speed, chronological pitching clips.
- No title cards, no overlays, no biomechanics annotation.
- `UnknownYear` when the game year cannot be determined reliably
  (published year is never faked as game year).

## OPTIONAL METADATA: manifest.json

Per-source manifest provides at least:

```
pitcher_name, source video_id, source title,
game_year, game_year_confidence,
final_clip_count, final_duration_sec, final_path
```

Plus run-level `run_manifest.json` (status, finals, per-source results)
and `quality_summary` / `quality_warning` / `warnings[]`.

## No guarantees beyond this file

Clip count varies by source (precision > recall). A small number of
replays may remain. Tightly edited broadcasts may lose pitches.
