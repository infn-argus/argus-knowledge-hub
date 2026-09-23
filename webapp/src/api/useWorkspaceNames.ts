import { useQuery } from "@tanstack/react-query";
import { workspacesApi } from "./client";

/** Workspace id → display name, for the workspaces this identity can reach.
 * A shared object can belong to one it cannot, in which case the id is all
 * there is to show, and callers fall back to it. */
export function useWorkspaceNames(): (id: string) => string {
  const mine = useQuery({ queryKey: ["my-workspaces"], queryFn: workspacesApi.listMine, staleTime: 60_000 });
  const names = new Map((mine.data ?? []).map((w) => [w.id, w.name]));
  return (id) => names.get(id) ?? id;
}
