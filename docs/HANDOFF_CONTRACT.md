# 交付規格 CONTRACT（contract_version 2）

供片專案（mlb-pitch-clipper）與分析專案之間唯一的介面。本檔由供片端維護，
每次交付時複製到交付資料夾根目錄的 `CONTRACT.md`。分析端只需要讀這份檔案，
不需要、也不應該讀取供片專案的程式碼或內部資料夾。

## 資料夾結構

```
<handoff>/
  CONTRACT.md                         本規格
  index.jsonl                         每行一個批次，最後才追加
  <pitcher-slug>/<batch_id>/
    batch.json                        批次說明
    <pitch_id>.mp4                    一顆完整投球（一檔一球）
    <pitch_id>.json                   與 MP4 配對的單球說明
    viewing/<Pitcher_Name>_<Game_Year>.mp4   多球合併，僅供觀看，不作分析輸入
```

- 一個批次 = 一個來源影片產出的所有合格單球。`batch_id` = `<run_id>_<source video_id>`，
  `pitch_id` = `<batch_id>_pNN`，全域唯一。
- 檔案先寫成暫存檔再改名；`index.jsonl` 的該行在批次所有檔案完成後才追加。
  依 `index.jsonl` 讀取就不會讀到不完整的批次。
- 批次交付後內容固定，永不覆寫或刪除；更新一律以新批次提供。

## index.jsonl（每行）

`batch_id, pitcher_name, contract_version, pitch_count, batch_json, created_utc`
（路徑皆相對於交付資料夾根目錄）

## 單球 MP4

- H.264、yuv420p、MP4；正常速度、保留來源原始每秒格數，不補影格、不放大。
  來源解析度上限 720p（不放大、不裁切）。可能含聲音，聲音不保證、也不需使用。
- 一檔一球；從檔案第 0 格起算。起點：動作開始前約 2 秒（站定／準備）；
  終點：動作平息後約 1.5 秒（收尾）。兩端都不跨出同一個連續鏡頭，
  也不跨入同一鏡頭中的另一顆球；所以鏡頭較短時前後保留會比較少。
- 視角只有 `rear_centerfield_broadcast`（中外野後方轉播鏡位）。
- 每檔 ≤ 30 秒。每批次至少 3 顆球。

## 單球 JSON（<pitch_id>.json）

| 欄位 | 說明 |
|---|---|
| `contract_version` | 2 |
| `pitch_id`, `batch_id`, `index` | 識別；`index` 為批次內時間順序 |
| `pitcher_name` | 搜尋時指定的投手英文名 |
| `throws` | `R` / `L` / `unknown`；由操作者提供，不從畫面推測 |
| `view` | `rear_centerfield_broadcast` |
| `video_file`, `sha256` | 配對的 MP4 與其 SHA-256 |
| `video` | 由檔案本身讀出：`fps`（分數字串）、`fps_float`、`constant_frame_rate`、`frame_count`、`duration_sec`、`width`、`height`、`codec`、`pix_fmt`、`square_pixels`、`container_start_time_sec`、`frame_time_rule`、`has_audio` |
| `source` | `video_id, title, url, channel, source_type, start_sec, end_sec`（本球在原始影片中的起訖秒數） |
| `game` | `season`（僅高／中信心年份，否則 `unknown`）、`season_confidence`、`team`、`opponent`、`game_id`、`pitch_type`（目前皆 `unknown`，不從標題猜測） |
| `pipeline_anchors_sec` | `motion_onset`、`motion_peak`、`settle`：相對第 0 格的動作能量錨點，**不是**生物力學事件（不代表出手、前腳落地） |
| `checks` | 每項 `{status, how}`；`status` 為 `verified_by_pipeline` 或 `not_verified` |
| `requires_human_review` | 所有 `not_verified` 的項目 |

`checks` 的內容：

| 項目 | status | 說明 |
|---|---|---|
| `single_motion_event` | verified_by_pipeline | 一個完整動作事件；邊界不跨入同鏡頭的其他事件 |
| `pitch_delivery_visible` | **not_verified** | 動作偵測可能被捕手／打者的動作觸發，而投手其實沒有投球 |
| `continuous_shot` | verified_by_pipeline | 在一個偵測到的鏡頭內（結尾與偵測切點保持 0.25 秒以上），經過轉場檢查，交付檔並逐格掃描確認沒有硬切 |
| `view_rear_centerfield` | verified_by_pipeline | 視角分類＋特寫排除＋同來源構圖一致性 |
| `normal_speed_export` | verified_by_pipeline | 輸出不變速、保留原格率、不補格 |
| `not_replay_or_slow_motion` | **not_verified** | 重播偵測保守，可能殘留慢動作重播 |
| `not_mirrored` | **not_verified** | 無自動檢查 |
| `full_body_in_frame` | **not_verified** | 無自動檢查 |
| `pitcher_identity` | **not_verified** | 來源是以該投手為主的影片，但不做畫面身分辨識 |

## 時間

每格時間一律以 `t = frame_index / fps_float` 計算，第 0 格 = 0.0 秒；交付檔皆為固定格率
（`constant_frame_rate` 為 true）。`container_start_time_sec` 只是容器標記（編碼器常有約 1 格的偏移），
一般解碼器讀出的第 0 格仍在 0 秒，請勿用它平移時間。

## batch.json

`contract_version, batch_id, created_utc, pitcher_name, throws, view,
pitch_count, pitches[{pitch_id, video_file, json}], source, game,
viewing_video, excluded_by_operator[], quality_warning, warnings[]`

`excluded_by_operator`：供片端人工覆核後排除的球（原始順序、在來源中的起訖、原因）；
排除會留下紀錄，不會無聲消失。排除後不足 3 顆的批次不交付。同一個 `batch_id` 只會寫入一次。

## 分析端規則

- 只透過 `index.jsonl` 找新批次；自行記錄已處理的 `batch_id` / `pitch_id`。
- 交付資料夾唯讀：不寫入、不改名、不刪除。要標註或長期保存，先比對 `sha256`
  再複製到分析專案自己的資料夾。
- 遇到不認得的 `contract_version` 就拒收並記錄。
- `requires_human_review` 中的項目（特別是投手身分）須由人工確認後才可視為正式素材。
