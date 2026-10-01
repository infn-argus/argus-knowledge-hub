import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { catalogueMappingApi } from "../../api/client";
import type { CatalogueMapping, MappingField, MappingItem, MappingStatus } from "../../api/types";
import { RecordMappingReview } from "./RecordMappingReview";

const FILTERS: [string, string][] = [
  ["proposed", "To review"],
  ["accepted", "Accepted"],
  ["skipped", "Skipped"],
  ["applied", "Applied"],
  ["all", "All"],
];

const ACTION_LABEL = { create_model: "New model", merge: "Merge", create_vendor: "New vendor" } as const;

/** "avatar · 3 files · 5 history · 1 ticket": what comes along with the row. */
function carryText(c?: MappingItem["source"]["carry"] | Record<string, number | boolean>): string {
  if (!c) return "";
  const n = (k: string) => Number(c[k as keyof typeof c] ?? 0);
  const parts = [
    c.avatar ? "avatar" : "",
    n("attachments") ? `${n("attachments")} file${n("attachments") > 1 ? "s" : ""}` : "",
    n("history") ? `${n("history")} history` : "",
    n("comments") ? `${n("comments")} comment${n("comments") > 1 ? "s" : ""}` : "",
    n("tickets") ? `${n("tickets")} ticket${n("tickets") > 1 ? "s" : ""}` : "",
  ];
  return parts.filter(Boolean).join(" · ");
}

const SOURCE_STYLE: Record<string, string> = {
  rule: "bg-slate-100 text-slate-600",
  ai: "bg-violet-50 text-violet-700",
  person: "bg-emerald-50 text-emerald-700",
};

function Confidence({ value }: { value: number | null }) {
  if (value === null) return null;
  const pct = Math.round(value * 100);
  const color = value >= 0.8 ? "bg-emerald-500" : value >= 0.6 ? "bg-amber-400" : "bg-red-400";
  return (
    <span className="inline-flex items-center gap-1.5 text-xs tabular-nums text-slate-600" title="The row's weakest part">
      <span className={`h-2 w-2 rounded-full ${color}`} />
      {pct}%
    </span>
  );
}

function Source({ field }: { field?: MappingField }) {
  if (!field) return null;
  return (
    <span
      className={`ml-1 rounded px-1 py-0.5 text-[10px] font-medium ${SOURCE_STYLE[field.source]}`}
      title={field.evidence ? `From: “${field.evidence}”` : undefined}
    >
      {field.source}
    </span>
  );
}

