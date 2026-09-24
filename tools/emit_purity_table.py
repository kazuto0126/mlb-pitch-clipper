"""Emit the shot-level evidence table (human_class from frame audits)."""
import json

# (shot_id, run/video key, view, conf, human, note)
ROWS = [
    # Ohtani production run (av5KQk1HNbc)
    ("s005", "oht", "center_field_good", 0.6479, "bad-impure", "CF+batter, missed cut"),
    ("s030", "oht", "center_field_good", 0.623, "bad-impure", "28s mega-shot, mixed"),
    ("s079", "oht", "center_field_good", 0.3664, "bad-view", "pure batter close-up"),
    ("s186", "oht", "center_field_good", 0.3087, "bad-view", "base runner"),
    ("s241", "oht", "center_field_good", 0.3431, "bad-view", "dirt-play close-up"),
    # Crochet production run (myyfpqlODso)
    ("s024", "cro", "center_field_good", 0.5566, "bad-view", "16s pure close-up+graphic"),
    ("s224", "cro", "center_field_good", 0.3001, "bad-view", "logo animation"),
    ("s011", "cro", "center_field_good", 0.3123, "bad-view", "logo animation"),
    ("s087", "cro", "center_field_good", 0.817, "good-impure?", "homogeneous CF, real pitch tail"),
    # Yamamoto production run (Q8Bl2X4VKuw) low-conf events
    ("s037", "yam", "center_field_good", 0.458, "bad-view", "pitcher head close-up"),
    ("s236", "yam", "center_field_good", 0.421, "bad-view", "pitcher face close-up"),
    ("s258", "yam", "center_field_good", 0.383, "bad-view", "pitcher face close-up"),
    ("s309", "yam", "center_field_good", 0.452, "bad-view", "pitcher upper close-up"),
    ("s322", "yam", "center_field_good", 0.384, "bad-view", "batter close-up"),
    ("s153", "yam", "center_field_good", 0.3126, "bad-view", "batter close-up"),
    ("s013", "yam", "center_field_good", 0.7463, "good", "audited-clean event source"),
    # Skenes / Miller / dev goods
    ("s060", "ske", "center_field_good", 0.3178, "bad-view", "SUBSCRIBE end card"),
    ("s000", "ske", "center_field_good", 0.7385, "good", "audited-clean event source"),
    ("s091", "mil", "center_field_good", 0.3708, "bad-view", "pitcher close-up"),
    ("s000", "mil", "center_field_good", 0.7411, "good", "audited-clean event source"),
    ("s001", "dev", "center_field_good", 0.6088, "good", "verified CF pitch"),
    ("s023", "dev", "center_field_good", 0.75, "good", "verified CF pitch"),
    ("s035", "dev", "center_field_good", 0.88, "good", "verified CF pitch"),
    ("s037", "dev", "center_field_good", 0.88, "good", "verified CF pitch"),
]
json.dump([{"shot_id": s, "run": r, "predicted": v, "confidence": c,
            "human_class": h, "note": n} for s, r, v, c, h, n in ROWS],
          open("validation/regression_cases/m1_shot_purity/shots.json", "w"),
          indent=1)
print(len(ROWS), "rows")
