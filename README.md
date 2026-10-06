# MLB Pitch Clipper

輸入一位 MLB 投手的英文姓名，自動搜尋 YouTube，剪輯完整 center-field
投球 sequences，輸出濃縮 MP4 給 downstream analysis 使用。

本專案只回答「哪一段是乾淨、完整、適合分析的投球影片」，
不做投球 mechanics / pose / biomechanics 分析。

## Requirements

- Python 3.10+
- FFmpeg (ffmpeg + ffprobe on PATH)
- yt-dlp
- Python packages: `pip install -r requirements.txt`

`run.py` 起動前會自動做 pre-flight 檢查，缺東西會直接說明，不會跑到一半才 crash。

## Installation

```bash
pip install -r requirements.txt
```

## Basic Usage

```bash
python run.py "Shohei Ohtani"
```

正常使用只需要投手英文名。可選 flags：`--top-n 3`、`--max-sources 3`、
`--year 2026`。不需要手動提供 URL、選片、標 clips 或刪 replay。

交給下游專案：加 `--deliver-to <交付資料夾>`（放在兩個 repo 之外）與
`--throws R|L`（左右投由操作者提供）。每顆球一個 MP4＋配對 JSON，以批次寫入並
登記到 `index.jsonl`；規格見 `docs/HANDOFF_CONTRACT.md`（會複製到交付資料夾的
`CONTRACT.md`）。已產出的 run 也可事後交付：
`python -m src.clipper.production.deliver --run output/<slug>/<run_id> --to <資料夾> --throws R`。
兩專案只透過這個資料夾溝通。

## Example

```bash
python run.py "Yoshinobu Yamamoto"
# → output/yoshinobu-yamamoto/<run_id>/Yoshinobu_Yamamoto_2025.mp4
```

## Output

```
output/<pitcher-slug>/<run_id>/
  run_manifest.json          # 全輪狀態 + finals + per-source results
  <Pitcher>_<Year>.mp4       # 產品影片（H.264/yuv420p，時間排序）
  sources/<video_id>/
    source/original.mp4      # 下載原檔
    intermediate/            # normalize 檔
    shots.json / candidates.json / events.json / rejected_events.json
    clips/raw/               # 逐顆 clips
    dedup.json / final.mp4 / manifest.json
```

檔名：`<英文名>_<年份>.mp4`（同年撞名加 `_01`；只用 `game_year_confidence`
為 high/medium 的年份，low（上傳年份 fallback）/null 一律用 `UnknownYear`，
不用上傳年份假裝）。manifest 仍保留原始 `game_year` / `game_year_confidence`。

## Known Limitations（誠實版）

- precision > recall：寧可少收，不收半套。緊剪輯 broadcast 會漏掉一些投球。
- replay detection 保守（`replay_status=uncertain`），可能保留少量 replay；
  誤刪比漏刪更糟，故只刪高信心（視覺近似＋60秒內）。
- homogeneous 且高信心的誤判理論上仍可能漏網（罕見）。
- impure mega-shot 可能因 precision 政策整段拒絕（含其中的真投球）。
- YouTube availability 隨時間改變；WBC/NPB/業餘/bullpen 預設不進 production。

## Troubleshooting

- `FFmpeg not found`：安裝 FFmpeg 並加到 PATH（本工具不修改系統）。
- `yt-dlp not found`：`pip install yt-dlp`。
- 單支影片失敗會自動 fallback 下一支；全滅時產生 `no_suitable_source` /
  `acquisition_failed` manifest，不會只剩 stack trace。
- `quality_warning=true` 仍是成功輸出（clip 太少 / borderline 來源 /
  低 yield / 年份低信心時提醒）。

## Scope Boundary

只做搜尋→取得→剪輯→整理完整投球影片。生物力學、pose、球種、球速、
投球評分全部屬於 downstream project。

---

## Milestone 1
Local Broadcast -> Candidate Center-Field Shots

Production 預設只接受 `center_field_good`。
`side_fullbody_acceptable` 僅保留作 validation / diagnostic label，不進 final.mp4。

