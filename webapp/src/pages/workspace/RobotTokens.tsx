import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { apiBaseUrl, schemasApi, tokensApi } from "../../api/client";
import { ROBOT_PRESETS, TokenForm, TokenTable } from "../../components/ApiTokens";

/** Tokens for machines that work for this workspace: a facility's daily-logbook uploader, a script, an
 * instrument. They belong to the workspace, not to a person, so they keep working when people change. */
export function RobotTokensPage() {
  const { workspaceId = "" } = useParams<{ workspaceId: string }>();
  const queryClient = useQueryClient();
  const tokens = useQuery({ queryKey: ["robot-tokens", workspaceId], queryFn: () => tokensApi.robots(workspaceId) });
  const types = useQuery({ queryKey: ["schemas"], queryFn: schemasApi.list });
  const base = useQuery({ queryKey: ["api-base-url"], queryFn: apiBaseUrl });
  const logbook = (types.data ?? []).find((s) => s.applies_to === "documents" && /logbook/i.test(s.name));
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["robot-tokens", workspaceId] });
  const api = base.data || "https://<argus-api>";

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Robot tokens</h1>
        <p className="mt-1 text-sm text-slate-500">
          For machines that work for this workspace — a control room's daily-logbook uploader, a data feed, an
          instrument. A robot token belongs to the workspace, not to a person, does only what is ticked, and is
          named in the history as <code>robot:&lt;name&gt;</code>. It needs no <code>X-Workspace-Id</code>.
          Give each machine its own token, so one can be revoked without stopping the others.
        </p>
      </div>
      {tokens.isError ? (
        <p className="text-sm text-red-600">Only the workspace's owners manage its robot tokens.</p>
      ) : (
        <>
          <TokenForm kind="robot" presets={ROBOT_PRESETS} allowAdmin
                     onCreate={async (input) => { const t = await tokensApi.makeRobot(workspaceId, input); refresh(); return t; }} />
          <TokenTable tokens={tokens.data ?? []} onRevoke={(t) => void tokensApi.revokeRobot(workspaceId, t.id).then(refresh)} />
        </>
      )}
      <details className="rounded border border-slate-200 bg-white p-4 text-sm">
        <summary className="cursor-pointer font-medium text-slate-900">Example: upload a daily logbook</summary>
        <p className="mt-2 text-slate-600">With a <i>Daily logbook upload</i> token (read, create and modify
          documents), a scheduled job creates the day's entry and attaches the file:</p>
        <pre className="mt-2 overflow-x-auto rounded bg-slate-50 p-3 text-xs">{`export ARGUS_TOKEN=argus_bot_…        # stored in the job's secret store
DAY=$(date +%F)
ENTRY="logbook-${workspaceId}-$DAY"

# 1. The day's entry (a Logbook Entry document, as a draft revision)
curl -sf -X POST ${api}/v1/documents \\
  -H "Authorization: Bearer $ARGUS_TOKEN" -H "Content-Type: application/json" \\
  -d "$(jq -n --arg uid "$ENTRY" --arg title "Logbook $DAY" --rawfile body summary.md \\
        '{uid: $uid, title: $title, ${logbook ? `document_type_uid: "${logbook.uid}", ` : ""}body_markdown: $body}')"

# 2. The full logbook file, on the entry's first revision
curl -sf -X POST ${api}/v1/documents/$ENTRY/revisions/$ENTRY-r1/attachments \\
  -H "Authorization: Bearer $ARGUS_TOKEN" -F "file=@logbook-$DAY.pdf"`}</pre>
        <p className="mt-2 text-xs text-slate-500">
          {logbook ? <>This workspace's logbook type is <code>{logbook.uid}</code> ({logbook.name}).</>
            : <>This workspace has no Logbook Entry type yet: leave <code>document_type_uid</code> out, or add the
              type on the document types page.</>}{" "}
          Re-running the same day answers 409 (already there): safe to retry. The full API is described at{" "}
          <code>{api}/docs</code>.
        </p>
      </details>
    </div>
  );
}
