import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { beamModelApi } from "../../api/client";
import type { AssetSyncApplied, SyncProposal } from "../../api/types";

/** Beamline asset synchronization (docs/beam-asset-sync.md): which physical assets implement the model's
 *  components, how sure the matcher is, and what a person decides. A preview never changes anything. */

const GROUPS = ["magnets", "diagnostics", "vacuum", "rf", "optics", "mechanical", "interception", "sources"];
const STATUSES = ["unmatched", "ambiguous", "proposed", "confirmed"];
const TONE: Record<string, string> = {
  confirmed: "bg-emerald-100 text-emerald-800", proposed: "bg-sky-100 text-sky-800",
  ambiguous: "bg-amber-100 text-amber-900", unmatched: "bg-slate-100 text-slate-600", rejected: "bg-rose-100 text-rose-800",
};
const DIFF_TONE: Record<string, string> = {
  missing_asset: "text-rose-700", conflict: "text-rose-700", changed: "text-amber-800", changed_candidate: "text-amber-800",
  candidate_lost: "text-amber-800", new_match: "text-sky-700",
};

export function BeamAssetSyncPage() {
  const { modelId = "" } = useParams();
  const qc = useQueryClient();
  const [filter, setFilter] = useState<string | null>(null);
  const [choice, setChoice] = useState<Record<string, string>>({});   // component → chosen asset id
  const [result, setResult] = useState<AssetSyncApplied | null>(null);
  const status = useQuery({ queryKey: ["asset-sync", modelId], queryFn: () => beamModelApi.syncStatus(modelId) });
  const refresh = () => void qc.invalidateQueries({ queryKey: ["asset-sync", modelId] });
  const apply = useMutation({
    mutationFn: (body: Parameters<typeof beamModelApi.syncApply>[1]) => beamModelApi.syncApply(modelId, body),
    onSuccess: (r) => { setResult(r); setChoice({}); refresh(); },
  });

  const rows = useMemo(() => {
    const all = (status.data?.proposals ?? []).filter((p) => p.expects_asset);
    if (!filter) return all;
    if (STATUSES.includes(filter)) return all.filter((p) => p.status === filter);
    const fam: Record<string, string[]> = {
      magnets: ["magnet"], diagnostics: ["diagnostic"], vacuum: ["vacuum"], rf: ["rf"], optics: ["optical"],
      mechanical: ["mechanical"], interception: ["interception", "injection_extraction", "material"], sources: ["source_destination"],
    };
    return all.filter((p) => (fam[filter] ?? []).includes(p.family));
  }, [status.data, filter]);

  if (status.isError) return <p className="text-sm text-rose-700">{String(status.error)}</p>;
  if (!status.data) return <p className="text-sm text-slate-500">Matching…</p>;
  const s = status.data.summary;
  const selected = Object.entries(choice).filter(([, a]) => a);
  const proposed = (p: SyncProposal) => choice[p.component] ?? (p.status === "proposed" ? p.asset?.id ?? "" : "");

  return (
    <div className="max-w-7xl space-y-4">
      <Link to="/beam-model" className="text-xs text-slate-500 hover:text-slate-700">&larr; Beam model</Link>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">Beamline asset synchronization</h1>
          <p className="text-sm text-slate-600">
            Model <span className="font-mono">{modelId}</span> · matcher {status.data.matcher} {status.data.matcher_version}.
            Proposals are never applied on their own: a person accepts or rejects them, and confirmed bindings are
            never replaced by a later sync.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" disabled={apply.isPending || s.auto_acceptable === 0}
                  onClick={() => apply.mutate({ accept_high_confidence: true, keep_proposals: true })}
                  className="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:bg-slate-300"
                  title="Confirm every proposal backed by a name, alias or convention, a compatible type, and ≥ 90% confidence">
            Accept high confidence ({s.auto_acceptable})
          </button>
          <button type="button" disabled={apply.isPending || selected.length === 0}
                  onClick={() => apply.mutate({ accept: selected.map(([component, asset]) => ({ component, asset })), keep_proposals: true })}
                  className="rounded bg-emerald-700 px-3 py-1.5 text-sm font-medium text-white disabled:bg-slate-300">
            Apply selected ({selected.length})
          </button>
          <button type="button" disabled={apply.isPending || selected.length === 0}
                  onClick={() => apply.mutate({ reject: selected.map(([component, asset]) => ({ component, asset })), keep_proposals: true })}
                  className="rounded border border-rose-300 px-3 py-1.5 text-sm text-rose-700 disabled:text-slate-300">
            Reject selected
          </button>
          <button type="button" onClick={refresh} className="rounded border border-slate-300 px-3 py-1.5 text-sm text-slate-700">
            Sync again
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">
        {([["Model components", s.model_components], ["Physical candidates", s.physical_candidates], ["Confirmed", s.confirmed],
           ["Proposed", s.proposed], ["Ambiguous", s.ambiguous], ["Unmatched", s.unmatched], ["Rejected", s.rejected],
           ["No asset expected", s.virtual_components]] as [string, number][]).map(([k, v]) => (
          <div key={k} className="rounded-lg border border-slate-200 bg-white p-2">
            <div className="text-[11px] text-slate-500">{k}</div>
            <div className="text-lg font-semibold tabular-nums text-slate-900">{v}</div>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap gap-1 text-xs">
        <button type="button" onClick={() => setFilter(null)}
                className={`rounded-full px-2.5 py-1 ${!filter ? "bg-slate-900 text-white" : "bg-white text-slate-700 ring-1 ring-slate-200"}`}>all</button>
        {GROUPS.filter((g) => (status.data!.groups[g] ?? 0) > 0).map((g) => (
          <button key={g} type="button" onClick={() => setFilter(g)}
                  className={`rounded-full px-2.5 py-1 ${filter === g ? "bg-slate-900 text-white" : "bg-white text-slate-700 ring-1 ring-slate-200"}`}>
            {g} <span className="opacity-60">{status.data!.groups[g]}</span>
          </button>
        ))}
        <span className="mx-1 text-slate-300">|</span>
        {STATUSES.map((st) => (
          <button key={st} type="button" onClick={() => setFilter(st)}
                  className={`rounded-full px-2.5 py-1 ${filter === st ? "bg-slate-900 text-white" : `${TONE[st]}`}`}>{st}</button>
        ))}
      </div>

      {result && (
        <div className="rounded border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
          {result.confirmed.length} confirmed, {result.rejected.length} rejected, {result.kept} kept for review.
          {result.problems.length > 0 && (
            <ul className="mt-1 list-disc pl-5 text-rose-800">{result.problems.map((p) => <li key={p}>{p}</li>)}</ul>
          )}
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs text-slate-500">
            <tr>
              <th className="px-3 py-2">Model</th><th>Type</th><th className="w-72">Candidate asset</th><th>Confidence</th>
              <th>Status</th><th>Since last sync</th><th>Evidence</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.component} className="border-t border-slate-100 align-top">
                <td className="px-3 py-2 font-mono text-xs">{p.component}
                  {p.s !== null && <div className="text-[11px] text-slate-400">s {p.s.toFixed(3)} m</div>}</td>
                <td className="py-2 text-xs">{p.type.replace(/_/g, " ")}</td>
                <td className="py-2">
                  {p.status === "confirmed" ? (
                    <span className="text-sm">{p.asset?.name ?? p.asset?.id}
                      <span className="ml-1 text-[11px] text-slate-500">{p.authority?.replace(/_/g, " ")}</span></span>
                  ) : p.candidates.length > 0 ? (
                    <select value={proposed(p)} onChange={(e) => setChoice({ ...choice, [p.component]: e.target.value })}
                            className={`w-full rounded border px-2 py-1 text-xs ${choice[p.component] ? "border-emerald-400 bg-emerald-50" : "border-slate-300"}`}>
                      <option value="">{p.status === "ambiguous" ? "choose…" : "—"}</option>
                      {p.candidates.map((c) => (
                        <option key={c.asset.id} value={c.asset.id}>{c.asset.name} ({Math.round(c.confidence * 100)}%)</option>
                      ))}
                    </select>
                  ) : <span className="text-slate-400">—</span>}
                  {p.notes.map((n) => <div key={n} className="mt-0.5 text-[11px] text-amber-800">{n}</div>)}
                </td>
                <td className="py-2 tabular-nums">{p.confidence !== null ? `${Math.round(p.confidence * 100)}%` : p.status === "ambiguous" ? "ambiguous" : "—"}
                  {p.auto_acceptable && <div className="text-[11px] text-emerald-700">auto-acceptable</div>}</td>
                <td className="py-2"><span className={`rounded px-2 py-0.5 text-xs ${TONE[p.status]}`}>{p.status}</span></td>
                <td className={`py-2 text-xs ${DIFF_TONE[p.diff] ?? "text-slate-400"}`}>{p.diff.replace(/_/g, " ")}</td>
                <td className="py-2 pr-3 text-[11px] text-slate-500">
                  {p.evidence.map((e) => e.replace(/_/g, " ")).join(" · ")}
                  {p.delta_s !== null && ` · Δs ${(p.delta_s * 1000).toFixed(0)} mm`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <p className="p-4 text-sm text-slate-500">Nothing here.</p>}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-lg border border-slate-200 bg-white p-3 text-sm">
          <h2 className="font-semibold text-slate-900">Physical assets with no model component</h2>
          <p className="text-xs text-slate-500">In this beamline's scope, matched to nothing: a pump, a support, a sensor the
            physics model does not need. Normal, and listed so nothing is missed.</p>
          <ul className="mt-2 columns-2 text-xs">
            {status.data.unmodelled_assets.map((a) => <li key={a.id}><Link to={`/assets/${a.id}`} className="text-indigo-700 hover:underline">{a.name}</Link> <span className="text-slate-400">{a.type}</span></li>)}
          </ul>
        </section>
        <section className="rounded-lg border border-slate-200 bg-white p-3 text-sm">
          <h2 className="font-semibold text-slate-900">Stale bindings</h2>
          <p className="text-xs text-slate-500">Confirmed bindings whose model component is gone. They are kept until a person ends them.</p>
          {status.data.stale_bindings.length === 0 ? <p className="mt-2 text-xs text-slate-400">None.</p> : (
            <ul className="mt-2 text-xs">{status.data.stale_bindings.map((b) => <li key={b.component + b.asset}>{b.component} → {b.asset}</li>)}</ul>
          )}
        </section>
      </div>
    </div>
  );
}
