"""Preview evidence states + adaptive expansion policy (M7.1, pure logic).

States (from round stats, global cutoffs calibrated on M4/M7 previews):
- sufficient_good: >=1 M2 complete event (proceed, never expand).
- sufficient_bad: CF >= BAD_CF_MIN with 0 events AND (rejected >=
  BAD_REJECT_MIN OR discontinuity >= BAD_DISC_MIN OR start_incomplete >=
  BAD_START_MIN) — e.g. 29-min montage: 18 CF, 9 start_incomplete.
  Never expands: more downloading cannot fix a bad source.
- insufficient: sparse sample (CF <= SPARSE_CF_MAX, 0 events) or thin
  evidence otherwise — expand before judging.
Failed acquisition is not an evidence state (handled by failure policy).
"""
from __future__ import annotations

SPARSE_CF_MAX = 5
BAD_CF_MIN = 8
BAD_REJECT_MIN = 6
BAD_DISC_MIN = 2
BAD_START_MIN = 4

# Budget caps (global, per source, all three must hold to expand further).
MAX_PREVIEW_SEGMENTS = 10
MAX_PREVIEW_SECONDS = 200.0
MAX_PREVIEW_FRACTION = 0.5
# Short sources may use a third round up to the caps (a 10-min video is
# mostly downloaded by then: judge on coverage, not sampling luck).
SHORT_VIDEO_SEC = 900.0

ROUND2_FRACS = (0.20, 0.40, 0.60, 0.80)
ROUND3_FRACS = (0.05, 0.25, 0.45, 0.65, 0.85)


def classify_evidence(cf_shots: int, complete: int, rejected: int,
                      by_reason: dict) -> tuple[str, str]:
    if complete >= 1:
        return "sufficient_good", f"{complete} complete event(s) observed"
    if cf_shots >= BAD_CF_MIN and (
            rejected >= BAD_REJECT_MIN
            or by_reason.get("shot_discontinuity", 0) >= BAD_DISC_MIN
            or by_reason.get("start_incomplete", 0) >= BAD_START_MIN):
        return "sufficient_bad", (
            f"{cf_shots} CF, 0 events with {rejected} rejections "
            f"{dict(by_reason)}")
    return "insufficient", (
        f"only {cf_shots} CF candidates, 0 events: sample too sparse to judge")


def budget_ok(n_seg: int, seconds: float, duration: float | None) -> bool:
    if n_seg >= MAX_PREVIEW_SEGMENTS or seconds >= MAX_PREVIEW_SECONDS:
        return False
    if duration and duration > 0 and seconds / duration >= MAX_PREVIEW_FRACTION:
        return False
    return True


def expansion_rounds(duration: float | None) -> list[tuple[int, tuple]]:
    """Deterministic extra rounds: always round-2; round-3 only for short
    videos (still capped by budget_ok at runtime)."""
    rounds = [(2, ROUND2_FRACS)]
    if duration is not None and duration <= SHORT_VIDEO_SEC:
        rounds.append((3, ROUND3_FRACS))
    return rounds
