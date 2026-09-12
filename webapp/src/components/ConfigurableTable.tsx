import { ReactNode, useEffect, useMemo, useRef, useState } from "react";

export function formatCellValue(value: unknown): string {
  if (value == null) return "—";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "—";
  return String(value);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

export interface ColumnDef<T> {
  key: string;
  label: string;
  render: (row: T) => ReactNode;
  sortValue?: (row: T) => string | number | null;
  alwaysOn?: boolean;
  defaultVisible?: boolean;
  align?: "left" | "right";
}

interface SortState {
  key: string;
  dir: "asc" | "desc";
}

interface StoredPrefs {
  visible?: string[];
  sort?: SortState | null;
}

function loadPrefs(storageKey: string): StoredPrefs {
  try {
    const raw = localStorage.getItem(storageKey);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function savePrefs(storageKey: string, prefs: StoredPrefs) {
  try {
    localStorage.setItem(storageKey, JSON.stringify(prefs));
  } catch {
    // ignore
  }
}

export function useConfigurableColumns<T>(storageKey: string, columns: ColumnDef<T>[]) {
  const initial = useMemo(() => loadPrefs(storageKey), [storageKey]);
  const [visibleKeys, setVisibleKeys] = useState<Set<string>>(() => {
    if (initial.visible) return new Set(initial.visible);
    return new Set(columns.filter((c) => c.alwaysOn || c.defaultVisible !== false).map((c) => c.key));
  });
  const [sort, setSort] = useState<SortState | null>(initial.sort ?? null);

  useEffect(() => {
    savePrefs(storageKey, { visible: Array.from(visibleKeys), sort });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storageKey, visibleKeys, sort]);

  const orderedColumns = useMemo(
    () => columns.filter((c) => c.alwaysOn || visibleKeys.has(c.key)),
    [columns, visibleKeys],
  );

  function toggleColumn(key: string) {
    setVisibleKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function toggleSort(key: string) {
    setSort((prev) => {
      if (!prev || prev.key !== key) return { key, dir: "asc" };
      if (prev.dir === "asc") return { key, dir: "desc" };
      return null;
    });
  }

  function sortRows(rows: T[]): T[] {
    if (!sort) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (!col?.sortValue) return rows;
    const sorted = [...rows].sort((a, b) => {
      const av = col.sortValue!(a);
      const bv = col.sortValue!(b);
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (av < bv) return -1;
      if (av > bv) return 1;
      return 0;
    });
    if (sort.dir === "desc") sorted.reverse();
    return sorted;
  }

  return { visibleKeys, toggleColumn, sort, toggleSort, orderedColumns, sortRows };
}

export function ColumnPickerButton<T>({
  columns,
  visibleKeys,
  onToggle,
}: {
  columns: ColumnDef<T>[];
  visibleKeys: Set<string>;
  onToggle: (key: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const optional = columns.filter((c) => !c.alwaysOn);
  if (optional.length === 0) return null;

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="rounded border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
      >
        Columns
      </button>
      {open && (
        <div className="absolute right-0 z-10 mt-1 w-56 rounded border border-slate-200 bg-white p-2 shadow-lg">
          {optional.map((c) => (
            <label
              key={c.key}
              className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
            >
              <input
                type="checkbox"
                checked={visibleKeys.has(c.key)}
                onChange={() => onToggle(c.key)}
              />
              {c.label}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

export function SortableTh<T>({
  column,
  sort,
  onToggleSort,
  className,
}: {
  column: ColumnDef<T>;
  sort: SortState | null;
  onToggleSort: (key: string) => void;
  className?: string;
}) {
  const active = sort?.key === column.key;
  const sortable = !!column.sortValue;
  return (
    <th
      className={`px-4 py-2 ${sortable ? "cursor-pointer select-none hover:text-slate-700" : ""} ${className ?? ""}`}
      onClick={sortable ? () => onToggleSort(column.key) : undefined}
    >
      {column.label}
      {active && <span className="ml-1">{sort!.dir === "asc" ? "▲" : "▼"}</span>}
    </th>
  );
}
