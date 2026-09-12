import { useMemo, useState } from "react";
import { Asset } from "../api/types";

/** Search-as-you-type asset picker, used for reference-attribute values.
 * `options` is expected to already be filtered to the reference's allowed
 * target schema(s) by the caller. */
export function AssetPicker({
  options,
  value,
  onChange,
  disabled,
  placeholder = "Search assets…",
}: {
  options: Asset[];
  value?: string | null;
  onChange: (uid: string | null) => void;
  disabled?: boolean;
  placeholder?: string;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);

  const byUid = useMemo(() => new Map(options.map((a) => [a.uid, a])), [options]);
  const selected = value ? byUid.get(value) : undefined;

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = q
      ? options.filter(
          (a) => a.name.toLowerCase().includes(q) || a.key.toLowerCase().includes(q),
        )
      : options;
    return [...filtered].sort((a, b) => a.name.localeCompare(b.name)).slice(0, 30);
  }, [options, query]);

  return (
    <div className="relative flex-1">
      <div className="flex items-center gap-1">
        <input
          disabled={disabled}
          value={open ? query : selected ? `${selected.name} (${selected.key})` : value ?? ""}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => {
            setQuery("");
            setOpen(true);
          }}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          placeholder={placeholder}
          className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm disabled:bg-slate-100"
        />
        {selected && !disabled && (
          <button
            type="button"
            onMouseDown={(e) => {
              e.preventDefault();
              onChange(null);
            }}
            title="Clear"
            className="text-xs text-slate-400 hover:text-slate-700"
          >
            ×
          </button>
        )}
      </div>
      {open && !disabled && (
        <div className="absolute z-10 mt-1 max-h-56 w-full min-w-[16rem] overflow-y-auto rounded border border-slate-200 bg-white shadow-lg">
          {matches.map((a) => (
            <button
              type="button"
              key={a.uid}
              onMouseDown={(e) => {
                e.preventDefault();
                onChange(a.uid);
                setQuery("");
                setOpen(false);
              }}
              className="block w-full px-2 py-1.5 text-left text-sm hover:bg-slate-50"
            >
              <span className="text-slate-900">{a.name}</span>{" "}
              <span className="text-xs text-slate-400">({a.key})</span>
            </button>
          ))}
          {matches.length === 0 && (
            <p className="px-2 py-1.5 text-sm text-slate-400">No matching assets.</p>
          )}
        </div>
      )}
    </div>
  );
}
