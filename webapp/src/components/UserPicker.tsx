import { useMemo, useState } from "react";
import { MemberDirectoryEntry } from "../api/types";

function displayName(u: MemberDirectoryEntry): string {
  return u.name || u.email;
}

/** Search-as-you-type picker over the workspace's registered members, used
 * for "user"-type attribute values (e.g. a ticket's Assignee). */
export function UserPicker({
  members,
  value,
  onChange,
  disabled,
  placeholder = "Search members…",
}: {
  members: MemberDirectoryEntry[];
  value?: string | null;
  onChange: (userId: string | null) => void;
  disabled?: boolean;
  placeholder?: string;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);

  const byId = useMemo(() => new Map(members.map((m) => [m.user_id, m])), [members]);
  const selected = value ? byId.get(value) : undefined;

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = q
      ? members.filter(
          (m) => displayName(m).toLowerCase().includes(q) || m.email.toLowerCase().includes(q),
        )
      : members;
    return [...filtered].sort((a, b) => displayName(a).localeCompare(displayName(b))).slice(0, 30);
  }, [members, query]);

  return (
    <div className="relative flex-1">
      <div className="flex items-center gap-1">
        <input
          disabled={disabled}
          value={open ? query : selected ? displayName(selected) : value ?? ""}
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
          {matches.map((m) => (
            <button
              type="button"
              key={m.user_id}
              onMouseDown={(e) => {
                e.preventDefault();
                onChange(m.user_id);
                setQuery("");
                setOpen(false);
              }}
              className="block w-full px-2 py-1.5 text-left text-sm hover:bg-slate-50"
            >
              <span className="text-slate-900">{displayName(m)}</span>{" "}
              {m.name && <span className="text-xs text-slate-400">({m.email})</span>}
            </button>
          ))}
          {matches.length === 0 && (
            <p className="px-2 py-1.5 text-sm text-slate-400">No matching members.</p>
          )}
        </div>
      )}
    </div>
  );
}
