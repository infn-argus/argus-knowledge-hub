import { useEffect, useMemo, useRef, useState } from "react";
import type { BeamNode, BeamPathGraph } from "../../api/types";

/** The beam path drawn to scale: in the hall (the survey — each element from its entry point along its heading,
 *  dipoles as the arcs they bend) and unrolled along `s`, with each kind of element its own glyph and the
 *  optics under the line. Lengths and gaps are metres on one scale; only elements with no length (a BPM, a
 *  thin corrector) get a minimum size so they can be seen and clicked. */

export interface KindStyle { label: string; colour: string; glyph: "sector" | "box" | "bar" | "square" | "diamond" | "triangle" | "circle" | "pill" }

export const KIND_STYLE: Record<string, KindStyle> = {
  bpm: { label: "BPM", colour: "#a3e3a0", glyph: "diamond" },
  kicker: { label: "fast kicker", colour: "#d4d4d4", glyph: "square" },
  septum: { label: "septum", colour: "#9b7fd4", glyph: "square" },
  corrector: { label: "corrector", colour: "#d8392f", glyph: "square" },
  dipole: { label: "dipole", colour: "#6b9a5c", glyph: "sector" },
  quadrupole: { label: "quadrupole", colour: "#ecc93b", glyph: "box" },
  sextupole: { label: "sextupole", colour: "#c8379a", glyph: "bar" },
  rf_cavity: { label: "RF cavity", colour: "#38bdf8", glyph: "pill" },
  screen: { label: "screen", colour: "#f472b6", glyph: "triangle" },
  generic_monitor: { label: "monitor", colour: "#a5b4fc", glyph: "triangle" },
  solenoid: { label: "solenoid", colour: "#fb923c", glyph: "box" },
  collimator: { label: "collimator", colour: "#a8a29e", glyph: "bar" },
  undulator: { label: "undulator", colour: "#a3e635", glyph: "box" },
  source: { label: "source", colour: "#34d399", glyph: "circle" },
  dump: { label: "dump", colour: "#78716c", glyph: "square" },
  mirror: { label: "mirror", colour: "#c4b5fd", glyph: "bar" },
  lens: { label: "lens", colour: "#7dd3fc", glyph: "pill" },
  beam_splitter: { label: "beam splitter", colour: "#e879f9", glyph: "diamond" },
  drift: { label: "drift", colour: "#475569", glyph: "box" },
  generic: { label: "other", colour: "#94a3b8", glyph: "circle" },
};
const ORDER = Object.keys(KIND_STYLE);
export const styleOf = (kind?: string | null) => KIND_STYLE[kind ?? "generic"] ?? KIND_STYLE.generic;

/** Transverse size of each glyph, as a fraction of the drawing's size unit (layout) or in pixels (line). */
const SIZE: Record<string, { w: number; h: number }> = {
  dipole: { w: 5, h: 64 }, quadrupole: { w: 4, h: 50 }, sextupole: { w: 3.2, h: 44 }, solenoid: { w: 3.6, h: 40 },
  rf_cavity: { w: 3.6, h: 40 }, undulator: { w: 3, h: 34 }, collimator: { w: 3, h: 40 }, drift: { w: 0.6, h: 6 },
};
const POINT = 1.15; // a thin element's marker, in size units

// ---------------------------------------------------------------------------- placement (the survey)

export interface Placed { node: BeamNode; x: number; y: number; yaw: number; length: number; angle: number }

const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

/** Where each element sits in the hall. The dataset's geometry when every element has it; otherwise the
 *  survey from `s`, lengths and bend angles (as a converter computes it); otherwise, for a ring with `s` but
 *  no angles, a circle of its circumference. Null when none of these can be drawn honestly. */
