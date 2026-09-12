import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, workspacesApi } from "../../api/client";
import { getActiveProfile } from "../../api/session";

export function AdminUsers() {
  const queryClient = useQueryClient();
  const profile = getActiveProfile();
  const selfUserId = profile?.authType === "oidc" ? profile.id : null;

  const users = useQuery({
    queryKey: ["admin-users"],
    queryFn: workspacesApi.listUsers,
    retry: false, // a 403 here is permanent, not transient — retrying just delays the message
  });

  const setAdminMutation = useMutation({
    mutationFn: ({ userId, isAdmin }: { userId: string; isAdmin: boolean }) =>
      workspacesApi.setUserAdmin(userId, isAdmin),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  if (users.isError) {
    const forbidden = users.error instanceof ApiError && users.error.status === 403;
    return (
      <p className="text-sm text-red-600">
        {forbidden ? "Admins only." : "Failed to load users."}
      </p>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-900">Users</h1>
      <p className="mt-1 text-sm text-slate-500">
        Everyone who has signed in at least once. Admins have full rights on every workspace.
      </p>

      {users.isLoading && <p className="mt-4 text-sm text-slate-500">Loading…</p>}

      {users.data && (
        <div className="mt-4 overflow-hidden rounded-lg border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-2">Email</th>
                <th className="px-4 py-2">Name</th>
                <th className="px-4 py-2">Last login</th>
                <th className="px-4 py-2 text-center">Admin</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {users.data.map((u) => (
                <tr key={u.id}>
                  <td className="px-4 py-2 font-medium text-slate-900">{u.email}</td>
                  <td className="px-4 py-2 text-slate-500">{u.name ?? "—"}</td>
                  <td className="px-4 py-2 text-slate-500">
                    {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "—"}
                  </td>
                  <td className="px-4 py-2 text-center">
                    <input
                      type="checkbox"
                      checked={u.is_admin}
                      disabled={u.id === selfUserId}
                      title={u.id === selfUserId ? "You can't remove your own admin rights here" : undefined}
                      onChange={(e) =>
                        setAdminMutation.mutate({ userId: u.id, isAdmin: e.target.checked })
                      }
                    />
                  </td>
                </tr>
              ))}
              {users.data.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-slate-400">
                    No users yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
