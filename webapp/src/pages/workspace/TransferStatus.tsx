import { useQuery } from "@tanstack/react-query";
import { Fragment } from "react";
import { Link, useParams } from "react-router-dom";
import { transfersApi } from "../../api/client";

const COUNTS: [string, string][] = [
  ["types", "Types"],
  ["assets", "Objects"],
  ["documents", "Documents"],
  ["issues", "Tickets"],
  ["relations_copied", "Relations copied"],
  ["relations_dropped", "Relations dropped"],
  ["links_dropped", "Ticket/document links dropped"],
];

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-slate-100 text-slate-600",
  running: "bg-blue-100 text-blue-700",
  succeeded: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
};

export function TransferStatus() {
  const { uid, workspaceId } = useParams<{ uid: string; workspaceId: string }>();

  const { data, isLoading } = useQuery({
    queryKey: ["transfers", uid],
    queryFn: () => transfersApi.get(uid!),
    refetchInterval: (query) =>
      query.state.data && (query.state.data.status === "pending" || query.state.data.status === "running")
        ? 1500
        : false,
  });

  return (
    <div className="max-w-2xl">
      <Link to={`/workspaces/${workspaceId}/transfer`} className="text-sm text-slate-500 hover:underline">
        &larr; Transfer
      </Link>

      {isLoading && <p className="mt-4 text-sm text-slate-500">Loading…</p>}

      {data && (
        <div className="mt-3">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold text-slate-900">
              {data.mode === "copy" ? "Copy" : "Move"}
            </h1>
            <span className={`rounded px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[data.status] ?? ""}`}>
              {data.status}
            </span>
          </div>

          <div className="mt-6 rounded-lg border border-slate-200 bg-white p-5">
            <dl className="grid grid-cols-2 gap-y-3 text-sm">
              <dt className="text-slate-500">From workspace</dt>
              <dd className="font-medium text-slate-900">{data.workspace_id}</dd>

              <dt className="text-slate-500">To workspace</dt>
              <dd className="font-medium text-slate-900">{data.target_workspace_id}</dd>

              <dt className="text-slate-500">Progress</dt>
              <dd className="text-slate-900">{data.progress ?? "—"}</dd>

              {COUNTS.map(([key, label]) =>
                data.counts[key] !== undefined ? (
                  <Fragment key={key}>
                    <dt className="text-slate-500">{label}</dt>
                    <dd className="text-slate-900">{data.counts[key]}</dd>
                  </Fragment>
                ) : null,
              )}

              <dt className="text-slate-500">Started</dt>
              <dd className="text-slate-900">
                {data.started_at ? new Date(data.started_at).toLocaleString() : "—"}
              </dd>

              <dt className="text-slate-500">Completed</dt>
              <dd className="text-slate-900">
                {data.completed_at ? new Date(data.completed_at).toLocaleString() : "—"}
              </dd>
            </dl>

            {data.error && (
              <div className="mt-4 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {data.error}
              </div>
            )}
          </div>

          {data.warnings.length > 0 && (
            <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4">
              <p className="text-sm font-medium text-amber-800">
                {data.warnings.length} note{data.warnings.length === 1 ? "" : "s"}
              </p>
              <ul className="mt-2 max-h-64 space-y-1 overflow-y-auto text-xs text-amber-900">
                {data.warnings.map((w, i) => (
                  <li key={i} className="border-t border-amber-100 pt-1 first:border-t-0 first:pt-0">
                    {w}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
