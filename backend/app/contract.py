"""The committed API contract (asset-model-revision §24.3, flutter-app-design §3.1).

`openapi/openapi.json` is the whole contract. `openapi/field-client.json` is
the subset the Flutter field client is generated from: the operations
listed in FIELD_OPERATIONS, and the schemas they reference. Both are
written by `python -m app.contract`. A test fails when the running API
and the committed contract differ, so a change to the API is a deliberate
change to the contract, reviewed with it (docs/api-policy.md).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "openapi"

# (method, path) the field client calls. Adding one here is how the field client starts using it.
FIELD_OPERATIONS = [
    ("get", "/v1/meta/api"),
    ("get", "/v1/me"),
    ("get", "/v1/me/workspaces"),
    ("post", "/v1/devices"),
    ("get", "/v1/devices"),
    ("post", "/v1/devices/{device_id}/revoke"),
    ("get", "/v1/links/resolve"),
    ("get", "/v1/lookup/{identifier}"),
    ("get", "/v1/hub/search"),
    ("get", "/v1/assets/{uid}"),
    ("get", "/v1/hub/assets/{uid}/context"),
    ("get", "/v1/installations"),
    ("get", "/v1/schemas/{uid}"),
    ("get", "/v1/issues/{uid}"),
    ("get", "/v1/hub/tickets/{uid}/context"),
    ("get", "/v1/documents/{uid}"),
    ("get", "/v1/documents/{uid}/current"),
    ("get", "/v1/hub/documents/{uid}/context"),
    # Writes (M0: every one accepts Idempotency-Key; edits take If-Match with the version read)
    ("put", "/v1/assets/{uid}"),
    ("post", "/v1/installations/swap"),
    ("post", "/v1/issues"),
    ("put", "/v1/issues/{uid}"),
    ("post", "/v1/issues/{uid}/transition"),
    ("get", "/v1/issues/{uid}/comments"),
    ("post", "/v1/issues/{uid}/comments"),
    ("get", "/v1/issues/{uid}/attachments"),
    ("post", "/v1/uploads"),
    ("get", "/v1/uploads/{uid}"),
    ("put", "/v1/uploads/{uid}"),
    ("post", "/v1/uploads/{uid}/complete"),
    ("post", "/v1/uploads/{uid}/attach/ticket/{issue_uid}"),
    ("post", "/v1/uploads/{uid}/attach/asset/{asset_uid}"),
    # Capture and tickets (M2)
    ("get", "/v1/schemas"),
    ("post", "/v1/assets"),
    ("get", "/v1/issues/{uid}/transitions"),
    ("post", "/v1/intake/guide/asset"),
    ("post", "/v1/intake/guide/ticket"),
    ("post", "/v1/intake/assist/ticket"),
    ("post", "/v1/intake/assist/{kind}/file"),
    ("post", "/v1/intake/runs/{run_id}/outcome"),
    ("get", "/v1/notifications"),
    ("post", "/v1/notifications/{nid}/read"),
]


def full() -> dict:
    from app.main import app
    return app.openapi()


def _refs(node, found: set) -> None:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            found.add(ref.rsplit("/", 1)[1])
        for v in node.values():
            _refs(v, found)
    elif isinstance(node, list):
        for v in node:
            _refs(v, found)


def field_subset(spec: dict) -> dict:
    """The field client's operations, and every schema they reach."""
    out = {k: copy.deepcopy(v) for k, v in spec.items() if k not in ("paths", "components")}
    out["info"] = {**spec.get("info", {}), "title": "ARGUS field client API"}
    out["paths"] = {}
    for method, path in FIELD_OPERATIONS:
        op = spec["paths"].get(path, {}).get(method)
        if op is None:
            raise KeyError(f"{method.upper()} {path} is not in the API")
        op = copy.deepcopy(op)
        # FastAPI's operation id is "<function>_v1_<path>_<method>"; the function name reads better in a client.
        op["operationId"] = op.get("operationId", "").split("_v1_")[0] or op.get("operationId")
        out["paths"].setdefault(path, {})[method] = op
    ids = [o["operationId"] for p in out["paths"].values() for o in p.values()]
    if len(ids) != len(set(ids)):
        raise ValueError(f"field-client operation ids are not unique: {sorted(ids)}")
    schemas = spec.get("components", {}).get("schemas", {})
    needed: set = set()
    _refs(out["paths"], needed)
    while True:
        before = set(needed)
        for name in list(needed):
            _refs(schemas.get(name, {}), needed)
        if needed == before:
            break
    out["components"] = {"schemas": {k: schemas[k] for k in sorted(needed) if k in schemas}}
    return _for_generators(out)


PRIMITIVES = {"string", "integer", "number", "boolean"}


def _untyped(schema) -> bool:
    return isinstance(schema, dict) and not (set(schema) & {"type", "$ref", "anyOf", "oneOf", "allOf", "enum"})


def _nullable(schema) -> bool:
    if not isinstance(schema, dict):
        return False
    options = schema.get("anyOf") or schema.get("oneOf") or []
    return schema.get("nullable") is True or schema.get("type") == "null" or any(
        isinstance(o, dict) and o.get("type") == "null" for o in options)


def _for_generators(node):
    """Client generators cannot type a value that is one of several primitive types (FastAPI's
    validation-error `loc` is a string or an integer). Such a value becomes "any value". Nor can
    they type a list of "any value" (the Dart generator emits `Object.listFromJson`), so such a
    list becomes "any value" too. Object defaults are dropped (see below)."""
    if isinstance(node, dict):
        options = node.get("anyOf")
        if isinstance(options, list) and len(options) > 1 and all(
                isinstance(o, dict) and set(o) <= {"type"} and o.get("type") in PRIMITIVES for o in options) \
                and len({o["type"] for o in options}) > 1:
            node = {k: v for k, v in node.items() if k != "anyOf"}
        node = {k: _for_generators(v) for k, v in node.items()}
        # A property that may be null is not "required" to a generator: the Dart one asserts that a
        # required key is non-null, and "present and null" and "absent" mean the same to a client.
        props, required = node.get("properties"), node.get("required")
        if isinstance(props, dict) and isinstance(required, list):
            kept = [r for r in required if not _nullable(props.get(r))]
            node = {**node, "required": kept} if kept else {k: v for k, v in node.items() if k != "required"}
        # An object default ({}) becomes a non-constant default in Dart; the server applies it anyway.
        if isinstance(node.get("default"), dict):
            node = {k: v for k, v in node.items() if k != "default"}
        if node.get("type") == "array" and _untyped(node.get("items")):
            node = {k: v for k, v in node.items() if k not in ("type", "items")}
        return node
    if isinstance(node, list):
        return [_for_generators(v) for v in node]
    return node


def dump(obj: dict) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write() -> list[Path]:
    ROOT.mkdir(exist_ok=True)
    spec = full()
    files = {ROOT / "openapi.json": spec, ROOT / "field-client.json": field_subset(spec)}
    for path, content in files.items():
        path.write_text(dump(content))
    return list(files)


if __name__ == "__main__":
    for p in write():
        print(f"wrote {p}")
    sys.exit(0)
