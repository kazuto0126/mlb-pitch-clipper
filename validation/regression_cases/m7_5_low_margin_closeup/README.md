# m7_5_low_margin_closeup — M7.5 evidence set (frozen after this round)

Residual M1 wrong views inside delivered outputs (M7.4 audit). Stored
per-shot CLIP scores only (no new features); margin = CF − max(non-CF).

## Final clips (114 audited, current code)

The three lowest-margin final clips were all wrong views, each with
`side_fullbody_acceptable` as runner-up:

| video / clip / shot | margin | runner-up | frames |
|---|---|---|---|
| WjJtcfLaSjI p001 s015 | +0.116 | side | pitcher upper-body close-up |
| Q8Bl2X4VKuw p011 s355 | +0.220 | side | pitcher upper-body close-up |
| av5KQk1HNbc p001 s118 | +0.220 | side | home-side front full body, no delivery |

Lowest-margin correct final clip: av5KQk1HNbc p003 s279, +0.322 (CF,
delivery visible). Batter close-ups / reverse angles / intro montage / PIP
sit at margins 0.39–0.90, mixed with correct clips → not separable with
stored scores (out of scope here).

## ERRATUM for m1_homogeneous_fp (M6.4)

`oht-s118` (= av5KQk1HNbc s118, 762.0–771.8 s) was recorded as the
"critical guard" TRUE CF pitch that forced the AND design. An 8-frame
re-check of the re-downloaded section shows a home-plate-side front view
of the pitcher standing on the mound, no delivery in any frame: not a
center-field view and not a pitch. The AND rule therefore had no verified
true positive below margin 0.40 to protect.

## Accepted-CF shots with margin < 0.30 (31 sources, deduplicated)

84 of 1774 accepted CF shots (4.7%), producing 3 complete events (the 3
wrong clips above). Stratified sample of 23, re-downloaded and checked:

| runner-up | sampled | not CF |
|---|---|---|
| side_fullbody / batter / other | 13 | 13 (pitcher/batter close-ups, dugout, crowd, intro montage) |
| field_bad | 10 | 5 (overhead/high wide views); 5 true CF in one dim night broadcast (av5KQk1HNbc s004/s015/s020/s033/s055) |

## Rule adopted (M7.5)

In `shot_purity.assess_closeup`: margin < 0.30 with runner-up not
`field_bad` → vetoed without the texture check; otherwise the M6.4 rule
(margin < 0.40 AND edge < 0.10) is unchanged. `field_bad` stays benign:
wide field views are the CF class's natural neighbour and dim broadcasts
lower the margin of true CF shots.

Replay on stored JSON: final clips lose exactly the 3 wrong ones
(Q8Bl2X4VKuw 11→10, WjJtcfLaSjI 5→4, av5KQk1HNbc 3→2 → below the 3-clip
minimum, not delivered; that pitcher's higher-tier source is unaffected);
100 stored previews: 93 unchanged, 7 shift evidence state, 2 borderline →
reject(insufficient), which remain in the M7.3 fallback tier. All M6.4
verified goods have margins ≥ 0.590 and are untouched.

Not addressed: batter close-ups / reverse angles at margin ≥ 0.39, and M2
temporal errors (start cut, post-play, tail camera cut).
