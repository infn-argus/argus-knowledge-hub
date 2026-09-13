import { useMemo, useState } from "react";
import { Asset } from "../api/types";

/** Search-as-you-type picker for several objects at once.
 *
 * A ticket usually concerns more than one thing — the camera, the switch
 * it hangs off, the rack both sit in — and a single dropdown forces that
 * into one, which is then the only one anybody can find it from.
 *
 * The first object chosen is the ticket's subject; the rest are links.
 * That's stated in the UI rather than left implicit, because it decides
 * which object the ticket shows up on as its own.
 */
export function AssetMultiPicker({
  options,
  value,
  onChange,
  placeholder = "Search objects…",
}: {
  options: Asset[];
  value: string[];
  onChange: (uids: string[]) => void;
  placeholder?: string;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);

  const byUid = useMemo(() => new Map(options.map((a) => [a.uid, a])), [options]);

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    const chosen = new Set(value);
    const pool = options.filter((a) => !chosen.has(a.uid));
    if (!q) return pool.slice(0, 20);
    return pool
      .filter(
        (a) => a.name.toLowerCase().includes(q) || a.key.toLowerCase().includes(q),
      )
      .slice(0, 20);
  }, [options, query, value]);

  return (
    <div>
      <div className="flex flex-wrap items-center gap-1 rounded border border-slate-300 px-2 py-1.5">
        {value.map((uid, index) => {
          const asset = byUid.get(uid);
          return (
            <span
              key={uid}
              className="inline-flex items-center gap-1 rounded bg-indigo-50 px-1.5 py-0.5 text-xs text-indigo-700"
            >
              {index === 0 && (
                <span className="rounded bg-indigo-100 px-1 text-[10px] uppercase tracking-wide">
                  subject
                </span>
              )}
              {asset ? `${asset.name} (${asset.key})` : uid}
              <button
                type="button"
                onClick={() => onChange(value.filter((v) => v !== uid))}
                className="text-indigo-400 hover:text-indigo-700"
                aria-label={`Remove ${asset?.name ?? uid}`}
              >
                ×
              </button>
            </span>
          );
        })}
        <div className="relative min-w-40 flex-1">
          <input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            // A click on a result has to land before the list closes.
            onBlur={() => window.setTimeout(() => setOpen(false), 150)}
            onKeyDown={(e) => {
              if (e.key === "Enter") e.preventDefault();
              if (e.key === "Backspace" && !query && value.length) {
                onChange(value.slice(0, -1));
              }
            }}
            placeholder={value.length ? "" : placeholder}
            className="w-full text-sm focus:outline-none"
          />
          {open && matches.length > 0 && (
            <ul className="absolute z-20 mt-1 max-h-64 w-full min-w-64 overflow-y-auto rounded border border-slate-200 bg-white shadow-lg">
              {matches.map((asset) => (
                <li key={asset.uid}>
                  <button
                    type="button"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => {
                      onChange([...value, asset.uid]);
                      setQuery("");
                    }}
                    className="flex w-full items-baseline gap-2 px-2 py-1.5 text-left text-xs hover:bg-slate-50"
                  >
                    <span className="truncate text-slate-800">{asset.name}</span>
                    <span className="shrink-0 font-mono text-slate-400">{asset.key}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      {value.length > 1 && (
        <p className="mt-1 text-xs text-slate-500">
          The first is the ticket's subject; the others are linked to it.
        </p>
      )}
    </div>
  );
}
