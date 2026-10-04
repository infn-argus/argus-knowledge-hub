import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { portabilityApi, problemText, workspacesApi } from "../../../api/client";
import type { DryRunReport, ImportView, ReconciliationReport } from "../../../api/portabilityTypes";
import { ActionButton, bytes, Empty, ErrorBox, IMPORT_STEPS, JobsPanel, KV, Labels, LegalHold, Mono, PolicySummary, Section,
  StateBadge, Steps, UninspectedList, useJob, when } from "./shared";

type Step = "fetch-git" | "verify" | "approve" | "execute" | "resume" | "finalize";

export function ImportDetailPage() {
  const { id = "" } = useParams();
  const qc = useQueryClient();
  const me = useQuery({ queryKey: ["me"], queryFn: workspacesApi.me });
  const imp = useQuery({ queryKey: ["portability-import", id], queryFn: () => portabilityApi.getImport(id) });
  const cfg = useQuery({ queryKey: ["portability-config"], queryFn: portabilityApi.config });
  const [accepted, setAccepted] = useState(false);
  const state = imp.data?.state;
  const reconciled = !!state && ["ready_to_finalize", "finalized", "failed"].includes(state) && imp.data?.reconciliation_passed !== null;
  const rec = useQuery({ queryKey: ["portability-reconciliation", id], queryFn: () => portabilityApi.reconciliation(id),
                         enabled: reconciled, retry: false });
  const prov = useQuery({ queryKey: ["portability-provenance", id], queryFn: () => portabilityApi.provenance(id) });
  const [error, setError] = useState<string | null>(null);
  const refresh = (v?: ImportView) => {
    if (v) qc.setQueryData(["portability-import", id], v);
    for (const k of ["portability-imports", "portability-import", "portability-reconciliation", "portability-provenance"]) {
      void qc.invalidateQueries({ queryKey: k === "portability-imports" ? [k] : [k, id] });
    }
  };
  const reload = useCallback(() => {
    for (const k of ["portability-imports", "portability-import", "portability-reconciliation", "portability-provenance"]) {
      void qc.invalidateQueries({ queryKey: k === "portability-imports" ? [k] : [k, id] });
    }
  }, [qc, id]);
  const { job, setJob, running } = useJob(reload);
  // Approving is quick; fetching, verifying, executing and finalizing run as background jobs the page polls.
  const step = useMutation({
    mutationFn: async (s: Step) => {
      if (s === "approve") return portabilityApi.importStep(id, s, { acknowledge_uninspected: accepted });
      const { job: started } = await portabilityApi.importJob(id, s);
      setJob(started);
      return undefined;
    },
    onSuccess: (v) => { setError(null); refresh(v); },
    onError: (e) => { setError(problemText(e)); refresh(); },
  });
  const [reason, setReason] = useState("");
  const discard = useMutation({
    mutationFn: () => portabilityApi.discardImport(id, reason),
    onSuccess: (v) => { setError(null); refresh(v); },
    onError: (e) => { setError(problemText(e)); refresh(); },
  });
  const chain = useQuery({ queryKey: ["portability-origin-chain", id], queryFn: () => portabilityApi.originChain(id),
                           enabled: imp.data?.state === "finalized" && imp.data?.mode !== "evidence", retry: false });
  const dry = useMutation({
    mutationFn: (decisions: Record<string, unknown>) => portabilityApi.dryRun(id, decisions),
    onSuccess: (v) => { setError(null); refresh(v); },
    onError: (e) => { setError(problemText(e)); refresh(); },
  });

  if (imp.isError) return <p className="text-sm text-rose-700">{problemText(imp.error)}</p>;
  if (!imp.data) return <p className="text-sm text-slate-500">Loading…</p>;
  const i = imp.data;
  const busy = step.isPending ? step.variables : dry.isPending ? "dry-run" : null;
  const report = i.dry_run as DryRunReport;
  const hasDryRun = !!report && "ready" in report;
  const policy = cfg.data?.policy;
  const needsSecond = !!policy?.separation_of_duties &&
    (i.mode === "merge" || i.mode === "restore" || (i.manifest?.classifications?.included ?? []).length > 0);
  const selfApproval = needsSecond && me.data?.email === i.requested_by;
  const uninspected = report?.uninspected_content ?? (i.manifest?.blobs?.inspection?.uninspected
    ? { count: i.manifest.blobs.inspection.uninspected, warning: "", items: i.manifest.blobs.uninspected ?? [] } : undefined);
  const stepBusy = (s: Step) => busy === s || (running && job?.action === s);
  const final = i.state === "finalized" || i.state === "discarded";

  return (
    <div className="max-w-6xl space-y-4">
      <Link to="/admin/portability?tab=imports" className="text-xs text-slate-500 hover:text-slate-700">&larr; Portability</Link>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-mono text-lg font-semibold text-slate-900">{i.id}</h1>
          <p className="text-sm text-slate-600">
            {i.mode} · {i.source.repository ? <>from <b>{i.source.repository}</b> <Mono>{i.source.ref}</Mono></> : "uploaded checkpoint"}
          </p>
          <div className="mt-2">
            {i.manifest ? <Labels labels={i.labels} />
              : <span className="text-xs text-slate-500">Labels appear once the checkpoint is verified.</span>}
          </div>
        </div>
        <StateBadge state={i.state} />
      </div>
      <Steps steps={IMPORT_STEPS} state={i.state} />
      <ErrorBox error={error ?? (["failed", "invalid"].includes(i.state) || i.error?.code === "interrupted" ? i.error : null)} />

      <Section title="Next step">
        <div className="flex flex-wrap items-center gap-3">
          {i.state === "created" && i.source.repository && (
            <ActionButton label="Fetch into quarantine" busy={stepBusy("fetch-git")} disabled={running} onClick={() => step.mutate("fetch-git")} />
          )}
          {i.state === "created" && !i.source.repository && <span className="text-sm text-slate-500">Waiting for the uploaded checkpoint.</span>}
          {i.state === "quarantined" && (
            <ActionButton label="Verify" busy={stepBusy("verify")} disabled={running} onClick={() => step.mutate("verify")} />
          )}
          {(i.state === "dry_run_ready" || i.state === "awaiting_approval") && (
            <ActionButton label={hasDryRun ? "Run the dry run again" : "Dry run"} busy={busy === "dry-run"}
                          onClick={() => dry.mutate({})} />
          )}
          {i.state === "awaiting_approval" && (
            <>
              {uninspected && (
                <label className="flex items-center gap-2 text-sm text-amber-900">
                  <input type="checkbox" checked={accepted} onChange={(ev) => setAccepted(ev.target.checked)} />
                  I accept that {uninspected.count} file(s) were not inspected for secrets or classified content
                </label>
              )}
              <ActionButton label="Approve" busy={busy === "approve"} onClick={() => step.mutate("approve")}
                            disabled={selfApproval || (!!uninspected && !accepted)}
                            confirm="Approve this import as shown by the dry run?" />
              {selfApproval && <span className="text-sm text-amber-800">You registered it: another administrator must approve.</span>}
            </>
          )}
          {i.state === "approved" && (
            <ActionButton label="Execute" busy={stepBusy("execute")} disabled={running} onClick={() => step.mutate("execute")}
                          confirm={i.mode === "evidence" ? "Store this archive as read-only evidence?" :
                            "Load the archive into staged workspaces, rebuild and reconcile?"} />
          )}
          {(i.state === "importing" || i.state === "failed") && (
            <ActionButton label={`Resume in staging (${i.checkpoints.done} steps done)`} busy={stepBusy("resume")} disabled={running} onClick={() => step.mutate("resume")} />
          )}
          {i.state === "ready_to_finalize" && (
            <ActionButton label="Finalize" busy={stepBusy("finalize")} disabled={running} onClick={() => step.mutate("finalize")}
                          confirm={i.mode === "evidence" ? "Finalize: keep this archive as read-only evidence."
                            : "Finalize: promote the reconciled import into this instance in one transaction — all of it becomes visible at once, as permanent history."} />
          )}
          {i.state === "finalized" && <span className="text-sm text-emerald-700">Finalized {i.reconciliation_sha256 ? <>— reconciliation <Mono short>{i.reconciliation_sha256}</Mono></> : null}.</span>}
          {i.state === "discarded" && <span className="text-sm text-slate-500">Discarded: nothing it loaded remains.</span>}
          {running && <span className="text-sm text-sky-700">{job?.action.replace("-", " ")} is {job?.state}… this page updates by itself.</span>}
          {job?.state === "failed" && <span className="text-sm text-rose-700">{job.action} failed: {job.error?.error}</span>}
          {!final && (
            <span className="ml-auto flex items-center gap-2">
              <input value={reason} onChange={(ev) => setReason(ev.target.value)} placeholder="Reason to discard"
                     className="w-48 rounded border border-slate-300 px-2 py-1 text-sm" />
              <ActionButton label="Discard" danger busy={discard.isPending} onClick={() => discard.mutate()}
                            confirm="Discard: drop its staging database and quarantine. Active data was never touched; the audit trail stays." />
            </span>
          )}
        </div>
      </Section>

      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Source and signature">
          <KV rows={[
            ["Registered by", i.requested_by], ["Approved by", i.approved_by ?? "—"], ["Created", when(i.created_at)],
            ["Tag", i.verification.git?.tag ? <Mono>{i.verification.git.tag}</Mono> : undefined],
            ["Commit", <Mono>{i.commit}</Mono>],
            ["Signed by", i.verification.git?.signed_by ?? i.verification.checkpoint?.signed_by ?? undefined],
            ["Repository identity", i.verification.git ? <Mono>{i.verification.git.repository_id}</Mono> : undefined],
            ["Previous export tag", i.verification.git?.previous_tag ? <Mono>{i.verification.git.previous_tag}</Mono> : undefined],
            ["Upload", i.verification.upload ? `${bytes(i.verification.upload.bytes)}, sha256 ${i.verification.upload.sha256.slice(0, 12)}` : undefined],
            ["Staging", i.staging?.database ? `${i.staging.database} — isolated; nothing is visible here before finalization` : undefined],
          ]} />
        </Section>
        <Section title="Verification">
          {i.verification.checkpoint ? (
            <KV rows={[
              ["Files", i.verification.checkpoint.files], ["Chunks", i.verification.checkpoint.chunks],
              ["Rows", i.verification.checkpoint.rows],
              ["Artifacts", `${i.verification.checkpoint.blobs} (${bytes(i.verification.checkpoint.blob_bytes)})${i.verification.checkpoint.artifact_complete ? ", all present" : ""}`],
              ["External chunks", i.verification.checkpoint.external_chunks ?? undefined],
              ["Content", i.verification.checkpoint.content_verified ? "verified" + (i.manifest?.labels?.encrypted ? " (decrypted for this session)" : "") : "not verified"],
              ["Manifest", <Mono>{i.verification.checkpoint.manifest_sha256}</Mono>],
            ]} />
          ) : <Empty>Not verified yet: checksums, signature, chunks and artifacts are checked in quarantine.</Empty>}
        </Section>
      </div>

      {i.manifest && (
        <Section title="Archive">
          <KV rows={[
            ["Export", i.manifest.export_id], ["Mode", i.manifest.mode],
            ["Workspaces", i.manifest.workspaces.join(", ")],
            ["Watermark", <>checkpoint {i.manifest.watermark.checkpoint_sequence} · <Mono short>{i.manifest.watermark.vector_sha256}</Mono> at {when(i.manifest.watermark.snapshot_time)}</>],
            ["People", i.manifest.identity?.profile.replace(/_/g, " ")],
            ["Base export", i.manifest.base?.export_id],
            ["From", `${i.manifest.argus.instance_name ?? ""} ${i.manifest.argus.instance_id} · ARGUS ${i.manifest.argus.application_version}`],
            ["Restricted classes included", (i.manifest.classifications.included ?? []).join(", ") || "none"],
            ["Classes left out", (i.manifest.classifications.excluded_classes ?? []).join(", ") || "none"],
            ["Purpose", i.manifest.purpose?.replace(/_/g, " ")],
          ]} />
          {i.manifest.policy && (
            <div className="mt-3 border-t border-slate-100 pt-3">
              <div className="mb-1 text-xs text-slate-500">Made under</div>
              <PolicySummary policy={i.manifest.policy} />
            </div>
          )}
        </Section>
      )}

      <JobsPanel subject={i.id} current={job} />
      {uninspected && uninspected.items.length > 0 && <UninspectedList items={uninspected.items} total={uninspected.count} />}

      {(i.state === "dry_run_ready" || i.state === "awaiting_approval") && i.mode !== "evidence" && (
        <DecisionsForm i={i} running={dry.isPending} onRun={(d) => dry.mutate(d)} />
      )}
      {hasDryRun && <DryRun r={report} />}
      {rec.data && <Reconciliation r={rec.data.report} sha={rec.data.sha256} />}
      {chain.data && (
        <Section title="Origin chain" right={<span className={`text-sm font-medium ${chain.data.ok ? "text-emerald-700" : "text-rose-700"}`}>
          {chain.data.ok ? "Verifies" : "Changed"}</span>}>
          <KV rows={[["Chain", <Mono>{chain.data.origin_chain_sha256}</Mono>], ["Ingestion event", chain.data.ingestion_event],
                     ["Problems", chain.data.problems?.length ? chain.data.problems.map((p) => `${p.family} ${p.key}: ${p.problem}`).join("; ") : undefined]]} />
          <p className="mt-2 text-xs text-slate-500">Every imported ledger row, recomputed from what is here, against the hash of the archive line it came from.</p>
        </Section>
      )}
      {i.state === "finalized" && i.mode === "evidence" && <Evidence id={i.id} />}
      {prov.data && (
        <Section title="Provenance and audit">
          <ol className="space-y-1 text-xs">
            {prov.data.events.map((e) => (
              <li key={e.seq} className="flex flex-wrap gap-2">
                <span className="w-40 shrink-0 text-slate-500">{when(e.at)}</span>
                <span className="w-32 shrink-0 font-medium">{e.kind.replace(/_/g, " ")}</span>
                <span className="text-slate-500">{e.from && e.to ? `${e.from} → ${e.to}` : e.to ?? ""}</span>
                <span className="ml-auto text-slate-500">{e.actor}</span>
              </li>
            ))}
          </ol>
        </Section>
      )}
      {cfg.data?.is_admin && (
        <Section title="Retention">
          <p className="mb-2 text-xs text-slate-500">Quarantine, staging and evidence copies are deleted {policy?.retention_days ?? 90} days
            after registration unless held; the import's record and audit are kept.</p>
          <LegalHold kind="imports" id={i.id} on={i.legal_hold} reason={i.legal_hold_reason} purgedAt={i.purged_at}
                     onChange={reload} />
        </Section>
      )}
    </div>
  );
}

