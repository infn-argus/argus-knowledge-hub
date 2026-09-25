"""Authority policies (asset-model-revision §7.7, fifth revision).

A policy decides, for each claim, its rank (authoritative, contributory,
advisory, ignored) and whether it is accepted automatically. The rule that
applies is chosen **lexicographically**, level by level:

    L1 source_instance given   L2 semantic rule given   L3 scope count
    L4 predicate exact>glob    L5 type exact>inherited  L6 inherited depth
    L7 source_kind given       L8 explicit priority

`validate()` checks a policy against a finite vocabulary before activation:
ambiguous and unreachable rules are errors, shadowed and redundant ones are
warnings, and a scoped rule that makes a non-owner authoritative for a
protected predicate is an error unless it says why (`allow_dominant`).
"""
from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from typing import Iterable, Optional

RANKS = ("authoritative", "contributory", "advisory", "ignored")
RANK_ORDER = {r: i for i, r in enumerate(RANKS)}
DIMENSIONS = ("predicate", "object_type", "owner_workspace", "facility", "domain",
              "source_kind", "source_instance", "rule")


class PolicyError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class ClaimContext:
    predicate: str
    object_type: Optional[str]
    type_lineage: tuple[str, ...]      # the type and its ancestors, nearest first
    owner_workspace: Optional[str]
    facility: Optional[str]
    domain: Optional[str]
    source_kind: str
    source_instance: str
    rule: Optional[str]
    method: str


@dataclass(frozen=True)
class Effect:
    rule_id: str
    rank: str
    auto_accept: bool
    exclusive_set: bool = False
    tie_break: str = "conflict"

    def signature(self) -> tuple:
        return (self.rank, self.auto_accept, self.exclusive_set, self.tie_break)


def _as_list(v) -> Optional[list]:
    if v is None:
        return None
    return list(v) if isinstance(v, (list, tuple)) else [v]


@dataclass
class Rule:
    id: str
    match: dict
    effect: Effect
    priority: int = 0
    allow_dominant: Optional[str] = None
    type_depth: dict = field(default_factory=dict)

    # --- matching ---------------------------------------------------------
    def matches(self, ctx: ClaimContext) -> bool:
        m = self.match
        preds = _as_list(m.get("predicate"))
        if preds is not None and not any(fnmatchcase(ctx.predicate, p) for p in preds):
            return False
        types = _as_list(m.get("object_type"))
        if types is not None and not any(_type_matches(t, ctx) for t in types):
            return False
        for dim, value in (("owner_workspace", ctx.owner_workspace), ("facility", ctx.facility),
                           ("domain", ctx.domain), ("source_kind", ctx.source_kind),
                           ("source_instance", ctx.source_instance), ("rule", ctx.rule)):
            wanted = _as_list(m.get(dim))
            if wanted is not None and value not in wanted:
                return False
        return True

    # --- precedence (L1…L8) ------------------------------------------------
    def key(self) -> tuple:
        m = self.match
        preds = _as_list(m.get("predicate"))
        if preds is None:
            l4 = 0
        else:
            l4 = 2 if all(not any(c in p for c in "*?[") for p in preds) else 1
        types = _as_list(m.get("object_type"))
        if types is None:
            l5, l6 = 0, 0
        elif all(not t.endswith("+") for t in types):
            l5, l6 = 2, 0
        else:
            l5 = 1
            l6 = min(self.type_depth.get(t.rstrip("+"), 0) for t in types)
        scope = sum(1 for d in ("owner_workspace", "facility", "domain") if m.get(d) is not None)
        return (
            1 if m.get("source_instance") is not None else 0,
            1 if m.get("rule") is not None else 0,
            scope, l4, l5, l6,
            1 if m.get("source_kind") is not None else 0,
            self.priority,
        )


def _type_matches(spec: str, ctx: ClaimContext) -> bool:
    if spec.endswith("+"):
        return spec[:-1] in ctx.type_lineage
    return ctx.object_type == spec


DEFAULT_AUTO = {"authoritative": True, "contributory": True, "advisory": False, "ignored": False}


class Policy:
    def __init__(self, body: dict, type_depth: Optional[dict] = None):
        self.body = body
        self.version = str(body.get("policy_version", "unversioned"))
        self.type_depth = type_depth or {}
        # `reconciled`: what the pipeline itself establishes from the ledger
        # (service intervals, successors); a person's confirmation still wins.
        self.defaults = {**{"manual": "authoritative", "stated": "contributory",
                            "resolved": "contributory", "inferred": "advisory", "reconciled": "authoritative"},
                         **(body.get("defaults") or {})}
        self.protected = body.get("protected") or []
        self.rules: list[Rule] = []
        for raw in body.get("rules") or []:
            rank = raw.get("rank", "contributory")
            if rank not in RANKS:
                raise PolicyError([f"rule {raw.get('id')}: unknown rank {rank!r}"])
            unknown = set(raw.get("match") or {}) - set(DIMENSIONS)
            if unknown:
                raise PolicyError([f"rule {raw.get('id')}: unknown match dimension(s) {sorted(unknown)}"])
            effect = Effect(raw["id"], rank, bool(raw.get("auto_accept", DEFAULT_AUTO[rank])),
                            bool(raw.get("exclusive_set", False)), raw.get("tie_break", "conflict"))
            self.rules.append(Rule(raw["id"], raw.get("match") or {}, effect, int(raw.get("priority", 0)),
                                   raw.get("allow_dominant"), self.type_depth))

    def select(self, ctx: ClaimContext) -> Effect:
        candidates = [r for r in self.rules if r.matches(ctx)]
        if not candidates:
            rank = self.defaults.get(ctx.method, "advisory")
            return Effect(f"default:{ctx.method}", rank, DEFAULT_AUTO[rank])
        candidates.sort(key=lambda r: r.key(), reverse=True)
        return candidates[0].effect


