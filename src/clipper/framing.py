"""Per-source center-field framing consistency (M7.6, production only).

A broadcast's center-field camera framing is nearly constant through a
source. Each accepted CF shot is compared with the SAME source's confident
CF shots (class margin >= FRAMING_PROTO_MARGIN, leave-one-out) in CLIP
image-embedding space (the embedding M1 already computes; no new model,
no body/face/identity features). Mean cosine to the FRAMING_K nearest
prototype shots below FRAMING_MIN_KNN -> reject_reason
framing_inconsistent.

Evidence (validation/regression_cases/m7_6_framing_consistency/): over 16
audited sources, 9 wrong-view delivered clips (batter close-ups, reverse
angles, pitcher close-ups) scored 0.695-0.882 while all 63 correct
delivered clips scored >= 0.950; a re-downloaded sample of shots below
0.92 was 18/20 not CF (the two true CF at 0.904/0.911 stay above 0.90).

Skipped (everything kept) when the source has fewer than FRAMING_MIN_PROTO
prototype shots or no embeddings (heuristic backend). Not applied in the
preview gate: 20-second preview segments rarely hold enough prototypes.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .shot_purity import class_margin

FRAMING_PROTO_MARGIN = 0.6
FRAMING_MIN_PROTO = 5
FRAMING_K = 3
FRAMING_MIN_KNN = 0.90


def framing_scores(shots: list[dict], ids: list[str], embs: np.ndarray) -> dict[str, float]:
    """kNN cosine to the source's prototype CF shots for each accepted shot
    with an embedding; shots without enough prototypes are left out."""
    row = {sid: i for i, sid in enumerate(ids)}
    E = embs.astype(np.float32)
    E = E / np.maximum(np.linalg.norm(E, axis=1, keepdims=True), 1e-8)
    accepted = [s for s in shots if s.get("accepted_for_pitch_detection") and s["shot_id"] in row]
    proto = [s["shot_id"] for s in accepted if class_margin(s.get("scores")) >= FRAMING_PROTO_MARGIN]
    out: dict[str, float] = {}
    for s in accepted:
        others = [row[p] for p in proto if p != s["shot_id"]]
        if len(others) < FRAMING_MIN_PROTO:
            continue
        sims = E[others] @ E[row[s["shot_id"]]]
        out[s["shot_id"]] = round(float(np.sort(sims)[-FRAMING_K:].mean()), 4)
    return out


def apply_framing_veto(m1_dir: str) -> dict:
    """Rewrite m1_dir/shots.json + candidates.json with the framing veto.

    Returns {"status", "checked", "vetoed": [shot_id, ...]}."""
    d = Path(m1_dir)
    emb_path = d / "embeddings.npz"
    if not emb_path.exists():
        return {"status": "skipped: no embeddings", "checked": 0, "vetoed": []}
    shots = json.loads((d / "shots.json").read_text(encoding="utf-8"))
    z = np.load(emb_path)
    scores = framing_scores(shots, [str(i) for i in z["ids"]], z["embs"])
    if not scores:
        return {"status": f"skipped: < {FRAMING_MIN_PROTO} prototype CF shots",
                "checked": 0, "vetoed": []}
    vetoed = []
    for s in shots:
        if s["shot_id"] in scores:
            s["framing_knn"] = scores[s["shot_id"]]
            if scores[s["shot_id"]] < FRAMING_MIN_KNN:
                s["accepted_for_pitch_detection"] = False
                s["reject_reason"] = "framing_inconsistent"
                vetoed.append(s["shot_id"])
    cands = [s for s in shots if s.get("accepted_for_pitch_detection")]
    (d / "shots.json").write_text(json.dumps(shots, indent=2), encoding="utf-8")
    (d / "candidates.json").write_text(json.dumps(cands, indent=2), encoding="utf-8")
    return {"status": "applied", "checked": len(scores), "vetoed": vetoed}