function DecisionsForm({ i, onRun, running }: { i: ImportView; onRun: (d: Record<string, unknown>) => void; running: boolean }) {
  const current = i.decisions as { workspace_map?: Record<string, string>; unresolved_references?: string; governance?: string };
  const [map, setMap] = useState<Record<string, string>>(current.workspace_map ?? {});
  const [refs, setRefs] = useState(current.unresolved_references ?? "block");
  const [gov, setGov] = useState(current.governance === "load");
  const [chosen, setChosen] = useState<string[]>((i.decisions as { select_workspaces?: string[] }).select_workspaces ?? []);
  return (
    <Section title="Decisions for the dry run">
      <div className="space-y-3 text-sm">
        <div>
          <span className="block text-xs font-medium text-slate-600">Workspace ids here (leave as is to keep the archive's)</span>
          <div className="mt-1 grid gap-2 md:grid-cols-2">
            {(i.manifest?.workspaces ?? []).map((w) => (
              <label key={w} className="flex items-center gap-2">
                <span className="w-40 truncate font-mono text-xs">{w}</span> →
                <input value={map[w] ?? w} onChange={(e) => setMap({ ...map, [w]: e.target.value })}
                       className="flex-1 rounded border border-slate-300 px-2 py-1 font-mono text-xs" />
              </label>
            ))}
          </div>
        </div>
        {i.mode === "selective" && (
          <div>
            <span className="block text-xs font-medium text-slate-600">Workspaces to import</span>
            <div className="mt-1 flex flex-wrap gap-3">
              {(i.manifest?.workspaces ?? []).map((w) => (
                <label key={w} className="flex items-center gap-1 font-mono text-xs">
                  <input type="checkbox" checked={chosen.includes(w)}
                         onChange={() => setChosen(chosen.includes(w) ? chosen.filter((x) => x !== w) : [...chosen, w])} />
                  {w}
                </label>
              ))}
            </div>
          </div>
        )}
        <label className="flex items-center gap-2">
          References the archive and this instance both lack:
          <select value={refs} onChange={(e) => setRefs(e.target.value)} className="rounded border border-slate-300 px-2 py-1">
            <option value="block">block the import</option>
            <option value="defer">leave unresolved and list them in the reconciliation</option>
          </select>
        </label>
        {(i.mode === "merge" || i.mode === "selective") && (
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={gov} onChange={(e) => setGov(e.target.checked)} />
            Load the archive's authority policies and rulesets (otherwise they are listed, not loaded)
          </label>
        )}
        <button type="button" disabled={running}
                onClick={() => onRun({ workspace_map: Object.fromEntries(Object.entries(map).filter(([k, v]) => v && v !== k)),
                                       unresolved_references: refs, ...(gov ? { governance: "load" } : {}),
                                       ...(i.mode === "selective" ? { select_workspaces: chosen } : {}) })}
                className="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:bg-slate-300">
          {running ? "Running…" : "Run the dry run with these decisions"}
        </button>
      </div>
    </Section>
  );
}

const OUTCOMES = ["create", "identical", "update_same_origin", "known_identity", "unresolved_reference", "divergent"];

function DryRun({ r }: { r: DryRunReport }) {
  return (
    <Section title="Dry run" right={<span className={`text-sm font-medium ${r.ready ? "text-emerald-700" : "text-rose-700"}`}>
      {r.ready ? "Ready for approval" : "Blocked"}</span>}>
      {r.note && <p className="mb-2 text-sm text-slate-600">{r.note}</p>}
      {r.chain && <p className="mb-2 text-sm text-slate-600">Chain: <b>{r.chain.status.replace(/_/g, " ")}</b>
        {r.chain.applied !== undefined && ` · ${r.chain.applied} export(s) from this origin applied here`}</p>}
      {r.families && (
        <table className="mb-3 w-full text-xs">
          <thead className="text-left text-slate-500">
            <tr><th className="py-1">Family</th>{OUTCOMES.map((o) => <th key={o} className="px-2 text-right">{o.replace(/_/g, " ")}</th>)}</tr>
          </thead>
          <tbody>
            {Object.entries(r.families).map(([f, c]) => (
              <tr key={f} className="border-t border-slate-100">
                <td className="py-0.5">{f}</td>
                {OUTCOMES.map((o) => (
                  <td key={o} className={`px-2 text-right tabular-nums ${c[o] && (o === "divergent" || o === "unresolved_reference") ? "font-semibold text-rose-700" : ""}`}>
                    {c[o] ?? ""}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <Issues title="Blocking" items={(r.blocking ?? []).map((b) => `${b.family} ${b.key}: ${b.reason}`)} tone="rose" />
      <Issues title="Catalogue conflicts (never overwritten; review the type here)" tone="rose"
              items={(r.catalogue_conflicts ?? []).map((c) => `${c.key}: ${c.reason}`)} />
      <Issues title="Identity candidates (opened for review after import, never merged)" tone="amber"
              items={(r.identity_candidates ?? []).map((c) => `${c.identifier} ${c.value}: archive ${c.archive.slice(0, 8)} ↔ here ${c.here.slice(0, 8)}`)} />
      <Issues title={`Unresolved references (${r.unresolved_reference_count ?? 0}; outcome: ${r.unresolved_references_outcome})`} tone="amber"
              items={(r.unresolved_references ?? []).map((u) => `${u.family} ${u.key} → ${u.missing.map((m) => m[1]).join(", ")}`)} />
      <Issues title="Governance not loaded" tone="amber" items={r.governance_not_loaded ?? []} />
      <Issues title="People already known here (kept as they are)" tone="slate" items={(r.identities ?? []).map((x) => x.user)} />
      {r.workspaces && (
        <p className="mt-2 text-xs text-slate-500">
          Workspaces: {r.workspaces.map((w) => `${w.archive}${w.local !== w.archive ? ` → ${w.local}` : ""}${w.exists ? " (exists here)" : ""}`).join(", ")}
        </p>
      )}
    </Section>
  );
}

function Issues({ title, items, tone }: { title: string; items: string[]; tone: "rose" | "amber" | "slate" }) {
  if (items.length === 0) return null;
  const c = tone === "rose" ? "text-rose-800" : tone === "amber" ? "text-amber-800" : "text-slate-600";
  return (
    <div className="mt-2">
      <div className={`text-xs font-semibold ${c}`}>{title}</div>
      <ul className={`mt-1 max-h-40 list-disc overflow-auto pl-5 text-xs ${c}`}>
        {items.slice(0, 50).map((x, k) => <li key={k} className="font-mono">{x}</li>)}
      </ul>
    </div>
  );
}

function Reconciliation({ r, sha }: { r: ReconciliationReport; sha: string }) {
  const fams = Object.entries(r.families ?? {});
  const projs = Object.entries(r.projections ?? {});
  const events = Object.entries(r.rebuild?.events_written_by_rebuild ?? {});
  return (
    <Section title="Reconciliation" right={<span className={`text-sm font-medium ${r.passed ? "text-emerald-700" : "text-rose-700"}`}>
      {r.passed ? "Passed" : "Failed — finalization blocked"}</span>}>
      <KV rows={[["Report", <Mono>{sha}</Mono>], ["Signed", r.signature ? `${r.signature.algorithm} by ${r.signature.principal}` : "no"],
                 ["Note", r.evidence_only ? "evidence only: no projection to rebuild" : r.already_applied ? "this export was already applied here: nothing changed" : undefined],
                 ["Invariants", r.invariants ? `${r.invariants.ok ? "ok" : "failing"} here; ${r.invariants.exported_ok ? "ok" : "failing"} at the source` : undefined]]} />
      {fams.length > 0 && (
        <div className="mt-3 grid gap-4 md:grid-cols-2">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Authoritative, row by row</div>
            <table className="mt-1 w-full text-xs"><tbody>
              {fams.map(([f, v]) => (
                <tr key={f} className="border-t border-slate-100">
                  <td className="py-0.5">{f}</td>
                  <td className="text-right tabular-nums">{v.rows}/{v.expected_rows}</td>
                  <td className={`pl-2 ${v.ok ? "text-emerald-700" : "text-rose-700"}`}>{v.ok ? "equal" : `${v.mismatch_count} differ`}</td>
                </tr>
              ))}
            </tbody></table>
          </div>
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Projections rebuilt here vs exported</div>
            <table className="mt-1 w-full text-xs"><tbody>
              {projs.map(([f, v]) => (
                <tr key={f} className="border-t border-slate-100">
                  <td className="py-0.5">{f}</td>
                  <td className="text-right tabular-nums">{v.rebuilt}/{v.exported}</td>
                  <td className={`pl-2 ${v.ok ? "text-emerald-700" : "text-rose-700"}`}>{v.ok ? "equal" : "differ"}</td>
                </tr>
              ))}
            </tbody></table>
            {events.length > 0 && <p className="mt-2 text-xs text-slate-500">Events the rebuild wrote: {events.map(([k, n]) => `${k} ${n}`).join(", ")}</p>}
          </div>
        </div>
      )}
      {fams.some(([, v]) => !v.ok) && (
        <pre className="mt-3 max-h-48 overflow-auto rounded bg-rose-50 p-2 text-xs text-rose-800">
          {JSON.stringify(Object.fromEntries(fams.filter(([, v]) => !v.ok).map(([f, v]) => [f, v.mismatches])), null, 1)}
        </pre>
      )}
      {(r.deferred_references ?? []).length > 0 && (
        <p className="mt-2 text-xs text-amber-800">{r.deferred_references!.length} reference(s) left unresolved by decision.</p>
      )}
    </Section>
  );
}

function Evidence({ id }: { id: string }) {
  const [family, setFamily] = useState("assets");
  const [offset, setOffset] = useState(0);
  const rows = useQuery({ queryKey: ["portability-evidence", id, family, offset], queryFn: () => portabilityApi.evidence(id, family, offset, 25),
                          retry: false });
  const fams = useQuery({ queryKey: ["portability-evidence-families", id], queryFn: () => portabilityApi.evidenceFamilies(id) });
  const families = (fams.data ?? []).map((f) => f.family);
  return (
    <Section title="Evidence (read-only, from the archive)">
      <p className="mb-2 text-xs text-slate-500">Browsed only — not searched, indexed or downloadable. Restricted rows appear only for the
        institution's evidence readers; counts are of what you may see. Every read is audited.</p>
      <div className="mb-2 flex items-center gap-2 text-sm">
        <select value={family} onChange={(e) => { setFamily(e.target.value); setOffset(0); }} className="rounded border border-slate-300 px-2 py-1">
          {families.map((f) => <option key={f} value={f}>{f}</option>)}
        </select>
        {rows.data && <span className="text-xs text-slate-500">{rows.data.total === 0 ? "no rows" :
          `${offset + 1}–${Math.min(offset + 25, rows.data.total)} of ${rows.data.total}`}</span>}
        <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 25))} className="rounded border px-2 py-0.5 text-xs disabled:opacity-40">‹</button>
        <button type="button" disabled={!rows.data || offset + 25 >= rows.data.total} onClick={() => setOffset(offset + 25)} className="rounded border px-2 py-0.5 text-xs disabled:opacity-40">›</button>
      </div>
      {rows.isError ? <p className="text-sm text-slate-500">{problemText(rows.error)}</p> : (
        <div className="max-h-[28rem] space-y-1 overflow-auto">
          {(rows.data?.rows ?? []).map((r) => (
            <details key={r.key} className="rounded border border-slate-100 px-2 py-1 text-xs">
              <summary className="cursor-pointer font-mono">{String(r.row.name ?? r.row.title ?? r.row.predicate ?? r.key)}</summary>
              <pre className="mt-1 overflow-auto whitespace-pre-wrap">{JSON.stringify(r.row, null, 1)}</pre>
            </details>
          ))}
        </div>
      )}
    </Section>
  );
}
