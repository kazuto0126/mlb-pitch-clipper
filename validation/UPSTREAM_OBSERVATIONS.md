# Upstream (M1) observations from M2 dev-video audit — DO NOT edit M1 code

Source (dev only, not part of pipeline): MLB official `w2rP_qc4EAs` 00:00–04:00.
M1 run `output/m1_ohtani_test/` → 26 candidates → M2 → 2 events + 25 rejected.

## O1. Missed dissolves / soft transitions (s004, s008, s033)
M1 histogram hard-cut detector misses non-hard transitions:
- s004 (44.6–60.8): center-field → batter-side cut ~56–57s missed.
  M2 consequence: batter-swing pattern accepted, later killed by M2
  `shot_discontinuity` guard (min_corr 0.212). Guard works when the pattern
  straddles the cut; see O3 for when it does not.
- s008 (75.0–88.0): game → ABS challenge graphic segment missed.
  Graphic animation mimicked a full temporal pattern; killed by
  `shot_discontinuity` (shotstart-vs-peak corr 0.403 < 0.45).
- s033 (219.0–223.0): side-view → center-field cut 219.0–219.3 missed.
  Event itself is a TRUE pitch (onset 219.9 in center-field), but clip_start
  219.0 keeps ~0.3s of side-view. Continuity guard passes (corr 0.656):
  same green palette across the cut. Accepted with known head contamination.

## O2. M1 false-positive candidates become M2's hardest cases (s002, s019, s027)
Batter close-ups / back-walking shots labeled `center_field_good` with low
confidence (0.38–0.50). M2 rejected all three (`hot throughout` /
`no_complete_pitch`), so M2 acts as a second filter — but M2 cannot fix a
shot that is entirely wrong-view. Confidence-gated input (e.g. ≥0.6) for M2
is suggested for validation on the acceptance set, not hard-coded here.

## O3. Highlights editing defeats motion-only patterns (s004 p001 case)
s004 event 48.2–51.3 starts ON the previous play's swing and spans the
dead-ball reaction + next windup: quiet→active→settle arises *between* plays.
No frame-diff/flow signal distinguishes "dead-ball lull" from "preparation".
Fix belongs to source selection (prefer full-game, long-hold broadcast over
montage/highlights), not to M2 body semantics (out of scope).

## O4. Strict settle rejects visually-complete pitches (s001, s011)
Pitcher finished, but catcher/batter/umpire keep moving → floor stays
0.42–0.50, never ≤ LOW. Correct per reject-first spec; expected recall is
higher on full-game footage where the camera holds the shot longer.

## Standing rule
M1 files (`segment.py`, view-classifier production rule, class definitions)
stay frozen. These notes are input to M3/M4 (source selection preference:
full outing / every-pitch / long-hold broadcast), not M1 patches.
