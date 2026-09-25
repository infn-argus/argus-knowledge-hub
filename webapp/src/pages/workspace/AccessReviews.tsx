/** Role templates per domain and signed access reviews (§19 item 1): a
 * snapshot of every grant, what changed since the last review, and the
 * signatures of its owners. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { accessReviewsApi, ApiError } from "../../api/client";
import type { AccessReviewView } from "../../api/ledgerTypes";
import { useCurrentWorkspaceId } from "../../api/useCurrentWorkspaceId";
import { errorText } from "../../components/hub/LedgerPanels";

const perms = (p: Record<string, string[]>) =>
  Object.entries(p)
    .map(([k, v]) => `${k}: ${v.join(", ")}`)
    .join(" · ");

export function AccessReviews() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const current = useCurrentWorkspaceId();
  const queryClient = useQueryClient();
  const [openId, setOpenId] = useState<string | null>(null);
  const [signers, setSigners] = useState(2);
  const templates = useQuery({ queryKey: ["role-templates"], queryFn: accessReviewsApi.templates });
  const reviews = useQuery({ queryKey: ["access-reviews", current], queryFn: accessReviewsApi.list, retry: false });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["access-reviews"] });
  const install = useMutation({ mutationFn: accessReviewsApi.installTemplates,
                                onSuccess: () => queryClient.invalidateQueries({ queryKey: ["roles"] }) });
  const create = useMutation({ mutationFn: () => accessReviewsApi.create(signers),
                               onSuccess: (r) => { refresh(); setOpenId(r.id); } });

  if (workspaceId && current && workspaceId !== current) {
    return (
      <p className="text-sm text-slate-600">
        Access reviews cover the workspace you are working in ({current}). Switch to {workspaceId} to review it.
      </p>
    );
  }
  if (reviews.isError) {
    const forbidden = reviews.error instanceof ApiError && reviews.error.status === 403;
    return <p className="text-sm text-red-600">{forbidden ? "Reviewing access needs approval rights." : errorText(reviews.error)}</p>;
  }
  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Access reviews</h1>
        <p className="mt-1 text-sm text-slate-500">
          A review records every grant in this workspace: people (directly and through groups), groups, API tokens,
          open defaults and administrators, and what changed since the last one. It is complete once enough distinct
          owners have signed it; if access moves before then, take a new one.{" "}
          <Link to={`/workspaces/${current}/access`} className="text-indigo-600 hover:underline">
            Manage access
          </Link>
        </p>
      </div>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-900">Roles per domain</h2>
          <button onClick={() => install.mutate()} className="rounded border border-slate-300 px-3 py-1 text-xs hover:bg-slate-50">
            Install missing roles
          </button>
        </div>
        {install.data && (
          <p className="mt-1 text-xs text-slate-500">
            {install.data.added.length ? `Added ${install.data.added.join(", ")}.` : "All roles were already there."}
          </p>
        )}
        {install.isError && <p className="mt-1 text-xs text-red-600">{errorText(install.error)}</p>}
        <ul className="mt-2 divide-y divide-slate-100 text-sm">
          {(templates.data ?? []).map((t) => (
            <li key={t.id} className="py-1.5">
              <span className="font-medium text-slate-800">{t.name}</span>{" "}
              <span className="text-slate-500">— {t.description}</span>
              <span className="block text-xs text-slate-400">{perms(t.permissions)}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-slate-900">Reviews</h2>
          <span className="flex items-center gap-2 text-xs text-slate-600">
            Signers needed
            <input type="number" min={1} max={9} value={signers} onChange={(e) => setSigners(Number(e.target.value) || 1)}
                   className="w-14 rounded border border-slate-300 px-2 py-0.5" />
            <button onClick={() => create.mutate()} disabled={create.isPending}
                    className="rounded bg-slate-900 px-3 py-1 font-medium text-white disabled:opacity-40">
              Take a review
            </button>
          </span>
        </div>
        {create.isError && <p className="mt-1 text-xs text-red-600">{errorText(create.error)}</p>}
        <table className="mt-2 w-full text-sm">
          <thead className="text-left text-xs text-slate-400">
            <tr>
              <th className="py-1 font-normal">Taken</th>
              <th className="font-normal">By</th>
              <th className="font-normal">Scope</th>
              <th className="font-normal">Changes</th>
              <th className="font-normal">Signed</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {(reviews.data ?? []).map((r) => (
              <tr key={r.id} onClick={() => setOpenId(openId === r.id ? null : r.id)} className="cursor-pointer hover:bg-slate-50">
                <td className="py-1.5">{new Date(r.created_at).toLocaleString()}</td>
                <td>{r.created_by}</td>
                <td className="text-xs text-slate-500">
                  {r.summary.people} people · {r.summary.groups} groups · {r.summary.tokens} tokens
                </td>
                <td className="text-xs text-slate-500">
                  +{r.changes.added.length} −{r.changes.removed.length} ~{r.changes.changed.length}
                </td>
                <td>
                  {r.completed_at ? (
                    <span className="rounded bg-emerald-50 px-2 py-0.5 text-xs text-emerald-700">complete</span>
                  ) : (
                    <span className="text-xs text-slate-500">{r.signatures.length} of {r.required_signers}</span>
                  )}
                </td>
              </tr>
            ))}
            {reviews.data?.length === 0 && (
              <tr>
                <td colSpan={5} className="py-3 text-sm text-slate-500">No review yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </section>

      {openId && <ReviewDetail id={openId} onSigned={refresh} />}
    </div>
  );
}

function ReviewDetail({ id, onSigned }: { id: string; onSigned: () => void }) {
  const queryClient = useQueryClient();
  const review = useQuery({ queryKey: ["access-review", id], queryFn: () => accessReviewsApi.get(id) });
  const [signer, setSigner] = useState("");
  const [comment, setComment] = useState("");
  const sign = useMutation({
    mutationFn: () => accessReviewsApi.sign(id, { signer: signer || undefined, comment: comment || undefined }),
    onSuccess: (r: AccessReviewView) => {
      queryClient.setQueryData(["access-review", id], r);
      setComment("");
      onSigned();
    },
  });
  const r = review.data;
  if (!r?.snapshot) return null;
  const s = r.snapshot;
  const changes = [
    ...r.changes.added.map((k) => ["added", k]),
    ...r.changes.removed.map((k) => ["removed", k]),
    ...r.changes.changed.map((k) => ["changed", k]),
  ];
  return (
    <section className="space-y-4 rounded-lg border border-slate-200 bg-white p-4 text-sm">
      <div className="flex items-baseline justify-between">
        <h2 className="text-sm font-semibold text-slate-900">Review of {new Date(r.created_at).toLocaleString()}</h2>
        <span className="font-mono text-[11px] text-slate-400" title="SHA-256 of the snapshot">
          {r.snapshot_hash.slice(0, 16)}…
        </span>
      </div>

      <div>
        <h3 className="text-xs font-medium uppercase tracking-wide text-slate-400">Since the previous review</h3>
        {changes.length === 0 ? (
          <p className="text-slate-500">No change.</p>
        ) : (
          <ul className="mt-1 space-y-0.5">
            {changes.map(([kind, key]) => (
              <li key={`${kind}-${key}`}>
                <span className={kind === "added" ? "text-emerald-700" : kind === "removed" ? "text-red-600" : "text-amber-700"}>
                  {kind}
                </span>{" "}
                <span className="font-mono text-xs">{key}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <h3 className="text-xs font-medium uppercase tracking-wide text-slate-400">People</h3>
        <table className="mt-1 w-full">
          <tbody className="divide-y divide-slate-100">
            {s.people.map((p) => (
              <tr key={p.user}>
                <td className="py-1 pr-3">{p.name ?? p.user}<span className="block text-xs text-slate-400">{p.email}</span></td>
                <td className="pr-3 text-xs text-slate-600">{p.roles.join(", ") || "—"}</td>
                <td className="text-xs text-slate-500">{perms(p.permissions)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <h3 className="text-xs font-medium uppercase tracking-wide text-slate-400">API tokens</h3>
          <ul className="mt-1 space-y-0.5 text-xs">
            {s.tokens.filter((t) => !t.revoked).map((t) => (
              <li key={t.token}>
                {t.label ?? `token ${t.token}`}
                {t.restricted_grants.length > 0 && <span className="text-amber-700"> · sees {t.restricted_grants.join(", ")}</span>}
                <span className="text-slate-400"> · last used {t.last_used_at ? new Date(t.last_used_at).toLocaleDateString() : "never"}</span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="text-xs font-medium uppercase tracking-wide text-slate-400">Open to everyone / administrators</h3>
          <p className="mt-1 text-xs text-slate-600">{s.open_defaults.join(", ") || "Nothing is open by default."}</p>
          <p className="mt-1 text-xs text-slate-600">{s.administrators.join(", ") || "No administrator."}</p>
        </div>
      </div>

      <div>
        <h3 className="text-xs font-medium uppercase tracking-wide text-slate-400">
          Signatures ({r.signatures.length} of {r.required_signers})
        </h3>
        <ul className="mt-1 space-y-0.5 text-xs">
          {r.signatures.map((g) => (
            <li key={g.signer}>
              {g.signer} · {new Date(g.at).toLocaleString()}
              {g.comment ? ` — ${g.comment}` : ""}
            </li>
          ))}
        </ul>
        {!r.completed_at && (
          <div className="mt-2 flex flex-wrap gap-2 text-xs">
            <input value={signer} onChange={(e) => setSigner(e.target.value)} placeholder="Signer (API token sessions only)"
                   className="rounded border border-slate-300 px-2 py-1" />
            <input value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Comment"
                   className="flex-1 rounded border border-slate-300 px-2 py-1" />
            <button onClick={() => sign.mutate()} className="rounded bg-slate-900 px-3 py-1 font-medium text-white">
              Sign
            </button>
          </div>
        )}
        {sign.isError && <p className="mt-1 text-xs text-red-600">{errorText(sign.error)}</p>}
      </div>
    </section>
  );
}
