"""Questions answered from a canonical document alone: the limiting aperture between two components, what
moves with a support, which fiducials define a component's alignment.

Apertures belong to whatever produces them — a magnet bore, a chamber, a bellows, a valve's bore, a
collimator jaw, an optical iris — and are compared through one shape-independent measure: the free
half-aperture along +x/−x and +y/−y from the beam axis, and the inscribed radius.
"""
from __future__ import annotations

import math
from typing import Optional

from app.beam_model_core.network import Network, resolve
from app.beam_model_core.schema import Boundary, Document, Profile


# --------------------------------------------------------------------------- apertures

def _polygon(p: Profile) -> list[tuple[float, float]]:
    """The profile as a polygon around (0, 0) before its offset."""
    if p.shape in ("polygon", "custom") and p.points:
        return [(float(x), float(y)) for x, y in p.points]
    if p.shape == "circle":
        a = b = p.radius
    elif p.shape == "ellipse":
        a, b = p.semi_axis_x, p.semi_axis_y
    elif p.shape == "rectangle":
        w, h = p.half_width_x, p.half_height_y
        return [(w, h), (-w, h), (-w, -h), (w, -h)]
    elif p.shape == "racetrack":
        w, h = p.half_width_x, p.half_height_y
        r = min(p.corner_radius or 0.0, w, h)
        pts = []
        for cx, cy, a0 in ((w - r, h - r, 0), (-(w - r), h - r, 90), (-(w - r), -(h - r), 180), (w - r, -(h - r), 270)):
            for k in range(9):
                t = math.radians(a0 + k * 90 / 8)
                pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
        return pts
    else:
        raise ValueError(f"no geometry for a {p.shape} profile without points")
    return [(a * math.cos(2 * math.pi * k / 64), b * math.sin(2 * math.pi * k / 64)) for k in range(64)]


def _ray(poly: list[tuple[float, float]], dx: float, dy: float) -> float:
    """Distance from the origin along (dx, dy) to the polygon's edge (inf when the ray misses: origin outside)."""
    best = math.inf
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        ex, ey = x2 - x1, y2 - y1
        den = dx * ey - dy * ex
        if abs(den) < 1e-15:
            continue
        t = (x1 * ey - y1 * ex) / den
        u = (x1 * dy - y1 * dx) / den
        if t >= 0 and -1e-12 <= u <= 1 + 1e-12:
            best = min(best, t)
    return best


def _seg_dist(x1, y1, x2, y2) -> float:
    ex, ey = x2 - x1, y2 - y1
    L2 = ex * ex + ey * ey
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, -(x1 * ex + y1 * ey) / L2))
    return math.hypot(x1 + t * ex, y1 + t * ey)


def half_apertures(p: Profile) -> dict[str, float]:
    """Free half-apertures from the beam axis: `x` = min(+x, −x), `y` = min(+y, −y), and `radius`, the largest
    circle around the axis that fits. Exact for centred circles, ellipses, rectangles and racetracks."""
    ox, oy = p.offset_x or 0.0, p.offset_y or 0.0
    if not ox and not oy:
        if p.shape == "circle":
            return {"x": p.radius, "y": p.radius, "radius": p.radius}
        if p.shape == "ellipse":
            return {"x": p.semi_axis_x, "y": p.semi_axis_y, "radius": min(p.semi_axis_x, p.semi_axis_y)}
        if p.shape in ("rectangle", "racetrack"):
            r = min(p.half_width_x, p.half_height_y)
            return {"x": p.half_width_x, "y": p.half_height_y, "radius": r}
    poly = [(x + ox, y + oy) for x, y in _polygon(p)]
    hx = min(_ray(poly, 1, 0), _ray(poly, -1, 0))
    hy = min(_ray(poly, 0, 1), _ray(poly, 0, -1))
    inside = math.isfinite(hx) and math.isfinite(hy)
    r = min(_seg_dist(x1, y1, x2, y2) for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1])) if inside else 0.0
    return {"x": hx if inside else 0.0, "y": hy if inside else 0.0, "radius": r}


