import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { transfersApi } from "../api/client";
import { useCurrentWorkspaceId } from "../api/useCurrentWorkspaceId";
import type { TransferMode } from "../api/types";
import { WorkspaceTargetPicker } from "./WorkspaceTargetPicker";

type Kind = "asset_uids" | "document_uids" | "issue_uids";

/** A bulk "copy/move N selected to workspace…" bar — one action bar, reused
 * on every list page that supports selecting assets, documents or tickets,
 * mirroring the same-workspace bulk-move bar these pages already had. */
export function TransferSelectionBar({
  selected,
  kind,
  label,
  onStarted,
  onClear,
}: {
  selected: Set<string>;
  kind: Kind;
  label: string;
  onStarted: () => void;
  onClear: () => void;
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

  return (
    <div className="mt-3 flex h-12 flex-wrap items-center gap-3 rounded border border-slate-200 bg-white px-3">
      {selected.size === 0 ? (
        <span className="text-sm text-slate-400">
          Select {label} to copy or move them to another workspace.
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
          <button onClick={onClear} className="text-sm text-slate-500 hover:underline">
            Clear
          </button>
        </>
      )}
    </div>
  );
}