export function place(g: BeamPathGraph): Placed[] | null {
  const ns = g.nodes;
  if (ns.length < 2) return null;
  const len = (n: BeamNode) => num(n.length) ?? 0;
  const ang = (n: BeamNode) => (n.element_kind === "dipole" ? num(n.angle) ?? 0 : 0);
  if (ns.every((n) => num(n.geometry?.x) != null && num(n.geometry?.y) != null)) {
    return ns.map((n, i) => {
      const next = ns[(i + 1) % ns.length];
      const yaw = num(n.geometry?.yaw) ??
        Math.atan2(next.geometry!.y! - n.geometry!.y!, next.geometry!.x! - n.geometry!.x!);
      return { node: n, x: n.geometry!.x!, y: n.geometry!.y!, yaw, length: len(n), angle: ang(n) };
    });
  }
  if (!ns.every((n) => num(n.s) != null)) return null;
  const sorted = [...ns].sort((a, b) => a.s! - b.s!);
  const bend = sorted.reduce((t, n) => t + ang(n), 0);
  if (Math.abs(bend) > 1e-6) {
    let x = 0, y = 0, yaw = 0, pos = 0;
    const advance = (d: number, a: number) => {
      if (d <= 0) return;
      if (Math.abs(a) > 1e-12) {
        const r = d / a;
        x += r * (Math.sin(yaw + a) - Math.sin(yaw));
        y -= r * (Math.cos(yaw + a) - Math.cos(yaw));
        yaw += a;
      } else {
        x += d * Math.cos(yaw);
        y += d * Math.sin(yaw);
      }
    };
    return sorted.map((n) => {
      advance(n.s! - pos, 0);
      pos = Math.max(pos, n.s!);
      const p = { node: n, x, y, yaw, length: len(n), angle: ang(n) };
      advance(len(n), ang(n));
      pos = n.s! + len(n);
      return p;
    });
  }
  if (g.topology === "closed") {
    const C = num(g.length) ?? Math.max(...sorted.map((n) => n.s! + len(n)));
    const R = C / (2 * Math.PI);
    return sorted.map((n) => {
      const t = (n.s! / C) * 2 * Math.PI;
      return { node: n, x: R * Math.sin(t), y: R - R * Math.cos(t), yaw: t, length: len(n), angle: (len(n) / C) * 2 * Math.PI };
    });
  }
  return null;
}

/** Points along an element's centre line, from its entry: straight, or the arc a dipole bends. */
function centreLine(p: Placed, minLen: number, steps = 10): [number, number, number][] {
  const L = Math.max(p.length, minLen);
  const a = p.length > 0 ? p.angle : 0;
  const x0 = p.length > 0 ? p.x : p.x - (L / 2) * Math.cos(p.yaw);
  const y0 = p.length > 0 ? p.y : p.y - (L / 2) * Math.sin(p.yaw);
  const n = Math.abs(a) > 1e-9 ? steps : 1;
  const out: [number, number, number][] = [];
  for (let i = 0; i <= n; i++) {
    const d = (L * i) / n;
    if (Math.abs(a) > 1e-9) {
      const r = L / a;
      const t = (a * i) / n;
      out.push([x0 + r * (Math.sin(p.yaw + t) - Math.sin(p.yaw)), y0 - r * (Math.cos(p.yaw + t) - Math.cos(p.yaw)), p.yaw + t]);
    } else {
      out.push([x0 + d * Math.cos(p.yaw), y0 + d * Math.sin(p.yaw), p.yaw]);
    }
  }
  return out;
}

/** The glyph of an element in the hall, in world coordinates (y up; the SVG flips it). */
function layoutShape(p: Placed, u: number): { d: string; cx: number; cy: number } {
  const kind = p.node.element_kind ?? "generic";
  const st = styleOf(kind);
  const thin = p.length <= 1e-9;
  const pts = centreLine(p, POINT * u);
  const mid = pts[Math.floor(pts.length / 2)];
  const [cx, cy] = pts.length > 2 ? mid : [(pts[0][0] + pts[pts.length - 1][0]) / 2, (pts[0][1] + pts[pts.length - 1][1]) / 2];
  const path = (ps: [number, number][]) => "M" + ps.map(([x, y]) => `${x.toFixed(4)},${(-y).toFixed(4)}`).join("L") + "Z";
  if (thin || ["square", "diamond", "triangle", "circle"].includes(st.glyph) && !SIZE[kind]) {
    const r = (POINT * u) / 2 * (st.glyph === "diamond" ? 1.25 : 1);
    const yaw = p.yaw;
    const at = (dx: number, dy: number): [number, number] =>
      [cx + dx * Math.cos(yaw) - dy * Math.sin(yaw), cy + dx * Math.sin(yaw) + dy * Math.cos(yaw)];
    if (st.glyph === "diamond") return { d: path([at(-r, 0), at(0, r), at(r, 0), at(0, -r)]), cx, cy };
    if (st.glyph === "triangle") return { d: path([at(-r, -r), at(r, -r), at(0, r)]), cx, cy };
    if (st.glyph === "circle") {
      return { d: `M${cx - r},${-cy}a${r},${r} 0 1,0 ${2 * r},0a${r},${r} 0 1,0 ${-2 * r},0`, cx, cy };
    }
    return { d: path([at(-r, -r), at(r, -r), at(r, r), at(-r, r)]), cx, cy };
  }
  const half = ((SIZE[kind]?.w ?? 2.4) * u) / 2;
  const side = (k: number) => pts.map(([x, y, yaw]): [number, number] => [x - k * half * Math.sin(yaw), y + k * half * Math.cos(yaw)]);
  return { d: path([...side(1), ...side(-1).reverse()]), cx, cy };
}