def limiting_aperture(doc: Document, path: str, start: Optional[str] = None, end: Optional[str] = None,
                      dataset: Optional[str] = None, states: Optional[dict[str, str]] = None) -> dict:
    """The tightest restriction between two components of a path (both included), in beam direction (round a
    closed path when `end` comes before `start`). Every boundary counts, whatever produces it: those of the
    placed components (in their assumed state — `states` overrides the model's default state), and boundaries
    given along the path or in a dataset where `s` places them in the range.

    Returns the limit in x, in y and as an inscribed radius, each with the boundary and the component that
    produces it, plus every boundary considered and any that could not be placed."""
    net = Network.of(doc)
    res = resolve(doc)
    row = net.order(path)
    if not row:
        raise ValueError(f"no path {path}")

    def index(ref: Optional[str], default: int) -> int:
        if ref is None:
            return default
        hits = [n.index for n in row if n.component == ref or n.placement_id == ref]
        if not hits:
            raise ValueError(f"{ref} is not on {path}")
        return hits[0]

    i, j = index(start, 0), index(end, len(row) - 1)
    closed = next((p.topology == "closed" for p in doc.paths if p.id == path), False)
    if i <= j:
        nodes = row[i:j + 1]
    elif closed:
        nodes = row[i:] + row[:j + 1]
    else:
        raise ValueError(f"{end} is upstream of {start} on the open path {path}")
    pos = net.positions(path, dataset)
    ds = next((d for d in doc.datasets if d.id == dataset), None) if dataset else None
    states = states or {}

    def assumed(comp: str) -> Optional[str]:
        r = res.get(comp)
        return states.get(comp) or (r.states.default if r and r.states else None)

    considered, unplaced = [], []

    def consider(b: Boundary, owner: str, where: dict) -> None:
        if b.when_state is not None and b.when_state != assumed(b.component or owner):
            return
        h = half_apertures(b.profile)
        source = b.component or owner
        r = res.get(source)
        considered.append({"component": source, "type": r.type if r else None, "family": r.family if r else None,
                           "boundary": b.id, "shape": b.profile.shape, "half_aperture": h,
                           "state": assumed(source), **where})

    in_range = set()
    for n in nodes:
        in_range.add(n.component)
        p = pos.get(n.placement_id) or {}
        for b in res[n.component].boundaries if n.component in res else []:
            s0 = (p.get("s") + (b.s_start or 0.0)) if p.get("s") is not None else None
            s1 = (p.get("s") + (b.s_end if b.s_end is not None else (p.get("length") or 0.0))) \
                if p.get("s") is not None else None
            consider(b, n.component, {"placement": n.placement_id, "s_start": s0, "s_end": s1})
    s_lo = (pos.get(nodes[0].placement_id) or {}).get("s")
    last = pos.get(nodes[-1].placement_id) or {}
    s_hi = (last.get("s") + (last.get("length") or 0.0)) if last.get("s") is not None else None
    along = [b for b in doc.boundaries if b.path == path] + [b for b in (ds.boundaries if ds else []) if b.path == path]
    along += [b for b in (ds.boundaries if ds else []) if b.path is None and b.component in in_range]
    for b in along:
        if b.path is None:
            consider(b, b.component, {"from_dataset": dataset})
            continue
        if b.s_start is None or s_lo is None or s_hi is None:
            unplaced.append({"boundary": b.id, "component": b.component, "reason": "no s to place it"})
            continue
        wraps = closed and i > j
        lo, hi = b.s_start, (b.s_end if b.s_end is not None else b.s_start)
        hit = (hi >= s_lo or lo <= s_hi) if wraps else (hi >= s_lo and lo <= s_hi)
        if hit:
            consider(b, b.component, {"s_start": lo, "s_end": hi})
    out = {"path": path, "from": nodes[0].component, "to": nodes[-1].component,
           "components": [n.component for n in nodes], "considered": considered, "unplaced": unplaced}
    for key in ("x", "y", "radius"):
        best = min(considered, key=lambda c: c["half_aperture"][key], default=None)
        out[f"limit_{key}"] = None if best is None else {"value": best["half_aperture"][key], **{
            k: best[k] for k in ("component", "type", "family", "boundary", "shape", "state") if best.get(k)},
            **({"s_start": best["s_start"]} if best.get("s_start") is not None else {})}
    return out


# --------------------------------------------------------------------------- alignment and supports

def support_chain(doc: Document, component: str) -> list[str]:
    """What a component is mounted on, and what that is mounted on, nearest first."""
    by_id = {c.id: c for c in doc.components}
    out, cur = [], by_id.get(component)
    while cur is not None and cur.mounted_on and cur.mounted_on not in out:
        out.append(cur.mounted_on)
        cur = by_id.get(cur.mounted_on)
    return out


def moves_with(doc: Document, support: str) -> list[str]:
    """Every component that moves when `support` moves: mounted on it, directly or through other supports."""
    children: dict[str, list[str]] = {}
    for c in doc.components:
        if c.mounted_on:
            children.setdefault(c.mounted_on, []).append(c.id)
    out, stack = [], list(children.get(support, []))
    while stack:
        c = stack.pop(0)
        if c in out:
            continue
        out.append(c)
        stack.extend(children.get(c, []))
    return out


def fiducials_of(doc: Document, component: str) -> dict[str, list[str]]:
    """The fiducials that define a component's alignment: its own, else those of the supports it is mounted
    on (the girder's fiducials define where every magnet on it is), with where each came from."""
    by_id = {c.id: c for c in doc.components}
    res = resolve(doc)
    own = list((by_id[component].fiducials if component in by_id else []) or [])
    via: dict[str, list[str]] = {}
    for s in support_chain(doc, component):
        fids = list(by_id[s].fiducials) if s in by_id else []
        fids += [c.id for c in doc.components if c.mounted_on == s and "survey_reference" in res[c.id].capabilities]
        if fids:
            via[s] = sorted(set(fids))
    return {"own": own, "via_supports": via}
