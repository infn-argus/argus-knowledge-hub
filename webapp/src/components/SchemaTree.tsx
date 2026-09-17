import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { assetsApi, documentsApi, iconsApi, issuesApi, schemasApi } from "../api/client";
import { AppSchema } from "../api/types";
import { useCurrentWorkspaceId } from "../api/useCurrentWorkspaceId";
import { AuthenticatedImage } from "./AuthenticatedImage";

interface TreeNode {
  schema: AppSchema;
  children: TreeNode[];
}

function buildTree(schemas: AppSchema[]): TreeNode[] {
  const byUid = new Map(schemas.map((s) => [s.uid, { schema: s, children: [] as TreeNode[] }]));
  const roots: TreeNode[] = [];
  for (const s of schemas) {
    const node = byUid.get(s.uid)!;
    if (s.parent_schema_uid && byUid.has(s.parent_schema_uid)) {
      byUid.get(s.parent_schema_uid)!.children.push(node);
    } else {
      roots.push(node);
    }
  }
  const sortRec = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => a.schema.name.localeCompare(b.schema.name));
    nodes.forEach((n) => sortRec(n.children));
  };
  sortRec(roots);
  return roots;
}

/** Keeps a node if it (or any descendant) matches the query, expanding its full subtree. */
function filterTree(nodes: TreeNode[], query: string): TreeNode[] {
  if (!query) return nodes;
  const q = query.toLowerCase();
  const walk = (node: TreeNode): TreeNode | null => {
    const children = node.children.map(walk).filter((n): n is TreeNode => n !== null);
    if (node.schema.name.toLowerCase().includes(q) || children.length > 0) {
      return { schema: node.schema, children };
    }
    return null;
  };
  return nodes.map(walk).filter((n): n is TreeNode => n !== null);
}

function TreeNodeRow({
  node,
  depth,
  counts,
  selectedUid,
  onSelect,
  forceExpanded,
}: {
  node: TreeNode;
  depth: number;
  counts: Map<string, number>;
  selectedUid: string | null;
  onSelect: (uid: string) => void;
  forceExpanded?: boolean;
}) {
  const [expandedState, setExpanded] = useState(depth < 1);
  const expanded = forceExpanded || expandedState;
  const hasChildren = node.children.length > 0;
  const count = counts.get(node.schema.uid) ?? 0;
  const isSelected = node.schema.uid === selectedUid;

  return (
    <div>
      <div
        className={`flex cursor-pointer items-center gap-1 rounded px-1.5 py-1 text-xs hover:bg-slate-100 ${
          isSelected ? "bg-slate-100 font-medium text-slate-900" : "text-slate-600"
        }`}
        style={{ paddingLeft: `${depth * 12 + 6}px` }}
        onClick={() => onSelect(node.schema.uid)}
      >
        <span
          className="w-3 shrink-0 text-slate-400"
          onClick={(e) => {
            if (hasChildren) {
              e.stopPropagation();
              setExpanded((v) => !v);
            }
          }}
        >
          {hasChildren ? (expanded ? "▾" : "▸") : ""}
        </span>
        {node.schema.icon_uid ? (
          <AuthenticatedImage
            uid={node.schema.icon_uid}
            alt=""
            fetchBlobUrl={iconsApi.fetchBlobUrl}
            className="h-3.5 w-3.5 shrink-0 rounded-sm object-contain"
          />
        ) : (
          <span className="h-3.5 w-3.5 shrink-0 rounded-sm bg-slate-200" />
        )}
        <span className="truncate">{node.schema.name}</span>
        {count > 0 && <span className="ml-auto shrink-0 text-slate-400">{count}</span>}
      </div>
      {hasChildren && expanded && (
        <div>
          {node.children.map((child) => (
            <TreeNodeRow
              key={child.schema.uid}
              node={child}
              depth={depth + 1}
              counts={counts}
              selectedUid={selectedUid}
              onSelect={onSelect}
              forceExpanded={forceExpanded}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function SchemaTree({
  appliesTo = "objects",
}: {
  appliesTo?: "objects" | "tickets" | "documents";
}) {
  const navigate = useNavigate();
  const { uid: selectedUid } = useParams<{ uid?: string }>();
  const [query, setQuery] = useState("");
  const currentWorkspaceId = useCurrentWorkspaceId();

  const schemas = useQuery({ queryKey: ["schemas"], queryFn: schemasApi.list });
  const assets = useQuery({
    queryKey: ["assets"],
    queryFn: () => assetsApi.list(),
    enabled: appliesTo === "objects",
  });
  const issues = useQuery({
    queryKey: ["issues"],
    queryFn: () => issuesApi.list(),
    enabled: appliesTo === "tickets",
  });
  const documents = useQuery({
    queryKey: ["documents"],
    queryFn: () => documentsApi.list(),
    enabled: appliesTo === "documents",
  });

  // /v1/schemas also returns every *global* type owned by another workspace,
  // because references have to resolve across workspaces. That belongs in the
  // reference pickers, not here: a workspace with 24 types of its own was
  // listing 105 once a neighbouring workspace shared its catalogue. The tree
  // shows what this workspace owns; a type whose parent lives elsewhere simply
  // surfaces as a root.
  const scopedSchemas = useMemo(
    () =>
      (schemas.data ?? []).filter(
        (s) =>
          (s.applies_to ?? "objects") === appliesTo &&
          (currentWorkspaceId === null || s.workspace_id === currentWorkspaceId),
      ),
    [schemas.data, appliesTo, currentWorkspaceId],
  );
  const tree = useMemo(() => buildTree(scopedSchemas), [scopedSchemas]);
  const visibleTree = useMemo(() => filterTree(tree, query), [tree, query]);
  const counts = useMemo(() => {
    const m = new Map<string, number>();
    if (appliesTo === "tickets") {
      for (const i of issues.data ?? []) {
        if (i.schema_uid) m.set(i.schema_uid, (m.get(i.schema_uid) ?? 0) + 1);
      }
    } else if (appliesTo === "documents") {
      for (const d of documents.data ?? []) {
        if (d.document_type_uid) m.set(d.document_type_uid, (m.get(d.document_type_uid) ?? 0) + 1);
      }
    } else {
      for (const a of assets.data ?? []) {
        m.set(a.schema_uid, (m.get(a.schema_uid) ?? 0) + 1);
      }
    }
    return m;
  }, [appliesTo, assets.data, issues.data, documents.data]);

  if (schemas.isLoading) {
    return <p className="px-2 py-1 text-xs text-slate-400">Loading schemas…</p>;
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={
          appliesTo === "tickets"
            ? "Search ticket types…"
            : appliesTo === "documents"
              ? "Search document types…"
              : "Search object types…"
        }
        className="mb-2 w-full shrink-0 rounded border border-slate-200 px-2 py-1 text-xs"
      />
      <div className="min-h-0 flex-1 overflow-y-auto">
        {visibleTree.map((node) => (
          <TreeNodeRow
            key={node.schema.uid}
            node={node}
            depth={0}
            counts={counts}
            selectedUid={selectedUid ?? null}
            onSelect={(uid) => navigate(`/schemas/${uid}`)}
            forceExpanded={query.length > 0}
          />
        ))}
      </div>
    </div>
  );
}
