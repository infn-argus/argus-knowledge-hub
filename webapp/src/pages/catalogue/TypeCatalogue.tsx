import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { iconsApi, typeCatalogueApi, type CatalogueType } from "../../api/client";
import { AuthenticatedImage } from "../../components/AuthenticatedImage";

const BRANCH_LABEL: Record<string, string> = {
  equipment: "Equipment",
  functional: "Functional",
  control: "Control",
  catalogue: "Catalogue",
  locations: "Locations",
  it: "IT records",
  engineering: "Engineering",
  other: "This workspace's own",
};

function Icon({ uid, className = "h-4 w-4" }: { uid: string | null; className?: string }) {
  return uid ? (
    <AuthenticatedImage uid={uid} alt="" fetchBlobUrl={iconsApi.fetchBlobUrl} className={`${className} shrink-0 object-contain`} />
  ) : (
    <span className={`${className} shrink-0 rounded-sm bg-slate-200`} />
  );
}

/** Every object type this workspace can use, as one map: where it sits, what it is, what it holds. */
export function TypeCataloguePage() {
  const data = useQuery({ queryKey: ["type-catalogue"], queryFn: typeCatalogueApi.get });
  const [query, setQuery] = useState("");
  const [branch, setBranch] = useState<string>("");
  const [selected, setSelected] = useState<string | null>(null);
  const [open, setOpen] = useState<Set<string>>(new Set(["Item", "Engineered Item", "Asset"]));

  const types = useMemo(() => data.data?.types ?? [], [data.data]);
  const byName = useMemo(() => new Map(types.map((t) => [t.name, t])), [types]);
  const children = useMemo(() => {
    const m = new Map<string, CatalogueType[]>();
    for (const t of types) {
      const key = t.parent && byName.has(t.parent) ? t.parent : "";
      m.set(key, [...(m.get(key) ?? []), t]);
    }
    for (const list of m.values()) list.sort((a, b) => a.name.localeCompare(b.name));
    return m;
  }, [types, byName]);

  const q = query.trim().toLowerCase();
  const matches = (t: CatalogueType) =>
    (!branch || t.branch === branch) &&
    (!q ||
      t.name.toLowerCase().includes(q) ||
      (t.description ?? "").toLowerCase().includes(q) ||
      t.aliases.some((a) => a.toLowerCase().includes(q)) ||
      t.attributes.some((a) => a.key.toLowerCase().includes(q) || a.name.toLowerCase().includes(q)));
  // A type shows when it or anything below it matches.
  const shows = useMemo(() => {
    const memo = new Map<string, boolean>();
    const visit = (t: CatalogueType): boolean => {
      if (memo.has(t.name)) return memo.get(t.name)!;
      const v = matches(t) || (children.get(t.name) ?? []).some(visit);
      memo.set(t.name, v);
      return v;
    };
    types.forEach(visit);
    return memo;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [types, children, q, branch]);
  const filtering = !!q || !!branch;
  const current = selected ? byName.get(selected) : undefined;

  const row = (t: CatalogueType, depth: number): JSX.Element | null => {
    if (!shows.get(t.name)) return null;
    const kids = children.get(t.name) ?? [];
    const expanded = filtering || open.has(t.name);
    return (
      <div key={t.uid}>
        <div
          className={`flex cursor-pointer items-center gap-1.5 rounded px-1.5 py-1 text-sm hover:bg-slate-100 ${
            selected === t.name ? "bg-indigo-50" : ""
          } ${filtering && !matches(t) ? "opacity-50" : ""}`}
          style={{ paddingLeft: depth * 14 + 6 }}
          onClick={() => setSelected(t.name)}
        >
          <button
            className="w-3 shrink-0 text-xs text-slate-400"
            onClick={(e) => {
              e.stopPropagation();
              setOpen((cur) => {
                const next = new Set(cur);
                if (next.has(t.name)) next.delete(t.name);
                else next.add(t.name);
                return next;
              });
            }}
          >
            {kids.length ? (expanded ? "▾" : "▸") : ""}
          </button>
          <Icon uid={t.icon_uid} />
          <span className={t.abstract ? "font-medium text-slate-500" : "text-slate-900"}>{t.name}</span>
          {t.shared && <span className="rounded bg-sky-50 px-1 text-[10px] text-sky-700">shared</span>}
          <span className="ml-2 truncate text-xs text-slate-400">{t.description}</span>
          {t.records_with_subtypes > 0 && (
            <span className="ml-auto shrink-0 pl-2 text-xs tabular-nums text-slate-400">{t.records_with_subtypes}</span>
          )}
        </div>
        {expanded && kids.map((k) => row(k, depth + 1))}
      </div>
    );
  };

  return (
    <div className="max-w-7xl">
      <h1 className="text-2xl font-semibold text-slate-900">Type catalogue</h1>
      <p className="mt-1 text-sm text-slate-500">
        Every object type this workspace can use: its own and the shared catalogue's. Pick one to see what it is,
        where it sits, what its records hold and what its references mean in the graph. Grey names are categories
        that group kinds; counts are this workspace's records, the type's and those of the types below it.
      </p>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search names, descriptions, aliases, attributes…"
          className="w-80 rounded border border-slate-300 px-3 py-1.5 text-sm"
        />
        {(data.data?.branches ?? []).map((b) => (
          <button
            key={b}
            onClick={() => setBranch(branch === b ? "" : b)}
            className={`rounded-full px-3 py-1 text-xs ${
              branch === b ? "bg-slate-900 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200"
            }`}
          >
            {BRANCH_LABEL[b] ?? b}
          </button>
        ))}
      </div>
      {data.isLoading && <p className="mt-4 text-sm text-slate-500">Loading…</p>}
      {data.isError && <p className="mt-4 text-sm text-red-600">{(data.error as Error).message}</p>}

      <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="max-h-[75vh] overflow-y-auto rounded-lg border border-slate-200 bg-white p-2">
          {(children.get("") ?? []).map((t) => row(t, 0))}
        </div>
        <div className="lg:sticky lg:top-4 lg:self-start">
          {!current && (
            <p className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-400">
              Pick a type on the left.
            </p>
          )}
          {current && <TypeCard t={current} classes={data.data?.equipment_classes ?? []} onPick={setSelected} />}
        </div>
      </div>
    </div>
  );
}

function TypeCard({
  t,
  classes,
  onPick,
}: {
  t: CatalogueType;
  classes: { name: string; status: string; promoted_type: string | null }[];
  onPick: (name: string) => void;
}) {
  const own = t.attributes.filter((a) => a.origin === t.name);
  const inherited = t.attributes.filter((a) => a.origin !== t.name);
  const origins = [...new Set(inherited.map((a) => a.origin))];
  const attrRow = (a: CatalogueType["attributes"][number]) => (
    <tr key={a.key}>
      <td className="py-1 pr-2 align-top">
        <div className="text-slate-800">{a.name}</div>
        <div className="font-mono text-[11px] text-slate-400">{a.key}</div>
      </td>
      <td className="py-1 pr-2 align-top text-xs text-slate-600">
        {a.type}
        {a.multi ? ", several" : ""}
        {a.unique ? ", unique" : ""}
        {a.required ? ", required" : ""}
        {a.refers_to && (
          <div>
            → <button onClick={() => onPick(a.refers_to!)} className="text-indigo-600 hover:underline">{a.refers_to}</button>
            {a.relation && <span className="ml-1 rounded bg-slate-100 px-1 font-mono text-[10px]">{a.relation}</span>}
          </div>
        )}
      </td>
      <td className="py-1 align-top text-[11px] text-slate-500">{a.options.slice(0, 8).join(", ")}{a.options.length > 8 ? "…" : ""}</td>
    </tr>
  );
  return (
    <div className="max-h-[80vh] overflow-y-auto rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-start gap-3">
        <Icon uid={t.icon_uid} className="h-8 w-8" />
        <div>
          <h2 className="text-lg font-semibold text-slate-900">{t.name}</h2>
          <p className="text-xs text-slate-400">
            {t.path.map((p, i) => (
              <span key={p}>
                {i > 0 && " › "}
                {p === t.name ? p : (
                  <button onClick={() => onPick(p)} className="hover:text-indigo-600 hover:underline">{p}</button>
                )}
              </span>
            ))}
          </p>
        </div>
        <Link to={`/schemas/${t.uid}`} className="ml-auto shrink-0 text-xs text-indigo-600 hover:underline">
          Open type ↗
        </Link>
      </div>
      {t.description && <p className="mt-3 text-sm text-slate-700">{t.description}</p>}
      <div className="mt-3 flex flex-wrap gap-1 text-[11px]">
        {t.abstract && <span className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-600">category: records are of its kinds</span>}
        <span className={`rounded px-1.5 py-0.5 ${t.shared ? "bg-sky-50 text-sky-700" : "bg-slate-100 text-slate-600"}`}>
          {t.shared ? `shared, from ${t.owner_workspace}` : "this workspace's own"}
        </span>
        <span className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-600">
          {t.records} records{t.records_with_subtypes !== t.records ? `, ${t.records_with_subtypes} with the types below` : ""}
        </span>
      </div>
      {t.aliases.length > 0 && (
        <p className="mt-2 text-xs text-slate-500">
          Also called: {t.aliases.join(", ")} <span className="text-slate-400">(imports matching these names map here)</span>
        </p>
      )}

      <h3 className="mt-4 text-xs font-medium uppercase text-slate-400">Its own attributes</h3>
      {own.length ? (
        <table className="mt-1 w-full text-sm"><tbody className="divide-y divide-slate-100">{own.map(attrRow)}</tbody></table>
      ) : (
        <p className="mt-1 text-xs text-slate-400">None: it holds what it inherits.</p>
      )}
      {origins.map((o) => (
        <details key={o} className="mt-3">
          <summary className="cursor-pointer text-xs font-medium uppercase text-slate-400">
            From {o} ({inherited.filter((a) => a.origin === o).length})
          </summary>
          <table className="mt-1 w-full text-sm">
            <tbody className="divide-y divide-slate-100">{inherited.filter((a) => a.origin === o).map(attrRow)}</tbody>
          </table>
        </details>
      ))}

      {t.name === "Other Equipment" && (
        <div className="mt-4">
          <h3 className="text-xs font-medium uppercase text-slate-400">Equipment classes</h3>
          <p className="mt-1 text-xs text-slate-500">
            A unit with no type of its own gets one of these classes. A promoted class has become a type.
          </p>
          <ul className="mt-1 space-y-0.5 text-sm">
            {classes.map((c) => (
              <li key={c.name}>
                {c.name}{" "}
                {c.status === "promoted" ? (
                  <span className="text-xs text-slate-400">
                    → type{" "}
                    <button onClick={() => onPick(c.promoted_type!)} className="text-indigo-600 hover:underline">
                      {c.promoted_type}
                    </button>
                  </span>
                ) : (
                  <span className="text-xs text-emerald-700">assignable</span>
                )}
              </li>
            ))}
          </ul>
          <Link to="/catalogue/equipment-classes" className="mt-1 inline-block text-xs text-indigo-600 hover:underline">
            Manage the classes ↗
          </Link>
        </div>
      )}
    </div>
  );
}
