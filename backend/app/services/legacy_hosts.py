"""The Jira host after retirement (asset-model-revision §19 item 11).

Once Jira is retired its host name points at ARGUS. Every request that
arrives for it — a bookmark, a link in an e-mail, a wiki page, a URL
printed on a label — is sent to the ARGUS lookup page with the original
URL. The page resolves it with the reader's own access: the redirect itself
reveals nothing about what exists.

    JIRA_LEGACY_HOSTS=jira.example.org,insight.example.org
    ARGUS_WEB_URL=https://argus.example.org

A proxy that cannot route by host can send the old host's traffic to
`/legacy/jira/<path>` instead, with `X-Forwarded-Host` set.
"""
from __future__ import annotations

import os
from typing import Optional
from urllib.parse import quote


def legacy_hosts() -> set[str]:
    return {h.strip().lower() for h in os.environ.get("JIRA_LEGACY_HOSTS", "").split(",") if h.strip()}


def web_url() -> str:
    return os.environ.get("ARGUS_WEB_URL", "").rstrip("/")


def is_legacy(host: Optional[str]) -> bool:
    return bool(host) and host.split(":")[0].lower() in legacy_hosts()


def target(host: str, path: str, query: str = "", scheme: str = "https") -> str:
    """Where a request for `host` + `path` + `query` goes."""
    if path in ("", "/") and not query:
        return f"{web_url()}/"
    original = f"{scheme}://{host}{path}" + (f"?{query}" if query else "")
    return f"{web_url()}/lookup/{quote(original, safe='')}"
