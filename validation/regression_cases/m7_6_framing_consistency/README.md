# m7_6_framing_consistency — M7.6 evidence set (frozen after this round)

Residual wrong views that CLIP text scores cannot separate (batter
close-ups and reverse angles at margins 0.39–0.81). Idea: a broadcast's
center-field camera framing is nearly constant within a source, so compare
each accepted CF shot with the SAME source's confident CF shots in CLIP
image-embedding space (the embedding M1 already computes).

Feature: `knn` = mean cosine of the shot's embedding to its 3 nearest
prototype shots, prototypes = accepted CF shots of the source with class
margin ≥ 0.6, leave-one-out, ≥ 5 prototypes required. Experiment
embeddings came from 360p video-only re-downloads with M1's own 3 sample
times and CLIP preprocessing (CLIP sees 224 px).

## Delivered clips (16 sources, 72 audited clips with embeddings)

| | clips | knn |
|---|---|---|
| wrong views | 9 | 0.695–0.882 |
| correct | 63 | ≥ 0.950 |

Wrong views: XD-bn6GhRBQ p001 0.695 (batter), JgdDkwC7plw p003 0.709
(batter), Q8Bl2X4VKuw p012 0.779 (batter), -kdqbKXRL8U p002 0.784
(batter), Q8Bl2X4VKuw p011 0.795, WjJtcfLaSjI p001 0.798 (pitcher
close-ups), wlf9OO-jV6s p003 0.841, 9izErZHWvYc p002 0.848 (reverse
angles), av5KQk1HNbc p001 0.882 (front close-up; also vetoed by M7.5).
The 3 temporal (M2) errors in these sources sit ≥ 0.95, as expected.

## All accepted CF shots (917 with ≥ 5 prototypes)

knn < 0.92: 220 shots (24%), carrying 9 complete events — exactly the 9
wrong clips above; no correct event is lost. Re-downloaded sample:

- 20 shots below 0.92: 18 not CF (sky, crowd, batter close-ups, base
  runners, high/overhead wide views, high-home and low reverse angles,
  celebration); 2 true CF at 0.904 (a shot from another game inserted in
  the edit) and 0.911 (CF with a large stats overlay).
- 6 shots at 0.921–0.927: 4 true CF, 2 reverse angles (0.921, 0.922).

The population overlaps around 0.90–0.93, so the cut is set at **0.90**:
all 9 wrong delivered clips fall below it (the highest, 0.882, is also an
M7.5 veto) and both sampled true-CF shots stay above it. Shots that pass
in the overlap band produced no complete events in this data.

## Rule adopted (M7.6)

`src/clipper/framing.py`, production only (`run_source` after M1, before
M2): knn < 0.90 → `reject_reason = framing_inconsistent`. Skipped when a
source has < 5 prototype shots or no embeddings (heuristic backend). Not in
the preview gate (20-s segments rarely hold 5 prototypes). M1 now writes
`embeddings.npz` (float16) next to shots.json.

Known limits: a source whose confident CF shots are themselves wrong
(e.g. backstop fan footage, RCC0dhypebY) gets a wrong prototype — the
preview zero-CF veto keeps such sources out. Inserted shots from other
games with a different CF camera may be vetoed (acceptable: they are not
the source game).
