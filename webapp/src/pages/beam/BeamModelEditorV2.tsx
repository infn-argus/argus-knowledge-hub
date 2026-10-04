import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, beamModelApi } from "../../api/client";
import type {
  BeamImportReport, BeamModelCheck, BeamModelV2, BeamVocabulary, V2Boundary, V2Component, V2Dataset, V2Path,
  V2Placement, V2Profile,
} from "../../api/types";

/** The beam model editor for argus.beam-model/2 (docs/beam-model-format.md). It edits the document an import
 *  reads: beams, systems, paths of placements (a component may be on several paths), the connections between
 *  paths, and each component — type, capabilities, aliases, supports, fiducials, boundaries, material, states,
 *  measurement model. Everything it does not show (definitions, other datasets, bindings, provenance, a tool's
 *  own fields) is passed through untouched, so saving never loses what came in. */

const SYSTEM_KINDS = ["Storage ring", "Synchrotron", "Accumulator", "Collider", "Linac", "Transfer line",
  "Laser transport", "FEL line", "Injector", "Experimental line", "Other"];
/** The strength a type is usually given, offered as a column. */
const STRENGTH: Record<string, string> = {
  quadrupole: "k1", sextupole: "k2", octupole: "k3", dipole: "angle", corrector: "kick", kicker: "kick",
  rf_cavity: "voltage", accelerating_structure: "voltage", buncher: "voltage", rf_deflector: "voltage",
  crab_cavity: "voltage", solenoid: "ks", lens: "focal_length", beam_splitter: "split_ratio", mirror: "incidence_angle",
};

export function emptyModelV2(): BeamModelV2 {
  return {
    schema_version: "argus.beam-model/2",
    model: { id: "", name: "", source: "argus-editor", version: "1" },
    systems: [{ id: "main", name: "", kind: "Linac", beams: ["beam"] }],
    beams: [{ id: "beam", kind: "particle", species: "electron", systems: ["main"] }],
    paths: [{ id: "line", name: "", system: "main", topology: "open", placements: [] }],
    connections: [],
    components: [],
    datasets: [],
  };
}

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
type Update = (fn: (d: BeamModelV2) => void) => void;

function placements(p: V2Path): V2Placement[] {
  return p.placements.map((x) => (typeof x === "string" ? { component: x } : x));
}

/** Placement ids as the model resolves them: the component, then `ID#2` for a second pass. */
function placementIds(p: V2Path): string[] {
  const seen: Record<string, number> = {};
  return placements(p).map((pl) => {
    seen[pl.component] = (seen[pl.component] ?? 0) + 1;
    return pl.id ?? (seen[pl.component] === 1 ? pl.component : `${pl.component}#${seen[pl.component]}`);
  });
}

function setPlacements(p: V2Path, list: V2Placement[]) {
  p.placements = list.map((pl) => (Object.keys(pl).filter((k) => (pl as unknown as Record<string, unknown>)[k] !== undefined
    && !(k === "reversed" && !pl.reversed)).length === 1 ? pl.component : pl));
}

function familyOf(vocab: BeamVocabulary | undefined, type: string | undefined): string {
  if (!vocab || !type) return "generic";
  return Object.entries(vocab.families).find(([, ts]) => type in ts)?.[0] ?? "generic";
}

function capsOf(vocab: BeamVocabulary | undefined, c: V2Component): string[] {
  if (c.capabilities) return c.capabilities;
  const fam = familyOf(vocab, c.type);
  return vocab?.families[fam]?.[c.type ?? ""] ?? [];
}

function pathDataset(doc: BeamModelV2, pathId: string): V2Dataset | undefined {
  const all = (doc.datasets ?? []).filter((d) => d.path === pathId);
  return all.find((d) => Object.keys(d.values ?? {}).length > 0) ?? all[0];
}

function ensureDataset(d: BeamModelV2, pathId: string): V2Dataset {
  d.datasets = d.datasets ?? [];
  let ds = pathDataset(d, pathId);
  if (!ds) {
    const p = d.paths.find((x) => x.id === pathId)!;
    ds = { id: `${pathId}-design`, name: `${p.name || p.id} design`, kind: "design", path: pathId, values: {} };
    d.datasets.push(ds);
  }
  ds.values = ds.values ?? {};
  return ds;
}

function newId(d: BeamModelV2, prefix = "E"): string {
  let n = d.components.length + 1;
  while (d.components.some((c) => c.id === `${prefix}${String(n).padStart(3, "0")}`)) n++;
  return `${prefix}${String(n).padStart(3, "0")}`;
}

function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    const b = e.body as { detail?: unknown } | undefined;
    const d = b?.detail as { problems?: string[]; models?: BeamModelCheck[] } | string | undefined;
    if (typeof d === "string") return d;
    if (d?.problems) return d.problems.join("; ");
    if (d?.models) return d.models.filter((m) => !m.ok).map((m) => m.problems.join("; ")).join(" · ");
    return e.message;
  }
  return e instanceof Error ? e.message : String(e);
}

/** What is sent: empty names dropped, empty datasets left out, observables used but not built in declared. */
export function tidyV2(doc: BeamModelV2, vocab?: BeamVocabulary): BeamModelV2 {
  const d = clone(doc);
  const strip = (o: { name?: string }) => { if (!o.name) delete o.name; };
  d.systems.forEach(strip);
  d.paths.forEach(strip);
  d.components.forEach(strip);
  d.beams.forEach(strip);
  if (!d.model.name) delete d.model.name;
  d.datasets = (d.datasets ?? []).filter((x) => Object.keys(x.values ?? {}).length > 0 || Object.keys(x).some(
    (k) => !["id", "name", "kind", "path", "values"].includes(k)));
  const builtIn = new Set(Object.keys(vocab?.observables ?? {}));
  const declared = new Set((d.observables ?? []).map((o) => o.quantity));
  for (const q of d.components.flatMap((c) => c.observes ?? [])) {
    if (!declared.has(q) && !builtIn.has(q)) {
      d.observables = [...(d.observables ?? []), { quantity: q }];
      declared.add(q);
    }
  }
  return d;
}

// ------------------------------------------------------------------------- the editor

