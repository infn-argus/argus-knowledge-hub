"""Talking to an ARGUS Knowledge Hub, as a client.

Kept to the public REST API and a Bearer token, so this tool stays
something you run from your own machine against whichever hub you point it
at — not a part of the server that happens to live in the same repository.
"""
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional


class HubError(RuntimeError):
    """Something to show a person, not a traceback."""


class Hub:
    def __init__(self, base_url: str, token: str, timeout: int = 60):
        self.base = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def _call(self, method: str, path: str, payload: Optional[dict] = None) -> Any:
        request = urllib.request.Request(
            f"{self.base}{path}",
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read()
                return json.loads(body) if body else None
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:400]
            if e.code in (401, 403):
                raise HubError(
                    f"The hub refused the token ({e.code}). Check it is a token for the "
                    f"workspace you mean to write into."
                ) from e
            raise HubError(f"{method} {path} failed ({e.code}): {detail}") from e
        except urllib.error.URLError as e:
            raise HubError(f"Could not reach {self.base}: {e.reason}") from e

    def whoami(self) -> dict:
        return self._call("GET", "/v1/me")

    def schemas(self) -> list[dict]:
        return self._call("GET", "/v1/schemas") or []

    def assets(self) -> list[dict]:
        return self._call("GET", "/v1/assets") or []

    def create_schema(self, uid: str, name: str, description: str) -> dict:
        return self._call("POST", "/v1/schemas", {
            "uid": uid, "name": name, "description": description,
            "applies_to": "objects", "attributes": [],
        })

    def create_asset(self, payload: dict) -> dict:
        return self._call("POST", "/v1/assets", payload)

    def update_asset(self, uid: str, patch: dict) -> dict:
        return self._call("PUT", f"/v1/assets/{urllib.parse.quote(uid)}", patch)

    def get_asset(self, uid: str) -> Optional[dict]:
        try:
            return self._call("GET", f"/v1/assets/{urllib.parse.quote(uid)}")
        except HubError:
            return None
