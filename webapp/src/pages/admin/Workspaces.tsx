import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, workspacesApi } from "../../api/client";

export function AdminWorkspaces() {
  const queryClient = useQueryClient();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState("");

  const workspaces = useQuery({
    queryKey: ["me-workspaces"],
    queryFn: workspacesApi.listMine,
    retry: false,
  });

  const renameMutation = useMutation({
    mutationFn: (vars: { id: string; name: string }) => workspacesApi.update(vars.id, { name: vars.name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["me-workspaces"] });
      setEditingId(null);
    },
    onError: () => alert("Rename failed."),
  });

  const toggleGlobalMutation = useMutation({
    mutationFn: (vars: { id: string; is_global: boolean }) =>
      workspacesApi.update(vars.id, { is_global: vars.is_global }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["me-workspaces"] }),
    onError: () => alert("Failed to update global flag."),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => workspacesApi.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["me-workspaces"] }),
    onError: () => alert("Delete failed."),
  });

  if (workspaces.isError) {
    const forbidden = workspaces.error instanceof ApiError && workspaces.error.status === 403;
    return (
      <p className="text-sm text-red-600">
        {forbidden ? "Admins only." : "Failed to load workspaces."}
      </p>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Workspaces</h1>
          <p className="mt-1 text-sm text-slate-500">
            Every workspace on this instance. Deleting one permanently removes everything in it.
          </p>
        </div>
        <Link
          to="/admin/new-workspace"
          className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          New workspace
        </Link>
      </div>

      {workspaces.isLoading && <p className="mt-4 text-sm text-slate-500">Loading…</p>}

      {workspaces.data && (
        <div className="mt-4 overflow-hidden rounded-lg border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-2">Id</th>
                <th className="px-4 py-2">Name</th>
                <th className="px-4 py-2">Global</th>
                <th className="px-4 py-2">Created</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {workspaces.data.map((ws) => (
                <tr key={ws.id}>
                  <td className="px-4 py-2 font-mono text-xs text-slate-500">{ws.id}</td>
                  <td className="px-4 py-2 font-medium text-slate-900">
                    {editingId === ws.id ? (
                      <input
                        autoFocus
                        value={editingName}
                        onChange={(e) => setEditingName(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" && editingName.trim()) {
                            renameMutation.mutate({ id: ws.id, name: editingName.trim() });
                          }
                          if (e.key === "Escape") setEditingId(null);
                        }}
                        className="rounded border border-slate-300 px-2 py-1 text-sm"
                      />
                    ) : (
                      ws.name
                    )}
                  </td>
                  <td className="px-4 py-2">
                    <label className="inline-flex items-center gap-1.5 text-xs text-slate-600">
                      <input
                        type="checkbox"
                        checked={ws.is_global}
                        disabled={toggleGlobalMutation.isPending}
                        onChange={(e) => {
                          const next = e.target.checked;
                          if (
                            !next ||
                            confirm(
                              `Make every schema in "${ws.name}" global? This makes every object type (and its objects) in this workspace visible and referenceable from every other workspace.`,
                            )
                          ) {
                            toggleGlobalMutation.mutate({ id: ws.id, is_global: next });
                          }
                        }}
                      />
                      Global
                    </label>
                  </td>
                  <td className="px-4 py-2 text-slate-500">
                    {new Date(ws.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-2 text-right">
                    {editingId === ws.id ? (
                      <>
                        <button
                          onClick={() =>
                            editingName.trim() &&
                            renameMutation.mutate({ id: ws.id, name: editingName.trim() })
                          }
                          disabled={renameMutation.isPending}
                          className="mr-3 text-slate-700 hover:underline"
                        >
                          Save
                        </button>
                        <button
                          onClick={() => setEditingId(null)}
                          className="mr-3 text-slate-500 hover:underline"
                        >
                          Cancel
                        </button>
                      </>
                    ) : (
                      <>
                        <Link
                          to={`/workspaces/${ws.id}/members`}
                          className="mr-3 text-slate-500 hover:text-slate-900"
                        >
                          Members
                        </Link>
                        <Link
                          to={`/workspaces/${ws.id}/integrity`}
                          className="mr-3 text-slate-500 hover:text-slate-900"
                        >
                          Integrity
                        </Link>
                        <Link
                          to={`/workspaces/${ws.id}/transfer`}
                          className="mr-3 text-slate-500 hover:text-slate-900"
                        >
                          Transfer
                        </Link>
                        <button
                          onClick={() => {
                            setEditingId(ws.id);
                            setEditingName(ws.name);
                          }}
                          className="mr-3 text-slate-500 hover:text-slate-900"
                        >
                          Rename
                        </button>
                        <button
                          onClick={() => {
                            if (
                              confirm(
                                `Delete workspace "${ws.name}"? This permanently deletes every schema, object, ticket, label, global value and import in it. This cannot be undone.`,
                              )
                            ) {
                              deleteMutation.mutate(ws.id);
                            }
                          }}
                          className="text-red-500 hover:text-red-700"
                        >
                          Delete
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
              {workspaces.data.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
                    No workspaces yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
