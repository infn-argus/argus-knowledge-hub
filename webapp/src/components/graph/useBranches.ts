import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { graphApi } from "../../api/client";
import type { Graph, GraphNode } from "../../api/types";
import { bundleEdges, edgeKey, nodeId, openBundle, place, type GEdge, type GNode, type Kind, type Neighbour } from "./model";

const asNode = (n: GraphNode): Neighbour["node"] => ({
  id: nodeId(n.kind, n.uid), kind: n.kind as Kind, uid: n.uid, label: n.label,
  sub: n.type_name ?? n.sublabel ?? null, restricted: !!n.restricted,
});

/** A graph that grows from one record as the person opens nodes: each opening fetches that node's
 *  neighbours (one hop) and places what points at it to its left, what it points at to its right. */
export function useBranches(start: { kind: string; uid: string } | null, kinds?: string[]) {
  const queryClient = useQueryClient();
  const [nodes, setNodes] = useState<Map<string, GNode>>(new Map());
  const [edges, setEdges] = useState<Map<string, GEdge>>(new Map());
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const seq = useRef(0);
  const nodesRef = useRef(nodes);
  nodesRef.current = nodes;
  const kindsKey = (kinds ?? []).join(",");

  const fetchBranch = useCallback(
    (kind: string, uid: string) =>
      queryClient.fetchQuery<Graph>({
        queryKey: ["graph-branch", kind, uid, kindsKey],
        queryFn: () => graphApi.walk({ kind, uid, depth: 1, kinds: kindsKey ? kindsKey.split(",") : undefined, maxNodes: 400 }),
        staleTime: 60_000,
      }),
    [queryClient, kindsKey],
  );

  const addEdges = (list: GEdge[]) =>
    setEdges((prev) => {
      const next = new Map(prev);
      for (const e of list) next.set(edgeKey(e), e);
      return next;
    });

  const expand = useCallback(async (id: string) => {
    const at = nodesRef.current.get(id);
    if (!at || at.bundle || at.restricted || !["asset", "ticket", "document", "group", "person"].includes(at.kind)) return;
    setLoading((s) => new Set(s).add(id));
    setError(null);
    try {
      const graph = await fetchBranch(at.kind, at.uid);
      const byId = new Map(graph.nodes.map((n) => [nodeId(n.kind, n.uid), n]));
      const sides: Record<"in" | "out", Neighbour[]> = { in: [], out: [] };
      const seen = new Set<string>();
      const own: GEdge[] = [];
      for (const e of graph.edges) {
        const from = nodeId(e.from_kind, e.from_uid);
        const to = nodeId(e.to_kind, e.to_uid);
        if (from !== id && to !== id) continue;
        const edge = { from, to, relation: e.relation, via: e.via };
        own.push(edge);
        const side = to === id ? "in" : "out";
        const other = side === "in" ? from : to;
        const n = byId.get(other);
        if (!n || other === id || seen.has(`${side}:${other}`)) continue;
        seen.add(`${side}:${other}`);
        sides[side].push({ node: asNode(n), edge });
      }
      // Placed from what is drawn now, so the groups' edges below are known before React renders.
      const next = new Map(nodesRef.current);
      let added: GNode[] = [];
      for (const side of ["in", "out"] as const) {
        const placed = place(next, at, at.col + (side === "in" ? -1 : 1), sides[side], seq);
        for (const n of placed) next.set(n.id, n);
        added = added.concat(placed);
      }
      nodesRef.current = next;
      setNodes(next);
      // The node's own edges to what is drawn, and a group's one edge in place of its members'.
      const grouped = new Set(added.flatMap((n) => n.bundle?.members.map((m) => m.id) ?? []));
      addEdges([...own.filter((e) => !grouped.has(e.from) && !grouped.has(e.to)), ...added.flatMap(bundleEdges)]);
      setOpen((s) => new Set(s).add(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading((s) => {
        const next = new Set(s);
        next.delete(id);
        return next;
      });
    }
  }, [fetchBranch]);

  /** Fold a node's branches: everything its opening brought in, and theirs in turn. */
  const collapse = useCallback((id: string) => {
    const current = nodesRef.current;
    const gone = new Set<string>();
    const walk = (p: string) => {
      for (const n of current.values()) {
        if (n.parent === p && !gone.has(n.id)) {
          gone.add(n.id);
          walk(n.id);
        }
      }
    };
    walk(id);
    const kept = new Map([...current].filter(([k]) => !gone.has(k)));
    nodesRef.current = kept;
    setNodes(kept);
    setOpen((prev) => {
      const stillOpen = new Set([...prev].filter((k) => k !== id && !gone.has(k)));
      setEdges((edgesNow) => new Map([...edgesNow].filter(([, e]) => {
        if (gone.has(e.from) || gone.has(e.to)) return false;
        const other = e.from === id ? e.to : e.to === id ? e.from : null;
        return other === null || stillOpen.has(other);
      })));
      return stillOpen;
    });
  }, []);

  const reveal = useCallback((group: GNode) => {
    const { nodes: members, edges: memberEdges } = openBundle(nodesRef.current, group, seq);
    const next = new Map(nodesRef.current);
    next.delete(group.id);
    for (const m of members) next.set(m.id, m);
    nodesRef.current = next;
    setNodes(next);
    setEdges((prev) => {
      const next = new Map([...prev].filter(([, e]) => e.from !== group.id && e.to !== group.id));
      for (const e of memberEdges) next.set(edgeKey(e), e);
      return next;
    });
  }, []);

  /** Double-click: a group shows its members; a node opens its branches, or folds them. */
  const toggle = useCallback((n: GNode) => {
    if (n.bundle) return reveal(n);
    if (loading.has(n.id)) return;
    if (open.has(n.id)) collapse(n.id);
    else void expand(n.id);
  }, [reveal, collapse, expand, loading, open]);

  // Start (or restart) from one record.
  useEffect(() => {
    if (!start) {
      setNodes(new Map());
      setEdges(new Map());
      setOpen(new Set());
      return;
    }
    let cancelled = false;
    seq.current = 0;
    setEdges(new Map());
    setOpen(new Set());
    setError(null);
    fetchBranch(start.kind, start.uid)
      .then((graph) => {
        if (cancelled) return;
        const me = graph.nodes.find((n) => n.uid === start.uid && n.kind === start.kind);
        const rootNode: GNode = me
          ? { ...asNode(me), col: 0, y: 0, parent: null, seq: seq.current++ }
          : { id: nodeId(start.kind, start.uid), kind: start.kind as Kind, uid: start.uid, label: start.uid, sub: null,
              col: 0, y: 0, parent: null, seq: seq.current++ };
        const first = new Map([[rootNode.id, rootNode]]);
        nodesRef.current = first;
        setNodes(first);
        void expand(rootNode.id);
      })
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [start?.kind, start?.uid, kindsKey]);

  return {
    nodes, edges: [...edges.values()], open, loading, error, toggle, expand, collapse, reveal,
    rootId: start ? nodeId(start.kind, start.uid) : null,
  };
}
