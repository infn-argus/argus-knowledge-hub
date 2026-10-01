import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, catalogueMappingApi } from "../../api/client";
import type {
  CatalogueMapping,
  MappingItem,
  MappingStatus,
  MappingVocabulary,
  PlanEntry,
  PlanField,
  RecordProposal,
} from "../../api/types";

const SOURCE_STYLE: Record<string, string> = {
  rule: "bg-slate-100 text-slate-600",
  ai: "bg-violet-50 text-violet-700",
  person: "bg-emerald-50 text-emerald-700",
};

function Badge({ source, confidence }: { source?: string; confidence?: number }) {
  if (!source) return null;
  return (
    <span
      className={`ml-1 rounded px-1 py-0.5 text-[10px] font-medium ${SOURCE_STYLE[source] ?? ""}`}
      title={confidence !== undefined ? `${Math.round(confidence * 100)}% sure` : undefined}
    >
      {source}
    </span>
  );
}

function Dot({ value }: { value: number | null | undefined }) {
  if (value === null || value === undefined) return null;
  const color = value >= 0.8 ? "bg-emerald-500" : value >= 0.6 ? "bg-amber-400" : "bg-red-400";
  return (
    <span className="inline-flex items-center gap-1.5 text-xs tabular-nums text-slate-600">
      <span className={`h-2 w-2 rounded-full ${color}`} />
      {Math.round(value * 100)}%
    </span>
  );
}

// What a field can be sent to, as one select value: "attr:<key>", "description", "drop" or "link".
function destination(f: PlanField): string {
  if (f.kind === "link") return "link";
  if (f.kind === "companion") return `comp:${f.companion}:${f.target}`;
  if (f.kind === "description" || f.kind === "drop") return f.kind;
  return `attr:${f.target}`;
}

/** Values every row of this type gets, whatever the import says. */
function AlwaysSet({
  mapping,
  typeUid,
  entry,
  vocabulary,
  onSaved,
}: {
  mapping: CatalogueMapping;
  typeUid: string;
  entry: PlanEntry;
  vocabulary: MappingVocabulary;
  onSaved: () => void;
}) {
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const attrs = (vocabulary.attributes[entry.target_type?.uid ?? ""] ?? []).filter(
    (a) => a.type !== "reference" && a.key !== "description",
  );
  const byKey = new Map(attrs.map((a) => [a.key, a]));
  const fixed = entry.fixed ?? {};
  const save = useMutation({
    mutationFn: (next: Record<string, string>) => catalogueMappingApi.setPlan(mapping.id, typeUid, { fixed: next }),
    onSuccess: () => {
      setKey("");
      setValue("");
      onSaved();
    },
  });
  const chosen = byKey.get(key);
  return (
    <div className="mb-3">
      <p className="text-xs font-medium uppercase text-slate-400">Always set</p>
      {Object.keys(fixed).length === 0 && <p className="mt-1 text-xs text-slate-400">Nothing: rows hold only what the import says.</p>}
      <div className="mt-1 flex flex-wrap gap-1">
        {Object.entries(fixed).map(([k, v]) => (
          <span key={k} className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-700">
            {byKey.get(k)?.name ?? k} = {v}
            <button
              onClick={() => {
                const next = { ...fixed };
                delete next[k];
                save.mutate(next);
              }}
              className="ml-1 text-slate-400 hover:text-red-600"
              title="Remove"
            >
              ×
            </button>
          </span>
        ))}
      </div>
      <div className="mt-1 flex items-center gap-1 text-xs">
        <select value={key} onChange={(e) => { setKey(e.target.value); setValue(""); }} className="rounded border border-slate-300 px-1.5 py-0.5">
          <option value="">attribute…</option>
          {attrs.map((a) => (
            <option key={a.key} value={a.key}>
              {a.name}
            </option>
          ))}
        </select>
        {chosen?.type === "enumeration" ? (
          <select value={value} onChange={(e) => setValue(e.target.value)} className="rounded border border-slate-300 px-1.5 py-0.5">
            <option value="">value…</option>
            {chosen.options.map((o) => (
              <option key={o.id} value={o.value}>
                {o.value}
              </option>
            ))}
          </select>
        ) : (
          <input value={value} onChange={(e) => setValue(e.target.value)} placeholder="value" className="w-28 rounded border border-slate-300 px-1.5 py-0.5" />
        )}
        <button
          onClick={() => save.mutate({ ...fixed, [key]: value })}
          disabled={!key || !value || save.isPending}
          className="rounded bg-slate-900 px-2 py-0.5 text-white disabled:opacity-40"
        >
          Set
        </button>
      </div>
      {save.isError && <p className="mt-1 text-xs text-red-600">{(save.error as Error).message}</p>}
    </div>
  );
}

