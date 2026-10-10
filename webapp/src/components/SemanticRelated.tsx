import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { graphApi } from "../api/client";

const PATH: Record<string, string> = { asset: "/assets/", ticket: "/tickets/", document: "/documents/" };
const KIND: Record<string, string> = { asset: "Object", ticket: "Ticket", document: "Document" };

/** What the knowledge index finds about the same thing as this record — the semantic graph, as a list: each
 *  record with how close it is and the two passages that are closest, so the link explains itself. Nobody had
 *  to link them; that is the point, and also why each is a lead to check, not a fact. */
export function SemanticRelated({ kind, uid }: { kind: "asset" | "ticket" | "document"; uid: string }) {
  const q = useQuery({ queryKey: ["semantic", kind, uid], queryFn: () => graphApi.semantic(kind, uid), staleTime: 60_000 });
  const g = q.data;
  if (q.isLoading) return <p className="text-sm text-slate-400">Looking for what is about the same thing…</p>;
  if (q.isError || !g) return null;
  if (!g.available) return <p className="text-sm text-slate-400">{g.reason ?? "The written knowledge is not indexed."}</p>;
  const label = new Map(g.nodes.map((n) => [`${n.kind}:${n.uid}`, n]));
  if (g.edges.length === 0) {
    return <p className="text-sm text-slate-400">
      {g.basis === "nothing indexed" ? "Nothing of this record is indexed yet." : "Nothing else is about the same thing."}
    </p>;
  }
  return (
    <ul className="divide-y divide-slate-100">
      {g.edges.map((e) => {
        const n = label.get(`${e.to_kind}:${e.to_uid}`);
        return (
          <li key={`${e.to_kind}:${e.to_uid}`} className="py-2">
            <div className="flex items-center gap-2 text-sm">
              <span className="w-20 shrink-0 text-xs text-slate-500">{KIND[e.to_kind] ?? e.to_kind}</span>
              <Link to={`${PATH[e.to_kind] ?? "/"}${e.to_uid}`} className="min-w-0 flex-1 truncate font-medium text-indigo-700 hover:underline">
                {n?.label ?? e.to_uid}
              </Link>
              <span className="flex shrink-0 items-center gap-1 text-xs tabular-nums text-slate-500" title="How close in meaning, 0 to 1">
                <span className="inline-block h-1.5 w-12 rounded-full bg-slate-100">
                  <span className="block h-1.5 rounded-full bg-teal-600" style={{ width: `${Math.round(e.score * 100)}%` }} />
                </span>
                {e.score.toFixed(2)}
              </span>
            </div>
            <details className="mt-1 text-xs text-slate-600">
              <summary className="cursor-pointer text-slate-400">why</summary>
              <p className="mt-1 whitespace-pre-line rounded bg-slate-50 p-2">“{e.excerpt}”</p>
              <p className="mt-1 text-slate-400">closest to this record's: “{e.matched}”</p>
            </details>
          </li>
        );
      })}
    </ul>
  );
}