// ---------------------------------------------------------------------------- chips, controls

export function KindChips({ nodes, hidden, toggle }: { nodes: BeamNode[]; hidden: Set<string>; toggle: (k: string) => void }) {
  const counts = new Map<string, number>();
  nodes.forEach((n) => counts.set(n.element_kind ?? "generic", (counts.get(n.element_kind ?? "generic") ?? 0) + 1));
  const kinds = [...counts.keys()].sort((a, b) => (ORDER.indexOf(a) + 99 * +(ORDER.indexOf(a) < 0)) - (ORDER.indexOf(b) + 99 * +(ORDER.indexOf(b) < 0)));
  return (
    <div className="flex flex-wrap gap-2">
      {kinds.map((k) => {
        const off = hidden.has(k);
        return (
          <button key={k} type="button" onClick={() => toggle(k)} title={off ? "Show" : "Hide"}
                  className={`flex items-center gap-2 rounded-full border px-3 py-1 text-xs ${off ? "border-slate-600 text-slate-500" : "border-indigo-300/70 bg-slate-800 text-slate-100"}`}>
            <span className="inline-block h-3 w-3 rounded-sm" style={{ background: off ? "transparent" : styleOf(k).colour, border: `1px solid ${styleOf(k).colour}` }} />
            {styleOf(k).label === "other" ? k.replace(/_/g, " ") : styleOf(k).label}
            <span className="text-slate-400">{counts.get(k)}</span>
          </button>
        );
      })}
    </div>
  );
}

function Tool({ on, onClick, children }: { on?: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" onClick={onClick}
            className={`rounded-md border px-3 py-1 text-xs ${on ? "border-indigo-300/70 bg-slate-700 text-white" : "border-slate-700 bg-slate-900 text-slate-200 hover:bg-slate-800"}`}>
      {children}
    </button>
  );
}

const CANVAS = "#151a17";

// ---------------------------------------------------------------------------- the hall layout

type Box = { x: number; y: number; w: number; h: number };

/** Pan with the mouse, zoom with the wheel about the cursor. */
function usePanZoom(home: Box) {
  const [box, setBox] = useState(home);
  const ref = useRef<SVGSVGElement>(null);
  const drag = useRef<{ x: number; y: number; box: Box; moved: boolean } | null>(null);
  const homeKey = `${home.x},${home.y},${home.w},${home.h}`;
  useEffect(() => setBox(home), [homeKey]); // eslint-disable-line react-hooks/exhaustive-deps
  const toWorld = (cx: number, cy: number, b: Box) => {
    const r = ref.current!.getBoundingClientRect();
    const k = Math.max(b.w / r.width, b.h / r.height);
    return { x: b.x + b.w / 2 + (cx - r.left - r.width / 2) * k, y: b.y + b.h / 2 + (cy - r.top - r.height / 2) * k, k };
  };
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      setBox((b) => {
        const f = Math.exp(e.deltaY * 0.0015);
        const p = toWorld(e.clientX, e.clientY, b);
        return { x: p.x - (p.x - b.x) * f, y: p.y - (p.y - b.y) * f, w: b.w * f, h: b.h * f };
      });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);
  const handlers = {
    onPointerDown: (e: React.PointerEvent) => { drag.current = { x: e.clientX, y: e.clientY, box, moved: false }; },
    onPointerMove: (e: React.PointerEvent) => {
      const d = drag.current;
      if (!d) return;
      if (Math.abs(e.clientX - d.x) + Math.abs(e.clientY - d.y) > 3) d.moved = true;
      if (!d.moved) return;
      const k = toWorld(0, 0, d.box).k;
      setBox({ ...d.box, x: d.box.x - (e.clientX - d.x) * k, y: d.box.y - (e.clientY - d.y) * k });
    },
    onPointerUp: () => { setTimeout(() => { drag.current = null; }, 0); },
    onPointerLeave: () => { drag.current = null; },
  };
  const wasDrag = () => !!drag.current?.moved;
  return { ref, box, reset: () => setBox(home), handlers, wasDrag };
}

