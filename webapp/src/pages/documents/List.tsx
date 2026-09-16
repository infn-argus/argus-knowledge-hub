import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { documentsApi, schemasApi } from "../../api/client";
import { BulkActionsBar } from "../../components/BulkActionsBar";

const AUTHORITY_STYLES: Record<string, string> = {
  ufficiale: "bg-indigo-100 text-indigo-700",
  informativo: "bg-slate-100 text-slate-600",
  bozza_interna: "bg-amber-100 text-amber-700",
};

export function DocumentList() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["documents"], queryFn: () => documentsApi.list() });
  const schemas = useQuery({ queryKey: ["schemas"], queryFn: schemasApi.list });
  const documentSchemas = useMemo(
    () => (schemas.data ?? []).filter((s) => s.applies_to === "documents"),
    [schemas.data],
  );
  const typeName = useMemo(
    () => new Map(documentSchemas.map((s) => [s.uid, s.name])),
    [documentSchemas],
  );

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [target, setTarget] = useState("");

  const toggle = (uid: string) =>
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(uid)) next.delete(uid);
      else next.add(uid);
      return next;
    });

  const retype = useMutation({
    mutationFn: () => documentsApi.retype([...selected], target || null),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      setSelected(new Set());
      if (result!.not_found.length) {
        alert(`Moved ${result!.moved}. ${result!.not_found.length} could not be found.`);
      }
    },
    onError: () => alert("Could not move those documents."),
  });

  const rows = data ?? [];
  const allSelected = rows.length > 0 && selected.size === rows.length;

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Documents</h1>
        <Link
          to="/documents/new"
          className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          New document
        </Link>
      </div>

      {isLoading && <p className="mt-4 text-sm text-slate-500">Loading…</p>}

      {/* An import types documents by guessing from a label or a title, so
          correcting a batch of them is the normal case, not an edge one.
          The bar is always here: appearing on the first tick would push
          every row down under the pointer, mid-selection. */}
      <div className="mt-4 flex h-12 flex-wrap items-center gap-3 rounded border border-slate-200 bg-white px-3">
        {selected.size === 0 ? (
          <span className="text-sm text-slate-400">
            Select documents to move them to another type.
          </span>
        ) : (
          <>
          <span className="text-sm text-slate-600">{selected.size} selected</span>
          <span className="text-sm text-slate-400">move to</span>
          <select
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1 text-sm"
          >
            <option value="">No type</option>
            {documentSchemas.map((s) => (
              <option key={s.uid} value={s.uid}>
                {s.name}
              </option>
            ))}
          </select>
          <button
            onClick={() => retype.mutate()}
            disabled={retype.isPending}
            className="rounded bg-slate-900 px-3 py-1 text-sm text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {retype.isPending ? "Moving…" : "Move"}
          </button>
          <button
            onClick={() => setSelected(new Set())}
            className="text-sm text-slate-500 hover:underline"
          >
            Clear
          </button>
          </>
        )}
      </div>

      <BulkActionsBar
        selected={selected}
        kind="document_uids"
        label="documents"
        onStarted={() => {
          queryClient.invalidateQueries({ queryKey: ["documents"] });
          setSelected(new Set());
        }}
        onClear={() => setSelected(new Set())}
        bulkDelete={documentsApi.bulkDelete}
      />

      {data && (
        <div className="mt-4 overflow-hidden rounded-lg border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="w-8 px-3 py-2">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={() =>
                      setSelected(allSelected ? new Set() : new Set(rows.map((d) => d.uid)))
                    }
                    aria-label="Select all documents"
                  />
                </th>
                <th className="px-4 py-2">Code</th>
                <th className="px-4 py-2">Title</th>
                <th className="px-4 py-2">Type</th>
                <th className="px-4 py-2">Authority</th>
                <th className="px-4 py-2">Confidentiality</th>
                <th className="px-4 py-2">Published</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((d) => (
                <tr
                  key={d.uid}
                  className={selected.has(d.uid) ? "bg-indigo-50/60" : "hover:bg-slate-50"}
                >
                  <td className="px-3 py-2">
                    <input
                      type="checkbox"
                      checked={selected.has(d.uid)}
                      onChange={() => toggle(d.uid)}
                      aria-label={`Select ${d.title}`}
                    />
                  </td>
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
                    {d.document_type_uid ? typeName.get(d.document_type_uid) ?? "—" : "—"}
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={`rounded px-2 py-0.5 text-xs ${AUTHORITY_STYLES[d.authority_level] ?? ""}`}
                    >
                      {d.authority_level}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-slate-500">{d.confidentiality}</td>
                  <td className="px-4 py-2">
                    {d.current_revision_uid ? (
                      <span className="rounded bg-green-100 px-2 py-0.5 text-xs text-green-700">
                        published
                      </span>
                    ) : (
                      <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
                        unpublished
                      </span>
                    )}
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-6 text-center text-slate-400">
                    No documents yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
