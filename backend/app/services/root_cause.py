"""Impact and root-cause analysis over the object graph.

Two questions, one model.

  impact      This stopped: what does it take with it?
  root cause  These are misbehaving: what single thing, or which few, would explain them?

Both run on the dependency graph that `causal_model` makes out of the stored relations: an edge from a
provider to whatever depends on it, carrying what the dependent loses (control, function, permit,
degradation). What a node has lost decides where the loss can go next (see `causal_model.follows`),
so an IOC that stopped reaches the devices it serves and the assets they act on, but not the lattice
element an ion pump realises: the pump is still pumping, nobody can see it.

The ranking is deliberately plain and every term is returned, so a person or an assistant can argue
with it instead of trusting a number. Candidates are ordered by how well they fit the evidence, and
among those that fit equally, by how parsimonious they are:

  coverage       the share of the symptoms the candidate would explain
  contradiction  the share of the *healthy* things it would also have taken down, when the caller
                 knows some. A hypothesis that predicts a failure that did not happen is wrong.
  fit            coverage × (1 − contradiction): what the evidence says. This orders first.
  specificity    what it explains against everything it would take down. A rack that explains three
                 symptoms and would have downed three hundred things is a worse guess than a converter
                 that explains the same three and would have downed five.
  proximity      nearer to the symptom is likelier than three hops away
  parsimony      0.6 × specificity + 0.4 × proximity. This breaks ties in fit.

Fit is not folded into one number with parsimony, because a candidate that explains half the symptoms
must not outrank one that explains all of them for being smaller. Nothing here is a probability. What
the caller gets is the evidence: the path
from each candidate to each symptom, whether any hop of it is an inference rather than something a
file states, and how often tickets have named the candidate before.
"""
import collections
import hashlib
from dataclasses import dataclass, field
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset, Relation
from app.models.asset_subresources import AssetTicket
from app.models.issue import Issue
from app.models.schema import Schema
from app.services.causal_model import (
    CONTROL, DEGRADATION, FUNCTION, PERMIT, classify, dependency, follows,
)
from app.services.visibility import can_see

MAX_DEPTH = 8
MAX_AFFECTED = 600
STATES = (FUNCTION, CONTROL, PERMIT, DEGRADATION)


@dataclass(frozen=True)
class Hop:
    provider: str           # uid
    dependent: str          # uid
    relation: str           # as stored
    layer: str
    carries: str
    weak: bool


@dataclass
class NodeInfo:
    uid: str
    key: str
    name: str
    type: str
    inferred: bool
    lifecycle: Optional[str] = None


class DependencyGraph:
    """A workspace's asset relations, as who depends on whom."""

    def __init__(self, nodes: dict, hops: list, unclassified: collections.Counter):
        self.nodes: dict[str, NodeInfo] = nodes
        self.unclassified = unclassified
        self._by_key = {n.key: uid for uid, n in nodes.items()}
        self.dependents: dict[str, list[Hop]] = collections.defaultdict(list)
        self.providers: dict[str, list[Hop]] = collections.defaultdict(list)
        for hop in hops:
            self.dependents[hop.provider].append(hop)
            self.providers[hop.dependent].append(hop)

    def resolve(self, reference: str) -> Optional[str]:
        """An asset by uid or key."""
        return reference if reference in self.nodes else self._by_key.get(reference)

    def adopt(self, db: Session, workspace_id: str, references: Iterable[str]) -> None:
        """Objects that exist but have no relation a failure can cross: they are in the graph as
        themselves, so asking about one answers "nothing depends on it" instead of "no such object"."""
        for reference in references:
            if self.resolve(reference) is not None:
                continue
            asset = db.scalar(select(Asset).where(
                Asset.workspace_id == workspace_id, Asset.deleted_at.is_(None),
                (Asset.uid == reference) | (Asset.key == reference)))
            if asset is not None:
                self.nodes[asset.uid] = _info(asset)
                self._by_key[asset.key] = asset.uid


def _visible(asset: Asset, workspace_id: str) -> bool:
    return asset.workspace_id == workspace_id or bool(asset.is_global)


