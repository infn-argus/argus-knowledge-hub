import { useMemo, useState } from "react";

export interface PickerOption {
  uid: string;
  label: string;
  sub?: string;
}

/** Search-as-you-type over records of one kind, returning the one picked.
 *
 * The same shape as the object and ticket pickers, kept separate from them
 * because what it searches is supplied by the caller: a document links to
 * objects, tickets and other documents, and one control that takes a list
 * beats three that each know how to fetch their own.
 */
export function RecordPicker({
  options,
  onPick,
  placeholder = "Search…",
  disabled,
  excludeUid,
}: {
  options: PickerOption[];
  onPick: (uid: string) => void;
  placeholder?: string;
  disabled?: boolean;
  excludeUid?: string;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    return options
      .filter((o) => o.uid !== excludeUid)
      .filter(
        (o) =>
          !q ||
          o.label.toLowerCase().includes(q) ||
          (o.sub ?? "").toLowerCase().includes(q),
      )
      .slice(0, 30);
  }, [options, query, excludeUid]);

  return (
    <div className="relative flex-1">
      <input
        value={query}
        disabled={disabled}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder={placeholder}
        className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm disabled:bg-slate-100"
      />
      {open && matches.length > 0 && (
        <div className="absolute z-20 mt-1 max-h-56 w-full min-w-[18rem] overflow-y-auto rounded border border-slate-200 bg-white shadow-lg">
          {matches.map((o) => (
            <button
              type="button"
              key={o.uid}
              onMouseDown={(e) => {
                e.preventDefault();
                onPick(o.uid);
                setQuery("");
                setOpen(false);
              }}
              className="block w-full px-2 py-1.5 text-left text-sm hover:bg-slate-50"
            >
              <span className="text-slate-800">{o.label}</span>
              {o.sub && <span className="ml-2 text-xs text-slate-400">{o.sub}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
