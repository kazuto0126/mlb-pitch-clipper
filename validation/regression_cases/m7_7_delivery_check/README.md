# m7_7_delivery_check — M7.7 evidence set

The commonest error left after M7.6: M2 accepts a "pitch" in which the
pitcher never delivers (batter steps out, catcher/umpire move, pitcher
holds the set or walks around the mound). M2 normalizes motion per shot,
so these small motions reach the same normalized level as a delivery.
All of them were caught only by the operator's frame-by-frame audit
before delivery (Yamamoto 1, Ohtani 1, Sasaki 4, Kershaw 2, Skubal 5).

Idea: the center-field view has a fixed layout — the pitcher stands left
of and below the batter, catcher and umpire. Compare motion energy
(frame difference + optical flow, M2's own signal family) in two fixed
boxes over [motion_onset, settle_time]:

- pitcher box: x 0.19–0.50, y 0.35–0.82
- batter box: x 0.50–0.81, y 0.10–0.55
- `pitcher_share` = pitcher / (pitcher + batter)

No person detection, tracking, body parts or identity.

## Labelled set (`labels.json`)

63 events from the 10 sources delivered between 2026-10-06 and 10-13,
labelled during the delivery audits: 13 without a delivery, 45 delivered
pitches, 5 real deliveries the operator excluded for bad bounds.

| | n | pitcher_share |
|---|---|---|
| no delivery, vetoed | 8 | 0.286–0.420 (+ 2 short events at 0.472/0.474) |
| no delivery, kept | 5 | 0.456–0.735 |
| delivered pitches | 45 | ≥ 0.457 (short ones ≥ 0.564) |

The 5 kept no-delivery events overlap with deliveries on this feature
(Ohtani's reliever at 0.735 moves a lot while taking signs; a Sheehan
walk-off at 0.456). They are left to the operator audit.

An earlier candidate, the vertical centroid of all motion, caught 9/13
but a delivered pitch sat 0.0007 from its threshold; it was dropped for
the box share, which leaves a 0.017 gap to the nearest delivered pitch.

## Rule adopted (M7.7)

`src/clipper/delivery_check.py`, production only (`run_source` after M2,
before clip extraction): `pitcher_share < 0.44`, or event shorter than
1.4 s with `pitcher_share < 0.48` → `reject_reason =
no_delivery_suspected` (detail names the event and its share).
Unreadable events are kept. Result on this set: 8/13 no-delivery events
rejected, 0/45 delivered pitches lost (also 3 of the 5 bad-bounds
deliveries rejected).

Known limits: assumes the standard offset CF camera (pitcher left of the
batter); a straight-on camera would split the pitcher across both boxes.
The hand-off contract keeps `pitch_delivery_visible` as `not_verified`.

## After adoption

- Paul Skenes (YWXd-ZXNkcc, 2026-10-14): the veto removed a home-plate-
  side view of a play (share 0.434, correctly). Two no-delivery events
  were missed (0.559, 0.453): the batter was left-handed and stands left
  of the plate in the CF view, inside the pitcher box. A left-handed
  batter can only raise the share, so the rule misses more often against
  them but does not reject more deliveries. 3 deliveries kept (≥ 0.52).
- Rejected events now keep their full event (times, share) in
  rejected_events.json for the audit.
