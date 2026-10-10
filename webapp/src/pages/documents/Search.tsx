import { useQueries, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { documentsApi, schemasApi } from "../../api/client";
import { AttributeFilterInput } from "../../components/AttributeFilterInput";
import { activeFilterCount, defaultFilterFor, FilterState, matchesFilters } from "../../components/AttributeFilters";
import { effectiveAttributes } from "../../lib/schemaAttributes";
import { ListDate, SortHeader, useSort } from "../../components/SortableTable";
import { SchemaTree } from "../../components/SchemaTree";
import { useShowKeys } from "../../api/displayPrefs";

export function DocumentSearch() {
  const showKeys = useShowKeys();
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

  const matched = useMemo(() => {
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

  const { sorted: results, sort, toggle: sortBy } = useSort(
    matched,
    {
      code: (d) => d.code,
      title: (d) => d.title,
      status: (d) => (d.current_revision_uid ? "published" : "unpublished"),
      created: (d) => d.created_at,
      updated: (d) => d.updated_at,
    },
    { key: "updated", dir: "desc" },
    "document-search",
  );

  return (
    <div className="flex min-h-[calc(100vh-7rem)] gap-4">
      <aside className="flex w-72 shrink-0 flex-col rounded-lg border border-slate-200 bg-white p-3">
        <div className="mb-2 flex items-center justify-between px-1">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Document types</p>
          <Link to="/schemas/new?applies_to=documents" title="New document type" className="text-sm font-medium text-slate-400 hover:text-slate-700">+</Link>
        </div>
        <button
          type="button"
          onClick={() => setSchemaUid("")}
          className={`mb-1 rounded px-2 py-1 text-left text-xs ${!schemaUid ? "bg-slate-100 font-medium text-slate-900" : "text-slate-600 hover:bg-slate-50"}`}
        >
          All documents
          <span className="ml-1 text-slate-400">{documents.data?.length ?? 0}</span>
        </button>
        <div className="min-h-0 flex-1">
          <SchemaTree appliesTo="documents" fill selectedUid={schemaUid || null} onSelect={(uid) => setSchemaUid(uid ?? "")} />
        </div>
      </aside>
      <div className="min-w-0 flex-1">
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
                  {showKeys && <SortHeader label="Code" column="code" sort={sort} onSort={sortBy} />}
                  <SortHeader label="Title" column="title" sort={sort} onSort={sortBy} />
                  <SortHeader label="Status" column="status" sort={sort} onSort={sortBy} />
                  <SortHeader label="Created" column="created" sort={sort} onSort={sortBy} time />
                  <SortHeader label="Updated" column="updated" sort={sort} onSort={sortBy} time />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {results.map((d) => (
                  <tr key={d.uid} className="hover:bg-slate-50">
                    {showKeys && (
                    <td className="px-4 py-2 font-mono text-xs text-slate-500">
                        <Link to={`/documents/${d.uid}`} className="hover:underline">
                          {d.code}
                        </Link>
                      </td>
                    )}
                    <td className="px-4 py-2 font-medium text-slate-900">
                      <Link to={`/documents/${d.uid}`} className="hover:underline">
                        {d.title}
                      </Link>
                    </td>
                    <td className="px-4 py-2 text-slate-500">
                      {d.current_revision_uid ? "published" : "unpublished"}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2 text-slate-500"><ListDate value={d.created_at} /></td>
                    <td className="whitespace-nowrap px-4 py-2 text-slate-500"><ListDate value={d.updated_at} /></td>
                  </tr>
                ))}
                {results.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
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
    </div>
  );
}