## 範圍 (M1)
- probe video
- scene / shot segmentation
- per-shot view classification (7 classes)
- production candidate list = only `center_field_good`

不做：pitch start/end, release, replay dedup, YouTube/download, merge, final.mp4, filename export。

## 禁止
pose estimation / skeleton / body landmarks / biomechanics /
face recognition / jersey OCR / pitcher identity classifier。

允許：frame sampling, image/layout classifier, scene continuity,
crop/layout statistics, lightweight pretrained visual embedding.

## 使用
```bash
pip install -r requirements.txt
python -m src.clipper.pipeline --video <local.mp4> --out output/<run_id>   # M1
python -m src.clipper.run_m2 --run output/<run_id> --video <local.mp4>    # M2
pytest -q --basetemp=.pytest-tmp -p no:asyncio
python tools/evaluate_validation.py --labels validation/acceptance_set_v1/labels --preds output/<run_id>/shots.json
```

## M2 (Complete Pitch Event Localization)
- 輸入只吃 M1 `candidates.json`（`accepted_for_pitch_detection=true`），不重掃全片。
- 狀態只有 `PREPARED → MOTION_ACTIVE → POST_MOTION → SETTLED`，訊號只有
  frame-diff + optical flow + smoothing + 中央 broad region + shot continuity。
  無 body-part / release-mechanics 欄位；`motion_peak` 只是 temporal anchor。
- 輸出 `events.json`（`complete==true`）、`rejected_events.json`
 （`no_complete_pitch / start_incomplete / end_incomplete / ambiguous_motion /
  shot_too_short / shot_discontinuity`）、`diagnostics/temporal_scores.csv`、
  `diagnostics/event_windows/`、`manifest_m2.json`。不產 final.mp4。
- M1 凍結：M2 發現的上游問題記在 `validation/UPSTREAM_OBSERVATIONS.md`。

## M3 (YouTube Source Discovery & Selection — 無下載)
```bash
python run.py "Shohei Ohtani" --top-n 3
# → output/discovery/<pitcher-slug>/<run_id>/{candidates.json, selected_sources.json, discovery_manifest.json}
```
- 7組 query（full outing / every pitch / full start / full game / complete game / vs / pitching highlights），yt-dlp metadata only。
- `source_type`：full_outing / every_pitch / full_start / full_game / pitching_highlights / general_highlights / short / interview / reaction / unknown（無投手特例）。
- suitability 可觀察：semantic / duration / source / hold − editing_risk → final（`WEIGHTS` 可配，全投手共用）。
- game_year：explicit date=high，標題年份=medium，published_date=low，否則 null（不硬猜）。
- preview：`preview_stats_for_local_file()` 已實作（center-field比例/平均hold/rapid-cut率）；URL分段下載於 M4 實作（`acquisition/preview_acquire.py`）。

## M4 (Preview-Gated Source Acquisition)
```bash
python -m src.clipper.acquisition.run_preview --pitcher-slug shohei-ohtani \
  --selected output/discovery/shohei-ohtani/<run>/selected_sources.json --max-sources 3
# → output/preview/<slug>/<run_id>/{preview_manifest.json, source_preview_report.json,
#    sources/<video_id>/{segments/, m1m2/, preview_stats.json}}
```
- 取樣：5×20s（10/30/50/70/90%，避intro/outro，原速不crop）；短片降為3/1段。
- 取得：yt-dlp `--download-sections`，失敗則 full-then-trim，method逐段記錄；單 source 失敗不 crash 全輪（fallback 下一位）。
- 每段跑 **frozen** M1→M2（只重用不改）；section 邊界截斷的首尾 shot 計 `edge_skipped_shots`，不進 metrics。
- 指標：`complete_event_yield = complete/max(CF,1)`，`per_minute`，`incomplete_rate`，`discontinuity_rate`；decision `recommended/borderline/reject`（全投手同一保守規則，components全輸出）。
- `competition_context`：WBC/NPB/業餘/bullpen→`non_mlb`（預設不下載、直接reject）；無法確認→`unknown`（至多borderline）。
- `full_acquire.py`（完整下載）於 M5 實作。

