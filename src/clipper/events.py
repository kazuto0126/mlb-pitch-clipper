"""M2 event localization: PREPARED -> MOTION_ACTIVE -> POST_MOTION -> SETTLED.

High-level temporal states only. No body-part states (no leg_lift,
arm_cock, stride, release mechanics, ...). motion_peak is a temporal
anchor, not a biomechanical release point.

Reject-first: missing either side -> reject, never pad across shots.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from .motion import MotionTrack

# Tunables (global — never per-pitcher). Frozen M2 values kept as CFG0.
LOW = 0.30        # below: quiet / prepared
HIGH = 0.45       # above: active motion
MIN_PREPARED = 0.5   # seconds of quiet required before onset
MIN_ACTIVE = 0.8     # seconds of sustained activity required
MIN_SETTLE = 0.6     # seconds of stable regime required after decay
PRE_BUFFER = 1.0     # clip_start = onset - PRE_BUFFER (clamped to shot/prepared)
POST_BUFFER = 0.4    # clip_end = settle + POST_BUFFER (clamped to shot)
MAX_EVENTS_PER_SHOT = 2
QUIET_ANCHOR = 0.3   # scan starts at the first sustained-quiet run; anything
                     # hotter before it is cut-transition/unprepared motion
PRE_HEAT_MIN = 0.8   # opening heat this long => shot opens mid-action
DECAY_RATIO = 0.5    # relative completion: post level must fall to
                     # max(LOW, peak * DECAY_RATIO), not to near-zero


@dataclass(frozen=True)
class EventParams:
    """Global-only parameter set (no pitcher/source fields exist by design)."""
    low: float = LOW
    high: float = HIGH
    min_prepared: float = MIN_PREPARED
    min_active: float = MIN_ACTIVE
    min_settle: float = MIN_SETTLE
    pre_buffer: float = PRE_BUFFER
    post_buffer: float = POST_BUFFER
    max_events: int = MAX_EVENTS_PER_SHOT
    quiet_anchor: float = QUIET_ANCHOR
    pre_heat_min: float = PRE_HEAT_MIN
    decay_ratio: float = DECAY_RATIO
    relative: bool = False  # False = frozen absolute settle (CFG0)
    gap_bridge: float = 0.3  # bridge sub-threshold dips this long inside
                             # one active blob (delivery wobble, calibrated)
    edge_skip: float = 0.3  # trailing samples hold cut-transition spikes;
                            # invisible to the stability scan (structural)
    edge_min_stable: float = 0.25  # min calm after decay when the shot ends
                                   # during a stable regime (structural)


DEFAULT_PARAMS = EventParams(  # M4.5 calibration winner (LOPO F1 0.40,
    relative=True, high=0.45, decay_ratio=0.7,  # prec 0.75, 30 negatives -> 1 FP;
    min_settle=0.6, gap_bridge=0.5, min_prepared=0.8,  # start-cut relabels all rejected
)  # global-only: no pitcher/source fields exist by design


@dataclass
class PitchEvent:
    event_id: str
    source_shot_id: str
    clip_start: float
    motion_onset: float
    motion_peak: float | None
    settle_time: float
    clip_end: float
    confidence: float
    complete: bool = True
    reject_reason: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RejectedWindow:
    source_shot_id: str
    reject_reason: str
    detail: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _prep_bounds(sm, ts, o, i, low, gap=0.2):
    """Bridged quiet run ending at o-1, bounded by scan cursor i.

    Brief above-LOW wobble (< gap seconds each) inside preparation does not
    break the run (batter/umpire/camera micro-motion during a visible set).
    Returns (qs, qe) or None when no quiet sample exists.
    """
    qe = o - 1
    q = qe
    start = None
    while q >= i:
        if sm[q] <= low:
            start = q
            q -= 1
        else:
            g1 = q
            while q >= i and sm[q] > low:
                q -= 1
            if q >= i and sm[q] <= low and ts[g1] - ts[q + 1] < gap:
                start = q  # bridge short wobble, extend through it
                q -= 1
            else:
                break
    if start is None:
        return None
    return start, qe


def localize(
    shot_id: str,
    shot_start: float,
    shot_end: float,
    track: MotionTrack,
    event_id_prefix: str = "p",
    start_count: int = 1,
    params: EventParams | None = None,
) -> tuple[list[PitchEvent], list[RejectedWindow]]:
    """Scan one candidate shot for 0..N complete pitch patterns."""
    P = params or DEFAULT_PARAMS
    LOW_, HIGH_ = P.low, P.high
    events: list[PitchEvent] = []
    rejected: list[RejectedWindow] = []
    n = len(track.times)
    if n < 5 or (shot_end - shot_start) < 1.5:
        rejected.append(RejectedWindow(shot_id, "shot_too_short",
                                       f"samples={n} dur={shot_end - shot_start:.2f}"))
        return events, rejected

    sm, ts = track.smoothed, track.times
    if all(v > LOW_ for v in sm):
        rejected.append(RejectedWindow(shot_id, "start_incomplete",
                                       "hot throughout, never prepared"))
        return events, rejected

    ev_n = start_count
    # anchor: first sustained-quiet run; pre-anchor heat is untrusted
    # (cut transition or mid-action entry), never used as preparation.
    i = None
    k = 0
    while k < n:
        if sm[k] <= LOW_:
            e = k
            while e < n and sm[e] <= LOW_:
                e += 1
            if ts[e - 1] - ts[k] >= P.quiet_anchor:
                i = k
                break
            k = e
        else:
            k += 1
    if i is None:
        rejected.append(RejectedWindow(shot_id, "start_incomplete",
                                       "hot throughout, never prepared"))
        return events, rejected
    saw_prepared = True  # anchored: sustained quiet observed (prep TBD per onset)
    pre_heat = ts[i] - shot_start
    while i < n:
        # onset: first sample above LOW at/after i
        o = next((k for k in range(i, n) if sm[k] > LOW_), None)
        if o is None:
            break
        # trailing quiet run ending at o-1 (bounded by scan cursor i);
        # relative path bridges micro-wobble inside preparation.
        if P.relative:
            bounds = _prep_bounds(sm, ts, o, i, LOW_)
            prep = (ts[bounds[1]] - ts[bounds[0]]) if bounds else 0.0
            qs = bounds[0] if bounds else o
        else:
            qe = o - 1
            qs = qe
            while qs >= i and sm[qs] <= LOW_:
                qs -= 1
            qs += 1
            prep = (ts[qe] - ts[qs]) if qe >= qs else 0.0
        if prep >= P.min_prepared:
            saw_prepared = True
        if prep < P.min_prepared:
            if not P.relative and ts[o] - shot_start < P.min_prepared + P.quiet_anchor:
                rejected.append(RejectedWindow(
                    shot_id, "start_incomplete",
                    f"onset@{ts[o]:.2f} without prepared interval"))
                return events, rejected
            # relative: forgive a head transition blip and keep scanning;
            # a genuinely hot open still ends as start_incomplete via
            # pre_heat (no quiet ever anchors a pattern).
            # mid-shot blip without preparation: skip the active blob
            j = o
            while j < n and sm[j] > LOW_:
                j += 1
            i = j
            continue
        if P.relative:
            nxt = _relative_event(shot_id, shot_start, shot_end, sm, ts,
                                  o, qs, prep, ev_n, event_id_prefix, P)
        else:
            nxt = _absolute_event(shot_id, shot_start, shot_end, sm, ts,
                                  o, qs, prep, ev_n, event_id_prefix, P)
        kind, payload, i = nxt
        if kind == "event":
            events.append(payload)
            ev_n += 1
            if len(events) >= P.max_events:
                break
        elif kind == "reject":
            rejected.append(payload)
            return events, rejected
        # kind == "skip": keep scanning at i
    if not events and not rejected:
        if pre_heat >= P.pre_heat_min:
            rejected.append(RejectedWindow(shot_id, "start_incomplete",
                                           f"opens mid-action ({pre_heat:.2f}s heat)"))
        else:
            rejected.append(RejectedWindow(shot_id, "no_complete_pitch", "no full pattern"))
    return events, rejected


def _absolute_event(shot_id, shot_start, shot_end, sm, ts, o, qs, prep,
                    ev_n, prefix, P):
    """Frozen completion: settle = uninterrupted run below LOW."""
    n = len(ts)
    HIGH_ = P.high
    LOW_ = P.low
    a = o
    while a < n and sm[a] > LOW_:
        a += 1
    active_dur = ts[a - 1] - ts[o]
    has_high = any(v >= HIGH_ for v in sm[o:a])
    if not has_high or active_dur < P.min_active:
        return "skip", None, a
    peak = max(range(o, a), key=lambda k: sm[k])
    if a >= n:
        return ("reject", RejectedWindow(shot_id, "end_incomplete",
                f"onset@{ts[o]:.2f} motion runs into cut"), a)
    s = a
    while s < n and sm[s] <= LOW_:
        s += 1
    settle_dur = ts[s - 1] - ts[a] if s > a else 0.0
    if settle_dur < P.min_settle:
        if s >= n:
            return ("reject", RejectedWindow(
                shot_id, "end_incomplete",
                f"onset@{ts[o]:.2f} settle too short before cut"), s)
        return "skip", None, s
    return ("event", _make_event(shot_id, prefix, ev_n, shot_start, shot_end,
                                 ts, qs, o, peak, ts[a], settle_dur, prep,
                                 active_dur, P), s)


def _blob_end(sm, ts, o, P):
    """End (exclusive) of the >LOW blob containing o, bridging quiet gaps
    shorter than gap_bridge (delivery wobble, not scene change)."""
    n = len(ts)
    j = o
    while j < n:
        if sm[j] > P.low:
            j += 1
            continue
        k = j
        while k < n and sm[k] <= P.low and ts[k] - ts[j] < P.gap_bridge:
            k += 1
        if k < n and sm[k] > P.low and ts[k] - ts[j] < P.gap_bridge:
            j = k + 1
        else:
            break
    return j


def _relative_event(shot_id, shot_start, shot_end, sm, ts, o, qs, prep,
                    ev_n, prefix, P):
    """Relative completion: rise -> sustained blob with delivery-level core
    -> significant decay (post <= max(LOW, peak*DECAY)) -> stable regime.
    Brief (< MIN_ACTIVE) re-bumps are tolerated as residual; only a
    sustained renewed delivery level abandons the pattern. Residual below
    HIGH is tolerated throughout."""
    n = len(ts)
    HIGH_ = P.high
    b1 = _blob_end(sm, ts, o, P)
    h = next((k for k in range(o, b1) if sm[k] >= HIGH_), None)
    if h is None:
        return "skip", None, b1  # never reaches delivery level
    active_dur = ts[b1 - 1] - ts[o]
    peak = max(range(o, b1), key=lambda k: sm[k])
    peak_val = sm[peak]
    if active_dur < P.min_active:
        return "skip", None, b1
    # quiet-only preparation before the rise (exclude mid-zone ramp)
    q = h
    while q >= qs and sm[q] > P.low:
        q -= 1
    prep = (ts[q] - ts[qs]) if q >= qs else 0.0
    target = max(P.low, peak_val * P.decay_ratio)
    edge_limit = shot_end - P.edge_skip
    d = peak + 1
    while d < n and sm[d] > target:
        d += 1
    if d >= n or ts[d] > edge_limit:
        # decay never reached, or only inside the transition edge
        return ("reject", RejectedWindow(shot_id, "end_incomplete",
                f"onset@{ts[o]:.2f} never decays before cut"), d)
    # stable regime from d: accumulate below-HIGH calm time. Once calm
    # reaches min_settle the event is complete (supports multi-event shots:
    # scanning continues after). A sustained renewed core before that
    # abandons the pattern; brief re-bumps are tolerated as residual.
    calm, j = 0.0, d
    while j < n and ts[j] <= edge_limit:
        if sm[j] < HIGH_:
            k = j
            while k < n and ts[k] <= edge_limit and sm[k] < HIGH_:
                k += 1
            calm += ts[k - 1] - ts[j]
            j = k
            if calm >= P.min_settle:
                return ("event", _make_event(
                    shot_id, prefix, ev_n, shot_start, shot_end, ts, qs, o,
                    peak, ts[d], calm, prep, active_dur, P), j)
            continue
        b = j
        while b < n and ts[b] <= edge_limit and sm[b] >= HIGH_:
            b += 1
        if ts[b - 1] - ts[j] >= P.min_active:
            if calm >= P.min_settle:
                return ("event", _make_event(
                    shot_id, prefix, ev_n, shot_start, shot_end, ts, qs, o,
                    peak, ts[d], calm, prep, active_dur, P), b)
            bb = b
            while bb < n and sm[bb] >= HIGH_:
                bb += 1
            return "skip", None, bb
        j = b  # brief residual bump: tolerate
    if calm >= P.edge_min_stable:
        return ("event", _make_event(shot_id, prefix, ev_n, shot_start,
                                     shot_end, ts, qs, o, peak, ts[d], calm,
                                     prep, active_dur, P), n)
    return ("reject", RejectedWindow(
        shot_id, "end_incomplete",
        f"onset@{ts[o]:.2f} settle too short before cut"), j)


def _make_event(shot_id, prefix, ev_n, shot_start, shot_end, ts, qs, o,
                peak, settle, settle_dur, prep, active_dur, P):
    cs = max(shot_start, ts[o] - P.pre_buffer, ts[qs])
    ce = min(shot_end, settle + P.post_buffer)
    conf = round(min(1.0, prep / 1.5 * 0.3 + active_dur / 2.0 * 0.4
                     + settle_dur / 1.5 * 0.3), 3)
    return PitchEvent(
        event_id=f"{prefix}{ev_n:03d}",
        source_shot_id=shot_id,
        clip_start=round(cs, 3),
        motion_onset=round(ts[o], 3),
        motion_peak=round(ts[peak], 3),
        settle_time=round(settle, 3),
        clip_end=round(ce, 3),
        confidence=conf,
    )
