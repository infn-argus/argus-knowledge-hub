import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ApiError, ledgerApi } from "../../api/client";
import type { Decision, RecordBrief, ReviewQueue } from "../../api/ledgerTypes";
import { Card, Empty, StatTile } from "../../components/hub/ui";
import { formatTemporal } from "../../components/hub/LedgerPanels";

/**
 * Everything waiting on a person: conflicts between sources and confirmations,
 * inferred facts that need a yes or no, installations found from inventory
 * links, and source revisions held because they would retire too much. Every
 * button here records a decision in the ledger; nothing is overwritten.
 */
const CONFLICT_TEXT: Record<string, { title: string; explain: string }> = {
  confirmed_vs_confirmed: {
    title: "Two people confirmed different values",
    explain: "The earlier confirmation still applies. Pick the value that is right; the other is superseded, both stay on record.",
  },
  authority_vs_authority: {
    title: "Two authoritative sources disagree",
    explain: "The value seen first still applies. Confirm the right one.",
  },
  source_vs_confirmed: {
    title: "A source disagrees with a confirmed value",
    explain: "The confirmed value stays. If the source is right, change the value on the record.",
  },
  contributory_disagreement: {
    title: "Sources disagree",
    explain: "The most recent observation is used for now.",
  },
  possible_overlap: {
    title: "Installations may overlap",
    explain: "Their dates are not precise enough to tell. Give an exact date to one of them.",
  },
  port_confirmation_required: {
    title: "A bus segment needs its port confirmed",
    explain: "The segment carries a safety class, or the only match is not backed by the IT registry. Pick the port for the unit installed now; the choice applies to this installation only.",
  },
  port_mapping_unresolved: {
    title: "No single port matches a bus segment",
    explain: "The unit installed now has no port, or several, that meet the requirement. Fix the IT registry or confirm the port.",
  },
  port_map_invalid: {
    title: "A confirmed port is no longer compatible",
    explain: "The port confirmed for this installation fails a hard check. A confirmation never overrides compatibility.",
  },
  retirement_blocked: {
    title: "A source dropped a position that is still occupied",
    explain: "The position stays active because a confirmed installation is current. End the installation if the unit was removed.",
  },
};

function RecordLink({ r }: { r: RecordBrief | null }) {
  if (!r) return <span className="text-slate-400">—</span>;
  return (
    <Link to={`/assets/${r.uid}`} className="font-medium text-slate-900 hover:underline">
      {r.name}
      <span className="ml-1.5 font-mono text-[11px] font-normal text-slate-400">{r.key}</span>
    </Link>
  );
}

function show(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "string") return v;
  if (typeof v === "object" && v && "ref" in (v as object)) return String((v as { ref: string }).ref);
  if (typeof v === "object" && v && "type" in (v as object)) return `a ${(v as { type: string }).type}`;
  return JSON.stringify(v);
}

