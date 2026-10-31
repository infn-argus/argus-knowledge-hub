import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, packagesApi, type PackageChange, type PackagePlan } from "../../api/client";
import { contentsLine } from "../../components/PackagePicker";

function problem(e: unknown): string {
  if (e instanceof ApiError) {
    const d = (e.body as { detail?: unknown })?.detail;
    if (d && typeof d === "object" && "error" in d) return String((d as { error: string }).error);
    if (typeof d === "string") return d;
  }
  return "It could not be done.";
}

interface CatalogueBehindDetail {
  code: "catalogue_behind";
  catalogue_workspace_id: string;
  needs: { package_id: string; version: string; has: string | null; shared_types: number }[];
}

function catalogueBehind(e: unknown): CatalogueBehindDetail | null {
  if (!(e instanceof ApiError)) return null;
  const d = (e.body as { detail?: { code?: string } })?.detail;
  return d && d.code === "catalogue_behind" ? (d as CatalogueBehindDetail) : null;
}

/** This workspace hangs from a shared catalogue that lacks what it would stand on: what the catalogue needs,
 * and a way there. The catalogue goes first, then this workspace. */
function CatalogueFirst({ d }: { d: CatalogueBehindDetail }) {
  return (
    <div role="alert" className="mt-2 rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">
      <p>
        This workspace takes its shared types from the catalogue <b>{d.catalogue_workspace_id}</b>, which must have
        these packages first:
      </p>
      <ul className="mt-1 list-disc pl-5">
        {d.needs.map((n) => (
          <li key={n.package_id}>
            <span className="font-mono">{n.package_id} {n.version}</span>{" "}
            {n.has ? <>— it has {n.has}</> : <>— not installed there</>}
            <span className="text-amber-800"> · {n.shared_types} shared type{n.shared_types === 1 ? "" : "s"}</span>
          </li>
        ))}
      </ul>
      <p className="mt-2">
        <Link to={`/workspaces/${encodeURIComponent(d.catalogue_workspace_id)}/packages`} className="font-medium text-sky-800 underline">
          Open {d.catalogue_workspace_id}'s packages
        </Link>{" "}
        to preview and apply its upgrade, then come back here.
      </p>
    </div>
  );
}

function how(options: Record<string, string> | null): string {
  if (!options?.scope) return "";
  if (options.scope === "global") return "as the catalogue other workspaces hang from";
  if (options.scope === "beamline") return `hanging from ${options.catalogue_workspace_id}`;
  return "self-contained";
}

const ACTIONS: Record<string, string> = {
  install: "installed", upgrade: "upgraded", revert: "reverted", seeded: "seeded by an import",
  detected: "found in place", unchanged: "unchanged",
};

/** What is being worked out: adding a package, upgrading one, or going back to an earlier version. */
type Pending =
  | { kind: "install"; packageId: string; name: string; version: string }
  | { kind: "upgrade"; packageId: string; name: string; from: string; version: string }
  | { kind: "revert"; packageId: string; name: string; from: string; version: string; checksum: string };

const VERB: Record<Pending["kind"], string> = { install: "Install", upgrade: "Upgrade", revert: "Go back" };

/** Which template packages this workspace uses — exact versions and checksums, how each was put in, the
 *  history — with upgrading, going back to an earlier version, and adding one, each previewed before
 *  anything changes. */
export function WorkspacePackages() {
  const { workspaceId = "" } = useParams();
  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Packages</h1>
        <p className="mt-1 text-sm text-slate-500">
          The template packages this workspace's types come from, at their exact versions. A package holds
          definitions only — types, fields, enumerations, workflows — never records.
        </p>
      </div>
      <PackageManager workspaceId={workspaceId} />
    </div>
  );
}

/** One workspace's packages, with their upgrades, reverts and additions: on the workspace's own page, and for
 *  each workspace in Administration → Packages. */
