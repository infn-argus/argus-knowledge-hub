import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { assetsApi, globalValuesApi, issuesApi, membersApi, schemasApi } from "../../api/client";
import { AttributeValue } from "../../components/AttributeValue";
import { effectiveAttributes } from "../../lib/schemaAttributes";

const STATE_STYLES: Record<string, string> = {
  new: "bg-slate-100 text-slate-600",
  in_progress: "bg-blue-100 text-blue-700",
  pending: "bg-amber-100 text-amber-700",
  resolved: "bg-green-100 text-green-700",
  closed: "bg-slate-200 text-slate-500",
};

const PRIORITY_STYLES: Record<string, string> = {
  blocker: "text-red-700",
  critical: "text-red-600",
  high: "text-orange-600",
  medium: "text-amber-600",
  low: "text-slate-500",
};

/** Fields the imported "Jira Issue" ticket type carries, grouped the way a
 * Jira issue view groups them — details on the left, people and dates on the
 * right — so a ticket imported from there reads the way it does at source. */
const DETAIL_KEYS = [
  "jira_issue_type",
  "jira_resolution",
  "jira_priority",
  "jira_affects_versions",
  "jira_fix_versions",
  "jira_components",
  "jira_environment",
  "jira_parent",
];
const PEOPLE_KEYS = ["jira_reporter", "jira_votes", "jira_watchers"];
const DATE_KEYS = ["jira_created", "jira_updated"];
const HIDDEN_KEYS = ["jira_key", "jira_url", "jira_project", "jira_status"];

function Panel({
  title,
  children,
  action,
}: {
  title: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5">
        <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
        {action}
      </div>
      <div className="px-4 py-3">{children}</div>
    </section>
  );
}

function FieldRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[minmax(7rem,auto)_1fr] gap-x-4 gap-y-1 py-1 text-sm">
      <dt className="text-slate-500">{label}</dt>
      <dd className="min-w-0 text-slate-900">{children}</dd>
    </div>
  );
}

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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issues", uid] });
      queryClient.invalidateQueries({ queryKey: ["issues"] });
    },
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
  const attr = (key: string) => i.attributes?.[key];
  const jiraKey = attr("jira_key") as string | undefined;
  const jiraUrl = attr("jira_url") as string | undefined;
  const jiraProject = attr("jira_project") as string | undefined;
  const jiraStatus = attr("jira_status") as string | undefined;

  // The fields come from the parent type ("Jira Issue"), not from the
  // child the ticket is an instance of ("Task") — saying otherwise sends
  // someone to the wrong type to edit them.
  const parentType = allSchemas.data?.find((s) => s.uid === schema.data?.parent_schema_uid);
  const byKey = new Map(attrDefs.map((a) => [a.key ?? a.name, a]));
  const renderAttr = (key: string) => {
    const def = byKey.get(key);
    if (!def) return null;
    const value = i.attributes?.[key];
    if (value == null || value === "" || (Array.isArray(value) && value.length === 0)) return null;
    return (
      <FieldRow key={key} label={def.name}>
        <AttributeValue
          attribute={def}
          value={value}
          assets={allAssets.data}
          members={members.data}
        />
      </FieldRow>
    );
  };

  // Anything the type defines that isn't placed by hand above — a field a
  // project added to its own Bug type, say — still has to appear somewhere.
  const placed = new Set([...DETAIL_KEYS, ...PEOPLE_KEYS, ...DATE_KEYS, ...HIDDEN_KEYS]);
  const otherAttrs = attrDefs.filter((a) => !placed.has(a.key ?? a.name));

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs text-slate-500">
            {jiraProject && <span>{jiraProject} / </span>}
            {jiraUrl && jiraKey ? (
              <a
                href={jiraUrl}
                target="_blank"
                rel="noreferrer"
                className="text-indigo-600 hover:underline"
              >
                {jiraKey}
              </a>
            ) : (
              jiraKey
            )}
          </p>
          <h1 className="mt-0.5 text-2xl font-semibold text-slate-900">{i.title}</h1>
        </div>

        <div className="flex shrink-0 items-center gap-2">
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
            {statusOptions.length > 0 ? (
              statusOptions.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.value}
                </option>
              ))
            ) : (
              <option value={i.state}>{i.state}</option>
            )}
          </select>
          <Link
            to={`/tickets/${i.uid}/edit`}
            className="rounded border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
          >
            Edit
          </Link>
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

      {jiraStatus && jiraStatus.toLowerCase() !== (currentStatus?.value ?? "").toLowerCase() && (
        <p className="mt-1 text-xs text-slate-400">
          Status in Jira: <span className="font-medium text-slate-500">{jiraStatus}</span>
        </p>
      )}
      {currentStatus?.meaning && (
        <p className="mt-1 text-xs text-slate-400">
          {currentStatus.meaning}
          {currentStatus.responsible && ` — responsible: ${currentStatus.responsible}`}
        </p>
      )}

      <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          <Panel title="Details">
            <dl>
              <FieldRow label="Priority">
                <span className={PRIORITY_STYLES[i.priority ?? ""] ?? "text-slate-900"}>
                  {priorityLabel ?? "—"}
                </span>
              </FieldRow>
              {DETAIL_KEYS.map(renderAttr)}
              {i.labels.length > 0 && (
                <FieldRow label="Labels">
                  <span className="flex flex-wrap gap-1">
                    {i.labels.map((l) => (
                      <span
                        key={l}
                        className="rounded bg-indigo-50 px-1.5 py-0.5 text-xs text-indigo-700"
                      >
                        {l}
                      </span>
                    ))}
                  </span>
                </FieldRow>
              )}
              {asset.data && (
                <FieldRow label="Object">
                  <Link to={`/assets/${asset.data.uid}`} className="text-indigo-600 hover:underline">
                    {asset.data.name}
                  </Link>
                </FieldRow>
              )}
              {otherAttrs.map((a) => renderAttr(a.key ?? a.name))}
              {parentType && (
                <p className="pt-1 text-[10px] uppercase tracking-wide text-slate-400">
                  Fields inherited from {parentType.name}
                </p>
              )}
            </dl>
          </Panel>

          <Panel title="Description">
            {i.description ? (
              <p className="whitespace-pre-wrap break-words text-sm text-slate-700">
                {i.description}
              </p>
            ) : (
              <p className="text-sm text-slate-400">No description.</p>
            )}
          </Panel>

          <Panel title={`Activity${comments.data?.length ? ` (${comments.data.length})` : ""}`}>
            <ul className="space-y-3">
              {comments.data?.map((c) => (
                <li key={c.uid} className="border-l-2 border-slate-100 pl-3">
                  <p className="whitespace-pre-wrap break-words text-sm text-slate-800">{c.body}</p>
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
              className="mt-4 space-y-2 border-t border-slate-100 pt-3"
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
          </Panel>
        </div>

        <div className="space-y-4">
          <Panel title="People">
            <dl>
              <FieldRow label="Assignee">
                <select
                  value={i.assignee ?? ""}
                  onChange={(e) =>
                    updateMutation.mutate({ assignee: e.target.value || null })
                  }
                  className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
                >
                  <option value="">Unassigned</option>
                  {/* An imported assignee is a Jira display name, not one of
                      our users; keep it selectable so saving doesn't silently
                      drop it. */}
                  {i.assignee && !assignedMember && (
                    <option value={i.assignee}>{i.assignee}</option>
                  )}
                  {members.data?.map((m) => (
                    <option key={m.user_id} value={m.user_id}>
                      {m.name || m.email}
                    </option>
                  ))}
                </select>
              </FieldRow>
              {PEOPLE_KEYS.map(renderAttr)}
              {i.created_by && <FieldRow label="Created by">{i.created_by}</FieldRow>}
            </dl>
          </Panel>

          <Panel title="Dates">
            <dl>
              {DATE_KEYS.map(renderAttr)}
              <FieldRow label="Imported">{new Date(i.created_at).toLocaleString()}</FieldRow>
              {i.due_date && (
                <FieldRow label="Due">{new Date(i.due_date).toLocaleDateString()}</FieldRow>
              )}
              {i.closed_at && (
                <FieldRow label="Resolved">{new Date(i.closed_at).toLocaleString()}</FieldRow>
              )}
            </dl>
          </Panel>

          {jiraUrl && (
            <a
              href={jiraUrl}
              target="_blank"
              rel="noreferrer"
              className="block rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm text-indigo-600 hover:bg-slate-50"
            >
              Open in Jira ↗
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
