import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { SchemaTree } from "../../components/SchemaTree";
import { ListDate, SortHeader, useSort } from "../../components/SortableTable";
import { Link } from "react-router-dom";
import { assetsApi, schemasApi } from "../../api/client";
import { AttributeFilterInput } from "../../components/AttributeFilterInput";
import { activeFilterCount, defaultFilterFor, FilterState, matchesFilters } from "../../components/AttributeFilters";
import { BulkActionsBar } from "../../components/BulkActionsBar";
import { OwnerBadge } from "../../components/OwnerBadge";
import { useCurrentWorkspaceId } from "../../api/useCurrentWorkspaceId";
import { effectiveAttributes } from "../../lib/schemaAttributes";

export function AssetSearch() {
  const queryClient = useQueryClient();
  const [q, setQ] = useState("");
  const [schemaUid, setSchemaUid] = useState("");
  const [owner, setOwner] = useState<"all" | "own" | "shared">("own");
  const currentWorkspaceId = useCurrentWorkspaceId();
  const [filters, setFilters] = useState<FilterState>({});
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const toggle = (uid: string) =>
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(uid)) next.delete(uid);
      else next.add(uid);
      return next;
    });

  const schemas = useQuery({ queryKey: ["schemas"], queryFn: schemasApi.list });
  const assets = useQuery({ queryKey: ["assets"], queryFn: () => assetsApi.list() });

  const objectSchemas = useMemo(
    () => (schemas.data ?? []).filter((s) => s.applies_to === "objects"),
    [schemas.data],
  );
  // The chosen type and every type below it: choosing "Asset" lists the objects of all its kinds.
  const familyUids = useMemo(() => {
    if (!schemaUid) return null;
    const children = new Map<string, string[]>();
    for (const s of objectSchemas) {
      if (s.parent_schema_uid) children.set(s.parent_schema_uid, [...(children.get(s.parent_schema_uid) ?? []), s.uid]);
    }
    const out = new Set<string>();
    const walk = (uid: string) => {
      if (out.has(uid)) return;
      out.add(uid);
      (children.get(uid) ?? []).forEach(walk);
    };
    walk(schemaUid);
    return out;
  }, [objectSchemas, schemaUid]);
  const schema = objectSchemas.find((s) => s.uid === schemaUid);
  const attrDefs = effectiveAttributes(schema, schemas.data);

  const matched = useMemo(() => {
    if (!assets.data) return [];
    const needle = q.trim().toLowerCase();
    return assets.data.filter((a) => {
      if (needle && !a.name.toLowerCase().includes(needle) && !a.key.toLowerCase().includes(needle)) {
        return false;
      }
      if (familyUids && !familyUids.has(a.schema_uid)) return false;
      if (currentWorkspaceId !== null) {
        if (owner === "own" && a.workspace_id !== currentWorkspaceId) return false;
        if (owner === "shared" && a.workspace_id === currentWorkspaceId) return false;
      }
      if (schema && Object.keys(filters).length > 0 && !matchesFilters(a.attributes, filters)) {
        return false;
      }
      return true;
    });
  }, [assets.data, q, familyUids, schema, filters, owner, currentWorkspaceId]);
  const { sorted: results, sort, toggle: sortBy } = useSort(
    matched,
    {
      name: (a) => a.name,
      key: (a) => a.key,
      type: (a) => a.type,
      created: (a) => a.created_at,
      updated: (a) => a.updated_at,
    },
    { key: "name", dir: "asc" },
    "assets",
  );

  return (
    <div className="flex min-h-[calc(100vh-7rem)] gap-4">
      <aside className="flex w-72 shrink-0 flex-col rounded-lg border border-slate-200 bg-white p-3">
        <div className="mb-2 flex items-center justify-between px-1">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Object types</p>
          <Link to="/schemas/new" title="New object type" className="text-sm font-medium text-slate-400 hover:text-slate-700">+</Link>
        </div>
        <button
          type="button"
          onClick={() => setSchemaUid("")}
          className={`mb-1 rounded px-2 py-1 text-left text-xs ${!schemaUid ? "bg-slate-100 font-medium text-slate-900" : "text-slate-600 hover:bg-slate-50"}`}
        >
          All objects
          <span className="ml-1 text-slate-400">{assets.data?.length ?? 0}</span>
        </button>
        <div className="min-h-0 flex-1">
          <SchemaTree appliesTo="objects" fill selectedUid={schemaUid || null} onSelect={(uid) => setSchemaUid(uid ?? "")} />
        </div>
      </aside>
      <div className="min-w-0 flex-1">
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
        <select
          value={owner}
          onChange={(e) => setOwner(e.target.value as "all" | "own" | "shared")}
          className="rounded border border-slate-300 px-3 py-2 text-sm"
          aria-label="Whose objects"
        >
          <option value="own">This workspace only</option>
          <option value="all">This workspace + shared</option>
          <option value="shared">Shared from other workspaces</option>
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
          <BulkActionsBar
            selected={selected}
            kind="asset_uids"
            label="objects"
            onStarted={() => {
              queryClient.invalidateQueries({ queryKey: ["assets"] });
              setSelected(new Set());
            }}
            onClear={() => setSelected(new Set())}
            bulkDelete={assetsApi.bulkDelete}
          />
          <div className="mt-4 overflow-hidden rounded-lg border border-slate-200 bg-white">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="w-8 px-3 py-2">
                    <input
                      type="checkbox"
                      checked={results.length > 0 && selected.size === results.length}
                      onChange={() =>
                        setSelected(
                          selected.size === results.length
                            ? new Set()
                            : new Set(results.map((a) => a.uid)),
                        )
                      }
                      aria-label="Select all objects"
                    />
                  </th>
                  <SortHeader label="Name" column="name" sort={sort} onSort={sortBy} />
                  <SortHeader label="Key" column="key" sort={sort} onSort={sortBy} />
                  <SortHeader label="Type" column="type" sort={sort} onSort={sortBy} />
                  <SortHeader label="Created" column="created" sort={sort} onSort={sortBy} time />
                  <SortHeader label="Updated" column="updated" sort={sort} onSort={sortBy} time />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {results.map((a) => (
                  <tr key={a.uid} className={selected.has(a.uid) ? "bg-indigo-50/60" : "hover:bg-slate-50"}>
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        checked={selected.has(a.uid)}
                        onChange={() => toggle(a.uid)}
                        aria-label={`Select ${a.name}`}
                      />
                    </td>
                    <td className="px-4 py-2 font-medium text-slate-900">
                      <Link to={`/assets/${a.uid}`} className="hover:underline">
                        {a.name}
                      </Link>
                    </td>
                    <td className="px-4 py-2 text-slate-500">{a.key}</td>
                    <td className="px-4 py-2 text-slate-500">
                      {a.type}
                      <OwnerBadge workspaceId={a.workspace_id} />
                    </td>
                    <td className="whitespace-nowrap px-4 py-2 text-slate-500"><ListDate value={a.created_at} /></td>
                    <td className="whitespace-nowrap px-4 py-2 text-slate-500"><ListDate value={a.updated_at} /></td>
                  </tr>
                ))}
                {results.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-6 text-center text-slate-400">
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
    </div>
  );
}