export function EditorV2({ initial, editing }: { initial: BeamModelV2; editing: boolean }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const vocab = useQuery({ queryKey: ["beam-vocabulary"], queryFn: beamModelApi.vocabulary, staleTime: Infinity });
  const [doc, setDoc] = useState<BeamModelV2>(() => normalise(clone(initial)));
  const [pathId, setPathId] = useState(initial.paths[0]?.id ?? "");
  const [selected, setSelected] = useState<string | null>(null);
  const update: Update = (fn) => setDoc((d) => { const n = clone(d); fn(n); return n; });
  const check = useMutation({ mutationFn: () => beamModelApi.validate(tidyV2(doc, vocab.data)) });
  const save = useMutation({
    mutationFn: () => beamModelApi.importModels(tidyV2(doc, vocab.data)),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["beam-systems"] });
      void qc.invalidateQueries({ queryKey: ["beam-model-export"] });
    },
  });
  const report = save.data && !("models" in save.data) ? (save.data as BeamImportReport) : null;
  const path = doc.paths.find((p) => p.id === pathId);
  const placed = useMemo(() => new Set(doc.paths.flatMap((p) => placements(p).map((pl) => pl.component))), [doc.paths]);
  const offPath = doc.components.filter((c) => !placed.has(c.id));
  const verdict = check.data?.models[0];

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_24rem]">
      <div className="min-w-0 space-y-4">
        <ModelBox doc={doc} update={update} editing={editing} />
        <BeamsBox doc={doc} update={update} />
        <SystemsBox doc={doc} update={update} />

        <Box title="Paths" action={<Small onClick={() => update((d) => {
          let n = d.paths.length + 1;
          while (d.paths.some((p) => p.id === `path${n}`)) n++;
          d.paths.push({ id: `path${n}`, system: d.systems[0]?.id, topology: "open", placements: [] });
          setPathId(`path${n}`);
        })}>+ path</Small>}>
          <div className="flex flex-wrap gap-2">
            {doc.paths.map((p) => (
              <button key={p.id} type="button" onClick={() => setPathId(p.id)}
                      className={`rounded border px-2 py-1 text-sm ${p.id === pathId ? "border-slate-900 bg-slate-900 text-white" : "border-slate-300"}`}>
                {p.name || p.id} · {p.topology} · {p.placements.length}
              </button>
            ))}
          </div>
          {path && (
            <PathEditor doc={doc} path={path} vocab={vocab.data} update={update} selected={selected} onSelect={setSelected}
                        onRenamed={setPathId} onRemoved={() => setPathId(doc.paths.find((p) => p.id !== path.id)?.id ?? "")} />
          )}
        </Box>

        <ConnectionsBox doc={doc} update={update} />

        <Box title="Components not on any path" action={
          <span className="flex gap-1">
            {(["girder", "support", "mover", "fiducial", "alignment_reference"] as const).map((t) => (
              <Small key={t} onClick={() => update((d) => {
                const id = newId(d, t === "fiducial" ? "FID" : t === "girder" ? "GIR" : "SUP");
                d.components.push({ id, type: t });
                setSelected(id);
              })}>+ {t.replace("_", " ")}</Small>
            ))}
          </span>}>
          {offPath.length === 0 ? <p className="text-xs text-slate-400">None: supports, girders and fiducials that carry or locate components live here.</p> : (
            <div className="flex flex-wrap gap-1">
              {offPath.map((c) => (
                <button key={c.id} type="button" onClick={() => setSelected(c.id)}
                        className={`rounded border px-2 py-0.5 text-xs ${selected === c.id ? "border-indigo-500 bg-indigo-50" : "border-slate-300"}`}>
                  <span className="font-mono">{c.id}</span> <span className="text-slate-400">{c.type}</span>
                </button>
              ))}
            </div>
          )}
        </Box>

        <PassedThrough doc={doc} />

        <div className="flex flex-wrap items-center gap-3">
          <button type="button" disabled={!doc.model.id || save.isPending} onClick={() => save.mutate()}
                  className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:bg-slate-300">
            {save.isPending ? "Saving…" : editing ? "Save changes" : "Create model"}
          </button>
          <button type="button" disabled={!doc.model.id || check.isPending} onClick={() => check.mutate()}
                  className="rounded border border-slate-300 px-3 py-2 text-sm">Check</button>
          <button type="button" onClick={() => downloadJson(`${doc.model.id || "beam-model"}.beam.json`, tidyV2(doc, vocab.data))}
                  className="rounded border border-slate-300 px-3 py-2 text-sm">Download .beam.json</button>
          {save.isError && <span className="text-sm text-rose-700">{errorText(save.error)}</span>}
          {report && (
            <span className="text-sm text-emerald-700">
              Saved: {report.elements} components, {report.values} values{report.levels ? ` · ${report.levels.join(", ")}` : ""}.{" "}
              <button type="button" className="underline" onClick={() => navigate("/beam-model")}>Open the beam model</button>
            </span>
          )}
        </div>
        {verdict && (
          <div className={`rounded border p-3 text-sm ${verdict.ok ? "border-emerald-200 bg-emerald-50" : "border-rose-200 bg-rose-50"}`}>
            {verdict.ok ? <>Valid · levels <b>{(verdict.levels ?? []).join(", ")}</b></> : <span className="text-rose-800">{verdict.problems.join("; ")}</span>}
            {verdict.gaps && Object.keys(verdict.gaps).length > 0 && (
              <ul className="mt-1 text-xs text-slate-600">
                {Object.entries(verdict.gaps).map(([lvl, g]) => <li key={lvl}><b>{lvl}</b> needs: {g.slice(0, 8).join(", ")}{g.length > 8 ? "…" : ""}</li>)}
              </ul>
            )}
            {(verdict.warnings ?? []).length > 0 && <ul className="mt-1 list-disc pl-5 text-xs text-amber-800">{verdict.warnings!.map((w) => <li key={w}>{w}</li>)}</ul>}
          </div>
        )}
      </div>

      <aside className="xl:sticky xl:top-4 xl:self-start">
        {selected && doc.components.some((c) => c.id === selected)
          ? <ComponentPanel doc={doc} id={selected} vocab={vocab.data} update={update} onRenamed={setSelected} onClose={() => setSelected(null)} />
          : <p className="rounded border border-dashed border-slate-300 p-4 text-xs text-slate-500">
              Select a component (its row, or a chip above) to edit what a table cannot show: aliases, capabilities,
              supports and fiducials, boundaries, material, states, measurement model, parameters.
            </p>}
      </aside>
    </div>
  );
}

/** Older documents may hold systems without beam lists or paths without connections: fill the gaps once. */
function normalise(d: BeamModelV2): BeamModelV2 {
  d.systems = d.systems ?? [];
  d.beams = d.beams ?? [];
  d.paths = (d.paths ?? []).map((p) => ({ ...p, placements: p.placements ?? [], topology: p.topology ?? "open" }));
  d.connections = d.connections ?? [];
  d.components = d.components ?? [];
  return d;
}

// ------------------------------------------------------------------------- model, beams, systems

