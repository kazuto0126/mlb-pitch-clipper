"""List general_highlights pool members for picking a montage validation source."""
import glob
import json

for slug in ["tarik-skubal", "paul-skenes", "mason-miller", "garrett-crochet"]:
    cands = sorted(glob.glob(f"output/discovery/{slug}/*/candidates.json"))[-1]
    allc = json.load(open(cands, encoding="utf-8"))
    print("=" * 15, slug)
    for c in allc:
        if c["source_type"] == "general_highlights":
            print(f"  {c['video_id']} | {(c['duration'] or 0) // 60}min | "
                  f"{c['channel'][:20]} | {c['title'][:75]}")
