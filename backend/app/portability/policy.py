"""The portability policy: every rule that an institution may make stricter, in one place
(docs/export-import-design.md §20).

Two named profiles:

  trusted   the initial deployment policy (stakeholder decisions of 2026-10): an internal, authenticated,
            trusted environment. One administrator approves; step-up accepts a recent session plus an
            explicit confirmation when the identity provider sends no `auth_time`; opaque and
            uninspectable files travel, clearly labelled, after an administrator accepts the warning;
            only document readers with tested fixtures are used; `full_identity` is the profile for
            backup, restore and migration and is not by itself high-risk; workspace administrators
            import into, and read evidence of, their own workspaces.
  strict    the stricter rules the design describes: separation of duties, strict `auth_time`, every
            opaque or uninspectable blob held for a decision, `full_identity` high-risk, imports and
            evidence for instance administrators and named readers only.

`ARGUS_PORTABILITY_POLICY` picks the profile (default `trusted`); any single setting can be overridden
with `ARGUS_PORTABILITY_POLICY_<SETTING>` (e.g. `ARGUS_PORTABILITY_POLICY_SEPARATION_OF_DUTIES=1`).

Policy changes gates and labels only — never the archive format. Every archive records the policy it
was made under (`manifest.policy`), every audited approval, generation and import records the
relaxations in force, and `GET /v1/portability/config` shows them: a relaxed choice is always visible.
Fixed regardless of policy: secrets are never exported; restricted classes leave only encrypted, to an
approved destination; nothing is promoted that did not reconcile.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field, fields, replace
from typing import Optional

PROFILES = ("trusted", "strict")
READERS = ("text", "email", "pdf", "office", "archive")
# Readers with tested fixtures (backend/tests/test_portability_policy.py): enabled by default.
TESTED_READERS = ("text", "email", "pdf", "office", "archive")
PURPOSES = ("backup", "restore", "migration", "analysis", "external_sharing", "evidence")
# Which identity profile a purpose implies when none is chosen.
PURPOSE_PROFILE = {"backup": "full_identity", "restore": "full_identity", "migration": "full_identity",
                   "analysis": "pseudonymized", "external_sharing": "pseudonymized",
                   "evidence": "institutional_reference"}


@dataclass(frozen=True)
class Policy:
    profile: str = "trusted"
    # approvals
    separation_of_duties: bool = False           # a second person must approve high-risk work
    step_up: str = "session_confirmation"        # strict | session_confirmation
    step_up_seconds: int = 300                   # how recent `auth_time` must be
    session_seconds: int = 1800                  # without `auth_time`: how recent the session (`iat`)
    full_identity_high_risk: bool = False
    # content
    opaque_blobs: str = "allow_with_warning"     # allow_with_warning | require_decision
    uninspectable_blobs: str = "allow_with_warning"
    classified_blobs: str = "require_decision"   # require_decision | allow_with_warning
    blob_readers: tuple = TESTED_READERS
    # who
    export_permission: str = "read"              # read | approve: the right needed on each workspace
    import_permission: str = "workspace_admin"   # workspace_admin | instance_admin
    evidence_workspace_admins: bool = True       # workspace administrators read their workspace's evidence
    # downloads
    query_tokens: bool = False                   # tokens in the query string (needs proxy redaction)
    proxy_redacts_tokens: bool = False           # operator's confirmation that proxies redact `token=`
    # retention
    retention_days: int = 90                     # archives, quarantine, staging, evidence copies
    # fixed by design (shown, not configurable)
    restricted_requires_encryption: bool = field(default=True, init=False)
    secrets_never_exported: bool = field(default=True, init=False)

    @classmethod
    def trusted(cls) -> "Policy":
        return cls()

    @classmethod
    def strict(cls) -> "Policy":
        return cls(profile="strict", separation_of_duties=True, step_up="strict", full_identity_high_risk=True,
                   opaque_blobs="require_decision", uninspectable_blobs="require_decision",
                   classified_blobs="require_decision", export_permission="approve",
                   import_permission="instance_admin", evidence_workspace_admins=False)

    def relaxations(self) -> list[str]:
        """What this policy allows that the strict one does not: shown and audited."""
        strict = Policy.strict()
        out = []
        for f in fields(self):
            if not f.init or f.name in ("profile", "step_up_seconds", "session_seconds", "retention_days",
                                        "proxy_redacts_tokens"):
                continue
            mine, theirs = getattr(self, f.name), getattr(strict, f.name)
            if mine != theirs:
                out.append(f"{f.name}={mine if not isinstance(mine, tuple) else ','.join(mine)}")
        return out

    def describe(self) -> dict:
        d = asdict(self)
        d["blob_readers"] = list(self.blob_readers)
        d["relaxations"] = self.relaxations()
        return d

    def query_tokens_allowed(self) -> bool:
        return self.query_tokens and self.proxy_redacts_tokens


def _bool(v: str) -> bool:
    return v.strip().lower() in ("1", "true", "yes", "on")


def from_env(env: Optional[dict] = None) -> Policy:
    env = env if env is not None else os.environ
    name = (env.get("ARGUS_PORTABILITY_POLICY") or "trusted").strip()
    if name not in PROFILES:
        raise ValueError(f"ARGUS_PORTABILITY_POLICY must be one of {PROFILES}")
    base = Policy.strict() if name == "strict" else Policy.trusted()
    overrides = {}
    for f in fields(Policy):
        if not f.init or f.name == "profile":
            continue
        raw = env.get(f"ARGUS_PORTABILITY_POLICY_{f.name.upper()}")
        if raw is None:
            continue
        cur = getattr(base, f.name)
        if isinstance(cur, bool):
            overrides[f.name] = _bool(raw)
        elif isinstance(cur, int):
            overrides[f.name] = int(raw)
        elif isinstance(cur, tuple):
            overrides[f.name] = tuple(x for x in (y.strip() for y in raw.split(",")) if x in READERS)
        else:
            overrides[f.name] = raw.strip()
    if "step_up_seconds" not in overrides and env.get("ARGUS_PORTABILITY_STEP_UP_SECONDS"):
        overrides["step_up_seconds"] = int(env["ARGUS_PORTABILITY_STEP_UP_SECONDS"])
    return replace(base, **overrides)
