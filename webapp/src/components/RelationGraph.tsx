import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { assetsApi, relationsApi } from "../api/client";

const SIZE = 560;
const CENTER = SIZE / 2;
const RADIUS = 200;

export function RelationGraph({
  assetUid,
  onClose,
}: {
  assetUid: string;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const relations = useQuery({ queryKey: ["relations"], queryFn: relationsApi.list });
  const assets = useQuery({ queryKey: ["assets"], queryFn: () => assetsApi.list() });

  const byUid = new Map((assets.data ?? []).map((a) => [a.uid, a]));
  const center = byUid.get(assetUid);

  const edges = (relations.data ?? [])
    .filter((r) => r.from_asset_uid === assetUid || r.to_asset_uid === assetUid)
    .map((r) => ({
      relation: r,
      direction: r.from_asset_uid === assetUid ? "out" : ("in" as const),
      neighborUid: r.from_asset_uid === assetUid ? r.to_asset_uid : r.from_asset_uid,
    }));

  const n = edges.length;
  const positioned = edges.map((e, i) => {
    const angle = (2 * Math.PI * i) / Math.max(n, 1) - Math.PI / 2;
    return {
      ...e,
      x: CENTER + RADIUS * Math.cos(angle),
      y: CENTER + RADIUS * Math.sin(angle),
    };
  });

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-6"
      onClick={onClose}
    >
      <div
        className="max-h-full w-full max-w-3xl overflow-auto rounded-lg bg-white p-4 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-900">
            Relations for {center?.name ?? assetUid}
          </h2>
          <button
            onClick={onClose}
            className="rounded px-2 py-1 text-sm text-slate-500 hover:bg-slate-100"
          >
            Close
          </button>
        </div>

        {n === 0 ? (
          <p className="p-8 text-center text-sm text-slate-400">No relations to graph.</p>
        ) : (
          <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="mx-auto w-full max-w-xl">
            <defs>
              <marker
                id="arrow"
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M0,0 L10,5 L0,10 z" fill="#94a3b8" />
              </marker>
            </defs>

            {positioned.map((e, i) => {
              const [x1, y1, x2, y2] =
                e.direction === "out"
                  ? [CENTER, CENTER, e.x, e.y]
                  : [e.x, e.y, CENTER, CENTER];
              return (
                <g key={i}>
                  <line
                    x1={x1}
                    y1={y1}
                    x2={x2}
                    y2={y2}
                    stroke="#94a3b8"
                    strokeWidth={1.5}
                    markerEnd="url(#arrow)"
                  />
                  <text
                    x={(e.x + CENTER) / 2}
                    y={(e.y + CENTER) / 2 - 4}
                    textAnchor="middle"
                    className="fill-slate-500"
                    fontSize={10}
                  >
                    {e.relation.relation_type}
                  </text>
                </g>
              );
            })}

            {positioned.map((e, i) => {
              const neighbor = byUid.get(e.neighborUid);
              return (
                <g
                  key={`node-${i}`}
                  className="cursor-pointer"
                  onClick={() => {
                    onClose();
                    navigate(`/assets/${e.neighborUid}`);
                  }}
                >
                  <circle cx={e.x} cy={e.y} r={28} fill="#eef2ff" stroke="#6366f1" />
                  <text
                    x={e.x}
                    y={e.y}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fontSize={9}
                    className="fill-indigo-700"
                  >
                    {(neighbor?.name ?? e.neighborUid).slice(0, 14)}
                  </text>
                </g>
              );
            })}

            <circle cx={CENTER} cy={CENTER} r={34} fill="#0f172a" />
            <text
              x={CENTER}
              y={CENTER}
              textAnchor="middle"
              dominantBaseline="middle"
              fontSize={10}
              fill="white"
            >
              {(center?.name ?? assetUid).slice(0, 16)}
            </text>
          </svg>
        )}
      </div>
    </div>
  );
}
