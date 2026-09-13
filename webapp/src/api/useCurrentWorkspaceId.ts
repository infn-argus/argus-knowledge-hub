import { useQuery } from "@tanstack/react-query";
import { workspacesApi } from "./client";
import { getActiveProfile } from "./session";

/** The workspace the app is currently acting as: a signed-in identity can span
 * several and carries the choice on its profile, while a PAT is fixed to the
 * one it was minted for. Null while /v1/me is still in flight. */
export function useCurrentWorkspaceId(): string | null {
  const profile = getActiveProfile();
  const me = useQuery({ queryKey: ["me"], queryFn: workspacesApi.me });
  const id =
    profile?.authType === "oidc" ? profile.activeWorkspaceId : me.data?.workspace_id;
  return id ?? null;
}
