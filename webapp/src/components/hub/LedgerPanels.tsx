/** Installation history and provenance: what was installed where and when,
 * and why every value is what it is. Nothing here edits a value directly;
 * every action is a decision recorded in the ledger. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, assetsApi, ledgerApi } from "../../api/client";
import type { FactContributor, InstallationView, TemporalValue } from "../../api/ledgerTypes";
import { AssetPicker } from "../AssetPicker";
import { Empty } from "./ui";

export const INSTALLABLE = new Set([
  "Equipment Position", "Motion Axis", "Mirror", "Dipole", "Quadrupole", "Sextupole", "Corrector",
  "Solenoid", "Accelerating Structure", "RF Gun", "Beam Position Monitor",
]);
const NOT_EQUIPMENT = new Set([...INSTALLABLE, "Installation", "IOC", "Control Device", "Access Point",
  "Communication Path", "Bus Segment", "Facility", "Section", "Product Model", "Vendor"]);

export function formatTemporal(v: TemporalValue | null | undefined, role: "from" | "until"): string {
  if (!v) return role === "until" ? "now" : "not scheduled";
  const d = (iso?: string) => (iso ? new Date(iso) : null);
  switch (v.kind) {
    case "open":
      return "now";
    case "unscheduled":
      return "not scheduled";
    case "before_records":
      return `before records (by ${d(v.bound)?.toLocaleDateString()})`;
    case "unknown_past":
      return `ended, date unknown (by ${d(v.bound)?.toLocaleDateString()})`;
    case "range":
      return `between ${d(v.earliest)?.toLocaleDateString()} and ${d(v.latest)?.toLocaleDateString()}`;
    default: {
      const at = d(v.nominal)!;
      if (v.precision === "year") return String(at.getUTCFullYear());
      if (v.precision === "month") return at.toLocaleDateString(undefined, { year: "numeric", month: "short", timeZone: "UTC" });
      if (v.precision === "day") return at.toLocaleDateString(undefined, { timeZone: "UTC" });
      return at.toLocaleString();
    }
  }
}

const STATUS_STYLE: Record<string, string> = {
  Confirmed: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  Proposed: "bg-amber-50 text-amber-800 ring-amber-200",
  Rejected: "bg-slate-100 text-slate-500 ring-slate-200",
  Withdrawn: "bg-slate-100 text-slate-500 ring-slate-200",
};

export function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    const d = (e.body as { detail?: { error?: string } | string } | null)?.detail;
    if (typeof d === "string") return d;
    if (d && typeof d === "object" && d.error) return d.error;
  }
  return "The request failed.";
}

export function InstallationHistory({ uid, type }: { uid: string; type: string }) {
  const queryClient = useQueryClient();
  const isPosition = INSTALLABLE.has(type);
  const query = isPosition ? { position_uid: uid } : { asset_uid: uid };
  const history = useQuery({ queryKey: ["installations", uid], queryFn: () => ledgerApi.installations(query) });
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["installations"] });
    queryClient.invalidateQueries({ queryKey: ["hub-asset"] });
    queryClient.invalidateQueries({ queryKey: ["ledger-review"] });
  };
  const confirm = useMutation({ mutationFn: (id: string) => ledgerApi.confirmInstallation(id), onSuccess: refresh });
  const reject = useMutation({ mutationFn: (id: string) => ledgerApi.rejectInstallation(id), onSuccess: refresh });
  const rows = history.data ?? [];

  return (
    <div className="space-y-3 pt-2">
      <p className="text-xs text-slate-500">
        {isPosition
          ? "Which unit occupied this position, and when. A unit is in one place at a time; dates carry their precision."
          : "Where this unit has been installed, and when."}
      </p>
      {history.isLoading ? (
        <Empty>Loading…</Empty>
      ) : rows.length === 0 ? (
        <Empty>{isPosition ? "No installation recorded at this position." : "This unit has never been installed."}</Empty>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 text-left text-[11px] uppercase tracking-wide text-slate-400">
              <th className="py-1.5 font-medium">{isPosition ? "Unit" : "Position"}</th>
              <th className="py-1.5 font-medium">From</th>
              <th className="py-1.5 font-medium">Until</th>
              <th className="py-1.5 font-medium">Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((r: InstallationView) => {
              const other = isPosition ? r.asset : r.position;
              return (
                <tr key={r.uid} className="border-b border-slate-50 last:border-0 align-top">
                  <td className="py-2">
                    {other ? (
                      <Link to={`/assets/${other.uid}`} className="font-medium text-slate-900 hover:underline">
                        {other.name}
                      </Link>
                    ) : (
                      "—"
                    )}
                    <div className="font-mono text-[11px] text-slate-400">{r.key}</div>
                  </td>
                  <td className="py-2 text-slate-700">{formatTemporal(r.valid_from, "from")}</td>
                  <td className="py-2 text-slate-700">
                    {formatTemporal(r.valid_until, "until")}
                    {r.removal_reason && <div className="text-[11px] text-slate-500">{r.removal_reason}</div>}
                  </td>
                  <td className="py-2">
                    <span className={`rounded px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-inset ${STATUS_STYLE[r.status] ?? ""}`}>
                      {r.status}
                    </span>
                    {r.status === "Confirmed" && (
                      <span className="ml-1.5 text-[11px] text-slate-500">
                        {r.temporal_state}
                        {r.temporal_certainty === "possible" ? " (uncertain)" : ""}
                      </span>
                    )}
                  </td>
                  <td className="py-2 text-right">
                    {r.status === "Proposed" && (
                      <span className="flex justify-end gap-1.5">
                        <button
                          onClick={() => confirm.mutate(r.uid)}
                          className="rounded bg-emerald-600 px-2 py-1 text-xs font-medium text-white hover:bg-emerald-700"
                        >
                          Confirm
                        </button>
                        <button
                          onClick={() => reject.mutate(r.uid)}
                          className="rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50"
                        >
                          Reject
                        </button>
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      {(confirm.isError || reject.isError) && (
        <p className="text-sm text-red-600">{errorText(confirm.error ?? reject.error)}</p>
      )}
      {isPosition && <SwapForm positionUid={uid} onDone={refresh} />}
    </div>
  );
}

function SwapForm({ positionUid, onDone }: { positionUid: string; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [unit, setUnit] = useState<string | null>(null);
  const [at, setAt] = useState(() => new Date().toISOString().slice(0, 16));
  const [precision, setPrecision] = useState("instant");
  const [reason, setReason] = useState("Failure");
  const assets = useQuery({ queryKey: ["assets"], queryFn: () => assetsApi.list(), enabled: open });
  const swap = useMutation({
    mutationFn: () =>
      ledgerApi.swap({ position_uid: positionUid, new_asset_uid: unit!, at: new Date(at).toISOString(), precision, reason }),
    onSuccess: () => {
      setOpen(false);
      setUnit(null);
      onDone();
    },
  });
  if (!open)
    return (
      <button
        onClick={() => setOpen(true)}
        className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
      >
        Replace unit…
      </button>
    );
  const equipment = (assets.data ?? []).filter((a) => !NOT_EQUIPMENT.has(a.type));
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
      <p className="text-sm font-medium text-slate-900">Replace the unit at this position</p>
      <p className="mt-0.5 text-xs text-slate-500">
        Ends the current installation and starts the new one at the same instant, in one step.
      </p>
      <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
        <label className="text-xs text-slate-600">
          New unit
          <AssetPicker options={equipment} value={unit} onChange={setUnit} placeholder="Search equipment…" />
        </label>
        <label className="text-xs text-slate-600">
          When
          <div className="mt-1 flex gap-2">
            <input
              type="datetime-local"
              value={at}
              onChange={(e) => setAt(e.target.value)}
              className="flex-1 rounded border border-slate-300 px-2 py-1 text-sm"
            />
            <select value={precision} onChange={(e) => setPrecision(e.target.value)} className="rounded border border-slate-300 px-2 text-sm">
              <option value="instant">exact</option>
              <option value="day">that day</option>
              <option value="month">that month</option>
            </select>
          </div>
        </label>
        <label className="text-xs text-slate-600">
          Reason the old unit came out
          <select value={reason} onChange={(e) => setReason(e.target.value)} className="mt-1 block w-full rounded border border-slate-300 px-2 py-1 text-sm">
            {["Failure", "Maintenance", "Upgrade", "Relocation", "Decommissioning", "Unknown"].map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        </label>
      </div>
      {swap.isError && <p className="mt-2 text-sm text-red-600">{errorText(swap.error)}</p>}
      <div className="mt-3 flex gap-2">
        <button
          disabled={!unit || swap.isPending}
          onClick={() => swap.mutate()}
          className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          Record the swap
        </button>
        <button onClick={() => setOpen(false)} className="rounded-md border border-slate-300 px-3 py-1.5 text-xs">
          Cancel
        </button>
      </div>
    </div>
  );
}

const CONTRIBUTOR_STYLE: Record<string, string> = {
  accepted: "text-emerald-700",
  confirmed: "text-emerald-700",
  proposed: "text-amber-700",
  outranked: "text-slate-500",
  rejected: "text-red-700",
  withdrawn: "text-slate-400",
  superseded: "text-slate-400",
  pending: "text-amber-700",
  ignored: "text-slate-400",
};

function show(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "object" && value && "kind" in (value as object)) {
    const t = value as TemporalValue;
    return formatTemporal(t, t.kind === "open" || t.kind === "unknown_past" ? "until" : "from");
  }
  if (typeof value === "object" && value && "ref" in (value as object)) return String((value as { ref: string }).ref);
  return JSON.stringify(value);
}

function describe(c: FactContributor): string {
  if (c.kind === "decision") return `${c.decision} by ${c.actor}${c.reason ? ` — ${c.reason}` : ""}`;
  const how = c.method === "inferred" ? `inferred by ${c.rule_id}` : c.method === "resolved" ? `resolved by ${c.rule_id}` : c.method;
  return `${how} · ${c.source_kind ?? ""} ${c.stream ?? ""}${c.revision ? ` @ ${c.revision.slice(0, 12)}` : ""}`;
}

export function ProvenancePanel({ uid }: { uid: string }) {
  const facts = useQuery({ queryKey: ["ledger-facts", uid], queryFn: () => ledgerApi.facts(uid) });
  if (facts.isLoading) return <Empty>Loading…</Empty>;
  const rows = facts.data?.facts ?? [];
  if (rows.length === 0)
    return <Empty>No source has stated anything about this record through the ledger yet.</Empty>;
  return (
    <div className="space-y-3 pt-2">
      <p className="text-xs text-slate-500">
        Every value with the sources and decisions behind it. The effective one is marked ●; a person's confirmation
        outranks any source until someone explicitly replaces it.
      </p>
      <ul className="divide-y divide-slate-100">
        {rows.map((f) => (
          <li key={`${f.predicate}|${f.member ?? ""}`} className="py-2">
            <p className="text-sm font-medium text-slate-900">
              {f.predicate.replace(/^attr:/, "").replace(/^rel:/, "→ ")}
              {f.member && <span className="ml-1 font-normal text-slate-500">[{show(safeParse(f.member))}]</span>}
            </p>
            <ul className="mt-1 space-y-0.5">
              {f.contributors.map((c, i) => (
                <li key={i} className="flex items-baseline gap-2 text-xs">
                  <span className={c.effective ? "text-emerald-600" : "text-slate-300"}>●</span>
                  <span className="min-w-[8rem] font-mono text-slate-800">
                    {c.kind === "claim" && c.polarity === "absent"
                      ? "absent"
                      : f.predicate === "exists"
                        ? existsLabel(c.value)
                        : show(c.value)}
                  </span>
                  <span className={`min-w-[5.5rem] ${CONTRIBUTOR_STYLE[c.status] ?? "text-slate-500"}`}>{c.status}</span>
                  <span className="truncate text-slate-500" title={c.evidence ? JSON.stringify(c.evidence) : undefined}>
                    {describe(c)}
                  </span>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </div>
  );
}

function existsLabel(value: unknown): string {
  if (typeof value === "string") return value;
  const type = (value as { type?: string } | null)?.type;
  return type ? `exists (${type})` : "exists";
}

function safeParse(s: string): unknown {
  try {
    return JSON.parse(s);
  } catch {
    return s;
  }
}
