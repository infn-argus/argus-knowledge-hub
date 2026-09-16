import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { transfersApi } from "../../api/client";

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-slate-100 text-slate-600",
  running: "bg-blue-100 text-blue-700",
  succeeded: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
};

export function TransferList() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const { data, isLoading } = useQuery({
    queryKey: ["transfers"],
    queryFn: () => transfersApi.list(),
    refetchInterval: (query) =>
      query.state.data?.some((j) => j.status === "pending" || j.status === "running") ? 2000 : false,
  });

  if (!workspaceId) return null;

  return (
    <div>
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Transfer history</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-500">
            Every copy/move out of this workspace, most recent first.
          </p>
        </div>
        <Link
          to={`/workspaces/${workspaceId}/transfer`}
          className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          New transfer
        </Link>
      </div>

      {isLoading && <p className="mt-4 text-sm text-slate-500">Loading…</p>}
      {data && data.length === 0 && <p className="mt-4 text-sm text-slate-500">No transfers yet.</p>}

      {data && data.length > 0 && (
        <div className="mt-4 overflow-hidden rounded-lg border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-2">Mode</th>
                <th className="px-4 py-2">To workspace</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Progress</th>
                <th className="px-4 py-2">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.map((job) => (
                <tr key={job.uid} className="hover:bg-slate-50">
                  <td className="px-4 py-2">
                    <Link
                      to={`/workspaces/${workspaceId}/transfers/${job.uid}`}
                      className="font-medium text-slate-900 hover:underline"
                    >
                      {job.mode === "copy" ? "Copy" : "Move"}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-slate-600">{job.target_workspace_id}</td>
                  <td className="px-4 py-2">
                    <span className={`rounded px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[job.status] ?? ""}`}>
                      {job.status}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-slate-600">{job.progress ?? "—"}</td>
                  <td className="px-4 py-2 text-slate-500">{new Date(job.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
