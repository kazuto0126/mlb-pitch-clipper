"""Build output/generalization/m6_report.json + .md (audit-only aggregation)."""
import json
import sys

sys.path.insert(0, ".")

from src.clipper.production.reporting import build_rows

YAMAMOTO_Q8 = {
    "pitcher": "Yoshinobu Yamamoto", "run": "20260923T005044Z (M5 baseline)",
    "video_id": "Q8Bl2X4VKuw", "source_type": "full_start",
    "competition_context": "mlb", "game_year": 2025,
    "source_selection_mode": "borderline_fallback",
    "shot_count": 405, "center_field_candidates": 310,
    "complete_events": 25, "rejected_start_incomplete": 95,
    "rejected_end_incomplete": 52, "rejected_no_complete_pitch": 100,
    "rejected_discontinuity": 5, "raw_clip_count": 25,
    "duplicate_rejected": 3, "replay_rejected": 0, "final_clip_count": 22,
    "final_duration_sec": 87.2, "final_filename": "Yoshinobu_Yamamoto_2025.mp4",
    "codec": "h264,yuv420p", "resolution": "1280x720",
    "full_video_duration_sec": 2603, "quality_warning": False,
    "audit": "2 clips sampled: both complete CF pitches; 3 dup pairs removed "
             "(4s gaps, plausible live+replay)",
}


def load_run(slug, run):
    m = json.load(open(f"output/{slug}/{run}/run_manifest.json"))
    outs = []
    for r in m.get("results", []):
        q = r.get("quality_summary", {}) or {}
        outs.append({
            "pitcher": m["pitcher"], "run": run,
            "video_id": r.get("video_id"), "source_type": "see-manifest",
            "competition_context": r.get("competition_context"),
            "game_year": r.get("game_year"),
            "source_selection_mode": r.get("source_selection_mode"),
            "shot_count": r.get("shot_count"),
            "center_field_candidates": r.get("center_field_candidates"),
            "complete_events": r.get("complete_events"),
            "rejected_start_incomplete": q.get("rejected_start_incomplete"),
            "rejected_end_incomplete": q.get("rejected_end_incomplete"),
            "rejected_no_complete_pitch": q.get("rejected_no_complete_pitch"),
            "rejected_discontinuity": q.get("rejected_discontinuity"),
            "raw_clip_count": r.get("raw_clip_count"),
            "duplicate_rejected": r.get("duplicate_rejected"),
            "replay_rejected": r.get("replay_rejected"),
            "final_clip_count": r.get("final_clip_count"),
            "final_duration_sec": r.get("final_duration_sec"),
            "final_filename": r.get("final_path"),
            "codec": r.get("final_codec"), "resolution": "1280x720",
            "full_video_duration_sec": None,
            "quality_warning": q.get("quality_warning"),
        })
    return outs


rows = [YAMAMOTO_Q8]
rows += load_run("paul-skenes", "20260923T095225Z")
rows += load_run("shohei-ohtani", "20260923T100612Z")
rows += load_run("garrett-crochet", "20260923T104950Z")
rows += load_run("mason-miller", "20260923T111351Z")
# source durations + types from discovery/manifests
DURS = {"Q8Bl2X4VKuw": 2603, "q2dSaXzowlw": 300, "av5KQk1HNbc": 2196,
        "myyfpqlODso": 1380, "q7ndAVBppQQ": 660}
TYPES = {"Q8Bl2X4VKuw": "full_start", "q2dSaXzowlw": "every_pitch",
         "av5KQk1HNbc": "full_outing", "myyfpqlODso": "every_pitch",
         "q7ndAVBppQQ": "every_pitch-reliever"}
for r in rows:
    r["full_video_duration_sec"] = DURS.get(r["video_id"])
    r["source_type"] = TYPES.get(r["video_id"], r["source_type"])
AUDIT = {
    "Q8Bl2X4VKuw": "SUCCESS-clean: 2 sampled clips complete CF; 3 dup pairs "
                   "(~4s gaps, plausible live+replay)",
    "q2dSaXzowlw": "SUCCESS-clean: 3/3 complete CF incl. 101mph K of Ohtani; "
                   "top-1 matchup video correctly gate-rejected first",
    "av5KQk1HNbc": "PARTIAL: 16 clips but 2-3 sampled segments wrong-view "
                   "(batter close-ups from missed dissolves s005/s030 + "
                   "low-conf CF s079 0.37)",
    "myyfpqlODso": "PARTIAL: 8 clips but 2 sampled non-pitch (close-up+graphic, "
                   "dugout; WEEI heavy packaging); LHP handling itself fine",
    "q7ndAVBppQQ": "SUCCESS-clean: 2 sampled complete CF (reliever works); "
                   "CAUTION: 1 likely false-dup deletion (p013 358s from p003, "
                   "fixed-camera similarity) — see §8",
}
for r in rows:
    r["audit_note"] = AUDIT.get(r["video_id"], "")
rows = build_rows(rows)
json.dump(rows, open("output/generalization/m6_report.json", "w",
                     encoding="utf-8"), indent=2)

L = ["# M6 Cross-Pitcher Generalization Report",
     "",
     "failure_taxonomy = high-level failure bucket (UNKNOWN on success rows "
     "means no failure bucket matched); audit_note = human spot-check verdict.",
     "", "| pitcher | source (type/year) | shots→CF→events→final | "
     "final | yield | taxonomy | audit |",
     "|---|---|---|---|---|---|---|"]
for r in rows:
    L.append(f"| {r['pitcher']} | {r['video_id']} ({r['source_type']}/{r['game_year']}) "
             f"| {r['shot_count']}→{r['center_field_candidates']}→"
             f"{r['complete_events']}→{r['final_clip_count']} "
             f"| {r['final_filename']} {r['final_duration_sec']}s "
             f"| CF {r['center_field_rate']} / done {r['complete_yield']} "
             f"| {r['failure_taxonomy']} | {r['audit_note']} |")
open("output/generalization/m6_report.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L))
