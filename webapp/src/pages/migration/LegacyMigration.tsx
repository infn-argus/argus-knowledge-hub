/** §12: ARGUS's own inferred records become Positions, Equipment and
 * Installations. The plan changes nothing; owners read the report and may
 * override an outcome; applying checks itself item by item; a rollback is
 * possible until the plan is finalized or the domain cuts over. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { legacyMigrationApi } from "../../api/client";
import type { MigrationAction, MigrationOutcome, MigrationRow } from "../../api/ledgerTypes";
import { errorText } from "../../components/hub/LedgerPanels";
import { Card, Empty } from "../../components/hub/ui";

const OUTCOME: Record<MigrationOutcome, { text: string; tone: string }> = {
  "M-BLOCK": { text: "blocked", tone: "bg-red-50 text-red-700" },
  "M-FUNC": { text: "functional", tone: "bg-slate-100 text-slate-700" },
  "M-POS": { text: "position", tone: "bg-sky-50 text-sky-800" },
  "M-PHYS": { text: "position + equipment", tone: "bg-emerald-50 text-emerald-800" },
  "M-MIXED": { text: "mixed — review", tone: "bg-amber-50 text-amber-800" },
  "M-RETIRE": { text: "retire", tone: "bg-slate-100 text-slate-500" },
};
const CHOICES: MigrationOutcome[] = ["M-POS", "M-PHYS", "M-MIXED", "M-RETIRE", "M-BLOCK"];

function planned(a: MigrationAction): string {
  switch (a.do) {
    case "retype":
      return `position ${a.key}`;
    case "equipment":
      return a.match ? "equipment: the inventory's record" : `equipment (${a.status}) in ${a.workspace}`;
    case "installation":
      return `installation ${a.status}`;
    case "move_labels":
      return `${a.labels?.length} identifier label(s) → equipment`;
    case "move_attachments":
      return `${a.attachments?.length} photo(s) → equipment`;
    case "retire":
      return "retired, not deleted";
    default:
      return "kept as it is";
  }
}

export function LegacyMigrationCard() {
  const queryClient = useQueryClient();
  const plans = useQuery({ queryKey: ["migration-plans"], queryFn: legacyMigrationApi.list, retry: false });
  const gate = useQuery({ queryKey: ["migration-gate"], queryFn: legacyMigrationApi.gate, retry: false });
  const [selected, setSelected] = useState<string | null>(null);
  const current = selected ?? plans.data?.[0]?.id ?? null;
  const refresh = () => {
    for (const key of ["migration-plans", "migration-plan", "migration-gate"]) queryClient.invalidateQueries({ queryKey: [key] });
  };
  const create = useMutation({ mutationFn: () => legacyMigrationApi.plan(), onSuccess: (p) => { setSelected(p.id); refresh(); } });
  if (plans.isError) return null;
  const g = gate.data;
  return (
    <Card
      title="Legacy records (§12)"
      action={
        g && (
          <span className={`rounded px-2 py-0.5 text-xs ${g.ok ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-800"}`}>
            {g.ok ? "ready for cutover" : `${g.blocked.length} blocked · ${g.mixed_open.length} to review · ${g.unplanned} unplanned`}
          </span>
        )
      }
    >
      <p className="py-1 text-sm text-slate-600">
        Records the old importer inferred become Positions, Equipment and Installations. Planning changes nothing; a domain
        cannot be frozen for cutover until none is blocked, every mixed one is accepted, and none is left unplanned.
      </p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        {(plans.data ?? []).map((p) => (
          <button
            key={p.id}
            onClick={() => setSelected(p.id)}
            className={`rounded border px-2 py-1 font-mono text-xs ${p.id === current ? "border-slate-900" : "border-slate-200"}`}
          >
            {p.id.slice(0, 14)}… · {p.status}
          </button>
        ))}
        <button onClick={() => create.mutate()} className="rounded-md bg-slate-900 px-3 py-1 text-xs font-medium text-white">
          Plan the migration
        </button>
      </div>
      {create.isError && <p className="mt-2 text-sm text-red-600">{errorText(create.error)}</p>}
      {current ? <PlanDetail id={current} onChange={refresh} /> : <Empty>No plan yet.</Empty>}
    </Card>
  );
}

function PlanDetail({ id, onChange }: { id: string; onChange: () => void }) {
  const plan = useQuery({ queryKey: ["migration-plan", id], queryFn: () => legacyMigrationApi.get(id) });
  const [filter, setFilter] = useState<string>("");
  const act = (fn: (id: string) => Promise<unknown>) => ({ mutationFn: () => fn(id), onSuccess: onChange });
  const apply = useMutation(act(legacyMigrationApi.apply));
  const rollback = useMutation(act(legacyMigrationApi.rollback));
  const finalize = useMutation(act(legacyMigrationApi.finalize));
  const verify = useMutation(act(legacyMigrationApi.verify));
  const override = useMutation({
    mutationFn: (v: { item: number; outcome: string; reason: string }) => legacyMigrationApi.override(id, v.item, v.outcome, v.reason),
    onSuccess: onChange,
  });
  const download = async () => {
    const url = await legacyMigrationApi.reportUrl(id);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${id}.csv`;
    a.click();
  };
  if (!plan.data) return null;
  const p = plan.data;
  const rows = (p.rows ?? []).filter((r) => !filter || r.outcome === filter || r.status === filter);
  const open = p.status !== "finalized" && p.status !== "rolled_back";
  const error = [apply, rollback, finalize, override, verify].find((m) => m.isError)?.error;
  const deep = p.invariants?.deep_verification;
  return (
    <div className="mt-3 space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        {Object.entries(p.outcomes).map(([o, n]) => (
          <button key={o} onClick={() => setFilter(filter === o ? "" : o)}
                  className={`rounded px-2 py-0.5 ${OUTCOME[o as MigrationOutcome]?.tone} ${filter === o ? "ring-1 ring-slate-900" : ""}`}>
            {o} {n}
          </button>
        ))}
        <span className="text-slate-400">·</span>
        {Object.entries(p.statuses).map(([s, n]) => (
          <button key={s} onClick={() => setFilter(filter === s ? "" : s)} className={`text-slate-600 ${filter === s ? "underline" : ""}`}>
            {s} {n}
          </button>
        ))}
        <span className="ml-auto flex gap-2">
          <button onClick={download} className="rounded border border-slate-300 px-2 py-1">Report (CSV)</button>
          {open && (
            <button onClick={() => apply.mutate()} disabled={apply.isPending} className="rounded bg-slate-900 px-2 py-1 font-medium text-white">
              {apply.isPending ? "Applying…" : "Apply"}
            </button>
          )}
          {open && p.applied_at && (
            <button onClick={() => confirm("Undo every applied item of this plan?") && rollback.mutate()}
                    className="rounded border border-red-200 px-2 py-1 text-red-700">
              Roll back
            </button>
          )}
          {open && p.applied_at && (
            <button onClick={() => verify.mutate()} disabled={verify.isPending} className="rounded border border-slate-300 px-2 py-1"
                    title="Data invariants (I-MIG-4); registry report before and after (I-MIG-5); rebuild from the ledger and compare (I-MIG-6)">
              {verify.isPending ? "Verifying…" : "Deep verify"}
            </button>
          )}
          {p.status === "verified" && (
            <button onClick={() => confirm("After finalizing, the plan can no longer be rolled back.") && finalize.mutate()}
                    className="rounded border border-slate-300 px-2 py-1">
              Finalize
            </button>
          )}
        </span>
      </div>
      {p.invariants && (
        <p className="text-xs text-slate-600">
          {Object.entries(p.invariants.checks).map(([k, ok]) => (
            <span key={k} className={`mr-3 ${ok ? "text-emerald-700" : "text-red-600"}`}>{ok ? "✓" : "✗"} {k}</span>
          ))}
          {deep ? (
            <>
              {deep["I-MIG-4"] && (
                <span className={`mr-3 ${deep["I-MIG-4"].ok ? "text-emerald-700" : "text-red-600"}`}>
                  {deep["I-MIG-4"].ok ? "✓ I-MIG-4 (data invariants)" : `✗ I-MIG-4 (${deep["I-MIG-4"].failing.join(", ")})`}
                </span>
              )}
              <span className={`mr-3 ${deep["I-MIG-5"].ok ? "text-emerald-700" : "text-red-600"}`}
                    title={deep["I-MIG-5"].grew && Object.keys(deep["I-MIG-5"].grew).length ? `grew: ${Object.keys(deep["I-MIG-5"].grew).join(", ")}` : undefined}>
                {deep["I-MIG-5"].ok ? "✓" : "✗"} I-MIG-5 (registry {deep["I-MIG-5"].before ?? "?"} → {deep["I-MIG-5"].after ?? "?"})
              </span>
              <span className={`mr-3 ${deep["I-MIG-6"].ok ? "text-emerald-700" : "text-red-600"}`}>
                {deep["I-MIG-6"].ok ? "✓" : "✗"} I-MIG-6 (rebuild: {deep["I-MIG-6"].differences.length} of {deep["I-MIG-6"].records} differ)
              </span>
            </>
          ) : (
            <span className="mr-3 text-slate-500">I-MIG-4, I-MIG-5, I-MIG-6: deep verification not run</span>
          )}
          <span className="text-slate-400">checked by people: {p.invariants.not_automated.map((x) => x.split(" ")[0]).join(", ")}</span>
        </p>
      )}
      {error && <p className="text-sm text-red-600">{errorText(error)}</p>}
      <div className="max-h-[32rem] overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-white text-left text-xs text-slate-400">
            <tr>
              <th className="py-1 font-normal">Record</th>
              <th className="font-normal">Outcome</th>
              <th className="font-normal">Becomes</th>
              <th className="font-normal">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 align-top">
            {rows.map((r) => (
              <Row key={r.item} r={r} open={open} onOverride={(outcome, reason) => override.mutate({ item: r.item, outcome, reason })} />
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <Empty>No inferred record is waiting for migration.</Empty>}
      </div>
    </div>
  );
}

function Row({ r, open, onOverride }: { r: MigrationRow; open: boolean; onOverride: (outcome: string, reason: string) => void }) {
  const o = OUTCOME[r.outcome];
  return (
    <tr>
      <td className="py-1.5 pr-3">
        <Link to={`/assets/${r.legacy_uid}`} className="font-mono text-xs text-slate-800 hover:underline">{r.legacy_key}</Link>
        <span className="block text-xs text-slate-400">{r.legacy_type}</span>
        {r.warnings.map((w) => (
          <span key={w} className="block text-[11px] text-amber-700">{w}</span>
        ))}
      </td>
      <td className="pr-3">
        <span className={`rounded px-1.5 py-0.5 text-xs ${o.tone}`} title={`confidence ${r.confidence}`}>{o.text}</span>
        {r.override && <span className="block text-[11px] text-slate-500" title={r.override.reason}>overridden by {r.override.by}</span>}
        {open && r.status !== "applied" && r.outcome !== "M-FUNC" && (
          <select
            value=""
            onChange={(e) => {
              const reason = e.target.value && prompt(`Why ${e.target.value}?`);
              if (reason) onOverride(e.target.value, reason);
            }}
            className="mt-1 block rounded border border-slate-200 text-[11px]"
          >
            <option value="">Override…</option>
            {CHOICES.filter((c) => c !== r.outcome).map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        )}
      </td>
      <td className="pr-3 text-xs text-slate-600">
        {r.actions.map((a, i) => (
          <span key={i} className="block">{planned(a)}</span>
        ))}
      </td>
      <td className="text-xs">
        <span className={r.status === "applied" ? "text-emerald-700" : r.status === "failed" || r.status === "stale" ? "text-red-600" : "text-slate-500"}>
          {r.status}
        </span>
        {r.reason && <span className="block text-[11px] text-slate-500">{r.reason}</span>}
      </td>
    </tr>
  );
}
