import { useQuery } from "@tanstack/react-query";
import { workspacesApi } from "../api/client";
import { useCurrentWorkspaceId } from "../api/useCurrentWorkspaceId";

/** Which workspace an operation is about to change.
 *
 * The switcher in the sidebar says which workspace you are in; it does not
 * say that the thing in front of you writes into it. Somebody imported one
 * beamline's control configuration into another beamline's workspace, ran
 * it, and had no way afterwards to see where the 587 objects had gone —
 * every screen looked the same in both.
 */
export function WorkspaceScopeBanner({ action }: { action: string }) {
  const workspaceId = useCurrentWorkspaceId();
  const mine = useQuery({ queryKey: ["my-workspaces"], queryFn: workspacesApi.listMine });

  if (!workspaceId) return null;
  const workspace = mine.data?.find((w) => w.id === workspaceId);

  return (
    <div className="mt-4 flex flex-wrap items-baseline gap-x-2 gap-y-1 rounded border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-900">
      <span>{action}</span>
      <span className="font-semibold">{workspace?.name ?? workspaceId}</span>
      <code className="rounded bg-sky-100 px-1.5 py-0.5 text-xs">{workspaceId}</code>
      {mine.data && mine.data.length > 1 && (
        <span className="text-xs text-sky-800">
          — switch workspace in the sidebar if that is not the right one.
        </span>
      )}
    </div>
  );
}
