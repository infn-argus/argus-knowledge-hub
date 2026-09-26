"""Secrets never reach a model, a claim or the audit log (§23.10, AS §9.4).

A deterministic scan, run on everything the intake sends or stores. A
finding is replaced by a marker; the caller records that a redaction
happened, never the value.
"""
from __future__ import annotations

import re

MARK = "[redacted]"

PATTERNS = [
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S)),
    ("assignment", re.compile(
        r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|client[_-]?secret|"
        r"credentials?|community)\b(\s*[:=]\s*|\s+is\s+)(\"[^\"]+\"|'[^']+'|[^\s,;]+)")),
    ("bearer", re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]{16,}")),
    ("aws_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("url_credentials", re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@")),
]


def scan(text: str) -> list[str]:
    """The kinds of secret found in `text`, without their values."""
    return [kind for kind, pattern in PATTERNS if pattern.search(text or "")]


def redact(text: str) -> tuple[str, dict[str, int]]:
    """`text` with every secret replaced, and how many of each kind."""
    counts: dict[str, int] = {}
    out = text or ""
    for kind, pattern in PATTERNS:
        def sub(m, kind=kind):
            counts[kind] = counts.get(kind, 0) + 1
            if kind == "assignment":
                return f"{m.group(1)}{m.group(2)}{MARK}"
            if kind == "url_credentials":
                return m.group(0).split("://", 1)[0] + f"://{MARK}@"
            return MARK
        out = pattern.sub(sub, out)
    return out, counts
