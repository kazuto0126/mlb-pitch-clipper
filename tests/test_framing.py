"""M7.6 tests: per-source CF framing consistency veto (synthetic embeddings,
no CLIP weights needed)."""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, ".")


def _scores(margin):
    cf = 0.5 + margin / 2
    return {"center_field_good": cf, "side_fullbody_acceptable": cf - margin,
            "closeup_bad": 0.0, "batter_bad": 0.0, "field_bad": 0.0,
            "graphic_bad": 0.0, "other_bad": 0.0}


def _m1_dir(tmp_path, n_proto=6, with_emb=True):
    """n_proto confident CF shots sharing one framing, plus an on-framing
    low-margin shot (keep), an off-framing shot (veto) and a rejected shot."""
    rng = np.random.default_rng(0)
    cf_dir = np.zeros(16)
    cf_dir[0] = 1.0
    off_dir = np.zeros(16)
    off_dir[1] = 1.0
    shots, ids, embs = [], [], []
    def add(sid, margin, vec, accepted=True):
        shots.append({"shot_id": sid, "start": 0.0, "end": 5.0, "scores": _scores(margin),
                      "accepted_for_pitch_detection": accepted,
                      "reject_reason": None if accepted else "low_view_confidence"})
        ids.append(sid)
        embs.append(vec + rng.normal(0, 0.05, 16))
    for i in range(n_proto):
        add(f"s{i:03d}", 0.8, cf_dir)
    add("s100", 0.45, cf_dir)          # same framing, indecisive text scores
    add("s101", 0.70, off_dir)         # confident text scores, other camera
    add("s102", 0.10, off_dir, accepted=False)
    d = tmp_path / "m1"
    d.mkdir()
    (d / "shots.json").write_text(json.dumps(shots), encoding="utf-8")
    (d / "candidates.json").write_text(json.dumps([s for s in shots if s["accepted_for_pitch_detection"]]),
                                       encoding="utf-8")
    if with_emb:
        np.savez_compressed(d / "embeddings.npz", ids=np.array(ids), embs=np.stack(embs).astype(np.float16))
    return d


def test_off_framing_shot_vetoed_on_framing_kept(tmp_path):
    from src.clipper.framing import apply_framing_veto
    d = _m1_dir(tmp_path)
    r = apply_framing_veto(str(d))
    assert r["status"] == "applied" and r["vetoed"] == ["s101"]
    shots = {s["shot_id"]: s for s in json.loads((d / "shots.json").read_text(encoding="utf-8"))}
    assert shots["s101"]["reject_reason"] == "framing_inconsistent"
    assert shots["s100"]["accepted_for_pitch_detection"] is True
    assert shots["s100"]["framing_knn"] > 0.9
    cands = {s["shot_id"] for s in json.loads((d / "candidates.json").read_text(encoding="utf-8"))}
    assert "s101" not in cands and "s100" in cands
    assert shots["s102"]["reject_reason"] == "low_view_confidence"  # untouched


def test_skipped_without_enough_prototypes(tmp_path):
    from src.clipper.framing import FRAMING_MIN_PROTO, apply_framing_veto
    # s101 (margin 0.70) is itself a prototype: total = n_proto + 1
    d = _m1_dir(tmp_path, n_proto=FRAMING_MIN_PROTO - 2)
    before = (d / "candidates.json").read_text(encoding="utf-8")
    r = apply_framing_veto(str(d))
    assert r["status"].startswith("skipped") and r["vetoed"] == []
    assert (d / "candidates.json").read_text(encoding="utf-8") == before


def test_skipped_without_embeddings(tmp_path):
    from src.clipper.framing import apply_framing_veto
    d = _m1_dir(tmp_path, with_emb=False)
    r = apply_framing_veto(str(d))
    assert r == {"status": "skipped: no embeddings", "checked": 0, "vetoed": []}


def test_prototype_is_leave_one_out(tmp_path):
    # exactly FRAMING_MIN_PROTO prototypes (MIN-1 on-framing + s101): a
    # prototype has only MIN-1 others -> not scored (never compared with
    # itself), while the non-prototype s100 sees all MIN -> scored
    from src.clipper.framing import FRAMING_MIN_PROTO, framing_scores
    d = _m1_dir(tmp_path, n_proto=FRAMING_MIN_PROTO - 1)
    shots = json.loads((d / "shots.json").read_text(encoding="utf-8"))
    z = np.load(d / "embeddings.npz")
    sc = framing_scores(shots, [str(i) for i in z["ids"]], z["embs"])
    assert "s000" not in sc and "s101" not in sc and "s100" in sc


def test_pipeline_saves_embeddings_when_classifier_provides_them(tmp_path, monkeypatch):
    import cv2
    from src.clipper import pipeline
    from src.clipper.view_classifier import ViewResult
    v = str(tmp_path / "v.mp4")
    w = cv2.VideoWriter(v, cv2.VideoWriter_fourcc(*"mp4v"), 10, (160, 120))
    for i in range(30):
        w.write(np.full((120, 160, 3), 40 if i < 15 else 200, dtype=np.uint8))
    w.release()

    class Fake:
        backend = "fake"

        def classify(self, frames):
            sc = {k: 0.0 for k in _scores(0.0)}
            sc["other_bad"] = 1.0
            return ViewResult("other_bad", 1.0, sc, "fake", embedding=np.ones(8, np.float32))

    monkeypatch.setattr(pipeline, "load_classifier", lambda prefer_clip=True: Fake())
    pipeline.run_pipeline(v, str(tmp_path / "out"))
    z = np.load(tmp_path / "out" / "embeddings.npz")
    assert len(z["ids"]) == len(json.loads((tmp_path / "out" / "shots.json").read_text(encoding="utf-8")))
