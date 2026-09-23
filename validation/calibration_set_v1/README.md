# calibration_set_v1 (ONE-TIME, FROZEN AFTER M4.5)

一次性人工窗級標註，只用於 M4.5 temporal completion calibration。
`validation/acceptance_set_v1/` 維持凍結不動；此目錄是 M4.5 專用。

- 41 windows：14 complete → relabel 後 11 complete / 30 not-complete。
  Dense re-view 將 w03 / w11 / w41 改為 start_cut（panel1 已在動作中，
  preparation 不可見）；w07 / w10 維持 complete（set 可見，需容忍
  transition blip）。w07 / w10 是 head-blip forgiveness 的關鍵測試。
- 只標 motion-completeness，不標 body mechanics。
- LOPO groups（pitcher）：crochet(4) / yamamoto(6) / miller(8) /
  skubal-tape(4) / ohtani(17)。WBC 窗歸 yamamoto（同一投手不同賽事）。
- skubal-tape 為 montage 混剪（多人），自成一組，測剪輯泛化。

## 欄位
window_id, video_file, t0_file, t1_file, pitcher, broadcast_source,
view, complete_pitch, acceptable_clip_start, acceptable_clip_end,
failure_reason (null|start_cut|end_cut|wrong_view|no_pitch|transition|post_play),
notes

## 判定規則（evaluator 用）
- complete=true：系統須輸出 ≥1 event，且其 clip_start ∈ [ws−0.5, acc_start]、
  clip_end ∈ [acc_end, we+0.5]，其中 acc_start = ws+1.0、acc_end = we−0.5。
- complete=false：系統須輸出 0 events（任一 event 即 false）。
