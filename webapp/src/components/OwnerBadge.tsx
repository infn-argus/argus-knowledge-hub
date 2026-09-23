import { useCurrentWorkspaceId } from "../api/useCurrentWorkspaceId";
import { useWorkspaceNames } from "../api/useWorkspaceNames";

/** Says whose an object is when it is not this workspace's: everything of a
 * shared type is visible everywhere, and without this a row from another
 * workspace looks exactly like one of your own — including the fact that it
 * can only be edited where it lives. Renders nothing for your own. */
export function OwnerBadge({ workspaceId }: { workspaceId: string }) {
  const current = useCurrentWorkspaceId();
  const nameOf = useWorkspaceNames();
  if (current === null || workspaceId === current) return null;
  return (
    <span
      title={`Owned by ${nameOf(workspaceId)}, and shared with this workspace. It can be edited only there.`}
      className="ml-2 rounded bg-sky-50 px-1.5 py-0.5 text-[11px] font-medium text-sky-700"
    >
      {nameOf(workspaceId)}
    </span>
  );
}
