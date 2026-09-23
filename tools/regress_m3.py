"""M6.2 offline regression: rescore saved M3 pools with new code (no download)."""
import glob
import json
import sys

sys.path.insert(0, ".")

from src.clipper.discovery.select import enrich


def raw_of(c):
    pub = (c.get("published_date") or "").replace("-", "")
    return {"id": c["video_id"], "title": c["title"], "channel": c["channel"],
            "webpage_url": c["url"], "duration": c["duration"],
            "upload_date": pub if len(pub) == 8 else "",
            "description": c.get("description_excerpt", ""),
            "_query_source": c.get("query_source", "")}


for slug in ["shohei-ohtani", "yoshinobu-yamamoto", "garrett-crochet",
             "mason-miller", "tarik-skubal", "paul-skenes"]:
    path = sorted(glob.glob(f"output/discovery/{slug}/*/candidates.json"))[-1]
    pool = json.load(open(path, encoding="utf-8"))
    print("=" * 110)
    print(slug, len(pool), "candidates")
    rows = []
    for c in pool:
        r = enrich(raw_of(c))
        rows.append((c, r))
    rows.sort(key=lambda t: t[1]["suitability"]["final_score"], reverse=True)
    for c, r in rows[:6]:
        o, n = c["source_type"], r["source_type"]
        mark = " " if o == n else "*"
        print(f" {mark} {r['suitability']['final_score']:.3f} (was "
              f"{c['suitability']['final_score']:.3f}) [{o}->{n}] "
              f"{(c['duration'] or 0)//60:3d}min {c['channel'][:20]:20s} | "
              f"{c['title'][:62]}")
        if o != n or "sanity" in r["suitability"]["duration_sanity_reason"].lower() \
                or "likely" in r["suitability"]["duration_sanity_reason"]:
            print(f"     reason: {r['classification_reason']} | "
                  f"{r['suitability']['duration_sanity_reason']} | "
                  f"risk={r['suitability']['risk_terms']}")
