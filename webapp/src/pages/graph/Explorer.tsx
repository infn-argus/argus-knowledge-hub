import { useQuery } from "@tanstack/react-query";
import { useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { assetsApi, documentsApi, graphApi, issuesApi } from "../../api/client";
import type { Graph, GraphEdge, GraphNode } from "../../api/types";

/** Colour by what a node *is*. The whole point of the picture is that a
 * camera, the work done on it and the procedure covering it are different
 * kinds of fact, so they must not look alike. */
const KIND_STYLE: Record<string, { fill: string; stroke: string; label: string }> = {
  asset: { fill: "#e0e7ff", stroke: "#4f46e5", label: "Objects" },
  ticket: { fill: "#fef3c7", stroke: "#d97706", label: "Tickets" },
  document: { fill: "#d1fae5", stroke: "#059669", label: "Documents" },
  group: { fill: "#e0f2fe", stroke: "#0284c7", label: "Groups" },
  person: { fill: "#ede9fe", stroke: "#7c3aed", label: "People" },
};

/** Edges are coloured by what sort of connection they are, not by their
 * endpoints: "this is mounted in that" and "this ticket mentioned that"
 * are both asset-to-asset-ish but mean very different things. */
const VIA_STYLE: Record<string, { stroke: string; label: string }> = {
  structure: { stroke: "#6366f1", label: "structure" },
  work: { stroke: "#f59e0b", label: "work" },
  documentation: { stroke: "#10b981", label: "documentation" },
  people: { stroke: "#0ea5e9", label: "people" },
};

const START_KINDS = [
  { kind: "asset", label: "Object" },
  { kind: "ticket", label: "Ticket" },
  { kind: "document", label: "Document" },
] as const;

const W = 1000;
const H = 680;
const CX = W / 2;
const CY = H / 2;
// Rings tighten as they go out: the outer hops hold far more nodes than
// the inner ones, and even spacing wastes the middle of the canvas. The
// outermost must still clear the canvas edge with room for its labels —
// a fourth hop drawn off-frame is a fourth hop nobody asked for.
const RING = [0, 115, 200, 258, 295];
// Screens are wider than they are tall, so the rings are ellipses.
const X_STRETCH = 1.45;

type StartKind = (typeof START_KINDS)[number]["kind"];

interface Placed extends GraphNode {
  x: number;
  y: number;
  /** Labels alternate above and below around a ring: neighbours on a
   * crowded ring otherwise write over each other. */
  labelAbove: boolean;
}

function detailPath(node: GraphNode): string | null {
  if (node.kind === "asset") return `/assets/${node.uid}`;
  if (node.kind === "ticket") return `/tickets/${node.uid}`;
  if (node.kind === "document") return `/documents/${node.uid}`;
  return null;
}

function truncate(text: string, max: number) {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

/** Concentric rings by hop count. A force layout would look livelier, but
 * distance-from-centre is the one thing the traversal actually computes,
 * and a ring says it exactly. */
function layout(graph: Graph): Placed[] {
  const byDepth = new Map<number, GraphNode[]>();
  for (const node of graph.nodes) {
    const bucket = byDepth.get(node.depth) ?? [];
    bucket.push(node);
    byDepth.set(node.depth, bucket);
  }

  const placed: Placed[] = [];
  for (const [depth, nodes] of [...byDepth.entries()].sort((a, b) => a[0] - b[0])) {
    if (depth === 0) {
      placed.push({ ...nodes[0], x: CX, y: CY, labelAbove: false });
      continue;
    }
    // Group same kinds together around the ring so the picture reads as
    // "equipment over here, work over there".
    const ordered = [...nodes].sort(
      (a, b) => a.kind.localeCompare(b.kind) || a.label.localeCompare(b.label),
    );
    const radius = RING[Math.min(depth, RING.length - 1)];
    // Offset each ring so nodes don't line up radially with the ring inside.
    const offset = depth % 2 ? -Math.PI / 2 : -Math.PI / 2 + Math.PI / ordered.length;
    ordered.forEach((node, i) => {
      const angle = offset + (2 * Math.PI * i) / ordered.length;
      placed.push({
        ...node,
        x: CX + radius * Math.cos(angle) * X_STRETCH,
        y: CY + radius * Math.sin(angle),
        labelAbove: i % 2 === 1,
      });
    });
  }
  return placed;
}

function edgeKey(edge: GraphEdge) {
  const a = `${edge.from_kind}:${edge.from_uid}`;
  const b = `${edge.to_kind}:${edge.to_uid}`;
  return [a < b ? a : b, a < b ? b : a, edge.relation].join("|");
}

function StartPicker({
  kind,
  value,
  onPick,
}: {
  kind: StartKind;
  value: GraphNode | null;
  onPick: (uid: string, label: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);

  const assets = useQuery({
    queryKey: ["assets"],
    queryFn: () => assetsApi.list(),
    enabled: kind === "asset",
  });
  const issues = useQuery({
    queryKey: ["issues"],
    queryFn: () => issuesApi.list(),
    enabled: kind === "ticket",
  });
  const documents = useQuery({
    queryKey: ["documents"],
    queryFn: () => documentsApi.list(),
    enabled: kind === "document",
  });

  const options = useMemo(() => {
    if (kind === "asset")
      return (assets.data ?? []).map((a) => ({ uid: a.uid, label: a.name, sub: a.key }));
    if (kind === "ticket")
      return (issues.data ?? []).map((i) => ({
        uid: i.uid,
        label: i.title,
        sub: (i.attributes?.argus_source_key as string) ?? "",
      }));
    return (documents.data ?? []).map((d) => ({ uid: d.uid, label: d.title, sub: d.code }));
  }, [kind, assets.data, issues.data, documents.data]);

  const loading = assets.isLoading || issues.isLoading || documents.isLoading;

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = q
      ? options.filter(
          (o) => o.label.toLowerCase().includes(q) || o.sub.toLowerCase().includes(q),
        )
      : options;
    return filtered.slice(0, 40);
  }, [options, query]);

  return (
    <div className="relative">
      <input
        value={open ? query : value ? value.label : ""}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => {
          setQuery("");
          setOpen(true);
        }}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder={loading ? "Loading…" : `Search ${kind}s…`}
        className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
      />
      {open && (
        <div className="absolute z-20 mt-1 max-h-72 w-full overflow-y-auto rounded border border-slate-200 bg-white shadow-lg">
          {matches.length === 0 && (
            <p className="px-2 py-2 text-xs text-slate-400">
              {loading ? "Loading…" : "Nothing matches"}
            </p>
          )}
          {matches.map((o) => (
            <button
              type="button"
              key={o.uid}
              onMouseDown={(e) => {
                e.preventDefault();
                onPick(o.uid, o.label);
                setOpen(false);
              }}
              className="block w-full px-2 py-1.5 text-left text-sm hover:bg-slate-50"
            >
              <span className="text-slate-800">{truncate(o.label, 48)}</span>
              {o.sub && <span className="ml-2 text-xs text-slate-400">{o.sub}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function GraphExplorer() {
  const [startKind, setStartKind] = useState<StartKind>("asset");
  const [startUid, setStartUid] = useState<string | null>(null);
  const [startLabel, setStartLabel] = useState("");
  const [depth, setDepth] = useState(2);
  const [kinds, setKinds] = useState<string[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [view, setView] = useState({ x: 0, y: 0, w: W, h: H });
  const drag = useRef<{ x: number; y: number; vx: number; vy: number } | null>(null);

  const summary = useQuery({ queryKey: ["graph-summary"], queryFn: graphApi.summary });

  const graph = useQuery({
    queryKey: ["graph", startKind, startUid, depth, kinds.join(",")],
    queryFn: () =>
      graphApi.walk({ kind: startKind, uid: startUid!, depth, kinds: kinds.length ? kinds : undefined }),
    enabled: !!startUid,
  });

  const placed = useMemo(() => (graph.data ? layout(graph.data) : []), [graph.data]);
  const byRef = useMemo(
    () => new Map(placed.map((n) => [`${n.kind}:${n.uid}`, n])),
    [placed],
  );

  const edges = useMemo(() => {
    if (!graph.data) return [];
    const seen = new Set<string>();
    return graph.data.edges.filter((e) => {
      const key = edgeKey(e);
      if (seen.has(key)) return false;
      seen.add(key);
      return byRef.has(`${e.from_kind}:${e.from_uid}`) && byRef.has(`${e.to_kind}:${e.to_uid}`);
    });
  }, [graph.data, byRef]);

  // Above this many nodes every label becomes unreadable overlap, so they
  // come off and hover/selection carries the naming instead.
  const showLabels = placed.length <= 45;

  const selectedNode = selected ? byRef.get(selected) : null;
  const selectedEdges = selectedNode
    ? edges.filter(
        (e) =>
          `${e.from_kind}:${e.from_uid}` === selected || `${e.to_kind}:${e.to_uid}` === selected,
      )
    : [];

  const recenter = (node: GraphNode) => {
    if (node.kind !== "asset" && node.kind !== "ticket" && node.kind !== "document") return;
    setStartKind(node.kind);
    setStartUid(node.uid);
    setStartLabel(node.label);
    setSelected(null);
    setView({ x: 0, y: 0, w: W, h: H });
  };

  const onWheel = (e: React.WheelEvent<SVGSVGElement>) => {
    const factor = e.deltaY > 0 ? 1.12 : 1 / 1.12;
    setView((v) => {
      const w = Math.min(W * 2.5, Math.max(W * 0.25, v.w * factor));
      const h = (w / W) * H;
      return { x: v.x + (v.w - w) / 2, y: v.y + (v.h - h) / 2, w, h };
    });
  };

  return (
    <div>
      <div className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Knowledge graph</h1>
        {summary.data && (
          <p className="text-xs text-slate-500">
            {summary.data.nodes.assets} objects · {summary.data.nodes.tickets} tickets ·{" "}
            {summary.data.nodes.documents} documents ·{" "}
            {Object.values(summary.data.edges).reduce((a, b) => a + b, 0)} connections
          </p>
        )}
      </div>
      <p className="mt-1 text-sm text-slate-500">
        Start from anything and walk outwards: what it is part of, what work touched it, what
        documents it.
      </p>

      <div className="mt-4 flex flex-wrap items-end gap-3 rounded border border-slate-200 bg-white p-3">
        <div className="w-28">
          <label className="block text-xs font-medium text-slate-500">Start from</label>
          <select
            value={startKind}
            onChange={(e) => {
              setStartKind(e.target.value as StartKind);
              setStartUid(null);
              setStartLabel("");
            }}
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
          >
            {START_KINDS.map((k) => (
              <option key={k.kind} value={k.kind}>
                {k.label}
              </option>
            ))}
          </select>
        </div>

        <div className="min-w-[18rem] flex-1">
          <label className="block text-xs font-medium text-slate-500">
            {START_KINDS.find((k) => k.kind === startKind)!.label}
          </label>
          <div className="mt-1">
            <StartPicker
              kind={startKind}
              value={startUid ? ({ label: startLabel } as GraphNode) : null}
              onPick={(uid, label) => {
                setStartUid(uid);
                setStartLabel(label);
                setSelected(null);
                setView({ x: 0, y: 0, w: W, h: H });
              }}
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-500">Hops</label>
          <div className="mt-1 flex gap-1">
            {[1, 2, 3, 4].map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => setDepth(d)}
                className={`h-8 w-8 rounded text-sm ${
                  depth === d
                    ? "bg-slate-900 text-white"
                    : "border border-slate-300 text-slate-600 hover:bg-slate-50"
                }`}
              >
                {d}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-500">Show</label>
          <div className="mt-1 flex flex-wrap gap-1">
            {Object.entries(KIND_STYLE).map(([kind, style]) => {
              const on = kinds.length === 0 || kinds.includes(kind);
              return (
                <button
                  key={kind}
                  type="button"
                  onClick={() =>
                    setKinds((current) => {
                      // An empty filter means "everything", so the first
                      // click has to turn the others off rather than this
                      // one on.
                      const base =
                        current.length === 0 ? Object.keys(KIND_STYLE) : current;
                      const next = base.includes(kind)
                        ? base.filter((k) => k !== kind)
                        : [...base, kind];
                      return next.length === Object.keys(KIND_STYLE).length ? [] : next;
                    })
                  }
                  className={`rounded-full border px-2.5 py-1 text-xs ${
                    on ? "text-slate-700" : "text-slate-300"
                  }`}
                  style={{
                    borderColor: on ? style.stroke : "#e2e8f0",
                    background: on ? style.fill : "#fff",
                  }}
                >
                  {style.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {graph.data?.truncated && (
        <p className="mt-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          Too much to draw at this distance — this is a subset. Reduce the hops or filter to
          fewer kinds to see a complete answer.
        </p>
      )}

      <div className="mt-3 flex gap-4">
        <div className="min-w-0 flex-1 rounded border border-slate-200 bg-white">
          <div className="flex items-center justify-between border-b border-slate-100 px-3 py-1.5">
            <div className="flex flex-wrap gap-3 text-[11px] text-slate-500">
              {Object.entries(VIA_STYLE).map(([via, style]) => (
                <span key={via} className="inline-flex items-center gap-1">
                  <span className="inline-block h-0.5 w-4" style={{ background: style.stroke }} />
                  {style.label}
                </span>
              ))}
            </div>
            <button
              type="button"
              onClick={() => setView({ x: 0, y: 0, w: W, h: H })}
              className="text-xs text-slate-500 hover:text-slate-900"
            >
              Reset view
            </button>
          </div>

          {!startUid ? (
            <p className="py-24 text-center text-sm text-slate-400">
              Pick something above to see what it connects to.
            </p>
          ) : graph.isLoading ? (
            <p className="py-24 text-center text-sm text-slate-400">Walking…</p>
          ) : graph.isError ? (
            <p className="py-24 text-center text-sm text-slate-400">
              Nothing found for that node in this workspace.
            </p>
          ) : placed.length <= 1 ? (
            <p className="py-24 text-center text-sm text-slate-400">
              Nothing is linked to this yet.
            </p>
          ) : (
            <svg
              viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`}
              className="w-full cursor-grab active:cursor-grabbing"
              // Keep the whole picture and the controls on one screen; a
              // graph you have to scroll to see is a graph you can't read.
              style={{ touchAction: "none", maxHeight: "68vh" }}
              onWheel={onWheel}
              onPointerDown={(e) => {
                drag.current = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y };
                e.currentTarget.setPointerCapture(e.pointerId);
              }}
              onPointerMove={(e) => {
                const d = drag.current;
                if (!d) return;
                const rect = e.currentTarget.getBoundingClientRect();
                const scale = view.w / rect.width;
                setView((v) => ({
                  ...v,
                  x: d.vx - (e.clientX - d.x) * scale,
                  y: d.vy - (e.clientY - d.y) * scale,
                }));
              }}
              onPointerUp={() => {
                drag.current = null;
              }}
            >
              {edges.map((e, i) => {
                const a = byRef.get(`${e.from_kind}:${e.from_uid}`)!;
                const b = byRef.get(`${e.to_kind}:${e.to_uid}`)!;
                const touched =
                  !selected ||
                  `${e.from_kind}:${e.from_uid}` === selected ||
                  `${e.to_kind}:${e.to_uid}` === selected;
                return (
                  <line
                    key={`${edgeKey(e)}-${i}`}
                    x1={a.x}
                    y1={a.y}
                    x2={b.x}
                    y2={b.y}
                    stroke={VIA_STYLE[e.via]?.stroke ?? "#94a3b8"}
                    strokeWidth={touched ? 1.4 : 1}
                    strokeOpacity={touched ? 0.55 : 0.12}
                  />
                );
              })}

              {placed.map((node) => {
                const ref = `${node.kind}:${node.uid}`;
                const style = KIND_STYLE[node.kind] ?? KIND_STYLE.asset;
                const isRoot = node.depth === 0;
                const isSelected = selected === ref;
                const r = isRoot ? 15 : 8;
                return (
                  <g
                    key={ref}
                    className="cursor-pointer"
                    onPointerDown={(e) => e.stopPropagation()}
                    onClick={() => setSelected(isSelected ? null : ref)}
                    onDoubleClick={() => recenter(node)}
                  >
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r={r}
                      fill={isRoot ? "#0f172a" : style.fill}
                      stroke={isSelected ? "#0f172a" : style.stroke}
                      strokeWidth={isSelected ? 3 : 1.6}
                    />
                    {(showLabels || isRoot || isSelected) && (
                      <text
                        x={node.x}
                        y={node.labelAbove ? node.y - r - 6 : node.y + r + 12}
                        textAnchor="middle"
                        style={{ fontSize: isRoot ? 13 : 11, fill: "#334155" }}
                      >
                        {truncate(node.label, isRoot ? 38 : 24)}
                      </text>
                    )}
                  </g>
                );
              })}
            </svg>
          )}
        </div>

        <aside className="w-72 shrink-0">
          {selectedNode ? (
            <div className="rounded border border-slate-200 bg-white p-3">
              <span
                className="inline-block rounded-full px-2 py-0.5 text-[10px] uppercase tracking-wide"
                style={{
                  background: KIND_STYLE[selectedNode.kind]?.fill,
                  color: KIND_STYLE[selectedNode.kind]?.stroke,
                }}
              >
                {selectedNode.type_name ?? selectedNode.kind}
              </span>
              <h2 className="mt-2 text-sm font-semibold text-slate-900">{selectedNode.label}</h2>
              {selectedNode.sublabel && (
                <p className="text-xs text-slate-500">{selectedNode.sublabel}</p>
              )}
              <p className="mt-1 text-xs text-slate-400">
                {selectedNode.depth === 0
                  ? "starting point"
                  : `${selectedNode.depth} hop${selectedNode.depth > 1 ? "s" : ""} away`}
                {selectedNode.state ? ` · ${selectedNode.state}` : ""}
              </p>

              <div className="mt-3 flex gap-2">
                {detailPath(selectedNode) && (
                  <Link
                    to={detailPath(selectedNode)!}
                    className="rounded bg-slate-900 px-2 py-1 text-xs text-white"
                  >
                    Open
                  </Link>
                )}
                {selectedNode.depth > 0 && detailPath(selectedNode) && (
                  <button
                    type="button"
                    onClick={() => recenter(selectedNode)}
                    className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
                  >
                    Walk from here
                  </button>
                )}
              </div>

              <ul className="mt-3 space-y-1 border-t border-slate-100 pt-2">
                {selectedEdges.map((e, i) => {
                  const otherRef =
                    `${e.from_kind}:${e.from_uid}` === selected
                      ? `${e.to_kind}:${e.to_uid}`
                      : `${e.from_kind}:${e.from_uid}`;
                  const other = byRef.get(otherRef);
                  if (!other) return null;
                  return (
                    <li key={`${edgeKey(e)}-${i}`} className="text-xs">
                      <span className="text-slate-400">{e.relation}</span>{" "}
                      <button
                        type="button"
                        onClick={() => setSelected(otherRef)}
                        className="text-slate-700 hover:underline"
                      >
                        {truncate(other.label, 30)}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : (
            <div className="rounded border border-dashed border-slate-200 p-3 text-xs text-slate-500">
              <p>Click a node to see what it is and where it goes. Double-click to walk from it.</p>
              <p className="mt-2">Drag to pan, scroll to zoom.</p>
              {graph.data && (
                <p className="mt-3 text-slate-400">
                  {graph.data.nodes.length} nodes · {edges.length} connections
                </p>
              )}
            </div>
          )}

          {summary.data && (
            <div className="mt-3 rounded border border-slate-200 bg-white p-3">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                This workspace
              </p>
              <ul className="mt-1 space-y-0.5 text-xs text-slate-600">
                {Object.entries(summary.data.edges).map(([name, count]) => (
                  <li key={name} className="flex justify-between">
                    <span>{name.replace(/_/g, " ")}</span>
                    <span className="tabular-nums text-slate-900">{count}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
