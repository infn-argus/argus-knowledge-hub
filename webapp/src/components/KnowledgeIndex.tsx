import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { aiApi, ApiError } from "../api/client";

const KIND_LABEL: Record<string, string> = {
  document: "Documents",
  ticket: "Tickets",
  ticket_comment: "Ticket comments",
  attachment: "Attached files",
  asset_comment: "Equipment comments",
};

/** The written knowledge Ask ARGUS can search by meaning: what is indexed, and a button to bring it up to
 * date (only what changed since the last run is embedded again). */
export function KnowledgeIndex() {
  const queryClient = useQueryClient();
  const status = useQuery({
    queryKey: ["ai-knowledge"],
    queryFn: aiApi.knowledge,
    refetchInterval: (q) => (q.state.data?.run?.state === "running" ? 3000 : false),
  });
  const reindex = useMutation({
    mutationFn: aiApi.reindexKnowledge,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["ai-knowledge"] }),
  });
  const s = status.data;
  const run = s?.run;
  const running = run?.state === "running";
  const result = run?.result;
  return (
    <section className="mt-6 rounded border border-slate-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-slate-900">Written knowledge for Ask ARGUS</h2>
      <p className="mt-1 text-xs text-slate-600">
        Procedures, tickets and their comments, comments on equipment and the text of attached files
        (datasheets, manuals) are cut into passages and indexed with the embedding model, so Ask ARGUS can
        find what they say by meaning, in any language. Each answer still only shows what the person asking
        may read.
      </p>
      {s && !s.pgvector && (
        <p className="mt-3 rounded bg-amber-50 px-3 py-2 text-xs text-amber-900">
          This database has no pgvector extension. Run Postgres with pgvector (the{" "}
          <code>pgvector/pgvector:pg16-trixie</code> image) to enable it.
        </p>
      )}
      {s && s.pgvector && !s.embedding_model && (
        <p className="mt-3 rounded bg-amber-50 px-3 py-2 text-xs text-amber-900">
          Set an embedding model above (for example <code>qwen3-embedding-8b</code>) to index.
        </p>
      )}
      {s?.ready && (
        <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-xs sm:grid-cols-3">
          {Object.keys(KIND_LABEL).map((k) => (
            <div key={k} className="flex justify-between gap-2">
              <dt className="text-slate-500">{KIND_LABEL[k]}</dt>
              <dd className="tabular-nums text-slate-900">
                {s.sources[k] ?? 0} <span className="text-slate-400">({s.passages[k] ?? 0} passages)</span>
              </dd>
            </div>
          ))}
        </dl>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <button
          type="button"
          disabled={!s?.pgvector || !s?.embedding_model || running || reindex.isPending}
          onClick={() => reindex.mutate()}
          className="rounded bg-slate-900 px-3 py-1.5 text-xs font-medium text-white disabled:bg-slate-300"
        >
          {running ? "Indexing…" : s?.run ? "Update the index" : "Build the index"}
        </button>
        {run && !running && (
          <span className="text-xs text-slate-500">
            Last run {run.finished_at ? new Date(run.finished_at).toLocaleString() : ""}
            {result && typeof result.indexed === "number" &&
              ` — ${result.indexed} indexed, ${result.unchanged ?? 0} unchanged, ${result.removed ?? 0} removed` +
              (result.unreadable ? `, ${result.unreadable} without text (scans?)` : "") +
              ` in ${result.seconds}s`}
          </span>
        )}
        {reindex.isError && (
          <span className="text-xs text-rose-700">
            {reindex.error instanceof ApiError ? String(reindex.error.detail ?? reindex.error.message) : String(reindex.error)}
          </span>
        )}
      </div>
      {result?.failed && result.failed.length > 0 && (
        <ul className="mt-2 list-disc pl-5 text-xs text-rose-700">
          {result.failed.slice(0, 5).map((f) => <li key={f}>{f}</li>)}
        </ul>
      )}
    </section>
  );
}
