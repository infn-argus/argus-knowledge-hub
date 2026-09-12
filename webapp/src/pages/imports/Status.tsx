import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { importsApi } from "../../api/client";

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-slate-100 text-slate-600",
  running: "bg-blue-100 text-blue-700",
  succeeded: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
};

export function ImportStatus() {
  const { uid } = useParams<{ uid: string }>();

  const { data, isLoading } = useQuery({
    queryKey: ["imports", uid],
    queryFn: () => importsApi.get(uid!),
    refetchInterval: (query) =>
      query.state.data && (query.state.data.status === "pending" || query.state.data.status === "running")
        ? 1500
        : false,
  });

  return (
    <div className="max-w-2xl">
      <Link to="/imports" className="text-sm text-slate-500 hover:underline">
        &larr; Imports
      </Link>

      {isLoading && <p className="mt-4 text-sm text-slate-500">Loading…</p>}

      {data && (
        <div className="mt-3">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold text-slate-900">
              {data.source === "jira" ? "Jira import" : "Git import"}
            </h1>
            <span
              className={`rounded px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[data.status] ?? ""}`}
            >
              {data.status}
            </span>
          </div>

          <div className="mt-6 rounded-lg border border-slate-200 bg-white p-5">
            <dl className="grid grid-cols-2 gap-y-3 text-sm">
              <dt className="text-slate-500">Progress</dt>
              <dd className="text-slate-900">{data.progress ?? "—"}</dd>

              <dt className="text-slate-500">Schemas</dt>
              <dd className="text-slate-900">{data.counts.schemas ?? 0}</dd>

              <dt className="text-slate-500">Assets</dt>
              <dd className="text-slate-900">{data.counts.assets ?? 0}</dd>

              <dt className="text-slate-500">Relations</dt>
              <dd className="text-slate-900">{data.counts.relations ?? 0}</dd>

              {data.counts.errors !== undefined && (
                <>
                  <dt className="text-slate-500">Errors</dt>
                  <dd className="text-slate-900">{data.counts.errors}</dd>
                </>
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
                {data.warnings.length} constraint warning{data.warnings.length === 1 ? "" : "s"}
              </p>
              <p className="mt-1 text-xs text-amber-700">
                These objects were imported anyway — their values just don't meet a
                unique/cardinality/regex rule configured on their type.
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

          {data.status === "succeeded" && (
            <p className="mt-4 text-sm text-slate-500">
              Imported types now appear in the Object types tree on the left.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
