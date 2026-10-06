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

## HAND-OFF FOLDER (contract_version 1) — the only shared surface

The two projects share no code and no repository. The producer writes
finished videos into a hand-off folder outside both repos; the consumer
only reads it.

```bash
python run.py "Mason Miller" --deliver-to D:/project/pitch-video-handoff
```

```
<handoff>/
  index.jsonl                               one JSON line per delivery
  <pitcher-slug>/<delivery_id>/
    <Pitcher_Name>_<Game_Year>.mp4
    delivery.json
```

`index.jsonl` line: `delivery_id, pitcher_name, contract_version, video,
delivery_json, created_utc` (paths relative to the hand-off root).

`delivery.json`:

```
contract_version, delivery_id, created_utc, pitcher_name,
video_file, sha256, final_clip_count, final_duration_sec,
game_year, game_year_confidence,
source {video_id, title, url, channel, source_type},
quality_warning, warnings[],
clips [{index, start_sec, end_sec, source_start_sec, source_end_sec}]
```

`clips[].start_sec/end_sec` locate each pitch inside the delivered video
(cumulative clip durations, ±1 frame); `source_*` are times in the
original YouTube video.

Rules for the consumer:
- Discover deliveries ONLY through `index.jsonl`. A line is appended after
  the video and `delivery.json` are fully written (temp file + rename), so
  every listed delivery is complete. Remember processed `delivery_id`s.
- Treat the folder as read-only. Never write, rename or delete in it.
- Verify `sha256` before use; reject unknown `contract_version`s.
- Deliveries are immutable: a re-run of the same pitcher appears as a new
  `delivery_id`; nothing is overwritten.
- Never read the producer's `output/` folder or import its code.

## No guarantees beyond this file

Clip count varies by source (precision > recall). A small number of
replays may remain. Tightly edited broadcasts may lose pitches.