function ModelBox({ doc, update, editing }: { doc: BeamModelV2; update: Update; editing: boolean }) {
  return (
    <Box title="Model">
      <div className="grid gap-2 sm:grid-cols-5">
        <Field label="Id" value={doc.model.id} disabled={editing} placeholder="e.g. sparc-linac" onChange={(v) => update((d) => { d.model.id = v.trim(); })} />
        <Field label="Name" value={doc.model.name ?? ""} onChange={(v) => update((d) => { d.model.name = v; })} />
        <Field label="Version" value={doc.model.version ?? ""} onChange={(v) => update((d) => { d.model.version = v; })} />
        <Field label="Source" value={doc.model.source ?? ""} onChange={(v) => update((d) => { d.model.source = v; })} />
        <Field label="Simulator" value={doc.model.simulator ?? ""} placeholder="madx, xsuite, bmad…" onChange={(v) => update((d) => { d.model.simulator = v || undefined; })} />
      </div>
      <div className="mt-2 grid gap-2 sm:grid-cols-4">
        <Field label="Facility id" value={doc.facility?.id ?? ""} placeholder="e.g. dafne" onChange={(v) => update((d) => {
          if (!v.trim()) { delete d.facility; return; }
          d.facility = { ...(d.facility ?? {}), id: v.trim() };
        })} />
        <Field label="Facility name" value={doc.facility?.name ?? ""} disabled={!doc.facility} onChange={(v) => update((d) => { if (d.facility) d.facility.name = v || undefined; })} />
        <Field label="Namespace" value={doc.facility?.namespace ?? ""} disabled={!doc.facility} placeholder="dafne/accumulator" onChange={(v) => update((d) => { if (d.facility) d.facility.namespace = v || undefined; })} />
        <Field label="Site" value={doc.facility?.site ?? ""} disabled={!doc.facility} onChange={(v) => update((d) => { if (d.facility) d.facility.site = v || undefined; })} />
      </div>
    </Box>
  );
}

function num(v: string): number | undefined {
  return v.trim() === "" || Number.isNaN(Number(v)) ? undefined : Number(v);
}

function BeamsBox({ doc, update }: { doc: BeamModelV2; update: Update }) {
  return (
    <Box title="Beams" action={<Small onClick={() => update((d) => {
      let n = d.beams.length + 1;
      while (d.beams.some((b) => b.id === `beam${n}`)) n++;
      d.beams.push({ id: `beam${n}`, kind: "particle", systems: [] });
    })}>+ beam</Small>}>
      {doc.beams.length === 0 && <p className="text-xs text-slate-400">No beam: a model may describe topology alone.</p>}
      <table className="w-full text-xs">
        {doc.beams.length > 0 && (
          <thead><tr className="text-left text-slate-500"><th>Id</th><th>Kind</th><th>Species</th><th>Charge (e)</th>
            <th>Energy (GeV)</th><th>Wavelength (nm)</th><th>Other parameters</th><th /></tr></thead>
        )}
        <tbody>
          {doc.beams.map((b, i) => (
            <tr key={i} className="border-t border-slate-100">
              <td><Cell value={b.id} mono onCommit={(v) => update((d) => renameBeam(d, i, v.trim()))} /></td>
              <td>
                <select value={b.kind ?? "particle"} onChange={(e) => update((d) => { d.beams[i].kind = e.target.value as "particle" | "photon"; })}
                        className="rounded border border-slate-300 px-1 py-0.5">
                  <option value="particle">particle</option><option value="photon">photon</option>
                </select>
              </td>
              <td><Cell value={b.species ?? ""} placeholder={b.kind === "photon" ? "photon" : "electron"} onCommit={(v) => update((d) => { d.beams[i].species = v || undefined; })} narrow /></td>
              <td><Cell value={b.charge?.toString() ?? ""} onCommit={(v) => update((d) => { d.beams[i].charge = num(v); })} narrow /></td>
              <td><Cell value={b.reference_energy?.toString() ?? ""} onCommit={(v) => update((d) => { d.beams[i].reference_energy = num(v); })} narrow /></td>
              <td><Cell value={b.wavelength?.toString() ?? ""} onCommit={(v) => update((d) => { d.beams[i].wavelength = num(v); })} narrow /></td>
              <td><Cell value={kv(b.parameters ?? {})} placeholder="pulse_duration_fs=30" onCommit={(v) => update((d) => { d.beams[i].parameters = parseKv(v); })} /></td>
              <td><Icon title="remove" onClick={() => update((d) => {
                const id = d.beams[i].id;
                d.beams.splice(i, 1);
                d.systems.forEach((s) => { s.beams = (s.beams ?? []).filter((x) => x !== id); });
                d.paths.forEach((p) => { if (p.beams) p.beams = p.beams.filter((x) => x !== id); });
              })}>✕</Icon></td>
            </tr>
          ))}
        </tbody>
      </table>
    </Box>
  );
}

function renameBeam(d: BeamModelV2, i: number, v: string) {
  if (!v || d.beams.some((b, j) => j !== i && b.id === v)) return;
  const old = d.beams[i].id;
  d.beams[i].id = v;
  d.systems.forEach((s) => { s.beams = (s.beams ?? []).map((x) => (x === old ? v : x)); });
  d.paths.forEach((p) => { if (p.beams) p.beams = p.beams.map((x) => (x === old ? v : x)); });
}

function SystemsBox({ doc, update }: { doc: BeamModelV2; update: Update }) {
  return (
    <Box title="Systems" action={<Small onClick={() => update((d) => {
      let n = d.systems.length + 1;
      while (d.systems.some((s) => s.id === `system${n}`)) n++;
      d.systems.push({ id: `system${n}`, kind: "Other", beams: [] });
    })}>+ system</Small>}>
      <datalist id="system-kinds">{SYSTEM_KINDS.map((k) => <option key={k} value={k} />)}</datalist>
      {doc.systems.map((s, i) => (
        <div key={i} className="mb-2 grid gap-2 rounded border border-slate-100 p-2 sm:grid-cols-4">
          <Field label="Id" value={s.id} onChange={(v) => update((d) => {
            const old = d.systems[i].id;
            d.systems[i].id = v;
            d.paths.forEach((p) => { if (p.system === old) p.system = v; });
            d.beams.forEach((b) => { if (b.systems) b.systems = b.systems.map((x) => (x === old ? v : x)); });
          })} />
          <Field label="Name" value={s.name ?? ""} onChange={(v) => update((d) => { d.systems[i].name = v; })} />
          <label className="block text-xs text-slate-500">Kind
            <input list="system-kinds" value={s.kind ?? ""} onChange={(e) => update((d) => { d.systems[i].kind = e.target.value; })}
                   className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1 text-sm text-slate-900" />
          </label>
          <div className="text-xs text-slate-500">Beams
            <div className="mt-1 flex flex-wrap items-center gap-1">
              {doc.beams.map((b) => {
                const on = (s.beams ?? []).includes(b.id);
                return (
                  <button key={b.id} type="button" onClick={() => update((d) => {
                    const sys = d.systems[i];
                    sys.beams = on ? (sys.beams ?? []).filter((x) => x !== b.id) : [...(sys.beams ?? []), b.id];
                  })} className={`rounded-full px-2 py-0.5 ${on ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600"}`}>{b.id}</button>
                );
              })}
              {doc.systems.length > 1 && <Small danger onClick={() => update((d) => {
                const id = d.systems[i].id;
                d.systems.splice(i, 1);
                d.paths.forEach((p) => { if (p.system === id) delete p.system; });
              })}>remove</Small>}
            </div>
          </div>
        </div>
      ))}
    </Box>
  );
}

