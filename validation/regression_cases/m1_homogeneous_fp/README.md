# m1_homogeneous_fp — M6.4 regression set (frozen after this round)

Homogeneous close-up FPs: stable shot, no transition, wrong view labeled
center_field_good. Neither the confidence gate (s024 0.557) nor the
dissolve guard (homogeneous) catches them alone.

BAD (must be vetoed by margin<0.40 AND edge<0.10):
- cro-s024 (CF 0.557, margin +0.277, edge 0.061): 16s pure close-up+graphic
- oht-s079 (CF 0.366, margin +0.003, edge 0.081): batter close-up
  (also gate-killed; defense in depth)
- yam-s236/s258/s309 (margins +0.053..+0.151, edges ~0.05)
- yam-s322 (margin +0.137, edge 0.080)

GOOD (must be kept; edges 0.119..0.168, day + night, 5 pitchers/sources):
- dev s001/s023/s035/s037, yam-s013, cro-s076, ske-ev, mil-ev
  (margins +0.590..+0.825)
- oht-s118 is the critical guard for the AND design: TRUE CF pitch
  (audited set-on-mound) with margin only +0.22, but edge 0.168 passes,
  so margin-alone would wrongly kill it while AND-veto keeps it.

Vetoed event-shots sampled 6/6: post-play aftermath / close-ups / tails,
0 full-pitch losses.

> ERRATUM (M7.5): oht-s118 was re-checked with 8 frames and is NOT a
> center-field pitch (home-side front view, no delivery). See
> `../m7_5_low_margin_closeup/README.md`. Text above left as frozen.
