"""One problem shape for every error (flutter-app-design §3.4, revision §24.3 item 4).

Every error response keeps its `detail`, as it always had (an additive change within /v1), and
gains a top-level `problem`:

    {"error": "a person-readable sentence", "code": "stale", "invariant": "I-INS-1",
     "field": "attributes.serial", "current": {...}, "review_item": "..."}

Clients decide from `code`, never from the English text.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

BY_STATUS = {
    400: "invalid",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    405: "invalid",
    409: "conflict",
    410: "gone",
    412: "stale",
    413: "too_large",
    415: "invalid",
    422: "invalid",
    426: "client_too_old",
    428: "invalid",
    429: "rate_limited",
}

# Keys of a dict `detail` carried into the problem as they are.
PASSTHROUGH = ("invariant", "field", "current", "review_item", "minimum", "candidates", "limit")


def problem(status: int, detail: Any) -> dict:
    """The problem for a status and whatever `detail` an endpoint raised."""
    out: dict = {"code": BY_STATUS.get(status, "server_error" if status >= 500 else "invalid")}
    if isinstance(detail, str):
        out["error"] = detail
    elif isinstance(detail, dict):
        message = detail.get("error") or detail.get("message")
        if not message:
            # Older endpoints name their payload ({"reasons": [...]}, {"errors": [...]}).
            first = next((v for v in detail.values() if isinstance(v, (str, list))), None)
            message = first if isinstance(first, str) else (
                "; ".join(map(str, first[:3])) if isinstance(first, list) and first else None)
        out["error"] = str(message or _default_message(status))
        if detail.get("code"):
            out["code"] = str(detail["code"])
        elif detail.get("invariant"):
            out["code"] = "invariant"
        for key in PASSTHROUGH:
            if detail.get(key) is not None:
                out[key] = detail[key]
    elif isinstance(detail, list) and detail:
        out["error"] = "; ".join(map(str, detail[:3]))
    else:
        out["error"] = _default_message(status)
    return out


def _default_message(status: int) -> str:
    return {401: "Sign in again.", 403: "You are not allowed to do this.", 404: "Not found.",
            409: "This conflicts with the current state.", 413: "Too large."}.get(
        status, "The request failed." if status < 500 else "ARGUS failed to handle the request.")


def response(status: int, detail: Any, headers: Optional[dict] = None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": detail, "problem": problem(status, detail)},
                        headers=headers)


def _field(loc) -> Optional[str]:
    parts = [str(p) for p in (loc or ()) if p not in ("body", "query", "path", "header")]
    return ".".join(parts) or None


async def http_exception(request: Request, exc: StarletteHTTPException):
    return response(exc.status_code, exc.detail, getattr(exc, "headers", None))


async def validation_exception(request: Request, exc: RequestValidationError):
    from fastapi.encoders import jsonable_encoder
    errors = jsonable_encoder(exc.errors())
    first = errors[0] if errors else {}
    body = {"error": first.get("msg", "The request is not valid."), "code": "invalid",
            "field": _field(first.get("loc"))}
    return JSONResponse(status_code=422, content={"detail": errors, "problem": {k: v for k, v in body.items() if v}})


def install(app) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception)
    app.add_exception_handler(RequestValidationError, validation_exception)
