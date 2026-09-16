import { useQuery } from "@tanstack/react-query";
import { workspacesApi } from "../api/client";

/** Pick some *other* workspace as the destination of a copy/move — unlike
 * the sidebar switcher or WorkspacePicker, this never changes the session's
 * own current workspace, it just produces a value. */
export function WorkspaceTargetPicker({
  excludeWorkspaceId,
  value,
  onChange,
}: {
  excludeWorkspaceId: string | null;
  value: string;
  onChange: (workspaceId: string) => void;
}) {
  const mine = useQuery({ queryKey: ["my-workspaces"], queryFn: workspacesApi.listMine });
  const options = (mine.data ?? []).filter((w) => w.id !== excludeWorkspaceId);

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="rounded border border-slate-300 px-2 py-1 text-sm"
    >
      <option value="">Choose a workspace…</option>
      {options.map((w) => (
        <option key={w.id} value={w.id}>
          {w.name} ({w.id})
        </option>
      ))}
    </select>
  );
}