## M4.5 (M2 Temporal Completion Calibration)
- 一次性 `validation/calibration_set_v1/`（41窗：11 complete / 30 not；
  RHP/LHP、先發/後援、多球場多轉播；只標 motion-completeness）。
  `acceptance_set_v1/` 維持凍結。
- 新 completion 定義：rise → sustained blob（gap-bridge 0.5s）→ 顯著
  decay（post ≤ max(LOW, peak×0.7)）→ stable（短 re-bump 容忍、sustained
  renewal 才放棄；尾端 0.3s transition 不可見）。不再要求全畫面安靜。
- 訊號：median-0.3s despike 先於 p99 正規化（過渡幀尖峰不再錨定尺度）。
  mound mask 證偽（無分離效果），維持 standard。
- 勝出全域參數（LOPO F1 0.40 / prec 0.75，TP 跨 3 投手 3 球場；
  start-cut 重標 4 窗全拒絕）：`relative, HIGH 0.45, DECAY 0.7,
  SETTLE 0.6, GAP 0.5, PREP 0.8`（`DEFAULT_PARAMS`，無投手欄位）。
- M4 gate 門檻本輪未動。

## M5 (Full Automatic Acquisition → Clean Pitch Video)
```bash
python run.py "Yoshinobu Yamamoto" [--top-n 3] [--year 2026] [--max-sources 3]
# → output/<slug>/<run_id>/{run_manifest.json,<Name>_<Year>.mp4,sources/<video_id>/{...}}
```
- 全自動：M3 discovery → M4 preview gate → full下載 → normalize(H.264/yuv420p)
  → frozen M1 → calibrated M2 → 精確clip抽出 → 保守dedup → 時間排序concat。
- source選擇：recommended優先，否則best borderline MLB/unknown（reject永不當
  fallback）；`source_selection_mode` 寫入manifest；non_mlb不進production。
- 每source獨立產出（`sources/<video_id>/final.mp4`＋產品檔名拷貝）；
  同年撞名加`_01`；year confidence low/null→`_UnknownYear`（不用published year
  假裝；manifest保留原值並加 `game year unreliable` warning）。
- `--year`：只有 high/medium 年份不符才排除；low/null 視為未知而保留，
  但 published year 早於 `--year` 者排除（影片不會早於比賽上傳）。
- dedup只刪高信心（dHash≤8＋時長±25%或時間重疊，留長者）；replay無獨立
  detector→`replay_status=uncertain`，不亂刪。
- 任一source失敗→下一位；全滅→`no_suitable_source` manifest，不crash。

## M6.3 (M1 Shot Purity Hardening)
- 生產接受條件：`CF + conf ≥ 0.5 + 非 transition_contaminated`。
  門檻證據：5 runs 14個frame-verified bad CF全≤0.458；已確認good全≥0.61。
- dissolve guard：shot內5點HSV-hist，`min_adj<0.8 OR edge<0.8`即veto。
  擋s005/s030等混剪mega-shot；7個verified goods全過（≥0.936）。
- 已知殘留：homogeneous close-up FP（如16秒純特寫s024 0.557）兩關皆過，
  需classifier層改進（見`validation/regression_cases/m1_shot_purity/`）。
- M2/M3/M4/dedup/acquisition 全未動。

## M6.4 (Homogeneous Close-up FP Rejection)
- 新增veto：`margin (CF−max非CF) < 0.40 AND 單幀edge密度 < 0.10`
  → `homogeneous_closeup`。只用已有多類scores＋場景紋理，無身體特徵。
- 證據：4 verified close-up FP（margins≤0.277/edges≤0.081）全擋；
  10 verified真CF保留（含margin僅0.22的s118，靠edge通過——故須AND）。
- 綠色比例證偽（夜賽）；mound mask先前已證偽。
- 已知殘留：margin高且紋理夠的誤判（罕見），需classifier層。
- M2/M3/M4/dedup/acquisition 全未動。

