"""Validation evaluator: never use training accuracy as success evidence.

Reads ground-truth labels (.jsonl, acceptance schema) and predicted
shots.json (M1 Shot model) and reports:
  - center_field precision / recall (production class)
  - per-class confusion
  - per-pitcher results, per-source results
  - leave-one-pitcher-out splits (and leave-one-source placeholder)

Matching: predicted shot matches a GT shot if IoU over time >= 0.5.
"""
from __future__ import annotations

import argparse
import glob
import json
from collections import Counter, defaultdict
from pathlib import Path


def iou(a0: float, a1: float, b0: float, b1: float) -> float:
    inter = max(0.0, min(a1, b1) - max(a0, b0))
    union = max(a1, b1) - min(a0, b0)
    return inter / union if union > 0 else 0.0


def load_gt(pattern: str) -> list[dict]:
    rows = []
    for f in glob.glob(pattern):
        pitcher = Path(f).stem
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            r.setdefault("pitcher", pitcher)
            rows.append(r)
    return rows


def evaluate(gt: list[dict], preds: list[dict], iou_thresh: float = 0.5) -> dict:
    # match each GT to best overlapping pred
    tp = fp = fn = 0
    per_pitcher: dict[str, Counter] = defaultdict(Counter)
    per_source: dict[str, Counter] = defaultdict(Counter)
    confusion: Counter = Counter()
    matched_pred = set()
    for g in gt:
        best, bestj = -1, 0.0
        for j, p in enumerate(preds):
            v = iou(g["start"], g["end"], p["start"], p["end"])
            if v > bestj:
                best, bestj = j, v
        g_pos = g.get("view") == "center_field_good"
        if best >= 0 and bestj >= iou_thresh:
            matched_pred.add(best)
            p_pos = preds[best]["view_class"] == "center_field_good"
            confusion[(g.get("view"), preds[best]["view_class"])] += 1
            key_p, key_s = g.get("pitcher", "?"), g.get("broadcast_source", "?")
            if g_pos and p_pos:
                tp += 1
                per_pitcher[key_p]["tp"] += 1
                per_source[key_s]["tp"] += 1
            elif g_pos and not p_pos:
                fn += 1
                per_pitcher[key_p]["fn"] += 1
                per_source[key_s]["fn"] += 1
            elif not g_pos and p_pos:
                fp += 1
                per_pitcher[key_p]["fp"] += 1
                per_source[key_s]["fp"] += 1
            else:
                per_pitcher[key_p]["tn"] += 1
                per_source[key_s]["tn"] += 1
        else:
            confusion[(g.get("view"), "<no_match>")] += 1
            if g_pos:
                fn += 1
                per_pitcher[g.get("pitcher", "?")]["fn"] += 1
    # unmatched preds that claim center_field are FPs
    for j, p in enumerate(preds):
        if j not in matched_pred and p["view_class"] == "center_field_good":
            fp += 1
            confusion[("<no_gt>", "center_field_good")] += 1
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    return {
        "center_field_precision": round(prec, 4),
        "center_field_recall": round(rec, 4),
        "tp": tp, "fp": fp, "fn": fn,
        "per_pitcher": {k: dict(v) for k, v in per_pitcher.items()},
        "per_source": {k: dict(v) for k, v in per_source.items()},
        "confusion": [ {"gt": g, "pred": p, "n": n} for (g, p), n in confusion.items()],
    }


def lopo_splits(gt: list[dict]) -> dict[str, list[str]]:
    """Leave-one-pitcher-out: {held_out_pitcher: [train pitchers]}."""
    pitchers = sorted({g.get("pitcher", "?") for g in gt})
    return {p: [q for q in pitchers if q != p] for p in pitchers}


def loso_splits(gt: list[dict]) -> dict[str, list[str]]:
    """Leave-one-source/broadcast-out placeholder (same shape as LOPO)."""
    sources = sorted({g.get("broadcast_source", "?") for g in gt})
    return {s: [t for t in sources if t != s] for s in sources}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", required=True, help="glob, e.g. validation/.../labels/*.jsonl")
    ap.add_argument("--preds", required=True, help="shots.json from M1 pipeline")
    args = ap.parse_args()
    gt = load_gt(args.labels)
    preds = json.loads(open(args.preds, encoding="utf-8").read())
    out = evaluate(gt, preds)
    out["lopo"] = lopo_splits(gt)
    out["loso_broadcast"] = loso_splits(gt)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