function Editor({
  mapping,
  item,
  onDone,
}: {
  mapping: CatalogueMapping;
  item: MappingItem;
  onDone: () => void;
}) {
  const queryClient = useQueryClient();
  const p = item.proposal;
  const [action, setAction] = useState(p.action);
  const [values, setValues] = useState<Record<string, string>>({
    name: p.fields.name?.value ?? "",
    model_code: p.fields.model_code?.value ?? "",
    device_class: p.fields.device_class?.value ?? "",
    datasheet_url: p.fields.datasheet_url?.value ?? "",
    description: p.fields.description?.value ?? "",
  });
  const [vendor, setVendor] = useState(p.vendor?.name ?? "");
  const save = useMutation({
    mutationFn: () =>
      catalogueMappingApi.decide(mapping.id, item.id, {
        action,
        fields: values,
        ...(action === "create_model" ? { vendor } : {}),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["catalogue-mapping", mapping.id] });
      onDone();
    },
  });
  const input = (key: string, label: string, wide = false) => (
    <label className={`text-xs ${wide ? "sm:col-span-2" : ""}`}>
      <span className="block font-medium text-slate-500">{label}</span>
      {key === "description" ? (
        <textarea
          value={values[key]}
          onChange={(e) => setValues((v) => ({ ...v, [key]: e.target.value }))}
          rows={3}
          className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1 text-sm"
        />
      ) : (
        <input
          value={values[key]}
          onChange={(e) => setValues((v) => ({ ...v, [key]: e.target.value }))}
          className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1 text-sm"
        />
      )}
    </label>
  );

  return (
    <div className="space-y-3 bg-slate-50 px-3 py-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1 text-xs text-slate-600">
          <p className="font-medium text-slate-500">What the import says</p>
          <p>
            <span className="text-slate-400">Name:</span> {item.source_name}
          </p>
          {item.source.producer && (
            <p>
              <span className="text-slate-400">Producer:</span> {String(item.source.producer)}
            </p>
          )}
          {item.source.reseller && (
            <p>
              <span className="text-slate-400">Sold by:</span> {String(item.source.reseller)}
            </p>
          )}
          {item.source.product_code ? (
            <p>
              <span className="text-slate-400">Product code:</span> {String(item.source.product_code)}
            </p>
          ) : null}
          {item.source.description && (
            <p className="max-h-24 overflow-y-auto whitespace-pre-wrap text-slate-500">{item.source.description}</p>
          )}
        </div>
        <div className="space-y-1 text-xs">
          <p className="font-medium text-slate-500">Why</p>
          {p.warnings.length === 0 && <p className="text-slate-400">Nothing to flag.</p>}
          {p.warnings.map((w) => (
            <p key={w} className="text-amber-700">
              {w}
            </p>
          ))}
          {p.merge_into && (
            <p className="text-slate-600">
              Same product as{" "}
              <Link to={`/assets/${p.merge_into.uid}`} className="text-indigo-600 hover:underline">
                {p.merge_into.name}
              </Link>{" "}
              already in the catalogue: its old key is added there as an alias.
            </p>
          )}
          {p.duplicate_of && <p className="text-slate-600">Same product as another row of this mapping.</p>}
        </div>
      </div>
      <div className="flex items-center gap-2 text-xs">
        <span className="font-medium text-slate-500">Becomes</span>
        <select
          value={action}
          onChange={(e) => setAction(e.target.value as typeof action)}
          className="rounded border border-slate-300 px-2 py-1 text-sm"
        >
          <option value="create_model">a new Product Model</option>
          <option value="create_vendor">a new Vendor (it is a company)</option>
          {(p.merge_into || p.duplicate_of) && <option value="merge">merged into the same product</option>}
        </select>
      </div>
      {action !== "merge" && (
        <div className="grid gap-3 sm:grid-cols-2">
          {input("name", action === "create_vendor" ? "Vendor name" : "Model name")}
          {action === "create_model" && (
            <>
              <label className="text-xs">
                <span className="block font-medium text-slate-500">Vendor (manufacturer)</span>
                <input
                  value={vendor}
                  onChange={(e) => setVendor(e.target.value)}
                  className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1 text-sm"
                />
              </label>
              {input("model_code", "Model code")}
              {input("device_class", "Device class")}
              {input("datasheet_url", "Datasheet", true)}
              {input("description", "Description", true)}
            </>
          )}
        </div>
      )}
      <div className="flex items-center gap-3">
        <button
          onClick={() => save.mutate()}
          disabled={save.isPending}
          className="rounded bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {save.isPending ? "Saving…" : "Save and accept"}
        </button>
        <button onClick={onDone} className="text-xs text-slate-500 hover:text-slate-900">
          Close
        </button>
        {save.isError && <span className="text-xs text-red-600">{(save.error as Error).message}</span>}
      </div>
    </div>
  );
}

