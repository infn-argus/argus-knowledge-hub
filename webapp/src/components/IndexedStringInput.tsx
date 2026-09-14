import { useMemo, useState } from "react";

/** A string attribute marked `indexed`: a key, not prose.
 *
 * What the workspace has already used is offered as you type, and an
 * existing term is reused with its original spelling — otherwise "BTF",
 * "btf" and "BTF " become three values that no filter brings back
 * together. New terms are still allowed: this is a vocabulary that grows
 * from what people actually write, not a list someone has to curate
 * up front.
 */
export function IndexedStringInput({
  value,
  onChange,
  suggestions,
  disabled,
  loading,
  className,
}: {
  value: string;
  onChange: (value: string) => void;
  suggestions: string[];
  disabled?: boolean;
  loading?: boolean;
  className?: string;
}) {
  const [open, setOpen] = useState(false);

  const matches = useMemo(() => {
    const q = value.trim().toLowerCase();
    return suggestions
      .filter((s) => s.toLowerCase() !== q && (!q || s.toLowerCase().includes(q)))
      .slice(0, 12);
  }, [suggestions, value]);

  return (
    <div className="relative">
      <input
        className={className}
        disabled={disabled}
        value={value}
        placeholder={loading ? "Loading…" : suggestions.length ? "Type or pick…" : undefined}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
      />
      {open && matches.length > 0 && (
        <div className="absolute z-20 mt-1 max-h-56 w-full min-w-[14rem] overflow-y-auto rounded border border-slate-200 bg-white shadow-lg">
          {matches.map((s) => (
            <button
              type="button"
              key={s}
              onMouseDown={(e) => {
                e.preventDefault();
                onChange(s);
                setOpen(false);
              }}
              className="block w-full px-2 py-1.5 text-left text-sm hover:bg-slate-50"
            >
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
