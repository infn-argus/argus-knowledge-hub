/** Equipment readiness on the asset page: lifecycle with its allowed
 * transitions, custody and location with their history, compatible spares
 * for a position, and the record's audit trail. Every change is a decision
 * recorded in the ledger. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { auditApi, equipmentApi } from "../../api/client";
import type { AuditEntry, ValueHistory } from "../../api/ledgerTypes";
import { errorText } from "./LedgerPanels";
import { Empty } from "./ui";

const STATE_TONE: Record<string, string> = {
  Installed: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  "In stock": "bg-sky-50 text-sky-700 ring-sky-200",
  "In repair": "bg-amber-50 text-amber-800 ring-amber-200",
  Decommissioned: "bg-slate-100 text-slate-600 ring-slate-200",
  Scrapped: "bg-slate-100 text-slate-500 ring-slate-200",
};

function when(iso: string | null | undefined) {
  return iso ? new Date(iso).toLocaleString() : "now";
}

function show(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  return typeof v === "string" ? v : JSON.stringify(v);
}

function History({ title, data }: { title: string; data: ValueHistory }) {
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{title}</p>
      {data.history.length === 0 ? (
        <p className="text-sm text-slate-500">{show(data.current)}</p>
      ) : (
        <ol className="mt-1 space-y-1 border-l border-slate-200 pl-3">
          {[...data.history].reverse().map((h, i) => (
            <li key={i} className="text-sm">
              <span className={i === 0 ? "font-medium text-slate-900" : "text-slate-600"}>{show(h.value)}</span>
              <span className="ml-2 text-[11px] text-slate-500">
                {when(h.at)} → {h.until ? when(h.until) : "now"} · {h.via === "decision" ? h.by : `${h.via} (${h.by})`}
                {h.reason ? ` · ${h.reason}` : ""}
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

export function EquipmentPanel({ uid }: { uid: string }) {
  const queryClient = useQueryClient();
  const state = useQuery({ queryKey: ["equipment", uid], queryFn: () => equipmentApi.get(uid) });
  const [custodian, setCustodian] = useState("");
  const [reason, setReason] = useState("");
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["equipment", uid] });
    queryClient.invalidateQueries({ queryKey: ["hub-asset", uid] });
  };
  const move = useMutation({ mutationFn: (s: string) => equipmentApi.setLifecycle(uid, s, reason || undefined), onSuccess: refresh });
  const custody = useMutation({
    mutationFn: () => equipmentApi.setCustody(uid, custodian, reason || undefined),
    onSuccess: () => {
      setCustodian("");
      refresh();
    },
  });
  if (state.isLoading) return <Empty>Loading…</Empty>;
  if (!state.data) return <Empty>Not available.</Empty>;
  const e = state.data;
  const current = e.lifecycle.state;
  const error = move.error ?? custody.error;
  return (
    <div className="grid grid-cols-1 gap-5 pt-2 md:grid-cols-2">
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-slate-600">Lifecycle</span>
          <span className={`rounded px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${STATE_TONE[current ?? ""] ?? "bg-slate-50 text-slate-600 ring-slate-200"}`}>
            {current ?? "not set"}
          </span>
          {e.designated_spare && (
            <span className="rounded bg-indigo-50 px-2 py-0.5 text-xs text-indigo-700 ring-1 ring-inset ring-indigo-200">designated spare</span>
          )}
        </div>
        {e.lifecycle.installation && (
          <p className="text-xs text-slate-500">Installed follows from its current installation; swap or end it to change.</p>
        )}
        <div className="flex flex-wrap gap-2">
          {e.lifecycle.allowed.map((s) => (
            <button key={s} onClick={() => move.mutate(s)} className="rounded border border-slate-300 px-2.5 py-1 text-xs hover:bg-slate-50">
              → {s}
            </button>
          ))}
        </div>
        <input
          value={reason}
          onChange={(ev) => setReason(ev.target.value)}
          placeholder="Reason (kept with the decision)"
          className="w-full rounded border border-slate-300 px-2 py-1 text-xs"
        />
        <div className="flex gap-2">
          <input
            value={custodian}
            onChange={(ev) => setCustodian(ev.target.value)}
            placeholder="New custodian (e-mail or name)"
            className="flex-1 rounded border border-slate-300 px-2 py-1 text-xs"
          />
          <button
            disabled={!custodian || custody.isPending}
            onClick={() => custody.mutate()}
            className="rounded bg-slate-900 px-3 py-1 text-xs font-medium text-white disabled:opacity-50"
          >
            Hand over
          </button>
        </div>
        {error && <p className="text-sm text-red-600">{errorText(error)}</p>}
        <History title="Lifecycle history" data={e.lifecycle_history} />
      </div>
      <div className="space-y-4">
        <History title="Custody" data={e.custody} />
        <History title="Location" data={e.location} />
      </div>
    </div>
  );
}

export function PositionSpares({ uid }: { uid: string }) {
  const data = useQuery({ queryKey: ["position-spares", uid], queryFn: () => equipmentApi.positionSpares(uid) });
  if (!data.data || !data.data.basis) return null;
  const { basis, spares } = data.data;
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <p className="text-sm font-medium text-slate-900">
        Spares that fit{" "}
        <span className="text-xs font-normal text-slate-500">
          ({basis.product_model ? `product model ${basis.product_model}` : `type ${basis.type}`})
        </span>
      </p>
      {spares.length === 0 ? (
        <p className="mt-1 text-sm text-slate-500">No designated spare in the workspaces you can read.</p>
      ) : (
        <ul className="mt-1 divide-y divide-slate-100">
          {spares.map((s) => (
            <li key={s.uid} className="flex items-center justify-between gap-3 py-1.5 text-sm">
              <Link to={`/assets/${s.uid}`} className="min-w-0 truncate font-medium text-slate-900 hover:underline">
                {s.name}
              </Link>
              <span className="shrink-0 text-xs text-slate-500">
                {s.location ?? "location unknown"} ·{" "}
                {s.available ? <span className="text-emerald-700">available</span> : <span>{s.why_not}</span>}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const ENTRY_LABEL: Record<AuditEntry["type"], string> = {
  record: "record",
  decision: "decision",
  fact: "fact",
  identity: "identity",
  conflict: "review item",
};

export function AuditTrail({ uid }: { uid: string }) {
  const trail = useQuery({ queryKey: ["audit-trail", uid], queryFn: () => auditApi.trail(uid) });
  const [all, setAll] = useState(false);
  if (!trail.data || trail.data.length === 0) return null;
  const rows = [...trail.data].reverse();
  const shown = all ? rows : rows.slice(0, 15);
  return (
    <div className="mt-4 border-t border-slate-100 pt-3">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
        Audit trail — append-only, newest first
      </p>
      <ul className="mt-1 space-y-0.5">
        {shown.map((e, i) => (
          <li key={i} className="flex gap-2 text-xs">
            <span className="w-36 shrink-0 tabular-nums text-slate-400">{new Date(e.at).toLocaleString()}</span>
            <span className="w-20 shrink-0 text-slate-500">{ENTRY_LABEL[e.type]}</span>
            <span className="min-w-0 truncate text-slate-800">
              {e.kind}
              {e.predicate ? ` · ${e.predicate}` : ""}
              {e.value !== undefined && e.value !== null ? ` = ${show(e.value)}` : ""}
              {e.after !== undefined && e.after !== null && e.type === "record" ? ` → ${show(e.after)}` : ""}
              {e.actor ? ` · ${e.actor}` : ""}
              {e.cause ? <span className="text-slate-400"> · {e.cause}</span> : null}
            </span>
          </li>
        ))}
      </ul>
      {rows.length > 15 && (
        <button onClick={() => setAll(!all)} className="mt-1 text-xs text-indigo-700 hover:underline">
          {all ? "Show fewer" : `Show all ${rows.length}`}
        </button>
      )}
    </div>
  );
}
