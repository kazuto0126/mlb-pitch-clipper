"""M4 runner: preview-gate ranked candidates with fallback.

Reads output/discovery/<slug>/<discovery_run>/selected_sources.json
(or candidates.json), previews top-N in rank order, falls back to the next
candidate when one fails. A failure never crashes the run.

Writes output/preview/<pitcher-slug>/<run_id>/:
  preview_manifest.json, source_preview_report.json,
  sources/<video_id>/{segments/, m1m2/, preview_stats.json}
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
from pathlib import Path

from ..discovery.competition import classify_competition
from .gate import preview_source


def run_preview(pitcher_slug: str, selected_path: str, out_root: str,
                max_sources: int = 3, run_id: str | None = None,
                include_non_mlb: bool = False) -> dict:
    selected = json.loads(Path(selected_path).read_text(encoding="utf-8"))
    rid = run_id or _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(out_root) / pitcher_slug / rid
    (out / "sources").mkdir(parents=True, exist_ok=True)

    reports = []
    for cand in selected[:max_sources]:
        cand = dict(cand)
        ctx = classify_competition(cand.get("title", ""),
                                   cand.get("description_excerpt", ""),
                                   cand.get("channel", ""))
        if ctx == "non_mlb" and not include_non_mlb:
            rep_dict = {"video_id": cand.get("video_id", ""),
                        "title": cand.get("title", ""),
                        "channel": cand.get("channel", ""),
                        "source_type": cand.get("source_type", "unknown"),
                        "competition_context": "non_mlb",
                        "preview_status": "skipped",
                        "preview_decision": "reject",
                        "reasons": ["non-MLB competition context: "
                                    "no preview download (production default)"]}
            reports.append(rep_dict)
            sdir = out / "sources" / cand.get("video_id", "noid")
            sdir.mkdir(parents=True, exist_ok=True)
            (sdir / "preview_stats.json").write_text(
                json.dumps(rep_dict, indent=2), encoding="utf-8")
            continue
        try:
            rep = preview_source(cand, str(out / "sources" / cand["video_id"]))
        except Exception as e:  # per-source failure policy: record, continue
            from .schemas import SourcePreview
            rep = SourcePreview(video_id=cand.get("video_id", ""),
                                title=cand.get("title", ""),
                                preview_status="failed",
                                preview_error=str(e)[:300])
            from .gate import decide
            decide(rep)
        rep.competition_context = ctx
        # competition evaluated at decision time: re-apply gate rule
        if ctx == "non_mlb":
            rep.preview_decision = "reject"
            rep.reasons = ["non-MLB competition context excluded from production"] \
                + [r for r in rep.reasons if "acquire:" in r]
        elif ctx == "unknown" and rep.preview_decision == "recommended":
            rep.preview_decision = "borderline"
            rep.reasons.append("competition context unknown (not confirmed MLB)")
        rep_dict = rep.to_dict()
        reports.append(rep_dict)
        (out / "sources" / cand["video_id"] / "preview_stats.json").write_text(
            json.dumps(rep_dict, indent=2), encoding="utf-8")

    summary = {
        "pitcher_slug": pitcher_slug, "run_id": rid,
        "created_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "milestone": 4,
        "sources_previewed": len(reports),
        "recommended": [r["video_id"] for r in reports
                        if r["preview_decision"] == "recommended"],
        "borderline": [r["video_id"] for r in reports
                       if r["preview_decision"] == "borderline"],
        "rejected": [r["video_id"] for r in reports
                     if r["preview_decision"] == "reject"],
    }
    (out / "source_preview_report.json").write_text(
        json.dumps(reports, indent=2), encoding="utf-8")
    (out / "preview_manifest.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    return {"out_dir": str(out), **summary}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pitcher-slug", required=True)
    ap.add_argument("--selected", required=True)
    ap.add_argument("--out-root", default="output/preview")
    ap.add_argument("--max-sources", type=int, default=3)
    ap.add_argument("--include-non-mlb", action="store_true")
    args = ap.parse_args()
    print(json.dumps(run_preview(args.pitcher_slug, args.selected,
                                 args.out_root, args.max_sources,
                                 include_non_mlb=args.include_non_mlb), indent=2))


if __name__ == "__main__":
    main()
