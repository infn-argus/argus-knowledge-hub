import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { schemasApi, transfersApi } from "../../api/client";
import type { TransferMode } from "../../api/types";
import { useCurrentWorkspaceId } from "../../api/useCurrentWorkspaceId";
import { WorkspaceScopeBanner } from "../../components/WorkspaceScopeBanner";
import { WorkspaceTargetPicker } from "../../components/WorkspaceTargetPicker";

const GROUPS: ["objects" | "tickets" | "documents", string][] = [
  ["objects", "Object types"],
  ["tickets", "Ticket types"],
  ["documents", "Document types"],
];

/** Copy or move a whole type — and, optionally, every instance of it — into
 * another workspace. For individual objects, the bulk action bar on each
 * list page (Objects/Documents/Tickets) covers it instead. */
export function WorkspaceTransfer() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const navigate = useNavigate();
  const currentWorkspaceId = useCurrentWorkspaceId();
  const schemas = useQuery({ queryKey: ["schemas"], queryFn: schemasApi.list });

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [includeInstances, setIncludeInstances] = useState(true);
  const [target, setTarget] = useState("");
  const [mode, setMode] = useState<TransferMode>("copy");

  const toggle = (uid: string) =>
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(uid)) next.delete(uid);
      else next.add(uid);
      return next;
    });

  const transfer = useMutation({
    mutationFn: () =>
      transfersApi.create({
        target_workspace_id: target,
        mode,
        type_uids: [...selected],
        include_instances: includeInstances,
      }),
    onSuccess: (job) => navigate(`/workspaces/${workspaceId}/transfers/${job.uid}`),
    onError: (err) => alert(err instanceof Error ? err.message : "Could not start the transfer."),
  });

  // Only types actually owned here — an is_global type from elsewhere just
  // shows up as already usable, not as something to transfer.
  const own = (schemas.data ?? []).filter((s) => s.workspace_id === currentWorkspaceId);

  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Transfer to another workspace</h1>
        <Link to={`/workspaces/${workspaceId}/transfers`} className="text-sm text-slate-500 hover:underline">
          History
        </Link>
      </div>
      <p className="mt-1 max-w-2xl text-sm text-slate-500">
        Copy or move a type — and, if you like, every object of that type — into another
        workspace. A relation or link to something left behind is dropped, not migrated; the
        finished transfer reports how many.
      </p>
      <WorkspaceScopeBanner action="This transfers out of" />

      {schemas.isLoading && <p className="mt-4 text-sm text-slate-500">Loading…</p>}

      {schemas.data && own.length === 0 && (
        <p className="mt-4 text-sm text-slate-400">No types owned by this workspace yet.</p>
      )}

      {GROUPS.map(([appliesTo, label]) => {
        const group = own.filter((s) => s.applies_to === appliesTo);
        if (group.length === 0) return null;
        return (
          <section key={appliesTo} className="mt-6">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">{label}</h2>
            <div className="mt-2 space-y-1">
              {group.map((s) => (
                <label key={s.uid} className="flex items-center gap-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={selected.has(s.uid)}
                    onChange={() => toggle(s.uid)}
                  />
                  {s.name}
                </label>
              ))}
            </div>
          </section>
        );
      })}

      <div className="mt-6 flex flex-wrap items-center gap-3 rounded border border-slate-200 bg-white px-3 py-3">
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={includeInstances}
            onChange={(e) => setIncludeInstances(e.target.checked)}
          />
          Include every object of the selected type(s)
        </label>
        <span className="text-sm text-slate-300">|</span>
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value as TransferMode)}
          className="rounded border border-slate-300 px-2 py-1 text-sm"
        >
          <option value="copy">Copy</option>
          <option value="move">Move</option>
        </select>
        <span className="text-sm text-slate-400">to</span>
        <WorkspaceTargetPicker excludeWorkspaceId={currentWorkspaceId} value={target} onChange={setTarget} />
        <button
          onClick={() => transfer.mutate()}
          disabled={selected.size === 0 || !target || transfer.isPending}
          className="ml-auto rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {transfer.isPending ? "Starting…" : mode === "copy" ? "Copy" : "Move"}
        </button>
      </div>
    </div>
  );
}
