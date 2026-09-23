# labels/ — 每位投手一個 .jsonl

檔名：`<pitcher-slug>.jsonl`，例 `shohei-ohtani.jsonl`。

欄位見上層 README。`clip_start/release_time/clip_end` 在 M1 可先留 null，
M2 (pitch temporal event) 才必填。

最小範例：
```json
{"source_id": "example_a", "shot_id": "s001", "start": 0.0, "end": 8.0, "view": "center_field_good", "completeness": null, "play_type": null, "clip_start": null, "release_time": null, "clip_end": null, "pitcher": "Example Pitcher", "broadcast_source": "MLB", "game_year": 2026, "notes": "template"}
```
