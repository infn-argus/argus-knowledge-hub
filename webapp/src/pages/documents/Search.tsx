import { useQueries, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { documentsApi, schemasApi } from "../../api/client";
import { AttributeFilterInput } from "../../components/AttributeFilterInput";
import { activeFilterCount, defaultFilterFor, FilterState, matchesFilters } from "../../components/AttributeFilters";
import { effectiveAttributes } from "../../lib/schemaAttributes";

export function DocumentSearch() {
  const [q, setQ] = useState("");
  const [schemaUid, setSchemaUid] = useState("");
  const [filters, setFilters] = useState<FilterState>({});
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const schemas = useQuery({ queryKey: ["schemas"], queryFn: schemasApi.list });
  const documents = useQuery({ queryKey: ["documents"], queryFn: () => documentsApi.list() });

  const documentSchemas = useMemo(
    () => (schemas.data ?? []).filter((s) => s.applies_to === "documents"),
    [schemas.data],
  );
  const schema = documentSchemas.find((s) => s.uid === schemaUid);
  const attrDefs = effectiveAttributes(schema, schemas.data);

  const typeMatches = useMemo(
    () => (documents.data ?? []).filter((d) => !schemaUid || d.document_type_uid === schemaUid),
    [documents.data, schemaUid],
  );
  const hasActiveFilters = activeFilterCount(filters) > 0;

  // Attribute values live on the current revision, not the Document row, so
  // advanced filtering needs each candidate's current revision fetched —
  // only done once a type is picked (bounding the fetch count) and a filter
  // is actually set.
  const currentRevisionQueries = useQueries({
    queries:
      schema && hasActiveFilters
        ? typeMatches.map((d) => ({
            queryKey: ["document-current", d.uid],
            queryFn: () => documentsApi.current(d.uid),
            enabled: !!d.current_revision_uid,
            retry: false as const,
          }))
        : [],
  });

  const results = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const textFiltered = typeMatches.filter(
      (d) => !needle || d.title.toLowerCase().includes(needle) || d.code.toLowerCase().includes(needle),
    );
    if (!schema || !hasActiveFilters) return textFiltered;

    const attrsByDoc = new Map(
      typeMatches.map((d, i) => [d.uid, currentRevisionQueries[i]?.data?.attributes ?? null]),
    );
    return textFiltered.filter((d) => {
      const attrs = attrsByDoc.get(d.uid);
      return attrs !== null && attrs !== undefined && matchesFilters(attrs, filters);
    });
  }, [typeMatches, q, schema, hasActiveFilters, filters, currentRevisionQueries]);

  const revisionsLoading = hasActiveFilters && currentRevisionQueries.some((r) => r.isLoading);

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-900">Search documents</h1>

      <div className="mt-4 flex gap-3">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search by title or code…"
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
          {documentSchemas.map((s) => (
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
              <p className="text-xs text-slate-400">
                Filters match against each document's current published revision — unpublished
                documents won't match any filter here.
              </p>
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
            </div>
          )}
        </div>
      )}

      {(documents.isLoading || revisionsLoading) && (
        <p className="mt-4 text-sm text-slate-500">Loading…</p>
      )}

      {documents.data && (
        <>
          <div className="mt-4 overflow-hidden rounded-lg border border-slate-200 bg-white">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2">Code</th>
                  <th className="px-4 py-2">Title</th>
                  <th className="px-4 py-2">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {results.map((d) => (
                  <tr key={d.uid} className="hover:bg-slate-50">
                    <td className="px-4 py-2 font-mono text-xs text-slate-500">
                      <Link to={`/documents/${d.uid}`} className="hover:underline">
                        {d.code}
                      </Link>
                    </td>
                    <td className="px-4 py-2 font-medium text-slate-900">
                      <Link to={`/documents/${d.uid}`} className="hover:underline">
                        {d.title}
                      </Link>
                    </td>
                    <td className="px-4 py-2 text-slate-500">
                      {d.current_revision_uid ? "published" : "unpublished"}
                    </td>
                  </tr>
                ))}
                {results.length === 0 && (
                  <tr>
                    <td colSpan={3} className="px-4 py-6 text-center text-slate-400">
                      No documents match.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-xs text-slate-400">
            Showing {results.length} of {documents.data.length}
          </p>
        </>
      )}
    </div>
  );
}
