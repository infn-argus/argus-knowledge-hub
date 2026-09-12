import { useEffect, useState } from "react";
import { workspacesApi } from "../api/client";
import { MyWorkspace } from "../api/types";
import { clearSession, Profile, updateProfile } from "../api/session";
import { firebaseSignOut } from "../api/firebase";

export function WorkspacePicker({
  profile,
  onPicked,
}: {
  profile: Profile;
  onPicked: () => void;
}) {
  const [workspaces, setWorkspaces] = useState<MyWorkspace[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    workspacesApi
      .listMine()
      .then((ws) => {
        setWorkspaces(ws);
        if (ws.length === 1) {
          updateProfile(profile.id, { activeWorkspaceId: ws[0].id });
          onPicked();
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, [profile.id, onPicked]);

  const signOutAndRetry = async () => {
    await firebaseSignOut().catch(() => {});
    clearSession();
    window.location.reload();
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <div className="w-full max-w-md space-y-4 rounded-lg border border-slate-200 bg-white p-8 shadow-sm">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Choose a workspace</h1>
          <p className="mt-1 text-sm text-slate-500">Signed in as {profile.name}.</p>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}
        {!error && workspaces === null && (
          <p className="text-sm text-slate-500">Loading…</p>
        )}
        {workspaces?.length === 0 && (
          <p className="text-sm text-slate-500">
            You don't have access to any workspace yet — ask an admin to add{" "}
            {profile.name} to one.
          </p>
        )}
        {workspaces && workspaces.length > 0 && (
          <div className="space-y-2">
            {workspaces.map((ws) => (
              <button
                key={ws.id}
                onClick={() => {
                  updateProfile(profile.id, { activeWorkspaceId: ws.id });
                  onPicked();
                }}
                className="block w-full rounded border border-slate-200 px-4 py-2 text-left text-sm hover:border-slate-400 hover:bg-slate-50"
              >
                {ws.name}
              </button>
            ))}
          </div>
        )}

        {(error || workspaces?.length === 0) && (
          <button
            onClick={signOutAndRetry}
            className="text-sm text-slate-500 underline hover:text-slate-700"
          >
            Sign out and try a different account
          </button>
        )}
      </div>
    </div>
  );
}