export function PackageManager({ workspaceId, compact = false }: { workspaceId: string; compact?: boolean }) {
  const queryClient = useQueryClient();
  const mine = useQuery({ queryKey: ["workspace-packages", workspaceId],
                          queryFn: () => packagesApi.ofWorkspace(workspaceId) });
  const all = useQuery({ queryKey: ["packages"], queryFn: packagesApi.list });
  const [pending, setPending] = useState<Pending | null>(null);
  const [plan, setPlan] = useState<PackagePlan | null>(null);
  const [decisions, setDecisions] = useState<Record<string, "apply" | "keep">>({});

  const work = (p: Pending, d: Record<string, "apply" | "keep">) => p.kind === "revert"
    ? { revert: { package_id: p.packageId, checksum: p.checksum, decisions: d } }
    : { install: { packages: [p.packageId], decisions: d } };
  const preview = useMutation({
    mutationFn: ({ p, d }: { p: Pending; d: Record<string, "apply" | "keep"> }) => {
      const w = work(p, d);
      return w.revert ? packagesApi.previewRevert(workspaceId, w.revert) : packagesApi.preview(workspaceId, w.install!);
    },
    onSuccess: setPlan,
  });
  const apply = useMutation({
    mutationFn: (p: Pending) => {
      const w = work(p, decisions);
      return w.revert ? packagesApi.revert(workspaceId, w.revert) : packagesApi.install(workspaceId, w.install!);
    },
    onSuccess: () => {
      close();
      queryClient.invalidateQueries({ queryKey: ["workspace-packages", workspaceId] });
      queryClient.invalidateQueries({ queryKey: ["admin-packages"] });
      queryClient.invalidateQueries({ queryKey: ["schemas"] });
    },
  });
  function start(p: Pending) {
    setPending(p);
    setPlan(null);
    setDecisions({});
    preview.reset();
    apply.reset();
    preview.mutate({ p, d: {} });
  }
  function close() {
    setPending(null);
    setPlan(null);
    setDecisions({});
  }

  const rows = mine.data?.packages ?? [];
  const have = new Set(rows.map((p) => p.package_id));
  const addable = (all.data ?? []).filter((p) => p.installable && !have.has(p.id));
  const undecided = (plan?.steps ?? []).some((s) => (s.action === "upgrade" || s.action === "revert") &&
    ((s.result.needs_decision as string[]) ?? []).some((id) => !decisions[id]));

  return (
    <div className="space-y-6">
      <div className="overflow-x-auto rounded border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr><th className="px-4 py-2">Package</th><th className="px-4 py-2">Version</th>
              {!compact && <><th className="px-4 py-2">Checksum</th><th className="px-4 py-2">How</th>
                <th className="px-4 py-2">Since</th></>}
              <th className="px-4 py-2 text-right"><span className="sr-only">Actions</span></th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.length === 0 && (
              <tr><td colSpan={compact ? 3 : 6} className="px-4 py-3 text-slate-500">None recorded.</td></tr>
            )}
            {rows.map((p) => (
              <tr key={p.package_id} className={pending?.packageId === p.package_id ? "bg-sky-50" : undefined}>
                <td className="px-4 py-2"><span className="font-medium text-slate-900">{p.name}</span>
                  <span className="block font-mono text-xs text-slate-400">{p.package_id}</span></td>
                <td className="px-4 py-2 font-mono whitespace-nowrap">
                  {p.version}
                  {p.upgrade_available && <span className="block text-xs text-amber-700">{p.shipped_version} available</span>}
                </td>
                {!compact && <>
                  <td className="px-4 py-2 font-mono text-xs text-slate-500" title={p.checksum}>{p.checksum.slice(0, 12)}</td>
                  <td className="px-4 py-2 text-slate-600">{how(p.options)}</td>
                  <td className="px-4 py-2 text-slate-500">{p.installed_at ? new Date(p.installed_at).toLocaleDateString() : ""}</td>
                </>}
                <td className="px-4 py-2">
                  <div className="flex flex-wrap items-center justify-end gap-2">
                    {p.upgrade_available && p.shipped_version && (
                      <button type="button" disabled={preview.isPending || apply.isPending}
                              onClick={() => start({ kind: "upgrade", packageId: p.package_id, name: p.name,
                                                     from: p.version, version: p.shipped_version! })}
                              className="whitespace-nowrap rounded bg-amber-600 px-3 py-1 text-xs font-medium text-white hover:bg-amber-700 disabled:opacity-50">
                        Upgrade to {p.shipped_version}
                      </button>
                    )}
                    {(p.revert_to ?? []).length > 0 && (
                      <select aria-label={`Go back: ${p.name}`} value=""
                              disabled={preview.isPending || apply.isPending}
                              onChange={(e) => {
                                const t = p.revert_to!.find((x) => x.checksum === e.target.value);
                                if (t) start({ kind: "revert", packageId: p.package_id, name: p.name, from: p.version,
                                               version: t.version, checksum: t.checksum });
                              }}
                              className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-700">
                        <option value="">Go back to…</option>
                        {p.revert_to!.map((t) => <option key={t.checksum} value={t.checksum}>{t.version}</option>)}
                      </select>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {pending && (
        <section aria-label="Preview" className="rounded border border-sky-200 bg-white p-4">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <h2 className="text-sm font-semibold text-slate-900">
              {pending.kind === "install" && <>Install {pending.name} {pending.version}</>}
              {pending.kind === "upgrade" && <>Upgrade {pending.name} from {pending.from} to {pending.version}</>}
              {pending.kind === "revert" && <>Go back: {pending.name} from {pending.from} to {pending.version}</>}
            </h2>
            <button type="button" onClick={close} className="text-xs text-slate-500 hover:underline">Cancel</button>
          </div>
          {pending.kind === "revert" && (
            <p className="mt-1 text-xs text-slate-500">
              What {pending.version} did not have is removed only where you choose apply; the values records hold
              under a removed field are kept. A field {pending.from} renamed is renamed back, its values with it.
            </p>
          )}
          {preview.isPending && <p className="mt-2 text-sm text-slate-500">Working it out…</p>}
          {preview.isError && (catalogueBehind(preview.error)
            ? <CatalogueFirst d={catalogueBehind(preview.error)!} />
            : <p className="mt-2 text-sm text-red-600">{problem(preview.error)}</p>)}
          {plan && (
            <div className="mt-3 space-y-2 text-sm">
              {plan.steps.map((s) => {
                const created = (s.result?.created as string[] | undefined) ?? [];
                const extended = (s.result?.extended as string[] | undefined) ?? [];
                const changes = (s.result?.changes as PackageChange[] | undefined) ?? [];
                return (
                  <p key={s.package_id}>
                    <span className="font-mono">{s.package_id} {s.version}</span>: {ACTIONS[s.action] ?? s.action}
                    {s.action === "install" ? "" : s.from_version ? ` from ${s.from_version}` : ""}
                    {created.length > 0 && ` — creates ${created.length} types`}
                    {extended.length > 0 && `, extends ${extended.length}`}
                    {(s.action === "upgrade" || s.action === "revert") && ` — ${changes.length} change${changes.length === 1 ? "" : "s"}`}
                    {s.action === "install" && created.length === 0 && extended.length === 0 && " — nothing new"}
                  </p>
                );
              })}
              {plan.steps.filter((s) => s.action === "upgrade" || s.action === "revert").map((s) => (
                <Upgrade key={s.package_id} changes={(s.result.changes as PackageChange[]) ?? []}
                         decisions={decisions} onDecide={(id, v) => setDecisions({ ...decisions, [id]: v })} />
              ))}
              {plan.options?.scope && <p className="text-xs text-slate-500">The object catalogue goes in {how(plan.options)}.</p>}
              <div className="flex flex-wrap items-center gap-2">
                <button type="button" disabled={!plan.changes || apply.isPending || undecided}
                        onClick={() => apply.mutate(pending)}
                        className="rounded bg-slate-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50">
                  {apply.isPending ? "Working…" : plan.changes ? VERB[pending.kind] : "Nothing to do"}
                </button>
                {undecided && <span className="text-xs text-amber-800">Decide each change that needs a decision first.</span>}
                {Object.keys(decisions).length > 0 && (
                  <button type="button" onClick={() => preview.mutate({ p: pending, d: decisions })} disabled={preview.isPending}
                          className="text-xs text-sky-800 underline">Check again with these decisions</button>
                )}
              </div>
              {apply.isError && (catalogueBehind(apply.error)
                ? <CatalogueFirst d={catalogueBehind(apply.error)!} />
                : <p className="text-sm text-red-600">{problem(apply.error)}</p>)}
            </div>
          )}
        </section>
      )}

      {addable.length > 0 && (
        <section aria-label="Add a package" className="rounded border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-900">Add a package</h2>
          <p className="mt-0.5 text-xs text-slate-500">What it depends on comes with it. Nothing changes until you install after the preview.</p>
          <ul className="mt-3 grid gap-3 sm:grid-cols-2">
            {addable.map((p) => (
              <li key={p.id} className="flex min-w-0 flex-col rounded border border-slate-200 p-3">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="font-medium text-slate-900">{p.name}</span>
                  <span className="shrink-0 font-mono text-xs text-slate-500">{p.version}</span>
                </div>
                <span className="font-mono text-xs text-slate-400">{p.id}</span>
                {p.description && <p className="mt-1 line-clamp-3 text-xs text-slate-600" title={p.description}>{p.description}</p>}
                <p className="mt-1 text-xs text-slate-500">{contentsLine(p)}</p>
                {Object.keys(p.depends ?? {}).length > 0 && (
                  <p className="mt-0.5 text-xs text-slate-400">Needs {Object.keys(p.depends).join(", ")}</p>
                )}
                <div className="mt-auto pt-2">
                  <button type="button" disabled={preview.isPending || apply.isPending}
                          onClick={() => start({ kind: "install", packageId: p.id, name: p.name, version: p.version })}
                          className="rounded border border-slate-300 px-3 py-1 text-xs hover:bg-slate-50 disabled:opacity-50">
                    Preview
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {!compact && (
        <div>
          <h2 className="mb-2 text-sm font-semibold text-slate-900">History</h2>
          <ul className="space-y-1 text-sm text-slate-600">
            {(mine.data?.history ?? []).slice().reverse().map((h, i) => (
              <li key={i}>
                <span className="text-slate-400">{h.at ? new Date(h.at).toLocaleString() : ""}</span>{" "}
                <span className="font-mono">{h.package_id}</span> {h.from_version ? `${h.from_version} → ` : ""}
                <span className="font-mono">{h.to_version}</span> — {ACTIONS[h.action] ?? h.action}
                {h.actor ? ` by ${h.actor}` : ""}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}


const CATEGORY: Record<string, string> = {
  additive: "Added — applied by itself",
  definition: "Changed wording — applied where this workspace did not change it",
  breaking: "Needs a decision",
};

/** An upgrade's changes, grouped; each breaking one with its records and the choice to apply or keep it. */
function Upgrade({ changes, decisions, onDecide }: {
  changes: PackageChange[];
  decisions: Record<string, "apply" | "keep">;
  onDecide: (id: string, v: "apply" | "keep") => void;
}) {
  return (
    <div className="space-y-3 rounded border border-slate-200 p-3">
      {(["breaking", "additive", "definition"] as const).map((cat) => {
        const list = changes.filter((c) => c.category === cat);
        if (!list.length) return null;
        return (
          <div key={cat}>
            <h3 className="text-xs font-semibold uppercase text-slate-500">{CATEGORY[cat]} ({list.length})</h3>
            <ul className="mt-1 space-y-1">
              {list.map((c) => (
                <li key={c.id} className="text-sm">
                  <span className="text-slate-500">{c.subject}:</span> {c.detail}
                  {c.records > 0 && <span className="text-xs text-slate-500"> · {c.records} record(s)</span>}
                  {c.violations > 0 && (
                    <span className="text-xs text-red-700"> · {c.violations} would not be accepted: change them first, or keep</span>
                  )}
                  {c.conflict && <span className="text-xs text-amber-700"> · {c.conflict}</span>}
                  {cat === "breaking" && (
                    <span className="ml-2 inline-flex gap-2 text-xs">
                      {c.actions.map((a) => (
                        <label key={a} className="flex items-center gap-1">
                          <input type="radio" name={c.id} checked={decisions[c.id] === a} onChange={() => onDecide(c.id, a)} />
                          {a === "apply" ? "apply" : "keep this workspace's"}
                        </label>
                      ))}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
