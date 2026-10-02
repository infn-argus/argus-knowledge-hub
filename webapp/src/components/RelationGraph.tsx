import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { GraphCanvas, IN, OUT } from "./graph/GraphCanvas";
import { edgeKey, type GEdge } from "./graph/model";
import { useBranches } from "./graph/useBranches";

/* An asset's relations as a directed graph that grows on demand: what points at a node to its left, what it
   points at to its right. Double-clicking a node opens its branches on the same rule, and folds them again;
   many neighbours of one kind arrive as one group that opens on demand. */
export function RelationGraph({ assetUid, onClose }: { assetUid: string; onClose: () => void }) {
  const navigate = useNavigate();
  const [rootUid, setRootUid] = useState(assetUid);
  const graph = useBranches({ kind: "asset", uid: rootUid }, ["asset"]);
  const [selected, setSelected] = useState<string | null>(null);
  const [showIn, setShowIn] = useState(true);
  const [showOut, setShowOut] = useState(true);
  const current = selected && graph.nodes.has(selected) ? selected : graph.rootId;
  const sel = current ? graph.nodes.get(current) : undefined;

  const edges = graph.edges.filter((e) => (e.to === current ? showIn : e.from === current ? showOut : true));
  const selIn = graph.edges.filter((e) => e.to === current && graph.nodes.has(e.from));
  const selOut = graph.edges.filter((e) => e.from === current && graph.nodes.has(e.to));
  const name = (id: string) => graph.nodes.get(id)?.label ?? id;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="flex h-full max-h-[90vh] w-full max-w-7xl flex-col rounded-lg bg-white shadow-xl"
           onClick={(e) => e.stopPropagation()}>
        <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 px-4 py-2">
          <h2 className="text-sm font-semibold text-slate-900">Relations of {graph.rootId ? name(graph.rootId) : ""}</h2>
          <DirectionLegend />
          <label className="flex items-center gap-1 text-xs text-slate-600">
            <input type="checkbox" checked={showIn} onChange={(e) => setShowIn(e.target.checked)} /> inbound
          </label>
          <label className="flex items-center gap-1 text-xs text-slate-600">
            <input type="checkbox" checked={showOut} onChange={(e) => setShowOut(e.target.checked)} /> outbound
          </label>
          <span className="text-xs text-slate-400">Click to select · double-click to open or fold · drag to pan · scroll to zoom</span>
          <button onClick={onClose} className="ml-auto rounded px-2 py-1 text-sm text-slate-500 hover:bg-slate-100">Close</button>
        </div>
        {graph.error && <p className="px-4 py-2 text-sm text-red-600">{graph.error}</p>}
        <div className="flex min-h-0 flex-1">
          <div className="min-w-0 flex-1">
            <GraphCanvas nodes={graph.nodes} edges={edges} rootId={graph.rootId} selected={current}
                         onSelect={setSelected} onOpen={graph.toggle} open={graph.open} loading={graph.loading} />
          </div>
          {sel && (
            <aside className="w-72 shrink-0 overflow-y-auto border-l border-slate-200 p-3 text-sm">
              <div className="font-semibold text-slate-900">{sel.restricted ? "Restricted" : sel.label}</div>
              <div className="text-xs text-slate-500">{sel.bundle ? `grouped by “${sel.sub}”` : sel.sub}</div>
              {sel.bundle ? (
                <button onClick={() => graph.toggle(sel)} className="mt-2 rounded border border-slate-300 px-2 py-0.5 text-xs hover:bg-slate-50">
                  Show all {sel.bundle.members.length}
                </button>
              ) : !sel.restricted && (
                <div className="mt-2 flex flex-wrap gap-1">
                  <button onClick={() => { onClose(); navigate(`/assets/${sel.uid}`); }}
                          className="rounded border border-slate-300 px-2 py-0.5 text-xs hover:bg-slate-50">Open</button>
                  <button onClick={() => graph.toggle(sel)}
                          className="rounded border border-slate-300 px-2 py-0.5 text-xs hover:bg-slate-50">
                    {graph.open.has(sel.id) ? "Fold branches" : "Open branches"}
                  </button>
                  {sel.id !== graph.rootId && (
                    <button onClick={() => { setSelected(null); setRootUid(sel.uid); }}
                            className="rounded border border-slate-300 px-2 py-0.5 text-xs hover:bg-slate-50">Centre here</button>
                  )}
                </div>
              )}
              <RelationList title="Inbound" color={IN} edges={selIn} side="in" name={name} onPick={setSelected} />
              <RelationList title="Outbound" color={OUT} edges={selOut} side="out" name={name} onPick={setSelected} />
              {!graph.open.has(sel.id) && !sel.bundle && (
                <p className="mt-3 text-xs text-slate-400">Only the relations already drawn are listed: open its branches to see all.</p>
              )}
            </aside>
          )}
        </div>
      </div>
    </div>
  );
}

export function DirectionLegend() {
  return (
    <span className="flex items-center gap-3 text-xs text-slate-600">
      <span className="flex items-center gap-1"><span className="inline-block h-0.5 w-5" style={{ background: IN }} /> inbound (points at the selected)</span>
      <span className="flex items-center gap-1"><span className="inline-block h-0.5 w-5" style={{ background: OUT }} /> outbound (the selected points at)</span>
    </span>
  );
}

export function RelationList({
  title, color, edges, side, name, onPick,
}: {
  title: string; color: string; edges: GEdge[]; side: "in" | "out";
  name: (id: string) => string; onPick: (id: string) => void;
}) {
  return (
    <div className="mt-3">
      <div className="text-xs font-semibold uppercase tracking-wide" style={{ color }}>{title} ({edges.length})</div>
      {edges.length === 0 ? (
        <div className="text-xs text-slate-400">none shown</div>
      ) : (
        <ul className="mt-1 space-y-0.5">
          {edges.map((e) => {
            const other = side === "in" ? e.from : e.to;
            return (
              <li key={edgeKey(e)} className="text-xs">
                <button onClick={() => onPick(other)} className="text-left hover:underline">
                  {side === "in" ? (
                    <><span className="text-slate-900">{name(other)}</span> <span className="text-slate-500">{e.relation} →</span> this</>
                  ) : (
                    <>this <span className="text-slate-500">{e.relation} →</span> <span className="text-slate-900">{name(other)}</span></>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
