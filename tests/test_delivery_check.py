"""M7.7 delivery check: an event whose motion stays in the batter/catcher
area (right-upper) is not a delivery; motion in the pitcher's area
(left-lower) is kept."""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, ".")

W, H, FPS = 320, 180, 30
PITCHER_AREA = (0.30, 0.60)  # block centre (x, y) inside the pitcher box
BATTER_AREA = (0.62, 0.30)   # block centre inside the batter box


def _video(path: Path, moves: list[tuple[float, float, tuple]]) -> str:
    """moves: (t0, t1, (x, y) centre fractions) — a bright block wobbling
    sideways around that point; static elsewhere."""
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    for i in range(FPS * 12):
        t = i / FPS
        f = np.full((H, W, 3), 60, np.uint8)
        for t0, t1, (cx, cy) in moves:
            if t0 <= t <= t1:
                x = int(W * cx + 12 * np.sin(8 * t))
                y = int(H * cy)
                f[y - 10:y + 10, x - 12:x + 12] = 230
        w.write(f)
    w.release()
    return str(path)


def test_share_follows_where_the_motion_is(tmp_path):
    from src.clipper.delivery_check import pitcher_share
    v = _video(tmp_path / "v.mp4", [(1.0, 3.0, BATTER_AREA), (6.0, 8.0, PITCHER_AREA)])
    assert pitcher_share(v, 1.0, 3.0) < 0.2
    assert pitcher_share(v, 6.0, 8.0) > 0.8


def test_reason_rules():
    from src.clipper.delivery_check import no_delivery_reason
    assert no_delivery_reason(0.38, 3.0)            # batter area dominates
    assert no_delivery_reason(0.43, 3.0) is None    # a left-hander's delivery
    assert no_delivery_reason(0.46, 1.0)            # short, no pitcher dominance
    assert no_delivery_reason(0.46, 2.0) is None    # long enough at 0.46
    assert no_delivery_reason(0.50, 1.0) is None    # short but pitcher moves
    assert no_delivery_reason(None, 0.5) is None    # unreadable: keep


def test_veto_moves_events_and_records_why(tmp_path):
    from src.clipper.delivery_check import apply_delivery_veto
    v = _video(tmp_path / "v.mp4", [(1.0, 3.0, BATTER_AREA), (6.0, 8.0, PITCHER_AREA)])
    d = tmp_path / "m1"
    d.mkdir()
    ev = [{"event_id": "p001", "source_shot_id": "s1", "motion_onset": 1.0, "settle_time": 3.0},
          {"event_id": "p002", "source_shot_id": "s2", "motion_onset": 6.0, "settle_time": 8.0}]
    (d / "events.json").write_text(json.dumps(ev), encoding="utf-8")
    (d / "rejected_events.json").write_text(json.dumps([{"reject_reason": "x"}]), encoding="utf-8")
    r = apply_delivery_veto(str(d), v)
    assert r == {"status": "applied", "checked": 2, "vetoed": ["p001"]}
    kept = json.loads((d / "events.json").read_text(encoding="utf-8"))
    assert [e["event_id"] for e in kept] == ["p002"] and kept[0]["pitcher_share"] > 0.8
    rej = json.loads((d / "rejected_events.json").read_text(encoding="utf-8"))
    assert [x["reject_reason"] for x in rej] == ["x", "no_delivery_suspected"]
    assert rej[1]["detail"].startswith("p001: pitcher area quiet")
    assert rej[1]["event"]["motion_onset"] == 1.0 and rej[1]["event"]["pitcher_share"] < 0.2
