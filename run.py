"""Product entry: python run.py "Shohei Ohtani" [--top-n 3] [--year 2026]

Full automatic chain (no manual steps):
  M3 discovery -> M4 preview gate -> full acquisition -> M1 -> M2 ->
  clips -> conservative dedup -> chronological merge -> <Name>_<Year>.mp4

Ranking/selection/gate/M1/M2 reused frozen; per-source failures fall back
to the next eligible source; total failure yields no_suitable_source
manifest instead of a stack trace.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
from pathlib import Path

from src.clipper.acquisition.run_preview import run_preview
from src.clipper.discovery.competition import classify_competition
from src.clipper.discovery.run_discovery import run_discovery, slug
from src.clipper.production.manifest import FEW_CLIPS
from src.clipper.production.naming import reliable_game_year
from src.clipper.production.run_source import produce_source


def year_filter_ok(s: dict, year: int) -> bool:
    """--year: only a high/medium game year can mismatch. low (published
    year) / null are unknown and kept, except a video can't show a game
    played after it was published: published year < year excludes."""
    gy = reliable_game_year(s.get("game_year"), s.get("game_year_confidence"))
    if gy is not None:
        return gy == year
    pub = (s.get("published_date") or "")[:4]
    return not (pub.isdigit() and int(pub) < year)


INSUFFICIENT_FALLBACK = "insufficient_evidence_fallback"


def _insufficient_fallback_ok(rep: dict) -> bool:
    """Preview too sparse to judge (not evidence of a bad source): CF seen,
    MLB/unknown context, acquisition worked. sufficient_bad, zero-CF,
    non-MLB and failed previews stay vetoed."""
    return (rep.get("preview_decision") == "reject"
            and rep.get("evidence_state") == "insufficient"
            and (rep.get("center_field_shots") or 0) > 0
            and rep.get("competition_context", "unknown") in ("mlb", "unknown")
            and rep.get("preview_status") in ("ok", "partial"))


def _min_final_clips(mode: str, rep: dict) -> int:
    """Sources the preview never saw a complete event in (insufficient tier,
    borderline on CF alone) must prove themselves in the full run: 1-2 clip
    outputs from them were mostly wrong views (M7.3 audit: 1/4 good)."""
    if mode == INSUFFICIENT_FALLBACK:
        return FEW_CLIPS
    if mode == "borderline_fallback" and not rep.get("m2_complete_events"):
        return FEW_CLIPS
    return 1


def pick_sources(selected: list[dict], preview_reports: list[dict]) -> tuple[list[dict], str]:
    """Tiered pool: recommended -> borderline MLB/unknown -> insufficient-
    evidence rejects (M7.3). Each candidate carries min_final_clips (see
    _min_final_clips). Returns (pool, mode of the first tier present)."""
    by_id = {r["video_id"]: r for r in preview_reports}

    def rep(s):
        return by_id.get(s["video_id"], {})

    def score(s):
        return (s.get("suitability") or {}).get("final_score", 0.0)

    rec = [s for s in selected if rep(s).get("preview_decision") == "recommended"]
    border = [s for s in selected if rep(s).get("preview_decision") == "borderline"
              and rep(s).get("competition_context", "unknown") in ("mlb", "unknown")]
    insuff = [s for s in selected if _insufficient_fallback_ok(rep(s))]
    # order: M2 preview evidence (events), then M3 score; the insufficient
    # tier has no events by definition, so preview CF evidence comes first.
    tiers = [
        ("recommended", sorted(rec, key=lambda s: (
            rep(s).get("m2_complete_events", 0), score(s)), reverse=True)),
        ("borderline_fallback", sorted(border, key=lambda s: (
            rep(s).get("m2_complete_events", 0), score(s)), reverse=True)),
        (INSUFFICIENT_FALLBACK, sorted(insuff, key=lambda s: (
            rep(s).get("center_field_shots", 0), score(s)), reverse=True)),
    ]
    pool = []
    for mode, group in tiers:
        for s in group:
            s["preview_decision"] = rep(s).get("preview_decision")
            s["competition_context"] = rep(s).get("competition_context", "unknown")
            s["source_selection_mode"] = mode
            s["min_final_clips"] = _min_final_clips(mode, rep(s))
            pool.append(s)
    mode = pool[0]["source_selection_mode"] if pool else "borderline_fallback"
    return pool, mode


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pitcher")
    ap.add_argument("--top-n", type=int, default=3)
    ap.add_argument("--max-sources", type=int, default=3)
    ap.add_argument("--year", type=int, default=None)
    ap.add_argument("--keep-source", action="store_true")
    ap.add_argument("--diagnostics", action="store_true")
    ap.add_argument("--out-root", default="output")
    args = ap.parse_args()

    rid = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = Path(args.out_root) / slug(args.pitcher) / rid
    (root / "sources").mkdir(parents=True, exist_ok=True)

    # 0. pre-flight: fail fast with a clear message, never mid-pipeline.
    from src.clipper.production.preflight import check as preflight_check
    problems = preflight_check()
    if problems:
        manifest = {"pitcher": args.pitcher, "run_id": rid,
                    "status": "environment_error",
                    "reason": "; ".join(problems)}
        (root / "run_manifest.json").write_text(json.dumps(manifest, indent=2),
                                                encoding="utf-8")
        print(json.dumps(manifest, indent=2))
        raise SystemExit(2)

    try:
        return _run_chain(args, rid, root)
    except Exception as e:  # last-resort guard: manifest, not a bare trace
        manifest = {"pitcher": args.pitcher, "run_id": rid,
                    "status": "run_error",
                    "reason": f"{type(e).__name__}: {str(e)[:300]}"}
        try:
            (root / "run_manifest.json").write_text(json.dumps(manifest, indent=2),
                                                    encoding="utf-8")
        except Exception:
            pass
        print(json.dumps(manifest, indent=2))
        raise SystemExit(1)


def _run_chain(args, rid: str, root: Path):
    # 1. discovery (frozen M3)
    disc = run_discovery(args.pitcher, out_root=str(Path(args.out_root) / "discovery"),
                         top_n=args.top_n, run_id=rid)
    selected = json.loads(Path(disc["out_dir"], "selected_sources.json")
                          .read_text(encoding="utf-8"))
    if args.year is not None:
        filt = [s for s in selected if year_filter_ok(s, args.year)]
        selected = filt or selected
    # production competition filter (frozen rule: non_mlb never produces)
    eligible = [s for s in selected if classify_competition(
        s.get("title", ""), s.get("description_excerpt", ""),
        s.get("channel", "")) != "non_mlb"]
    if not eligible:
        manifest = {"pitcher": args.pitcher, "run_id": rid, "status": "no_suitable_source",
                    "reason": "all discovery candidates non-MLB context",
                    "milestone": 7,
                    "discovery": {"candidate_count": len(selected),
                                  "selected_count": 0}}
        (root / "run_manifest.json").write_text(json.dumps(manifest, indent=2),
                                                encoding="utf-8")
        print(json.dumps(manifest, indent=2))
        return

    # 2. preview gate (frozen M4) over eligible in rank order
    prev = run_preview(slug(args.pitcher),
                       _write_tmp_selected(eligible, root),
                       str(Path(args.out_root) / "preview"),
                       max_sources=min(args.max_sources, len(eligible)),
                       run_id=rid)
    reports = json.loads(Path(prev["out_dir"], "source_preview_report.json")
                         .read_text(encoding="utf-8"))
    pool, mode = pick_sources(eligible, reports)
    if not pool:
        manifest = {"pitcher": args.pitcher, "run_id": rid, "status": "no_suitable_source",
                    "reason": "preview gate admitted no source",
                    "milestone": 7,
                    "source_selection_mode": mode,
                    "discovery": {"candidate_count": len(selected),
                                  "selected_count": 0}}
        (root / "run_manifest.json").write_text(json.dumps(manifest, indent=2),
                                                encoding="utf-8")
        print(json.dumps(manifest, indent=2))
        return

    # 3. production with fallback across pool
    taken: set = set()
    results = []
    for cand in pool:
        try:
            man = produce_source(args.pitcher, cand,
                                 str(root / "sources" / cand["video_id"]), taken,
                                 min_final_clips=cand.get("min_final_clips", 1))
        except Exception as e:  # never crash the run on one source
            man = {"pitcher_name": args.pitcher, "video_id": cand.get("video_id", ""),
                   "source_selection_mode": cand["source_selection_mode"],
                   "status": f"failed-exception: {str(e)[:200]}"}
        results.append(man)
        if man.get("status") == "ok":
            break
    ok = [m for m in results if m.get("status") == "ok"]
    if ok:  # run-level mode = tier that actually produced the output
        mode = ok[0].get("source_selection_mode", mode)
    dl_failed = [m for m in results
                 if (m.get("status") or "").startswith("failed-download")]
    if ok:
        status = "ok"
    elif dl_failed and len(dl_failed) == len(results):
        status = "acquisition_failed"
    else:
        status = "no_suitable_source"
    manifest = {
        "pitcher": args.pitcher, "run_id": rid,
        "created_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "milestone": 7, "source_selection_mode": mode,
        "discovery": {"candidate_count": len(selected),
                      "selected_count": len(pool)},
        "sources_attempted": [m.get("video_id") for m in results],
        "status": status,
        "finals": [m.get("final_path") for m in ok],
        "results": results,
    }
    (root / "run_manifest.json").write_text(json.dumps(manifest, indent=2),
                                            encoding="utf-8")
    print(json.dumps({k: v for k, v in manifest.items() if k != "results"}, indent=2))


def _write_tmp_selected(eligible: list[dict], root: Path) -> str:
    p = root / "_eligible_selected.json"
    p.write_text(json.dumps(eligible, indent=2), encoding="utf-8")
    return str(p)


if __name__ == "__main__":
    main()
