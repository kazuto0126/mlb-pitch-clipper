"""Emit windows.jsonl from picks + hand labels (run once, then frozen)."""
import json

picks = json.load(open("output/calib_picks.json", encoding="utf-8"))
by_n = {n: p for n, p in enumerate(picks)}

# n -> (complete, failure_reason, pitcher_override, source, notes)
LABELS = {
    0: (True, None, "Garrett Crochet", "fenway", "set->delivery->follow-through"),
    1: (False, "post_play", "Garrett Crochet", "fenway", "opens on ball-in-play aftermath"),
    2: (True, None, "Garrett Crochet", "fenway", ""),
    3: (False, "start_cut", "Garrett Crochet", "fenway", "leg already up at head, no set visible"),
    4: (True, None, "Yoshinobu Yamamoto", "dodger-stadium", ""),    5: (False, "wrong_view", "Yoshinobu Yamamoto", "dodger-stadium", "batter close-up"),
    6: (False, "no_pitch", "Yoshinobu Yamamoto", "dodger-stadium", "6s hold, preparation only"),
    7: (True, None, "Yoshinobu Yamamoto", "dodger-stadium", ""),
    8: (False, "no_pitch", "Mason Miller", "wrigley", "walking off, dead-ball"),
    9: (True, None, "Mason Miller", "wrigley", "side-angle full delivery"),
    10: (True, None, "Mason Miller", "wrigley", "behind-catcher view, small pitcher"),
    11: (False, "start_cut", "Mason Miller", "wrigley", "already in motion at head"),
    12: (True, None, "skubal-tape", "comerica", "montage, tigers pitcher"),
    13: (True, None, "skubal-tape", "comerica", ""),
    14: (True, None, "skubal-tape", "comerica", ""),
    15: (False, "start_cut", "skubal-tape", "comerica", "opens mid-delivery, catcher-cam"),
    16: (False, "no_pitch", "Shohei Ohtani", "dodger-stadium", "pitcher walking, no delivery"),
    17: (None, None, None, None, "ambiguous pickoff/delivery, DROPPED"),
    18: (False, "no_pitch", "Shohei Ohtani", "dodger-stadium", "7s hold, no delivery"),
    19: (False, "no_pitch", "Shohei Ohtani", "dodger-stadium", "batter walk-up, set only"),
    20: (False, "wrong_view", "Shohei Ohtani", "chase-field", "side-view feature, not CF"),
    21: (True, None, "Shohei Ohtani", "chase-field", "canonical: pitcher done, scene active"),
    22: (None, None, None, None, "mixed shot w/ missed cut, DROPPED"),
    23: (True, None, "Shohei Ohtani", "chase-field", ""),
    24: (False, "wrong_view", "Shohei Ohtani", "chase-field", "pitcher close-up"),
    25: (False, "wrong_view", "Shohei Ohtani", "chase-field", "batter close-up"),
    26: (False, "no_pitch", "Shohei Ohtani", "chase-field", "batter walk + set, no delivery"),
    27: (False, "no_pitch", "Shohei Ohtani", "chase-field", "pitcher close-up hold"),
    28: (False, "no_pitch", "Shohei Ohtani", "chase-field", "ball in play, fielders"),
    29: (False, "no_pitch", "Shohei Ohtani", "chase-field", "dugout"),
    30: (False, "no_pitch", "Shohei Ohtani", "chase-field", "batter close-up 1.6s"),
    31: (False, "no_pitch", "Shohei Ohtani", "chase-field", "batter walk-up"),
    32: (False, "post_play", "Shohei Ohtani", "pnc-park", "pitcher walking off + transition wipe"),
    33: (False, "no_pitch", "Shohei Ohtani", "pnc-park", "pitcher close-up hold"),
    34: (False, "wrong_view", "Shohei Ohtani", "pnc-park", "batter-side view"),
    35: (False, "no_pitch", "Shohei Ohtani", "pnc-park", "batter walk-up"),
    36: (False, "no_pitch", "Mason Miller", "oakland", "pitcher walking, dead-ball"),
    37: (False, "transition", "Mason Miller", "wrigley", "scoreboard graphic overlay"),
    38: (False, "transition", "Mason Miller", "oakland", "0.4s graphic wipe"),
    39: (False, "no_pitch", "Mason Miller", "oakland", "1.0s hold, no delivery"),
    40: (False, "no_pitch", "Mason Miller", "oakland", "2s close-up hold"),
    41: (False, "start_cut", "Yoshinobu Yamamoto", "wbc-tokyo-dome", "WBC, mid-delivery at head"),
    42: (False, "wrong_view", "Yoshinobu Yamamoto", "wbc-tokyo-dome", "fielder close-up"),
}

out = []
for n, p in by_n.items():
    comp, fail, pitcher, src, notes = LABELS[n]
    if comp is None:
        continue
    if p["base"] == "dev:mlb_test_ohtani":
        video, t0, t1 = p["video"], p["start"], p["end"]
    else:
        video, t0, t1 = p["file"], p["seg_start"], p["seg_end"]
    ws, we = round(t0, 2), round(t1, 2)
    out.append({
        "window_id": f"w{n:02d}",
        "video_file": video, "t0_file": ws, "t1_file": we,
        "pitcher": pitcher, "broadcast_source": src,
        "view": p["view_class"], "complete_pitch": comp,
        "acceptable_clip_start": round(ws + 1.0, 2) if comp else None,
        "acceptable_clip_end": round(we - 0.5, 2) if comp else None,
        "failure_reason": fail, "notes": notes,
    })
json.dump(out, open("validation/calibration_set_v1/windows.jsonl", "w",
                    encoding="utf-8"), indent=1)
from collections import Counter
print(len(out), "windows")
print(Counter((w["pitcher"], w["complete_pitch"]) for w in out))
