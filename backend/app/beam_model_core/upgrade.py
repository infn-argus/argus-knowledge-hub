"""Reading any supported version: `argus.beam-model/1` documents are upgraded to `/2` without loss.

v1 → v2:
* `elements` become `components`; v1 kinds map to the v2 vocabulary (`source` → `generic_source`,
  `dump` → `beam_dump`); the v1 capability `beam_transport` becomes `particle_transport` (or
  `photon_transport` on a path that carries only photon beams), `radiation` → `radiation_emission`,
  `beam_dump` → `beam_destination` + `beam_interception`;
* beams embedded in systems become top-level `beams`, their `parameters` lifted into named fields where
  v2 has one;
* a path's `elements` become its `placements`, its `branches` become `connections` of kind `branch`;
* element-level values (`s`, `geometry`, `physics`, `optics`, native parameters) are filed into datasets
  exactly as v1 did: `model.dataset`, else the first dataset of the element's path, else one made for it.
"""
from __future__ import annotations

import copy
from typing import Any

from app.beam_model_core.schema import SCHEMA_VERSION
from app.beam_model_core.vocabulary import normalise_type

V1 = "argus.beam-model/1"
V1_BUNDLE = "argus.beam-model-bundle/1"
V2_BUNDLE = "argus.beam-model-bundle/2"

_CAPS = {"beam_transport": None, "radiation": ["radiation_emission"],
         "beam_dump": ["beam_destination", "beam_interception"]}
_BEAM_FIELDS = ("species", "charge", "rest_mass", "reference_energy", "reference_momentum", "wavelength")


def version_of(doc: Any) -> str:
    if isinstance(doc, dict):
        return str(doc.get("schema_version") or doc.get("format") or "")
    return ""


def upgrade(doc: dict) -> dict:
    """A v2 document from a v1 or v2 one (a v2 document is returned as a copy)."""
    v = version_of(doc)
    if v == SCHEMA_VERSION:
        return copy.deepcopy(doc)
    if v != V1:
        raise ValueError(f"unsupported beam model version {v or '(none)'}: expected {SCHEMA_VERSION} or {V1}")
    return _from_v1(copy.deepcopy(doc))


def models_of(doc: Any) -> list[dict]:
    """The models in what was sent: one model, a bundle (v1 or v2), or a plain list of models."""
    if isinstance(doc, list):
        return doc
    if isinstance(doc, dict) and version_of(doc) in (V1_BUNDLE, V2_BUNDLE):
        return list(doc.get("models") or [])
    return [doc]


def _from_v1(d: dict) -> dict:
    model = d.get("model") or {}
    systems, beams = [], []
    for s in d.get("systems") or []:
        ids = []
        for b in s.get("beams") or []:
            params = dict(b.get("parameters") or {})
            lifted = {k: params.pop(k) for k in _BEAM_FIELDS if k in params}
            beams.append({"id": b["id"], **({"name": b["name"]} if b.get("name") else {}),
                          "kind": b.get("kind") or "particle", **lifted, "systems": [s["id"]],
                          **({"parameters": params} if params else {})})
            ids.append(b["id"])
        systems.append({k: v for k, v in (("id", s.get("id")), ("name", s.get("name")), ("kind", s.get("kind")),
                                          ("beams", ids)) if v not in (None, [])})
    photon_systems = {s["id"] for s in d.get("systems") or []
                      if (s.get("beams") or []) and all(b.get("kind") == "photon" for b in s["beams"])}
    paths, connections = [], []
    medium_of: dict[str, str] = {}
    for p in d.get("paths") or []:
        medium = "photon" if p.get("system") in photon_systems else "particle"
        for e in p.get("elements") or []:
            medium_of[e] = medium
        paths.append({k: v for k, v in (
            ("id", p.get("id")), ("name", p.get("name")), ("system", p.get("system")),
            ("topology", p.get("topology") or "open"), ("placements", list(p.get("elements") or [])),
            ("reference", p.get("reference")), ("length", p.get("length")), ("direction", p.get("direction")))
            if v is not None})
        for br in p.get("branches") or []:
            connections.append({"kind": "branch", "from": {"path": p["id"], "component": br["at"]},
                                "to": {"path": br["to_path"]}})
    components = []
    for e in d.get("elements") or []:
        caps = e.get("capabilities")
        if caps is not None:
            out = []
            for c in caps:
                if c == "beam_transport":
                    out.append("photon_transport" if medium_of.get(e["id"]) == "photon" else "particle_transport")
                else:
                    out.extend(_CAPS.get(c) or [c])
            caps = sorted(set(out))
        native = e.get("native") or None
        comp = {"id": e["id"], "type": normalise_type(e.get("type") or "generic")}
        if e.get("name") and e["name"] != e["id"]:
            comp["name"] = e["name"]
        if caps is not None:
            comp["capabilities"] = caps
        if e.get("observes"):
            comp["observes"] = list(e["observes"])
        if native and (native.get("source") or native.get("type")):
            comp["native"] = {k: v for k, v in (("format", native.get("source") or model.get("simulator")),
                                                ("type", native.get("type")), ("name", e["id"])) if v}
        components.append(comp)
    datasets = [dict(x) for x in d.get("datasets") or []]
    _file_element_values(d, datasets)
    out = {"schema_version": SCHEMA_VERSION, "model": model, "systems": systems, "beams": beams, "paths": paths,
           "connections": connections, "components": components,
           "observables": list(d.get("observables") or []), "datasets": datasets,
           "provenance": {"upgraded_from": V1}}
    return out


def _file_element_values(d: dict, datasets: list[dict]) -> None:
    model = d.get("model") or {}
    by_id = {x.get("id"): x for x in datasets}
    path_of = {e: p["id"] for p in d.get("paths") or [] for e in p.get("elements") or []}
    first_of_path: dict[str, str] = {}
    for x in datasets:
        first_of_path.setdefault(x.get("path"), x.get("id"))
    for e in d.get("elements") or []:
        native = e.get("native") or {}
        own = {k: e[k] for k in ("s", "geometry", "physics", "optics") if e.get(k) not in (None, {}, [])}
        if native.get("parameters"):
            own["native"] = {k: v for k, v in (("format", native.get("source")), ("type", native.get("type")),
                                               ("parameters", native["parameters"])) if v}
        if not own or e["id"] not in path_of:
            continue
        target_id = model.get("dataset") or first_of_path.get(path_of[e["id"]]) or \
            f"{model.get('id')}@{model.get('version') or 'source'}:{path_of[e['id']]}"
        if target_id not in by_id:
            by_id[target_id] = {"id": target_id, "name": f"{model.get('name') or model.get('id')} (as imported)",
                                "kind": "design", "path": path_of[e["id"]], "values": {}}
            datasets.append(by_id[target_id])
            first_of_path.setdefault(path_of[e["id"]], target_id)
        values = by_id[target_id].setdefault("values", {})
        values.setdefault(e["id"], own)
