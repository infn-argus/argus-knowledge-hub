import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { controlBindingApi, type ControlBindingReport } from "../../api/client";

/** Which hardware each control channel drives: proposed from the naming convention and the network,
 * confirmed here by a person (Controls own these mappings). An IOC then `drives` the confirmed hardware. */
export function ControlBindingsPage() {
  const queryClient = useQueryClient();
  const [report, setReport] = useState<ControlBindingReport | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [notice, setNotice] = useState<string | null>(null);
  const proposals = useQuery({ queryKey: ["control-bindings"], queryFn: controlBindingApi.list });
  const refresh = () => {
    setSelected(new Set());
    queryClient.invalidateQueries({ queryKey: ["control-bindings"] });
  };
  const propose = useMutation({
    mutationFn: controlBindingApi.propose,
    onSuccess: (r) => {
      setReport(r);
      refresh();
    },
    onError: (e) => setNotice((e as Error).message),
  });
  const decide = useMutation({
    mutationFn: controlBindingApi.decide,
    onSuccess: (r, v) => {
      setNotice(`${r.decided} ${v.accept ? "confirmed" : "rejected"}.`);
      refresh();
    },
    onError: (e) => setNotice((e as Error).message),
  });
  const rows = proposals.data ?? [];
  const toggle = (id: string) =>
    setSelected((cur) => {
      const next = new Set(cur);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const confident = rows.filter((p) => (p.confidence ?? 0) >= 0.9).length;

  return (
    <div className="max-w-5xl">
      <h1 className="text-2xl font-semibold text-slate-900">Control channels ↔ hardware</h1>
      <p className="mt-1 text-sm text-slate-500">
        Which physical unit each control channel acts on, proposed from the naming convention (zone, function code
        and number: <span className="font-mono">FI33TRB01</span> ↔ <span className="font-mono">FI33-V-PMP-TRB-001</span>)
        and from the network (an Ethernet instrument's address). Nothing is bound until you confirm it. Once it is,
        the IOC that provides the channel <em>drives</em> that unit, in the graph and in the impact analysis.
      </p>

      <div className="mt-5 flex flex-wrap items-center gap-2">
        <button
          onClick={() => propose.mutate()}
          disabled={propose.isPending}
          className="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {propose.isPending ? "Looking…" : "Find matches"}
        </button>
        <button
          onClick={() => decide.mutate({ accept: true, min_confidence: 0.9 })}
          disabled={!confident || decide.isPending}
          className="rounded border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          Confirm all ≥ 90% ({confident})
        </button>
        <button
          onClick={() => decide.mutate({ accept: true, claim_ids: [...selected] })}
          disabled={!selected.size || decide.isPending}
          className="rounded border border-emerald-300 px-3 py-1.5 text-sm text-emerald-800 hover:bg-emerald-50 disabled:opacity-50"
        >
          Confirm selected ({selected.size})
        </button>
        <button
          onClick={() => decide.mutate({ accept: false, claim_ids: [...selected] })}
          disabled={!selected.size || decide.isPending}
          className="rounded border border-red-200 px-3 py-1.5 text-sm text-red-700 hover:bg-red-50 disabled:opacity-50"
        >
          Reject selected
        </button>
      </div>
      {notice && (
        <p className="mt-3 rounded bg-slate-100 px-3 py-2 text-sm text-slate-700">
          {notice}{" "}
          <button onClick={() => setNotice(null)} className="text-slate-400 hover:text-slate-700">
            ×
          </button>
        </p>
      )}

      {report && (
        <div className="mt-4 rounded-lg border border-slate-200 bg-white p-3 text-sm">
          <p>
            <strong>{report.proposed}</strong> proposals: {report.by_tag} by name, {report.by_host} by network address
            {report.already_bound ? `; ${report.already_bound} channels already act on something` : ""}.
          </p>
          {report.ambiguous.length > 0 && (
            <div className="mt-2">
              <p className="text-xs font-medium uppercase text-amber-700">More than one candidate: decide by hand</p>
              {report.ambiguous.map((a) => (
                <p key={a.uid} className="text-xs text-slate-600">
                  <Link to={`/assets/${a.uid}`} className="font-mono text-indigo-600 hover:underline">
                    {a.device}
                  </Link>{" "}
                  → {a.candidates.map((c) => c.name).join(" or ")}
                </p>
              ))}
            </div>
          )}
          {report.unmatched.length > 0 && (
            <p className="mt-2 text-xs text-slate-500">
              No candidate: {report.unmatched.map((u) => u.device).join(", ")}
            </p>
          )}
        </div>
      )}

      <div className="mt-4 overflow-hidden rounded-lg border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="w-8 px-3 py-2">
                <input
                  type="checkbox"
                  checked={rows.length > 0 && selected.size === rows.length}
                  onChange={(e) => setSelected(e.target.checked ? new Set(rows.map((r) => r.claim_id)) : new Set())}
                />
              </th>
              <th className="px-3 py-2">Channel</th>
              <th className="px-3 py-2">Relation</th>
              <th className="px-3 py-2">Hardware</th>
              <th className="px-3 py-2">Why</th>
              <th className="px-3 py-2">Confidence</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((p) => (
              <tr key={p.claim_id}>
                <td className="px-3 py-2">
                  <input type="checkbox" checked={selected.has(p.claim_id)} onChange={() => toggle(p.claim_id)} />
                </td>
                <td className="px-3 py-2">
                  <Link to={`/assets/${p.subject.uid}`} className="font-mono text-xs text-indigo-600 hover:underline">
                    {p.subject.name}
                  </Link>
                  <div className="text-[11px] text-slate-400">{p.subject.type}</div>
                </td>
                <td className="px-3 py-2 font-mono text-xs text-slate-600">{p.predicate}</td>
                <td className="px-3 py-2">
                  {p.target && (
                    <>
                      <Link to={`/assets/${p.target.uid}`} className="font-mono text-xs text-indigo-600 hover:underline">
                        {p.target.name}
                      </Link>
                      <div className="text-[11px] text-slate-400">{p.target.type}</div>
                    </>
                  )}
                </td>
                <td className="px-3 py-2 text-xs text-slate-500">{String(p.evidence?.matched_on ?? "")}</td>
                <td className="px-3 py-2 text-xs tabular-nums text-slate-600">
                  {p.confidence != null ? `${Math.round(p.confidence * 100)}%` : ""}
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={6} className="px-3 py-6 text-center text-slate-400">
                  {proposals.isLoading ? "Loading…" : "No proposals waiting. Use “Find matches”."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
