import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { helpApi } from "../../api/client";
import { MarkdownView } from "../../components/MarkdownView";

/** The user guide: how to do things in ARGUS, step by step. The same Markdown Ask ARGUS reads (its
 * `search_help` and `read_help` tools), so what the page says and what the assistant says agree. */
export function HelpPage() {
  const { slug } = useParams();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const query = params.get("q") ?? "";
  const [draft, setDraft] = useState(query);
  useEffect(() => setDraft(query), [query]);

  const index = useQuery({ queryKey: ["help"], queryFn: helpApi.topics, staleTime: 5 * 60_000 });
  const current = slug ?? (query ? undefined : index.data?.[0]?.slug);
  const topic = useQuery({
    queryKey: ["help", current],
    queryFn: () => helpApi.topic(current!),
    enabled: !!current,
    staleTime: 5 * 60_000,
  });
  const results = useQuery({
    queryKey: ["help-search", query],
    queryFn: () => helpApi.search(query),
    enabled: query.trim().length >= 2,
  });

  // A section asked for by the address (#anchor, from a search result) is scrolled to once the topic is shown.
  useEffect(() => {
    const anchor = decodeURIComponent(window.location.hash.slice(1));
    if (!anchor || !topic.data) return;
    const heading = [...document.querySelectorAll("article h2")].find(
      (h) => h.textContent?.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") === anchor,
    );
    heading?.scrollIntoView({ block: "start" });
  }, [topic.data]);

  return (
    <div className="-m-6 flex h-[calc(100vh-3.5rem)] min-h-0">
      <aside className="flex w-64 shrink-0 flex-col border-r border-slate-200 bg-white">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const q = draft.trim();
            if (q.length >= 2) navigate(`/help?q=${encodeURIComponent(q)}`);
          }}
          className="p-3"
        >
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Search the guide…"
            className="w-full rounded border border-slate-300 px-3 py-1.5 text-sm"
          />
        </form>
        <ul className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
          {(index.data ?? []).map((t) => (
            <li key={t.slug}>
              <Link
                to={`/help/${t.slug}`}
                title={t.summary}
                className={`block rounded px-2 py-1.5 text-sm ${
                  t.slug === current && !query ? "bg-slate-100 font-medium text-slate-900" : "text-slate-600 hover:bg-slate-50"
                }`}
              >
                {t.title}
              </Link>
            </li>
          ))}
          {index.isError && <li className="px-2 text-xs text-rose-600">The guide could not be loaded.</li>}
        </ul>
      </aside>

      <section className="min-w-0 flex-1 overflow-y-auto bg-slate-50">
        <div className="mx-auto max-w-3xl p-6">
          {query && (
            <div>
              <div className="flex items-baseline justify-between">
                <h1 className="text-lg font-semibold text-slate-900">“{query}”</h1>
                <button type="button" onClick={() => setParams({})} className="text-xs text-slate-500 underline">
                  Clear
                </button>
              </div>
              {results.isLoading && <p className="mt-3 text-sm text-slate-400">Searching…</p>}
              {results.data?.length === 0 && (
                <p className="mt-3 text-sm text-slate-500">
                  Nothing in the guide matches. Try other words, or{" "}
                  <Link className="underline" to={`/ask?draft=${encodeURIComponent(query)}`}>ask ARGUS</Link>.
                </p>
              )}
              <ul className="mt-4 space-y-3">
                {(results.data ?? []).map((r) => (
                  <li key={`${r.topic}#${r.anchor}`} className="rounded-lg border border-slate-200 bg-white p-4">
                    <Link
                      to={`/help/${r.topic}${r.anchor ? `#${r.anchor}` : ""}`}
                      className="text-sm font-medium text-indigo-700 hover:underline"
                    >
                      {r.title} › {r.section}
                    </Link>
                    <p className="mt-1 line-clamp-3 whitespace-pre-line text-xs text-slate-600">
                      {r.text.replace(/[`*|#]/g, "").slice(0, 400)}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {!query && topic.data && (
            <article>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h1 className="text-2xl font-semibold text-slate-900">{topic.data.title}</h1>
                  <p className="mt-1 text-sm text-slate-500">{topic.data.summary}</p>
                </div>
                <Link
                  to={`/ask?draft=${encodeURIComponent(`Walk me through "${topic.data.title}" step by step.`)}`}
                  className="shrink-0 rounded border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50"
                  title="Ask ARGUS answers from this guide and your workspace"
                >
                  Ask ARGUS to walk me through this
                </Link>
              </div>
              <div className="mt-6 rounded-lg border border-slate-200 bg-white p-6">
                <MarkdownView markdown={topic.data.body} />
              </div>
            </article>
          )}
          {!query && topic.isError && <p className="text-sm text-rose-600">No such help topic.</p>}
        </div>
      </section>
    </div>
  );
}