def load_graph(db: Session, workspace_id: str, layers: Optional[Iterable[str]] = None) -> DependencyGraph:
    """Every relation of this workspace that a failure can cross, with both ends visible from it.

    `layers` limits the walk to some axes: `["control"]` for "which hosts and IOCs could have cut this
    off", `["power", "cooling"]` for "what does the plant feed"."""
    wanted = set(layers) if layers else None
    relations = list(db.scalars(select(Relation).where(Relation.workspace_id == workspace_id)))
    uids = {r.from_asset_uid for r in relations} | {r.to_asset_uid for r in relations}
    assets = {}
    for chunk in _chunks(sorted(uids), 500):
        for asset in db.scalars(select(Asset).where(Asset.uid.in_(chunk), Asset.deleted_at.is_(None))):
            assets[asset.uid] = asset
    visible = {u: a for u, a in assets.items() if _visible(a, workspace_id)}

    hops, unclassified = [], collections.Counter()
    for r in relations:
        if r.from_asset_uid not in visible or r.to_asset_uid not in visible:
            continue
        meaning = classify(r.relation_type)
        if meaning is None:
            unclassified[r.relation_type] += 1
            continue
        edge = dependency(r.from_asset_uid, r.to_asset_uid, r.relation_type)
        if edge is None or (wanted is not None and meaning.layer not in wanted):
            continue
        hops.append(Hop(edge[0], edge[1], r.relation_type, meaning.layer, meaning.carries, meaning.weak))

    return DependencyGraph({u: _info(a) for u, a in visible.items()}, hops, unclassified)


def _info(a: Asset) -> NodeInfo:
    if not can_see(a):
        # A restricted unit stays in the dependency structure — hiding it would
        # change the answer — but as an anonymous node (I-ACL-1).
        opaque = "restricted-" + hashlib.sha256(f"asset:{a.uid}".encode()).hexdigest()[:12]
        return NodeInfo(uid=opaque, key=opaque, name="Restricted record", type=None, inferred=False, lifecycle=None)
    return NodeInfo(
        uid=a.uid, key=a.key, name=a.name, type=a.type,
        inferred="inferred" in ((a.attributes or {}).get("argus_keywords") or []),
        lifecycle=(a.attributes or {}).get("argus_lifecycle"),
    )


def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


# --- what a failure reaches ---------------------------------------------------------------------------------

@dataclass
class Reach:
    """One way a node is affected: the loss it suffers, how far away, and the path there."""
    state: str
    depth: int
    path: list = field(default_factory=list)      # Hops, from the origin


def spread(graph: DependencyGraph, origin: str, max_depth: int = MAX_DEPTH,
           limit: int = MAX_AFFECTED) -> tuple:
    """Everything the failure of `origin` reaches: {uid: {state: Reach}} and whether the cap bit.

    Breadth-first over (node, loss) pairs, so a node reached both as a lost readout and as a lost
    function is reported as both, each by its shortest path."""
    reached: dict[str, dict] = {origin: {FUNCTION: Reach(FUNCTION, 0, [])}}
    frontier = [(origin, FUNCTION)]
    truncated = False
    for depth in range(1, max_depth + 1):
        following = []
        for uid, state in frontier:
            path = reached[uid][state].path
            for hop in graph.dependents.get(uid, ()):
                if not follows(state, hop.carries):
                    continue
                known = reached.get(hop.dependent)
                if known is not None and hop.carries in known:
                    continue
                if known is None and len(reached) >= limit:
                    truncated = True
                    continue
                reached.setdefault(hop.dependent, {})[hop.carries] = Reach(hop.carries, depth, path + [hop])
                following.append((hop.dependent, hop.carries))
        frontier = following
        if not frontier:
            break
    return reached, truncated


def _describe_hop(graph: DependencyGraph, hop: Hop) -> dict:
    return {
        "provider": graph.nodes[hop.provider].key, "dependent": graph.nodes[hop.dependent].key,
        "relation": hop.relation, "layer": hop.layer, "carries": hop.carries,
    }


def _path_inferred(graph: DependencyGraph, path: list) -> bool:
    return any(graph.nodes[h.provider].inferred or graph.nodes[h.dependent].inferred for h in path)


def _node(graph: DependencyGraph, uid: str) -> dict:
    n = graph.nodes[uid]
    return {"uid": n.uid, "key": n.key, "name": n.name, "type": n.type, "inferred": n.inferred}


def impact_of(db: Session, workspace_id: str, reference: str, layers: Optional[list] = None,
              max_depth: int = 6) -> Optional[dict]:
    """This stopped: what does it take with it, how, and by which path?"""
    graph = load_graph(db, workspace_id, layers)
    graph.adopt(db, workspace_id, [reference])
    origin = graph.resolve(reference)
    if origin is None:
        return None
    reached, truncated = spread(graph, origin, min(max_depth, MAX_DEPTH))

    affected = []
    for uid, states in reached.items():
        if uid == origin:
            continue
        best = min(states.values(), key=lambda r: r.depth)
        affected.append({
            **_node(graph, uid),
            "depth": best.depth,
            "losses": {s: r.depth for s, r in sorted(states.items(), key=lambda kv: kv[1].depth)},
            "path": [_describe_hop(graph, h) for h in best.path],
            "layers": sorted({h.layer for h in best.path}),
            "via_inference": _path_inferred(graph, best.path),
            "weak": any(h.weak for h in best.path),
        })
    affected.sort(key=lambda a: (a["depth"], a["type"], a["key"]))

    return {
        "origin": _node(graph, origin),
        "affected": affected,
        "count": len(affected),
        "by_type": dict(collections.Counter(a["type"] for a in affected).most_common()),
        "by_loss": dict(collections.Counter(s for a in affected for s in a["losses"]).most_common()),
        "truncated": truncated,
        "unclassified_relations": dict(graph.unclassified),
    }


