import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { transfersApi } from "../api/client";
import { useCurrentWorkspaceId } from "../api/useCurrentWorkspaceId";
import type { TransferMode } from "../api/types";
import { WorkspaceTargetPicker } from "./WorkspaceTargetPicker";

type ItemKind = "asset" | "document" | "issue" | "type";

const FIELD: Record<ItemKind, "asset_uids" | "document_uids" | "issue_uids" | "type_uids"> = {
  asset: "asset_uids",
  document: "document_uids",
  issue: "issue_uids",
  type: "type_uids",
};

/** A "Copy to workspace…" / "Move to workspace…" popover for a single item
 * on its own detail page — the one-at-a-time counterpart to BulkActionsBar's
 * multi-select version on list pages. For a type, also offers whether to
 * bring its instances and/or its child types along. */
export function TransferItemAction({
  kind,
  uid,
  hasChildren,
  buttonClassName,
}: {
  kind: ItemKind;
  uid: string;
  /** Only meaningful for kind="type" — shows the include-descendants toggle. */
  hasChildren?: boolean;
  buttonClassName?: string;
}) {
  const [open, setOpen] = useState(false);
  const [target, setTarget] = useState("");
  const [mode, setMode] = useState<TransferMode>("copy");
  const [includeInstances, setIncludeInstances] = useState(true);
  const [includeDescendantTypes, setIncludeDescendantTypes] = useState(false);
  const navigate = useNavigate();
  const workspaceId = useCurrentWorkspaceId();

  const transfer = useMutation({
    mutationFn: () =>
      transfersApi.create({
        target_workspace_id: target,
        mode,
        [FIELD[kind]]: [uid],
        ...(kind === "type"
          ? { include_instances: includeInstances, include_descendant_types: includeDescendantTypes }
          : {}),
      }),
    onSuccess: (job) => {
      setOpen(false);
      if (workspaceId) navigate(`/workspaces/${workspaceId}/transfers/${job.uid}`);
    },
    onError: (err) => alert(err instanceof Error ? err.message : "Could not start the transfer."),
  });

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={
          buttonClassName ?? "rounded border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
        }
      >
        Copy/Move…
      </button>
      {open && (
        <div className="absolute right-0 z-10 mt-2 w-72 rounded-lg border border-slate-200 bg-white p-3 shadow-lg">
          <div className="flex items-center gap-2">
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as TransferMode)}
              className="rounded border border-slate-300 px-2 py-1 text-sm"
            >
              <option value="copy">Copy</option>
              <option value="move">Move</option>
            </select>
            <span className="text-sm text-slate-400">to</span>
          </div>
          <div className="mt-2">
            <WorkspaceTargetPicker excludeWorkspaceId={workspaceId} value={target} onChange={setTarget} />
          </div>
          {kind === "type" && (
            <div className="mt-2 space-y-1">
              <label className="flex items-center gap-2 text-xs text-slate-600">
                <input
                  type="checkbox"
                  checked={includeInstances}
                  onChange={(e) => setIncludeInstances(e.target.checked)}
                />
                Include its objects/documents/tickets
              </label>
              {hasChildren && (
                <label className="flex items-center gap-2 text-xs text-slate-600">
                  <input
                    type="checkbox"
                    checked={includeDescendantTypes}
                    onChange={(e) => setIncludeDescendantTypes(e.target.checked)}
                  />
                  Include its child type(s)
                </label>
              )}
            </div>
          )}
          <div className="mt-3 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="text-sm text-slate-500 hover:underline"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => transfer.mutate()}
              disabled={!target || transfer.isPending}
              className="rounded bg-slate-900 px-3 py-1 text-sm text-white hover:bg-slate-800 disabled:opacity-50"
            >
              {transfer.isPending ? "Starting…" : mode === "copy" ? "Copy" : "Move"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
