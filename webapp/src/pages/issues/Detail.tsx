import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { assetsApi, globalValuesApi, issuesApi, membersApi, schemasApi } from "../../api/client";
import { AttributeValue } from "../../components/AttributeValue";
import { effectiveAttributes, inheritedKeys } from "../../lib/schemaAttributes";

const STATE_STYLES: Record<string, string> = {
  new: "bg-slate-100 text-slate-600",
  in_progress: "bg-blue-100 text-blue-700",
  pending: "bg-amber-100 text-amber-700",
  resolved: "bg-green-100 text-green-700",
  closed: "bg-slate-200 text-slate-500",
};

export function IssueDetail() {
  const { uid } = useParams<{ uid: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [commentAuthor, setCommentAuthor] = useState("web-user");
  const [commentBody, setCommentBody] = useState("");

  const issue = useQuery({
    queryKey: ["issues", uid],
    queryFn: () => issuesApi.get(uid!),
    enabled: !!uid,
  });
  const comments = useQuery({
    queryKey: ["issue-comments", uid],
    queryFn: () => issuesApi.listComments(uid!),
    enabled: !!uid,
  });
  const asset = useQuery({
    queryKey: ["assets", issue.data?.asset_uid],
    queryFn: () => assetsApi.get(issue.data!.asset_uid!),
    enabled: !!issue.data?.asset_uid,
  });
  const schema = useQuery({
    queryKey: ["schemas", issue.data?.schema_uid],
    queryFn: () => schemasApi.get(issue.data!.schema_uid!),
    enabled: !!issue.data?.schema_uid,
  });
  const allSchemas = useQuery({ queryKey: ["schemas"], queryFn: schemasApi.list });
  const attrDefs = effectiveAttributes(schema.data, allSchemas.data);
  const inherited = inheritedKeys(schema.data, attrDefs);
  const allAssets = useQuery({
    queryKey: ["assets"],
    queryFn: () => assetsApi.list(),
    enabled: attrDefs.some((a) => a.type === "reference"),
  });
  const members = useQuery({ queryKey: ["members"], queryFn: membersApi.directory });
  const globalValues = useQuery({ queryKey: ["global-values"], queryFn: globalValuesApi.list });
  const ticketGlobals = globalValues.data?.filter((gv) => gv.applies_to === "tickets") ?? [];
  const statusOptions = ticketGlobals.find((gv) => gv.key === "status")?.options ?? [];
  const priorityOptions = ticketGlobals.find((gv) => gv.key === "priority")?.options ?? [];

  const updateMutation = useMutation({
    mutationFn: (patch: { state?: string; priority?: string; assignee?: string | null }) =>
      issuesApi.update(uid!, patch),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["issues", uid] }),
  });
  const addCommentMutation = useMutation({
    mutationFn: () => issuesApi.addComment(uid!, commentAuthor, commentBody),
    onSuccess: () => {
      setCommentBody("");
      queryClient.invalidateQueries({ queryKey: ["issue-comments", uid] });
    },
  });
  const deleteMutation = useMutation({
    mutationFn: () => issuesApi.delete(uid!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issues"] });
      navigate("/tickets");
    },
  });

  if (issue.isLoading) return <p className="text-sm text-slate-500">Loading…</p>;
  if (!issue.data) return <p className="text-sm text-red-600">Ticket not found.</p>;

  const i = issue.data;
  const currentStatus = statusOptions.find((o) => o.id === i.state);
  const assignedMember = members.data?.find((m) => m.user_id === i.assignee);
  const priorityLabel = priorityOptions.find((o) => o.id === i.priority)?.value ?? i.priority;

  return (
    <div className="max-w-2xl">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">{i.title}</h1>
          <p className="mt-1 text-sm text-slate-500">
            {i.priority && <span>Priority: {priorityLabel} · </span>}
            {i.assignee && (
              <span>Assignee: {assignedMember?.name || assignedMember?.email || i.assignee} · </span>
            )}
            Created {new Date(i.created_at).toLocaleString()}
          </p>
          {asset.data && (
            <p className="mt-1 text-sm text-slate-500">
              Linked asset:{" "}
              <Link to={`/assets/${asset.data.uid}`} className="hover:underline">
                {asset.data.name}
              </Link>
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <select
            value={i.state}
            onChange={(e) => updateMutation.mutate({ state: e.target.value })}
            title={
              currentStatus
                ? `${currentStatus.responsible ? `Responsible: ${currentStatus.responsible}. ` : ""}${currentStatus.meaning ?? ""}`
                : undefined
            }
            className={`rounded border-0 px-2 py-1 text-xs font-medium ${STATE_STYLES[i.state] ?? "bg-slate-100 text-slate-600"}`}
          >
            {statusOptions.length > 0
              ? statusOptions.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.value}
                  </option>
                ))
              : (
                <option value={i.state}>{i.state}</option>
              )}
          </select>
          <button
            onClick={() => {
              if (confirm("Delete this ticket?")) deleteMutation.mutate();
            }}
            className="rounded border border-red-200 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50"
          >
            Delete
          </button>
        </div>
      </div>
      {currentStatus?.meaning && (
        <p className="mt-1 text-xs text-slate-400">
          {currentStatus.meaning}
          {currentStatus.responsible && ` — responsible: ${currentStatus.responsible}`}
        </p>
      )}

      {i.description && (
        <p className="mt-4 whitespace-pre-wrap rounded border border-slate-200 bg-white p-4 text-sm text-slate-700">
          {i.description}
        </p>
      )}

      {schema.data && attrDefs.length > 0 && (
        <div className="mt-4 rounded border border-slate-200 bg-white p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            {schema.data.name}
          </p>
          <dl className="mt-2 space-y-1.5 text-sm">
            {attrDefs.map((attr) => (
              <div key={attr.id ?? attr.name} className="flex justify-between gap-4">
                <dt className="text-slate-500">
                  {attr.name}
                  {inherited.has(attr.key ?? attr.name) && (
                    <span className="ml-1 text-[10px] uppercase tracking-wide text-slate-400">
                      inherited
                    </span>
                  )}
                </dt>
                <dd className="text-right text-slate-900">
                  <AttributeValue
                    attribute={attr}
                    value={i.attributes[attr.key ?? attr.name]}
                    assets={allAssets.data}
                    members={members.data}
                  />
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      <h2 className="mt-8 text-lg font-semibold text-slate-900">Comments</h2>
      <ul className="mt-3 space-y-3">
        {comments.data?.map((c) => (
          <li key={c.uid} className="rounded border border-slate-200 bg-white p-3 text-sm">
            <p className="text-slate-900">{c.body}</p>
            <p className="mt-1 text-xs text-slate-400">
              {c.author} · {new Date(c.created_at).toLocaleString()}
            </p>
          </li>
        ))}
        {comments.data?.length === 0 && (
          <p className="text-sm text-slate-400">No comments yet.</p>
        )}
      </ul>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (commentBody.trim()) addCommentMutation.mutate();
        }}
        className="mt-4 space-y-2"
      >
        <input
          value={commentAuthor}
          onChange={(e) => setCommentAuthor(e.target.value)}
          className="w-full rounded border border-slate-300 px-2 py-1 text-xs"
          placeholder="Your name"
        />
        <textarea
          value={commentBody}
          onChange={(e) => setCommentBody(e.target.value)}
          rows={3}
          className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
          placeholder="Add a comment…"
        />
        <button
          type="submit"
          className="rounded bg-slate-900 px-4 py-2 text-sm text-white hover:bg-slate-800"
        >
          Comment
        </button>
      </form>
    </div>
  );
}
