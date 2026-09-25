/** §5.5: governing Other Equipment. The class vocabulary, the report the
 * catalogue reads monthly, promotion reviews and promotion. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, catalogueApi } from "../../api/client";
import type { ClassReview, EquipmentClassReport } from "../../api/ledgerTypes";
import { errorText } from "../../components/hub/LedgerPanels";
import { Card } from "../../components/hub/ui";

const STATUS_TONE: Record<string, string> = {
  active: "bg-emerald-50 text-emerald-700",
  promoted: "bg-sky-50 text-sky-800",
  deprecated: "bg-slate-100 text-slate-500",
};

export function EquipmentClassesPage() {
  const queryClient = useQueryClient();
  const refresh = () => {
    for (const k of ["equipment-classes", "class-report", "class-reviews"]) queryClient.invalidateQueries({ queryKey: [k] });
  };
  const classes = useQuery({ queryKey: ["equipment-classes"], queryFn: catalogueApi.classes });
  const report = useQuery({ queryKey: ["class-report"], queryFn: catalogueApi.report, retry: false });
  const reviews = useQuery({ queryKey: ["class-reviews"], queryFn: catalogueApi.reviews });
  const isCatalogue = !(report.error instanceof ApiError && report.error.status === 403);
  const [newClass, setNewClass] = useState("");
  const [ask, setAsk] = useState({ cls: "", attribute: "", reason: "" });
  const add = useMutation({ mutationFn: () => catalogueApi.addClass(newClass), onSuccess: () => { setNewClass(""); refresh(); } });
  const request = useMutation({
    mutationFn: () => catalogueApi.requestAttribute(ask.cls, ask.attribute, ask.reason || undefined),
    onSuccess: () => { setAsk({ cls: ask.cls, attribute: "", reason: "" }); refresh(); },
  });
  const run = useMutation({ mutationFn: catalogueApi.runThresholds, onSuccess: refresh });
  const active = (classes.data ?? []).filter((c) => c.status === "active");
  const error = [add, request, run].find((m) => m.isError)?.error;
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Equipment classes</h1>
        <p className="mt-0.5 text-sm text-slate-500">
          Equipment no type of its own describes is <em>Other Equipment</em>, with a class. A class that grows is promoted to a
          type: its objects are retyped in place and the class is no longer assignable.
        </p>
      </div>
      {error && <p className="text-sm text-red-600">{errorText(error)}</p>}

      {report.data && <ReportCard r={report.data} />}

      <Card title="Promotion reviews" action={isCatalogue ? (
        <button onClick={() => run.mutate()} className="rounded border border-slate-300 px-2 py-0.5 text-xs">Check the thresholds</button>
      ) : undefined}>
        <ul className="divide-y divide-slate-100 text-sm">
          {(reviews.data ?? []).map((r) => <ReviewRow key={r.id} r={r} canDecide={isCatalogue} onDone={refresh} />)}
          {reviews.data?.length === 0 && <li className="py-2 text-sm text-slate-500">No review yet.</li>}
        </ul>
      </Card>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card title="Vocabulary">
          <ul className="divide-y divide-slate-100 text-sm">
            {(classes.data ?? []).map((c) => (
              <li key={c.name} className="flex items-center justify-between py-1.5">
                <span>{c.name}</span>
                <span className={`rounded px-2 py-0.5 text-xs ${STATUS_TONE[c.status]}`}>
                  {c.status === "promoted" ? `type: ${c.promoted_type}` : c.status}
                </span>
              </li>
            ))}
          </ul>
          {isCatalogue && (
            <div className="mt-2 flex gap-2 text-xs">
              <input value={newClass} onChange={(e) => setNewClass(e.target.value)} placeholder="New class" className="flex-1 rounded border border-slate-300 px-2 py-1" />
              <button disabled={!newClass} onClick={() => add.mutate()} className="rounded bg-slate-900 px-2 py-1 font-medium text-white disabled:opacity-40">Add</button>
            </div>
          )}
        </Card>
        <Card title="Ask for an attribute">
          <p className="py-1 text-xs text-slate-500">Three requested attributes open a promotion review.</p>
          <div className="space-y-2 text-xs">
            <select value={ask.cls} onChange={(e) => setAsk({ ...ask, cls: e.target.value })} className="w-full rounded border border-slate-300 px-2 py-1">
              <option value="">Class…</option>
              {active.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
            </select>
            <input value={ask.attribute} onChange={(e) => setAsk({ ...ask, attribute: e.target.value })} placeholder="Attribute (e.g. Bandwidth)" className="w-full rounded border border-slate-300 px-2 py-1" />
            <input value={ask.reason} onChange={(e) => setAsk({ ...ask, reason: e.target.value })} placeholder="What for (optional)" className="w-full rounded border border-slate-300 px-2 py-1" />
            <button disabled={!ask.cls || !ask.attribute} onClick={() => request.mutate()} className="rounded bg-slate-900 px-2 py-1 font-medium text-white disabled:opacity-40">Ask</button>
          </div>
        </Card>
      </div>
    </div>
  );
}

function ReportCard({ r }: { r: EquipmentClassReport }) {
  const rows = r.classes.filter((c) => c.objects > 0 || c.triggers.length > 0 || c.requested_attributes.length > 0);
  return (
    <Card title="Report (§5.5)" action={<span className="text-xs text-slate-400">{new Date(r.at).toLocaleString()}</span>}>
      <p className={`mb-2 rounded px-3 py-2 text-sm ${r.unclassified.alert ? "bg-amber-50 text-amber-900" : "bg-slate-50 text-slate-600"}`}>
        {r.unclassified.alert ? "Alert: " : ""}
        {r.unclassified.count} Unclassified of {r.equipment} Equipment ({(r.unclassified.share * 100).toFixed(1)} %). The alert is
        raised at {r.unclassified.rule}.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-400">
            <tr>
              <th className="py-1 font-normal">Class</th>
              <th className="text-right font-normal">Objects</th>
              <th className="text-right font-normal">Workspaces</th>
              <th className="font-normal">Sources</th>
              <th className="text-right font-normal">In tickets</th>
              <th className="text-right font-normal">Causal</th>
              <th className="font-normal">Asked for / written in descriptions</th>
              <th className="font-normal">Thresholds met</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 align-top">
            {rows.map((c) => (
              <tr key={c.class}>
                <td className="py-1.5 pr-3">{c.class}</td>
                <td className="text-right tabular-nums">{c.objects}</td>
                <td className="text-right tabular-nums">{Object.keys(c.workspaces).length}</td>
                <td className="whitespace-nowrap pl-3 text-xs text-slate-500">{Object.entries(c.sources).map(([s, n]) => `${s} ${n}`).join(", ")}</td>
                <td className="text-right tabular-nums">{c.in_tickets || "·"}</td>
                <td className="text-right tabular-nums">{c.causal || "·"}</td>
                <td className="pl-3 text-xs text-slate-500">
                  {c.requested_attributes.join(", ")}
                  {c.description_keys.length > 0 && (
                    <span className="block text-slate-400">{c.description_keys.map((k) => `${k.key} ×${k.count}`).join(", ")}</span>
                  )}
                </td>
                <td className="text-xs text-amber-700">{c.triggers.map((t) => t.text).join("; ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function ReviewRow({ r, canDecide, onDone }: { r: ClassReview; canDecide: boolean; onDone: () => void }) {
  const [typeName, setTypeName] = useState(r.class);
  const promote = useMutation({
    mutationFn: (reason: string) => catalogueApi.promote(r.class, typeName, reason),
    onSuccess: onDone,
  });
  const decline = useMutation({ mutationFn: (reason: string) => catalogueApi.decline(r.id, reason), onSuccess: onDone });
  return (
    <li className="py-2">
      <div className="flex items-center gap-2">
        <span className="font-medium text-slate-800">{r.class}</span>
        <span className="text-xs text-slate-500">{r.status}</span>
        <span className="ml-auto text-xs text-slate-400">{new Date(r.opened_at).toLocaleDateString()}</span>
      </div>
      <p className="text-xs text-amber-700">{r.triggers.map((t) => t.text).join("; ")}</p>
      {r.reason && <p className="text-xs text-slate-500">{r.decided_by}: {r.reason}</p>}
      {canDecide && r.status === "open" && (
        <div className="mt-1 flex flex-wrap gap-2 text-xs">
          <input value={typeName} onChange={(e) => setTypeName(e.target.value)} placeholder="New type name" className="rounded border border-slate-300 px-2 py-1" />
          <button onClick={() => { const why = prompt(`Why promote ${r.class} to the type ${typeName}?`); if (why) promote.mutate(why); }}
                  className="rounded bg-slate-900 px-2 py-1 font-medium text-white">Promote</button>
          <button onClick={() => { const why = prompt("Why not now?"); if (why) decline.mutate(why); }}
                  className="rounded border border-slate-300 px-2 py-1">Decline</button>
        </div>
      )}
      {(promote.isError || decline.isError) && <p className="text-xs text-red-600">{errorText(promote.error ?? decline.error)}</p>}
      {promote.data && <p className="text-xs text-emerald-700">{promote.data.retyped} object(s) are now {promote.data.type}.</p>}
    </li>
  );
}