/** The linked records each row of this type brings: a port, an address… with how each relates to the row. */
function Companions({
  mapping,
  typeUid,
  entry,
  vocabulary,
  onSaved,
}: {
  mapping: CatalogueMapping;
  typeUid: string;
  entry: PlanEntry;
  vocabulary: MappingVocabulary;
  onSaved: () => void;
}) {
  const [adding, setAdding] = useState(false);
  const [type, setType] = useState("");
  const [verb, setVerb] = useState("");
  const [fromCompanion, setFromCompanion] = useState(true);
  const [label, setLabel] = useState("");
  const save = useMutation({
    mutationFn: (companions: Parameters<typeof catalogueMappingApi.setPlan>[2]["companions"]) =>
      catalogueMappingApi.setPlan(mapping.id, typeUid, { companions }),
    onSuccess: () => {
      setAdding(false);
      setType("");
      setVerb("");
      setLabel("");
      onSaved();
    },
  });
  const companions = Object.entries(entry.companions ?? {});
  const main = entry.target_type?.name ?? "the record";
  return (
    <div className="mb-2">
      <p className="text-xs font-medium uppercase text-slate-400">Linked records</p>
      {companions.length === 0 && (
        <p className="mt-1 text-xs text-slate-400">None: each row becomes one {main}.</p>
      )}
      {companions.map(([cid, c]) => {
        const fields = Object.entries(entry.fields).filter(([, f]) => f.kind === "companion" && f.companion === cid);
        return (
          <div key={cid} className="mt-2 rounded border border-slate-200 p-2 text-xs">
            <div className="flex items-center gap-2">
              <span className="font-medium text-slate-800">{c.label}</span>
              <span className="text-slate-400">{c.type.name}</span>
              <Badge source={c.source} />
              <button
                onClick={() => save.mutate({ [cid]: null })}
                className="ml-auto text-slate-400 hover:text-red-600"
                title="Remove: its fields go to the description"
              >
                remove
              </button>
            </div>
            <div className="mt-0.5 text-slate-500">
              {c.from_companion ? (
                <>
                  {c.label} <span className="font-mono">—{c.verb}→</span> {main}
                </>
              ) : (
                <>
                  {main} <span className="font-mono">—{c.verb}→</span> {c.label}
                </>
              )}
              {Object.keys(c.fixed).length > 0 && (
                <span className="ml-1 text-slate-400">
                  · always {Object.entries(c.fixed).map(([k, v]) => `${k} ${v}`).join(", ")}
                </span>
              )}
            </div>
            <div className="mt-0.5 text-slate-500">
              {fields.length ? `gets ${fields.map(([k, f]) => `${k} → ${f.target}`).join(", ")}` : "no field goes here yet"}
            </div>
            <label className="mt-0.5 flex items-center gap-1 text-slate-500">
              <input
                type="checkbox"
                checked={c.share}
                onChange={(e) => save.mutate({ [cid]: { share: e.target.checked } })}
              />
              shared with every workspace
            </label>
          </div>
        );
      })}
      {adding ? (
        <div className="mt-2 space-y-1 rounded border border-dashed border-slate-300 p-2 text-xs">
          <input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="Name, e.g. Serial port"
            className="w-full rounded border border-slate-300 px-1.5 py-0.5"
          />
          <select value={type} onChange={(e) => setType(e.target.value)} className="w-full rounded border border-slate-300 px-1.5 py-0.5">
            <option value="">Type…</option>
            {vocabulary.types.map((t) => (
              <option key={t.uid} value={t.uid}>
                {t.name}
              </option>
            ))}
          </select>
          <div className="flex items-center gap-1">
            <select
              value={fromCompanion ? "from" : "to"}
              onChange={(e) => setFromCompanion(e.target.value === "from")}
              className="rounded border border-slate-300 px-1.5 py-0.5"
            >
              <option value="from">it → {main}</option>
              <option value="to">{main} → it</option>
            </select>
            <select value={verb} onChange={(e) => setVerb(e.target.value)} className="flex-1 rounded border border-slate-300 px-1.5 py-0.5">
              <option value="">relation…</option>
              {Object.entries(vocabulary.verbs).map(([v, note]) => (
                <option key={v} value={v} title={note}>
                  {v}
                </option>
              ))}
            </select>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() =>
                save.mutate({
                  [`linked-${Date.now().toString(36)}`]: {
                    type_uid: type,
                    verb,
                    from_companion: fromCompanion,
                    label: label || undefined,
                    suffix: label || undefined,
                  },
                })
              }
              disabled={!type || !verb || save.isPending}
              className="rounded bg-slate-900 px-2 py-1 text-white disabled:opacity-40"
            >
              Add
            </button>
            <button onClick={() => setAdding(false)} className="text-slate-500">
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button onClick={() => setAdding(true)} className="mt-2 text-xs text-indigo-600 hover:underline">
          + Add linked record
        </button>
      )}
      {save.isError && <p className="mt-1 text-xs text-red-600">{(save.error as Error).message}</p>}
    </div>
  );
}