export function ReviewQueuePage() {
  const queryClient = useQueryClient();
  const review = useQuery({ queryKey: ["ledger-review"], queryFn: ledgerApi.review, refetchInterval: 30_000 });
  const done = () => {
    queryClient.invalidateQueries({ queryKey: ["ledger-review"] });
    queryClient.invalidateQueries({ queryKey: ["installations"] });
    queryClient.invalidateQueries({ queryKey: ["hub-asset"] });
  };
  const decide = useMutation({ mutationFn: (batch: Decision[]) => ledgerApi.decide(batch), onSuccess: done });
  const confirmInst = useMutation({ mutationFn: (uid: string) => ledgerApi.confirmInstallation(uid), onSuccess: done });
  const rejectInst = useMutation({ mutationFn: (uid: string) => ledgerApi.rejectInstallation(uid), onSuccess: done });
  const approve = useMutation({ mutationFn: (id: string) => ledgerApi.approveRevision(id), onSuccess: done });
  const rejectRev = useMutation({ mutationFn: (id: string) => ledgerApi.rejectRevision(id), onSuccess: done });
  const portMap = useMutation({
    mutationFn: (v: { segment: string; installation: string; port: string }) =>
      ledgerApi.confirmPortMap(v.segment, { installation_uid: v.installation, port_uid: v.port }),
    onSuccess: done,
  });
  const error = [decide, confirmInst, rejectInst, approve, rejectRev, portMap].find((m) => m.isError)?.error;

  if (review.isLoading) return <p className="text-sm text-slate-500">Loading the review queue…</p>;
  if (!review.data) return <p className="text-sm text-red-600">The review queue could not be loaded.</p>;
  const q: ReviewQueue = review.data;
  const blocking = q.conflicts.filter((c) => c.severity === "blocking");
  const other = q.conflicts.filter((c) => c.severity !== "blocking");

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Review queue</h1>
        <p className="mt-0.5 text-sm text-slate-500">
          Decisions only a person can make. Each one is recorded with its author; nothing is overwritten.
        </p>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <StatTile label="Blocking conflicts" value={q.counts.blocking} tone={q.counts.blocking ? "red" : "slate"} />
        <StatTile label="Held revisions" value={q.counts.held_revisions} tone={q.counts.held_revisions ? "red" : "slate"} />
        <StatTile label="Installations to confirm" value={q.counts.installation_proposals} tone="amber" />
        <StatTile label="Facts to confirm" value={q.counts.proposals} tone="amber" />
        <StatTile label="Other conflicts" value={other.length} />
      </div>
      {error && (
        <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error instanceof ApiError ? JSON.stringify((error.body as { detail?: unknown })?.detail) : "The decision failed."}
        </p>
      )}

      {q.held_revisions.length > 0 && (
        <Card title="Source revisions held before they change anything">
          <ul className="divide-y divide-slate-100">
            {q.held_revisions.map((h) => (
              <li key={h.revision_id} className="flex flex-wrap items-start justify-between gap-3 py-2.5">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-900">
                    {h.stream_id} <span className="font-mono text-xs text-slate-500">@ {h.revision.slice(0, 12)}</span>
                  </p>
                  <ul className="mt-0.5 list-disc pl-5 text-xs text-slate-600">
                    {h.reasons.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => approve.mutate(h.revision_id)} className="rounded bg-slate-900 px-3 py-1.5 text-xs font-medium text-white">
                    Approve and publish
                  </button>
                  <button onClick={() => rejectRev.mutate(h.revision_id)} className="rounded border border-slate-300 px-3 py-1.5 text-xs">
                    Reject revision
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card title="Conflicts">
        {blocking.length + other.length === 0 ? (
          <Empty>No conflicts.</Empty>
        ) : (
          <ul className="divide-y divide-slate-100">
            {[...blocking, ...other].map((c) => {
              const text = CONFLICT_TEXT[c.type] ?? { title: c.type, explain: "" };
              const values = (c.detail.values as unknown[] | undefined) ?? [];
              const decisions = (c.detail.decisions as string[] | undefined) ?? [];
              return (
                <li key={c.conflict_id} className="py-3">
                  <div className="flex flex-wrap items-baseline gap-2">
                    {c.severity === "blocking" && (
                      <span className="rounded bg-red-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-red-700">blocking</span>
                    )}
                    <span className="text-sm font-medium text-slate-900">{text.title}</span>
                    <span className="text-sm text-slate-500">on</span>
                    <RecordLink r={c.record} />
                    {c.predicate && <span className="font-mono text-xs text-slate-500">{c.predicate}</span>}
                  </div>
                  <p className="mt-0.5 text-xs text-slate-500">{text.explain}</p>
                  {(c.type === "confirmed_vs_confirmed" || c.type === "authority_vs_authority") && c.record && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {values.map((v, i) => (
                        <button
                          key={i}
                          onClick={() =>
                            decide.mutate([
                              decisions.length
                                ? { kind: "supersede", subject_uid: c.record!.uid, predicate: c.predicate!, member: c.member,
                                    value: v, supersedes: decisions }
                                : { kind: "confirm", subject_uid: c.record!.uid, predicate: c.predicate!, member: c.member, value: v },
                            ])
                          }
                          className="rounded border border-slate-300 bg-white px-3 py-1 text-xs hover:bg-slate-50"
                        >
                          Keep “{show(v)}”
                        </button>
                      ))}
                    </div>
                  )}
                  {c.type.startsWith("port_") && c.record && (
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      {((c.detail.candidates as { port_uid: string; label: string }[] | undefined) ?? []).map((p) => (
                        <button
                          key={p.port_uid}
                          onClick={() =>
                            portMap.mutate({
                              segment: c.record!.uid,
                              installation: String(c.detail.installation_uid),
                              port: p.port_uid,
                            })
                          }
                          className="rounded border border-slate-300 bg-white px-3 py-1 text-xs hover:bg-slate-50"
                        >
                          Use {p.label}
                        </button>
                      ))}
                      {typeof c.detail.failed === "string" && (
                        <span className="text-xs text-red-700">failed: {c.detail.failed}</span>
                      )}
                      <Link to={`/assets/${c.record.uid}#installations`} className="text-xs text-indigo-700 hover:underline">
                        See why each port was ruled out
                      </Link>
                    </div>
                  )}
                  {c.type === "source_vs_confirmed" && (
                    <p className="mt-1 text-xs text-slate-600">
                      Confirmed: <span className="font-mono">{show(c.detail.confirmed)}</span> · sources say{" "}
                      <span className="font-mono">{((c.detail.sources as unknown[]) ?? []).map(show).join(", ")}</span>
                    </p>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      <Card title="Installations found from inventory links">
        {q.installation_proposals.length === 0 ? (
          <Empty>No installation waits for confirmation.</Empty>
        ) : (
          <ul className="divide-y divide-slate-100">
            {q.installation_proposals.map((p) => (
              <li key={p.uid} className="flex flex-wrap items-center justify-between gap-3 py-2.5">
                <div className="text-sm">
                  <RecordLink r={p.asset} /> <span className="text-slate-500">at</span> <RecordLink r={p.position} />
                  <p className="text-xs text-slate-500">since {formatTemporal(p.valid_from, "from")}</p>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => confirmInst.mutate(p.uid)} className="rounded bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white">
                    Confirm
                  </button>
                  <button onClick={() => rejectInst.mutate(p.uid)} className="rounded border border-slate-300 px-3 py-1.5 text-xs">
                    Reject
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Facts waiting for confirmation">
        {q.proposals.length === 0 ? (
          <Empty>No inferred or proposed fact waits for a decision.</Empty>
        ) : (
          <ul className="divide-y divide-slate-100">
            {q.proposals.map((p) => (
              <li key={p.claim_id} className="flex flex-wrap items-center justify-between gap-3 py-2.5">
                <div className="min-w-0 text-sm">
                  <RecordLink r={p.record} /> <span className="font-mono text-xs text-slate-500">{p.predicate}</span>{" "}
                  <span className="font-mono text-xs">{show(p.value)}</span>
                  <p className="text-xs text-slate-500">
                    {p.method} {p.rule_id ? `by ${p.rule_id}` : ""} · {p.stream_id}
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => decide.mutate([{ kind: "accept", target: { claim_id: p.claim_id } }])}
                    className="rounded bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white"
                  >
                    Accept
                  </button>
                  <button
                    onClick={() => decide.mutate([{ kind: "reject", target: { claim_id: p.claim_id, scope: "fingerprint" } }])}
                    className="rounded border border-slate-300 px-3 py-1.5 text-xs"
                    title="Rejects this inference; the same rule will not propose it again"
                  >
                    Reject
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <RulesCard />

      {q.provisional_records.length > 0 && (
        <Card title="Provisional records">
          <ul className="flex flex-wrap gap-2 py-1">
            {q.provisional_records.map((r) => (
              <li key={r.uid}>
                <Link to={`/assets/${r.uid}#provenance`} className="rounded border border-slate-200 px-2 py-1 text-xs hover:bg-slate-50">
                  {r.name} <span className="text-slate-400">{r.type}</span>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}

/** Which semantic rule runs for each inference family, and whether the
 * catalogue passes its signature check (§7.9). */
function RulesCard() {
  const rules = useQuery({ queryKey: ["ledger-rules"], queryFn: ledgerApi.rules });
  if (!rules.data) return null;
  const active = rules.data.rules.filter((r) => r.active);
  return (
    <Card
      title="Inference rules in force"
      action={
        rules.data.check.length === 0 ? (
          <span className="text-xs text-emerald-700">catalogue check passes</span>
        ) : (
          <span className="text-xs text-red-700">{rules.data.check.length} catalogue problem(s)</span>
        )
      }
    >
      <ul className="divide-y divide-slate-100">
        {active.map((r) => (
          <li key={r.rule_id} className="py-2 text-sm">
            <span className="font-mono text-xs text-slate-900">{r.rule_id}</span>
            <span className="ml-2 text-xs text-slate-500">implementation {r.active_impl}</span>
            <p className="text-xs text-slate-600">{r.meaning}</p>
          </li>
        ))}
      </ul>
      {rules.data.check.map((e) => (
        <p key={e} className="text-xs text-red-700">
          {e}
        </p>
      ))}
    </Card>
  );
}
