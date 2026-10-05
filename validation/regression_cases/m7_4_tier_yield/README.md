# m7_4_tier_yield — M7.4 evidence set (frozen after this round)

Extends `m7_3_preview_insufficient` with 5 new pitchers (Wheeler, Webb,
Clase, Sale, Greene: real discovery + preview, then a FULL run of every
previewed source regardless of the gate verdict, sources ≤ 90 min) and a
visual audit of the high-yield regression outputs. Truth = current code
(M1 purity, calibrated M2); audit = 4–5 frames per final clip.

## Audit by final clip count (25 audited full runs)

| final clips | sources | clips correct |
|---|---|---|
| ≥ 3 (excl. vetoed fan footage) | 14 | **59/67 (88%)** |
| 1–2 | 10 | **5/10 (50%)** |

1–2 clip outputs: 9izErZHWvYc 1/2, GDugIdiSqRA 0/1, XD-bn6GhRBQ 0/1,
xT7FsAzEiq4 0/1, -kdqbKXRL8U 1/2 (p002 batter close-up), uq86tY4PXiU 1/2,
14K_jncH7fM 1/1, gi9KQVeGGBQ 1/1. No recommended / ≥1-event borderline
source produced 1–2 clips here (their yields: 0, 0, 3, 3, 6, 11, 16), so
the uniform minimum changes none of their observed outputs.

≥ 3 clip outputs: q7ndAVBppQQ 15/16 (p007 tail), Q8Bl2X4VKuw 9/11 (p011
pitcher close-up, p012 batter close-up), RObvkuHpkSo 6/6, CgZ2MrU3BKs 3/3,
1bZiuoaLARg 3/3, myyfpqlODso 4/4, J8rbe-phNPQ 4/4, WjJtcfLaSjI 4/5,
av5KQk1HNbc 2/3, 4EQCjkErc5k 3/3, q2dSaXzowlw 3/3, JgdDkwC7plw 2/3
(p003 batter close-up), p4jdR2TT5b0 1/3 (p001 post-pitch + zoom, p002
camera cut in tail).

## sufficient_bad rejects (4) — now a last-resort tier

| video_id | pitcher | final | audit |
|---|---|---|---|
| 4EQCjkErc5k | Crochet every_pitch 14m | 3 | 3/3 |
| gi9KQVeGGBQ | Diaz career montage 24m | 1 | 1/1 |
| 14K_jncH7fM | Wheeler every_pitch 12m | 1 | 1/1 |
| bJ2zfIE18fk | Sale strikeout montage 9m | 0 | – |

With the ≥ 3 minimum only 4EQCjkErc5k would be used (3/3 correct); no
wrong output would have shipped.

## Zero-CF veto confirmed (keep)

RCC0dhypebY (Greene "Full Outing", fan footage shot through the backstop
net, minor league): preview 0 CF → vetoed. The FULL run misreads it as
CF and yields 5 clips, 0/5 correct — ≥ 3 clips does not protect against
non-broadcast footage, so evidence-of-wrong-footage vetoes stay.

## Full-game broadcasts are multi-pitcher (now excluded)

SU_bMo561b8 (Blake Snell candidate; "FULL GAME: 2025 World Series Game 7",
212 min, preview insufficient): full run 249 min, 456 CF, 31 events, 28
final clips. Audit: p001–p003 pre-game cinematic intro, p006 split-screen
(PIP), p007 player/coach close-up; the remaining 23 are CF pitches from
BOTH teams (home white and road grey uniforms). Pitcher identity is out of
scope, so no full_game source can yield a clean single-pitcher video;
before M7.3 these were only kept out by luck (sparse preview). 12
full_game sources seen across runs (7 are ≥ 100-min broadcasts, the rest
5–10-min game recaps); 3 were fully run: ixs6erjwVH8 0 clips, QIYE1k6-LyI
0 clips, SU_bMo561b8 the multi-team 28. → `full_game` excluded from
production like `non_mlb`.

Also measured here: post-input `-ss` clip extraction decoded from 0 — clip
at ~2h50m took ~6 min, 31 clips ~1h40m (600s timeout risk). Input-side
`-ss` is frame-identical (0.00 MSE on a 43-min source) and ~2s per clip.

## Observations (not acted on)

- Preview vs full inconsistency: _3ml7CIgFX4 (Clase) and QIYE1k6-LyI
  (Greene) had 1 preview event but 0 full-run events (segment-local M1/M2
  differs from full-video M1/M2). Costs one wasted full run; not harmful.
- M1 misreads backstop fan footage as center field (RCC0dhypebY). M1 is
  frozen; the preview zero-CF veto is what keeps it out.

## Rule adopted (M7.4)

- Every product needs ≥ `FEW_CLIPS` (3) final clips, in every tier;
  fewer → `low-yield`, no product file, next source.
- Tier order: recommended → borderline → insufficient → sufficient_bad
  (`bad_evidence_fallback`); zero-CF, non-MLB, failed previews vetoed.
