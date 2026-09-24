/** Small, shared pieces of the unified interface: the same badge for "a
 * ticket" or "a procedure" wherever one appears, so assets, tickets and
 * documents read as one system rather than three applications. */
import { Link } from "react-router-dom";
import type { HubDocument, HubTicket, KnowledgeVia } from "../../api/hubTypes";

export type Kind = "asset" | "ticket" | "document";

export const KIND_META: Record<Kind, { label: string; badge: string; dot: string; icon: string }> = {
  asset: { label: "Asset", badge: "bg-indigo-50 text-indigo-700 ring-indigo-200", dot: "bg-indigo-500", icon: "▣" },
  ticket: { label: "Ticket", badge: "bg-amber-50 text-amber-800 ring-amber-200", dot: "bg-amber-500", icon: "◆" },
  document: { label: "Document", badge: "bg-emerald-50 text-emerald-700 ring-emerald-200", dot: "bg-emerald-500", icon: "▤" },
};

export function KindBadge({ kind, className = "" }: { kind: Kind; className?: string }) {
  const m = KIND_META[kind];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ring-1 ring-inset ${m.badge} ${className}`}
    >
      <span aria-hidden>{m.icon}</span>
      {m.label}
    </span>
  );
}

const STATE_STYLE: Record<string, string> = {
  new: "bg-sky-50 text-sky-700 ring-sky-200",
  open: "bg-sky-50 text-sky-700 ring-sky-200",
  in_progress: "bg-violet-50 text-violet-700 ring-violet-200",
  waiting: "bg-amber-50 text-amber-800 ring-amber-200",
  closed: "bg-slate-100 text-slate-500 ring-slate-200",
  done: "bg-slate-100 text-slate-500 ring-slate-200",
  resolved: "bg-slate-100 text-slate-500 ring-slate-200",
};

export function TicketState({ ticket }: { ticket: Pick<HubTicket, "state" | "open"> }) {
  const style = STATE_STYLE[ticket.state?.toLowerCase()] ??
    (ticket.open ? "bg-sky-50 text-sky-700 ring-sky-200" : "bg-slate-100 text-slate-500 ring-slate-200");
  return (
    <span className={`rounded px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-inset ${style}`}>
      {(ticket.state || "new").replace(/_/g, " ")}
    </span>
  );
}

const PRIORITY_DOT: Record<string, string> = {
  critical: "bg-red-600",
  highest: "bg-red-600",
  high: "bg-orange-500",
  medium: "bg-amber-400",
  low: "bg-slate-300",
  lowest: "bg-slate-200",
};

export function Priority({ value }: { value?: string | null }) {
  if (!value) return null;
  return (
    <span className="inline-flex items-center gap-1 text-[11px] text-slate-500" title={`Priority: ${value}`}>
      <span className={`h-2 w-2 rounded-full ${PRIORITY_DOT[value.toLowerCase()] ?? "bg-slate-300"}`} />
      {value}
    </span>
  );
}

export const VIA_META: Record<KnowledgeVia, { label: string; style: string; explain: string }> = {
  asset: { label: "This asset", style: "bg-emerald-50 text-emerald-700", explain: "Written about this object" },
  product: { label: "Product model", style: "bg-teal-50 text-teal-700", explain: "Applies to every unit of the product" },
  type: { label: "Type", style: "bg-cyan-50 text-cyan-700", explain: "Applies to every object of this type" },
  service: { label: "Responsible service", style: "bg-slate-100 text-slate-600", explain: "Names this object as responsible service" },
};

export function ViaBadge({ doc }: { doc: Pick<HubDocument, "via" | "via_label"> }) {
  if (!doc.via) return null;
  const m = VIA_META[doc.via];
  return (
    <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${m.style}`} title={m.explain}>
      {m.label}
      {doc.via === "type" || doc.via === "product" ? (doc.via_label ? `: ${doc.via_label}` : "") : ""}
    </span>
  );
}

export function DocumentRow({ doc, extra }: { doc: HubDocument; extra?: React.ReactNode }) {
  return (
    <li className="group flex items-start justify-between gap-3 py-2">
      <div className="min-w-0">
        <Link to={`/documents/${doc.uid}`} className="block truncate text-sm font-medium text-slate-900 group-hover:text-emerald-700">
          {doc.title}
        </Link>
        <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[11px] text-slate-500">
          <span className="font-mono">{doc.code}</span>
          <ViaBadge doc={doc} />
          {doc.state && <span className="rounded bg-slate-100 px-1.5 py-0.5">{doc.state.replace(/_/g, " ")}</span>}
          {doc.review_overdue && (
            <span className="rounded bg-red-50 px-1.5 py-0.5 font-medium text-red-700" title={`Review due ${doc.next_review_due}`}>
              review overdue
            </span>
          )}
          {extra}
        </div>
      </div>
    </li>
  );
}

export function TicketRow({ ticket, extra }: { ticket: HubTicket; extra?: React.ReactNode }) {
  return (
    <li className="group flex items-start justify-between gap-3 py-2">
      <div className="min-w-0">
        <Link to={`/tickets/${ticket.uid}`} className="block truncate text-sm font-medium text-slate-900 group-hover:text-amber-700">
          {ticket.title}
        </Link>
        <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
          <TicketState ticket={ticket} />
          <Priority value={ticket.priority} />
          {ticket.source_key && <span className="font-mono">{ticket.source_key}</span>}
          {ticket.updated_at && <span>{relativeTime(ticket.updated_at)}</span>}
          {extra}
        </div>
      </div>
    </li>
  );
}

export function StatTile({
  label,
  value,
  tone = "slate",
  to,
  hint,
}: {
  label: string;
  value: number | string;
  tone?: "slate" | "amber" | "red" | "emerald" | "indigo";
  to?: string;
  hint?: string;
}) {
  const tones: Record<string, string> = {
    slate: "text-slate-900",
    amber: "text-amber-700",
    red: "text-red-700",
    emerald: "text-emerald-700",
    indigo: "text-indigo-700",
  };
  const body = (
    <>
      <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-semibold tabular-nums ${tones[tone]}`}>{value}</p>
      {hint && <p className="mt-0.5 text-[11px] text-slate-400">{hint}</p>}
    </>
  );
  const cls = "block rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm";
  return to ? (
    <Link to={to} className={`${cls} transition hover:border-slate-300 hover:shadow`}>
      {body}
    </Link>
  ) : (
    <div className={cls}>{body}</div>
  );
}

export function Card({
  title,
  action,
  children,
  className = "",
}: {
  title: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-lg border border-slate-200 bg-white shadow-sm ${className}`}>
      <header className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5">
        <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
        {action}
      </header>
      <div className="px-4 py-2">{children}</div>
    </section>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="py-3 text-sm text-slate-400">{children}</p>;
}

export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
}: {
  tabs: { key: T; label: string; count?: number; alert?: boolean }[];
  value: T;
  onChange: (key: T) => void;
}) {
  return (
    <div role="tablist" className="flex gap-1 border-b border-slate-200">
      {tabs.map((t) => (
        <button
          key={t.key}
          role="tab"
          aria-selected={value === t.key}
          onClick={() => onChange(t.key)}
          className={`-mb-px flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium transition ${
            value === t.key
              ? "border-slate-900 text-slate-900"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          {t.label}
          {t.count !== undefined && (
            <span
              className={`rounded-full px-1.5 text-[11px] tabular-nums ${
                t.alert ? "bg-red-100 text-red-700" : "bg-slate-100 text-slate-600"
              }`}
            >
              {t.count}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

export function relativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 60) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}
