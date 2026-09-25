"""The API's version and deprecation policy (asset-model-revision §19 item 8).

* The version is in the path (`/v1`). Within a version, changes are
  additive only: new endpoints, new optional fields, new values where a
  client is told to expect more. Anything else is a new version.
* An endpoint is deprecated by listing it here. From then on each response
  carries `Deprecation` (RFC 9745), `Sunset` (RFC 8594) and a `Link` to its
  successor, and the endpoint keeps working for at least
  `MIN_NOTICE_DAYS`. After its sunset it answers 410 Gone with the
  successor.
* Every response names the API version in `X-ARGUS-API-Version`, and
  `GET /v1/meta/api` publishes this policy with the current deprecations.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from email.utils import format_datetime
from typing import Optional

API_VERSION = "1"
MIN_NOTICE_DAYS = 180

POLICY = [
    "The major version is in the path (/v1). Within it, changes are additive only.",
    "Removing or renaming a field, an endpoint or an accepted value needs a new version.",
    f"A deprecated endpoint keeps working for at least {MIN_NOTICE_DAYS} days and says so in its "
    "Deprecation, Sunset and Link headers.",
    "After its sunset a deprecated endpoint answers 410 Gone and names its successor.",
    "Jira keys, Jira URLs, Insight keys and objectIds stay resolvable through /v1/lookup for as long "
    "as ARGUS runs.",
]


@dataclass(frozen=True)
class Deprecation:
    method: str                  # GET, POST, … or * for every method
    path: str                    # a route template, e.g. /v1/issues/{uid}/state
    deprecated_on: date
    sunset: date
    successor: str
    note: str = ""

    def matches(self, method: str, path: str) -> bool:
        if self.method not in ("*", method.upper()):
            return False
        pattern = "^" + re.sub(r"\\\{[^/]+?\\\}", "[^/]+", re.escape(self.path)) + "/?$"
        return re.match(pattern, path) is not None


# Nothing is deprecated yet. An entry here is the whole announcement.
DEPRECATIONS: list[Deprecation] = []


def check(entries: list[Deprecation]) -> list[str]:
    """The notice each entry gives is at least the policy's."""
    return [f"{d.method} {d.path}: sunset {d.sunset} is less than {MIN_NOTICE_DAYS} days after {d.deprecated_on}"
            for d in entries if (d.sunset - d.deprecated_on).days < MIN_NOTICE_DAYS]


def find(method: str, path: str) -> Optional[Deprecation]:
    return next((d for d in DEPRECATIONS if d.matches(method, path)), None)


def _midnight(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=timezone.utc)


def headers(d: Deprecation) -> dict[str, str]:
    return {"Deprecation": f"@{int(_midnight(d.deprecated_on).timestamp())}",
            "Sunset": format_datetime(_midnight(d.sunset), usegmt=True),
            "Link": f'<{d.successor}>; rel="successor-version"'}


def is_past_sunset(d: Deprecation, today: Optional[date] = None) -> bool:
    return (today or datetime.now(timezone.utc).date()) >= d.sunset


def describe() -> dict:
    return {"version": API_VERSION, "min_notice_days": MIN_NOTICE_DAYS, "policy": POLICY,
            "deprecations": [{"method": d.method, "path": d.path, "deprecated_on": d.deprecated_on.isoformat(),
                              "sunset": d.sunset.isoformat(), "successor": d.successor, "note": d.note,
                              "gone": is_past_sunset(d)} for d in DEPRECATIONS]}
