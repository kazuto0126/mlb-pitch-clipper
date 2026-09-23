"""M3 runner: pitcher name -> ranked candidates -> selected_sources.json.

Writes output/discovery/<pitcher-slug>/<run_id>/:
  candidates.json, selected_sources.json, discovery_manifest.json
No download in this milestone.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
from pathlib import Path

from .dedup import dedup
from .fetch import fetch_candidates
from .queries import build_queries
from .select import enrich, select_sources


def slug(name: str) -> str:
    return "-".join(name.lower().split())


def run_discovery(pitcher_name: str, out_root: str = "output/discovery",
                  top_n: int = 3, per_query_limit: int = 5,
                  run_id: str | None = None) -> dict:
    queries = build_queries(pitcher_name, per_query_limit)
    hits = fetch_candidates(queries)
    raws = dedup(hits)
    cands = [enrich(r) for r in raws]
    selected = select_sources(cands, top_n)

    rid = run_id or _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(out_root) / slug(pitcher_name) / rid
    out.mkdir(parents=True, exist_ok=True)
    (out / "candidates.json").write_text(json.dumps(cands, indent=2), encoding="utf-8")
    (out / "selected_sources.json").write_text(json.dumps(selected, indent=2),
                                               encoding="utf-8")
    manifest = {
        "pitcher": pitcher_name, "run_id": rid,
        "created_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "milestone": 3,
        "queries": [q["query"] for q in queries],
        "raw_hits": len(hits), "unique_candidates": len(cands),
        "top_n": top_n,
        "selected_ids": [s["video_id"] for s in selected],
    }
    (out / "discovery_manifest.json").write_text(json.dumps(manifest, indent=2),
                                                 encoding="utf-8")
    return {"out_dir": str(out), **manifest}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pitcher")
    ap.add_argument("--top-n", type=int, default=3)
    ap.add_argument("--per-query-limit", type=int, default=5)
    args = ap.parse_args()
    print(json.dumps(run_discovery(args.pitcher, top_n=args.top_n,
                                   per_query_limit=args.per_query_limit), indent=2))


if __name__ == "__main__":
    main()
