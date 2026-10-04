"""Matching beamline model components to physical assets (docs/beam-asset-sync.md).

Pure: model components come from a canonical document, candidate assets are plain dicts (the Knowledge Hub,
or a test's mock), existing bindings are plain dicts. The result is proposals with a status, a confidence,
the evidence behind it and the difference from what was there — never a change to anything authoritative.

Evidence (each a weight in [0, 1]; combined as 1 − Π(1 − w), then penalties multiply):

    exact_name            the asset's name (or lattice/model name) is the component's id or name      0.85
    exact_alias_match     an alias of one is the name or an alias of the other                         0.80
    naming_convention     a configured rule maps the component's name to the asset's                  0.75
    control_name_match    the asset's control name / PV prefix contains the component's name          0.45
    normalized_name       equal once case, separators and leading zeros are ignored                    0.45
    type_match            the asset can implement this type (× compatibility); or it says it is one    0.25
    number_match          same trailing number, compatible type                                        0.10
    family_match          the asset's family is the component's model family                           0.10
    beamline_match        the asset's beamline/section/area names this model's system or path         0.15
    position_match        |Δs| within tolerance (entry or centre)                       0.45 × (1 − Δs/tol)
    geometry_match        3-D distance within tolerance                                 0.45 × (1 − d/tol)
    order_match           same rank along the line among components/assets of its kind                0.20
    neighbour_consistent  a neighbour is bound to the asset's neighbour                                0.25

    penalties: type incompatible (cap 0.2), other beamline of the facility (× 0.5), far away in s or
    space (× 0.5), no anchor — neither a name, a position, an order nor a neighbour (cap 0.45, below the
    propose threshold: kind and beamline alone never propose)

Decisions, per expected component (virtual components and model concepts expect no asset):

    CONFIRMED   an existing confirmed binding — kept, never replaced; differences are reported
    PROPOSED    best ≥ propose threshold (0.5), clearly ahead of the next (margin 0.1); `auto_acceptable`
                only when also ≥ auto threshold (0.9) *and* backed by identity evidence (a name, alias,
                convention or control name) *and* a compatible type — position alone never auto-accepts
    AMBIGUOUS   two or more candidates within the margin, or two components wanting one asset
    UNMATCHED   nothing good enough (weak suggestions listed)
    REJECTED    a pair a person rejected is never proposed again
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from app.beam_model_core import vocabulary as V
from app.beam_model_core.network import Network, resolve
from app.beam_model_core.schema import Document

MATCHER = "beamline_asset_matcher"
VERSION = "1.0"

# Which asset types (Knowledge Hub physical plane) can implement a component, with a compatibility in (0, 1].
# Types listed as incompatible are hardware *downstream* of the primary asset (electronics, supplies): a
# BPM is implemented by its pickup, not by its electronics, which Knowledge Hub connects to the pickup.
_GENERIC = {"Other Equipment": 0.5, "Asset": 0.3, "Instrument": 0.4}
FAMILY_ASSET_TYPES: dict[str, dict[str, float]] = {
    "magnet": {"Magnet Assembly": 1.0},
    "rf": {"RF Cavity": 1.0, "Accelerating Structure": 1.0, "Other Equipment": 0.6},
    "diagnostic": {"Instrument": 1.0, "Scintillator Screen": 0.9, "Camera": 0.6, "Optical Assembly": 0.6,
                   "Radiation Monitor": 0.6, "Other Equipment": 0.5},
    "injection_extraction": {"Other Equipment": 0.6, "Vacuum Component": 0.4},
    "interception": {"Other Equipment": 0.7, "Vacuum Component": 0.5},
    "vacuum": {"Vacuum Component": 0.8, "Vacuum Chamber": 0.8, "Vacuum Valve": 0.5},
    "material": {"Other Equipment": 0.6, "Vacuum Component": 0.5},
    "optical": {"Optical Assembly": 1.0, "Other Equipment": 0.5},
    "source_destination": {"Other Equipment": 0.6, "Laser System": 0.6},
    "mechanical": {"Mechanical Support": 1.0, "Motor Axis": 0.6, "Actuator": 0.5, "Other Equipment": 0.4},
}
TYPE_ASSET_TYPES: dict[str, dict[str, float]] = {
    "gate_valve": {"Vacuum Valve": 1.0}, "fast_valve": {"Vacuum Valve": 1.0},
    "vacuum_chamber": {"Vacuum Chamber": 1.0, "Vacuum Component": 0.6},
    "beam_pipe": {"Vacuum Chamber": 1.0, "Vacuum Component": 0.7},
    "bellows": {"Vacuum Component": 1.0, "Vacuum Chamber": 0.4},
    "screen": {"Scintillator Screen": 1.0, "Instrument": 0.8, "Optical Assembly": 0.5},
    "camera": {"Camera": 1.0}, "beam_loss_monitor": {"Radiation Monitor": 1.0, "Instrument": 0.8},
    "laser_source": {"Laser System": 1.0}, "mover": {"Motor Axis": 1.0, "Mechanical Support": 0.6},
    "translation_stage": {"Motor Axis": 1.0}, "rotation_stage": {"Motor Axis": 1.0},
    "power_meter": {"Instrument": 1.0}, "photodiode": {"Instrument": 1.0},
}
DOWNSTREAM_ASSET_TYPES = {"Power Supply", "Digitizer", "Electronics Board", "Electronics Crate", "Timing Module",
                          "I/O Module", "Low-Level RF Unit", "Motion Controller", "Vacuum Controller", "PLC",
                          "Cable Run", "Network Device", "Server", "Computing Node", "IOC"}


@dataclass
class Config:
    propose_threshold: float = 0.5
    auto_threshold: float = 0.9
    margin: float = 0.1
    s_tolerance: float = 0.2            # m, full position evidence well inside, none beyond
    xyz_tolerance: float = 0.3          # m
    naming_rules: list[dict] = field(default_factory=list)
    family_asset_types: dict = field(default_factory=lambda: FAMILY_ASSET_TYPES)
    type_asset_types: dict = field(default_factory=lambda: TYPE_ASSET_TYPES)


# --------------------------------------------------------------------------- what the model expects

@dataclass
class Expected:
    id: str
    name: str
    type: str
    family: str
    model_family: Optional[str]
    aliases: list[str]
    paths: list[str]
    s: dict[str, float]                 # path → s (entry)
    length: Optional[float]
    xyz: Optional[tuple[float, float, float]]
    upstream: list[str]
    downstream: list[str]
    rank: dict[str, int]                # path → rank among components of the same family on the path
    expects_asset: bool


def expectations(doc: Document, dataset: Optional[str] = None) -> list[Expected]:
    """Every component, with what the matcher needs from the model: names, kind, where it is, its neighbours.
    Virtual components (markers, reference points, interaction points, drifts) expect no asset."""
    res = resolve(doc)
    net = Network.of(doc)
    s_of: dict[str, dict[str, float]] = {}
    rank: dict[str, dict[str, int]] = {}
    for p in doc.paths:
        pos = net.positions(p.id, dataset)
        counter: dict[str, int] = {}
        for n in net.order(p.id):
            r = res.get(n.component)
            if r is None:
                continue
            v = pos.get(n.placement_id, {}).get("s")
            if v is not None:
                s_of.setdefault(n.component, {}).setdefault(p.id, v)
            if not r.virtual:
                counter[r.family] = counter.get(r.family, 0) + 1
                rank.setdefault(n.component, {}).setdefault(p.id, counter[r.family])
    xyz: dict[str, tuple] = {}
    for d in doc.datasets:
        if dataset and d.id != dataset:
            continue
        for key, v in d.values.items():
            g = v.geometry
            if g is not None and g.x is not None and g.y is not None:
                comp = next((n.component for n in net.nodes if n.placement_id == key), key)
                xyz.setdefault(comp, (g.x, g.y, g.z or 0.0))
    out = []
    for c in doc.components:
        r = res[c.id]
        geo = c.geometry.placement if c.geometry and c.geometry.placement else None
        point = (geo.x, geo.y, geo.z or 0.0) if geo is not None and geo.x is not None and geo.y is not None \
            else xyz.get(c.id)
        ups = [n.component for n, _d, _k in net.walk(c.id, "upstream", 1)]
        downs = [n.component for n, _d, _k in net.walk(c.id, "downstream", 1)]
        out.append(Expected(id=c.id, name=c.name or c.id, type=r.type, family=r.family, model_family=c.family,
                            aliases=list(c.aliases), paths=net.paths_of(c.id), s=s_of.get(c.id, {}),
                            length=r.length, xyz=point, upstream=ups, downstream=downs, rank=rank.get(c.id, {}),
                            expects_asset=not r.virtual and r.family in V.PHYSICAL_FAMILIES))
    return out


def context_names(doc: Document) -> set[str]:
    """Names that identify this model's beamline: the model, its systems and paths (not the facility: a
    facility has several beamlines, and an asset of another one must not count as this one's)."""
    names = {doc.model.id, doc.model.name or ""}
    names |= {s.id for s in doc.systems} | {s.name or "" for s in doc.systems}
    names |= {p.id for p in doc.paths} | {p.name or "" for p in doc.paths}
    return {_canon(n) for n in names if n and len(_canon(n)) >= 3}


