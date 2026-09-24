/** One search box for everything: equipment, tickets and documents at once,
 * plus the actions people reach for most. Opens with Ctrl/⌘ K or "/". */
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { hubApi } from "../../api/client";
import { KindBadge, Priority, TicketState, type Kind } from "./ui";

interface Item {
  id: string;
  kind: Kind | "action";
  title: string;
  subtitle?: string;
  to: string;
  meta?: React.ReactNode;
}

const ACTIONS: Item[] = [
  { id: "a-ticket", kind: "action", title: "Report an issue", subtitle: "Open a new ticket", to: "/tickets/new" },
  { id: "a-asset", kind: "action", title: "Register an asset", subtitle: "Create a new object", to: "/assets/new" },
  { id: "a-doc", kind: "action", title: "Write a document", subtitle: "Procedure, manual, report…", to: "/documents/new" },
  { id: "a-board", kind: "action", title: "Service board", subtitle: "Tickets by state", to: "/tickets/board" },
  { id: "a-graph", kind: "action", title: "Knowledge graph", subtitle: "Impact and root cause", to: "/graph" },
  { id: "a-ask", kind: "action", title: "Ask ARGUS", subtitle: "Question the knowledge base", to: "/ask" },
];

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

export function useCommandPaletteShortcut(open: () => void) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const typing =
        !!target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable);
      if ((e.key === "k" || e.key === "K") && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        open();
      } else if (e.key === "/" && !typing) {
        e.preventDefault();
        open();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);
}

export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounced = useDebounced(query.trim(), 180);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  const results = useQuery({
    queryKey: ["hub-search", debounced],
    queryFn: () => hubApi.search(debounced, 6),
    enabled: open && debounced.length >= 2,
    staleTime: 15_000,
  });

  const groups = useMemo(() => {
    const out: { label: string; items: Item[] }[] = [];
    const r = results.data;
    if (debounced.length >= 2 && r) {
      if (r.assets.length)
        out.push({
          label: "Assets",
          items: r.assets.map((a) => ({
            id: `as-${a.uid}`,
            kind: "asset",
            title: a.name,
            subtitle: `${a.key} · ${a.type}`,
            to: `/assets/${a.uid}`,
          })),
        });
      if (r.tickets.length)
        out.push({
          label: "Tickets",
          items: r.tickets.map((t) => ({
            id: `tk-${t.uid}`,
            kind: "ticket",
            title: t.title,
            subtitle: t.source_key ?? undefined,
            to: `/tickets/${t.uid}`,
            meta: (
              <span className="flex items-center gap-2">
                <TicketState ticket={t} />
                <Priority value={t.priority} />
              </span>
            ),
          })),
        });
      if (r.documents.length)
        out.push({
          label: "Documents",
          items: r.documents.map((d) => ({
            id: `dc-${d.uid}`,
            kind: "document",
            title: d.title,
            subtitle: d.code,
            to: `/documents/${d.uid}`,
          })),
        });
    }
    const q = query.trim().toLowerCase();
    const actions = ACTIONS.filter(
      (a) => !q || a.title.toLowerCase().includes(q) || (a.subtitle ?? "").toLowerCase().includes(q),
    );
    if (actions.length) out.push({ label: q ? "Actions" : "Quick actions", items: actions });
    return out;
  }, [results.data, debounced, query]);

  const flat = useMemo(() => groups.flatMap((g) => g.items), [groups]);

  useEffect(() => {
    setActive(0);
  }, [debounced]);

  if (!open) return null;

  const go = (item: Item | undefined) => {
    if (!item) return;
    onClose();
    navigate(item.to);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(i + 1, flat.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      go(flat[active]);
    }
  };

  let index = -1;
  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-slate-900/40 px-4 pt-[12vh] backdrop-blur-[1px]"
      onMouseDown={onClose}
    >
      <div
        role="dialog"
        aria-label="Search ARGUS"
        className="w-full max-w-2xl overflow-hidden rounded-xl border border-slate-200 bg-white shadow-2xl"
        onMouseDown={(e) => e.stopPropagation()}
        onKeyDown={onKeyDown}
      >
        <div className="flex items-center gap-3 border-b border-slate-100 px-4">
          <span className="text-slate-400" aria-hidden>
            ⌕
          </span>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search assets, tickets and documents — name, key, serial, IP, code…"
            className="h-12 flex-1 bg-transparent text-sm outline-none placeholder:text-slate-400"
            aria-label="Search"
          />
          {results.isFetching && <span className="text-xs text-slate-400">searching…</span>}
          <kbd className="rounded border border-slate-200 px-1.5 text-[10px] text-slate-400">Esc</kbd>
        </div>
        <div className="max-h-[60vh] overflow-y-auto py-2">
          {debounced.length >= 2 && results.data && flat.length === ACTIONS.length && (
            <p className="px-4 py-3 text-sm text-slate-500">
              Nothing matches “{debounced}” in assets, tickets or documents.
            </p>
          )}
          {groups.map((g) => (
            <div key={g.label} className="px-2 pb-1">
              <p className="px-2 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                {g.label}
              </p>
              <ul>
                {g.items.map((item) => {
                  index += 1;
                  const i = index;
                  return (
                    <li key={item.id}>
                      <button
                        type="button"
                        onMouseEnter={() => setActive(i)}
                        onClick={() => go(item)}
                        className={`flex w-full items-center gap-3 rounded-md px-2 py-2 text-left ${
                          active === i ? "bg-slate-100" : "hover:bg-slate-50"
                        }`}
                      >
                        {item.kind === "action" ? (
                          <span className="w-[72px] text-center text-xs text-slate-400">→</span>
                        ) : (
                          <KindBadge kind={item.kind} className="w-[72px] justify-center" />
                        )}
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm text-slate-900">{item.title}</span>
                          {item.subtitle && (
                            <span className="block truncate text-xs text-slate-500">{item.subtitle}</span>
                          )}
                        </span>
                        {item.meta}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
        <div className="flex items-center gap-4 border-t border-slate-100 bg-slate-50 px-4 py-2 text-[11px] text-slate-500">
          <span>
            <kbd className="rounded border border-slate-200 bg-white px-1">↑</kbd>{" "}
            <kbd className="rounded border border-slate-200 bg-white px-1">↓</kbd> to move
          </span>
          <span>
            <kbd className="rounded border border-slate-200 bg-white px-1">Enter</kbd> to open
          </span>
          <span className="ml-auto">One search across the asset, service and knowledge records</span>
        </div>
      </div>
    </div>
  );
}
