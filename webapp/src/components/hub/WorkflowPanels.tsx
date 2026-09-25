/** A ticket's workflow (the moves its type allows and what each needs), its
 * watchers, and the notification bell in the header. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { workflowApi } from "../../api/client";
import type { WorkflowTransition } from "../../api/ledgerTypes";
import { errorText } from "./LedgerPanels";
import { Card } from "./ui";

const CATEGORY_TONE: Record<string, string> = {
  open: "bg-slate-100 text-slate-700",
  active: "bg-indigo-50 text-indigo-700",
  waiting: "bg-amber-50 text-amber-800",
  done: "bg-emerald-50 text-emerald-700",
};

export function TicketWorkflowCard({ ticketUid }: { ticketUid: string }) {
  const queryClient = useQueryClient();
  const moves = useQuery({ queryKey: ["ticket-transitions", ticketUid], queryFn: () => workflowApi.transitions(ticketUid) });
  const [pending, setPending] = useState<WorkflowTransition | null>(null);
  const [assignee, setAssignee] = useState("");
  const [resolution, setResolution] = useState("");
  const [comment, setComment] = useState("");
  const move = useMutation({
    mutationFn: (t: WorkflowTransition) =>
      workflowApi.transition(ticketUid, {
        to: t.to,
        assignee: assignee || undefined,
        resolution: resolution || undefined,
        comment: comment || undefined,
      }),
    onSuccess: () => {
      setPending(null);
      setAssignee("");
      setResolution("");
      setComment("");
      for (const key of ["ticket-transitions", "issues", "issue-comments", "ticket-watchers", "hub-ticket", "notifications"])
        queryClient.invalidateQueries({ queryKey: [key] });
    },
  });
  if (!moves.data) return null;
  const m = moves.data;
  const current = m.states.find((s) => s.key === m.state);
  return (
    <Card title="Workflow" action={<span className="text-xs text-slate-400">{m.workflow.name}</span>}>
      <p className="py-1 text-sm">
        <span className={`rounded px-2 py-0.5 text-xs font-medium ${CATEGORY_TONE[current?.category ?? "open"]}`}>
          {m.state_name}
        </span>
        {current?.sla_hours && (
          <span className="ml-2 text-xs text-slate-500">escalates after {current.sla_hours} h in this state</span>
        )}
      </p>
      <div className="mt-1 flex flex-wrap gap-2">
        {m.transitions.map((t) => (
          <button
            key={t.to}
            onClick={() => (t.requires.length ? setPending(t) : move.mutate(t))}
            className="rounded border border-slate-300 px-2.5 py-1 text-xs hover:bg-slate-50"
            title={t.requires.length ? `Needs ${t.requires.join(", ")}` : undefined}
          >
            {t.name}
            {t.name !== t.to_name ? ` → ${t.to_name}` : ""}
          </button>
        ))}
        {m.transitions.length === 0 && <span className="text-xs text-slate-500">No move is possible from here.</span>}
      </div>
      {pending && (
        <div className="mt-2 space-y-2 rounded border border-slate-200 bg-slate-50 p-2 text-xs">
          <p className="font-medium text-slate-800">{pending.name} needs:</p>
          {pending.requires.includes("assignee") && (
            <input value={assignee} onChange={(e) => setAssignee(e.target.value)} placeholder="Assignee" className="w-full rounded border border-slate-300 px-2 py-1" />
          )}
          {pending.requires.includes("resolution") && (
            <input value={resolution} onChange={(e) => setResolution(e.target.value)} placeholder="Resolution (Fixed, Won't fix, …)" className="w-full rounded border border-slate-300 px-2 py-1" />
          )}
          {pending.requires.includes("comment") && (
            <textarea value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Comment" rows={2} className="w-full rounded border border-slate-300 px-2 py-1" />
          )}
          <div className="flex gap-2">
            <button onClick={() => move.mutate(pending)} className="rounded bg-slate-900 px-3 py-1 font-medium text-white">
              {pending.name}
            </button>
            <button onClick={() => setPending(null)} className="rounded border border-slate-300 px-3 py-1">
              Cancel
            </button>
          </div>
        </div>
      )}
      {move.isError && <p className="mt-2 text-sm text-red-600">{errorText(move.error)}</p>}
    </Card>
  );
}

export function WatchersCard({ ticketUid }: { ticketUid: string }) {
  const queryClient = useQueryClient();
  const watchers = useQuery({ queryKey: ["ticket-watchers", ticketUid], queryFn: () => workflowApi.watchers(ticketUid) });
  const [who, setWho] = useState("");
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["ticket-watchers", ticketUid] });
  const add = useMutation({ mutationFn: (u?: string) => workflowApi.watch(ticketUid, u), onSuccess: () => { setWho(""); refresh(); } });
  const remove = useMutation({ mutationFn: (u: string) => workflowApi.unwatch(ticketUid, u), onSuccess: refresh });
  return (
    <Card title="Watchers" action={<span className="text-xs text-slate-400">told about every change</span>}>
      <ul className="flex flex-wrap gap-1.5 py-1">
        {(watchers.data ?? []).map((w) => (
          <li key={w} className="flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-700">
            {w}
            <button onClick={() => remove.mutate(w)} className="text-slate-400 hover:text-red-600" aria-label={`Remove ${w}`}>
              ×
            </button>
          </li>
        ))}
      </ul>
      <div className="mt-1 flex gap-2">
        <input value={who} onChange={(e) => setWho(e.target.value)} placeholder="Add someone (e-mail)" className="flex-1 rounded border border-slate-300 px-2 py-1 text-xs" />
        <button onClick={() => add.mutate(who || undefined)} className="rounded border border-slate-300 px-2 py-1 text-xs">
          {who ? "Add" : "Watch"}
        </button>
      </div>
      {(add.isError || remove.isError) && <p className="mt-1 text-xs text-red-600">{errorText(add.error ?? remove.error)}</p>}
    </Card>
  );
}

export function NotificationBell() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  // Personal notifications need a signed-in person; an API-token profile has none.
  const items = useQuery({ queryKey: ["notifications"], queryFn: () => workflowApi.notifications(), retry: false,
                           refetchInterval: 60_000 });
  const readAll = useMutation({ mutationFn: workflowApi.readAll,
                                onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }) });
  useEffect(() => {
    const close = (e: MouseEvent) => box.current && !box.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  if (items.isError || !items.data) return null;
  const unread = items.data.filter((n) => !n.read).length;
  return (
    <div className="relative" ref={box}>
      <button onClick={() => setOpen(!open)} className="relative rounded-md px-2 py-1 text-slate-500 hover:bg-slate-100" aria-label="Notifications">
        🔔
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 rounded-full bg-red-600 px-1 text-[10px] font-medium text-white">{unread}</span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-1 w-96 rounded-lg border border-slate-200 bg-white shadow-lg">
          <div className="flex items-center justify-between border-b border-slate-100 px-3 py-2">
            <span className="text-sm font-semibold text-slate-900">Notifications</span>
            {unread > 0 && (
              <button onClick={() => readAll.mutate()} className="text-xs text-indigo-700 hover:underline">
                Mark all read
              </button>
            )}
          </div>
          <ul className="max-h-96 divide-y divide-slate-50 overflow-y-auto">
            {items.data.length === 0 && <li className="px-3 py-4 text-sm text-slate-500">Nothing yet.</li>}
            {items.data.map((n) => (
              <li key={n.id} className={`px-3 py-2 text-sm ${n.read ? "text-slate-500" : "text-slate-900"}`}>
                {n.issue_uid ? (
                  <Link to={`/tickets/${n.issue_uid}`} onClick={() => { workflowApi.readNotification(n.id); setOpen(false); }} className="hover:underline">
                    {n.title}
                  </Link>
                ) : (
                  n.title
                )}
                <span className="block text-[11px] text-slate-400">
                  {n.kind} · {new Date(n.created_at).toLocaleString()}
                  {n.actor ? ` · ${n.actor}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
