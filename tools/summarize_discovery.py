import json
import glob

for slug in ["shohei-ohtani", "yoshinobu-yamamoto", "garrett-crochet",
             "mason-miller", "tarik-skubal", "paul-skenes"]:
    d = sorted(glob.glob(f"output/discovery/{slug}/*/selected_sources.json"))[-1]
    print("=" * 20, slug)
    for s in json.load(open(d, encoding="utf-8")):
        dur = (s["duration"] or 0) // 60
        print(f"  {s['suitability']['final_score']:.3f} | {s['source_type']:20s} | "
              f"{dur:3d}min | {s['channel'][:22]:22s} | {s['title'][:75]} | "
              f"{s['game_year']}/{s['game_year_confidence']}")
    cands = sorted(glob.glob(f"output/discovery/{slug}/*/candidates.json"))[-1]
    allc = json.load(open(cands, encoding="utf-8"))
    from collections import Counter
    print("  pool:", len(allc), Counter(c["source_type"] for c in allc))
