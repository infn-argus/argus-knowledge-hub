/** Changing many records at once, safely: always previewed first, approved by
 * a second person above the threshold, applied as one ledger batch, and
 * undone as one. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { bulkApi } from "../../api/client";
import type { BulkChangeView } from "../../api/ledgerTypes";
import { errorText } from "../../components/hub/LedgerPanels";
import { Card, Empty } from "../../components/hub/ui";

const STATE_TEXT: Record<BulkChangeView["state"], string> = {
  previewed: "previewed — nothing changed yet",
  awaiting_approval: "waiting for a second person",
  applied: "applied",
  undone: "undone",
};

function show(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  return typeof v === "string" ? v : JSON.stringify(v);
}

export function BulkChangesPage() {
  const queryClient = useQueryClient();
  const list = useQuery({ queryKey: ["bulk-changes"], queryFn: bulkApi.list });
  const [selected, setSelected] = useState<string | null>(null);
  const [type, setType] = useState("");
  const [attribute, setAttribute] = useState("");
  const [equals, setEquals] = useState("");
  const [mode, setMode] = useState<"set" | "retire">("set");
  const [setName, setSetName] = useState("");
  const [setValue, setSetValue] = useState("");
  const [description, setDescription] = useState("");
  const refresh = (c: BulkChangeView) => {
    setSelected(c.id);
    queryClient.invalidateQueries({ queryKey: ["bulk-changes"] });
    queryClient.setQueryData(["bulk-change", c.id], c);
  };
  const preview = useMutation({
    mutationFn: () => {
      const targets: Record<string, unknown> = {};
      if (type) targets.type = type;
      if (attribute) targets.where = equals ? { attribute, equals } : { attribute };
      const spec =
        mode === "retire"
          ? { targets, retire: true }
          : { targets, set: [{ predicate: `attr:${setName}`, value: setValue }] };
      return bulkApi.preview(spec, description || undefined);
    },
    onSuccess: refresh,
  });
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Bulk changes</h1>
        <p className="mt-0.5 text-sm text-slate-500">
          Preview first; nothing is written until you apply. Above the threshold a second person approves. An applied
          change is one ledger batch and can be undone as one.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[22rem_1fr]">
        <div className="space-y-4">
          <Card title="New change">
            <div className="space-y-2 py-1 text-xs text-slate-600">
              <label className="block">
                Records of type
                <input value={type} onChange={(e) => setType(e.target.value)} placeholder="e.g. Ion Pump" className="mt-1 block w-full rounded border border-slate-300 px-2 py-1 text-sm" />
              </label>
              <div className="grid grid-cols-2 gap-2">
                <label className="block">
                  where attribute
                  <input value={attribute} onChange={(e) => setAttribute(e.target.value)} placeholder="argus_location" className="mt-1 block w-full rounded border border-slate-300 px-2 py-1 text-sm" />
                </label>
                <label className="block">
                  equals
                  <input value={equals} onChange={(e) => setEquals(e.target.value)} placeholder="(any value)" className="mt-1 block w-full rounded border border-slate-300 px-2 py-1 text-sm" />
                </label>
              </div>
              <div className="flex gap-3 pt-1">
                <label className="flex items-center gap-1">
                  <input type="radio" checked={mode === "set"} onChange={() => setMode("set")} /> set an attribute
                </label>
                <label className="flex items-center gap-1">
                  <input type="radio" checked={mode === "retire"} onChange={() => setMode("retire")} /> retire them
                </label>
              </div>
              {mode === "set" && (
                <div className="grid grid-cols-2 gap-2">
                  <input value={setName} onChange={(e) => setSetName(e.target.value)} placeholder="attribute" className="rounded border border-slate-300 px-2 py-1 text-sm" />
                  <input value={setValue} onChange={(e) => setSetValue(e.target.value)} placeholder="new value" className="rounded border border-slate-300 px-2 py-1 text-sm" />
                </div>
              )}
              <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Why (kept with every decision)" className="block w-full rounded border border-slate-300 px-2 py-1 text-sm" />
              {preview.isError && <p className="text-red-600">{errorText(preview.error)}</p>}
              <button
                disabled={(!type && !attribute) || (mode === "set" && !setName) || preview.isPending}
                onClick={() => preview.mutate()}
                className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
              >
                Preview
              </button>
            </div>
          </Card>
          <Card title="Recent changes">
            {(list.data ?? []).length === 0 ? (
              <Empty>None yet.</Empty>
            ) : (
              <ul className="divide-y divide-slate-100">
                {list.data!.map((c) => (
                  <li key={c.id}>
                    <button onClick={() => setSelected(c.id)} className="w-full py-2 text-left text-sm">
                      <span className="font-medium text-slate-900">{c.description ?? "Bulk change"}</span>
                      <span className="block text-xs text-slate-500">
                        {c.count} record(s) · {STATE_TEXT[c.state]} · {c.actor}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
        {selected ? <ChangePanel id={selected} onChanged={refresh} /> : <Empty>Preview a change to see it here.</Empty>}
      </div>
    </div>
  );
}

function ChangePanel({ id, onChanged }: { id: string; onChanged: (c: BulkChangeView) => void }) {
  const change = useQuery({ queryKey: ["bulk-change", id], queryFn: () => bulkApi.get(id) });
  const apply = useMutation({ mutationFn: () => bulkApi.apply(id), onSuccess: onChanged });
  const approve = useMutation({ mutationFn: () => bulkApi.approve(id), onSuccess: onChanged });
  const undo = useMutation({ mutationFn: () => bulkApi.undo(id), onSuccess: onChanged });
  if (!change.data) return <Empty>Loading…</Empty>;
  const c = change.data;
  const error = [apply, approve, undo].find((m) => m.isError)?.error;
  return (
    <Card title={c.description ?? "Bulk change"} action={<span className="text-xs text-slate-500">{STATE_TEXT[c.state]}</span>}>
      <p className="text-sm text-slate-700">
        {c.count} record(s) would change.{" "}
        {c.needs_approval && (
          <span className="text-amber-800">More than {c.threshold}: a second person must approve it.</span>
        )}
        {c.approved_by && <span className="text-emerald-700"> Approved by {c.approved_by}.</span>}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        {c.state === "previewed" && (
          <button onClick={() => apply.mutate()} className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white">
            {c.needs_approval ? "Submit for approval" : `Apply to ${c.count} record(s)`}
          </button>
        )}
        {c.state === "awaiting_approval" && (
          <button onClick={() => approve.mutate()} className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white">
            Approve and apply
          </button>
        )}
        {c.state === "applied" && (
          <button onClick={() => undo.mutate()} className="rounded-md border border-red-200 px-3 py-1.5 text-xs text-red-700">
            Undo the whole change
          </button>
        )}
      </div>
      {error && <p className="mt-2 text-sm text-red-600">{errorText(error)}</p>}
      <table className="mt-3 w-full text-sm">
        <thead>
          <tr className="border-b border-slate-100 text-left text-[11px] uppercase tracking-wide text-slate-400">
            <th className="py-1.5 font-medium">Record</th>
            <th className="py-1.5 font-medium">Field</th>
            <th className="py-1.5 font-medium">Before</th>
            <th className="py-1.5 font-medium">After</th>
          </tr>
        </thead>
        <tbody>
          {c.preview.flatMap((r) =>
            r.changes.map((ch, i) => (
              <tr key={`${r.uid}-${i}`} className="border-b border-slate-50">
                <td className="py-1.5">
                  <Link to={`/assets/${r.uid}`} className="text-slate-900 hover:underline">
                    {r.name}
                  </Link>
                  <span className="ml-1 font-mono text-[11px] text-slate-400">{r.key}</span>
                </td>
                <td className="py-1.5 font-mono text-xs">{ch.predicate.replace(/^attr:/, "")}</td>
                <td className="py-1.5 text-slate-500">{show(ch.before)}</td>
                <td className="py-1.5 font-medium text-slate-900">{show(ch.after)}</td>
              </tr>
            )),
          )}
        </tbody>
      </table>
    </Card>
  );
}
