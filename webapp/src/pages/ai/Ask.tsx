import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { aiApi } from "../../api/client";
import { ApiError } from "../../api/client";
import type { AskResult, AskStep } from "../../api/types";
import { MarkdownView } from "../../components/MarkdownView";

/** Asking the hub a question, and watching where the answer came from.
 *
 * This is a test harness, not a chat product. ARGUS claims that structured
 * knowledge answers what a pile of documents cannot; the only honest way
 * to find out is to ask in your own words and see which records were
 * actually opened. So the lookups are the main content of the page, not a
 * debug panel — an answer with no lookups behind it is the model talking
 * about some other laboratory, and it should be obvious at a glance.
 */

/** Questions worth trying first, each aimed at something different: a
 * count, a traversal, a document lookup, and one the corpus probably
 * cannot answer yet. */
const STARTERS = [
  "How many objects, tickets and documents are in this workspace?",
  "What cameras do we have, and where are they mounted?",
  "Which procedures cover the vacuum system?",
  "What has gone wrong with the BTF line before?",
];

function toolLabel(step: AskStep): string {
  const args = Object.entries(step.arguments)
    .filter(([, v]) => v !== null && v !== undefined && v !== "")
    .map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join(", ");
  return args ? `${step.tool}(${args})` : `${step.tool}()`;
}

/** How many records a result carried, for the one-line summary. */
function resultSummary(step: AskStep): string {
  if (step.error) return step.error;
  try {
    const data = JSON.parse(step.result) as Record<string, unknown>;
    if (typeof data.total === "number") return `${data.total} found`;
    if (Array.isArray(data.nodes)) {
      const edges = Array.isArray(data.edges) ? data.edges.length : 0;
      return `${data.nodes.length} connected records, ${edges} links`;
    }
    if (data.found === false) return "not found";
    if (data.found === true) return "1 record";
    return "";
  } catch {
    return "";
  }
}

function Step({ step, index }: { step: AskStep; index: number }) {
  const [open, setOpen] = useState(false);
  const summary = resultSummary(step);
  return (
    <li className="border-b border-slate-100 last:border-b-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-baseline gap-2 px-3 py-2 text-left hover:bg-slate-50"
      >
        <span className="w-5 shrink-0 text-xs tabular-nums text-slate-400">{index + 1}</span>
        <code
          className={`min-w-0 flex-1 truncate text-xs ${
            step.error ? "text-rose-700" : "text-slate-700"
          }`}
        >
          {toolLabel(step)}
        </code>
        {summary && (
          <span
            className={`shrink-0 text-xs ${step.error ? "text-rose-600" : "text-slate-500"}`}
          >
            {summary}
          </span>
        )}
        <span className="shrink-0 text-xs text-slate-400">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <pre className="max-h-80 overflow-auto border-t border-slate-100 bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-700">
          {step.result}
        </pre>
      )}
    </li>
  );
}

export function Ask() {
  const [question, setQuestion] = useState("");
  const [asked, setAsked] = useState("");
  const status = useQuery({ queryKey: ["ai-status"], queryFn: aiApi.status });

  const ask = useMutation<AskResult, Error, string>({
    mutationFn: (q: string) => aiApi.ask(q),
    onMutate: (q) => setAsked(q),
  });

  const usable = status.data?.validated && status.data?.enabled;
  const result = ask.data;

  const submit = (q: string) => {
    const text = q.trim();
    if (!text || ask.isPending) return;
    setQuestion(text);
    ask.mutate(text);
  };

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-6">
      <header>
        <h1 className="text-lg font-semibold text-slate-900">Ask</h1>
        <p className="mt-1 text-sm text-slate-600">
          A question answered only from this workspace's records — objects, tickets and
          documentation — showing every lookup it made. If the answer rests on nothing,
          you will see that here.
        </p>
      </header>

      {status.isSuccess && !usable && (
        <div className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {status.data?.reason ?? "AI features are not available in this workspace."}{" "}
          <Link className="underline" to="/workspace/ai">
            Configure the AI endpoint
          </Link>
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(question);
        }}
        className="flex gap-2"
      >
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="What has gone wrong with this magnet before?"
          disabled={!usable || ask.isPending}
          className="flex-1 rounded border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-50"
        />
        <button
          type="submit"
          disabled={!usable || ask.isPending || !question.trim()}
          className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:bg-slate-300"
        >
          {ask.isPending ? "Looking…" : "Ask"}
        </button>
      </form>

      {!ask.data && !ask.isPending && (
        <div className="flex flex-wrap gap-2">
          {STARTERS.map((q) => (
            <button
              key={q}
              type="button"
              disabled={!usable}
              onClick={() => submit(q)}
              className="rounded-full border border-slate-300 px-3 py-1 text-xs text-slate-600 hover:bg-slate-50 disabled:opacity-50"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {ask.isPending && (
        <p className="text-sm text-slate-500">
          Searching the records for “{asked}” — this takes a few seconds per lookup.
        </p>
      )}

      {ask.isError && (
        <div className="rounded border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
          {ask.error instanceof ApiError
            ? String(ask.error.detail ?? ask.error.message)
            : ask.error.message}
        </div>
      )}

      {result && (
        <>
          <section className="rounded border border-slate-200 bg-white">
            <div className="border-b border-slate-100 px-3 py-2 text-xs text-slate-500">
              “{asked}” · {result.seconds}s ·{" "}
              {result.steps.length === 1 ? "1 lookup" : `${result.steps.length} lookups`}
            </div>
            <div className="px-4 py-3">
              {result.answer ? (
                <MarkdownView markdown={result.answer} />
              ) : (
                <p className="text-sm text-slate-500">
                  No answer came back{result.error ? `: ${result.error}` : "."}
                </p>
              )}
            </div>
            {result.stopped === "exhausted" && (
              <p className="border-t border-slate-100 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                This was cut short at the lookup limit — the answer is whatever had been
                found by then, not a complete one.
              </p>
            )}
          </section>

          <section className="rounded border border-slate-200 bg-white">
            <h2 className="border-b border-slate-100 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
              What it looked at
            </h2>
            {result.steps.length === 0 ? (
              <p className="px-3 py-3 text-sm text-rose-700">
                Nothing. The answer above came from the model alone, not from this
                workspace — treat it as unfounded.
              </p>
            ) : (
              <ol>
                {result.steps.map((step, i) => (
                  <Step key={i} step={step} index={i} />
                ))}
              </ol>
            )}
          </section>
        </>
      )}
    </div>
  );
}
