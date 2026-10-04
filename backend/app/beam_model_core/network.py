"""The beam-transport network of a document, and components as they effectively are.

Nodes are *placements* — a component's place on a path — so one component can be on several paths (a shared
interaction region, a common section before a switchyard) without making any path's order ambiguous. Edges:

    next      consecutive placements of a path
    closes    a closed path's last placement to its first (a ring is an ordinary path with this edge)
    branch    a placement on one path to the first placement of another (a septum, a beam splitter)
    merge     a path's last placement into a placement on another (injection)
    continue  a path's last placement to another path's first (an injector chain)

`s` is never used to order anything here: it is a coordinate along one path (`positions`).
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from app.beam_model_core import vocabulary as V
from app.beam_model_core.schema import Boundary, Component, Document, Material, Placement, StateDef, StateModel


# --------------------------------------------------------------------------- components as they effectively are

@dataclass
class Resolved:
    """A component with its definition and the vocabulary's defaults applied."""
    id: str
    name: str
    type: str
    family: str
    capabilities: list[str]
    parameters: dict[str, Any]
    length: Optional[float]
    boundaries: list[Boundary]
    material: Optional[Material]
    states: Optional[StateModel]
    virtual: bool
    known_type: bool
    component: Component


def resolve(doc: Document) -> dict[str, Resolved]:
    defs = {d.id: d for d in doc.definitions}
    out = {}
    for c in doc.components:
        d = defs.get(c.definition) if c.definition else None
        t = V.normalise_type(c.type or (d.type if d else "") or "generic")
        caps = c.capabilities if c.capabilities is not None else (
            d.capabilities if d is not None and d.capabilities is not None else V.default_capabilities(t))
        params = {**(d.parameters if d else {}), **c.parameters}
        length = None
        for src in (c.geometry, d.geometry if d else None):
            if src is not None and src.length is not None:
                length = src.length
                break
        if length is None and isinstance(params.get("length"), (int, float)):
            length = float(params["length"])
        bounds = [*(d.boundaries if d else []), *c.boundaries,
                  *(b for b in doc.boundaries if b.component == c.id and b.path is None)]
        states = c.states or (d.states if d else None)
        if states is None and t in V.DEFAULT_STATES and ({"movable", "retractable", "pulsed"} & set(caps)):
            states = StateModel(states=[StateDef(name=n, meaning=m) for n, m in V.DEFAULT_STATES[t].items()],
                                default=next(iter(V.DEFAULT_STATES[t])))
        out[c.id] = Resolved(id=c.id, name=c.name or c.id, type=t, family=V.family(t), capabilities=sorted(set(caps)),
                             parameters=params, length=length, boundaries=bounds,
                             material=c.material or (d.material if d else None), states=states,
                             virtual=V.is_virtual(t, caps), known_type=t in V.TYPES, component=c)
    return out


# --------------------------------------------------------------------------- the network

@dataclass(frozen=True)
class Node:
    path: str
    index: int
    component: str
    placement_id: str
    reversed: bool = False

    @property
    def key(self) -> str:
        return f"{self.path}/{self.placement_id}"