# --- what would explain these symptoms ---------------------------------------------------------------------------

def _upstream(graph: DependencyGraph, symptom: str, max_depth: int) -> set:
    """Every node with any path to `symptom`, ignoring what is lost along it: the candidate causes,
    before the loss rules say which of them can really reach it."""
    seen, frontier = {symptom}, [symptom]
    for _ in range(max_depth):
        following = []
        for uid in frontier:
            for hop in graph.providers.get(uid, ()):
                if hop.provider not in seen:
                    seen.add(hop.provider)
                    following.append(hop.provider)
        frontier = following
        if not frontier:
            break
    return seen


def ticket_history(db: Session, workspace_id: str, uids: list) -> dict:
    """How often tickets have named each object: evidence, not part of the score. An object that has
    failed four times before is a better suspect, and the caller can weigh that as they see fit."""
    counts: dict[str, list] = collections.defaultdict(list)
    for issue in db.scalars(select(Issue).where(Issue.workspace_id == workspace_id,
                                                Issue.asset_uid.in_(uids))):
        counts[issue.asset_uid].append((issue.attributes or {}).get("argus_source_key") or issue.uid)
    for asset_uid, key in db.execute(select(AssetTicket.asset_uid, AssetTicket.ticket_key)
                                     .where(AssetTicket.asset_uid.in_(uids))):
        if key not in counts[asset_uid]:
            counts[asset_uid].append(key)
    return {uid: {"tickets": len(keys), "recent": keys[:3]} for uid, keys in counts.items()}


def root_causes(
    db: Session, workspace_id: str, symptoms: list, healthy: Optional[list] = None,
    layers: Optional[list] = None, max_depth: int = 6, top: int = 10,
    symptom_kind: Optional[dict] = None,
) -> dict:
    """These are misbehaving: what would explain them?

    `symptoms` and `healthy` are objects by uid or key. `symptom_kind` maps a symptom to what is
    wrong with it: `control` (its readout is gone), `function` (it has stopped doing its job) or
    `permit` (it will not run, because a condition is not met); a symptom with no entry may be any. The kind matters: a pump that has lost its IOC is a control
    symptom, and a power supply cannot have caused it."""
    graph = load_graph(db, workspace_id, layers)
    graph.adopt(db, workspace_id, [*symptoms, *(healthy or [])])
    max_depth = min(max_depth, MAX_DEPTH)
    missing = [s for s in symptoms if graph.resolve(s) is None]
    symptom_uids = [u for u in (graph.resolve(s) for s in symptoms) if u is not None]
    healthy_uids = {u for u in (graph.resolve(h) for h in (healthy or [])) if u is not None}
    kinds = {graph.resolve(k): v for k, v in (symptom_kind or {}).items() if graph.resolve(k)}
    if not symptom_uids:
        return {"symptoms": [], "candidates": [], "hypotheses": [], "not_found": missing}

    candidates = set()
    for s in symptom_uids:
        candidates |= _upstream(graph, s, max_depth)

    scored = []
    spreads: dict = {}
    for c in candidates:
        reached, _ = spread(graph, c, max_depth)
        spreads[c] = reached
        explained, paths = {}, {}
        for s in symptom_uids:
            states = reached.get(s)
            if not states:
                continue
            want = kinds.get(s)
            # The candidate's own failure (depth 0) is a cause of whatever is wrong with it.
            usable = {st: r for st, r in states.items()
                      if want is None or st == want or r.depth == 0
                      or (want == FUNCTION and st == DEGRADATION)}
            if not usable:
                continue
            best = min(usable.values(), key=lambda r: r.depth)
            explained[s], paths[s] = best, best.path
        if not explained:
            continue
        downstream = {u for u in reached if u != c}
        contradicted = downstream & healthy_uids
        coverage = len(explained) / len(symptom_uids)
        contradiction = len(contradicted) / len(healthy_uids) if healthy_uids else 0.0
        specificity = len(explained) / max(1, len(downstream | set(explained)))
        proximity = sum(1 / (1 + r.depth) for r in explained.values()) / len(explained)
        scored.append({
            "uid": c, "explained": explained, "coverage": coverage, "contradiction": contradiction,
            "specificity": specificity, "proximity": proximity, "downstream": len(downstream),
            "contradicted": contradicted,
            "fit": coverage * (1 - contradiction),
            "parsimony": 0.6 * specificity + 0.4 * proximity,
        })
    scored.sort(key=lambda x: (-x["fit"], -x["parsimony"], graph.nodes[x["uid"]].key))

    history = ticket_history(db, workspace_id, [x["uid"] for x in scored[:top]])
    out = []
    for x in scored[:top]:
        uid = x["uid"]
        out.append({
            **_node(graph, uid),
            "fit": round(x["fit"], 3),
            "parsimony": round(x["parsimony"], 3),
            "coverage": round(x["coverage"], 3),
            "contradiction": round(x["contradiction"], 3),
            "specificity": round(x["specificity"], 3),
            "proximity": round(x["proximity"], 3),
            "explains": [
                {**_node(graph, s), "loss": r.state, "depth": r.depth,
                 "path": [_describe_hop(graph, h) for h in r.path],
                 "via_inference": _path_inferred(graph, r.path)}
                for s, r in x["explained"].items()
            ],
            "would_also_affect": x["downstream"],
            "contradicted_by": sorted(graph.nodes[u].key for u in x["contradicted"]),
            "history": history.get(uid, {"tickets": 0, "recent": []}),
        })

    return {
        "symptoms": [_node(graph, s) for s in symptom_uids],
        "candidates": out,
        "hypotheses": _hypotheses(graph, scored, symptom_uids),
        "not_found": missing,
        "unclassified_relations": dict(graph.unclassified),
    }


