"""Validating a canonical document: errors that make it unusable, warnings, and the completeness levels
it reaches.

A model need not hold everything. Levels, each with what it builds on:

    TOPOLOGY    paths, components and connectivity are consistent
    LATTICE     TOPOLOGY + every beam-acting component on a path has its physics parameters
    GEOMETRY    LATTICE + every placement has coordinates (a survey dataset, or placements in the hall)
    OPTICS      LATTICE + an optics dataset gives optical functions on every path
    PHYSICAL    TOPOLOGY + the beam's physical surroundings: boundaries, or vacuum/interception components
    INTEGRATED  TOPOLOGY + every physical component is bound to an external asset (confirmed bindings)

So a lattice with optics and no survey is OPTICS without GEOMETRY.

A model with topology only is valid. A MAD-X sequence without survey is LATTICE. An asset binding is never
required for a component to be valid.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from pydantic import ValidationError

from app.beam_model_core import vocabulary as V
from app.beam_model_core.network import Network, resolve
from app.beam_model_core.schema import Document
from app.beam_model_core.upgrade import upgrade

LEVELS = ("TOPOLOGY", "LATTICE", "GEOMETRY", "OPTICS", "PHYSICAL", "INTEGRATED")
REQUIRES = {"LATTICE": "TOPOLOGY", "GEOMETRY": "LATTICE", "OPTICS": "LATTICE", "PHYSICAL": "TOPOLOGY",
            "INTEGRATED": "TOPOLOGY"}

# Parameters that say what a beam-acting component does, by type (any one is enough). Steering elements
# (correctors, kickers) are left out: a corrector at zero kick is a normal lattice.
STRENGTH = {
    "dipole": ("angle", "k0", "field", "bend_angle"), "quadrupole": ("k1", "k1l", "gradient"),
    "sextupole": ("k2", "k2l"), "octupole": ("k3", "k3l"), "multipole": ("knl", "ksl", "kn", "ks"),
    "solenoid": ("ks", "field"), "rf_cavity": ("voltage", "gradient"),
    "accelerating_structure": ("voltage", "gradient", "energy_gain"), "buncher": ("voltage",),
    "lens": ("focal_length",), "mirror": ("angle", "incidence_angle", "radius_of_curvature"),
}


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    levels: list[str] = field(default_factory=list)
    gaps: dict[str, list[str]] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {"ok": self.ok, "levels": self.levels, "errors": self.errors,
                "warnings": self.warnings, "gaps": self.gaps, "summary": self.summary}


def load(raw: Any) -> tuple[Optional[Document], Report]:
    """Read and validate one document of any supported version."""
    rep = Report()
    try:
        data = upgrade(raw)
    except (ValueError, TypeError, AttributeError) as e:
        rep.errors.append(str(e))
        return None, rep
    try:
        doc = Document.model_validate(data)
    except ValidationError as e:
        for err in e.errors():
            where = ".".join(str(x) for x in err["loc"])
            rep.errors.append(f"{where}: {err['msg']}")
        return None, rep
    check(doc, rep)
    return doc, rep


def _dupes(ids: list[str]) -> list[str]:
    seen, out = set(), []
    for i in ids:
        if i in seen and i not in out:
            out.append(i)
        seen.add(i)
    return out


def check(doc: Document, rep: Report) -> Report:
    E, W = rep.errors.append, rep.warnings.append
    comps = {c.id: c for c in doc.components}
    defs = {d.id: d for d in doc.definitions}
    paths = {p.id: p for p in doc.paths}
    for what, ids in (("component", [c.id for c in doc.components]), ("definition", [d.id for d in doc.definitions]),
                      ("path", [p.id for p in doc.paths]), ("system", [s.id for s in doc.systems]),
                      ("beam", [b.id for b in doc.beams]), ("dataset", [d.id for d in doc.datasets])):
        for d in _dupes(ids):
            E(f"two {what}s have the id {d}")
    systems, beams = {s.id for s in doc.systems}, {b.id for b in doc.beams}
    for s in doc.systems:
        for b in s.beams:
            if b not in beams:
                E(f"system {s.id} carries unknown beam {b}")
    for b in doc.beams:
        for s in b.systems:
            if s not in systems:
                E(f"beam {b.id} names unknown system {s}")
    for c in doc.components:
        if c.definition and c.definition not in defs:
            E(f"component {c.id} names unknown definition {c.definition}")
        if not c.type and not (c.definition and c.definition in defs):
            E(f"component {c.id} has no type (and no definition to take it from)")
        for rel in ("mounted_on", "contained_in"):
            t = getattr(c, rel)
            if t and t not in comps:
                E(f"component {c.id} is {rel} unknown component {t}")
            if t == c.id:
                E(f"component {c.id} is {rel} itself")
        for f in c.fiducials:
            if f not in comps:
                E(f"component {c.id} names unknown fiducial {f}")
    res = resolve(doc) if not rep.errors else {}
    for r in res.values():
        if not r.known_type:
            W(f"component {r.id}: type {r.type} is not in the vocabulary; it is kept, described by its capabilities")
        unknown = [c for c in r.capabilities if c not in V.CAPABILITIES]
        if unknown:
            W(f"component {r.id}: capabilities {unknown} are not in the vocabulary")
        c = r.component
        if c.mounted_on and "mechanical_support" not in res[c.mounted_on].capabilities:
            W(f"component {c.id} is mounted on {c.mounted_on}, which does not declare mechanical_support")
    quantities = set(V.OBSERVABLES) | {o.quantity for o in doc.observables}
    for c in doc.components:
        for q in c.observes:
            if q not in quantities:
                E(f"component {c.id} observes {q}, neither built in nor declared in observables")
        if c.measurement_model:
            extra = set(c.measurement_model.observables) - set(c.observes)
            if extra:
                E(f"component {c.id}: its measurement model derives {sorted(extra)}, which it does not observe")
            if c.measurement_model.type not in V.MEASUREMENT_MODELS:
                W(f"component {c.id}: measurement model {c.measurement_model.type} is not a known kind")
        if c.observes and c.id in res and "diagnostic" not in res[c.id].capabilities:
            W(f"component {c.id} observes quantities but does not declare the diagnostic capability")
    for p in doc.paths:
        if p.system and p.system not in systems:
            E(f"path {p.id} names unknown system {p.system}")
        for b in p.beams:
            if b not in beams:
                E(f"path {p.id} names unknown beam {b}")
        pls = p.placement_list()
        for pl in pls:
            if pl.component not in comps:
                E(f"path {p.id} places unknown component {pl.component}")
        explicit = [pl.id for pl in pls if pl.id]
        for d in _dupes(explicit):
            E(f"path {p.id} has two placements with id {d}")
        counts: dict[str, int] = {}
        for pl in pls:
            counts[pl.component] = counts.get(pl.component, 0) + 1
        if p.reference and p.reference not in counts and p.reference not in explicit:
            E(f"path {p.id}: reference {p.reference} is not placed on it")
        if not pls:
            W(f"path {p.id} has no placements")
    for c in doc.connections:
        for end in (c.from_, c.to):
            if end.path not in paths:
                E(f"a {c.kind} connection names unknown path {end.path}")
    net = Network.of(doc) if not rep.errors else None
    if net is not None:
        for prob in net.problems:
            E(prob)
    for b in doc.boundaries:
        if b.path and b.path not in paths:
            E(f"boundary {b.id or ''} is along unknown path {b.path}")
        if b.component and b.component not in comps:
            E(f"boundary {b.id or ''} names unknown component {b.component}")
        if not b.path and not b.component:
            E(f"boundary {b.id or ''} names neither a path nor a component")
    for d in doc.datasets:
        if d.path and d.path not in paths:
            E(f"dataset {d.id} is for unknown path {d.path}")
        placed = set()
        if net is not None and d.path in paths:
            placed = {n.placement_id for n in net.order(d.path)} | {n.component for n in net.order(d.path)}
        for key in d.values:
            if d.path:
                if net is not None and key not in placed:
                    E(f"dataset {d.id} has values for {key}, which is not placed on {d.path}")
            elif key not in comps:
                E(f"dataset {d.id} has values for unknown component {key}")
        for f in d.fields:
            if f.path not in paths:
                E(f"dataset {d.id}: field {f.quantity} is along unknown path {f.path}")
    for b in doc.external_bindings:
        if b.component not in comps:
            E(f"a binding names unknown component {b.component}")
        if b.relation not in V.BINDING_RELATIONS:
            E(f"binding of {b.component}: relation {b.relation} is not one of {sorted(V.BINDING_RELATIONS)}")
    if not rep.errors:
        _levels(doc, rep, net, res)
    return rep


def _levels(doc: Document, rep: Report, net: Network, res) -> None:
    placed = {n.component for n in net.nodes}
    acting = [r for r in res.values() if r.id in placed and not r.virtual and r.type in STRENGTH]
    gaps: dict[str, list[str]] = {}
    has: dict[str, dict] = {}
    for d in doc.datasets:
        for key, v in d.values.items():
            comp = next((n.component for n in net.nodes if n.placement_id == key), key)
            e = has.setdefault(comp, {"physics": set(), "geometry": False, "optics": False})
            e["physics"] |= set(v.physics) | set((v.native.parameters if v.native else {}) or {})
            e["geometry"] = e["geometry"] or (v.geometry is not None and v.geometry.x is not None)
            e["optics"] = e["optics"] or bool(v.optics)
    lattice_gaps = []
    for r in acting:
        known = set(r.parameters) | has.get(r.id, {}).get("physics", set())
        known_lower = {k.lower() for k in known}
        if not any(k in known_lower for k in STRENGTH[r.type]):
            lattice_gaps.append(r.id)
    gaps["LATTICE"] = lattice_gaps
    geo_gaps = [n.component for n in net.nodes if not has.get(n.component, {}).get("geometry") and not (
        res[n.component].component.geometry and res[n.component].component.geometry.placement)]
    gaps["GEOMETRY"] = sorted(set(geo_gaps))
    optics_paths = {d.path for d in doc.datasets if any(v.optics for v in d.values.values())}
    gaps["OPTICS"] = sorted({p.id for p in doc.paths if p.placements} - optics_paths)
    physical = any(r.boundaries for r in res.values()) or any(
        r.family in ("vacuum", "interception") for r in res.values()) or bool(doc.boundaries)
    gaps["PHYSICAL"] = [] if physical else ["no boundaries and no vacuum or interception components"]
    bound = {b.component for b in doc.external_bindings if b.status == "confirmed"}
    expected = [r.id for r in res.values() if not r.virtual and r.family in V.PHYSICAL_FAMILIES]
    gaps["INTEGRATED"] = sorted(set(expected) - bound)
    rep.levels.append("TOPOLOGY")
    for lvl in LEVELS[1:]:
        if not gaps[lvl] and REQUIRES[lvl] in rep.levels:
            rep.levels.append(lvl)
    rep.gaps = {k: v[:50] for k, v in gaps.items() if v}
    rep.summary = {"components": len(doc.components), "definitions": len(doc.definitions), "paths": len(doc.paths),
                   "placements": len(net.nodes), "connections": len(doc.connections), "beams": len(doc.beams),
                   "datasets": len(doc.datasets), "boundaries": sum(len(r.boundaries) for r in res.values())
                   + len(doc.boundaries), "bindings": len(doc.external_bindings),
                   "shared_components": sorted(c for c, ns in net.by_component.items()
                                               if len({n.path for n in ns}) > 1),
                   "connected": net.is_connected()}
