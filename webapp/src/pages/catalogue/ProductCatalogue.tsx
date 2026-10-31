import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { catalogueCollectionsApi, glpiMatchesApi, workspacesApi, type GlpiMatchReport } from "../../api/client";
import { problem } from "./catalogueText";

const STATUS: Record<string, string> = { catalogue: "From a collection", local: "Local", retired: "Retired" };

function Facet({ label, value, counts, onChange, names }: {
  label: string; value: string; counts: Record<string, number> | undefined; onChange: (v: string) => void;
  names?: Record<string, string>;
}) {
  const entries = Object.entries(counts ?? {}).sort(([a], [b]) => a.localeCompare(b));
  return (
    <label className="text-xs text-slate-500">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)}
              className="mt-0.5 block w-44 rounded border border-slate-300 px-2 py-1 text-sm text-slate-900">
        <option value="">All</option>
        {entries.map(([k, n]) => <option key={k} value={k === "—" ? "" : k}>{names?.[k] ?? k} ({n})</option>)}
      </select>
    </label>
  );
}

/** GLPI's devices in the current workspace: propose their catalogue models for review, and list the GLPI
 *  models nothing matches (candidates for new entries). */
export function GlpiMatches({ workspaceId }: { workspaceId?: string } = {}) {
  const [report, setReport] = useState<GlpiMatchReport | null>(null);
  const run = useMutation({ mutationFn: () => glpiMatchesApi.run(workspaceId), onSuccess: setReport });
  const unmatched = report?.unmatched;
  return (
    <section aria-label="GLPI devices" className="rounded border border-slate-200 bg-white p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">GLPI devices in {workspaceId ?? "this workspace"}</h2>
          <p className="text-xs text-slate-500">
            Proposes the catalogue model GLPI's manufacturer and model name, for each device that has none. Each
            proposal waits in the <Link to="/review" className="text-sky-800 underline">review queue</Link> until someone
            accepts or rejects it.
          </p>
        </div>
        <button type="button" disabled={run.isPending} onClick={() => run.mutate()}
                className="rounded border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50">
          {run.isPending ? "Matching…" : "Propose models"}
        </button>
      </div>
      {run.isError && <p className="mt-2 whitespace-pre-line text-sm text-red-600">{problem(run.error)}</p>}
      {report && (
        <div className="mt-2 space-y-1 text-sm">
          <p>
            {report.proposals} proposal{report.proposals === 1 ? "" : "s"} ({report.exact} exact, {report.near} near)
            {report.status === "unchanged" && " — the same as last time"}.
          </p>
          {report.ambiguous.length > 0 && (
            <p className="text-amber-800">
              Not proposed, two models fit equally:{" "}
              {report.ambiguous.map((a) => `${a.manufacturer} ${a.model} (${a.candidates.join(" or ")})`).join("; ")}
            </p>
          )}
          {unmatched && unmatched.length > 0 && (
            <div>
              <p className="text-slate-600">No catalogue model matches these — candidates for new entries:</p>
              <ul className="text-xs text-slate-600">
                {unmatched.map((u) => <li key={`${u.manufacturer}|${u.model}`}>{u.manufacturer} {u.model}: {u.units} unit{u.units === 1 ? "" : "s"}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

/** The shared Product Models: from a collection (with its catalogue id), made here, or retired. */
export function ProductCataloguePage() {
  const [q, setQ] = useState("");
  const [deviceClass, setDeviceClass] = useState("");
  const [vendor, setVendor] = useState("");
  const [status, setStatus] = useState("");
  const [collection, setCollection] = useState("");
  const params = { q, device_class: deviceClass, vendor, status, collection };
  const found = useQuery({ queryKey: ["catalogue-models", params], queryFn: () => catalogueCollectionsApi.models(params) });
  const me = useQuery({ queryKey: ["me"], queryFn: workspacesApi.me });

  return (
    <div className="max-w-6xl space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Product catalogue</h1>
          <p className="mt-1 text-sm text-slate-500">
            The Product Models every workspace can point at. A model from a collection carries its catalogue id;
            a local one was made here, and can be proposed for a collection.
          </p>
        </div>
        {(me.data?.is_admin || me.data?.catalogue_maintainer) && (
          <Link to="/admin/catalogue" className="text-sm font-medium text-sky-800 underline">Collections and updates</Link>
        )}
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded border border-slate-200 bg-white p-3">
        <label className="text-xs text-slate-500">
          Search
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name, code, vendor, catalogue id"
                 className="mt-0.5 block w-64 rounded border border-slate-300 px-2 py-1 text-sm text-slate-900" />
        </label>
        <Facet label="Device class" value={deviceClass} onChange={setDeviceClass} counts={found.data?.facets.device_class} />
        <Facet label="Vendor" value={vendor} onChange={setVendor} counts={found.data?.facets.vendor} />
        <Facet label="Source" value={status} onChange={setStatus} counts={found.data?.facets.status} names={STATUS} />
        <Facet label="Collection" value={collection} onChange={setCollection} counts={found.data?.facets.collection} />
      </div>

      {found.isError && <p className="whitespace-pre-line text-sm text-red-600">{problem(found.error)}</p>}
      {found.isLoading && <p className="text-sm text-slate-500">Loading…</p>}
      {found.data && (
        <>
          <p className="text-xs text-slate-500">{found.data.total} model{found.data.total === 1 ? "" : "s"}</p>
          <table className="w-full rounded border border-slate-200 bg-white text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr><th className="px-3 py-2">Model</th><th className="px-3 py-2">Vendor</th>
                <th className="px-3 py-2">Model code</th><th className="px-3 py-2">Device class</th>
                <th className="px-3 py-2">Source</th><th className="px-3 py-2 text-right">Units</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {found.data.models.length === 0 && (
                <tr><td colSpan={6} className="px-3 py-3 text-slate-500">No model matches.</td></tr>
              )}
              {found.data.models.map((m) => (
                <tr key={m.uid}>
                  <td className="px-3 py-2">
                    <Link to={`/catalogue/models/${m.uid}`} className="font-medium text-sky-800 hover:underline">{m.name}</Link>
                    {m.review && <span className="ml-1 text-xs text-amber-700" title="Waiting for review">● review</span>}
                    <span className="block font-mono text-xs text-slate-400">{m.key}</span>
                  </td>
                  <td className="px-3 py-2 text-slate-700">{m.vendor ?? "—"}</td>
                  <td className="px-3 py-2 font-mono text-xs">{m.model_code ?? "—"}</td>
                  <td className="px-3 py-2 text-slate-700">{m.device_class ?? "—"}</td>
                  <td className="px-3 py-2">
                    {m.catalogue_id
                      ? <><span className="font-mono text-xs">{m.catalogue_id}</span>
                          <span className="block text-xs text-slate-500">{m.collection} {m.version}
                            {m.status === "retired" && <span className="ml-1 text-red-700">retired</span>}</span></>
                      : <span className="text-xs text-slate-500">{m.status === "retired" ? "retired" : "local"}</span>}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">{m.units}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