export function LayoutView({ g, placed, selected, onPick }: { g: BeamPathGraph; placed: Placed[]; selected: string | null; onPick: (uid: string) => void }) {
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [names, setNames] = useState(true);
  const xs = placed.map((p) => p.x);
  const ys = placed.map((p) => p.y);
  const [minX, maxX, minY, maxY] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const span = Math.max(maxX - minX, maxY - minY, 1);
  const u = span / 70;                       // the size unit: glyph widths, label sizes
  const font = u * 0.95;
  const pad = span * 0.22;
  const home = { x: minX - pad, y: -maxY - pad, w: maxX - minX + 2 * pad, h: maxY - minY + 2 * pad };
  const pz = usePanZoom(home);
  const cx0 = (minX + maxX) / 2, cy0 = (minY + maxY) / 2;

  const shapes = useMemo(() => placed.map((p) => ({ p, ...layoutShape(p, u) })), [placed, u]);
  // Labels outside the line, pushed further out when they would overlap the previous one.
  const labels = useMemo(() => {
    const out: { uid: string; ax: number; ay: number; lx: number; ly: number; rot: number; anchor: "start" | "end" }[] = [];
    const last: { x: number; y: number }[] = [];
    for (const s of shapes) {
      if (hidden.has(s.p.node.element_kind ?? "generic")) continue;
      let nx = Math.sin(s.p.yaw), ny = -Math.cos(s.p.yaw);
      if (nx * (s.cx - cx0) + ny * (s.cy - cy0) < 0) { nx = -nx; ny = -ny; }
      const base = (SIZE[s.p.node.element_kind ?? ""]?.w ?? POINT) * u / 2 + u * 0.9;
      let level = 0;
      for (; level < 4; level++) {
        const lx = s.cx + nx * (base + level * u * 3.4), ly = s.cy + ny * (base + level * u * 3.4);
        const prev = last[level];
        if (!prev || Math.hypot(prev.x - lx, prev.y - ly) > font * 1.25) break;
      }
      level = Math.min(level, 3);
      const d = base + level * u * 3.4;
      const lx = s.cx + nx * d, ly = s.cy + ny * d;
      last[level] = { x: lx, y: ly };
      let rot = (Math.atan2(-ny, nx) * 180) / Math.PI;
      let anchor: "start" | "end" = "start";
      if (rot > 90 || rot < -90) { rot += 180; anchor = "end"; }
      out.push({ uid: s.p.node.uid, ax: s.cx + nx * (base - u * 0.7), ay: s.cy + ny * (base - u * 0.7), lx, ly, rot, anchor });
    }
    return out;
  }, [shapes, hidden, u, font, cx0, cy0]);

  // The reference trajectory: straight between elements, through each dipole along its arc.
  const line = placed.flatMap((p) => (p.length > 0 ? centreLine(p, 0, 16) : [[p.x, p.y, p.yaw] as [number, number, number]]))
    .map(([x, y]) => `${x},${-y}`).join(" ") + (g.topology === "closed" ? ` ${placed[0].x},${-placed[0].y}` : "");
  const pick = (uid: string) => { if (!pz.wasDrag()) onPick(uid); };
  return (
    <div className="flex h-full flex-col gap-3 p-3" style={{ background: "#0f1311" }}>
      <KindChips nodes={g.nodes} hidden={hidden} toggle={(k) => setHidden((h) => { const n = new Set(h); n.has(k) ? n.delete(k) : n.add(k); return n; })} />
      <div className="relative min-h-0 flex-1 overflow-hidden rounded-lg border border-slate-700" style={{ background: CANVAS }}>
        <div className="absolute left-3 top-3 z-10 flex gap-2">
          <Tool onClick={pz.reset}>Reset view</Tool>
          <Tool on={names} onClick={() => setNames((v) => !v)}>Names</Tool>
        </div>
        <ScaleBar box={pz.box} svg={pz.ref} />
        <svg ref={pz.ref} className="h-full w-full cursor-grab touch-none active:cursor-grabbing" {...pz.handlers}
             viewBox={`${pz.box.x} ${pz.box.y} ${pz.box.w} ${pz.box.h}`}>
          <polyline points={line} fill="none" stroke="#8a948f" strokeWidth={u * 0.12} />
          {shapes.map(({ p, d }) => {
            const kind = p.node.element_kind ?? "generic";
            if (hidden.has(kind)) return null;
            const sel = p.node.uid === selected;
            return (
              <path key={p.node.uid} d={d} fill={styleOf(kind).colour} stroke={sel ? "#7dd3fc" : "#0b0f0d"}
                    strokeWidth={sel ? u * 0.35 : u * 0.06} className="cursor-pointer" onClick={() => pick(p.node.uid)}>
                <title>{tip(p.node)}</title>
              </path>
            );
          })}
          {names && labels.map((l) => {
            const sel = l.uid === selected;
            const n = placed.find((p) => p.node.uid === l.uid)!.node;
            return (
              <g key={l.uid} className="cursor-pointer" onClick={() => pick(l.uid)}>
                <line x1={l.ax} y1={-l.ay} x2={l.lx} y2={-l.ly} stroke="#6b7280" strokeWidth={u * 0.05} />
                <text x={l.lx} y={-l.ly} fontSize={font} dominantBaseline="middle" textAnchor={l.anchor}
                      transform={`rotate(${l.rot} ${l.lx} ${-l.ly})`} fontWeight={600}
                      fill={sel ? "#93c5fd" : "#e5e7eb"} style={{ paintOrder: "stroke" }} stroke={CANVAS} strokeWidth={font * 0.25}>
                  {` ${n.name} `}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}

/** A scale bar in metres for the current zoom. */
function ScaleBar({ box, svg }: { box: Box; svg: React.RefObject<SVGSVGElement | null> }) {
  const [px, setPx] = useState(800);
  useEffect(() => {
    const el = svg.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setPx(el.getBoundingClientRect().width || 800));
    ro.observe(el);
    return () => ro.disconnect();
  }, [svg]);
  const mPerPx = Math.max(box.w / px, box.h / ((px * 9) / 16));
  const target = mPerPx * 120;
  const p10 = 10 ** Math.floor(Math.log10(target));
  const m = [1, 2, 5, 10].map((k) => k * p10).filter((v) => v <= target).pop() ?? p10;
  return (
    <div className="pointer-events-none absolute bottom-3 left-3 z-10 text-[11px] text-slate-300">
      <div className="h-1.5 border-x border-b border-slate-300" style={{ width: m / mPerPx }} />
      {m >= 1 ? `${m} m` : `${Math.round(m * 1000)} mm`}
    </div>
  );
}

function tip(n: BeamNode) {
  return `${n.name} (${n.element_kind ?? "element"})${n.s != null ? ` · s = ${n.s.toFixed(3)} m` : ""}` +
    `${n.length ? ` · L = ${n.length} m` : ""}${n.angle ? ` · angle = ${((n.angle * 180) / Math.PI).toFixed(2)}°` : ""}`;
}

// ---------------------------------------------------------------------------- unrolled along s

/** Labels in one row, in order, pushed apart to at least `gap` and centred back on what they label. */
function spread(xs: number[], gap: number): number[] {
  const out = [...xs];
  for (let i = 1; i < out.length; i++) out[i] = Math.max(out[i], out[i - 1] + gap);
  // Pull clusters back so a crowd of labels sits around its elements, not all to their right.
  let i = 0;
  while (i < out.length) {
    let j = i;
    while (j + 1 < out.length && out[j + 1] - out[j] <= gap + 1e-6) j++;
    const shift = (xs.slice(i, j + 1).reduce((a, b) => a + b, 0) - out.slice(i, j + 1).reduce((a, b) => a + b, 0)) / (j - i + 1);
    const lo = i > 0 ? out[i - 1] + gap - out[i] : -Infinity;
    const s = Math.max(shift, lo);
    for (let k = i; k <= j; k++) out[k] += s;
    i = j + 1;
  }
  return out;
}

export function LineView({ g, selected, onPick }: { g: BeamPathGraph; selected: string | null; onPick: (uid: string) => void }) {
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [names, setNames] = useState(true);
  const [zoom, setZoom] = useState(1);
  const wrap = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(1000);
  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth || 1000));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  useEffect(() => setZoom(1), [g.path.uid]);

  const withS = g.nodes.every((n) => n.s != null);
  const nodes = withS ? [...g.nodes].sort((a, b) => a.s! - b.s!) : g.nodes;
  const total = withS ? Math.max(g.length ?? 0, ...nodes.map((n) => n.s! + (n.length ?? 0)), 1e-6) : Math.max(nodes.length, 1);
  const M = 36;
  const W = Math.max(width, 400) * zoom;
  const k = (W - 2 * M) / total;                       // px per metre
  const xOf = (n: BeamNode) => M + (withS ? n.s! : n.index + 0.5) * k;
  const wOf = (n: BeamNode) => (withS && n.length ? n.length * k : 0);
  const optics = nodes.filter((n) => n.optics && (n.optics.beta_x != null || n.optics.beta_y != null));
  const hasOptics = withS && optics.length >= 2;
  const AX = 210, LBL = 150, PLOT = hasOptics ? 150 : 0;
  const H = AX + 60 + (hasOptics ? PLOT + 60 : 30);
  const visible = nodes.filter((n) => !hidden.has(n.element_kind ?? "generic"));
  const lx = spread(visible.map((n) => xOf(n) + wOf(n) / 2), 15);
  const ticks = useMemo(() => {
    if (!withS) return [];
    const target = total / Math.max(4, W / 110);
    const p10 = 10 ** Math.floor(Math.log10(target));
    const step = [1, 2, 5, 10].map((v) => v * p10).find((v) => v >= target) ?? p10;
    return Array.from({ length: Math.floor(total / step) + 1 }, (_, i) => +(i * step).toFixed(9));
  }, [withS, total, W]);
  const bmax = hasOptics ? Math.max(...optics.flatMap((n) => [n.optics!.beta_x ?? 0, n.optics!.beta_y ?? 0])) : 1;
  const bY = (v: number) => AX + 90 + PLOT - (v / (bmax * 1.08)) * PLOT;
  const curve = (key: "beta_x" | "beta_y") => optics.filter((n) => n.optics![key] != null)
    .map((n) => `${xOf(n) + wOf(n) / 2},${bY(n.optics![key]!)}`).join(" ");

  return (
    <div className="flex h-full flex-col gap-3 p-3" style={{ background: "#0f1311" }}>
      <KindChips nodes={g.nodes} hidden={hidden} toggle={(kd) => setHidden((h) => { const n = new Set(h); n.has(kd) ? n.delete(kd) : n.add(kd); return n; })} />
      <div className="flex gap-2">
        <Tool onClick={() => setZoom(1)}>Reset view</Tool>
        <Tool on={names} onClick={() => setNames((v) => !v)}>Names</Tool>
        <Tool onClick={() => setZoom((z) => Math.min(z * 1.6, 40))}>＋</Tool>
        <Tool onClick={() => setZoom((z) => Math.max(z / 1.6, 1))}>－</Tool>
        {withS && <span className="self-center text-[11px] text-slate-400">{k >= 1 ? `${k.toFixed(1)} px/m` : `${(1 / k).toFixed(2)} m/px`} · same scale for lengths and gaps</span>}
      </div>
      <div ref={wrap} className="min-h-0 flex-1 overflow-x-auto overflow-y-auto rounded-lg border border-slate-700" style={{ background: CANVAS }}>
        <svg width={W} height={H} style={{ display: "block" }}>
          <line x1={M} y1={AX} x2={M + total * k} y2={AX} stroke="#8a948f" strokeWidth={1.2} />
          {g.topology === "closed" && withS && (
            <text x={M + total * k} y={AX + 28} fontSize={11} textAnchor="end" fill="#94a3b8">↻ closes to {nodes[0]?.name}</text>
          )}
          {names && visible.map((n, i) => {
            const x = xOf(n) + wOf(n) / 2;
            const h = SIZE[n.element_kind ?? ""]?.h ?? 18;
            const sel = n.uid === selected;
            return (
              <g key={`l${n.uid}`} className="cursor-pointer" onClick={() => onPick(n.uid)}>
                <polyline points={`${x},${AX - h / 2 - 3} ${x},${AX - h / 2 - 16} ${lx[i]},${AX - LBL + 46} ${lx[i]},${AX - LBL + 40}`}
                          fill="none" stroke="#6b7280" strokeWidth={0.8} />
                <text x={lx[i]} y={AX - LBL + 36} fontSize={12} fontWeight={600} transform={`rotate(-90 ${lx[i]} ${AX - LBL + 36})`}
                      dominantBaseline="middle" fill={sel ? "#93c5fd" : "#e5e7eb"}>{n.name}</text>
              </g>
            );
          })}
          {visible.map((n) => <LineGlyph key={n.uid} n={n} x={xOf(n)} w={wOf(n)} y={AX} sel={n.uid === selected} onPick={onPick} />)}
          {withS && ticks.map((t) => (
            <g key={t}>
              <line x1={M + t * k} y1={AX + 40} x2={M + t * k} y2={AX + 46} stroke="#6b7280" />
              <text x={M + t * k} y={AX + 60} fontSize={11} textAnchor="middle" fill="#9ca3af">{t} m</text>
            </g>
          ))}
          {!withS && <text x={M} y={AX + 60} fontSize={11} fill="#9ca3af">no s in this dataset: elements in beam order, not to scale</text>}
          {hasOptics && (
            <g>
              <line x1={M} y1={AX + 90 + PLOT} x2={M + total * k} y2={AX + 90 + PLOT} stroke="#374151" />
              {[0.5, 1].map((f) => (
                <g key={f}>
                  <line x1={M} y1={bY(bmax * f)} x2={M + total * k} y2={bY(bmax * f)} stroke="#1f2937" />
                  <text x={M - 4} y={bY(bmax * f)} fontSize={10} textAnchor="end" dominantBaseline="middle" fill="#9ca3af">{(bmax * f).toFixed(bmax * f < 10 ? 1 : 0)}</text>
                </g>
              ))}
              <polyline points={curve("beta_x")} fill="none" stroke="#60a5fa" strokeWidth={1.6} />
              <polyline points={curve("beta_y")} fill="none" stroke="#f87171" strokeWidth={1.6} />
              <text x={M} y={AX + 80} fontSize={11} fill="#9ca3af">β [m]  <tspan fill="#60a5fa">— βx</tspan>  <tspan fill="#f87171">— βy</tspan></text>
            </g>
          )}
        </svg>
      </div>
    </div>
  );
}

function LineGlyph({ n, x, w, y, sel, onPick }: { n: BeamNode; x: number; w: number; y: number; sel: boolean; onPick: (uid: string) => void }) {
  const kind = n.element_kind ?? "generic";
  const st = styleOf(kind);
  const size = SIZE[kind];
  const stroke = sel ? "#7dd3fc" : "#0b0f0d";
  const sw = sel ? 2.5 : 0.8;
  const common = { fill: st.colour, stroke, strokeWidth: sw, className: "cursor-pointer", onClick: () => onPick(n.uid) };
  const t = <title>{tip(n)}</title>;
  if (w > 0 && size) {
    const ww = Math.max(w, 3);
    const h = size.h;
    if (st.glyph === "sector") {
      const inset = Math.min(ww * 0.18, 10);    // a bend drawn as a trapezoid, wider at the top
      return <path d={`M${x},${y - h / 2} h${ww} l${-inset},${h} h${-(ww - 2 * inset)} z`} {...common}>{t}</path>;
    }
    if (st.glyph === "pill") return <rect x={x} y={y - h / 2} width={ww} height={h} rx={Math.min(ww, h) / 2.5} {...common}>{t}</rect>;
    return <rect x={x} y={y - h / 2} width={ww} height={h} {...common}>{t}</rect>;
  }
  const cx = x + w / 2;
  const r = 8;
  if (st.glyph === "diamond") return <path d={`M${cx - r},${y} L${cx},${y - r} L${cx + r},${y} L${cx},${y + r} z`} {...common}>{t}</path>;
  if (st.glyph === "triangle") return <path d={`M${cx - r},${y + r} L${cx + r},${y + r} L${cx},${y - r} z`} {...common}>{t}</path>;
  if (st.glyph === "circle" || st.glyph === "pill") return <circle cx={cx} cy={y} r={r} {...common}>{t}</circle>;
  const hh = st.glyph === "bar" ? 30 : st.glyph === "sector" ? 40 : r;
  const ww = st.glyph === "bar" ? 5 : r * 2;
  return <rect x={cx - ww / 2} y={y - (st.glyph === "square" ? r : hh / 2)} width={ww} height={st.glyph === "square" ? 2 * r : hh} {...common}>{t}</rect>;
}
