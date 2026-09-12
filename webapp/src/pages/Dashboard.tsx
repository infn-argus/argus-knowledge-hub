import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { assetsApi, documentsApi, issuesApi, schemasApi } from "../api/client";

function StatCard({ label, value, to }: { label: string; value: number | string; to?: string }) {
  const content = (
    <>
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-1 text-3xl font-semibold text-slate-900">{value}</p>
    </>
  );
  const className = "block rounded-lg border border-slate-200 bg-white p-6 shadow-sm hover:border-slate-300";
  return to ? (
    <Link to={to} className={className}>
      {content}
    </Link>
  ) : (
    <div className={className}>{content}</div>
  );
}

function StatGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">{title}</h2>
      <div className="mt-2 grid grid-cols-2 gap-4">{children}</div>
    </div>
  );
}

function relativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

type ActivityKind = "asset" | "ticket" | "document";
interface ActivityItem {
  kind: ActivityKind;
  label: string;
  to: string;
  updatedAt: string;
}

const KIND_STYLES: Record<ActivityKind, string> = {
  asset: "bg-indigo-100 text-indigo-700",
  ticket: "bg-amber-100 text-amber-700",
  document: "bg-emerald-100 text-emerald-700",
};

export function Dashboard() {
  const schemas = useQuery({ queryKey: ["schemas"], queryFn: schemasApi.list });
  const assets = useQuery({ queryKey: ["assets"], queryFn: () => assetsApi.list() });
  const issues = useQuery({ queryKey: ["issues"], queryFn: () => issuesApi.list() });
  const documents = useQuery({ queryKey: ["documents"], queryFn: () => documentsApi.list() });

  const objectTypeCount = (schemas.data ?? []).filter((s) => (s.applies_to ?? "objects") === "objects").length;
  const openTickets = issues.data?.filter((i) => i.state !== "closed").length ?? 0;
  const publishedDocuments = documents.data?.filter((d) => d.current_revision_uid).length ?? 0;

  const activity: ActivityItem[] = [
    ...(assets.data ?? []).map((a): ActivityItem => ({
      kind: "asset", label: a.name, to: `/assets/${a.uid}`, updatedAt: a.updated_at,
    })),
    ...(issues.data ?? []).map((i): ActivityItem => ({
      kind: "ticket", label: i.title, to: `/tickets/${i.uid}`, updatedAt: i.updated_at,
    })),
    ...(documents.data ?? []).map((d): ActivityItem => ({
      kind: "document", label: d.title, to: `/documents/${d.uid}`, updatedAt: d.updated_at,
    })),
  ]
    .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
    .slice(0, 10);

  const loaded = !schemas.isLoading && !assets.isLoading && !issues.isLoading && !documents.isLoading;

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-900">Dashboard</h1>

      <div className="mt-6 space-y-6">
        <StatGroup title="Assets">
          <StatCard label="Object types" value={schemas.isLoading ? "…" : objectTypeCount} />
          <StatCard label="Objects" value={assets.data?.length ?? "…"} to="/assets/search" />
        </StatGroup>

        <StatGroup title="Tickets">
          <StatCard label="Open tickets" value={issues.isLoading ? "…" : openTickets} to="/tickets" />
          <StatCard label="Total tickets" value={issues.data?.length ?? "…"} to="/tickets" />
        </StatGroup>

        <StatGroup title="Documentation">
          <StatCard
            label="Published documents"
            value={documents.isLoading ? "…" : publishedDocuments}
            to="/documents"
          />
          <StatCard label="Total documents" value={documents.data?.length ?? "…"} to="/documents" />
        </StatGroup>
      </div>

      <div className="mt-8">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Recent activity
        </h2>
        <div className="mt-2 overflow-hidden rounded-lg border border-slate-200 bg-white">
          {!loaded && <p className="p-4 text-sm text-slate-500">Loading…</p>}
          {loaded && activity.length === 0 && (
            <p className="p-4 text-sm text-slate-400">Nothing yet.</p>
          )}
          {loaded && activity.length > 0 && (
            <ul className="divide-y divide-slate-100">
              {activity.map((item, i) => (
                <li key={i}>
                  <Link
                    to={item.to}
                    className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm hover:bg-slate-50"
                  >
                    <span className="flex min-w-0 items-center gap-2">
                      <span
                        className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wide ${KIND_STYLES[item.kind]}`}
                      >
                        {item.kind}
                      </span>
                      <span className="truncate text-slate-900">{item.label}</span>
                    </span>
                    <span className="shrink-0 text-xs text-slate-400">
                      {relativeTime(item.updatedAt)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
