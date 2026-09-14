import { useMemo, useState } from "react";

/** Labels as chips, with what's already in use offered as you type.
 *
 * The suggestion list is the point: a free-text field invites "BTF",
 * "btf" and "BTF " as three labels meaning one thing, which then can't be
 * filtered on. Existing labels are matched case-insensitively and reused
 * with their original spelling.
 */
export function LabelInput({
  value,
  onChange,
  suggestions = [],
  placeholder = "Add a label…",
  /** What these values are called, for the hint under the field — this
   * input holds components and sprints as well as labels. */
  noun = "labels",
}: {
  value: string[];
  onChange: (labels: string[]) => void;
  suggestions?: string[];
  placeholder?: string;
  noun?: string;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    const taken = new Set(value.map((v) => v.toLowerCase()));
    return suggestions
      .filter((s) => !taken.has(s.toLowerCase()) && (!q || s.toLowerCase().includes(q)))
      .slice(0, 12);
  }, [suggestions, query, value]);

  const add = (raw: string) => {
    const label = raw.trim();
    if (!label) return;
    // Reuse the existing spelling when one matches, so the vocabulary
    // doesn't fork on capitalisation.
    const existing = suggestions.find((s) => s.toLowerCase() === label.toLowerCase());
    const chosen = existing ?? label;
    if (!value.some((v) => v.toLowerCase() === chosen.toLowerCase())) {
      onChange([...value, chosen]);
    }
    setQuery("");
    setOpen(false);
  };

  return (
    <div>
      <div className="flex flex-wrap items-center gap-1 rounded border border-slate-300 px-2 py-1.5">
        {value.map((label) => (
          <span
            key={label}
            className="inline-flex items-center gap-1 rounded bg-indigo-50 px-1.5 py-0.5 text-xs text-indigo-700"
          >
            {label}
            <button
              type="button"
              onClick={() => onChange(value.filter((v) => v !== label))}
              className="text-indigo-400 hover:text-indigo-700"
              aria-label={`Remove ${label}`}
            >
              ×
            </button>
          </span>
        ))}
        <div className="relative min-w-32 flex-1">
          <input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            onBlur={() => window.setTimeout(() => setOpen(false), 150)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === ",") {
                // Enter would otherwise submit the surrounding form.
                e.preventDefault();
                add(query);
              } else if (e.key === "Backspace" && !query && value.length) {
                onChange(value.slice(0, -1));
              }
            }}
            placeholder={value.length ? "" : placeholder}
            className="w-full text-sm focus:outline-none"
          />
          {open && matches.length > 0 && (
            <ul className="absolute z-20 mt-1 max-h-48 w-full min-w-40 overflow-y-auto rounded border border-slate-200 bg-white shadow-lg">
              {matches.map((s) => (
                <li key={s}>
                  <button
                    type="button"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => add(s)}
                    className="w-full px-2 py-1 text-left text-xs text-slate-700 hover:bg-slate-50"
                  >
                    {s}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      <p className="mt-1 text-xs text-slate-500">
        Enter or comma to add. Existing {noun} are suggested as you type.
      </p>
    </div>
  );
}