export function CatalogueMappingReview() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState("proposed");
  const [open, setOpen] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const mapping = useQuery({
    queryKey: ["catalogue-mapping", id],
    queryFn: () => catalogueMappingApi.get(id!),
    enabled: !!id,
    refetchInterval: (q) => (q.state.data?.state === "analysing" ? 2000 : false),
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["catalogue-mapping", id] });

  const decide = useMutation({
    mutationFn: (v: { itemId: string; status: MappingStatus }) =>
      catalogueMappingApi.decide(id!, v.itemId, { status: v.status }),
    onSuccess: refresh,
    onError: (e) => setNotice((e as Error).message),
  });
  const acceptConfident = useMutation({
    mutationFn: () => catalogueMappingApi.decideMany(id!, { min_confidence: 0.8 }),
    onSuccess: (r) => {
      setNotice(`${r.changed} rows accepted.`);
      refresh();
    },
  });
  const apply = useMutation({
    mutationFn: () => catalogueMappingApi.apply(id!),
    onSuccess: (r) => {
      const carried = carryText({
        avatar: r.carried.avatar ?? 0,
        attachments: r.carried.attachments ?? 0,
        comments: r.carried.comments ?? 0,
        // One "mapped" entry per row is the mapping's own; the rest is the imported history.
        history: Math.max(0, (r.carried.history ?? 0) - r.applied),
        tickets: (r.carried.asset_tickets ?? 0) + (r.carried.ticket_links ?? 0),
      });
      setNotice(
        `${r.applied} rows applied.` +
          (carried ? ` Carried over: ${carried}.` : "") +
          (r.failed.length ? ` Not applied: ${r.failed.map((f) => `${f.source_key} (${f.error})`).join("; ")}` : ""),
      );
      refresh();
    },
    onError: (e) => setNotice((e as Error).message),
  });
  const bringAlong = useMutation({
    mutationFn: () => catalogueMappingApi.carry(id!),
    onSuccess: (r) => {
      const carried = carryText({
        avatar: r.carried.avatar ?? 0,
        attachments: r.carried.attachments ?? 0,
        comments: r.carried.comments ?? 0,
        history: Math.max(0, (r.carried.history ?? 0) - r.rows),
        tickets: (r.carried.asset_tickets ?? 0) + (r.carried.ticket_links ?? 0),
      });
      setNotice(
        `${r.rows} applied rows updated.` +
          (carried ? ` Carried over: ${carried}.` : "") +
          (r.failed.length ? ` Not carried: ${r.failed.map((f) => `${f.source_key} (${f.error})`).join("; ")}` : ""),
      );
      refresh();
    },
    onError: (e) => setNotice((e as Error).message),
  });
  const share = useMutation({
    mutationFn: () => catalogueMappingApi.share(id!),
    onSuccess: (r) => {
      setNotice(`${r.shared} records are now shared with every workspace.`);
      refresh();
    },
    onError: (e) => setNotice((e as Error).message),
  });
  const undo = useMutation({
    mutationFn: () => catalogueMappingApi.undo(id!),
    onSuccess: (r) => {
      setNotice(`Undone: ${r.retired} records retired in the catalogue; the rows are accepted again.`);
      refresh();
    },
  });

  const m = mapping.data;
  if (mapping.isError) return <p className="text-sm text-red-600">{(mapping.error as Error).message}</p>;
  if (!m) return <p className="text-sm text-slate-500">Loading…</p>;

  const items = m.items ?? [];
  const shown = filter === "all" ? items : items.filter((i) => i.status === filter);
  const byId = new Map(items.map((i) => [i.id, i]));
  const accepted = m.counts.accepted ?? 0;
  const applied = m.counts.applied ?? 0;
  const pct = m.total ? Math.round((m.analysed / m.total) * 100) : 0;

  return (
    <div className="max-w-6xl">
      <p className="text-sm">
        <Link to="/migration/catalogue" className="text-indigo-600 hover:underline">
          Map imported records
        </Link>
      </p>
      <h1 className="mt-1 text-2xl font-semibold text-slate-900">
        <span className="font-mono text-lg">{m.source_workspace_id}</span> →{" "}
        <span className="font-mono text-lg">{m.target_workspace_id}</span>
      </h1>
      <p className="mt-1 text-sm text-slate-500">
        {m.total} records, started by {m.actor}.{" "}
        {m.ai.used ? (
          <>
            AI: <span className="font-mono">{m.ai.model}</span> (configured for {m.ai.workspace}).
          </>
        ) : m.use_ai ? (
          <span className="text-amber-700">{m.ai.reason}</span>
        ) : (
          "Rules only."
        )}
        {m.ai.error && <span className="text-amber-700"> {m.ai.error}</span>}
      </p>

      {m.state === "analysing" && (
        <div className="mt-6 max-w-md">
          <p className="text-sm text-slate-600">
            Proposing… {m.analysed} of {m.total}
          </p>
          <div className="mt-2 h-2 overflow-hidden rounded bg-slate-100">
            <div className="h-2 bg-indigo-500 transition-all" style={{ width: `${pct}%` }} />
          </div>
        </div>
      )}
      {m.state === "failed" && <p className="mt-4 text-sm text-red-600">The analysis failed: {m.error}</p>}

      {m.state === "ready" && m.kind === "records" && <RecordMappingReview mapping={m} />}
      {m.state === "ready" && m.kind !== "records" && (
        <>
          <div className="mt-5 flex flex-wrap items-center gap-2">
            {FILTERS.map(([key, label]) => {
              const n = key === "all" ? items.length : m.counts[key as MappingStatus] ?? 0;
              return (
                <button
                  key={key}
                  onClick={() => setFilter(key)}
                  className={`rounded-full px-3 py-1 text-xs ${
                    filter === key ? "bg-slate-900 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200"
                  }`}
                >
                  {label} <span className="tabular-nums opacity-70">{n}</span>
                </button>
              );
            })}
            <div className="ml-auto flex items-center gap-2">
              <button
                onClick={() => acceptConfident.mutate()}
                disabled={!m.counts.proposed || acceptConfident.isPending}
                className="rounded border border-slate-300 px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                Accept all ≥ 80%
              </button>
              <button
                onClick={() => apply.mutate()}
                disabled={!accepted || apply.isPending}
                className="rounded bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-800 disabled:opacity-50"
              >
                {apply.isPending ? "Applying…" : `Apply ${accepted} accepted`}
              </button>
              {applied > 0 && (
                <button
                  onClick={() => {
                    if (confirm(`Retire the ${applied} applied rows' records in ${m.target_workspace_id}?`)) undo.mutate();
                  }}
                  disabled={undo.isPending}
                  className="rounded px-2 py-1.5 text-xs text-red-600 hover:bg-red-50"
                >
                  Undo applied
                </button>
              )}
            </div>
          </div>
          {(m.unshared ?? 0) > 0 && (
            <div className="mt-3 flex flex-wrap items-center gap-3 rounded border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-900">
              <span>
                {m.unshared} Product Models and Vendors from this mapping are visible only in {m.target_workspace_id}:
                other workspaces' equipment cannot point at them.
              </span>
              <button
                onClick={() => share.mutate()}
                disabled={share.isPending}
                className="ml-auto rounded bg-sky-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-sky-800 disabled:opacity-50"
              >
                {share.isPending ? "Sharing…" : "Share with every workspace"}
              </button>
            </div>
          )}
          {(m.pending_carry ?? 0) > 0 && (
            <div className="mt-3 flex flex-wrap items-center gap-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
              <span>
                {m.pending_carry} applied rows were created without their avatar, attachments, history, comments and
                ticket links.
              </span>
              <button
                onClick={() => bringAlong.mutate()}
                disabled={bringAlong.isPending}
                className="ml-auto rounded bg-amber-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-700 disabled:opacity-50"
              >
                {bringAlong.isPending ? "Copying…" : "Bring them along"}
              </button>
            </div>
          )}
          {notice && (
            <p className="mt-3 rounded bg-slate-100 px-3 py-2 text-sm text-slate-700">
              {notice}{" "}
              <button onClick={() => setNotice(null)} className="text-slate-400 hover:text-slate-700">
                ×
              </button>
            </p>
          )}

          <div className="mt-3 overflow-hidden rounded-lg border border-slate-200 bg-white">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-3 py-2">Imported</th>
                  <th className="px-3 py-2">Becomes</th>
                  <th className="px-3 py-2">Vendor</th>
                  <th className="px-3 py-2">Confidence</th>
                  <th className="px-3 py-2 text-right">Decision</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {shown.map((item) => {
                  const p = item.proposal;
                  const twin = p.duplicate_of ? byId.get(p.duplicate_of) : undefined;
                  return [
                    <tr key={item.id} className={item.status === "skipped" ? "opacity-60" : undefined}>
                      <td className="px-3 py-2 align-top">
                        <div className="text-slate-900">{item.source_name}</div>
                        <div className="text-xs text-slate-400">
                          <span className="font-mono">{item.source_key}</span> · {item.source_type}
                        </div>
                        {carryText(item.source.carry) && (
                          <div className="text-xs text-slate-500" title="Copied or linked onto the catalogue record when applied">
                            + {carryText(item.source.carry)}
                          </div>
                        )}
                      </td>
                      <td className="px-3 py-2 align-top">
                        <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-600">
                          {ACTION_LABEL[p.action]}
                        </span>{" "}
                        {p.action === "merge" ? (
                          <span className="text-slate-700">
                            into {p.merge_into?.name ?? twin?.proposal.fields.name?.value ?? "another row"}
                          </span>
                        ) : (
                          <>
                            <span className="text-slate-900">{p.fields.name?.value}</span>
                            <Source field={p.fields.name} />
                            {p.fields.model_code && (
                              <div className="text-xs text-slate-500">
                                code {p.fields.model_code.value}
                                <Source field={p.fields.model_code} />
                              </div>
                            )}
                            {p.fields.device_class && (
                              <div className="text-xs text-slate-500">
                                {p.fields.device_class.value}
                                <Source field={p.fields.device_class} />
                              </div>
                            )}
                          </>
                        )}
                        {p.warnings.length > 0 && (
                          <div className="mt-1 text-xs text-amber-700">⚠ {p.warnings[0]}</div>
                        )}
                      </td>
                      <td className="px-3 py-2 align-top text-sm">
                        {p.action === "create_model" && p.vendor ? (
                          <>
                            {p.vendor.name}{" "}
                            <span
                              className={`rounded px-1 py-0.5 text-[10px] font-medium ${
                                p.vendor.existing_uid ? "bg-emerald-50 text-emerald-700" : "bg-sky-50 text-sky-700"
                              }`}
                            >
                              {p.vendor.existing_uid ? "existing" : "new"}
                            </span>
                          </>
                        ) : p.action === "create_model" ? (
                          <span className="text-xs text-slate-400">none</span>
                        ) : null}
                      </td>
                      <td className="px-3 py-2 align-top">
                        <Confidence value={item.confidence} />
                      </td>
                      <td className="whitespace-nowrap px-3 py-2 text-right align-top text-xs">
                        {item.status === "applied" ? (
                          item.result_uid && (
                            <Link to={`/assets/${item.result_uid}`} className="text-emerald-700 hover:underline">
                              Applied ↗
                            </Link>
                          )
                        ) : (
                          <>
                            {item.status !== "accepted" && (
                              <button
                                onClick={() => decide.mutate({ itemId: item.id, status: "accepted" })}
                                className="mr-2 text-emerald-700 hover:underline"
                              >
                                Accept
                              </button>
                            )}
                            {item.status !== "skipped" && (
                              <button
                                onClick={() => decide.mutate({ itemId: item.id, status: "skipped" })}
                                className="mr-2 text-slate-500 hover:underline"
                              >
                                Skip
                              </button>
                            )}
                            {item.status !== "proposed" && (
                              <button
                                onClick={() => decide.mutate({ itemId: item.id, status: "proposed" })}
                                className="mr-2 text-slate-500 hover:underline"
                              >
                                Reopen
                              </button>
                            )}
                            <button
                              onClick={() => setOpen(open === item.id ? null : item.id)}
                              className="text-indigo-600 hover:underline"
                            >
                              {open === item.id ? "Close" : "Edit"}
                            </button>
                          </>
                        )}
                      </td>
                    </tr>,
                    open === item.id && (
                      <tr key={`${item.id}-edit`}>
                        <td colSpan={5} className="p-0">
                          <Editor mapping={m} item={item} onDone={() => setOpen(null)} />
                        </td>
                      </tr>
                    ),
                  ];
                })}
                {shown.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-3 py-6 text-center text-slate-400">
                      No rows here.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-slate-500">
            Applying creates the accepted rows in {m.target_workspace_id} through the ledger, each keeping its old key
            and its Insight link as aliases so they still resolve. Its avatar and attachments are copied, its history
            and comments keep their authors and dates, and its tickets stay where they are, linked to the new record.
            A merge adds all of that to the record it merges into. Rows you skip or leave to review stay open for a
            later mapping.
          </p>
        </>
      )}
    </div>
  );
}
