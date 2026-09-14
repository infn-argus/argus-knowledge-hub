import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { assetsApi, schemasApi } from "../../api/client";
import { AttributeFilterInput } from "../../components/AttributeFilterInput";
import { activeFilterCount, defaultFilterFor, FilterState, matchesFilters } from "../../components/AttributeFilters";
import { effectiveAttributes } from "../../lib/schemaAttributes";

export function AssetSearch() {
  const [q, setQ] = useState("");
  const [schemaUid, setSchemaUid] = useState("");
  const [filters, setFilters] = useState<FilterState>({});
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const schemas = useQuery({ queryKey: ["schemas"], queryFn: schemasApi.list });
  const assets = useQuery({ queryKey: ["assets"], queryFn: () => assetsApi.list() });

  const objectSchemas = useMemo(
    () => (schemas.data ?? []).filter((s) => s.applies_to === "objects"),
    [schemas.data],
  );
  const schema = objectSchemas.find((s) => s.uid === schemaUid);
  const attrDefs = effectiveAttributes(schema, schemas.data);

  const results = useMemo(() => {
    if (!assets.data) return [];
    const needle = q.trim().toLowerCase();
    return assets.data.filter((a) => {
      if (needle && !a.name.toLowerCase().includes(needle) && !a.key.toLowerCase().includes(needle)) {
        return false;
      }
      if (schemaUid && a.schema_uid !== schemaUid) return false;
      if (schema && Object.keys(filters).length > 0 && !matchesFilters(a.attributes, filters)) {
        return false;
      }
      return true;
    });
  }, [assets.data, q, schemaUid, schema, filters]);

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Search objects</h1>
        {/* The same affordance tickets and documents have: this is where
            the Assets section lands, so it is where somebody expects to be
            able to add one. */}
        <Link
          to="/assets/new"
          className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          New object
        </Link>
      </div>

      <div className="mt-4 flex gap-3">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search by name or key…"
          className="flex-1 rounded border border-slate-300 px-3 py-2 text-sm"
        />
        <select
          value={schemaUid}
          onChange={(e) => {
            setSchemaUid(e.target.value);
            setFilters({});
          }}
          className="rounded border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">All types</option>
          {objectSchemas.map((s) => (
            <option key={s.uid} value={s.uid}>
              {s.name}
            </option>
          ))}
        </select>
      </div>

      {schema && attrDefs.length > 0 && (
        <div className="mt-3">
          <button
            type="button"
            onClick={() => setAdvancedOpen((v) => !v)}
            className="text-sm text-slate-600 hover:text-slate-900"
          >
            {advancedOpen ? "▾" : "▸"} Advanced filters
            {activeFilterCount(filters) > 0 && (
              <span className="ml-1 rounded-full bg-slate-900 px-1.5 py-0.5 text-[10px] text-white">
                {activeFilterCount(filters)}
              </span>
            )}
          </button>
          {advancedOpen && (
            <div className="mt-2 space-y-3 rounded border border-slate-200 bg-white p-3">
              {attrDefs.map((attr) => {
                const key = attr.key ?? attr.name;
                const current = filters[key] ?? defaultFilterFor(attr);
                return (
                  <div key={key} className="flex items-center gap-3">
                    <label className="w-32 shrink-0 text-xs font-medium text-slate-600">
                      {attr.name}
                    </label>
                    <AttributeFilterInput
                      attribute={attr}
                      value={current}
                      onChange={(v) => setFilters((prev) => ({ ...prev, [key]: v }))}
                    />
                  </div>
                );
              })}
              {activeFilterCount(filters) > 0 && (
                <button
                  type="button"
                  onClick={() => setFilters({})}
                  className="text-xs text-slate-500 hover:text-slate-800"
                >
                  Clear filters
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {assets.isLoading && <p className="mt-4 text-sm text-slate-500">Loading…</p>}

      {assets.data && (
        <>
          <div className="mt-4 overflow-hidden rounded-lg border border-slate-200 bg-white">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2">Name</th>
                  <th className="px-4 py-2">Key</th>
                  <th className="px-4 py-2">Type</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {results.map((a) => (
                  <tr key={a.uid} className="hover:bg-slate-50">
                    <td className="px-4 py-2 font-medium text-slate-900">
                      <Link to={`/assets/${a.uid}`} className="hover:underline">
                        {a.name}
                      </Link>
                    </td>
                    <td className="px-4 py-2 text-slate-500">{a.key}</td>
                    <td className="px-4 py-2 text-slate-500">{a.type}</td>
                  </tr>
                ))}
                {results.length === 0 && (
                  <tr>
                    <td colSpan={3} className="px-4 py-6 text-center text-slate-400">
                      No objects match.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-xs text-slate-400">
            Showing {results.length} of {assets.data.length}
          </p>
        </>
      )}
    </div>
  );
}
