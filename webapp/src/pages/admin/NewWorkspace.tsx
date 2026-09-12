import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, workspacesApi } from "../../api/client";

export function NewWorkspace() {
  const navigate = useNavigate();
  const [id, setId] = useState("");
  const [name, setName] = useState("");

  const createMutation = useMutation({
    mutationFn: () => workspacesApi.create(id.trim(), name.trim()),
    onSuccess: (ws) => navigate(`/workspaces/${ws.id}/members`),
  });

  return (
    <div className="max-w-lg">
      <h1 className="text-2xl font-semibold text-slate-900">New workspace</h1>
      <p className="mt-1 text-sm text-slate-500">
        Admin only. You'll automatically get full rights on the new workspace.
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          createMutation.mutate();
        }}
        className="mt-6 space-y-5"
      >
        <div>
          <label className="block text-sm font-medium text-slate-700">Workspace id</label>
          <input
            value={id}
            onChange={(e) => setId(e.target.value)}
            placeholder="e.g. lnf-accelerator"
            required
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
          />
          <p className="mt-1 text-xs text-slate-400">
            Used in PAT tokens and URLs — pick something stable, it can't be changed later.
          </p>
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700">Name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
          />
        </div>

        {createMutation.isError && (
          <p className="text-sm text-red-600">
            {createMutation.error instanceof ApiError
              ? JSON.stringify(createMutation.error.body)
              : "Failed to create workspace"}
          </p>
        )}

        <button
          type="submit"
          disabled={createMutation.isPending}
          className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {createMutation.isPending ? "Creating…" : "Create workspace"}
        </button>
      </form>
    </div>
  );
}
