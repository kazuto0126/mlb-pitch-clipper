# MLB Pitch Clipper — Release Candidate (v0.1.0-rc1)

## Product

Pitcher name → YouTube search → automatic source selection →
complete center-field pitching clips → condensed H.264 MP4.

## CLI

```bash
python run.py "Shohei Ohtani"
```

## Output

```
<Pitcher_Name>_<Game_Year>.mp4
```

H.264 / yuv420p, original speed, chronological, no cards/overlays.
`UnknownYear` when the game year cannot be determined reliably
(published year is never faked as game year): only high/medium
`game_year_confidence` years are used; low (published-date fallback) and
null become `UnknownYear`. The manifest keeps the raw `game_year` /
`game_year_confidence` and adds a `game year unreliable` warning.

## Known Limitations

- precision > recall: tightly edited broadcasts may lose pitches.
- Conservative replay/duplicate handling: a few replays may remain;
  false deletion is treated as worse than a missed duplicate.
- YouTube availability changes over time. Every delivered video keeps
  ≥3 clips; a source yielding fewer is not used (1–2 clip outputs were
  5/10 correct vs 59/67 for ≥3). Sources the preview rejected as too
  sparse or as bad are only tried last
  (`insufficient_evidence_fallback`, `bad_evidence_fallback`).
- Strict shot purity may reject usable events inside impure containers.
- An occasional wrong-view segment may still slip through (no perfect detection claimed).
- WBC/NPB/amateur/bullpen footage is excluded from production by default.
- Full-game broadcasts are excluded: both teams' pitchers appear and
  pitcher identity is out of scope. Pitchers covered only by full games
  get no output.

## Scope

Finding clean, complete, analyzable pitching video only.
Biomechanics / pose / pitch-type / velocity belong to downstream.