def _hypotheses(graph: DependencyGraph, scored: list, symptoms: list, limit: int = 4) -> list:
    """The fewest causes that between them explain every symptom, chosen greedily: the best-scoring
    candidate, then the best of what it left unexplained, and so on. Several symptoms often have
    several causes, and one ranked list cannot say so."""
    remaining, chosen = set(symptoms), []
    # A cause that would have taken down something known to be working is refuted, not just less likely.
    pool = [x for x in scored if not x["contradicted"]]
    while remaining and pool and len(chosen) < limit:
        # Fewest causes first; among equals, a cause upstream of a symptom over the symptom itself,
        # which explains it only by restating it.
        pool.sort(key=lambda x: (-len(remaining & set(x["explained"])), x["uid"] in symptoms,
                                 -x["fit"], -x["parsimony"]))
        best = pool.pop(0)
        gained = remaining & set(best["explained"])
        if not gained:
            break
        chosen.append({**_node(graph, best["uid"]),
                       "explains": sorted(graph.nodes[s].key for s in gained)})
        remaining -= gained
    return [{"causes": chosen, "unexplained": sorted(graph.nodes[s].key for s in remaining)}] if chosen else []


# --- what the design depends on ----------------------------------------------------------------------------------------

def blast_radius(db: Session, workspace_id: str, layers: Optional[list] = None,
                 top: int = 20, max_depth: int = 6) -> dict:
    """The single points of failure: what would take the most with it.

    Ranked by weight = 3 × the things that lose their function + those that lose their readout +
    those that are degraded + those that lose a permit. A lost function is an outage and a lost
    readout is a blind spot, and three blind spots are not one outage, but a converter that blinds two
    hundred channels is a bigger problem than a supply that stops one magnet. Both lists are returned
    on their own as well, because which one matters depends on who is asking."""
    graph = load_graph(db, workspace_id, layers)
    ranked = []
    for uid, node in graph.nodes.items():
        if not graph.dependents.get(uid):
            continue
        reached, _ = spread(graph, uid, max_depth)
        tally = collections.Counter(st for u, states in reached.items() if u != uid for st in states)
        if tally:
            entry = {**_node(graph, uid), "function": tally[FUNCTION], "control": tally[CONTROL],
                     "degradation": tally[DEGRADATION], "permit": tally[PERMIT]}
            entry["weight"] = 3 * entry["function"] + entry["control"] + entry["degradation"] + entry["permit"]
            ranked.append(entry)
    weighted = sorted(ranked, key=lambda r: (-r["weight"], r["key"]))
    return {
        "assets": weighted[:top],
        "by_function": sorted((r for r in ranked if r["function"]), key=lambda r: (-r["function"], r["key"]))[:top],
        "by_readout": sorted((r for r in ranked if r["control"]), key=lambda r: (-r["control"], r["key"]))[:top],
        "considered": len(ranked),
        "unclassified_relations": dict(graph.unclassified),
    }