def _names_match(where: str, ctx: set[str]) -> bool:
    w = _canon(where)
    return bool(w) and (w in ctx or any(len(c) >= 6 and (c in w or w in c) for c in ctx))


# --------------------------------------------------------------------------- names

def _canon(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def _tag(text: str) -> Optional[tuple[str, int]]:
    """Letters and trailing number, leading zeros ignored: QUAA101, quaa-101 and QUAA_0101 compare equal."""
    m = re.match(r"^([a-z][a-z0-9]*?)0*(\d+)$", _canon(text))
    return (m.group(1), int(m.group(2))) if m else None


def _number(text: str) -> Optional[int]:
    m = re.search(r"(\d+)\D*$", text or "")
    return int(m.group(1)) if m else None


def _asset_names(a: dict) -> list[str]:
    attrs = a.get("attributes") or {}
    names = [a.get("name") or ""] + list(a.get("aliases") or []) + list(attrs.get("aliases") or [])
    names += [attrs.get(k) for k in ("lattice_name", "model_name", "tag", "label") if attrs.get(k)]
    return [n for n in names if n]


def convention_names(e: Expected, rules: list[dict]) -> list[str]:
    """Asset names the configured naming rules expect for a component. A rule:
    {"component": "^QUAA(?P<n>\\d+)$", "asset": "MAG-ACC-QF{n:02d}"} (groups that are digits become ints)."""
    out = []
    for rule in rules:
        for name in [e.id, e.name, *e.aliases]:
            m = re.match(rule["component"], name or "", re.IGNORECASE)
            if not m:
                continue
            groups = {k: (int(v) if v and v.isdigit() else v) for k, v in m.groupdict().items()}
            try:
                out.append(rule["asset"].format(**groups))
            except (KeyError, ValueError, IndexError):
                continue
    return out


# --------------------------------------------------------------------------- scoring

def type_compatibility(e: Expected, asset_type: str, cfg: Config) -> Optional[float]:
    """How well an asset type can implement a component (None: it cannot — e.g. electronics for a BPM)."""
    if asset_type in DOWNSTREAM_ASSET_TYPES:
        return None
    table = {**_GENERIC, **cfg.family_asset_types.get(e.family, {}), **cfg.type_asset_types.get(e.type, {})}
    return table.get(asset_type)


def _attr(a: dict, *keys) -> Any:
    attrs = a.get("attributes") or {}
    for k in keys:
        if a.get(k) not in (None, ""):
            return a[k]
        if attrs.get(k) not in (None, ""):
            return attrs[k]
    return None


def score(e: Expected, a: dict, cfg: Config, ctx: set[str], extra: Iterable[dict] = ()) -> tuple[float, list[dict]]:
    ev: list[dict] = []
    names = _asset_names(a)
    cnames = {n.lower() for n in names}
    mine = [e.id, e.name]
    if any(n.lower() in cnames for n in mine):
        ev.append({"kind": "exact_name", "weight": 0.85})
    elif any(al.lower() in cnames for al in e.aliases) or any(
            al.lower() in {m.lower() for m in mine} for al in (a.get("aliases") or [])
            + list((a.get("attributes") or {}).get("aliases") or [])):
        ev.append({"kind": "exact_alias_match", "weight": 0.80})
    elif any(n.lower() in cnames for n in convention_names(e, cfg.naming_rules)):
        ev.append({"kind": "naming_convention", "weight": 0.75})
    else:
        tags = {_tag(n) for n in names} - {None}
        if any(_tag(n) in tags for n in [*mine, *e.aliases] if _tag(n)):
            ev.append({"kind": "normalized_name", "weight": 0.45})
    control = _attr(a, "control_name", "pv_prefix", "control_prefix")
    if control and any(_canon(n) and _canon(n) in _canon(str(control)) for n in [e.id, *e.aliases]):
        ev.append({"kind": "control_name_match", "weight": 0.45, "detail": str(control)})
    compat = type_compatibility(e, a.get("type") or "", cfg)
    kind = _attr(a, "component_type", "element_kind", "device_kind", "magnet_kind")
    if kind and V.normalise_type(str(kind)) == e.type and compat is not None:
        ev.append({"kind": "type_match", "weight": 0.25, "detail": f"{a.get('type')}: {kind}"})
    elif compat:
        ev.append({"kind": "type_match", "weight": round(0.25 * compat, 3), "detail": a.get("type")})
    if compat is not None and _number(e.id) is not None and _number(e.id) in {_number(n) for n in names}:
        ev.append({"kind": "number_match", "weight": 0.10})
    fam = _attr(a, "family")
    if fam and e.model_family and _canon(str(fam)) == _canon(e.model_family):
        ev.append({"kind": "family_match", "weight": 0.10})
    where = [str(x) for x in (_attr(a, "beamline"), _attr(a, "section"), *(a.get("locations") or [])) if x]
    beamline_known = bool(where)
    beamline_ok = any(_names_match(w, ctx) for w in where)
    if beamline_ok:
        ev.append({"kind": "beamline_match", "weight": 0.15, "detail": ", ".join(where)})
    delta_s = distance = None
    s_asset = _attr(a, "s", "s_position", "beam_s")
    if s_asset is not None and e.s:
        try:
            sa = float(s_asset)
            delta_s = min(min(abs(sa - s), abs(sa - (s + (e.length or 0) / 2))) for s in e.s.values())
        except (TypeError, ValueError):
            delta_s = None
        if delta_s is not None and delta_s <= cfg.s_tolerance:
            ev.append({"kind": "position_match", "weight": round(0.45 * (1 - delta_s / cfg.s_tolerance), 3),
                       "detail": f"delta_s {delta_s * 1000:.0f} mm"})
    x, y = _attr(a, "x"), _attr(a, "y")
    if e.xyz is not None and x is not None and y is not None:
        try:
            distance = math.dist(e.xyz, (float(x), float(y), float(_attr(a, "z") or 0.0)))
        except (TypeError, ValueError):
            distance = None
        if distance is not None and distance <= cfg.xyz_tolerance:
            ev.append({"kind": "geometry_match", "weight": round(0.45 * (1 - distance / cfg.xyz_tolerance), 3),
                       "detail": f"distance {distance * 1000:.0f} mm"})
    ev.extend(extra)
    conf = 1.0
    for x_ in ev:
        conf *= 1 - x_["weight"]
    conf = 1 - conf
    if not {x_["kind"] for x_ in ev} & ANCHORS:
        conf = min(conf, 0.45)
    if compat is None:
        conf = min(conf, 0.2)
        ev.append({"kind": "type_incompatible", "weight": 0, "detail": a.get("type")})
    if beamline_known and not beamline_ok:
        conf *= 0.5
        ev.append({"kind": "other_beamline", "weight": 0, "detail": ", ".join(where)})
    if delta_s is not None and delta_s > 5 * cfg.s_tolerance:
        conf *= 0.5
        ev.append({"kind": "position_mismatch", "weight": 0, "detail": f"delta_s {delta_s:.3f} m"})
    if distance is not None and distance > 5 * cfg.xyz_tolerance:
        conf *= 0.5
        ev.append({"kind": "geometry_mismatch", "weight": 0, "detail": f"distance {distance:.3f} m"})
    return round(conf, 4), [{**x_, "delta_s": delta_s} if x_["kind"] == "position_match" else x_ for x_ in ev]


IDENTITY = {"exact_name", "exact_alias_match", "naming_convention", "control_name_match"}
ANCHORS = IDENTITY | {"normalized_name", "position_match", "geometry_match", "order_match", "neighbour_consistent"}


# --------------------------------------------------------------------------- the run

def _order_evidence(doc: Document, exp: list[Expected], assets: list[dict], ctx: set[str],
                    cfg: Config) -> dict[tuple, dict]:
    """Rank along the line: the k-th magnet of the model's main path and the k-th magnet asset of this
    beamline, ordered by the assets' `sequence` (or `s`) — useful when names share nothing. Asset positions
    are along one line, so only the main path (the one with the most placements) is ranked."""
    main = max(doc.paths, key=lambda p: len(p.placements), default=None)
    if main is None:
        return {}
    out = {}
    by_family: dict[str, list[dict]] = {}
    for a in assets:
        if _attr(a, "sequence", "s", "s_position") is None or not _in_scope(a, ctx):
            continue
        for fam in V.PHYSICAL_FAMILIES:
            probe = Expected(id="", name="", type="", family=fam, model_family=None, aliases=[], paths=[], s={},
                             length=None, xyz=None, upstream=[], downstream=[], rank={}, expects_asset=True)
            if type_compatibility(probe, a.get("type") or "", cfg) and \
                    a.get("type") in cfg.family_asset_types.get(fam, {}):
                by_family.setdefault(fam, []).append(a)
    for fam, lst in by_family.items():
        lst.sort(key=lambda a: float(_attr(a, "sequence", "s", "s_position")))
        for k, a in enumerate(lst, 1):
            for e in exp:
                if e.family == fam and e.rank.get(main.id) == k:
                    out[(e.id, a["id"])] = {"kind": "order_match", "weight": 0.20, "detail": f"rank {k} on {main.id}"}
    return out


def run(doc: Document, assets: list[dict], existing: list[dict] = (), cfg: Optional[Config] = None,
        dataset: Optional[str] = None, now: Optional[str] = None) -> dict:
    """Propose bindings for every component that expects a physical asset. `existing` are the bindings
    already known: {"component", "asset", "relation", "status" (confirmed|proposed|rejected), "authority",
    "snapshot": {"name", "s"}}. Nothing here changes them; the result says how things differ."""
    cfg = cfg or Config()
    now = now or datetime.now(timezone.utc).isoformat()
    exp = expectations(doc, dataset)
    ctx = context_names(doc)
    live = [a for a in assets if not a.get("retired")]
    by_id = {a["id"]: a for a in assets}
    rejected = {(b["component"], b["asset"]) for b in existing if b.get("status") == "rejected"}
    confirmed = {b["component"]: b for b in existing if b.get("status") == "confirmed"
                 and b.get("relation", "implemented_by") == "implemented_by"}
    previous = {b["component"]: b for b in existing if b.get("status") in ("proposed", "ambiguous")
                and b.get("relation", "implemented_by") == "implemented_by"}
    taken = {b["asset"] for b in confirmed.values()}
    order_ev = _order_evidence(doc, exp, live, ctx, cfg)
    bound_asset_of = {c: b["asset"] for c, b in confirmed.items()}
    asset_rank = {}
    seq = sorted((a for a in live if _attr(a, "sequence", "s", "s_position") is not None),
                 key=lambda a: float(_attr(a, "sequence", "s", "s_position")))
    for k, a in enumerate(seq):
        asset_rank[a["id"]] = k

    def extra_for(e: Expected, a: dict) -> list[dict]:
        extra = [order_ev[(e.id, a["id"])]] if (e.id, a["id"]) in order_ev else []
        k = asset_rank.get(a["id"])
        if k is not None:
            for nb, step in [*((u, -1) for u in e.upstream), *((d, 1) for d in e.downstream)]:
                na = bound_asset_of.get(nb)
                if na in asset_rank and abs(asset_rank[na] - k) == 1:
                    extra.append({"kind": "neighbour_consistent", "weight": 0.25, "detail": f"next to {nb}"})
                    break
        return extra

    proposals: list[dict] = []
    for e in exp:
        if not e.expects_asset:
            proposals.append(_entry(e, "unmatched", None, 0, [], [], expects=False))
            continue
        scored = []
        for a in live:
            if (e.id, a["id"]) in rejected:
                continue
            conf, ev = score(e, a, cfg, ctx, extra_for(e, a))
            if conf > 0.15:
                scored.append((conf, a, ev))
        scored.sort(key=lambda t: -t[0])
        cands = [{"asset": _asset_view(a), "confidence": c, "evidence": ev} for c, a, ev in scored[:5]]
        if e.id in confirmed:
            b = confirmed[e.id]
            a = by_id.get(b["asset"])
            diff = "unchanged"
            notes = []
            if a is None or a.get("retired"):
                diff = "missing_asset"
                notes.append("the bound asset no longer exists")
            else:
                snap = b.get("snapshot") or {}
                if snap.get("name") and snap["name"] != a.get("name"):
                    diff = "changed"
                    notes.append(f"asset renamed {snap['name']} → {a.get('name')}")
                s_now = _attr(a, "s", "s_position")
                if snap.get("s") is not None and s_now is not None and abs(float(s_now) - float(snap["s"])) > cfg.s_tolerance:
                    diff = "changed"
                    notes.append(f"asset moved in s from {snap['s']} to {s_now}")
                better = [c for c in scored if c[1]["id"] != a["id"] and c[0] >= cfg.auto_threshold]
                own = next((c[0] for c in scored if c[1]["id"] == a["id"]), 0.0)
                if better and own < cfg.propose_threshold:
                    diff = "conflict"
                    notes.append(f"{better[0][1].get('name')} now matches better ({better[0][0]:.2f} vs {own:.2f})")
            entry = _entry(e, "confirmed", a or {"id": b["asset"], "name": (b.get("snapshot") or {}).get("name")},
                           b.get("confidence"), b.get("evidence") or [], cands, diff=diff, notes=notes,
                           authority=b.get("authority") or "human_confirmed")
            if diff != "unchanged":       # what could replace it, for the reviewer — never applied by itself
                entry["candidates"] = [c for c in cands if c["asset"]["id"] != b["asset"]]
            proposals.append(entry)
            continue
        pool = [t for t in scored if t[1]["id"] not in taken]
        best = pool[0] if pool else None
        second = pool[1] if len(pool) > 1 else None
        if best is None or best[0] < cfg.propose_threshold:
            status = "unmatched"
            chosen = None
        elif second is not None and best[0] - second[0] < cfg.margin:
            status, chosen = "ambiguous", None
        else:
            status, chosen = "proposed", best
        prev = previous.get(e.id)
        if status == "proposed":
            diff = "new_match" if prev is None else ("unchanged" if prev.get("asset") == chosen[1]["id"]
                                                     else "changed_candidate")
        elif prev is not None:
            diff = "candidate_lost" if status == "unmatched" else "changed_candidate"
        else:
            diff = "unchanged" if status != "ambiguous" else "new_match"
        kinds = {x["kind"] for x in chosen[2]} if chosen else set()
        auto = bool(chosen and chosen[0] >= cfg.auto_threshold and kinds & IDENTITY
                    and kinds & {"type_match", "component_type_match"})
        proposals.append(_entry(e, status, chosen[1] if chosen else None, chosen[0] if chosen else None,
                                chosen[2] if chosen else [], cands, diff=diff, auto=auto,
                                authority="suggestion" if chosen else None))
    _one_to_one(proposals, cfg)
    known = {e.id for e in exp}
    stale = [{**{k: b.get(k) for k in ("component", "asset", "relation", "status", "authority")},
              "diff": "stale_binding", "note": "the model no longer has this component"}
             for b in existing if b.get("status") == "confirmed" and b["component"] not in known]
    bound = {p["asset"]["id"] for p in proposals if p["asset"] and p["status"] in ("confirmed", "proposed")}
    unmodelled = [_asset_view(a) for a in live if a["id"] not in bound
                  and a.get("type") not in DOWNSTREAM_ASSET_TYPES and _in_scope(a, ctx)]
    rejected_list = [{"component": c, "asset": a} for c, a in rejected]
    return {"matcher": MATCHER, "matcher_version": VERSION, "generated_at": now, "config": {
        "propose_threshold": cfg.propose_threshold, "auto_threshold": cfg.auto_threshold, "margin": cfg.margin,
        "s_tolerance": cfg.s_tolerance, "xyz_tolerance": cfg.xyz_tolerance},
        "proposals": proposals, "unmodelled_assets": unmodelled, "rejected": rejected_list,
        "stale_bindings": stale,
        "summary": summary(proposals, len(live), len(rejected_list))}


def _in_scope(a: dict, ctx: set[str]) -> bool:
    where = [str(x) for x in (_attr(a, "beamline"), _attr(a, "section"), *(a.get("locations") or [])) if x]
    return not where or any(_names_match(w, ctx) for w in where)


def _one_to_one(proposals: list[dict], cfg: Config) -> None:
    """An asset implements one component: when two components are proposed the same asset, the clearly
    better keeps it and the other becomes ambiguous; when neither is clearly better, both are ambiguous."""
    by_asset: dict[str, list[dict]] = {}
    for p in proposals:
        if p["status"] == "proposed" and p["asset"]:
            by_asset.setdefault(p["asset"]["id"], []).append(p)
    for lst in by_asset.values():
        if len(lst) < 2:
            continue
        lst.sort(key=lambda p: -(p["confidence"] or 0))
        clear = (lst[0]["confidence"] or 0) - (lst[1]["confidence"] or 0) >= cfg.margin
        for p in (lst[1:] if clear else lst):
            p["status"] = "ambiguous"
            p["auto_acceptable"] = False
            p["notes"].append(f"{p['asset']['name']} is also the best candidate for another component")
            p["asset"] = None
            p["authority"] = None


def _asset_view(a: dict) -> dict:
    return {k: a.get(k) for k in ("id", "name", "type") if a.get(k) is not None}


def _entry(e: Expected, status: str, asset: Optional[dict], confidence, evidence, candidates, *, diff: str = "unchanged",
           notes: Optional[list] = None, auto: bool = False, authority: Optional[str] = None,
           expects: bool = True) -> dict:
    pos = next(iter(e.s.values()), None)
    # Evidence read back from a stored binding may be just the kinds.
    evidence = [x if isinstance(x, dict) else {"kind": str(x), "weight": None, "stored": True} for x in evidence or []]
    delta = next((x.get("delta_s") for x in evidence if x.get("kind") == "position_match"), None)
    return {"component": e.id, "name": e.name, "type": e.type, "family": e.family, "relation": "implemented_by",
            "paths": e.paths, "s": pos, "status": status, "expects_asset": expects,
            "asset": _asset_view(asset) if asset else None, "confidence": confidence,
            "evidence": [x["kind"] for x in evidence if x.get("weight") or x.get("stored")
                         or x["kind"].endswith(("incompatible", "mismatch")) or x["kind"] == "other_beamline"],
            "evidence_detail": evidence, "delta_s": delta, "candidates": candidates if status != "confirmed" else [],
            "auto_acceptable": auto, "authority": authority, "diff": diff, "notes": list(notes or [])}


def summary(proposals: list[dict], candidates: int, rejected: int) -> dict:
    expected = [p for p in proposals if p["expects_asset"]]
    count = lambda st: sum(1 for p in expected if p["status"] == st)  # noqa: E731
    diffs: dict[str, int] = {}
    for p in expected:
        diffs[p["diff"]] = diffs.get(p["diff"], 0) + 1
    return {"model_components": len(expected), "virtual_components": len(proposals) - len(expected),
            "physical_candidates": candidates, "confirmed": count("confirmed"), "proposed": count("proposed"),
            "auto_acceptable": sum(1 for p in expected if p["auto_acceptable"]), "ambiguous": count("ambiguous"),
            "unmatched": count("unmatched"), "rejected": rejected, "diff": diffs}


def filter_proposals(proposals: list[dict], group: Optional[str]) -> list[dict]:
    """By family group (magnets, diagnostics, vacuum, rf, optics, mechanical…) or status."""
    if not group:
        return proposals
    if group in V.FILTER_GROUPS:
        fams = V.FILTER_GROUPS[group]
        return [p for p in proposals if p["family"] in fams]
    return [p for p in proposals if p["status"] == group]
