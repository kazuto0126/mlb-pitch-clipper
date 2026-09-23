# MLB Pitch Clipper — acceptance_set_v1 (FROZEN)

> 人工標註只在 development / validation 使用。
> 正式 `python run.py "Pitcher Name"` 不得要求任何人工標註。

## 狀態
- `manifest.json`: `frozen: true`。永久凍結，之後不再修改。
- 新 failure cases 請放 `validation/regression_cases/`，不要改這裡。

## 設計目標
學「什麼畫面是適合分析的完整 MLB 投球鏡頭」，不是「某投手長什麼樣」。
特徵只依賴 broadcast framing / camera layout / shot continuity /
motion timing / mound visibility / scene type，不依賴投手身份。

## 建議組成 (每人 2-3 段 x 3-5 分鐘，不需整場)
- Shohei Ohtani — 右投 (Dodgers 主場轉播)
- Yoshinobu Yamamoto — 右投 (客場/季後賽，不同 graphic 包)
- Garrett Crochet — 左投 starter
- Mason Miller — 右投 reliever (多 close-up / replay)
- Tarik Skubal — 左投 starter (不同球場)
- Paul Skenes — 右投 starter (小市場轉播)

## 標註格式
`labels/<pitcher-slug>.jsonl`，每行一個 candidate shot：

```json
{"source_id": "ohtani_dodgers_20240615_a", "shot_id": "s012",
 "video_path": "original file name (optional)",
 "start": 123.4, "end": 131.2,
 "view": "center_field_good",
 "completeness": "full_pitch",
 "play_type": "live_pitch",
 "clip_start": 123.4, "release_time": 128.1, "clip_end": 131.2,
 "pitcher": "Shohei Ohtani", "broadcast_source": "ESPN",
 "game_year": 2024, "notes": ""}
```

### VIEW (7 類)
- `center_field_good`
- `side_fullbody_acceptable` (validation/diagnostic 用，production 預設不進 final.mp4)
- `closeup_bad`
- `batter_bad`
- `field_bad`
- `graphic_bad`
- `other_bad`

### COMPLETENESS
- `full_pitch` / `start_cut` / `end_cut` / `no_pitch`

### PLAY_TYPE
- `live_pitch` / `replay` / `slow_motion` / `duplicate`

目前此目錄先建立結構與格式，標註逐批補上，不阻塞 M1 pipeline 開發。
