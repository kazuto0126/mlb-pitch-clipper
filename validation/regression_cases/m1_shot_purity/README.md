# m1_shot_purity — one-time M6.3 regression set (frozen after this round)

已知污染（frame-verified，必須被新規則擋下）：
- oht-s005 (CF 0.648, 6.6s)：missed hard-cut，前半 CF＋後半 batter close-up
- oht-s030 (CF 0.623, 28s mega-shot)：多段混剪，含 batter close-up
- oht-s079 (CF 0.366)：純 batter close-up 誤判
- cro-s024 (CF 0.557, 16s)：純 pitcher close-up＋graphic 誤判（homogeneous，guard 捉不到，gate 0.5 也放行 → 已知殘留）
- tail junk ×6 (CF 0.23–0.43)：logo 動畫 / SUBSCRIBE 卡 / close-up / 跑者 / batter
- yam low-conf events ×5 (CF 0.38–0.46)：全 pitcher/batter close-up
- oht-s241 event (CF 0.343)：dirt-play close-up

已知乾淨（frame-verified，必須保留）：
- dev s001 (0.61) / s023 (0.75) / s035 (0.88) / s037 (0.88)
- yam-s013 / ske-s000 / mil-s000（audited-clean events 來源）
- Skenes/Miller/Yamamoto 已審計 clips 的來源 shots

規則：
- MIN_CENTER_FIELD_CONFIDENCE = 0.5：擋 13 個已確認 bad（全 ≤0.458），
  0 已確認 good 被擋（最低 good 0.6088）。
- transition veto (min_adj<0.8 OR edge<0.8)：擋 s005/s030；
  s087 (0.884/0.849) 與所有 goods (≥0.936) 保留。
- 已知殘留：homogeneous close-up FP（s024 類）兩關皆過，
  需 classifier 層改進（未來 milestone，不在本輪）。
