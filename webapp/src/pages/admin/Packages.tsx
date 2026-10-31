import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, packagesApi, type UpgradeEverywhereResult } from "../../api/client";
import { PackageManager } from "../workspace/Packages";

function problem(e: unknown): string {
  if (e instanceof ApiError) {
    const d = (e.body as { detail?: unknown })?.detail;
    if (d && typeof d === "object" && "error" in d) return String((d as { error: string }).error);
    if (typeof d === "string") return d;
  }
  return "It could not be done.";
}

const STATUS: Record<string, { label: string; tone: string }> = {
  ready: { label: "ready — no decision to make", tone: "text-emerald-700" },
  upgraded: { label: "upgraded", tone: "text-emerald-700" },
  after_catalogue: { label: "after its shared catalogue", tone: "text-slate-600" },
  needs_decisions: { label: "needs decisions — upgrade it on its own", tone: "text-amber-800" },
  refused: { label: "refused", tone: "text-red-700" },
};

/** One package behind in some workspaces: preview the upgrade everywhere, then apply it where no decision is
 *  needed. The others are listed with a way to their own upgrade. */
function Everywhere({ id, name, version, behind, onOpen }: {
  id: string; name: string; version: string; behind: string[]; onOpen: (ws: string) => void;
}) {
  const queryClient = useQueryClient();
  const [result, setResult] = useState<UpgradeEverywhereResult | null>(null);
  const preview = useMutation({ mutationFn: () => packagesApi.previewEverywhere(id), onSuccess: setResult });
  const apply = useMutation({
    mutationFn: () => packagesApi.upgradeEverywhere(id),
    onSuccess: (r) => {
      setResult(r);
      queryClient.invalidateQueries({ queryKey: ["admin-packages"] });
      queryClient.invalidateQueries({ queryKey: ["workspace-packages"] });
    },
  });
  const ready = (result?.workspaces ?? []).filter((w) => w.status === "ready" || w.status === "after_catalogue").length;
  const applied = result?.workspaces.some((w) => w.status === "upgraded");
  return (
    <li className="rounded border border-slate-200 bg-white p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <span className="font-medium text-slate-900">{name}</span>{" "}
          <span className="font-mono text-xs text-slate-500">{id} {version}</span>
          <p className="text-xs text-slate-500">
            Behind in {behind.length} workspace{behind.length === 1 ? "" : "s"}: {behind.join(", ")}
          </p>
        </div>
        <button type="button" disabled={preview.isPending || apply.isPending} onClick={() => preview.mutate()}
                className="rounded border border-slate-300 px-3 py-1 text-xs hover:bg-slate-50 disabled:opacity-50">
          {preview.isPending ? "Working it out…" : "Preview upgrade everywhere"}
        </button>
      </div>
      {preview.isError && <p className="mt-2 text-sm text-red-600">{problem(preview.error)}</p>}
      {result && (
        <div className="mt-2 space-y-2">
          <ul className="space-y-1 text-sm">
            {result.workspaces.map((w) => (
              <li key={w.workspace_id} className="flex flex-wrap gap-x-2">
                <button type="button" onClick={() => onOpen(w.workspace_id)}
                        className="font-mono text-sky-800 hover:underline">{w.workspace_id}</button>
                <span className="text-slate-500">{w.from_version} → {w.to_version}</span>
                <span className={STATUS[w.status]?.tone}>
                  {STATUS[w.status]?.label ?? w.status}
                  {w.status === "needs_decisions" && w.decisions ? ` (${w.decisions})` : ""}
                </span>
                {(w.steps ?? []).filter((s) => s.package_id !== id).length > 0 && (
                  <span className="text-xs text-slate-500">
                    with {(w.steps ?? []).filter((s) => s.package_id !== id)
                      .map((s) => `${s.package_id} ${s.version}`).join(", ")}
                  </span>
                )}
                {w.error && <span className="basis-full text-xs text-red-700">{w.error}</span>}
              </li>
            ))}
          </ul>
          {!applied && ready > 0 && (
            <button type="button" disabled={apply.isPending} onClick={() => apply.mutate()}
                    className="rounded bg-slate-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50">
              {apply.isPending ? "Upgrading…" : `Upgrade ${ready} workspace${ready === 1 ? "" : "s"}`}
            </button>
          )}
          {apply.isError && <p className="text-sm text-red-600">{problem(apply.error)}</p>}
        </div>
      )}
    </li>
  );
}

