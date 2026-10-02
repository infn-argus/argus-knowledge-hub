/* What a directed graph of hub records is made of, shared by the asset graph and the Knowledge graph.

   Columns carry direction: what points at a node is drawn to its left, what it points at to its right.
   A node keeps the place it was given; new ones go into the nearest free space of their column, beside the
   node that brought them in. Many neighbours of one kind arrive as one group node, opened on demand. */

export const NODE_W = 184;
export const NODE_H = 44;
export const COL_GAP = 128;
export const ROW_GAP = 14;
export const STEP = NODE_H + ROW_GAP;

/** A neighbour group of at least this many is drawn as one node. */
export const GROUP_MIN = 6;

export type Kind = "asset" | "ticket" | "document" | "group" | "person" | "bundle";

export interface GNode {
  id: string;                      // `${kind}:${uid}`, or `bundle:…` for a group of neighbours
  kind: Kind;
  uid: string;
  label: string;
  sub: string | null;              // the type, or what the group is
  restricted?: boolean;
  col: number;
  y: number;
  /** The node whose opening brought this one in. */
  parent: string | null;
  seq: number;
  /** A group of neighbours, shown on demand. */
  bundle?: { members: GNode[]; edges: GEdge[] };
  /** Analysis marks: the failed node, an affected one, a symptom, a candidate cause. */
  mark?: "origin" | "affected" | "symptom" | "cause";
  /** What an affected node loses (impact). */
  loss?: string;
}

export interface GEdge {
  from: string;
  to: string;
  relation: string;
  /** What kind of connection (structure | work | documentation | people), or the failure layer. */
  via?: string;
}

export const edgeKey = (e: GEdge) => `${e.from}|${e.to}|${e.relation}`;
export const nodeId = (kind: string, uid: string) => `${kind}:${uid}`;

export const KIND_STYLE: Record<string, { fill: string; stroke: string; label: string }> = {
  asset: { fill: "#eef2ff", stroke: "#818cf8", label: "Objects" },
  ticket: { fill: "#fffbeb", stroke: "#f59e0b", label: "Tickets" },
  document: { fill: "#ecfdf5", stroke: "#10b981", label: "Documents" },
  group: { fill: "#f0f9ff", stroke: "#0ea5e9", label: "Groups" },
  person: { fill: "#f5f3ff", stroke: "#8b5cf6", label: "People" },
  bundle: { fill: "#f8fafc", stroke: "#94a3b8", label: "Groups of neighbours" },
};

/** Failure layers (services/causal_model.py), coloured for impact and root-cause paths. */
export const LAYER_STYLE: Record<string, string> = {
  control: "#6366f1",
  power: "#dc2626",
  cooling: "#0891b2",
  vacuum: "#7c3aed",
  timing: "#d97706",
  interlock: "#be123c",
  function: "#059669",
  composition: "#64748b",
  membership: "#94a3b8",
  beam: "#2563eb",
  environment: "#a16207",
};

export const LOSS_LABEL: Record<string, string> = {
  control: "loses its readout",
  function: "stops working",
  permit: "loses its permit",
};

/** Tops for `count` new boxes in a column: one block, as close as it fits to `nearY`. */
export function slots(nodes: Iterable<GNode>, col: number, nearY: number, count: number): number[] {
  if (count === 0) return [];
  const taken = [...nodes].filter((n) => n.col === col).map((n) => n.y);
  const height = count * STEP;
  const start = nearY - (height - STEP) / 2;
  const free = (top: number) => taken.every((t) => t <= top - STEP || t >= top + height);
  for (let i = 0; i < 4000; i++) {
    const offset = Math.ceil(i / 2) * STEP * (i % 2 ? 1 : -1);
    if (free(start + offset)) return Array.from({ length: count }, (_, k) => start + offset + k * STEP);
  }
  const bottom = Math.max(...taken) + STEP;
  return Array.from({ length: count }, (_, k) => bottom + k * STEP);
}

export interface Neighbour {
  node: Omit<GNode, "col" | "y" | "parent" | "seq">;
  edge: GEdge;
}

/** Neighbours placed in a column beside `from`: one node each, except that a run of at least GROUP_MIN with
 *  the same relation and type becomes one group node that opens on demand. Returns the nodes to add. */
export function place(
  existing: Map<string, GNode>,
  from: GNode,
  col: number,
  neighbours: Neighbour[],
  seq: { current: number },
  grouping = true,
): GNode[] {
  const fresh = neighbours.filter((n) => !existing.has(n.node.id));
  const groups = new Map<string, Neighbour[]>();
  for (const n of fresh) {
    const key = `${n.edge.relation}|${n.node.kind}|${n.node.sub ?? ""}`;
    groups.set(key, [...(groups.get(key) ?? []), n]);
  }
  const singles: Neighbour[] = [];
  const bundles: Neighbour[][] = [];
  for (const list of groups.values()) {
    if (grouping && list.length >= GROUP_MIN && fresh.length > GROUP_MIN) bundles.push(list);
    else singles.push(...list);
  }
  const ys = slots(existing.values(), col, from.y, singles.length + bundles.length);
  const out: GNode[] = singles.map((n, i) => ({ ...n.node, col, y: ys[i], parent: from.id, seq: seq.current++ }));
  bundles.forEach((list, i) => {
    const first = list[0];
    const id = `bundle:${from.id}:${col}:${first.edge.relation}:${first.node.kind}:${first.node.sub ?? ""}`;
    const kindLabel = first.node.sub ?? KIND_STYLE[first.node.kind]?.label ?? first.node.kind;
    out.push({
      id, kind: "bundle", uid: id, label: `${list.length} × ${kindLabel}`, sub: first.edge.relation,
      col, y: ys[singles.length + i], parent: from.id, seq: seq.current++,
      bundle: {
        members: list.map((n) => ({ ...n.node, col, y: 0, parent: from.id, seq: 0 })),
        edges: list.map((n) => n.edge),
      },
    });
  });
  return out;
}

/** A group's edge to its node: the members' edges, redrawn to the group. */
export function bundleEdges(group: GNode): GEdge[] {
  if (!group.bundle) return [];
  const e = group.bundle.edges[0];
  const memberIds = new Set(group.bundle.members.map((m) => m.id));
  return [memberIds.has(e.to) ? { from: e.from, to: group.id, relation: e.relation, via: e.via }
                              : { from: group.id, to: e.to, relation: e.relation, via: e.via }];
}

/** Opening a group: its members in its place, and their own edges. */
export function openBundle(existing: Map<string, GNode>, group: GNode, seq: { current: number }) {
  const members = (group.bundle?.members ?? []).filter((m) => !existing.has(m.id));
  const rest = new Map(existing);
  rest.delete(group.id);
  const ys = slots(rest.values(), group.col, group.y, members.length);
  return {
    nodes: members.map((m, i) => ({ ...m, y: ys[i], seq: seq.current++ })),
    edges: group.bundle?.edges ?? [],
  };
}
