"""Valid-time values with honest uncertainty (asset-model-revision §8.2).

A temporal value is stored as a dict:

    {"kind": "date", "nominal": "2026-03-01T00:00:00+00:00", "precision": "month"}
    {"kind": "before_records", "bound": "2026-09-01T00:00:00+00:00"}
    {"kind": "unscheduled"}
    {"kind": "open"}
    {"kind": "unknown_past", "bound": "..."}

Every comparison uses the computed `earliest` and `latest` instants and never
the nominal one (I-TIME-1). The true instant lies in [earliest, latest].
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

NEG_INF = datetime.min.replace(tzinfo=timezone.utc)
POS_INF = datetime.max.replace(tzinfo=timezone.utc)
_TICK = timedelta(microseconds=1)

FROM_KINDS = {"date", "before_records", "unscheduled"}
UNTIL_KINDS = {"date", "open", "unknown_past"}
PRECISIONS = {"instant", "day", "month", "year"}


class TemporalError(ValueError):
    pass


def parse_instant(value) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def instant(value, precision: str = "instant") -> dict:
    """A dated temporal value. The nominal instant is normalized to the start
    of its precision bucket."""
    dt = parse_instant(value)
    if precision == "day":
        dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    elif precision == "month":
        dt = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif precision == "year":
        dt = dt.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    elif precision != "instant":
        raise TemporalError(f"unknown precision {precision!r}")
    return {"kind": "date", "nominal": dt.isoformat(), "precision": precision}


def _bucket_end(start: datetime, precision: str) -> datetime:
    if precision == "instant":
        return start
    if precision == "day":
        return start + timedelta(days=1) - _TICK
    if precision == "month":
        days = calendar.monthrange(start.year, start.month)[1]
        return start + timedelta(days=days) - _TICK
    if precision == "year":
        return start.replace(year=start.year + 1) - _TICK
    raise TemporalError(f"unknown precision {precision!r}")


@dataclass(frozen=True)
class Bounds:
    earliest: datetime
    latest: datetime
    placed: bool = True     # False only for "unscheduled"


def bounds(value: Optional[dict], role: str, start: Optional[Bounds] = None) -> Bounds:
    """Earliest and latest instants of an endpoint. `role` is "from" or
    "until"; an until of kind unknown_past needs the interval's start."""
    if not value:
        value = {"kind": "open"} if role == "until" else {"kind": "unscheduled"}
    kind = value.get("kind")
    allowed = FROM_KINDS if role == "from" else UNTIL_KINDS
    if kind not in allowed:
        raise TemporalError(f"{kind!r} is not a valid {role} kind")
    if kind == "date":
        precision = value.get("precision", "instant")
        start_at = parse_instant(value["nominal"])
        return Bounds(start_at, _bucket_end(start_at, precision))
    if kind == "before_records":
        return Bounds(NEG_INF, parse_instant(value["bound"]))
    if kind == "unscheduled":
        return Bounds(POS_INF, POS_INF, placed=False)
    if kind == "open":
        return Bounds(POS_INF, POS_INF)
    if kind == "unknown_past":
        earliest = start.earliest if start is not None else NEG_INF
        return Bounds(earliest, parse_instant(value["bound"]))
    raise TemporalError(f"unknown kind {kind!r}")


@dataclass(frozen=True)
class Interval:
    start: Bounds
    end: Bounds

    @property
    def placed(self) -> bool:
        return self.start.placed


def interval(valid_from: Optional[dict], valid_until: Optional[dict]) -> Interval:
    start = bounds(valid_from, "from")
    return Interval(start, bounds(valid_until, "until", start))


def validate(iv: Interval) -> Optional[str]:
    """None, "possible" (possibly inverted) — or raises for a definite inversion."""
    if not iv.placed:
        return None
    if iv.end.latest <= iv.start.earliest:
        raise TemporalError("the interval ends before it starts")
    if iv.start.latest >= iv.end.earliest:
        return "possible"
    return None


def overlap(a: Interval, b: Interval) -> str:
    """"none", "possible" or "definite" (half-open intervals)."""
    if not (a.placed and b.placed):
        return "none"
    if a.end.latest <= b.start.earliest or b.end.latest <= a.start.earliest:
        return "none"
    if max(a.start.latest, b.start.latest) < min(a.end.earliest, b.end.earliest):
        return "definite"
    return "possible"


def covers(iv: Interval, t: datetime) -> str:
    """Whether the interval covers instant t: "definite", "possible" or "none"."""
    if not iv.placed:
        return "none"
    if iv.start.latest <= t < iv.end.earliest:
        return "definite"
    if iv.start.earliest <= t < iv.end.latest:
        return "possible"
    return "none"


def state_at(iv: Interval, t: datetime) -> tuple[str, str]:
    """The derived temporal state and its certainty (§8.2)."""
    if not iv.placed:
        return "Planned", "definite"
    c = covers(iv, t)
    if c != "none":
        return "Current", c
    if t < iv.start.earliest:
        return "Future", "definite"
    return "Ended", "definite"


def combine(*certainties: str) -> str:
    if "none" in certainties:
        return "none"
    return "definite" if all(c == "definite" for c in certainties) else "possible"
