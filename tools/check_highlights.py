"""Highlight/recap-specific before/after check across saved pools."""
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


n_change = 0
for path in sorted(glob.glob("output/discovery/*/*/candidates.json")):
    for c in json.load(open(path, encoding="utf-8")):
        t = c["title"].upper()
        if ("HIGHLIGHT" in t and ("FULL" in t or "RECAP" in t)) or "RECAP" in t \
                or "CINEMATIC" in t or "REWIND" in t:
            r = enrich(raw_of(c))
            flag = " " if c["source_type"] == r["source_type"] else "*"
            print(f"{flag} {c['source_type']:20s} -> {r['source_type']:20s} | "
                  f"{c['suitability']['final_score']:.3f} -> "
                  f"{r['suitability']['final_score']:.3f} | "
                  f"{(c['duration'] or 0)//60}min | {c['title'][:65]}")
            if r["source_type"] != c["source_type"]:
                n_change += 1
                print(f"   reason: {r['classification_reason']} | "
                      f"{r['suitability']['duration_sanity_reason']} | "
                      f"risk={r['suitability']['risk_terms']}")
print("type changes:", n_change)
