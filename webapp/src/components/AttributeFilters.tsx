import { SchemaAttribute } from "../api/types";

export type FilterValue =
  | { kind: "text"; value: string }
  | { kind: "range"; min?: number; max?: number }
  | { kind: "bool"; value: boolean }
  | { kind: "dateRange"; from?: string; to?: string }
  | { kind: "in"; values: string[] };

export type FilterState = Record<string, FilterValue>;

function toArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : value === undefined || value === null ? [] : [value];
}

/** True if a stored attribute value satisfies one filter. Multi-value
 * attributes match if ANY stored element satisfies the filter. */
function matchesOne(filter: FilterValue, value: unknown): boolean {
  switch (filter.kind) {
    case "text": {
      const needle = filter.value.trim().toLowerCase();
      if (!needle) return true;
      return toArray(value).some((v) => String(v ?? "").toLowerCase().includes(needle));
    }
    case "range": {
      return toArray(value).some((v) => {
        const n = Number(v);
        if (Number.isNaN(n)) return false;
        if (filter.min !== undefined && n < filter.min) return false;
        if (filter.max !== undefined && n > filter.max) return false;
        return true;
      });
    }
    case "bool":
      return toArray(value).some((v) => Boolean(v) === filter.value);
    case "dateRange": {
      return toArray(value).some((v) => {
        const t = new Date(String(v)).getTime();
        if (Number.isNaN(t)) return false;
        if (filter.from && t < new Date(filter.from).getTime()) return false;
        if (filter.to && t > new Date(filter.to + "T23:59:59").getTime()) return false;
        return true;
      });
    }
    case "in": {
      if (filter.values.length === 0) return true;
      const set = new Set(filter.values);
      return toArray(value).some((v) => set.has(String(v)));
    }
  }
}

export function matchesFilters(
  attributes: Record<string, unknown>,
  filters: FilterState,
): boolean {
  return Object.entries(filters).every(([key, filter]) => matchesOne(filter, attributes[key]));
}

export function defaultFilterFor(attribute: SchemaAttribute): FilterValue {
  switch (attribute.type) {
    case "integer":
    case "float":
      return { kind: "range" };
    case "boolean":
      return { kind: "bool", value: true };
    case "date":
    case "datetime":
      return { kind: "dateRange" };
    case "enumeration":
    case "reference":
      return { kind: "in", values: [] };
    default:
      return { kind: "text", value: "" };
  }
}

function isEmptyFilter(filter: FilterValue): boolean {
  switch (filter.kind) {
    case "text":
      return filter.value.trim() === "";
    case "range":
      return filter.min === undefined && filter.max === undefined;
    case "bool":
      return false;
    case "dateRange":
      return !filter.from && !filter.to;
    case "in":
      return filter.values.length === 0;
  }
}

export function activeFilterCount(filters: FilterState): number {
  return Object.values(filters).filter((f) => !isEmptyFilter(f)).length;
}
