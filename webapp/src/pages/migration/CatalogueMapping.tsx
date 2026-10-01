import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { catalogueMappingApi, workspacesApi } from "../../api/client";
import { useCurrentWorkspaceId } from "../../api/useCurrentWorkspaceId";

const KINDS = {
  catalogue: {
    label: "Product models & vendors",
    hint:
      "An import's product models (its \"… Models\" types) become Product Models with their Vendors, row by " +
      "row: names cleaned, duplicates merged. They are created shared, for every workspace's equipment to point at.",
    into: "Into (the workspace that keeps the catalogue)",
  },
  records: {
    label: "Records → a workspace's types",
    hint:
      "Anything else an import holds — equipment, locations, racks — becomes records of the target's own and " +
      "shared types. You check a plan per imported type: its target type, where each field goes, what its links " +
      "become, and whether its records are shared.",
    into: "Into (target workspace)",
  },
} as const;

/** Start a mapping: which imported types, into which workspace. */
export function CatalogueMappingPage() {
  const navigate = useNavigate();
  const currentWorkspaceId = useCurrentWorkspaceId();
  const workspaces = useQuery({ queryKey: ["my-workspaces"], queryFn: workspacesApi.listMine });
  const [kind, setKind] = useState<"catalogue" | "records">("records");
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [useAi, setUseAi] = useState(true);

  useEffect(() => {
    if (!source && currentWorkspaceId) setSource(currentWorkspaceId);
  }, [currentWorkspaceId, source]);

  const sources = useQuery({
    queryKey: ["mapping-sources", source, kind, target],
    queryFn: () => catalogueMappingApi.sources(source, kind, target || undefined),
    enabled: !!source,
  });
  // The "… Models" types are what this is for: chosen until the person says otherwise.
  useEffect(() => {
    if (sources.data) setSelected(new Set(sources.data.filter((s) => s.suggested && s.open > 0).map((s) => s.uid)));
  }, [sources.data]);

  const mappings = useQuery({ queryKey: ["catalogue-mappings"], queryFn: catalogueMappingApi.list });

  const start = useMutation({
    mutationFn: () =>
      catalogueMappingApi.start({
        kind,
        source_workspace_id: source,
        target_workspace_id: target,
        type_uids: [...selected],
        use_ai: useAi,
      }),
    onSuccess: (m) => navigate(`/migration/catalogue/${m.id}`),
  });

  const toggle = (uid: string) =>
    setSelected((cur) => {
      const next = new Set(cur);
      if (next.has(uid)) next.delete(uid);
      else next.add(uid);
      return next;
    });

  const rows = sources.data ?? [];
  const suggested = rows.filter((s) => s.suggested);
  const others = rows.filter((s) => !s.suggested);
  const openSelected = rows.filter((s) => selected.has(s.uid)).reduce((n, s) => n + s.open, 0);

  const typeRow = (s: (typeof rows)[number]) => (
    <label key={s.uid} className="flex items-center gap-2 py-1 text-sm">
      <input type="checkbox" checked={selected.has(s.uid)} disabled={s.open === 0} onChange={() => toggle(s.uid)} />
      <span className={s.open === 0 ? "text-slate-400" : "text-slate-800"}>{s.name}</span>
      <span className="ml-auto tabular-nums text-xs text-slate-500">
        {s.open} open{s.mapped > 0 && <span className="text-emerald-600"> · {s.mapped} mapped</span>}
      </span>
    </label>
  );

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-semibold text-slate-900">Map imported records</h1>
      <p className="mt-1 text-sm text-slate-500">
        Bring what an import brought in its own shape into a workspace's types. Rules propose what they can, the AI
        what they cannot, and you review before anything is created. Attachments, avatar, history, comments and
        ticket links come along; old keys keep working. The imported records are never changed, and rows you skip
        stay open for another time.
      </p>

      <div className="mt-5 grid gap-2 sm:grid-cols-2">
        {(Object.keys(KINDS) as (keyof typeof KINDS)[]).map((k) => (
          <button
            key={k}
            type="button"
            onClick={() => setKind(k)}
            className={`rounded-lg border p-3 text-left ${
              kind === k ? "border-slate-900 bg-white ring-1 ring-slate-900" : "border-slate-200 bg-white hover:border-slate-400"
            }`}
          >
            <span className="block text-sm font-medium text-slate-900">{KINDS[k].label}</span>
            <span className="mt-0.5 block text-xs text-slate-500">{KINDS[k].hint}</span>
          </button>
        ))}
      </div>

      <div className="mt-6 grid gap-4 rounded-lg border border-slate-200 bg-white p-4 sm:grid-cols-2">
        <label className="text-sm">
          <span className="block font-medium text-slate-700">From (imported workspace)</span>
          <select
            value={source}
            onChange={(e) => setSource(e.target.value)}
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
          >
            <option value="">Choose…</option>
            {(workspaces.data ?? []).map((w) => (
              <option key={w.id} value={w.id}>
                {w.name} ({w.id})
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="block font-medium text-slate-700">{KINDS[kind].into}</span>
          <select
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
          >
            <option value="">Choose…</option>
            {(workspaces.data ?? [])
              .filter((w) => w.id !== source)
              .map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name} ({w.id})
                </option>
              ))}
          </select>
        </label>
      </div>

      {source && (
        <div className="mt-4 rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-900">Which records</h2>
          {sources.isLoading && <p className="mt-2 text-sm text-slate-500">Loading…</p>}
          {sources.isError && <p className="mt-2 text-sm text-red-600">{(sources.error as Error).message}</p>}
          {suggested.length > 0 && (
            <div className="mt-2">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                {kind === "catalogue" ? "Model types" : "Record types"}
              </p>
              <div className="mt-1 grid gap-x-6 sm:grid-cols-2">{suggested.map(typeRow)}</div>
            </div>
          )}
          {others.length > 0 && (
            <details className="mt-3">
              <summary className="cursor-pointer text-xs font-medium uppercase tracking-wide text-slate-400">
                Other types ({others.length})
              </summary>
              <div className="mt-1 grid gap-x-6 sm:grid-cols-2">{others.map(typeRow)}</div>
            </details>
          )}
          <div className="mt-4 flex flex-wrap items-center gap-4 border-t border-slate-100 pt-3">
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={useAi} onChange={(e) => setUseAi(e.target.checked)} />
              Use the AI for what the rules cannot decide
            </label>
            <button
              onClick={() => start.mutate()}
              disabled={!target || selected.size === 0 || start.isPending}
              className="ml-auto rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
            >
              {start.isPending ? "Starting…" : `Propose ${openSelected} records`}
            </button>
          </div>
          {start.isError && <p className="mt-2 text-sm text-red-600">{(start.error as Error).message}</p>}
        </div>
      )}

      <h2 className="mt-8 text-sm font-semibold text-slate-900">Mappings</h2>
      <div className="mt-2 overflow-hidden rounded-lg border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-3 py-2">Started</th>
              <th className="px-3 py-2">From → into</th>
              <th className="px-3 py-2">Rows</th>
              <th className="px-3 py-2">By</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {(mappings.data ?? []).map((m) => (
              <tr key={m.id}>
                <td className="px-3 py-2">
                  <Link to={`/migration/catalogue/${m.id}`} className="text-indigo-600 hover:underline">
                    {new Date(m.created_at).toLocaleString()}
                  </Link>
                </td>
                <td className="px-3 py-2 font-mono text-xs">
                  {m.source_workspace_id} → {m.target_workspace_id}
                  <span className="ml-2 font-sans text-slate-400">
                    {m.kind === "records" ? "records" : "product models & vendors"}
                  </span>
                </td>
                <td className="px-3 py-2 text-xs text-slate-600">
                  {m.state === "ready"
                    ? `${m.counts.applied ?? 0} applied · ${m.counts.accepted ?? 0} accepted · ${
                        (m.counts.proposed ?? 0) + (m.counts.skipped ?? 0)
                      } open`
                    : m.state}
                </td>
                <td className="px-3 py-2 text-xs text-slate-500">{m.actor}</td>
              </tr>
            ))}
            {mappings.data?.length === 0 && (
              <tr>
                <td colSpan={4} className="px-3 py-4 text-center text-slate-400">
                  None yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
