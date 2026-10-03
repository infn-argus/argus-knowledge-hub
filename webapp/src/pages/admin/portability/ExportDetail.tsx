import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { portabilityApi, problemText, workspacesApi } from "../../../api/client";
import type { Dependency, ExportView } from "../../../api/portabilityTypes";
import { ActionButton, bytes, Empty, ErrorBox, EXPORT_STEPS, KV, Labels, Mono, Section, StateBadge, Steps, when } from "./shared";

const OUTCOME_HELP: Record<string, string> = {
  include_workspace: "add that workspace to the export",
  external_reference: "keep the reference as a uid; the importer resolves it or decides",
  exclude_referrers: "leave out the rows that name restricted records",
  block: "do not run this export",
};

export function ExportDetailPage() {
  const { id = "" } = useParams();
  const qc = useQueryClient();
  const me = useQuery({ queryKey: ["me"], queryFn: workspacesApi.me });
  const exp = useQuery({ queryKey: ["portability-export", id], queryFn: () => portabilityApi.getExport(id) });
  const generated = !!exp.data?.manifest_sha256;
  const manifest = useQuery({ queryKey: ["portability-manifest", id], queryFn: () => portabilityApi.manifest(id),
                              enabled: generated });
  const [error, setError] = useState<string | null>(null);
  const done = (e: ExportView) => {
    qc.setQueryData(["portability-export", id], e);
    void qc.invalidateQueries({ queryKey: ["portability-exports"] });
    void qc.invalidateQueries({ queryKey: ["portability-manifest", id] });
    setError(null);
  };
  const fail = (e: unknown) => {
    setError(problemText(e));
    void qc.invalidateQueries({ queryKey: ["portability-export", id] });
  };
  const step = useMutation({ mutationFn: (s: "approve" | "generate" | "publish-git") => portabilityApi.exportStep(id, s),
                             onSuccess: done, onError: fail });
  const [reason, setReason] = useState("");
  const revoke = useMutation({ mutationFn: () => portabilityApi.revokeExport(id, reason), onSuccess: done, onError: fail });
  const download = useMutation({ mutationFn: () => portabilityApi.downloadUrl(id),
                                 onSuccess: (url) => { window.location.href = url; }, onError: fail });

  if (exp.isError) return <p className="text-sm text-rose-700">{problemText(exp.error)}</p>;
  if (!exp.data) return <p className="text-sm text-slate-500">Loading…</p>;
  const e = exp.data;
  const myEmail = me.data?.email;
  const selfApproval = e.risk === "high" && myEmail === e.requested_by;
  const busy = step.isPending ? step.variables : null;

  return (
    <div className="max-w-6xl space-y-4">
      <Link to="/admin/portability?tab=exports" className="text-xs text-slate-500 hover:text-slate-700">&larr; Portability</Link>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-mono text-lg font-semibold text-slate-900">{e.id}</h1>
          <p className="text-sm text-slate-600">
            {e.mode === "full" ? "Every workspace" : e.workspaces.join(", ")} · {e.mode}
            {e.risk === "high" && <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-900">high risk</span>}
          </p>
          <div className="mt-2"><Labels labels={e.labels} /></div>
        </div>
        <StateBadge state={e.state} />
      </div>
      <Steps steps={EXPORT_STEPS} state={e.state} />
      <ErrorBox error={error ?? (e.state === "failed" ? e.error : null)} />

      <Section title="Next step">
        <div className="flex flex-wrap items-center gap-3">
          {e.state === "awaiting_approval" && (
            <>
              <ActionButton label="Approve" busy={busy === "approve"} onClick={() => step.mutate("approve")}
                            disabled={!e.analysis.ready || selfApproval}
                            title={selfApproval ? "A high-risk export needs another approver" : undefined}
                            confirm={`Approve this ${e.risk === "high" ? "high-risk " : ""}export?`} />
              {!e.analysis.ready && <span className="text-sm text-amber-800">Give every dependency an outcome first.</span>}
              {selfApproval && <span className="text-sm text-amber-800">You requested it: another administrator must approve.</span>}
            </>
          )}
          {e.state === "approved" && (
            <ActionButton label="Generate" busy={busy === "generate"} onClick={() => step.mutate("generate")} />
          )}
          {e.state === "ready_to_publish" && (
            <>
              <ActionButton label="Publish to Git" busy={busy === "publish-git"} onClick={() => step.mutate("publish-git")}
                            disabled={!e.destination.repository}
                            confirm={`Commit and tag this checkpoint in ${e.destination.repository}? A published tag cannot be withdrawn from history.`} />
              {!e.destination.repository && <span className="text-sm text-slate-500">No repository was chosen: download it instead.</span>}
            </>
          )}
          {(e.state === "ready_to_publish" || e.state === "published") && (
            <button type="button" onClick={() => download.mutate()} disabled={download.isPending}
                    className="rounded border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50">
              {download.isPending ? "Preparing…" : "Download checkpoint (.tar)"}
            </button>
          )}
          {e.state === "published" && <span className="text-sm text-emerald-700">Published. Import it elsewhere by its tag.</span>}
          {(e.state === "revoked" || e.state === "expired") && <span className="text-sm text-slate-500">This export is {e.state}.</span>}
          {!["revoked", "expired", "generating", "verifying", "publishing"].includes(e.state) && (
            <span className="ml-auto flex items-center gap-2">
              <input value={reason} onChange={(ev) => setReason(ev.target.value)} placeholder="Reason to revoke"
                     className="w-48 rounded border border-slate-300 px-2 py-1 text-sm" />
              <ActionButton label="Revoke" danger disabled={!reason.trim()} busy={revoke.isPending}
                            onClick={() => revoke.mutate()} confirm="Revoke this export?" />
            </span>
          )}
        </div>
      </Section>

      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Request">
          <KV rows={[
            ["Requested by", e.requested_by], ["Approved by", e.approved_by ?? "—"], ["Created", when(e.created_at)],
            ["Repository", e.destination.repository ?? "none"], ["Artifact store", e.destination.artifact_store ?? "none"],
            ["Restricted classes included", e.classifications.length ? e.classifications.join(", ") : "none"],
            ["Base export", e.base_export_id ? <Link className="text-indigo-700 hover:underline" to={`/admin/portability/exports/${e.base_export_id}`}>{e.base_export_id}</Link> : undefined],
          ]} />
        </Section>
        <Section title="Estimate and warnings">
          {e.analysis.estimate ? (
            <KV rows={[
              ["Records", e.analysis.estimate.records], ["Tickets", e.analysis.estimate.tickets],
              ["Ledger claim events", e.analysis.estimate.claim_events],
              ["Attachments", `${e.analysis.estimate.attachments} (${bytes(e.analysis.estimate.attachment_bytes)}, outside Git)`],
              ["Workspaces after closure", e.analysis.closure?.workspaces?.join(", ")],
            ]} />
          ) : <Empty>Not analysed yet.</Empty>}
          {(e.analysis.warnings ?? []).length > 0 && (
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-amber-800">
              {e.analysis.warnings!.map((w) => <li key={w}>{w}</li>)}
            </ul>
          )}
        </Section>
      </div>

      <Dependencies e={e} onSaved={done} onError={fail} />

      {e.watermark && (
        <Section title="Watermark">
          <KV rows={[["Label", e.watermark.label], ["Taken at", when(e.watermark.snapshot_at)],
                     ["Per table", <span className="font-mono text-xs">{Object.entries(e.watermark.tables).map(([t, n]) => `${t.replace("ledger_", "")} ${n}`).join(" · ")}</span>]]} />
        </Section>
      )}

      {e.git.tag && (
        <Section title="Git">
          <KV rows={[["Repository", e.git.repository], ["Tag", <Mono>{e.git.tag}</Mono>], ["Commit", <Mono>{e.git.commit}</Mono>],
                     ["Parent", <Mono short>{e.git.parent}</Mono>], ["Previous export tag", e.git.previous_tag ? <Mono>{e.git.previous_tag}</Mono> : undefined],
                     ["Repository identity", <Mono>{e.git.repository_id}</Mono>]]} />
        </Section>
      )}

      {manifest.data && <ManifestView m={manifest.data.manifest} sha={manifest.data.sha256} />}
    </div>
  );
}

function Dependencies({ e, onSaved, onError }: { e: ExportView; onSaved: (v: ExportView) => void; onError: (x: unknown) => void }) {
  const deps: Dependency[] = e.analysis.closure?.dependencies ?? [];
  const editable = e.state === "awaiting_approval" || e.state === "failed";
  const [draft, setDraft] = useState<Record<string, string>>({});
  useEffect(() => setDraft({}), [e.id, e.state]);
  const save = useMutation({ mutationFn: () => portabilityApi.decideExport(e.id, draft), onSuccess: onSaved, onError });
  return (
    <Section title="Dependencies"
             right={editable && Object.keys(draft).length > 0 && (
               <button type="button" onClick={() => save.mutate()} disabled={save.isPending}
                       className="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white">
                 {save.isPending ? "Analysing…" : "Save outcomes and analyse again"}
               </button>)}>
      {deps.length === 0 ? <Empty>Nothing outside the scope is referenced.</Empty> : (
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-500">
            <tr><th className="py-1">Dependency</th><th>References</th><th>Examples</th><th className="w-72">Outcome</th></tr>
          </thead>
          <tbody>
            {deps.map((d) => {
              const value = draft[d.id] ?? d.outcome ?? "";
              return (
                <tr key={d.id} className="border-t border-slate-100 align-top">
                  <td className="py-2">
                    <div className="font-medium">{d.rule.replace(/_/g, " ")}</div>
                    <div className="text-xs text-slate-500">{d.workspace ? `in ${d.workspace}` : d.rule === "restricted_reference" ? "restricted records left out" : "not found here"}</div>
                  </td>
                  <td className="py-2">{d.count ?? "—"}</td>
                  <td className="py-2 text-xs text-slate-500">
                    {(d.examples ?? []).slice(0, 3).map((x, i) => <div key={i} className="font-mono">{x.from.slice(0, 18)} → {x.to.slice(0, 18)}</div>)}
                  </td>
                  <td className="py-2">
                    {editable ? (
                      <select value={value} onChange={(ev) => setDraft({ ...draft, [d.id]: ev.target.value })}
                              className={`w-full rounded border px-2 py-1 text-sm ${value ? "border-slate-300" : "border-amber-400 bg-amber-50"}`}>
                        <option value="">Choose an outcome…</option>
                        {d.options.map((o) => <option key={o} value={o}>{o.replace(/_/g, " ")} — {OUTCOME_HELP[o]}</option>)}
                      </select>
                    ) : <span>{d.outcome?.replace(/_/g, " ") ?? "—"}</span>}
                    {d.problem && <div className="mt-1 text-xs text-rose-700">{d.problem}</div>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      {(e.analysis.closure?.automatic ?? []).length > 0 && (
        <ul className="mt-3 space-y-0.5 text-xs text-slate-500">
          {e.analysis.closure!.automatic.map((a) => <li key={a.rule}>Automatically included — {a.detail}</li>)}
        </ul>
      )}
    </Section>
  );
}

function ManifestView({ m, sha }: { m: import("../../../api/portabilityTypes").ArchiveManifest; sha: string }) {
  const [raw, setRaw] = useState(false);
  const groups = Object.entries(m.families).reduce<Record<string, [string, typeof m.families[string]][]>>((acc, f) => {
    (acc[f[1].group] ??= []).push(f);
    return acc;
  }, {});
  return (
    <Section title="Manifest" right={<button type="button" className="text-xs text-indigo-700 hover:underline" onClick={() => setRaw((v) => !v)}>{raw ? "Summary" : "Raw JSON"}</button>}>
      {raw ? <pre className="max-h-[32rem] overflow-auto rounded bg-slate-50 p-3 text-xs">{JSON.stringify(m, null, 1)}</pre> : (
        <div className="space-y-4">
          <KV rows={[
            ["Format", m.format], ["SHA-256", <Mono>{sha}</Mono>],
            ["From", `${m.argus.instance_name ?? ""} ${m.argus.instance_id} · ARGUS ${m.argus.application_version} · schema ${m.argus.database_schema ?? "?"}`],
            ["Signed", m.signature ? `${m.signature.algorithm} by ${m.signature.principal} (${m.signature.key_id})` : "no"],
            ["Policy", m.versions.policy], ["Blobs", `${m.blobs.count} (${bytes(m.blobs.bytes)}) in ${m.blobs.stores.join(", ") || "—"}`],
            ["Classes left out", m.classifications.excluded_classes.join(", ") || "none"],
            ["Invariants at export", m.invariants?.ok === null ? "not run" : m.invariants?.ok ? "ok" : `failing: ${(m.invariants?.codes ?? []).join(", ")}`],
          ]} />
          <div className="grid gap-3 md:grid-cols-2">
            {Object.entries(groups).map(([group, fams]) => (
              <div key={group}>
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{group}{group === "projection" ? " (compared, never loaded)" : ""}</div>
                <table className="mt-1 w-full text-xs">
                  <tbody>
                    {fams.map(([name, f]) => (
                      <tr key={name} className="border-t border-slate-100">
                        <td className="py-0.5">{name}</td>
                        <td className="py-0.5 text-right tabular-nums">{f.rows}</td>
                        <td className="py-0.5 pl-2 text-slate-400">{f.chunks.length} chunk{f.chunks.length === 1 ? "" : "s"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        </div>
      )}
    </Section>
  );
}