function PlanCard({
  mapping,
  typeUid,
  entry,
  vocabulary,
  onSaved,
}: {
  mapping: CatalogueMapping;
  typeUid: string;
  entry: PlanEntry;
  vocabulary: MappingVocabulary;
  onSaved: () => void;
}) {
  const [targetType, setTargetType] = useState(entry.target_type?.uid ?? "");
  const [fields, setFields] = useState<Record<string, PlanField>>(entry.fields);
  const [relations, setRelations] = useState(entry.relations);
  const [share, setShare] = useState(!!entry.share);
  const [dirty, setDirty] = useState(false);
  useEffect(() => {
    setTargetType(entry.target_type?.uid ?? "");
    setFields(entry.fields);
    setRelations(entry.relations);
    setShare(!!entry.share);
    setDirty(false);
  }, [entry]);

  const attrs = vocabulary.attributes[entry.target_type?.uid ?? ""] ?? [];
  const byKey = new Map(attrs.map((a) => [a.key, a]));
  const typeChanged = targetType !== (entry.target_type?.uid ?? "");

  const save = useMutation({
    mutationFn: () =>
      catalogueMappingApi.setPlan(mapping.id, typeUid, {
        ...(typeChanged ? { target_type_uid: targetType } : {}),
        ...(typeChanged || share === !!entry.share ? {} : { share }),
        ...(typeChanged
          ? {}
          : {
              fields: Object.fromEntries(
                Object.entries(fields)
                  .filter(([k, f]) => JSON.stringify(f) !== JSON.stringify(entry.fields[k]))
                  .map(([k, f]) => [
                    k,
                    {
                      kind: f.kind,
                      target: f.target,
                      values: f.values,
                      verb: f.verb,
                      reverse: f.reverse,
                      text_to: f.text_to,
                      create_type: f.create_type?.uid ?? null,
                      companion: f.companion,
                      create_missing: f.create_missing,
                    },
                  ]),
              ),
              relations: Object.fromEntries(
                Object.entries(relations)
                  .filter(([k, r]) => JSON.stringify(r) !== JSON.stringify(entry.relations[k]))
                  .map(([k, r]) => [k, { verb: r.verb, reverse: r.reverse }]),
              ),
            }),
      }),
    onSuccess: onSaved,
  });

  const setField = (k: string, f: PlanField) => {
    setFields((cur) => ({ ...cur, [k]: { ...f, source: "person", confidence: 1 } }));
    setDirty(true);
  };
  const changeDestination = (k: string, value: string) => {
    const f = fields[k];
    if (value === "drop" || value === "description") return setField(k, { ...f, kind: value, target: null });
    if (value === "link") return setField(k, { ...f, kind: "link", target: null, verb: f.verb ?? null });
    if (value.startsWith("comp:")) {
      const [, cid, key] = value.split(":");
      return setField(k, { ...f, kind: "companion", companion: cid, target: key });
    }
    const key = value.slice(5);
    const attr = byKey.get(key);
    const kind =
      attr?.type === "enumeration" ? "enum" : attr?.type === "reference" ? "reference" : attr?.type === "group" ? "group" : "copy";
    setField(k, { ...f, kind, target: key, values: kind === "enum" ? f.values ?? {} : undefined });
  };

  const verbOptions = (
    <>
      <option value="">— no relation —</option>
      {Object.entries(vocabulary.verbs).map(([v, note]) => (
        <option key={v} value={v} title={note}>
          {v}
        </option>
      ))}
    </>
  );

  return (
    <div className="rounded-lg border border-slate-200 bg-white">
      <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 px-4 py-3">
        <div>
          <span className="font-medium text-slate-900">{entry.source_type}</span>{" "}
          <span className="text-xs text-slate-400">{entry.count} records</span>
          <div className="text-xs text-slate-400">e.g. {entry.profile.examples.slice(0, 3).join(", ")}</div>
        </div>
        <span className="text-slate-400">→</span>
        <select
          value={targetType}
          onChange={(e) => {
            setTargetType(e.target.value);
            setDirty(true);
          }}
          className="min-w-[16rem] rounded border border-slate-300 px-2 py-1 text-sm"
        >
          <option value="">Choose a type…</option>
          {vocabulary.types.map((t) => (
            <option key={t.uid} value={t.uid} title={t.path}>
              {t.name}
              {t.shared ? " (shared)" : ""}
            </option>
          ))}
        </select>
        {entry.target_type && !typeChanged && (
          <span className="text-xs text-slate-500">
            <Badge source={entry.target_type.source} confidence={entry.target_type.confidence} />
            {entry.target_type.reason && <span className="ml-1">{entry.target_type.reason}</span>}
          </span>
        )}
        {entry.target_type && !typeChanged && (
          <label
            className="flex items-center gap-1.5 text-xs text-slate-600"
            title="Shared records are visible from every workspace and edited only in this one"
          >
            <input
              type="checkbox"
              checked={share}
              onChange={(e) => {
                setShare(e.target.checked);
                setDirty(true);
              }}
            />
            Share with every workspace
            {vocabulary.types.find((t) => t.uid === entry.target_type?.uid)?.shared && (
              <span className="text-slate-400">(shared type)</span>
            )}
          </label>
        )}
        <button
          onClick={() => save.mutate()}
          disabled={!dirty || !targetType || save.isPending}
          className="ml-auto rounded bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-800 disabled:opacity-40"
        >
          {save.isPending ? "Saving…" : typeChanged ? "Use this type" : "Save plan"}
        </button>
      </div>
      {save.isError && <p className="px-4 pt-2 text-sm text-red-600">{(save.error as Error).message}</p>}
      {typeChanged && (
        <p className="px-4 py-3 text-xs text-slate-500">
          Save to see this type's attributes; the rules then propose where each field goes.
        </p>
      )}

      {!typeChanged && entry.target_type && (
        <div className="grid gap-4 p-4 lg:grid-cols-[3fr_2fr]">
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-slate-400">
              <tr>
                <th className="pb-1">Field</th>
                <th className="pb-1">Goes to</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 align-top">
              {Object.entries(fields).map(([k, f]) => {
                const info = entry.profile.fields[k];
                const attr = f.target ? byKey.get(f.target) : undefined;
                return (
                  <tr key={k}>
                    <td className="py-1.5 pr-3">
                      <div className="font-mono text-xs text-slate-800">{k}</div>
                      <div className="max-w-[16rem] truncate text-xs text-slate-400" title={info?.samples?.join("; ")}>
                        {info?.link_to
                          ? `link to ${Object.keys(info.link_to).join(", ")}`
                          : `${info?.distinct ?? 0} values: ${(info?.samples ?? []).slice(0, 3).join("; ")}`}
                      </div>
                    </td>
                    <td className="py-1.5">
                      <div className="flex flex-wrap items-center gap-1">
                        <select
                          value={destination(f)}
                          onChange={(e) => changeDestination(k, e.target.value)}
                          className="rounded border border-slate-300 px-1.5 py-0.5 text-xs"
                        >
                          <option value="drop">— leave out —</option>
                          <option value="description">the description</option>
                          <option value="link">a relation</option>
                          {Object.entries(entry.companions ?? {}).map(([cid, c]) => (
                            <optgroup key={cid} label={`${c.label} (${c.type.name})`}>
                              {(vocabulary.attributes[c.type.uid] ?? [])
                                .filter((a) => a.type !== "reference")
                                .map((a) => (
                                  <option key={a.key} value={`comp:${cid}:${a.key}`}>
                                    {c.label} → {a.name}
                                  </option>
                                ))}
                            </optgroup>
                          ))}
                          {attrs.map((a) => (
                            <option key={a.key} value={`attr:${a.key}`}>
                              {a.name}
                              {a.type === "reference" ? ` → ${a.ref_type}` : ""}
                            </option>
                          ))}
                        </select>
                        {f.kind === "link" && (
                          <>
                            <select
                              value={f.verb ?? ""}
                              onChange={(e) => setField(k, { ...f, verb: e.target.value || null })}
                              className="rounded border border-slate-300 px-1.5 py-0.5 text-xs"
                            >
                              {verbOptions}
                            </select>
                            <label className="text-[11px] text-slate-500">
                              <input
                                type="checkbox"
                                checked={!!f.reverse}
                                onChange={(e) => setField(k, { ...f, reverse: e.target.checked })}
                              />{" "}
                              reversed
                            </label>
                          </>
                        )}
                        <Badge source={f.source} confidence={f.confidence} />
                      </div>
                      {f.kind === "group" && (
                        <label className="mt-0.5 flex items-center gap-1 text-[11px] text-slate-500">
                          matched to a group by name (case and accents ignored);
                          <input
                            type="checkbox"
                            checked={!!f.create_missing}
                            onChange={(e) => setField(k, { ...f, create_missing: e.target.checked })}
                          />
                          create the missing ones
                        </label>
                      )}
                      {f.kind === "reference" && (
                        <div className="mt-0.5 text-[11px] text-slate-500">
                          matched to a {f.ref_type} by name, code or old key
                          {f.text_to ? `; the text also goes to ${byKey.get(f.text_to)?.name ?? f.text_to}` : ""}
                          {(attr?.create_types.length ?? 0) > 0 && (
                            <div className="mt-0.5 flex items-center gap-1">
                              if none matches:
                              <select
                                value={f.create_type?.uid ?? ""}
                                onChange={(e) => {
                                  const t = attr?.create_types.find((c) => c.uid === e.target.value);
                                  setField(k, { ...f, create_type: t ?? null });
                                }}
                                className="rounded border border-slate-300 px-1 py-0 text-[11px]"
                              >
                                <option value="">keep the text, flag the row</option>
                                {attr?.create_types.map((c) => (
                                  <option key={c.uid} value={c.uid}>
                                    create a {c.name}
                                  </option>
                                ))}
                              </select>
                            </div>
                          )}
                        </div>
                      )}
                      {f.kind === "enum" && attr && (
                        <div className="mt-1 space-y-0.5">
                          {(info?.samples ?? []).map((v) => (
                            <div key={v} className="flex items-center gap-1 text-[11px]">
                              <span className="w-32 truncate text-slate-600" title={v}>
                                {v}
                              </span>
                              →
                              <select
                                value={f.values?.[v] ?? ""}
                                onChange={(e) => {
                                  const values = { ...(f.values ?? {}) };
                                  if (e.target.value) values[v] = e.target.value;
                                  else delete values[v];
                                  setField(k, { ...f, values });
                                }}
                                className="rounded border border-slate-300 px-1 py-0 text-[11px]"
                              >
                                <option value="">(keep in description)</option>
                                {attr.options.map((o) => (
                                  <option key={o.id} value={o.id}>
                                    {o.value}
                                  </option>
                                ))}
                              </select>
                            </div>
                          ))}
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          <div>
            <AlwaysSet mapping={mapping} typeUid={typeUid} entry={entry} vocabulary={vocabulary} onSaved={onSaved} />
            <Companions mapping={mapping} typeUid={typeUid} entry={entry} vocabulary={vocabulary} onSaved={onSaved} />
            <p className="mt-4 text-xs font-medium uppercase text-slate-400">Links</p>
            {Object.keys(relations).length === 0 && <p className="mt-1 text-xs text-slate-400">None.</p>}
            {Object.entries(relations).map(([name, r]) => (
              <div key={name} className="mt-2 text-sm">
                <div className="text-slate-800">
                  “{name}” <span className="text-xs text-slate-400">
                    {entry.profile.relations[name]?.count} to {Object.keys(entry.profile.relations[name]?.to ?? {}).join(", ")}
                  </span>
                </div>
                <div className="mt-0.5 flex flex-wrap items-center gap-1">
                  <select
                    value={r.verb ?? ""}
                    onChange={(e) => {
                      setRelations((cur) => ({
                        ...cur,
                        [name]: { ...r, verb: e.target.value || null, source: "person", confidence: 1 },
                      }));
                      setDirty(true);
                    }}
                    className="rounded border border-slate-300 px-1.5 py-0.5 text-xs"
                    title={r.verb ? vocabulary.verbs[r.verb] : undefined}
                  >
                    {verbOptions}
                  </select>
                  <label className="text-[11px] text-slate-500">
                    <input
                      type="checkbox"
                      checked={r.reverse}
                      onChange={(e) => {
                        setRelations((cur) => ({
                          ...cur,
                          [name]: { ...r, reverse: e.target.checked, source: "person", confidence: 1 },
                        }));
                        setDirty(true);
                      }}
                    />{" "}
                    reversed
                  </label>
                  <Badge source={r.source} confidence={r.confidence} />
                </div>
                {r.verb && <p className="text-[11px] text-slate-400">{vocabulary.verbs[r.verb]}</p>}
              </div>
            ))}
            <p className="mt-3 text-[11px] text-slate-400">
              A link becomes a relation once both of its records are mapped, even by a later mapping.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function attrText(v: RecordProposal["attributes"][string]): string {
  return v.label ?? String(v.value);
}

export function RecordMappingReview({ mapping: m }: { mapping: CatalogueMapping }) {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"plan" | "rows">("plan");
  const [typeFilter, setTypeFilter] = useState("");
  const [status, setStatus] = useState<string>("proposed");
  const [notice, setNotice] = useState<string | null>(null);

  const vocabulary = useQuery({
    queryKey: ["mapping-vocabulary", m.id],
    queryFn: () => catalogueMappingApi.vocabulary(m.id),
    enabled: m.state === "ready",
  });
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["catalogue-mapping", m.id] });
    queryClient.invalidateQueries({ queryKey: ["mapping-vocabulary", m.id] });
  };

  const decide = useMutation({
    mutationFn: (v: { itemId: string; status: MappingStatus }) =>
      catalogueMappingApi.decide(m.id, v.itemId, { status: v.status }),
    onSuccess: refresh,
    onError: (e) => setNotice((e as Error).message),
  });
  const acceptType = useMutation({
    mutationFn: (typeUid?: string) => catalogueMappingApi.decideMany(m.id, { min_confidence: 0.8, type_uid: typeUid }),
    onSuccess: (r) => {
      setNotice(`${r.changed} rows accepted.`);
      refresh();
    },
  });
  const recheck = useMutation({
    mutationFn: () => catalogueMappingApi.recheck(m.id),
    onSuccess: (r) => {
      setNotice(`${r.rows} open rows checked again; ${r.warnings} still have something to look at.`);
      refresh();
    },
  });
  const [refused, setRefused] = useState<string | null>(null);
  const shareRefs = useMutation({
    mutationFn: () => catalogueMappingApi.shareReferences(m.id),
    onSuccess: (r) => {
      setRefused(null);
      setNotice(`${r.shared} records shared with every workspace; the rows now point at them.`);
      refresh();
    },
    onError: (e) => setNotice((e as Error).message),
  });
  const fill = useMutation({
    mutationFn: () => catalogueMappingApi.fillReferences(m.id),
    onSuccess: (r) =>
      setNotice(
        `${r.filled} references set on ${r.records} applied records.` +
          (r.still_hidden ? ` ${r.still_hidden} still name records that are not shared.` : ""),
      ),
    onError: (e) => setNotice((e as Error).message),
  });
  const apply = useMutation({
    mutationFn: (keepText: boolean) => catalogueMappingApi.apply(m.id, keepText),
    onMutate: () => setRefused(null),
    onError: (e) => {
      const body = e instanceof ApiError ? (e.body as { detail?: { code?: string; error?: string } }) : null;
      if (body?.detail?.code === "hidden_references") setRefused(body.detail.error ?? "");
      else setNotice((e as Error).message);
    },
    onSuccess: (r) => {
      setNotice(
        `${r.applied} records created or merged` +
          (r.relations ? `, ${r.relations} relations made` : "") +
          "." +
          (r.failed.length ? ` Not applied: ${r.failed.map((f) => `${f.source_key} (${f.error})`).join("; ")}.` : "") +
          (r.relations_failed?.length ? ` ${r.relations_failed.length} relations refused: ${r.relations_failed[0].error}` : ""),
      );
      refresh();
    },
  });
  const undo = useMutation({
    mutationFn: () => catalogueMappingApi.undo(m.id),
    onSuccess: (r) => {
      setNotice(`Undone: ${r.retired} records retired, ${r.relations_removed ?? 0} relations removed.`);
      refresh();
    },
  });

  const items = m.items ?? [];
  const plan = m.plan ?? {};
  const typeOf = (i: MappingItem) => String((i.source as { type_uid?: string }).type_uid ?? "");
  const shown = useMemo(
    () =>
      items.filter(
        (i) => (!typeFilter || typeOf(i) === typeFilter) && (status === "all" || i.status === status),
      ),
    [items, typeFilter, status],
  );
  const unplanned = Object.values(plan).filter((e) => !e.target_type).length;
  const accepted = m.counts.accepted ?? 0;
  const applied = m.counts.applied ?? 0;

  return (
    <div>
      <div className="mt-5 flex flex-wrap items-center gap-2">
        {(["plan", "rows"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-md px-3 py-1.5 text-sm ${
              tab === t ? "bg-slate-900 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200"
            }`}
          >
            {t === "plan" ? `Plan · ${Object.keys(plan).length} types` : `Rows · ${items.length}`}
          </button>
        ))}
        {unplanned > 0 && (
          <span className="text-xs text-amber-700">{unplanned} types have no target type yet.</span>
        )}
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={() => recheck.mutate()}
            disabled={recheck.isPending}
            title="Match references again, e.g. after the catalogue's records were shared"
            className="rounded border border-slate-300 px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            {recheck.isPending ? "Checking…" : "Recheck references"}
          </button>
          <button
            onClick={() => apply.mutate(false)}
            disabled={!accepted || apply.isPending}
            className="rounded bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {apply.isPending ? "Applying…" : `Apply ${accepted} accepted`}
          </button>
          {applied > 0 && (
            <button
              onClick={() => fill.mutate()}
              disabled={fill.isPending}
              title="Set the references applied records still lack, now that they resolve"
              className="rounded border border-slate-300 px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              {fill.isPending ? "Filling in…" : "Fill in references"}
            </button>
          )}
          {applied > 0 && (
            <button
              onClick={() => {
                if (confirm(`Retire the ${applied} records this mapping created in ${m.target_workspace_id}?`)) undo.mutate();
              }}
              className="rounded px-2 py-1.5 text-xs text-red-600 hover:bg-red-50"
            >
              Undo applied
            </button>
          )}
        </div>
      </div>
      {(m.hidden_references?.length ?? 0) > 0 && (
        <div className="mt-3 rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          <div className="flex flex-wrap items-center gap-3">
            <span>
              <strong>{m.hidden_references!.reduce((n, h) => n + h.rows, 0)} rows</strong> name{" "}
              {m.hidden_references!.length} records that exist in{" "}
              {[...new Set(m.hidden_references!.map((h) => h.workspace_id))].join(", ")} but are not shared with{" "}
              {m.target_workspace_id}. Applied now, they would keep only the text.
            </span>
            <button
              onClick={() => shareRefs.mutate()}
              disabled={shareRefs.isPending}
              className="ml-auto rounded bg-amber-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-700 disabled:opacity-50"
            >
              {shareRefs.isPending ? "Sharing…" : "Share them and recheck"}
            </button>
          </div>
          <p className="mt-1 text-xs text-amber-800">
            {m.hidden_references!
              .slice(0, 8)
              .map((h) => `${h.name} (${h.type ?? "record"}, ${h.rows})`)
              .join(" · ")}
            {m.hidden_references!.length > 8 ? " …" : ""}
          </p>
        </div>
      )}
      {refused && (
        <div className="mt-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          <p>{refused}</p>
          <div className="mt-2 flex gap-2">
            <button
              onClick={() => shareRefs.mutate()}
              className="rounded bg-red-700 px-3 py-1 text-xs font-medium text-white hover:bg-red-800"
            >
              Share them and recheck
            </button>
            <button
              onClick={() => apply.mutate(true)}
              className="rounded border border-red-300 px-3 py-1 text-xs text-red-800 hover:bg-red-100"
            >
              Apply anyway, keeping the text
            </button>
          </div>
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

      {tab === "plan" && (
        <div className="mt-4 space-y-4">
          <p className="text-sm text-slate-500">
            One plan per imported type: what its records become, where each field goes, and what its links mean. Rows
            follow their type's plan, except rows you changed yourself.
          </p>
          {!vocabulary.data && <p className="text-sm text-slate-500">Loading the target's types…</p>}
          {vocabulary.data &&
            Object.entries(plan).map(([uid, entry]) => (
              <PlanCard key={uid} mapping={m} typeUid={uid} entry={entry} vocabulary={vocabulary.data} onSaved={refresh} />
            ))}
        </div>
      )}

      {tab === "rows" && (
        <div className="mt-4">
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="rounded border border-slate-300 px-2 py-1 text-sm"
            >
              <option value="">Every type</option>
              {Object.entries(plan).map(([uid, e]) => (
                <option key={uid} value={uid}>
                  {e.source_type} → {e.target_type?.name ?? "?"}
                </option>
              ))}
            </select>
            {(["proposed", "accepted", "skipped", "applied", "all"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setStatus(s)}
                className={`rounded-full px-3 py-1 text-xs ${
                  status === s ? "bg-slate-900 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200"
                }`}
              >
                {s === "proposed" ? "To review" : s[0].toUpperCase() + s.slice(1)}{" "}
                <span className="opacity-70">{s === "all" ? items.length : m.counts[s] ?? 0}</span>
              </button>
            ))}
            <button
              onClick={() => acceptType.mutate(typeFilter || undefined)}
              disabled={acceptType.isPending}
              className="ml-auto rounded border border-slate-300 px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50"
            >
              Accept {typeFilter ? "this type's" : "all"} rows ≥ 80%
            </button>
          </div>
          <div className="mt-3 overflow-hidden rounded-lg border border-slate-200 bg-white">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-3 py-2">Imported</th>
                  <th className="px-3 py-2">Becomes</th>
                  <th className="px-3 py-2">Confidence</th>
                  <th className="px-3 py-2 text-right">Decision</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {shown.map((item) => {
                  const p = item.proposal as unknown as RecordProposal;
                  const carry = item.source.carry;
                  return (
                    <tr key={item.id} className={item.status === "skipped" ? "opacity-60" : undefined}>
                      <td className="px-3 py-2 align-top">
                        <div className="text-slate-900">{item.source_name}</div>
                        <div className="text-xs text-slate-400">
                          <span className="font-mono">{item.source_key}</span> · {item.source_type}
                        </div>
                        {carry && (carry.avatar || carry.attachments || carry.history || carry.tickets) ? (
                          <div className="text-xs text-slate-500">
                            + {[carry.avatar && "avatar", carry.attachments && `${carry.attachments} files`,
                               carry.history && `${carry.history} history`, carry.comments && `${carry.comments} comments`,
                               carry.tickets && `${carry.tickets} tickets`].filter(Boolean).join(" · ")}
                          </div>
                        ) : null}
                      </td>
                      <td className="px-3 py-2 align-top">
                        {p.type ? (
                          <>
                            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-600">
                              {p.action === "merge" ? `merge into ${p.merge_into?.name}` : p.type.name}
                            </span>
                            {p.action !== "merge" && p.share && (
                              <span className="ml-1 rounded bg-sky-50 px-1.5 py-0.5 text-[11px] text-sky-700">
                                shared
                              </span>
                            )}
                          </>
                        ) : (
                          <span className="text-xs text-amber-700">no type yet</span>
                        )}
                        <div className="mt-1 flex flex-wrap gap-1">
                          {Object.entries(p.attributes ?? {})
                            .filter(([k]) => k !== "description")
                            .map(([k, v]) => (
                              <span key={k} className="rounded bg-slate-50 px-1.5 py-0.5 text-[11px] text-slate-600 ring-1 ring-slate-100">
                                {k}: <span className="text-slate-900">{attrText(v)}</span>
                                {v.create && <span className="ml-1 text-sky-700">new {v.create.type}</span>}
                                {v.create_group && <span className="ml-1 text-sky-700">new group</span>}
                                {v.hidden && <span className="ml-1 text-amber-700">not shared</span>}
                              </span>
                            ))}
                          {(p.companions ?? []).map((c) => (
                            <span
                              key={c.id}
                              className="rounded bg-indigo-50 px-1.5 py-0.5 text-[11px] text-indigo-700"
                              title={`${c.from_companion ? `${c.name} —${c.verb}→ this` : `this —${c.verb}→ ${c.name}`}`}
                            >
                              + {c.type.name}{" "}
                              {Object.entries(c.attributes)
                                .filter(([, a]) => a.from)
                                .map(([k, a]) => `${k} ${String(a.value)}`)
                                .join(", ")}
                            </span>
                          ))}
                          {(p.links ?? []).filter((l) => l.verb).length > 0 && (
                            <span className="rounded bg-sky-50 px-1.5 py-0.5 text-[11px] text-sky-700">
                              {(p.links ?? []).filter((l) => l.verb).length} link(s)
                            </span>
                          )}
                        </div>
                        {p.warnings?.map((w) => (
                          <div key={w} className="mt-0.5 text-xs text-amber-700">
                            ⚠ {w}
                          </div>
                        ))}
                      </td>
                      <td className="px-3 py-2 align-top">
                        <Dot value={item.confidence} />
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
                                className="text-slate-500 hover:underline"
                              >
                                Reopen
                              </button>
                            )}
                          </>
                        )}
                      </td>
                    </tr>
                  );
                })}
                {shown.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-3 py-6 text-center text-slate-400">
                      No rows here.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
