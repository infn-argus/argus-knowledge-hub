import { useState } from "react";
import type { ArchiveLabels, PortabilityError } from "../../../api/portabilityTypes";

/** Pieces shared by the export and import pages (docs/export-import-design.md §17). */

export const EXPORT_STEPS = ["requested", "analysing", "awaiting_approval", "approved", "generating", "verifying",
  "ready_to_publish", "publishing", "published"];
export const IMPORT_STEPS = ["created", "fetching", "quarantined", "verifying", "dry_run_ready", "awaiting_approval",
  "approved", "importing", "rebuilding", "reconciling", "ready_to_finalize", "finalized"];
const BAD = new Set(["failed", "invalid", "revoked", "expired", "discarded"]);

export function human(state: string): string {
  return state.replace(/_/g, " ").replace("publish git", "publish to Git");
}

export function StateBadge({ state }: { state: string }) {
  const tone = BAD.has(state) ? "bg-rose-100 text-rose-800"
    : state === "published" || state === "finalized" ? "bg-emerald-100 text-emerald-800"
      : state.startsWith("awaiting") || state === "dry_run_ready" || state === "ready_to_publish" ||
        state === "ready_to_finalize" ? "bg-amber-100 text-amber-800" : "bg-slate-100 text-slate-700";
  return <span className={`rounded px-2 py-0.5 text-xs font-medium ${tone}`}>{human(state)}</span>;
}

const LABELS: [keyof ArchiveLabels, string, string][] = [
  ["complete", "complete", "selective or partial"],
  ["incremental", "incremental", "checkpoint"],
  ["signed", "signed", "unsigned"],
  ["encrypted", "encrypted", "not encrypted"],
  ["git_published", "Git-published", "not in Git"],
  ["artifact_complete", "artifact-complete", "artifacts not checked"],
  ["verified", "verified", "not verified"],
  ["restorable", "restorable", "not restorable"],
  ["evidence_only", "evidence only", ""],
];

/** Every label a person must see about an archive, the absent ones too. */
export function Labels({ labels, compact }: { labels: ArchiveLabels; compact?: boolean }) {
  return (
    <span className="flex flex-wrap gap-1">
      {LABELS.map(([key, yes, no]) => {
        const on = labels[key];
        if (compact && !on) return null;
        if (!on && !no) return null;
        const good = on && key !== "evidence_only" && key !== "incremental";
        return (
          <span key={key} className={`rounded border px-1.5 py-0.5 text-[11px] ${on ? good
            ? "border-emerald-300 bg-emerald-50 text-emerald-800" : "border-sky-300 bg-sky-50 text-sky-800"
            : "border-slate-200 bg-white text-slate-400"}`}>
            {on ? yes : no}
          </span>
        );
      })}
      {labels.full && <span className="rounded border border-sky-300 bg-sky-50 px-1.5 py-0.5 text-[11px] text-sky-800">full</span>}
      {labels.selective && <span className="rounded border border-sky-300 bg-sky-50 px-1.5 py-0.5 text-[11px] text-sky-800">selective</span>}
    </span>
  );
}

/** Where a lifecycle is, as a row of steps. */
export function Steps({ steps, state }: { steps: string[]; state: string }) {
  const at = steps.indexOf(state);
  return (
    <ol className="flex flex-wrap items-center gap-1 text-[11px]">
      {steps.map((s, i) => (
        <li key={s} className="flex items-center gap-1">
          <span className={`rounded-full px-2 py-0.5 ${i < at || (i === at && (s === "published" || s === "finalized"))
            ? "bg-emerald-600 text-white" : i === at ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-500"}`}>
            {human(s)}
          </span>
          {i < steps.length - 1 && <span className="text-slate-300">›</span>}
        </li>
      ))}
      {at < 0 && <li className="ml-2"><StateBadge state={state} /></li>}
    </ol>
  );
}

export function ErrorBox({ error }: { error: PortabilityError | string | null | undefined }) {
  if (!error) return null;
  const e = typeof error === "string" ? { error, code: "" } : error;
  const extra = typeof e === "object" ? Object.entries(e).filter(([k]) => !["error", "code"].includes(k)) : [];
  return (
    <div className="rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
      <div className="font-medium">{e.error}{e.code ? <span className="ml-2 font-mono text-xs">{e.code}</span> : null}</div>
      {extra.length > 0 && (
        <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(Object.fromEntries(extra), null, 1)}</pre>
      )}
    </div>
  );
}

export function Section({ title, children, right }: { title: string; children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
        {right}
      </div>
      {children}
    </section>
  );
}

export function KV({ rows }: { rows: [string, React.ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm">
      {rows.filter(([, v]) => v !== undefined && v !== null && v !== "").map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-slate-500">{k}</dt>
          <dd className="min-w-0 break-all text-slate-900">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Mono({ children, short }: { children: string | null | undefined; short?: boolean }) {
  if (!children) return <span className="text-slate-400">—</span>;
  return <code className="font-mono text-xs" title={children}>{short ? children.slice(0, 12) : children}</code>;
}

/** A button for an action that changes state, with an inline confirmation instead of a dialog. */
export function ActionButton({ label, onClick, busy, disabled, confirm, danger, title }: {
  label: string; onClick: () => void; busy?: boolean; disabled?: boolean; confirm?: string; danger?: boolean;
  title?: string;
}) {
  const [asking, setAsking] = useState(false);
  const base = danger ? "bg-rose-600 hover:bg-rose-700" : "bg-slate-900 hover:bg-slate-800";
  if (asking) {
    return (
      <span className="flex items-center gap-2 rounded border border-amber-300 bg-amber-50 px-2 py-1 text-xs text-amber-900">
        {confirm}
        <button type="button" className={`rounded px-2 py-1 text-white ${base}`}
                onClick={() => { setAsking(false); onClick(); }}>Yes, {label.charAt(0).toLowerCase() + label.slice(1)}</button>
        <button type="button" className="rounded px-2 py-1 text-slate-600 hover:bg-white" onClick={() => setAsking(false)}>Cancel</button>
      </span>
    );
  }
  return (
    <button type="button" disabled={disabled || busy} title={title}
            onClick={() => (confirm ? setAsking(true) : onClick())}
            className={`rounded px-3 py-1.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-300 ${base}`}>
      {busy ? `${label}…` : label}
    </button>
  );
}

export function bytes(n: number | null | undefined): string {
  if (!n) return "0 B";
  const u = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(u.length - 1, Math.floor(Math.log(n) / Math.log(1024)));
  return `${(n / 1024 ** i).toFixed(i ? 1 : 0)} ${u[i]}`;
}

export function when(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleString() : "—";
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-slate-500">{children}</p>;
}
