# Downstream Contract (v0.1.0-rc1)

This project outputs condensed pitching video for a separate analysis
project. Downstream MUST depend only on this contract, never on internals
(M1 confidence, M2 temporal thresholds, CLIP scores, preview gate).

## PRIMARY: video file

```
<Pitcher_Name>_<Game_Year>.mp4
```

- H.264 / avc1, yuv420p, original speed, chronological pitching clips.
- At least 3 clips per produced video (`final_clip_count >= 3`); a source
  that keeps fewer is not delivered (1–2 clip outputs were mostly wrong
  views).
- Sources are pitcher-centered edits (every pitch / full start / full
  outing / pitching highlights). Full-game broadcasts are never used: they
  show both teams' pitchers and pitcher identity is not verified.
- No title cards, no overlays, no biomechanics annotation.
- `UnknownYear` when the game year cannot be determined reliably
  (published year is never faked as game year): only high/medium
  `game_year_confidence` years are used; low and null become `UnknownYear`.

## OPTIONAL METADATA: manifest.json (producer-internal)

Consumers should use `delivery.json` from the hand-off folder below; the
per-source manifest under the producer's `output/` is internal. It
provides at least:

```
pitcher_name, source video_id, source title,
game_year, game_year_confidence,
final_clip_count, final_duration_sec, final_path
```

`game_year` is the raw extracted value and may be set even when the
filename says `UnknownYear` (low confidence = published-date fallback).

Plus run-level `run_manifest.json` (status, finals, per-source results)
and `quality_summary` / `quality_warning` / `warnings[]`.

## HAND-OFF FOLDER — the only shared surface

Deliveries go to a hand-off folder outside both repositories, one MP4 per
pitch plus a paired JSON (contract_version 2). The full specification is
`docs/HANDOFF_CONTRACT.md`; it is copied into the hand-off folder as
`CONTRACT.md` on every delivery, so the consumer never reads this repo.

```bash
python run.py "Yoshinobu Yamamoto" --throws R --deliver-to D:/project/pitch-video-handoff
python -m src.clipper.production.deliver --run output/<slug>/<run_id> --to <handoff> --throws R
```

The merged `<Pitcher_Name>_<Game_Year>.mp4` above is provided in each batch
under `viewing/` for viewing only; it is not an analysis input.

## No guarantees beyond this file

Clip count varies by source (precision > recall). A small number of
replays may remain. Tightly edited broadcasts may lose pitches.
