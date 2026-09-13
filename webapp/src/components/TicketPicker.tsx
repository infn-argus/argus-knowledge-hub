import { useMemo, useState } from "react";
import { Issue } from "../api/types";

/** Search-as-you-type ticket picker, for linking a ticket to its epic,
 * parent, or a related ticket. Matches on title and on the source key,
 * since "LNFDCS-563" is what people have in front of them. */
export function TicketPicker({
  options,
  excludeUid,
  onPick,
  placeholder = "Search tickets…",
  disabled,
}: {
  options: Issue[];
  excludeUid?: string;
  onPick: (uid: string) => void;
  placeholder?: string;
  disabled?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    const pool = options.filter((i) => i.uid !== excludeUid);
    if (!q) return pool.slice(0, 20);
    return pool
      .filter((i) => {
        const key = String(i.attributes?.argus_source_key ?? "").toLowerCase();
        return i.title.toLowerCase().includes(q) || key.includes(q);
      })
      .slice(0, 20);
  }, [options, query, excludeUid]);

  return (
    <div className="relative flex-1">
      <input
        disabled={disabled}
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        // A click on a result has to land before the list closes.
        onBlur={() => window.setTimeout(() => setOpen(false), 150)}
        placeholder={placeholder}
        className="w-full rounded border border-slate-300 px-2 py-1 text-xs"
      />
      {open && matches.length > 0 && (
        <ul className="absolute z-20 mt-1 max-h-64 w-full overflow-y-auto rounded border border-slate-200 bg-white shadow-lg">
          {matches.map((issue) => {
            const key = issue.attributes?.argus_source_key as string | undefined;
            return (
              <li key={issue.uid}>
                <button
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => {
                    onPick(issue.uid);
                    setQuery("");
                    setOpen(false);
                  }}
                  className="flex w-full items-baseline gap-2 px-2 py-1.5 text-left text-xs hover:bg-slate-50"
                >
                  {key && <span className="shrink-0 font-mono text-slate-400">{key}</span>}
                  <span className="truncate text-slate-800">{issue.title}</span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