## M7 (Release Candidate)
- 起動 pre-flight（Python/ffmpeg/ffprobe/yt-dlp/套件），缺件直接說明並退出。
- 失敗契約：單源失敗→fallback；全滅→`no_suitable_source`/`acquisition_failed`；
  頂層守衛保證只剩 manifest，不剩裸 stack trace。
- manifest schema 凍結（含 M1 三種 reject 計數、acquisition 方法、warnings[]、
  quality_warning 規則）。
- 已知限制見上（Known Limitations）；replay 維持保守 `uncertain`。

## M7.1 (Adaptive Preview Evidence Expansion)
- preview 證據分三態：sufficient_good（≥1 event，直接過）／sufficient_bad
  （多CF零事件＋大量reject，不擴張）／insufficient（稀疏，擴張後再判）。
- 首輪維持5×20s；不足時第二輪＋4段（20/40/60/80%），短片（≤15min）可第三輪。
- 上限：10段／200秒／50%覆蓋；時間戳確定性不重疊；失敗隔離。
- M1/M2/Gate判斷邏輯全未動——只改變「看多少證據再判」。

## M7.2 (Download Reliability)
- 證據：RC 回歸 8 投手中 5 次出現 YouTube `HTTP Error 403`；完整下載無重試，
  Glasnow 較佳來源因一次 403 失去（手動重試即成功）。
- 完整下載最多 3 次（退避 5s/15s，timeout 不重試）；preview 分段下載重試 1 次
  後才 fallback full-then-trim（整支下載，僅 1 次）。
- 錯誤保留 yt-dlp 的 `ERROR` 行（如 403），不再是被截斷的指令字串。
- 無 deno 但有 node 時加 `--js-runtimes node`（yt-dlp 預設只認 deno）。
- 最終失敗時清除 `.part` / `.ytdl` 殘檔（共用 `acquisition/ytdlp.py`）。
- M1/M2/Gate判斷邏輯與 manifest schema 全未動。

## M7.3 (Insufficient-Evidence Fallback Tier)
- 證據（`validation/regression_cases/m7_3_preview_insufficient/`）：長片完整
  投球稀少（如 37 分鐘 6 顆），180 秒 preview 多半看不到 → insufficient 判
  reject 多屬取樣運氣。11 支 insufficient 來源完整跑：4 支 ≥3 clips（目視
  14/16 正確，與 gate 通過者相當）；3 支僅 1–2 clips（1/4 正確）。
- 選源改為三層：recommended → borderline（MLB/unknown）→ insufficient
  reject（preview CF>0、MLB/unknown、取得成功；依 preview CF、再依 M3 分數）。
  recommended 全失敗時也會往下試 borderline。
- preview 沒看過任何完整投球的來源（insufficient 層，以及僅憑 CF 比例進
  borderline、0 event 者）須完整跑出 ≥ `FEW_CLIPS`（3）clips 才採用，否則
  `low-yield`（不產檔、試下一位）；insufficient 層 manifest 標
  `source_selection_mode=insufficient_evidence_fallback` 並加 warning。
  （e2e：Edwin 0-event borderline 來源 2 clips，1 顆疑似缺起始 → 現在不出。）
- 仍永不 fallback：sufficient_bad、preview 零 CF、non_mlb、取得失敗。
  （sufficient_bad 有 1/2 誤殺紀錄，樣本太少未改。→ M7.4 已改。）
- 修正：完整影片零 CF candidate 時不再 AssertionError，改 `no-usable-clips`。
- M1/M2/Gate 判斷與門檻全未動；只改「哪些來源可當備援、何時算成功」。

## M7.4 (Uniform Yield Minimum + Bad-Evidence Last Resort)
- 證據（`validation/regression_cases/m7_4_tier_yield/`）：新增 5 投手、
  所有 preview 過的來源一律完整跑＋目視；25 支完整跑中，≥3 clips 的輸出
  59/67 正確，1–2 clips 只有 5/10。
- **每個產品都須 ≥ `FEW_CLIPS`（3）clips**（所有層級，含 recommended）；
  不足 → `low-yield`、不產檔、試下一位。觀察資料中 recommended / 有 event
  的 borderline 從未產出 1–2 clips，故它們的既有輸出不變。
