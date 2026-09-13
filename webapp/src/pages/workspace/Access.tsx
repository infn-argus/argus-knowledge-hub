import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, directoryApi, membersApi, rolesApi } from "../../api/client";
import { Role } from "../../api/types";

const RESOURCE_LABELS: [string, string][] = [
  ["objects", "Objects & types"],
  ["tickets", "Tickets"],
  ["documents", "Documents"],
  ["workspace", "Workspace"],
];

function PermissionSummary({ role }: { role: Role }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
      {RESOURCE_LABELS.map(([key, label]) => {
        const actions = role.permissions[key];
        if (!actions?.length) return null;
        return (
          <span key={key}>
            <span className="text-slate-400">{label}:</span> {actions.join(", ")}
          </span>
        );
      })}
    </div>
  );
}

export function WorkspaceAccess() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const queryClient = useQueryClient();
  const [subjectType, setSubjectType] = useState<"user" | "group">("group");
  const [subjectId, setSubjectId] = useState("");
  const [roleId, setRoleId] = useState("viewer");
  const [showRoles, setShowRoles] = useState(false);

  const bindings = useQuery({
    queryKey: ["bindings", workspaceId],
    queryFn: () => rolesApi.listBindings(workspaceId!),
    enabled: !!workspaceId,
    retry: false, // a 403 here is permanent, not transient
  });
  const roles = useQuery({ queryKey: ["roles"], queryFn: rolesApi.list });
  const groups = useQuery({ queryKey: ["groups"], queryFn: () => directoryApi.groups() });
  const directory = useQuery({ queryKey: ["directory-status"], queryFn: directoryApi.status });
  const people = useQuery({
    queryKey: ["member-directory", workspaceId],
    queryFn: membersApi.directory,
  });

  const createMutation = useMutation({
    mutationFn: () =>
      rolesApi.createBinding(workspaceId!, { subject_type: subjectType, subject_id: subjectId, role_id: roleId }),
    onSuccess: () => {
      setSubjectId("");
      queryClient.invalidateQueries({ queryKey: ["bindings", workspaceId] });
      queryClient.invalidateQueries({ queryKey: ["member-directory", workspaceId] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (bindingId: number) => rolesApi.deleteBinding(workspaceId!, bindingId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["bindings", workspaceId] });
      queryClient.invalidateQueries({ queryKey: ["member-directory", workspaceId] });
    },
  });

  const syncMutation = useMutation({
    mutationFn: directoryApi.sync,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["groups"] });
      queryClient.invalidateQueries({ queryKey: ["directory-status"] });
    },
  });

  if (bindings.isError) {
    const forbidden = bindings.error instanceof ApiError && bindings.error.status === 403;
    return (
      <p className="text-sm text-red-600">
        {forbidden
          ? "You don't have permission to manage access to this workspace."
          : "Failed to load access."}
      </p>
    );
  }

  const subjectOptions =
    subjectType === "group"
      ? (groups.data ?? []).filter((g) => g.active).map((g) => ({
          id: g.uid,
          label: `${g.name}${g.member_count ? ` · ${g.member_count} member${g.member_count === 1 ? "" : "s"}` : " · empty"}`,
        }))
      : (people.data ?? []).map((p) => ({ id: p.user_id, label: p.name || p.email }));

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-900">Access</h1>
      <p className="mt-1 text-sm text-slate-500">
        Grant a role to a person or to a whole group. Granting a group is how a service gets
        access in one go — anyone who joins it later inherits the same rights.{" "}
        <Link to={`/workspaces/${workspaceId}/members`} className="text-indigo-600 hover:underline">
          Older per-person permissions
        </Link>{" "}
        still apply and are managed separately.
      </p>

      {directory.data?.is_test_data && (
        <div className="mt-4 rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <strong>Built-in test directory.</strong> No LDAP is configured, so the people and groups
          below are fictional examples ({directory.data.active_groups} groups,{" "}
          {directory.data.users} people) meant for trying things out. Granting them access is safe
          but meaningless — they can't sign in.
        </div>
      )}

      <div className="mt-6 rounded-lg border border-slate-200 bg-white">
        <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          <h2 className="text-sm font-semibold text-slate-900">Granted roles</h2>
          <button
            onClick={() => setShowRoles((v) => !v)}
            className="text-xs text-indigo-600 hover:text-indigo-800"
          >
            {showRoles ? "Hide" : "What do the roles mean?"}
          </button>
        </div>

        {showRoles && (
          <div className="space-y-2 border-b border-slate-100 bg-slate-50 px-4 py-3">
            {roles.data?.map((role) => (
              <div key={role.id}>
                <p className="text-sm font-medium text-slate-900">
                  {role.name}
                  <span className="ml-2 font-normal text-slate-500">{role.description}</span>
                </p>
                <PermissionSummary role={role} />
              </div>
            ))}
          </div>
        )}

        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-2">Who</th>
              <th className="px-4 py-2">Type</th>
              <th className="px-4 py-2">Role</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {bindings.data?.map((b) => (
              <tr key={b.id} className="hover:bg-slate-50">
                <td className="px-4 py-2 font-medium text-slate-900">
                  {b.subject_label}
                  {!b.subject_active && (
                    <span className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500">
                      inactive
                    </span>
                  )}
                </td>
                <td className="px-4 py-2 text-slate-500">{b.subject_type}</td>
                <td className="px-4 py-2 text-slate-700">{b.role_name}</td>
                <td className="px-4 py-2 text-right">
                  <button
                    onClick={() => {
                      if (confirm(`Remove ${b.role_name} from ${b.subject_label}?`)) {
                        deleteMutation.mutate(b.id);
                      }
                    }}
                    className="text-xs text-red-500 hover:text-red-700"
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
            {bindings.data?.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-slate-400">
                  No roles granted yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>

        {deleteMutation.isError && (
          <p className="border-t border-slate-100 px-4 py-2 text-sm text-red-600">
            {(deleteMutation.error as ApiError)?.detail ?? "Could not remove that role."}
          </p>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (subjectId) createMutation.mutate();
          }}
          className="flex flex-wrap items-center gap-2 border-t border-slate-100 px-4 py-3"
        >
          <select
            value={subjectType}
            onChange={(e) => {
              setSubjectType(e.target.value as "user" | "group");
              setSubjectId("");
            }}
            className="rounded border border-slate-300 px-2 py-1.5 text-sm"
          >
            <option value="group">Group</option>
            <option value="user">Person</option>
          </select>
          <select
            value={subjectId}
            onChange={(e) => setSubjectId(e.target.value)}
            required
            className="min-w-64 flex-1 rounded border border-slate-300 px-2 py-1.5 text-sm"
          >
            <option value="">
              {subjectType === "group" ? "Choose a group…" : "Choose a person…"}
            </option>
            {subjectOptions.map((o) => (
              <option key={o.id} value={o.id}>
                {o.label}
              </option>
            ))}
          </select>
          <select
            value={roleId}
            onChange={(e) => setRoleId(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1.5 text-sm"
          >
            {roles.data?.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
          <button
            type="submit"
            disabled={createMutation.isPending || !subjectId}
            className="rounded bg-slate-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            Grant
          </button>
        </form>
        {createMutation.isError && (
          <p className="px-4 pb-3 text-sm text-red-600">
            {(createMutation.error as ApiError)?.detail ?? "Could not grant that role."}
          </p>
        )}
        {subjectType === "group" && subjectOptions.length === 0 && (
          <p className="px-4 pb-3 text-sm text-slate-500">
            No groups yet — run a directory sync below.
          </p>
        )}
      </div>

      <div className="mt-6 rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold text-slate-900">Directory</h2>
            <p className="mt-1 text-sm text-slate-500">
              Source: <span className="font-medium text-slate-700">{directory.data?.provider ?? "…"}</span>
              {" · "}
              {directory.data?.active_groups ?? 0} groups, {directory.data?.users ?? 0} people
              {directory.data?.last_synced_at && (
                <> · last synced {new Date(directory.data.last_synced_at).toLocaleString()}</>
              )}
            </p>
          </div>
          <button
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
            className="shrink-0 rounded border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            {syncMutation.isPending ? "Syncing…" : "Sync now"}
          </button>
        </div>
        {syncMutation.isError && (
          <p className="mt-2 text-sm text-red-600">
            {(syncMutation.error as ApiError)?.status === 403
              ? "Only an instance admin can run a directory sync."
              : ((syncMutation.error as ApiError)?.detail ?? "Sync failed.")}
          </p>
        )}
        {syncMutation.isSuccess && (
          <p className="mt-2 text-sm text-green-700">
            Synced. {String(syncMutation.data.groups_created ?? 0)} groups added,{" "}
            {String(syncMutation.data.users_created ?? 0)} people added,{" "}
            {String(syncMutation.data.users_deactivated ?? 0)} deactivated.
          </p>
        )}

        {(groups.data?.length ?? 0) > 0 && (
          <table className="mt-4 w-full text-sm">
            <thead className="text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="py-1">Group</th>
                <th className="py-1">Source</th>
                <th className="py-1 text-right">Members</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {groups.data?.map((g) => (
                <tr key={g.uid}>
                  <td className="py-1.5">
                    <span className="text-slate-900">{g.name}</span>
                    {g.description && (
                      <span className="ml-2 text-xs text-slate-400">{g.description}</span>
                    )}
                  </td>
                  <td className="py-1.5 text-slate-500">{g.source}</td>
                  <td className="py-1.5 text-right tabular-nums text-slate-500">
                    {g.member_count}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