// ------------------------------------------------------------------------- one path

function PathEditor({ doc, path, vocab, update, selected, onSelect, onRenamed, onRemoved }: {
  doc: BeamModelV2; path: V2Path; vocab?: BeamVocabulary; update: Update; selected: string | null;
  onSelect: (id: string) => void; onRenamed: (id: string) => void; onRemoved: () => void;
}) {
  const byId = useMemo(() => new Map(doc.components.map((c) => [c.id, c])), [doc.components]);
  const pls = placements(path);
  const pids = placementIds(path);
  const ds = pathDataset(doc, path.id);
  const [adding, setAdding] = useState("");
  const withPath = (fn: (p: V2Path, d: BeamModelV2) => void) => update((d) => fn(d.paths.find((x) => x.id === path.id)!, d));
  const otherPaths = (cid: string) => doc.paths.filter((p) => p.id !== path.id && placements(p).some((pl) => pl.component === cid)).map((p) => p.name || p.id);

  const setValue = (pid: string, key: string, raw: string) => update((d) => {
    const dataset = ensureDataset(d, path.id);
    const v = (dataset.values![pid] = dataset.values![pid] ?? {});
    const n = num(raw);
    if (key === "s") v.s = n ?? null;
    else {
      v.physics = { ...(v.physics ?? {}) };
      if (n === undefined) delete v.physics[key];
      else v.physics[key] = n;
    }
  });
  const insert = (after: number, component: string, create?: string) => update((d) => {
    const p = d.paths.find((x) => x.id === path.id)!;
    let cid = component;
    if (create) {
      cid = newId(d);
      d.components.push({ id: cid, type: create });
    }
    const list = placements(p);
    list.splice(after + 1, 0, { component: cid });
    setPlacements(p, list);
    onSelect(cid);
  });
  const move = (i: number, by: number) => withPath((p) => {
    const list = placements(p);
    const j = i + by;
    if (j < 0 || j >= list.length) return;
    [list[i], list[j]] = [list[j], list[i]];
    setPlacements(p, list);
  });
  const remove = (i: number) => update((d) => {
    const p = d.paths.find((x) => x.id === path.id)!;
    const list = placements(p);
    const pid = placementIds(p)[i];
    const [gone] = list.splice(i, 1);
    setPlacements(p, list);
    (d.datasets ?? []).filter((x) => x.path === path.id).forEach((x) => { if (x.values) delete x.values[pid]; });
    if (p.reference === pid || p.reference === gone.component) delete p.reference;
    const stillPlaced = d.paths.some((q) => placements(q).some((pl) => pl.component === gone.component));
    const referenced = d.components.some((c) => c.mounted_on === gone.component || c.contained_in === gone.component
      || (c.fiducials ?? []).includes(gone.component));
    d.connections = d.connections.filter((c) => !((c.from.path === path.id && (c.from.component === pid || c.from.component === gone.component))
      || (c.to.path === path.id && (c.to.component === pid || c.to.component === gone.component))));
    if (!stillPlaced && !referenced) {
      d.components = d.components.filter((c) => c.id !== gone.component);
      (d.datasets ?? []).forEach((x) => { if (x.values) delete x.values[gone.component]; });
    }
  });
  const editComponent = (id: string, fn: (c: V2Component) => void) => update((d) => { fn(d.components.find((c) => c.id === id)!); });

  return (
    <div className="mt-3 space-y-3">
      <div className="grid gap-2 sm:grid-cols-6">
        <Field label="Path id" value={path.id} onChange={(v) => {
          if (!v || doc.paths.some((p) => p.id === v)) return;
          update((d) => renamePath(d, path.id, v));
          onRenamed(v);
        }} />
        <Field label="Name" value={path.name ?? ""} onChange={(v) => withPath((p) => { p.name = v; })} />
        <Select label="System" value={path.system ?? ""} options={["", ...doc.systems.map((s) => s.id)]} onChange={(v) => withPath((p) => { if (v) p.system = v; else delete p.system; })} />
        <Select label="Topology" value={path.topology} options={["open", "closed"]} onChange={(v) => withPath((p) => { p.topology = v as "open" | "closed"; })} />
        <Field label="Length (m)" value={path.length?.toString() ?? ""} onChange={(v) => withPath((p) => { const n = num(v); if (n === undefined) delete p.length; else p.length = n; })} />
        <Select label="Reference (s = 0)" value={path.reference ?? ""} options={["", ...pids]} onChange={(v) => withPath((p) => { if (v) p.reference = v; else delete p.reference; })} />
      </div>
      {doc.beams.length > 0 && (
        <div className="flex flex-wrap items-center gap-1 text-xs text-slate-500">Carries:
          {doc.beams.map((b) => {
            const on = (path.beams ?? []).includes(b.id);
            return <button key={b.id} type="button" onClick={() => withPath((p) => { p.beams = on ? (p.beams ?? []).filter((x) => x !== b.id) : [...(p.beams ?? []), b.id]; })}
                           className={`rounded-full px-2 py-0.5 ${on ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600"}`}>{b.id}</button>;
          })}
        </div>
      )}
      <div className="text-xs text-slate-500">
        Values go into dataset <b>{ds?.name ?? ds?.id ?? `${path.id}-design`}</b> ({ds?.kind ?? "design"}); other datasets are kept as they are.
        {doc.paths.length > 1 && <> <Small danger onClick={() => {
          update((d) => {
            const p = d.paths.find((x) => x.id === path.id)!;
            const mine = new Set(placements(p).map((pl) => pl.component));
            d.paths = d.paths.filter((x) => x.id !== path.id);
            const still = new Set(d.paths.flatMap((q) => placements(q).map((pl) => pl.component)));
            d.components = d.components.filter((c) => !mine.has(c.id) || still.has(c.id));
            d.datasets = (d.datasets ?? []).filter((x) => x.path !== path.id);
            d.connections = d.connections.filter((c) => c.from.path !== path.id && c.to.path !== path.id);
          });
          onRemoved();
        }}>remove this path</Small></>}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-slate-500">
              <th className="w-6">#</th><th>Component</th><th>Name</th><th>Type</th><th>s (m)</th><th>Length (m)</th>
              <th>Strength</th><th>Observes</th><th title="passed backwards on this path">Rev</th><th>Also on</th><th />
            </tr>
          </thead>
          <tbody>
            {pls.map((pl, i) => {
              const c = byId.get(pl.component);
              const pid = pids[i];
              const v = ds?.values?.[pid] ?? {};
              const strength = c?.type ? STRENGTH[c.type] : undefined;
              const diagnostic = c ? capsOf(vocab, c).includes("diagnostic") : false;
              const also = otherPaths(pl.component);
              return (
                <tr key={`${pid}-${i}`} onClick={() => onSelect(pl.component)}
                    className={`cursor-pointer border-t border-slate-100 align-top ${selected === pl.component ? "bg-indigo-50" : "hover:bg-slate-50"}`}>
                  <td className="py-1 text-slate-400">{i + 1}</td>
                  <td><Cell value={pl.component} mono onCommit={(x) => update((d) => renameComponent(d, pl.component, x.trim()))} />
                    {pid !== pl.component && <div className="text-[10px] text-slate-400">{pid}</div>}</td>
                  <td><Cell value={c?.name ?? ""} onCommit={(x) => editComponent(pl.component, (el) => { el.name = x; })} /></td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <TypeSelect vocab={vocab} value={c?.type ?? ""} onChange={(t) => editComponent(pl.component, (el) => {
                      el.type = t;
                      delete el.capabilities;
                    })} />
                  </td>
                  <td><Cell value={v.s?.toString() ?? ""} onCommit={(x) => setValue(pid, "s", x)} narrow /></td>
                  <td><Cell value={(v.physics?.length as number | undefined)?.toString() ?? ""} onCommit={(x) => setValue(pid, "length", x)} narrow /></td>
                  <td>{strength ? (
                    <span className="flex items-center gap-1"><span className="text-slate-400">{strength}</span>
                      <Cell value={(v.physics?.[strength] as number | undefined)?.toString() ?? ""} onCommit={(x) => setValue(pid, strength, x)} narrow /></span>
                  ) : <span className="text-slate-300">—</span>}</td>
                  <td>{diagnostic ? (
                    <Cell value={(c?.observes ?? []).join(", ")} placeholder="beam.position.x, beam.position.y"
                          onCommit={(x) => editComponent(pl.component, (el) => { el.observes = x.split(",").map((q) => q.trim()).filter(Boolean); })} />
                  ) : <span className="text-slate-300">—</span>}</td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <input type="checkbox" checked={!!pl.reversed} onChange={(e) => withPath((p) => {
                      const list = placements(p);
                      list[i] = { ...list[i], reversed: e.target.checked || undefined };
                      setPlacements(p, list);
                    })} />
                  </td>
                  <td className="text-[11px] text-violet-700">{also.join(", ")}</td>
                  <td className="whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                    <Icon onClick={() => move(i, -1)} title="move up">↑</Icon>
                    <Icon onClick={() => move(i, 1)} title="move down">↓</Icon>
                    <Icon onClick={() => insert(i, "", "drift")} title="add a new component below">+</Icon>
                    <Icon onClick={() => remove(i)} title="remove from this path (the component goes when it is on no other path)">✕</Icon>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Small onClick={() => insert(pls.length - 1, "", "drift")}>+ new component at the end</Small>
        <span className="text-xs text-slate-500">or place an existing one (shared with another path):</span>
        <select value={adding} onChange={(e) => setAdding(e.target.value)} className="rounded border border-slate-300 px-1 py-0.5 text-xs">
          <option value="">choose…</option>
          {doc.components.map((c) => <option key={c.id} value={c.id}>{c.id}{c.type ? ` (${c.type})` : ""}</option>)}
        </select>
        <Small onClick={() => { if (adding) { insert(pls.length - 1, adding); setAdding(""); } }}>place at the end</Small>
      </div>
      <p className="text-xs text-slate-500">
        Order is beam order: each placement follows the one above it{path.topology === "closed" ? ", and the last closes to the first" : ""}.
        A component on several paths (an interaction region) keeps one identity; tick <i>Rev</i> where a beam passes it backwards.
        How paths join is under Connections. Capabilities follow the type unless set in the component's panel.
      </p>
    </div>
  );
}

function renamePath(d: BeamModelV2, old: string, v: string) {
  d.paths.find((p) => p.id === old)!.id = v;
  (d.datasets ?? []).forEach((ds) => {
    if (ds.path === old) ds.path = v;
    ((ds.fields as { path?: string }[] | undefined) ?? []).forEach((f) => { if (f.path === old) f.path = v; });
    ((ds.boundaries as V2Boundary[] | undefined) ?? []).forEach((b) => { if (b.path === old) b.path = v; });
  });
  d.connections.forEach((c) => { if (c.from.path === old) c.from.path = v; if (c.to.path === old) c.to.path = v; });
  (d.boundaries ?? []).forEach((b) => { if (b.path === old) b.path = v; });
}

function renameComponent(d: BeamModelV2, old: string, v: string) {
  if (!v || v === old || d.components.some((c) => c.id === v)) return;
  d.components.find((c) => c.id === old)!.id = v;
  const swap = (x?: string) => (x === old ? v : x?.startsWith(`${old}#`) ? `${v}${x.slice(old.length)}` : x);
  d.paths.forEach((p) => {
    setPlacements(p, placements(p).map((pl) => ({ ...pl, component: pl.component === old ? v : pl.component, id: swap(pl.id) })));
    p.reference = swap(p.reference);
    if (!p.reference) delete p.reference;
  });
  d.connections.forEach((c) => { c.from.component = swap(c.from.component); c.to.component = swap(c.to.component); });
  d.components.forEach((c) => {
    if (c.mounted_on === old) c.mounted_on = v;
    if (c.contained_in === old) c.contained_in = v;
    if (c.fiducials) c.fiducials = c.fiducials.map((f) => (f === old ? v : f));
    (c.boundaries ?? []).forEach((b) => { if (b.component === old) b.component = v; });
  });
  (d.boundaries ?? []).forEach((b) => { if (b.component === old) b.component = v; });
  (d.datasets ?? []).forEach((ds) => {
    for (const k of Object.keys(ds.values ?? {})) {
      const nk = swap(k)!;
      if (nk !== k) { ds.values![nk] = ds.values![k]; delete ds.values![k]; }
    }
  });
  ((d.external_bindings as { component: string }[] | undefined) ?? []).forEach((b) => { if (b.component === old) b.component = v; });
}

// ------------------------------------------------------------------------- connections

function ConnectionsBox({ doc, update }: { doc: BeamModelV2; update: Update }) {
  const opts = (pathId: string) => {
    const p = doc.paths.find((x) => x.id === pathId);
    return p ? placementIds(p) : [];
  };
  return (
    <Box title="Connections between paths" action={doc.paths.length > 1 ? <Small onClick={() => update((d) => {
      d.connections.push({ kind: "branch", from: { path: d.paths[0].id }, to: { path: d.paths[1].id } });
    })}>+ connection</Small> : undefined}>
      {doc.connections.length === 0 ? (
        <p className="text-xs text-slate-400">
          None. A <b>branch</b> leaves a component (a septum, a beam splitter) for the start of another path; a <b>merge</b>
          brings a path's end into a component of another (injection); <b>continue</b> joins a path's end to the next one's start.
        </p>
      ) : (
        <table className="w-full text-xs">
          <thead><tr className="text-left text-slate-500"><th>Kind</th><th>From path</th><th>From</th><th /><th>To path</th><th>To</th><th /></tr></thead>
          <tbody>
            {doc.connections.map((c, i) => (
              <tr key={i} className="border-t border-slate-100">
                <td><select value={c.kind} onChange={(e) => update((d) => { d.connections[i].kind = e.target.value as "branch" | "merge" | "continue"; })} className="rounded border border-slate-300 px-1 py-0.5">
                  <option value="branch">branch</option><option value="merge">merge</option><option value="continue">continue</option></select></td>
                <td><PathPick doc={doc} value={c.from.path} onChange={(v) => update((d) => { d.connections[i].from = { path: v }; })} /></td>
                <td><select value={c.from.component ?? ""} onChange={(e) => update((d) => { d.connections[i].from.component = e.target.value || undefined; })} className="rounded border border-slate-300 px-1 py-0.5">
                  <option value="">its end</option>{opts(c.from.path).map((o) => <option key={o} value={o}>{o}</option>)}</select></td>
                <td className="text-slate-400">→</td>
                <td><PathPick doc={doc} value={c.to.path} onChange={(v) => update((d) => { d.connections[i].to = { path: v }; })} /></td>
                <td><select value={c.to.component ?? ""} onChange={(e) => update((d) => { d.connections[i].to.component = e.target.value || undefined; })} className="rounded border border-slate-300 px-1 py-0.5">
                  <option value="">its start</option>{opts(c.to.path).map((o) => <option key={o} value={o}>{o}</option>)}</select></td>
                <td><Icon title="remove" onClick={() => update((d) => { d.connections.splice(i, 1); })}>✕</Icon></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Box>
  );
}

function PathPick({ doc, value, onChange }: { doc: BeamModelV2; value: string; onChange: (v: string) => void }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className="rounded border border-slate-300 px-1 py-0.5">
      {doc.paths.map((p) => <option key={p.id} value={p.id}>{p.name || p.id}</option>)}
    </select>
  );
}

// ------------------------------------------------------------------------- one component

function ComponentPanel({ doc, id, vocab, update, onRenamed, onClose }: {
  doc: BeamModelV2; id: string; vocab?: BeamVocabulary; update: Update; onRenamed: (id: string) => void; onClose: () => void;
}) {
  const c = doc.components.find((x) => x.id === id)!;
  const edit = (fn: (el: V2Component) => void) => update((d) => { fn(d.components.find((x) => x.id === id)!); });
  const defaults = vocab?.families[familyOf(vocab, c.type)]?.[c.type ?? ""] ?? [];
  const caps = c.capabilities ?? defaults;
  const fam = familyOf(vocab, c.type);
  const supports = doc.components.filter((x) => x.id !== id && capsOf(vocab, x).includes("mechanical_support"));
  const fiducials = doc.components.filter((x) => x.id !== id && capsOf(vocab, x).includes("survey_reference"));
  const typeStates = c.type ? vocab?.states[c.type] : undefined;
  const stateNames = (c.states?.states ?? []).map((s) => s.name);
  // Boundaries may name a state of the type's default set when the component declares none of its own.
  const boundaryStates = stateNames.length ? stateNames : Object.keys(typeStates ?? {});
  const placedOn = doc.paths.filter((p) => placements(p).some((pl) => pl.component === id)).map((p) => p.name || p.id);

  return (
    <div className="space-y-3 rounded border border-slate-200 bg-white p-3 text-xs">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-mono text-sm font-semibold text-slate-900">{c.id}</div>
          <div className="text-slate-500">{c.type ?? "no type"} · {fam}{placedOn.length ? ` · on ${placedOn.join(", ")}` : " · on no path"}</div>
        </div>
        <button type="button" onClick={onClose} className="text-slate-400 hover:text-slate-700">✕</button>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Id" value={c.id} onChange={() => undefined} disabled />
        <label className="block text-xs text-slate-500">Rename to
          <Cell value="" placeholder="new id" onCommit={(v) => { const n = v.trim(); if (n && !doc.components.some((x) => x.id === n)) { update((d) => renameComponent(d, id, n)); onRenamed(n); } }} />
        </label>
        <Field label="Name" value={c.name ?? ""} onChange={(v) => edit((el) => { el.name = v || undefined; })} />
        <label className="block text-xs text-slate-500">Type
          <div className="mt-0.5"><TypeSelect vocab={vocab} value={c.type ?? ""} onChange={(t) => edit((el) => { el.type = t; delete el.capabilities; })} /></div>
        </label>
        <Field label="Model family" value={c.family ?? ""} placeholder="QF" onChange={(v) => edit((el) => { el.family = v || undefined; })} />
        <Select label="Definition" value={c.definition ?? ""} options={["", ...(doc.definitions ?? []).map((x) => x.id)]} onChange={(v) => edit((el) => { el.definition = v || undefined; })} />
      </div>
      <Field label="Aliases (asset tags, control names — evidence for asset matching)" value={(c.aliases ?? []).join(", ")}
             onChange={(v) => edit((el) => { el.aliases = v.split(",").map((x) => x.trim()).filter(Boolean); if (!el.aliases.length) delete el.aliases; })} />

      <Group title="Capabilities" hint={c.capabilities ? "set for this component" : "the type's defaults"}
             action={c.capabilities ? <button type="button" className="text-indigo-700 hover:underline" onClick={() => edit((el) => { delete el.capabilities; })}>use the type's</button> : undefined}>
        <div className="flex flex-wrap gap-1">
          {Object.keys(vocab?.capabilities ?? {}).map((k) => {
            const on = caps.includes(k);
            return (
              <button key={k} type="button" title={vocab?.capabilities[k]} onClick={() => edit((el) => {
                const cur = el.capabilities ?? [...defaults];
                el.capabilities = on ? cur.filter((x) => x !== k) : [...cur, k];
              })} className={`rounded px-1.5 py-0.5 text-[11px] ${on ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-500"}`}>{k}</button>
            );
          })}
        </div>
      </Group>

      {caps.includes("diagnostic") && (
        <Group title="Diagnostic">
          <Field label="Observes" value={(c.observes ?? []).join(", ")} placeholder="beam.position.x, beam.position.y"
                 onChange={(v) => edit((el) => { el.observes = v.split(",").map((x) => x.trim()).filter(Boolean); })} />
          <datalist id="observables">{Object.keys(vocab?.observables ?? {}).map((q) => <option key={q} value={q} />)}</datalist>
          <div className="mt-1 grid grid-cols-2 gap-2">
            <Select label="Measurement model" value={c.measurement_model?.type ?? ""} options={["", ...(vocab?.measurement_models ?? [])]}
                    onChange={(v) => edit((el) => { if (v) el.measurement_model = { ...(el.measurement_model ?? {}), type: v, observables: el.measurement_model?.observables ?? el.observes ?? [] }; else delete el.measurement_model; })} />
            {c.measurement_model && <Field label="Derives" value={(c.measurement_model.observables ?? []).join(", ")}
                                           onChange={(v) => edit((el) => { el.measurement_model!.observables = v.split(",").map((x) => x.trim()).filter(Boolean); })} />}
          </div>
        </Group>
      )}

      <Group title="Supports and alignment">
        <div className="grid grid-cols-2 gap-2">
          <Select label="Mounted on" value={c.mounted_on ?? ""} options={["", ...supports.map((x) => x.id)]} onChange={(v) => edit((el) => { el.mounted_on = v || undefined; })} />
          <Select label="Contained in" value={c.contained_in ?? ""} options={["", ...doc.components.filter((x) => x.id !== id).map((x) => x.id)]} onChange={(v) => edit((el) => { el.contained_in = v || undefined; })} />
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-1 text-slate-500">Fiducials:
          {fiducials.length === 0 && <span className="text-slate-400">none in the model</span>}
          {fiducials.map((f) => {
            const on = (c.fiducials ?? []).includes(f.id);
            return <button key={f.id} type="button" onClick={() => edit((el) => { el.fiducials = on ? (el.fiducials ?? []).filter((x) => x !== f.id) : [...(el.fiducials ?? []), f.id]; })}
                           className={`rounded-full px-2 py-0.5 ${on ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600"}`}>{f.id}</button>;
          })}
        </div>
        <Field label="Length (m, of the object)" value={c.geometry?.length?.toString() ?? ""} onChange={(v) => edit((el) => {
          const n = num(v);
          el.geometry = { ...(el.geometry ?? {}) };
          if (n === undefined) delete el.geometry.length; else el.geometry.length = n;
          if (!Object.keys(el.geometry).length) delete el.geometry;
        })} />
      </Group>

      <BoundariesGroup c={c} vocab={vocab} stateNames={boundaryStates} edit={edit} />

      <Group title="Material" action={!c.material ? <button type="button" className="text-indigo-700 hover:underline" onClick={() => edit((el) => { el.material = { material: "" }; })}>add</button>
        : <button type="button" className="text-rose-700 hover:underline" onClick={() => edit((el) => { delete el.material; })}>remove</button>}>
        {c.material && (
          <div className="grid grid-cols-2 gap-2">
            <Field label="Material" value={c.material.material} placeholder="YAG:Ce, tungsten…" onChange={(v) => edit((el) => { el.material!.material = v; })} />
            <Field label="Thickness (m)" value={c.material.thickness?.toString() ?? ""} onChange={(v) => edit((el) => { el.material!.thickness = num(v); })} />
            <Field label="Density (g/cm³)" value={c.material.density?.toString() ?? ""} onChange={(v) => edit((el) => { el.material!.density = num(v); })} />
            <Field label="Radiation length (m)" value={c.material.radiation_length?.toString() ?? ""} onChange={(v) => edit((el) => { el.material!.radiation_length = num(v); })} />
          </div>
        )}
      </Group>

      <Group title="States" hint="what each means for the beam; never the live state"
             action={!c.states ? (typeStates
               ? <button type="button" className="text-indigo-700 hover:underline" onClick={() => edit((el) => {
                 el.states = { states: Object.entries(typeStates).map(([name, meaning]) => ({ name, meaning })), default: Object.keys(typeStates)[0] };
               })}>use the type's</button>
               : <button type="button" className="text-indigo-700 hover:underline" onClick={() => edit((el) => { el.states = { states: [{ name: "ON" }, { name: "OFF" }], default: "ON" }; })}>add</button>)
               : <button type="button" className="text-rose-700 hover:underline" onClick={() => edit((el) => { delete el.states; })}>remove</button>}>
        {c.states && (
          <div className="grid grid-cols-2 gap-2">
            <Field label="States" value={stateNames.join(", ")} onChange={(v) => edit((el) => {
              const names = v.split(",").map((x) => x.trim().toUpperCase()).filter(Boolean);
              const old = new Map((el.states!.states ?? []).map((s) => [s.name, s]));
              el.states!.states = names.map((n) => old.get(n) ?? { name: n });
              if (el.states!.default && !names.includes(el.states!.default)) el.states!.default = names[0];
            })} />
            <Select label="Assumed (normal operation)" value={c.states.default ?? ""} options={["", ...stateNames]} onChange={(v) => edit((el) => { el.states!.default = v || undefined; })} />
          </div>
        )}
      </Group>

      <Group title="Parameters" hint="normalised, not configuration-dependent (those go in a dataset)">
        <Cell value={kv(c.parameters ?? {})} placeholder="length=0.3, gradient=12" onCommit={(v) => edit((el) => { el.parameters = parseKv(v); if (!Object.keys(el.parameters).length) delete el.parameters; })} />
      </Group>
      <Field label="Description" value={c.description ?? ""} onChange={(v) => edit((el) => { el.description = v || undefined; })} />
      {c.native && (
        <p className="text-[11px] text-slate-400">Native: {c.native.format} {c.native.type} {c.native.name ? `“${c.native.name}”` : ""} {c.native.file ? `· ${c.native.file}` : ""} — kept as it came.</p>
      )}
    </div>
  );
}

const SHAPE_FIELDS: Record<string, [keyof V2Profile, string][]> = {
  circle: [["radius", "radius"]],
  ellipse: [["semi_axis_x", "semi-axis x"], ["semi_axis_y", "semi-axis y"]],
  rectangle: [["half_width_x", "half width x"], ["half_height_y", "half height y"]],
  racetrack: [["half_width_x", "half width x"], ["half_height_y", "half height y"], ["corner_radius", "corner radius"]],
  polygon: [], custom: [],
};

function BoundariesGroup({ c, vocab, stateNames, edit }: {
  c: V2Component; vocab?: BeamVocabulary; stateNames: string[]; edit: (fn: (el: V2Component) => void) => void;
}) {
  const list = c.boundaries ?? [];
  const setB = (i: number, fn: (b: V2Boundary) => void) => edit((el) => { fn(el.boundaries![i]); });
  return (
    <Group title="Beam boundaries" hint="the space this component leaves the beam, in metres from the axis"
           action={<button type="button" className="text-indigo-700 hover:underline" onClick={() => edit((el) => {
             el.boundaries = [...(el.boundaries ?? []), { profile: { shape: "circle", radius: 0.02 } }];
           })}>+ boundary</button>}>
      {list.map((b, i) => (
        <div key={i} className="mb-2 rounded border border-slate-100 p-2">
          <div className="grid grid-cols-3 gap-2">
            <Select label="Shape" value={b.profile.shape} options={vocab?.shapes ?? ["circle", "ellipse", "rectangle", "racetrack", "polygon"]}
                    onChange={(v) => setB(i, (x) => { x.profile = { shape: v as V2Profile["shape"] }; })} />
            {SHAPE_FIELDS[b.profile.shape]?.map(([k, label]) => (
              <Field key={k} label={`${label} (m)`} value={(b.profile[k] as number | undefined)?.toString() ?? ""}
                     onChange={(v) => setB(i, (x) => { (x.profile as Record<string, unknown>)[k] = num(v); })} />
            ))}
            {(b.profile.shape === "polygon" || b.profile.shape === "custom") && (
              <label className="col-span-2 block text-xs text-slate-500">Points (x y; x y; …)
                <Cell value={(b.profile.points ?? []).map((p) => p.join(" ")).join("; ")} placeholder="0.02 0.01; -0.02 0.01; -0.02 -0.01; 0.02 -0.01"
                      onCommit={(v) => setB(i, (x) => { x.profile.points = v.split(";").map((p) => p.trim().split(/[\s,]+/).map(Number)).filter((p) => p.length === 2 && p.every((n) => !Number.isNaN(n))); })} />
              </label>
            )}
            <Field label="Offset x" value={b.profile.offset_x?.toString() ?? ""} onChange={(v) => setB(i, (x) => { x.profile.offset_x = num(v); })} />
            <Field label="Offset y" value={b.profile.offset_y?.toString() ?? ""} onChange={(v) => setB(i, (x) => { x.profile.offset_y = num(v); })} />
            <Select label="Only when" value={b.when_state ?? ""} options={["", ...new Set([...stateNames, ...(b.when_state ? [b.when_state] : [])])]}
                    onChange={(v) => setB(i, (x) => { x.when_state = v || undefined; })} />
            <Field label="From (m, from entry)" value={b.s_start?.toString() ?? ""} onChange={(v) => setB(i, (x) => { x.s_start = num(v); })} />
            <Field label="To (m)" value={b.s_end?.toString() ?? ""} onChange={(v) => setB(i, (x) => { x.s_end = num(v); })} />
            <div className="flex items-end"><button type="button" className="text-rose-700 hover:underline" onClick={() => edit((el) => {
              el.boundaries!.splice(i, 1);
              if (!el.boundaries!.length) delete el.boundaries;
            })}>remove</button></div>
          </div>
        </div>
      ))}
    </Group>
  );
}

function TypeSelect({ vocab, value, onChange }: { vocab?: BeamVocabulary; value: string; onChange: (v: string) => void }) {
  const known = vocab ? Object.values(vocab.families).some((ts) => value in ts) : true;
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className="max-w-[11rem] rounded border border-slate-300 px-1 py-0.5 text-xs">
      {!value && <option value="">—</option>}
      {!known && value && <option value={value}>{value} (not in the vocabulary)</option>}
      {Object.entries(vocab?.families ?? {}).map(([fam, ts]) => (
        <optgroup key={fam} label={fam.replace(/_/g, " ")}>
          {Object.keys(ts).map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
        </optgroup>
      ))}
    </select>
  );
}

/** What the editor keeps without showing: listed, so a person knows it is there and travels with a save. */
function PassedThrough({ doc }: { doc: BeamModelV2 }) {
  const items: string[] = [];
  if ((doc.definitions ?? []).length) items.push(`${doc.definitions!.length} definitions`);
  const datasets = doc.datasets ?? [];
  if (datasets.length) items.push(`${datasets.length} datasets (${datasets.map((d) => d.kind ?? "design").join(", ")})`);
  if ((doc.boundaries ?? []).length) items.push(`${doc.boundaries!.length} boundaries along paths`);
  if ((doc.external_bindings ?? []).length) items.push(`${doc.external_bindings!.length} asset bindings`);
  if ((doc.observables ?? []).length) items.push(`${doc.observables!.length} declared observables`);
  if (!items.length) return null;
  return <p className="text-xs text-slate-500">Kept as they are and saved with the model: {items.join(" · ")}.</p>;
}

// ------------------------------------------------------------------------- small pieces

export function downloadJson(name: string, data: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 1)], { type: "application/json" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

function kv(o: Record<string, unknown>): string {
  return Object.entries(o ?? {}).map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : v}`).join(", ");
}

function parseKv(s: string): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const part of s.split(",")) {
    const [k, ...rest] = part.split("=");
    if (!k?.trim() || !rest.length) continue;
    const raw = rest.join("=").trim();
    out[k.trim()] = raw !== "" && !Number.isNaN(Number(raw)) ? Number(raw) : raw;
  }
  return out;
}

function Box({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded border border-slate-200 bg-white p-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function Group({ title, hint, action, children }: { title: string; hint?: string; action?: React.ReactNode; children?: React.ReactNode }) {
  return (
    <div className="border-t border-slate-100 pt-2">
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{title}
          {hint && <span className="ml-1 font-normal normal-case tracking-normal text-slate-400">· {hint}</span>}</span>
        {action}
      </div>
      {children}
    </div>
  );
}

function Field({ label, value, onChange, placeholder, disabled }: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string; disabled?: boolean;
}) {
  return (
    <label className="block text-xs text-slate-500">
      {label}
      <input value={value} placeholder={placeholder} disabled={disabled} onChange={(e) => onChange(e.target.value)}
             className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1 text-sm text-slate-900 disabled:bg-slate-50" />
    </label>
  );
}

function Select({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <label className="block text-xs text-slate-500">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)} className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1 text-sm text-slate-900">
        {options.map((o) => <option key={o} value={o}>{o || "—"}</option>)}
      </select>
    </label>
  );
}

/** Edited in place and committed on blur or Enter, so a rename does not happen per keystroke. */
function Cell({ value, onCommit, mono, narrow, placeholder }: {
  value: string; onCommit: (v: string) => void; mono?: boolean; narrow?: boolean; placeholder?: string;
}) {
  const [v, setV] = useState(value);
  useEffect(() => setV(value), [value]);
  return (
    <input value={v} placeholder={placeholder} onChange={(e) => setV(e.target.value)} onClick={(e) => e.stopPropagation()}
           onBlur={() => v !== value && onCommit(v)} onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
           className={`rounded border border-slate-200 px-1 py-0.5 ${mono ? "font-mono" : ""} ${narrow ? "w-20" : "w-full min-w-[7rem]"}`} />
  );
}

function Small({ children, onClick, danger }: { children: React.ReactNode; onClick: () => void; danger?: boolean }) {
  return (
    <button type="button" onClick={onClick}
            className={`rounded border px-2 py-0.5 text-xs ${danger ? "border-rose-200 text-rose-700 hover:bg-rose-50" : "border-slate-300 text-slate-700 hover:bg-slate-50"}`}>
      {children}
    </button>
  );
}

function Icon({ children, onClick, title }: { children: React.ReactNode; onClick: () => void; title: string }) {
  return <button type="button" title={title} onClick={onClick} className="px-1 text-slate-500 hover:text-slate-900">{children}</button>;
}
