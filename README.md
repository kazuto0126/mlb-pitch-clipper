# MLB Pitch Clipper — Milestone 1
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
- preview：`preview_stats_for_local_file()` 已實作（center-field比例/平均hold/rapid-cut率）；URL分段下載為 M4 stub。

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
- `full_acquire.py` 為 M5 stub。

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
  同年撞名加`_01`；year不可靠→`_UnknownYear`（不用published year假裝）。
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
