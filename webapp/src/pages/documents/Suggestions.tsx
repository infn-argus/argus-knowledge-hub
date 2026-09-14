import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { aiApi } from "../../api/client";
import { useCurrentWorkspaceId } from "../../api/useCurrentWorkspaceId";

/** Types a model proposed, for a person to accept or reject.
 *
 * Nothing here has been applied. That is the point: an import typing 258
 * of 273 pages as "Note" is a problem a model can help with, but a library
 * typed by a machine nobody checked is not a typed library.
 */
export function DocumentSuggestions() {
  const queryClient = useQueryClient();
  const workspaceId = useCurrentWorkspaceId();
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [onlyUntyped, setOnlyUntyped] = useState(true);

  const status = useQuery({ queryKey: ["ai-status"], queryFn: aiApi.status });
  const suggestions = useQuery({
    queryKey: ["ai-suggestions"],
    queryFn: () => aiApi.suggestions("proposed"),
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["ai-suggestions"] });
    queryClient.invalidateQueries({ queryKey: ["documents"] });
    setSelected(new Set());
  };

  const [progress, setProgress] = useState<{ seen: number; proposed: number } | null>(null);

  /** Works through the backlog in bounded requests.
   *
   * One request per document set would be simpler, but a hundred documents
   * is about two minutes and an ingress cuts a request off at sixty
   * seconds. Asking repeatedly keeps every request short and lets the
   * count climb while it runs.
   */
  const run = useMutation({
    mutationFn: async () => {
      const BATCH = 25;
      let seen = 0;
      let proposed = 0;
      let failed = 0;
      for (;;) {
        const result = await aiApi.suggestDocumentTypes(onlyUntyped, BATCH);
        seen += result.considered;
        proposed += result.proposed;
        failed += result.failed_batches;
        setProgress({ seen, proposed });
        queryClient.invalidateQueries({ queryKey: ["ai-suggestions"] });
        // Fewer than asked for means the backlog is done.
        if (result.considered < BATCH) break;
      }
      return { considered: seen, proposed, unchanged: 0, failed_batches: failed };
    },
    onSuccess: refresh,
    onSettled: () => setProgress(null),
  });
  const accept = useMutation({
    mutationFn: (ids: number[]) => aiApi.accept(ids),
    onSuccess: refresh,
  });
  const reject = useMutation({
    mutationFn: (ids: number[]) => aiApi.reject(ids),
    onSuccess: refresh,
  });

  const rows = suggestions.data ?? [];
  const allSelected = rows.length > 0 && selected.size === rows.length;
  const ai = status.data;

  if (ai && !ai.validated) {
    return (
      <div className="max-w-2xl">
        <h1 className="text-2xl font-semibold text-slate-900">Type suggestions</h1>
        <p className="mt-3 rounded border border-slate-200 bg-white p-4 text-sm text-slate-600">
          {ai.reason}
          {workspaceId && (
            <>
              {" "}
              <Link
                to={`/workspaces/${workspaceId}/ai`}
                className="text-indigo-600 hover:underline"
              >
                Set up the AI endpoint
              </Link>
              .
            </>
          )}
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Type suggestions</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-500">
            Proposals only — nothing below has been applied to a document. An import types a
            page from its labels, and a wiki whose pages carry none ends up as a pile of
            notes; this is a way to sort that out without opening each one.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <label className="flex items-center gap-1.5 text-xs text-slate-600">
            <input
              type="checkbox"
              checked={onlyUntyped}
              onChange={(e) => setOnlyUntyped(e.target.checked)}
            />
            Only untyped documents
          </label>
          <button
            onClick={() => run.mutate()}
            disabled={run.isPending}
            className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {run.isPending ? "Asking…" : "Suggest types"}
          </button>
        </div>
      </div>

      {run.isPending && (
        <p className="mt-3 text-sm text-slate-500">
          Reading the documents — about a second each.
          {progress && ` ${progress.seen} looked at, ${progress.proposed} proposed so far.`}
        </p>
      )}

      {run.data && (
        <p className="mt-3 rounded border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600">
          Looked at {run.data.considered}: {run.data.proposed} proposed
          {run.data.failed_batches > 0 && (
            <span className="text-amber-700">
              {" "}
              · {run.data.failed_batches} batch(es) the model didn't answer usefully
            </span>
          )}
          .
        </p>
      )}

      {run.isError && (
        <p className="mt-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {(run.error as Error).message}
        </p>
      )}

      {rows.length > 0 && (
        <div className="mt-4 flex items-center gap-3 rounded border border-slate-200 bg-white px-3 py-2">
          <span className="text-sm text-slate-600">{selected.size} selected</span>
          <button
            onClick={() => accept.mutate([...selected])}
            disabled={selected.size === 0 || accept.isPending}
            className="rounded bg-slate-900 px-3 py-1 text-sm text-white hover:bg-slate-800 disabled:opacity-50"
          >
            Apply
          </button>
          <button
            onClick={() => reject.mutate([...selected])}
            disabled={selected.size === 0 || reject.isPending}
            className="rounded border border-slate-300 px-3 py-1 text-sm text-slate-600 hover:bg-slate-50 disabled:opacity-50"
          >
            Dismiss
          </button>
          <span className="ml-auto text-xs text-slate-400">
            {rows.length} proposal{rows.length === 1 ? "" : "s"} · {rows[0]?.model}
          </span>
        </div>
      )}

      <div className="mt-4 overflow-hidden rounded-lg border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="w-8 px-3 py-2">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={() =>
                    setSelected(allSelected ? new Set() : new Set(rows.map((r) => r.id)))
                  }
                  aria-label="Select all proposals"
                />
              </th>
              <th className="px-4 py-2">Document</th>
              <th className="px-4 py-2">Now</th>
              <th className="px-4 py-2">Proposed</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((row) => (
              <tr key={row.id} className={selected.has(row.id) ? "bg-indigo-50/60" : ""}>
                <td className="px-3 py-2">
                  <input
                    type="checkbox"
                    checked={selected.has(row.id)}
                    onChange={() =>
                      setSelected((current) => {
                        const next = new Set(current);
                        if (next.has(row.id)) next.delete(row.id);
                        else next.add(row.id);
                        return next;
                      })
                    }
                    aria-label={`Select ${row.target_label ?? row.target_uid}`}
                  />
                </td>
                <td className="px-4 py-2 font-medium text-slate-900">
                  <Link to={`/documents/${row.target_uid}`} className="hover:underline">
                    {row.target_label ?? row.target_uid}
                  </Link>
                </td>
                <td className="px-4 py-2 text-slate-400">{row.previous_label ?? "—"}</td>
                <td className="px-4 py-2">
                  <span className="rounded bg-indigo-50 px-2 py-0.5 text-xs text-indigo-700">
                    {row.suggested_label}
                  </span>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-slate-400">
                  {suggestions.isLoading
                    ? "Loading…"
                    : "Nothing proposed. Run “Suggest types” to look at the untyped documents."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
