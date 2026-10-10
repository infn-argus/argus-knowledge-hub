import { useEffect, useMemo, useRef, useState } from "react";
import {
  COL_GAP, edgeKey, KIND_STYLE, LAYER_STYLE, NODE_H, NODE_W,
  type GEdge, type GNode,
} from "./model";

export const IN = "#d97706"; // amber: points at the selected node
export const OUT = "#4f46e5"; // indigo: the selected node points at it
export const SEMANTIC = "#0d9488"; // teal, dashed: about the same thing, by meaning
const OTHER = "#cbd5e1";

/** Draws a directed graph of hub records at a readable scale, over a camera the person pans and zooms.
 *  Edges are coloured by direction relative to the selected node ("direction"), or by failure layer
 *  ("layer", for impact and root-cause paths). */
export function GraphCanvas({
  nodes,
  edges,
  rootId,
  selected,
  onSelect,
  onOpen,
  open,
  loading,
  colouring = "direction",
  height = "100%",
  expandable = true,
  fitKey,
}: {
  nodes: Map<string, GNode>;
  edges: GEdge[];
  rootId: string | null;
  selected: string | null;
  onSelect: (id: string) => void;
  /** Double-click: open or fold a node's branches, or open a group. */
  onOpen?: (node: GNode) => void;
  /** Nodes whose branches are open (drawn with −) and being fetched (…). */
  open?: Set<string>;
  loading?: Set<string>;
  colouring?: "direction" | "layer";
  height?: string;
  /** Whether double-clicking a node opens its branches (Explore), or only opens groups (analyses). */
  expandable?: boolean;
  /** When this changes, the whole graph is fitted into view (a small analysis result). */
  fitKey?: string | number;
}) {
  const svg = useRef<SVGSVGElement>(null);
  const [size, setSize] = useState({ w: 900, h: 600 });
  const root = rootId ? nodes.get(rootId) : undefined;
  const [cam, setCam] = useState({ x: NODE_W / 2, y: NODE_H / 2, k: 1 });
  const drag = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    const el = svg.current;
    if (!el) return;
    const measure = () => setSize({ w: el.clientWidth || 900, h: el.clientHeight || 600 });
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    const onWheel = (ev: WheelEvent) => {
      ev.preventDefault();
      setCam((c) => ({ ...c, k: Math.min(2.5, Math.max(0.15, c.k * (ev.deltaY < 0 ? 1.1 : 0.9))) }));
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => {
      ro.disconnect();
      el.removeEventListener("wheel", onWheel);
    };
  }, []);

  // A new starting point: the camera goes back to it.
  useEffect(() => {
    if (root) setCam({ x: root.col * (NODE_W + COL_GAP) + NODE_W / 2, y: root.y + NODE_H / 2, k: 1 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rootId]);

  const pos = (n: GNode) => ({ x: n.col * (NODE_W + COL_GAP), y: n.y });
  const bounds = useMemo(() => {
    const all = [...nodes.values()].map(pos);
    if (!all.length) return { minX: 0, minY: 0, maxX: NODE_W, maxY: NODE_H };
    return {
      minX: Math.min(...all.map((p) => p.x)), minY: Math.min(...all.map((p) => p.y)),
      maxX: Math.max(...all.map((p) => p.x + NODE_W)), maxY: Math.max(...all.map((p) => p.y + NODE_H)),
    };
  }, [nodes]);
  const fit = () => {
    const w = bounds.maxX - bounds.minX + 80;
    const h = bounds.maxY - bounds.minY + 80;
    setCam({ x: (bounds.minX + bounds.maxX) / 2, y: (bounds.minY + bounds.maxY) / 2,
             k: Math.max(0.15, Math.min(1.5, size.w / w, size.h / h)) });
  };

  useEffect(() => {
    if (fitKey !== undefined && nodes.size) fit();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fitKey, nodes.size, size.w]);

  const drawn = edges.filter((e) => nodes.has(e.from) && nodes.has(e.to));
  const degree = useMemo(() => {
    const out = new Map<string, number>();
    const inn = new Map<string, number>();
    for (const e of drawn) {
      out.set(e.from, (out.get(e.from) ?? 0) + 1);
      inn.set(e.to, (inn.get(e.to) ?? 0) + 1);
    }
    return { out, inn };
  }, [drawn]);
  const cols = [...new Set([...nodes.values()].map((n) => n.col))];
  const vw = size.w / cam.k;
  const vh = size.h / cam.k;

  return (
    <div className="relative h-full w-full" style={{ height }}>
      <svg
        ref={svg}
        className="h-full w-full cursor-grab select-none bg-slate-50 active:cursor-grabbing"
        viewBox={`${cam.x - vw / 2} ${cam.y - vh / 2} ${vw} ${vh}`}
        onMouseDown={(e) => (drag.current = { x: e.clientX, y: e.clientY })}
        onMouseMove={(e) => {
          if (!drag.current) return;
          const dx = (e.clientX - drag.current.x) / cam.k;
          const dy = (e.clientY - drag.current.y) / cam.k;
          drag.current = { x: e.clientX, y: e.clientY };
          setCam((c) => ({ ...c, x: c.x - dx, y: c.y - dy }));
        }}
        onMouseUp={() => (drag.current = null)}
        onMouseLeave={() => (drag.current = null)}
      >
        <defs>
          {[["in", IN], ["out", OUT], ["other", "#94a3b8"], ...Object.entries(LAYER_STYLE)].map(([id, color]) => (
            <marker key={id} id={`arrow-${id}`} viewBox="0 0 10 10" refX="10" refY="5" markerWidth="7" markerHeight="7"
                    orient="auto-start-reverse">
              <path d="M0,0 L10,5 L0,10 z" fill={color} />
            </marker>
          ))}
        </defs>

        {colouring === "direction" && cols.map((col) => (
          <text key={`h${col}`} x={col * (NODE_W + COL_GAP) + NODE_W / 2} y={bounds.minY - 16} textAnchor="middle"
                fontSize={11} className="fill-slate-400">
            {col < 0 ? `← inbound${col < -1 ? ` (${-col} hops)` : ""}` : col > 0 ? `outbound${col > 1 ? ` (${col} hops)` : ""} →` : ""}
          </text>
        ))}

        {drawn.map((e) => {
          const a = nodes.get(e.from)!;
          const b = nodes.get(e.to)!;
          let kind = "other";
          let color = OTHER;
          if (colouring === "layer") {
            kind = e.via && LAYER_STYLE[e.via] ? e.via : "other";
            color = LAYER_STYLE[e.via ?? ""] ?? "#94a3b8";
          } else if (e.to === selected) {
            kind = "in"; color = IN;
          } else if (e.from === selected) {
            kind = "out"; color = OUT;
          }
          const fanOut = degree.out.get(e.from) ?? 1;
          const fanIn = degree.inn.get(e.to) ?? 1;
          const { d, mx, my } = curve(pos(a), pos(b), fanIn > fanOut ? 0.3 : fanOut > fanIn ? 0.7 : 0.5);
          const quiet = colouring === "direction" && kind === "other";
          // About the same thing, by meaning: no direction, and drawn apart from the relations people made.
          const semantic = e.via === "semantic";
          return (
            <g key={edgeKey(e)}>
              <path d={d} fill="none" stroke={semantic ? SEMANTIC : color} strokeWidth={semantic ? 1.6 : quiet ? 1.2 : 2}
                    strokeDasharray={semantic ? "6 4" : undefined} markerEnd={semantic ? undefined : `url(#arrow-${kind})`} />
              <text x={mx} y={my - 4} textAnchor="middle" fontSize={10} className={quiet ? "fill-slate-400" : "fill-slate-700"}
                    stroke="#f8fafc" strokeWidth={3} paintOrder="stroke">
                {e.relation}
              </text>
            </g>
          );
        })}

        {[...nodes.values()].map((n) => {
          const p = pos(n);
          const isRoot = n.id === rootId;
          const isSel = n.id === selected;
          const style = KIND_STYLE[n.kind] ?? KIND_STYLE.asset;
          const markFill = n.mark === "origin" || n.mark === "cause" ? "#7f1d1d" : n.mark === "symptom" ? "#fef2f2" : undefined;
          const markStroke = n.mark === "affected" ? "#f87171" : n.mark === "symptom" ? "#dc2626" : undefined;
          const dark = isRoot && !n.mark || n.mark === "origin" || n.mark === "cause";
          const isOpen = open?.has(n.id);
          return (
            <g key={n.id} transform={`translate(${p.x} ${p.y})`} className="cursor-pointer"
               onMouseDown={(ev) => ev.stopPropagation()}
               onClick={() => onSelect(n.id)}
               onDoubleClick={() => onOpen?.(n)}>
              <title>
                {n.bundle ? `${n.label} (${n.sub}) — double-click to show them`
                  : `${n.label}${n.sub ? ` (${n.sub})` : ""}${onOpen && expandable ? `\nDouble-click to ${isOpen ? "fold" : "open"} its branches` : ""}`}
              </title>
              <rect width={NODE_W} height={NODE_H} rx={8}
                    fill={markFill ?? (dark ? "#0f172a" : style.fill)}
                    stroke={isSel ? "#0ea5e9" : markStroke ?? (dark ? "#0f172a" : style.stroke)}
                    strokeWidth={isSel ? 3 : n.mark ? 1.8 : 1.2}
                    strokeDasharray={n.bundle ? "4 3" : undefined} />
              <text x={10} y={18} fontSize={11} fontWeight={600} className={dark ? "fill-white" : "fill-slate-900"}>
                {n.restricted ? "Restricted" : clip(n.label, 25)}
              </text>
              <text x={10} y={33} fontSize={9.5} className={dark ? "fill-slate-300" : "fill-slate-500"}>
                {clip(n.loss ? `${n.sub ?? ""} · ${n.loss}` : n.sub ?? "", 31)}
              </text>
              {onOpen && expandable && !n.restricted && !n.bundle && (
                <text x={NODE_W - 10} y={18} fontSize={12} textAnchor="end" className={dark ? "fill-slate-300" : "fill-slate-400"}>
                  {loading?.has(n.id) ? "…" : isOpen ? "−" : "+"}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      <button type="button" onClick={fit}
              className="absolute right-2 top-2 rounded border border-slate-200 bg-white px-2 py-0.5 text-xs text-slate-600 shadow-sm hover:bg-slate-50">
        Fit
      </button>
    </div>
  );
}

/** From the side of one box that faces the other to the facing side of the other, the label at `t` along the
 *  curve; an edge across several columns has its label in the last gap before its target. */
function curve(a: { x: number; y: number }, b: { x: number; y: number }, t: number) {
  const ay = a.y + NODE_H / 2;
  const by = b.y + NODE_H / 2;
  if (Math.abs(a.x - b.x) < 1) {
    const x = a.x + NODE_W;
    const bulge = 60 + Math.abs(ay - by) / 6;
    return { d: `M${x},${ay} C${x + bulge},${ay} ${x + bulge},${by} ${x},${by}`, mx: x + bulge * 0.75, my: (ay + by) / 2 };
  }
  const forward = a.x < b.x;
  const x1 = forward ? a.x + NODE_W : a.x;
  const x2 = forward ? b.x : b.x + NODE_W;
  const c = (x2 - x1) / 2;
  const p0 = [x1, ay], p1 = [x1 + c, ay], p2 = [x2 - c, by], p3 = [x2, by];
  const at = (u: number) => [0, 1].map((i) =>
    (1 - u) ** 3 * p0[i] + 3 * (1 - u) ** 2 * u * p1[i] + 3 * (1 - u) * u ** 2 * p2[i] + u ** 3 * p3[i]);
  const long = Math.abs(x2 - x1) > COL_GAP + 1;
  const [mx, my] = long ? [forward ? x2 - COL_GAP / 2 : x2 + COL_GAP / 2, at(0.9)[1]] : at(t);
  return { d: `M${p0.join(",")} C${p1.join(",")} ${p2.join(",")} ${p3.join(",")}`, mx, my };
}

function clip(s: string, n: number) {
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}