# --------------------------------------------------------------------------- vocabulary

@dataclass
class Vocabulary:
    """The finite values each match dimension can take. Registering a stream
    or a rule changes it, and a policy validated against an older vocabulary
    must be validated again (§7.7)."""
    types: dict                     # name -> lineage tuple (nearest first)
    workspaces: list
    facilities: list
    domains: list
    streams: dict                   # source_instance -> source_kind
    rules: list
    predicates: list = field(default_factory=list)

    def digest(self) -> str:
        payload = json.dumps({"streams": sorted(self.streams.items()), "rules": sorted(self.rules),
                              "workspaces": sorted(self.workspaces), "facilities": sorted(self.facilities),
                              "domains": sorted(self.domains), "types": sorted(self.types),
                              "predicates": sorted(self.predicates)}, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def depths(self) -> dict:
        return {name: len(lineage) - 1 for name, lineage in self.types.items()}


OTHER = "∅other"


def _dimension_values(policy: Policy, vocab: Vocabulary) -> dict:
    """The values each dimension can take, reduced to one representative per
    distinct matching signature: two types that every rule treats alike are
    interchangeable for validation, which keeps the enumeration small however
    large the catalogue grows."""
    mentioned: dict[str, set] = {d: set() for d in DIMENSIONS}
    for rule in policy.rules:
        for d in DIMENSIONS:
            for v in _as_list(rule.match.get(d)) or []:
                mentioned[d].add(v)
    for p in policy.protected:
        for v in _as_list(p.get("predicate")) or []:
            mentioned["predicate"].add(v)

    pred_specs = sorted(mentioned["predicate"])
    predicates = set(vocab.predicates) | {OTHER}
    for p in pred_specs:
        predicates.add(p.replace("*", "x").replace("?", "x") if any(c in p for c in "*?") else p)
    by_sig: dict = {}
    for p in sorted(predicates):
        by_sig.setdefault(tuple(fnmatchcase(p, spec) for spec in pred_specs), p)

    type_specs = sorted(mentioned["object_type"])
    types_by_sig: dict = {}
    for name in sorted(set(vocab.types) | {OTHER}):
        lineage = vocab.types.get(name, (name,))
        sig = tuple((spec[:-1] in lineage) if spec.endswith("+") else (spec == name) for spec in type_specs)
        types_by_sig.setdefault(sig, name)

    kinds, insts = mentioned["source_kind"], mentioned["source_instance"]
    streams: dict = {}
    candidates = [(k, i) for i, k in vocab.streams.items()] + [(k, f"{OTHER}:{k}") for k in kinds] + \
                 [(OTHER, i) for i in insts if i not in vocab.streams] + [(OTHER, OTHER)]
    for kind, inst in candidates:
        streams.setdefault((kind if kind in kinds else OTHER, inst if inst in insts else OTHER), (kind, inst))

    def small(dim: str, extra: list) -> list:
        return sorted(set(mentioned[dim]) | {OTHER}) if mentioned[dim] else [OTHER]

    return {
        "predicate": sorted(by_sig.values()),
        "object_type": sorted(types_by_sig.values()),
        "owner_workspace": small("owner_workspace", vocab.workspaces),
        "facility": small("facility", vocab.facilities),
        "domain": small("domain", vocab.domains),
        "stream": sorted(streams.values()),
        "rule": sorted(set(mentioned["rule"]) | {OTHER}),
    }


def validate(policy: Policy, vocab: Vocabulary, limit: int = 400_000) -> dict:
    """Errors and warnings for `policy` over `vocab`. Raises PolicyError when
    there are errors; returns the report otherwise."""
    errors: list[str] = []
    warnings: list[str] = []
    dims = _dimension_values(policy, vocab)
    # Only the dimensions a rule constrains can separate rules; the others are
    # fixed to one representative value to keep the enumeration small.
    used = {d for r in policy.rules for d in r.match} | ({"predicate"} if policy.protected else set())
    axes = {}
    for d in ("predicate", "object_type", "owner_workspace", "facility", "domain", "rule"):
        axes[d] = dims[d] if d in used else [OTHER]
    axes["stream"] = dims["stream"] if ({"source_kind", "source_instance"} & used) else [(OTHER, OTHER)]
    total = 1
    for v in axes.values():
        total *= len(v)
    if total > limit:
        raise PolicyError([f"vocabulary too large to validate exhaustively ({total} combinations)"])

    won: dict[str, set] = {r.id: set() for r in policy.rules}
    matched: dict[str, int] = {r.id: 0 for r in policy.rules}
    lost_to_other_effect: dict[str, set] = {r.id: set() for r in policy.rules}
    ambiguous: set = set()
    for pred, typ, ws, fac, dom, rule, (kind, inst) in itertools.product(
            axes["predicate"], axes["object_type"], axes["owner_workspace"], axes["facility"],
            axes["domain"], axes["rule"], axes["stream"]):
        lineage = vocab.types.get(typ, (typ,))
        ctx = ClaimContext(pred, typ, tuple(lineage), ws, fac, dom, kind, inst,
                           None if rule == OTHER else rule, "stated")
        hits = sorted((r for r in policy.rules if r.matches(ctx)), key=lambda r: r.key(), reverse=True)
        if not hits:
            continue
        top = hits[0]
        for r in hits:
            matched[r.id] += 1
        if len(hits) > 1 and hits[1].key() == top.key() and hits[1].effect.signature() != top.effect.signature():
            ambiguous.add(tuple(sorted((top.id, hits[1].id))))
        won[top.id].add(1)
        for r in hits[1:]:
            if r.effect.signature() != top.effect.signature():
                lost_to_other_effect[r.id].add(top.id)
    for a, b in sorted(ambiguous):
        errors.append(f"ambiguous: rules {a!r} and {b!r} tie on every precedence level with different effects")
    for r in policy.rules:
        if matched[r.id] == 0:
            warnings.append(f"rule {r.id!r} matches nothing in the current vocabulary")
        elif not won[r.id]:
            if lost_to_other_effect[r.id]:
                errors.append(f"unreachable: rule {r.id!r} is always outranked "
                              f"(by {sorted(lost_to_other_effect[r.id])})")
            else:
                warnings.append(f"redundant: rule {r.id!r} is always outranked by rules with the same effect")
        elif lost_to_other_effect[r.id]:
            warnings.append(f"shadowed: rule {r.id!r} is partly outranked by {sorted(lost_to_other_effect[r.id])}")
    # Dominant: a source-specific or scoped rule granting authority on a protected predicate.
    for r in policy.rules:
        k = r.key()
        if not (k[0] or k[1] or k[2]) or r.effect.rank not in ("authoritative", "contributory"):
            continue
        preds = _as_list(r.match.get("predicate"))
        kinds = set(_as_list(r.match.get("source_kind")) or [])
        for inst in _as_list(r.match.get("source_instance")) or []:
            kinds.add(vocab.streams.get(inst, OTHER))
        for p in policy.protected:
            owners = set(_as_list(p.get("owners")) or [])
            protected_preds = _as_list(p.get("predicate")) or []
            touches = preds is None or any(fnmatchcase(pp, q) or fnmatchcase(q, pp)
                                           for pp in protected_preds for q in preds)
            if not touches:
                continue
            non_owner = not kinds or bool(kinds - owners)
            if non_owner and not r.allow_dominant:
                errors.append(f"dominant: rule {r.id!r} would make a non-owner authoritative for "
                              f"protected {protected_preds} (owners {sorted(owners)})")
    report = {"version": policy.version, "vocabulary": vocab.digest(), "combinations": total,
              "errors": errors, "warnings": warnings}
    if errors:
        raise PolicyError(errors)
    return report


# --------------------------------------------------------------------------- default

DEFAULT_POLICY = {
    "policy_version": "slice-2026.09.2",
    "defaults": {"manual": "authoritative", "stated": "contributory",
                 "resolved": "contributory", "inferred": "advisory"},
    "protected": [
        {"predicate": ["attr:serial", "attr:inventory_number"], "owners": ["insight", "person"]},
    ],
    "rules": [
        {"id": "insight-identity", "match": {"predicate": ["attr:serial", "attr:inventory_number",
                                                           "attr:manufacturer", "attr:model"],
                                             "source_kind": "insight"},
         "rank": "authoritative"},
        {"id": "insight-location", "match": {"predicate": "attr:argus_location", "source_kind": "insight"},
         "rank": "authoritative"},
        {"id": "config-owns-control", "match": {"object_type": ["IOC", "Control Device"], "source_kind": "epik8s"},
         "rank": "authoritative"},
        # A position inferred from a channel name exists as soon as it is read,
        # visibly unconfirmed (§7.3: name-rule inferences that make objects
        # are accepted, composition by name pairing is proposed).
        {"id": "inferred-positions", "match": {"rule": ["infer.vac.sip/1", "infer.vac.sip/2", "infer.vac.sip/3",
                                                        "infer.mag.ps/1"],
                                               "predicate": ["exists", "attr:position_class", "rel:acts on",
                                                             "rel:assigned to"]},
         "rank": "advisory", "auto_accept": True},
        # An Installation found from an asset: URL is only ever a proposal (§8.4).
        # The proposal is its existence; its position, unit and dates project
        # so a reviewer sees exactly what is being proposed.
        {"id": "resolved-installations", "match": {"rule": "resolve.asset_url/1", "predicate": "exists"},
         "rank": "contributory", "auto_accept": False},
    ],
}
