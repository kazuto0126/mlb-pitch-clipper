"""Fresh-discovery top-3 per pitcher (M6.2 live recheck)."""
import glob
import json

for slug in ["shohei-ohtani", "yoshinobu-yamamoto", "garrett-crochet",
             "mason-miller", "tarik-skubal", "paul-skenes"]:
    ds = glob.glob(f"output/discovery/{slug}/*/selected_sources.json")
    # newest run dirs sort last; take latest
    d = sorted(ds)[-1]
    print("=" * 20, slug)
    for s in json.load(open(d, encoding="utf-8")):
        print(f"  {s['suitability']['final_score']:.3f} | {s['source_type']:20s} | "
              f"{(s['duration'] or 0)//60:3d}min | {s['channel'][:20]:20s} | "
              f"{s['title'][:66]}")
