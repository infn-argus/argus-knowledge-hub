"""Secrets never leave ARGUS in an archive (I-PORT-SEC).

Two layers:

* **What is never selected.** The families are an allow-list (`families.py`): API tokens, device
  push tokens, sessions, idempotency keys, upload sessions, model-provider and import credentials,
  application settings and caches have no family at all.
* **What is scanned.** Every row of every family, and every file before a Git commit, is scanned
  for credential formats and for credential-named fields holding credential-like values. A finding
  stops the export before anything is published; the report names where, never the value.
"""
from __future__ import annotations

import math
import re
from typing import Iterable, Iterator

PATTERNS = [
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY(?: BLOCK)?-----")),
    ("GitHub token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{20,}")),
    ("GitLab token", re.compile(r"\bglpat-[A-Za-z0-9_\-]{20,}")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}")),
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("model-provider key", re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_\-]{24,}")),
    ("JSON web token", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
]
SECRET_NAMES = re.compile(r"(?i)(^|[_\-.])(password|passwd|secret|api[_\-]?key|access[_\-]?token|refresh[_\-]?token|"
                          r"id[_\-]?token|private[_\-]?key|client[_\-]?secret|bearer|session[_\-]?id|push[_\-]?token)$")


def _entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = {c: s.count(c) for c in set(s)}
    return -sum(n / len(s) * math.log2(n / len(s)) for n in counts.values())


def credential_like(value: str) -> bool:
    """A value a credential-named field would hold: long, unspaced, varied."""
    v = value.strip()
    return len(v) >= 16 and " " not in v and _entropy(v) >= 3.5


def scan_text(text: str, where: str) -> list[dict]:
    return [{"where": where, "kind": kind} for kind, rx in PATTERNS if rx.search(text)]


def scan_value(value, where: str) -> Iterator[dict]:
    """Findings in a JSON value, walking dicts and lists; field names are part of the path."""
    if isinstance(value, dict):
        for k, v in value.items():
            path = f"{where}.{k}"
            if isinstance(v, str) and SECRET_NAMES.search(str(k)) and credential_like(v):
                yield {"where": path, "kind": f"credential in a field named {k}"}
            yield from scan_value(v, path)
    elif isinstance(value, list):
        for i, v in enumerate(value[:10_000]):
            yield from scan_value(v, f"{where}[{i}]")
    elif isinstance(value, str) and len(value) >= 16:
        yield from scan_text(value, where)


def scan_rows(family: str, rows: Iterable[tuple[str, dict]], limit: int = 50) -> list[dict]:
    out: list[dict] = []
    for key, row in rows:
        for f in scan_value(row, f"{family}[{key}]"):
            out.append(f)
            if len(out) >= limit:
                return out
    return out


class SecretFound(ValueError):
    def __init__(self, findings: list[dict]):
        super().__init__(f"{len(findings)} possible secret(s): " +
                         "; ".join(f"{f['kind']} at {f['where']}" for f in findings[:5]))
        self.findings = findings
