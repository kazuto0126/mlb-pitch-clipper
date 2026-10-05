# m7_3_preview_insufficient — M7.3 evidence set (frozen after this round)

Problem: the preview gate rejected sources on *insufficient* evidence
(sparse sample, 0 events) and reject was never a fallback. Complete events
are rare in long-form footage (e.g. 6 per 37 min), so a ~180s preview
usually sees none: the verdict was mostly sampling luck, not source quality.
Longer segments do not fix it (geometric sim on 5 sources: 40s segments
raise usable shots ~55%→75% but expected events stay ≈0 for long sources).

Truth = full-video run with CURRENT code (M1 purity + calibrated M2);
audit = 4 frames per final clip, visually checked (CF complete pitch?).

## Preview REJECT, evidence_state=insufficient (11)

| video_id | pitcher | type | preview CF | full CF | final | audit good |
|---|---|---|---|---|---|---|
| myyfpqlODso | Crochet | every_pitch 23m | 5 | 110 | 4 | 4/4 |
| J8rbe-phNPQ | Crochet | every_pitch 16m | 6 | 67 | 4 | 4/4 (p003 tight-zoom mid-clip) |
| WjJtcfLaSjI | Miller | highlights 16m | 6 | 41 | 5 | 4/5 (p001 face close-up) |
| av5KQk1HNbc | Ohtani | full_outing 36m | 7 | 97 | 3 | 2/3 (p001 low front close-up) |
| 9izErZHWvYc | Snell | highlights 17m | 3 | 49 | 2 | 1/2 (p002 high-home reverse) |
| GDugIdiSqRA | Snell | highlights 10m | 4 | 22 | 1 | 0/1 (post-play, no delivery) |
| XD-bn6GhRBQ | Skenes | every_pitch 6m | 4 | 18 | 1 | 0/1 (batter close-up) |
| dYa3bhFPfJ8 | Yamamoto | every_pitch 20m | 6 | 38 | 0 | – |
| sez3hoikZks | Diaz | unknown 8m | 1 | 8 | 0 | – |
| RaC6M1SiP84 | Diaz | unknown 8m | 1 | 13 | 0 | – |
| 70JvQczUyqI | Glasnow | podcast 48m | 0 | 0 | 0 | – (zero-CF crash, fixed) |

- final ≥ 3 clips: 4/11 sources, 14/16 clips good (88%) — on par with
  gate-admitted sources (wlf9OO-jV6s control: 3 clips, 2/3 good).
- final 1–2 clips: 3/11 sources, 1/4 clips good (25%) — low-yield output
  from an unproven source is mostly wrong views.

## Preview REJECT, evidence_state=sufficient_bad (2) — veto kept

| video_id | pitcher | final | audit |
|---|---|---|---|
| 4EQCjkErc5k | Crochet every_pitch 14m | 3 | 3/3 good (a false veto) |
| gi9KQVeGGBQ | Diaz career montage 24m | 1 | 1/1 |

n=2 is too small to change the sufficient_bad rule; recorded for a future
calibration round.

## Rule adopted (M7.3)

Insufficient-evidence rejects (CF > 0, MLB/unknown, acquisition ok) become
a last fallback tier after recommended and borderline, ordered by preview
CF then metadata score, and are produced only if the full run keeps
≥ FEW_CLIPS (3) clips; fewer → `low-yield`, no product file, next source.
On this set: 4/4 accepted sources clean-ish (14/16), all three 1–2-clip
sources (1/4 good) refused, zero-clip sources cost one full run each.

The same ≥ FEW_CLIPS minimum applies to borderline sources with 0 preview
events (admitted on CF ratio alone): e2e Edwin `uq86tY4PXiU` (borderline,
0 events) produced 2 clips, p001 good, p002 opens after release (start
likely cut) → now refused. Gate-admitted 0-event borderline sources
`JgdDkwC7plw` (Glasnow) and `q2dSaXzowlw` (Skenes) yield exactly 3 and
are unaffected. Borderline sources with ≥1 preview event and recommended
sources keep the old minimum of 1.
