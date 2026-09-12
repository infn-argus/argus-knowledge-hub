import { useMemo, useState } from "react";
import { AppSchema } from "../api/types";

function buildPath(schema: AppSchema, byUid: Map<string, AppSchema>): string {
  const parts: string[] = [schema.name];
  let current = schema;
  const seen = new Set([schema.uid]);
  while (current.parent_schema_uid) {
    const parent = byUid.get(current.parent_schema_uid);
    if (!parent || seen.has(parent.uid)) break;
    parts.unshift(parent.name);
    seen.add(parent.uid);
    current = parent;
  }
  return parts.join(" / ");
}

/** Search-as-you-type schema picker showing each match's full hierarchy path
 * (and workspace, when it differs from the caller's) so same-named types in
 * different subtrees or different (global) workspaces stay distinguishable. */
export function SchemaPicker({
  schemas,
  value,
  onChange,
  currentWorkspaceId,
  placeholder = "Search types…",
}: {
  schemas: AppSchema[];
  value?: string | null;
  onChange: (uid: string, schema: AppSchema | undefined) => void;
  currentWorkspaceId?: string | null;
  placeholder?: string;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);

  const byUid = useMemo(() => new Map(schemas.map((s) => [s.uid, s])), [schemas]);
  const selected = value ? byUid.get(value) : undefined;

  const withPath = useMemo(
    () => schemas.map((s) => ({ schema: s, path: buildPath(s, byUid) })),
    [schemas, byUid],
  );

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = q
      ? withPath.filter((w) => w.path.toLowerCase().includes(q))
      : withPath;
    return [...filtered].sort((a, b) => a.path.localeCompare(b.path)).slice(0, 30);
  }, [withPath, query]);

  return (
    <div className="relative flex-1">
      <div className="flex items-center gap-1">
        <input
          value={open ? query : selected ? buildPath(selected, byUid) : ""}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => {
            setQuery("");
            setOpen(true);
          }}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          placeholder={placeholder}
          className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
        />
        {selected && (
          <button
            type="button"
            onMouseDown={(e) => {
              e.preventDefault();
              onChange("", undefined);
            }}
            title="Clear"
            className="text-xs text-slate-400 hover:text-slate-700"
          >
            ×
          </button>
        )}
      </div>
      {open && (
        <div className="absolute z-10 mt-1 max-h-56 w-full min-w-[16rem] overflow-y-auto rounded border border-slate-200 bg-white shadow-lg">
          {matches.map(({ schema, path }) => (
            <button
              type="button"
              key={schema.uid}
              onMouseDown={(e) => {
                e.preventDefault();
                onChange(schema.uid, schema);
                setQuery("");
                setOpen(false);
              }}
              className="block w-full px-2 py-1.5 text-left text-sm hover:bg-slate-50"
            >
              <span className="text-slate-900">{path}</span>
              {schema.is_global && (
                <span className="ml-1.5 rounded bg-amber-50 px-1 py-0.5 text-[10px] font-medium text-amber-700">
                  global
                </span>
              )}
              {currentWorkspaceId && schema.workspace_id !== currentWorkspaceId && (
                <span className="ml-1.5 rounded bg-slate-100 px-1 py-0.5 text-[10px] text-slate-500">
                  ws {schema.workspace_id.slice(0, 8)}
                </span>
              )}
            </button>
          ))}
          {matches.length === 0 && (
            <p className="px-2 py-1.5 text-sm text-slate-400">No matching types.</p>
          )}
        </div>
      )}
    </div>
  );
}