/** Administration → Packages: every workspace's packages. Upgrade a package everywhere it is behind (where no
 *  decision is needed), or open any workspace to upgrade, go back or add a package there. */
export function AdminPackagesPage() {
  const every = useQuery({ queryKey: ["admin-packages"], queryFn: packagesApi.everywhere });
  const [open, setOpen] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const behind = (every.data?.packages ?? []).filter((p) => p.behind.length > 0);
  const workspaces = (every.data?.workspaces ?? []).filter((w) =>
    !q || `${w.id} ${w.name}`.toLowerCase().includes(q.toLowerCase()));

  function openWorkspace(ws: string) {
    setOpen(ws);
    setQ("");
    requestAnimationFrame(() => document.getElementById(`ws-${ws}`)?.scrollIntoView?.({ block: "start" }));
  }

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Packages</h1>
        <p className="mt-1 text-sm text-slate-500">
          The template packages of every workspace. Upgrade a package everywhere it is behind, or open a
          workspace to upgrade, go back to a version it had, or add a package — each previewed first.
        </p>
      </div>
      {every.isError && <p className="text-sm text-red-600">{problem(every.error)}</p>}
      {every.isLoading && <p className="text-sm text-slate-500">Loading…</p>}

      {every.data && (
        <section aria-label="Upgrades available">
          <h2 className="mb-2 text-sm font-semibold text-slate-900">Upgrades available</h2>
          {behind.length === 0
            ? <p className="text-sm text-slate-500">Every workspace has the version of each package this installation ships.</p>
            : <ul className="space-y-2">
                {behind.map((p) => <Everywhere key={p.id} {...p} onOpen={openWorkspace} />)}
              </ul>}
          <p className="mt-2 text-xs text-slate-500">
            Shared catalogues are upgraded before the workspaces that hang from them. A workspace whose upgrade
            needs a decision is left as it is: open it and decide there.
          </p>
        </section>
      )}

      {every.data && (
        <section aria-label="Workspaces">
          <div className="mb-2 flex flex-wrap items-end justify-between gap-2">
            <h2 className="text-sm font-semibold text-slate-900">Workspaces</h2>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find a workspace"
                   className="w-56 rounded border border-slate-300 px-2 py-1 text-sm" />
          </div>
          <ul className="divide-y divide-slate-100 rounded border border-slate-200 bg-white">
            {workspaces.map((w) => {
              const upgrades = w.packages.filter((p) => p.upgrade_available).length;
              const isOpen = open === w.id;
              return (
                <li key={w.id} id={`ws-${w.id}`} className="px-4 py-2">
                  <button type="button" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : w.id)}
                          className="flex w-full flex-wrap items-baseline justify-between gap-2 text-left">
                    <span>
                      <span className="font-medium text-slate-900">{w.name}</span>{" "}
                      <span className="font-mono text-xs text-slate-400">{w.id}</span>
                    </span>
                    <span className="text-xs text-slate-500">
                      {w.packages.length} package{w.packages.length === 1 ? "" : "s"}
                      {upgrades > 0 && <span className="ml-2 text-amber-700">{upgrades} upgrade{upgrades === 1 ? "" : "s"}</span>}
                      <span className="ml-2" aria-hidden>{isOpen ? "▾" : "▸"}</span>
                    </span>
                  </button>
                  {isOpen && (
                    <div className="mt-3 pb-2">
                      <PackageManager workspaceId={w.id} compact />
                      <Link to={`/workspaces/${encodeURIComponent(w.id)}/packages`}
                            className="mt-2 inline-block text-xs text-sky-800 underline">
                        Its packages page, with checksums and history
                      </Link>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </div>
  );
}
