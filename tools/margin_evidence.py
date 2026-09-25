"""Evidence: CF-score margin distribution, verified goods vs homog FPs."""
import json
import sys

sys.path.insert(0, ".")

NON_CF = ["closeup_bad", "batter_bad", "field_bad", "graphic_bad",
          "other_bad", "side_fullbody_acceptable"]


def margin(scores):
    cf = scores.get("center_field_good", 0)
    return round(cf - max(scores.get(k, 0) for k in NON_CF), 4), round(cf, 4)


def show(base, sids, tag):
    sh = {s["shot_id"]: s for s in json.load(open(base + "/shots.json"))}
    for i in sids:
        s = sh[i]
        m, cf = margin(s.get("scores") or {})
        print(f"{tag} {i} dur={s['duration']:<6} conf={s['confidence']:<7} "
              f"cf={cf} margin={m:+.3f} scores={s.get('scores')}")


OHT = "output/shohei-ohtani/20260923T100612Z/sources/av5KQk1HNbc"
CRO = "output/garrett-crochet/20260923T104950Z/sources/myyfpqlODso"
YAM = "output/yoshinobu-yamamoto/20260923T005044Z/sources/Q8Bl2X4VKuw"
print("--- known HOMOG-FP ---")
show(CRO, ["s024"], "cro-BAD")
show(OHT, ["s079"], "oht-BAD")
for sid in ["s037", "s236", "s258", "s309", "s322"]:
    show(YAM, [sid], "yam-BAD")
print("--- verified GOOD ---")
dev = {s["shot_id"]: s for s in
       json.load(open("output/m1_ohtani_test/shots.json"))}
for i in ["s001", "s023", "s035", "s037"]:
    s = dev[i]
    m, cf = margin(s.get("scores") or {})
    print(f"dev-GOOD {i} dur={s['duration']:<6} conf={s['confidence']:<7} "
          f"cf={cf} margin={m:+.3f}")
for base, sid, tag in [(YAM, "s013", "yam-GOOD"), (CRO, "s076", "cro-GOOD"),
                       (OHT, "s181", "oht-GOOD")]:
    show(base, [sid], tag)
