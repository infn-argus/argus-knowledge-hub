/** Connectivity and attribution: an address's history across positions, where
 * a bus segment attaches, and which tickets involved a unit. Every value here
 * is derived from Installations; the actions record decisions. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { assetsApi, ledgerApi } from "../../api/client";
import type { AccessPointView, RecordBrief, SegmentPort, TicketLinkView } from "../../api/ledgerTypes";
import { AssetPicker } from "../AssetPicker";
import { errorText, formatTemporal, INSTALLABLE } from "./LedgerPanels";
import { Empty } from "./ui";

function RecordLink({ r }: { r: RecordBrief | null | undefined }) {
  if (!r) return <span className="text-slate-400">—</span>;
  return (
    <Link to={`/assets/${r.uid}`} className="font-medium text-slate-900 hover:underline">
      {r.name}
    </Link>
  );
}

const CERTAINTY: Record<string, string> = {
  definite: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  possible: "bg-amber-50 text-amber-800 ring-amber-200",
};

function Certainty({ value }: { value: string }) {
  return (
    <span className={`rounded px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-inset ${CERTAINTY[value] ?? ""}`}>
      {value}
    </span>
  );
}

// --------------------------------------------------------------------------- Access Points

export function AccessPointPanel({ uid }: { uid: string }) {
  const queryClient = useQueryClient();
  const ap = useQuery({ queryKey: ["access-point", uid], queryFn: () => ledgerApi.accessPoint(uid) });
  const [at, setAt] = useState(() => new Date().toISOString().slice(0, 16));
  const address = ap.data?.access_point.address ?? "";
  const used = useQuery({
    queryKey: ["address-use", address, at],
    queryFn: () => ledgerApi.whoUsed(address, new Date(at).toISOString()),
    enabled: !!address && !!at,
  });
  if (ap.isLoading) return <Empty>Loading…</Empty>;
  if (!ap.data) return <Empty>This Access Point could not be loaded.</Empty>;
  const me = ap.data.access_point;
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["access-point"] });
    queryClient.invalidateQueries({ queryKey: ["address-use"] });
    queryClient.invalidateQueries({ queryKey: ["hub-asset"] });
  };
  return (
    <div className="space-y-4 pt-2">
      <p className="text-xs text-slate-500">
        An address serves one position at a time. When it moves, the old Access Point keeps its history and tickets and
        names its successor; the handover is shown as a range until someone confirms the exact time.
      </p>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-100 text-left text-[11px] uppercase tracking-wide text-slate-400">
            <th className="py-1.5 font-medium">Access Point</th>
            <th className="py-1.5 font-medium">Position</th>
            <th className="py-1.5 font-medium">In service from</th>
            <th className="py-1.5 font-medium">Until</th>
          </tr>
        </thead>
        <tbody>
          {ap.data.address_history.map((v: AccessPointView) => (
            <tr key={v.uid} className={`border-b border-slate-50 last:border-0 ${v.uid === uid ? "bg-indigo-50/40" : ""}`}>
              <td className="py-2">
                <Link to={`/assets/${v.uid}`} className="font-mono text-xs text-slate-800 hover:underline">
                  {v.key}
                </Link>
                <div className="text-[11px] text-slate-500">{v.record_status}</div>
              </td>
              <td className="py-2">
                <RecordLink r={v.position} />
              </td>
              <td className="py-2 text-slate-700">{formatTemporal(v.in_service_from, "from")}</td>
              <td className="py-2 text-slate-700">
                {formatTemporal(v.in_service_until, "until")}
                {v.successor_record && (
                  <div className="text-[11px] text-slate-500">
                    then <Link to={`/assets/${v.successor_record.uid}`} className="hover:underline">{v.successor_record.key}</Link>
                  </div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="rounded-lg border border-slate-200 p-3">
        <label className="flex flex-wrap items-center gap-2 text-sm text-slate-700">
          Who used <span className="font-mono">{address}</span> at
          <input
            type="datetime-local"
            value={at}
            onChange={(e) => setAt(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1 text-sm"
          />
        </label>
        {used.data && (
          used.data.used_by.length === 0 ? (
            <p className="mt-2 text-sm text-slate-500">Nobody: the address was not in service then.</p>
          ) : (
            <ul className="mt-2 space-y-1 text-sm">
              {used.data.used_by.map((r, i) => (
                <li key={i} className="flex items-center gap-2">
                  <Certainty value={r.certainty} />
                  <RecordLink r={r.position} />
                  <span className="text-slate-400">with</span>
                  {r.asset ? <RecordLink r={r.asset} /> : <span className="text-slate-400">no unit recorded</span>}
                </li>
              ))}
            </ul>
          )
        )}
      </div>
      {me.record_status === "Active" && <ReassignForm uid={uid} onDone={refresh} />}
    </div>
  );
}

function ReassignForm({ uid, onDone }: { uid: string; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<string | null>(null);
  const [at, setAt] = useState(() => new Date().toISOString().slice(0, 16));
  const assets = useQuery({ queryKey: ["assets"], queryFn: () => assetsApi.list(), enabled: open });
  const move = useMutation({
    mutationFn: () =>
      ledgerApi.reassign(uid, {
        position_uid: position!,
        at: { kind: "date", nominal: new Date(at).toISOString(), precision: "instant" },
      }),
    onSuccess: () => {
      setOpen(false);
      onDone();
    },
  });
  if (!open)
    return (
      <button
        onClick={() => setOpen(true)}
        className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
      >
        Move this address to another position…
      </button>
    );
  const positions = (assets.data ?? []).filter((a) => INSTALLABLE.has(a.type));
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
      <p className="text-sm font-medium text-slate-900">Move the address</p>
      <p className="mt-0.5 text-xs text-slate-500">
        This Access Point retires with a successor that serves the new position from the time you give. Its tickets stay
        with it.
      </p>
      <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
        <label className="text-xs text-slate-600">
          New position
          <AssetPicker options={positions} value={position} onChange={setPosition} placeholder="Search positions…" />
        </label>
        <label className="text-xs text-slate-600">
          From
          <input
            type="datetime-local"
            value={at}
            onChange={(e) => setAt(e.target.value)}
            className="mt-1 block w-full rounded border border-slate-300 px-2 py-1 text-sm"
          />
        </label>
      </div>
      {move.isError && <p className="mt-2 text-sm text-red-600">{errorText(move.error)}</p>}
      <div className="mt-3 flex gap-2">
        <button
          disabled={!position || move.isPending}
          onClick={() => move.mutate()}
          className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
        >
          Move
        </button>
        <button onClick={() => setOpen(false)} className="rounded-md border border-slate-300 px-3 py-1.5 text-xs">
          Cancel
        </button>
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- Bus Segments

const PORT_STATUS: Record<SegmentPort["status"], { title: string; tone: string; explain: string }> = {
  attached: { title: "Attached", tone: "text-emerald-700", explain: "One registry-backed port matches every requirement." },
  unresolved: {
    title: "Unresolved",
    tone: "text-amber-700",
    explain: "No port, or more than one, matches. Impact analysis treats the segment as unattached.",
  },
  confirmation_required: {
    title: "Needs a confirmation",
    tone: "text-amber-700",
    explain: "A person must identify the port for this installation before the segment attaches.",
  },
  invalid: {
    title: "Confirmed port no longer compatible",
    tone: "text-red-700",
    explain: "A confirmation identifies a port; it never authorizes an incompatible connection.",
  },
  not_applicable: {
    title: "Not placed",
    tone: "text-slate-500",
    explain: "The path's Access Point has no position with a unit installed, or the segment states no port requirement.",
  },
};

export function SegmentPortPanel({ uid }: { uid: string }) {
  const queryClient = useQueryClient();
  const port = useQuery({ queryKey: ["segment-port", uid], queryFn: () => ledgerApi.segmentPort(uid) });
  const confirm = useMutation({
    mutationFn: (portUid: string) =>
      ledgerApi.confirmPortMap(uid, { installation_uid: port.data!.installation_uid!, port_uid: portUid }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["segment-port", uid] });
      queryClient.invalidateQueries({ queryKey: ["ledger-review"] });
    },
  });
  if (port.isLoading) return <Empty>Loading…</Empty>;
  if (!port.data) return <Empty>The port could not be derived.</Empty>;
  const p = port.data;
  const meta = PORT_STATUS[p.status];
  return (
    <div className="space-y-3 pt-2">
      <p className={`text-sm font-medium ${meta.tone}`}>
        {meta.title}
        {p.status === "attached" && p.port && (
          <>
            {" "}to <RecordLink r={p.port} /> on <RecordLink r={p.unit} />
          </>
        )}
      </p>
      <p className="text-xs text-slate-500">
        {p.status === "attached" && p.evidence?.confirmed_map
          ? "A person confirmed this port for the current installation; it passes every hard compatibility check."
          : meta.explain}
        {p.reason ? ` (${p.reason})` : ""}
        {p.failed ? ` Failed: ${p.failed}.` : ""}
      </p>
      {p.required && (
        <p className="text-xs text-slate-600">
          Requires{" "}
          <span className="font-mono">
            {Object.entries(p.required)
              .map(([k, v]) => `${k}=${v}`)
              .join(" · ")}
          </span>
        </p>
      )}
      {(p.candidates ?? []).length > 0 && p.status !== "attached" && (
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Candidates</p>
          <ul className="mt-1 flex flex-wrap gap-2">
            {p.candidates!.map((c) => (
              <li key={c.port_uid}>
                <button
                  onClick={() => confirm.mutate(c.port_uid)}
                  className="rounded border border-slate-300 bg-white px-2.5 py-1 text-xs hover:bg-slate-50"
                  title="Confirm this port for the current installation only"
                >
                  Use {c.label}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      {p.status === "unresolved" && (p.ports ?? []).length > 0 && (
        <details className="text-xs text-slate-600">
          <summary className="cursor-pointer">Why each port was ruled out</summary>
          <ul className="mt-1 grid grid-cols-2 gap-x-4 md:grid-cols-4">
            {p.ports!.map((x) => (
              <li key={x.port_uid}>
                <span className="font-mono">{x.label}</span> — {x.failed ?? "matches"}
              </li>
            ))}
          </ul>
        </details>
      )}
      {confirm.isError && <p className="text-sm text-red-600">{errorText(confirm.error)}</p>}
    </div>
  );
}

// --------------------------------------------------------------------------- tickets

const ROLE_LABEL: Record<string, string> = {
  subject: "subject",
  related: "related",
  involved_equipment: "installed at the time",
  involved_position: "where it was installed",
};

/** On a ticket: the units (or positions) it involved at incident time. */
export function TicketAttribution({ ticketUid }: { ticketUid: string }) {
  const links = useQuery({ queryKey: ["ticket-links", ticketUid], queryFn: () => ledgerApi.ticketLinks(ticketUid) });
  const derived = (links.data ?? []).filter((l: TicketLinkView) => l.role.startsWith("involved"));
  if (derived.length === 0) return null;
  const incident = derived[0].detail?.incident;
  const source = derived[0].detail?.source;
  return (
    <div className="mt-3 border-t border-slate-100 pt-2">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Involved at incident time</p>
      {incident && (
        <p className="text-[11px] text-slate-500">
          {new Date(incident[0]).toLocaleString()} – {new Date(incident[1]).toLocaleString()}
          {source === "legacy_created_fallback" && " (estimated from the legacy creation date)"}
        </p>
      )}
      <ul className="mt-1 space-y-1">
        {derived.map((l) => (
          <li key={`${l.asset_uid}-${l.role}`} className="flex items-center gap-2 text-sm">
            <Certainty value={l.certainty} />
            <Link to={`/assets/${l.asset_uid}`} className="font-medium text-slate-900 hover:underline">
              {l.name}
            </Link>
            <span className="text-xs text-slate-500">
              {ROLE_LABEL[l.role]}
              {l.origin === "migration-split" ? " · from the legacy split, not counted" : ""}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** On a unit or position: the tickets it was involved in without being their subject. */
export function InvolvedTickets({ uid }: { uid: string }) {
  const data = useQuery({ queryKey: ["record-tickets", uid], queryFn: () => ledgerApi.recordTickets(uid) });
  const rows = data.data?.involved ?? [];
  if (rows.length === 0) return null;
  return (
    <div className="mt-3 border-t border-slate-100 pt-2">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
        Involved in {data.data!.counts.involved} ticket{data.data!.counts.involved === 1 ? "" : "s"} (counted) raised
        elsewhere
      </p>
      <ul className="mt-1 divide-y divide-slate-50">
        {rows.map((t) => (
          <li key={`${t.ticket_uid}-${t.role}`} className="flex items-center justify-between gap-3 py-1.5 text-sm">
            <Link to={`/tickets/${t.ticket_uid}`} className="min-w-0 truncate text-slate-800 hover:underline">
              <span className="mr-2 font-mono text-xs text-slate-500">{t.key.slice(0, 12)}</span>
              {t.title}
            </Link>
            <span className="flex shrink-0 items-center gap-2 text-xs text-slate-500">
              {ROLE_LABEL[t.role] ?? t.role}
              <Certainty value={t.certainty} />
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
