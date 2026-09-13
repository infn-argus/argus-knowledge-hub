import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { issueLinksApi } from "../api/client";

const SIZE = 620;
const CENTER = SIZE / 2;
const RADIUS = 210;

/** Colour by what a node *is*, since the point of the picture is that a
 * ticket sits between equipment, documentation and other work. */
const NODE_STYLES = {
  asset: { fill: "#eef2ff", stroke: "#6366f1", text: "#3730a3" },
  document: { fill: "#ecfdf5", stroke: "#10b981", text: "#065f46" },
  ticket: { fill: "#fff7ed", stroke: "#f59e0b", text: "#92400e" },
} as const;

type NodeKind = keyof typeof NODE_STYLES;

interface GraphNode {
  kind: NodeKind;
  label: string;
  sublabel?: string;
  relation: string;
  href: string;
}

export function TicketGraph({
  issueUid,
  title,
  onClose,
}: {
  issueUid: string;
  title: string;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const links = useQuery({
    queryKey: ["issue-links", issueUid],
    queryFn: () => issueLinksApi.list(issueUid),
  });

  const nodes: GraphNode[] = [
    ...(links.data?.assets ?? []).map((a) => ({
      kind: "asset" as const,
      label: a.name,
      sublabel: a.key,
      relation: a.relation,
      href: `/assets/${a.asset_uid}`,
    })),
    ...(links.data?.documents ?? []).map((d) => ({
      kind: "document" as const,
      label: d.title,
      sublabel: d.code,
      relation: d.relation,
      href: `/documents/${d.document_uid}`,
    })),
    ...(links.data?.tickets ?? []).map((t) => ({
      kind: "ticket" as const,
      label: t.title,
      sublabel: t.source_key ?? undefined,
      relation: t.outgoing ? t.relation : `${t.relation} ⟵`,
      href: `/tickets/${t.issue_uid}`,
    })),
  ];

  const positioned = nodes.map((node, i) => {
    const angle = (2 * Math.PI * i) / Math.max(nodes.length, 1) - Math.PI / 2;
    return {
      ...node,
      x: CENTER + RADIUS * Math.cos(angle),
      y: CENTER + RADIUS * Math.sin(angle),
    };
  });

  const truncate = (text: string, max: number) =>
    text.length > max ? `${text.slice(0, max - 1)}…` : text;

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
            What {truncate(title, 48)} connects to
          </h2>
          <button
            onClick={onClose}
            className="rounded px-2 py-1 text-sm text-slate-500 hover:bg-slate-100"
          >
            Close
          </button>
        </div>

        <div className="mb-2 flex gap-3 text-xs text-slate-500">
          {(["asset", "document", "ticket"] as NodeKind[]).map((kind) => (
            <span key={kind} className="inline-flex items-center gap-1">
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ background: NODE_STYLES[kind].stroke }}
              />
              {kind === "asset" ? "objects" : kind === "document" ? "documents" : "tickets"}
            </span>
          ))}
        </div>

        {nodes.length === 0 ? (
          <p className="py-10 text-center text-sm text-slate-400">
            This ticket isn't linked to anything yet.
          </p>
        ) : (
          <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="w-full">
            {positioned.map((node, i) => (
              <g key={`${node.href}-${i}`}>
                <line
                  x1={CENTER}
                  y1={CENTER}
                  x2={node.x}
                  y2={node.y}
                  stroke={NODE_STYLES[node.kind].stroke}
                  strokeWidth={1.5}
                  strokeOpacity={0.5}
                />
                <text
                  x={(CENTER + node.x) / 2}
                  y={(CENTER + node.y) / 2 - 4}
                  textAnchor="middle"
                  className="fill-slate-400"
                  style={{ fontSize: 10 }}
                >
                  {node.relation}
                </text>
              </g>
            ))}

            {positioned.map((node, i) => (
              <g
                key={`node-${node.href}-${i}`}
                className="cursor-pointer"
                onClick={() => {
                  onClose();
                  navigate(node.href);
                }}
              >
                <rect
                  x={node.x - 82}
                  y={node.y - 20}
                  width={164}
                  height={40}
                  rx={6}
                  fill={NODE_STYLES[node.kind].fill}
                  stroke={NODE_STYLES[node.kind].stroke}
                />
                <text
                  x={node.x}
                  y={node.y - 2}
                  textAnchor="middle"
                  style={{ fontSize: 11, fill: NODE_STYLES[node.kind].text }}
                >
                  {truncate(node.label, 24)}
                </text>
                {node.sublabel && (
                  <text
                    x={node.x}
                    y={node.y + 11}
                    textAnchor="middle"
                    className="fill-slate-400"
                    style={{ fontSize: 9 }}
                  >
                    {truncate(node.sublabel, 26)}
                  </text>
                )}
              </g>
            ))}

            <rect
              x={CENTER - 96}
              y={CENTER - 22}
              width={192}
              height={44}
              rx={7}
              fill="#0f172a"
            />
            <text
              x={CENTER}
              y={CENTER + 4}
              textAnchor="middle"
              style={{ fontSize: 12, fill: "#ffffff" }}
            >
              {truncate(title, 26)}
            </text>
          </svg>
        )}
      </div>
    </div>
  );
}
