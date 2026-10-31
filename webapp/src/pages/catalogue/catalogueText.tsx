import { ApiError, type CatalogueValueSource } from "../../api/client";

/** A value as a person reads it. */
export function shown(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export function problem(e: unknown): string {
  if (e instanceof ApiError) {
    const d = (e.body as { detail?: unknown })?.detail;
    if (d && typeof d === "object" && "error" in d) {
      const details = (d as { details?: string[] }).details ?? [];
      return [String((d as { error: string }).error), ...details].join("\n");
    }
    if (typeof d === "string") return d;
    if (e.status === 403) return "Only the catalogue workspace's owners and administrators may do this.";
  }
  return "It could not be done.";
}

export const SOURCE: Record<CatalogueValueSource, { label: string; hint: string; cls: string }> = {
  collection: { label: "from the collection", hint: "Managed: a new release updates it",
                cls: "bg-sky-50 text-sky-800 border-sky-200" },
  edited: { label: "edited here", hint: "Managed, but changed here since the release: say what it is",
            cls: "bg-amber-50 text-amber-900 border-amber-300" },
  local: { label: "local override", hint: "This workspace's value: releases leave it",
           cls: "bg-slate-50 text-slate-700 border-slate-300" },
  correction: { label: "proposed to Git", hint: "Kept here, and proposed back as a correction",
                cls: "bg-violet-50 text-violet-800 border-violet-200" },
  record: { label: "record", hint: "The collection does not state it", cls: "bg-white text-slate-500 border-slate-200" },
};

export function SourceBadge({ source }: { source: CatalogueValueSource }) {
  const s = SOURCE[source];
  return <span title={s.hint} className={`rounded border px-1.5 py-0.5 text-xs ${s.cls}`}>{s.label}</span>;
}

export const CATEGORY: Record<string, string> = {
  add: "New", change: "Changed", link: "Already here: link or create", conflict: "Kept local (review)",
  transfer: "Moved between collections", retire: "Retired", unchanged: "Unchanged",
};
