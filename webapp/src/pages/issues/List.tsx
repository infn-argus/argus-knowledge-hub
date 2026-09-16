import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { issuesApi } from "../../api/client";
import { BulkActionsBar } from "../../components/BulkActionsBar";

export function IssueList() {
  const queryClient = useQueryClient();
  const [stateFilter, setStateFilter] = useState<"all" | "open" | "closed">("open");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const { data, isLoading } = useQuery({ queryKey: ["issues"], queryFn: () => issuesApi.list() });

  const toggle = (uid: string) =>
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(uid)) next.delete(uid);
      else next.add(uid);
      return next;
    });

  const filtered = useMemo(() => {
    if (!data) return [];
    if (stateFilter === "all") return data;
    if (stateFilter === "open") return data.filter((i) => i.state !== "closed");
    return data.filter((i) => i.state === "closed");
  }, [data, stateFilter]);

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Tickets</h1>
        <Link
          to="/tickets/new"
          className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          New ticket
        </Link>
      </div>

      <div className="mt-4 flex gap-2 text-sm">
        {(["open", "closed", "all"] as const).map((s) => (
          <button
            key={s}
            onClick={() => setStateFilter(s)}
            className={`rounded px-3 py-1 ${
              stateFilter === s ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600"
            }`}
          >
            {s[0].toUpperCase() + s.slice(1)}
          </button>
        ))}
      </div>

      {isLoading && <p className="mt-4 text-sm text-slate-500">Loading…</p>}

      {data && (
        <>
        <BulkActionsBar
          selected={selected}
          kind="issue_uids"
          label="tickets"
          onStarted={() => {
            queryClient.invalidateQueries({ queryKey: ["issues"] });
            setSelected(new Set());
          }}
          onClear={() => setSelected(new Set())}
          bulkDelete={issuesApi.bulkDelete}
        />
        <div className="mt-4 overflow-hidden rounded-lg border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="w-8 px-3 py-2">
                  <input
                    type="checkbox"
                    checked={filtered.length > 0 && selected.size === filtered.length}
                    onChange={() =>
                      setSelected(
                        selected.size === filtered.length
                          ? new Set()
                          : new Set(filtered.map((i) => i.uid)),
                      )
                    }
                    aria-label="Select all tickets"
                  />
                </th>
                <th className="px-4 py-2">Title</th>
                <th className="px-4 py-2">State</th>
                <th className="px-4 py-2">Priority</th>
                <th className="px-4 py-2">Assignee</th>
                <th className="px-4 py-2">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((i) => (
                <tr key={i.uid} className={selected.has(i.uid) ? "bg-indigo-50/60" : "hover:bg-slate-50"}>
                  <td className="px-3 py-2">
                    <input
                      type="checkbox"
                      checked={selected.has(i.uid)}
                      onChange={() => toggle(i.uid)}
                      aria-label={`Select ${i.title}`}
                    />
                  </td>
                  <td className="px-4 py-2 font-medium text-slate-900">
                    <Link to={`/tickets/${i.uid}`} className="hover:underline">
                      {i.title}
                    </Link>
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={`rounded px-2 py-0.5 text-xs ${
                        i.state === "closed"
                          ? "bg-slate-100 text-slate-500"
                          : "bg-green-100 text-green-700"
                      }`}
                    >
                      {i.state}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-slate-500">{i.priority ?? "—"}</td>
                  <td className="px-4 py-2 text-slate-500">{i.assignee ?? "—"}</td>
                  <td className="px-4 py-2 text-slate-500">
                    {new Date(i.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-slate-400">
                    No tickets.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        </>
      )}
    </div>
  );
}