@dataclass
class Network:
    doc: Document
    nodes: list[Node] = field(default_factory=list)
    by_path: dict[str, list[Node]] = field(default_factory=dict)
    by_component: dict[str, list[Node]] = field(default_factory=dict)
    succ: dict[Node, list[tuple[Node, str]]] = field(default_factory=dict)
    pred: dict[Node, list[tuple[Node, str]]] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------ building
    @classmethod
    def of(cls, doc: Document) -> "Network":
        net = cls(doc=doc)
        for p in doc.paths:
            seen: dict[str, int] = {}
            row = []
            for i, pl in enumerate(p.placement_list()):
                seen[pl.component] = seen.get(pl.component, 0) + 1
                pid = pl.id or (pl.component if seen[pl.component] == 1 else f"{pl.component}#{seen[pl.component]}")
                n = Node(p.id, i, pl.component, pid, pl.reversed)
                row.append(n)
                net.nodes.append(n)
                net.by_component.setdefault(pl.component, []).append(n)
            net.by_path[p.id] = row
            for a, b in zip(row, row[1:]):
                net._edge(a, b, "next")
            if p.topology == "closed" and len(row) > 1:
                net._edge(row[-1], row[0], "closes")
        for c in doc.connections:
            # Leaves from the named placement (else the path's end); arrives at the named one (else its start).
            a = net.endpoint(c.from_.path, c.from_.component, "last")
            b = net.endpoint(c.to.path, c.to.component, "first")
            if a is None or b is None:
                net.problems.append(f"{c.kind} from {c.from_.path}:{c.from_.component or 'end'} to "
                                    f"{c.to.path}:{c.to.component or 'start'} names no placement")
                continue
            net._edge(a, b, c.kind)
        return net

    def _edge(self, a: Node, b: Node, kind: str) -> None:
        self.succ.setdefault(a, []).append((b, kind))
        self.pred.setdefault(b, []).append((a, kind))

    def endpoint(self, path: str, ref: Optional[str], default: str) -> Optional[Node]:
        row = self.by_path.get(path) or []
        if not row:
            return None
        if ref is None:
            return row[0] if default == "first" else row[-1]
        hits = [n for n in row if n.placement_id == ref] or [n for n in row if n.component == ref]
        return hits[0] if hits else None

    # ------------------------------------------------------------------ reading
    def order(self, path: str) -> list[Node]:
        return list(self.by_path.get(path) or [])

    def paths_of(self, component: str) -> list[str]:
        return sorted({n.path for n in self.by_component.get(component, [])})

    def _start(self, ref: str | Node) -> list[Node]:
        if isinstance(ref, Node):
            return [ref]
        if "/" in ref:
            path, pid = ref.split("/", 1)
            n = self.endpoint(path, pid, "first")
            return [n] if n else []
        return list(self.by_component.get(ref, []))

    def walk(self, ref: str | Node, direction: str = "downstream", n: Optional[int] = None) -> list[tuple[Node, int, str]]:
        """Placements reachable from a component (all its placements) or a placement, nearest first:
        (node, distance, edge kind). Rings are walked round once."""
        edges = self.succ if direction == "downstream" else self.pred
        start = self._start(ref)
        seen = set(start)
        out, q = [], deque((s, 0) for s in start)
        while q:
            cur, d = q.popleft()
            if n is not None and d >= n:
                continue
            for nxt, kind in edges.get(cur, []):
                if nxt in seen:
                    continue
                seen.add(nxt)
                out.append((nxt, d + 1, kind))
                q.append((nxt, d + 1))
        return out

    def between(self, a: str, b: str, path: Optional[str] = None) -> Optional[list[Node]]:
        """The placements strictly between two components. On a common path, along it (a closed path: the
        shorter way round); otherwise along the network, the shortest way in either direction."""
        common = [path] if path else sorted(set(self.paths_of(a)) & set(self.paths_of(b)))
        for p in common:
            row = self.by_path.get(p) or []
            ia = [n.index for n in row if n.component == a or n.placement_id == a]
            ib = [n.index for n in row if n.component == b or n.placement_id == b]
            if not ia or not ib:
                continue
            i, j = ia[0], ib[0]
            closed = next((x.topology == "closed" for x in self.doc.paths if x.id == p), False)
            if i <= j:
                fwd = row[i + 1:j]
                back = (row[j + 1:] + row[:i]) if closed else None
            else:
                fwd = (row[i + 1:] + row[:j]) if closed else None
                back = row[j + 1:i]
            options = [x for x in (fwd, back) if x is not None]
            return min(options, key=len) if options else []
        best = None
        for src, dst in ((a, b), (b, a)):
            prev: dict[Node, Optional[Node]] = {s: None for s in self._start(src)}
            q = deque(prev)
            target = set(self._start(dst))
            while q:
                cur = q.popleft()
                if cur in target:
                    chain, x = [], prev[cur]
                    while x is not None and prev.get(x) is not None:
                        chain.append(x)
                        x = prev[x]
                    chain.reverse()
                    if best is None or len(chain) < len(best):
                        best = chain
                    break
                for nxt, _k in self.succ.get(cur, []):
                    if nxt not in prev:
                        prev[nxt] = cur
                        q.append(nxt)
        return best

    def sources(self) -> list[Node]:
        """Where beams start: placements with nothing upstream, or of a source component."""
        res = resolve(self.doc)
        return [n for n in self.nodes if not self.pred.get(n)
                or "beam_source" in res.get(n.component, _NONE).capabilities]

    def destinations(self) -> list[Node]:
        res = resolve(self.doc)
        return [n for n in self.nodes if not self.succ.get(n)
                or "beam_destination" in res.get(n.component, _NONE).capabilities]

    def component_edges(self) -> set[tuple[str, str, str]]:
        """The network between components (every path together): what impact analysis walks."""
        return {(a.component, b.component, k) for a, outs in self.succ.items() for b, k in outs
                if a.component != b.component}

    def is_connected(self) -> bool:
        if not self.nodes:
            return True
        seen, q = {self.nodes[0]}, deque([self.nodes[0]])
        while q:
            cur = q.popleft()
            for nxt, _k in [*self.succ.get(cur, []), *self.pred.get(cur, [])]:
                if nxt not in seen:
                    seen.add(nxt)
                    q.append(nxt)
        return len(seen) == len(self.nodes)

    # ------------------------------------------------------------------ coordinates
    def positions(self, path: str, dataset: Optional[str] = None) -> dict[str, dict]:
        """`s` of each placement of a path (entry, m) and where it came from: the dataset (by placement id
        or component id), the placement itself, or computed from the lengths before it. None when unknown."""
        res = resolve(self.doc)
        ds = next((d for d in self.doc.datasets if d.id == dataset), None) if dataset else next(
            (d for d in self.doc.datasets if d.path == path and any(v.s is not None for v in d.values.values())), None)
        pls = {i: pl for p in self.doc.paths if p.id == path for i, pl in enumerate(p.placement_list())}
        out, running = {}, 0.0
        for n in self.order(path):
            pl: Placement = pls[n.index]
            v = ds.values.get(n.placement_id) or ds.values.get(n.component) if ds else None
            length = pl.length if pl.length is not None else res[n.component].length if n.component in res else None
            if v is not None and v.s is not None:
                s, how = v.s, "dataset"
            elif pl.s is not None:
                s, how = pl.s, "placement"
            elif running is not None:
                s, how = running, "computed"
            else:
                s, how = None, None
            out[n.placement_id] = {"s": s, "length": length, "from": how, "component": n.component}
            running = (s + (length or 0.0)) if s is not None and (length is not None or res.get(
                n.component, _NONE).virtual) else None
        return out


_NONE = Resolved(id="", name="", type="generic", family="generic", capabilities=[], parameters={}, length=None,
                 boundaries=[], material=None, states=None, virtual=False, known_type=False, component=None)  # type: ignore[arg-type]


def components_of(nodes: Iterable[Node]) -> list[str]:
    out, seen = [], set()
    for n in nodes:
        if n.component not in seen:
            seen.add(n.component)
            out.append(n.component)
    return out