- sufficient_bad 改為最後一層 `bad_evidence_fallback`（4 支完整跑：僅
  4EQCjkErc5k 達 3 clips 且 3/3 正確，其餘不達標不會出貨）。
- 零 CF veto 保留：RCC0dhypebY（隔網拍的業餘/小聯盟影片）完整跑被 M1 誤判
  出 5 clips、0/5 正確 → ≥3 clips 擋不住非轉播畫面，evidence 型 veto 必要。
- **full_game 一律不進 production**（同 non_mlb）：整場轉播/比賽集錦
  兩隊投手都出現在同一中外野機位，而投手身分辨識不在範圍內。證據：Snell
  的 WS G7 整場（212 分）完整跑出 28 clips，兩隊投手混雜＋5 段非投球
  （片頭、子母畫面、特寫）。M7.3 讓 insufficient 的整場比賽可當 fallback，
  此規則補上該破口。discovery 改取 2×`--top-n` 再排除，維持 preview 數量
  （無排除時排名前綴不變）；排除原因記在 run manifest `discovery.excluded`。
- clip 抽取改 input-side `-ss`：轉碼時仍逐格精準（與舊法 0.00 MSE），
  但不再從片頭解碼（整場比賽後段每顆 ~6 分 → 2 秒，舊法逼近 600s timeout）。
- 觀察未處理：preview 有 1 event、完整跑 0 event（2 例）；M1 會把隔網
  fan footage 誤判為 CF（M1 凍結，靠 preview veto 擋）。

## M7.5 (Indecisive Close-up Veto)
- 證據（`validation/regression_cases/m7_5_low_margin_closeup/`）：交付成品中
  margin 最低的 3 顆（0.116 / 0.220 / 0.220，runner-up 皆 side）全是投手
  特寫；margin<0.30 的已接受 CF shot 抽 23 支重下載目視：runner-up 為
  side/batter/other 者 13/13 非 CF；runner-up 為 field 者 5/10 是夜間轉播的真 CF。
- 新 veto：margin < 0.30 且 runner-up ≠ `field_bad` → 直接否決（不看紋理）；
  其餘維持 M6.4（margin<0.40 AND edge<0.10）。只用既有 CLIP 分數，無身體特徵。
- 勘誤：M6.4 的關鍵 TRUE 案例 oht-s118 經 8 幀重查為本壘側正面、無投球。
- 回放：成品只少掉那 3 顆錯的；100 次 preview 中 93 不變，改變者仍在
  M7.3 fallback 層內；M6.4 已驗證的正確鏡頭 margin 皆 ≥0.590 不受影響。
- 未處理：margin ≥0.39 的打者特寫 / 反向機位，以及 M2 時間性錯誤
  （起點被切、投後畫面、尾端切鏡）。→ 前者由 M7.6 處理。

## M7.6 (Per-Source CF Framing Consistency)
- 證據（`validation/regression_cases/m7_6_framing_consistency/`）：同一支
  轉播的中外野機位構圖幾乎固定。以該來源 margin≥0.6 的 CF shot 為原型，
  比較 CLIP 影像嵌入（M1 本來就算的）之 3-NN cosine：16 來源交付成品中
  9 顆錯誤視角（打者特寫×4、投手特寫×3、反向機位×2）為 0.695–0.882，
  63 顆正確者全 ≥0.950。
- 新規則（僅 production、M1 之後 M2 之前）：knn < 0.90 →
  `framing_inconsistent`；原型 <5 或無嵌入（heuristic）則跳過。
  M1 另存 `embeddings.npz`。不用身體/臉/身分特徵、無投手特例。
- 全部已接受 CF shot 中 knn<0.92 的有 24%，但其上僅有那 9 顆錯誤事件；
  重下載抽樣 20 支中 18 支非 CF，2 支真 CF 在 0.904/0.911（高於門檻）。
- 已知限制：原型本身錯（隔網 fan footage）時無效，靠 preview 零 CF veto；
  剪輯插入的他場 CF 鏡頭可能被擋（本來就不是該場）。
