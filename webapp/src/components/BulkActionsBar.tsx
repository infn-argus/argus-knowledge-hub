import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { transfersApi } from "../api/client";
import { useCurrentWorkspaceId } from "../api/useCurrentWorkspaceId";
import type { BulkDeleteResult, TransferMode } from "../api/types";
import { WorkspaceTargetPicker } from "./WorkspaceTargetPicker";

type Kind = "asset_uids" | "document_uids" | "issue_uids";

/** A bulk action bar — "copy/move N selected to workspace…" plus, where a
 * `bulkDelete` call is given, "Delete N selected". One bar, reused on every
 * list page that supports selecting assets, documents or tickets. */
export function BulkActionsBar({
  selected,
  kind,
  label,
  onStarted,
  onClear,
  bulkDelete,
}: {
  selected: Set<string>;
  kind: Kind;
  label: string;
  onStarted: () => void;
  onClear: () => void;
  /** Enables the Delete button when given. Called with the selected uids;
   * onStarted() runs afterward the same way it does for copy/move. */
  bulkDelete?: (uids: string[]) => Promise<BulkDeleteResult>;
}) {
  const navigate = useNavigate();
  const workspaceId = useCurrentWorkspaceId();
  const [target, setTarget] = useState("");
  const [mode, setMode] = useState<TransferMode>("copy");

  const transfer = useMutation({
    mutationFn: () =>
      transfersApi.create({ target_workspace_id: target, mode, [kind]: [...selected] }),
    onSuccess: (job) => {
      onStarted();
      if (workspaceId) navigate(`/workspaces/${workspaceId}/transfers/${job.uid}`);
    },
    onError: (err) => alert(err instanceof Error ? err.message : "Could not start the transfer."),
  });

  const deleteMutation = useMutation({
    mutationFn: () => bulkDelete!([...selected]),
    onSuccess: (result) => {
      onStarted();
      if (result.not_found.length) {
        alert(`Deleted ${result.deleted}. ${result.not_found.length} could not be found.`);
      }
    },
    onError: () => alert(`Could not delete those ${label}.`),
  });

  return (
    <div className="mt-3 flex h-12 flex-wrap items-center gap-3 rounded border border-slate-200 bg-white px-3">
      {selected.size === 0 ? (
        <span className="text-sm text-slate-400">
          Select {label} to copy, move or delete them.
        </span>
      ) : (
        <>
          <span className="text-sm text-slate-600">{selected.size} selected</span>
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value as TransferMode)}
            className="rounded border border-slate-300 px-2 py-1 text-sm"
          >
            <option value="copy">Copy</option>
            <option value="move">Move</option>
          </select>
          <span className="text-sm text-slate-400">to</span>
          <WorkspaceTargetPicker excludeWorkspaceId={workspaceId} value={target} onChange={setTarget} />
          <button
            onClick={() => transfer.mutate()}
            disabled={!target || transfer.isPending}
            className="rounded bg-slate-900 px-3 py-1 text-sm text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {transfer.isPending ? "Starting…" : mode === "copy" ? "Copy" : "Move"}
          </button>
          {bulkDelete && (
            <>
              <span className="text-sm text-slate-300">|</span>
              <button
                onClick={() => {
                  if (confirm(`Delete ${selected.size} ${label}? This cannot be undone.`)) {
                    deleteMutation.mutate();
                  }
                }}
                disabled={deleteMutation.isPending}
                className="rounded border border-red-200 px-3 py-1 text-sm text-red-600 hover:bg-red-50 disabled:opacity-50"
              >
                {deleteMutation.isPending ? "Deleting…" : "Delete"}
              </button>
            </>
          )}
          <button onClick={onClear} className="text-sm text-slate-500 hover:underline">
            Clear
          </button>
        </>
      )}
    </div>
  );
}
