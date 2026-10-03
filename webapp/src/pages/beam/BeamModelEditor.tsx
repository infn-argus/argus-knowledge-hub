import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, beamModelApi } from "../../api/client";
import type {
  BeamConversionReport,
  BeamImportReport, BeamModelCheck, CanonicalBeamModel, CanonicalDataset, CanonicalElement, CanonicalPath,
} from "../../api/types";

/** Bringing beam models into ARGUS (docs/beam-model.md): upload canonical JSON files — several models at once,
 *  checked before anything is written — or write one here. The editor writes the same canonical document an
 *  import reads, so editing a model is exporting it, changing it and importing it again: its history stays. */

const KINDS = ["drift", "dipole", "quadrupole", "sextupole", "corrector", "kicker", "septum", "rf_cavity", "bpm",
  "screen", "generic_monitor", "source", "dump", "mirror", "lens", "beam_splitter", "solenoid", "collimator",
  "undulator", "generic"];
const DIAGNOSTICS = new Set(["bpm", "screen", "generic_monitor"]);
const SYSTEM_KINDS = ["Storage ring", "Synchrotron", "Accumulator", "Linac", "Transfer line", "Laser transport",
  "FEL line", "Other"];
const OBSERVABLES = ["beam.position.x", "beam.position.y", "beam.size.x", "beam.size.y", "beam.intensity",
  "beam.energy", "beam.loss", "optical.power", "optical.profile"];
/** The strength a kind is usually given, offered as a column. */
const STRENGTH: Record<string, string> = {
  quadrupole: "k1", sextupole: "k2", dipole: "angle", corrector: "kick", kicker: "kick", rf_cavity: "voltage",
  lens: "focal_length", beam_splitter: "split_ratio", solenoid: "ks",
};

function emptyModel(): CanonicalBeamModel {
  return {
    format: "argus.beam-model/1",
    model: { id: "", name: "", source: "argus-editor", version: "1" },
    systems: [{ id: "main", name: "", kind: "Linac", beams: [{ id: "beam", kind: "particle", parameters: { species: "electron" } }] }],
    paths: [{ id: "line", name: "", system: "main", topology: "open", elements: [] }],
    elements: [],
    observables: [],
    datasets: [],
  };
}

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));

function download(name: string, data: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 1)], { type: "application/json" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}
export { download as downloadJson };

function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    const b = e.body as { detail?: unknown } | undefined;
    const d = b?.detail as { problems?: string[]; models?: BeamModelCheck[] } | string | undefined;
    if (typeof d === "string") return d;
    if (d?.problems) return d.problems.join("; ");
    if (d?.models) return d.models.filter((m) => !m.ok).map((m) => `${m.model ?? `#${m.index + 1}`}: ${m.problems.join("; ")}`).join(" · ");
    return e.message;
  }
  return e instanceof Error ? e.message : String(e);
}

export function BeamModelEditorPage() {
  const { modelId } = useParams();
  const [tab, setTab] = useState<"upload" | "edit">(modelId ? "edit" : "upload");
  const existing = useQuery({
    queryKey: ["beam-model-export", modelId],
    queryFn: () => beamModelApi.exportModel(modelId!),
    enabled: !!modelId,
  });
  const [seed, setSeed] = useState<CanonicalBeamModel | null>(null);
  useEffect(() => {
    if (existing.data) setSeed(existing.data);
  }, [existing.data]);

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">{modelId ? `Edit beam model ${modelId}` : "New beam model"}</h1>
          <p className="mt-1 text-sm text-slate-500">
            Machine models in the canonical <code>argus.beam-model/1</code> format, uploaded as they are or converted
            from MAD-X, TFS and Elegant files (other simulators through the Accelerator Model Toolbox). Positions,
            topology, diagnostics and datasets — never the hardware, which is installed at the positions afterwards.
          </p>
        </div>
        <Link to="/beam-model" className="text-sm text-indigo-700 hover:underline">← Beam model</Link>
      </div>
      {!modelId && (
        <div className="flex rounded border border-slate-300 text-sm w-fit">
          {([["upload", "Upload files"], ["edit", "Write a model"]] as const).map(([k, label]) => (
            <button key={k} type="button" onClick={() => setTab(k)}
                    className={`px-3 py-1.5 ${tab === k ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-50"}`}>{label}</button>
          ))}
        </div>
      )}
      {tab === "upload" && <Upload onEdit={(m) => { setSeed(m); setTab("edit"); }} />}
      {tab === "edit" && (modelId && !seed ? <p className="text-sm text-slate-400">Loading the model…</p>
        : <Editor key={seed?.model.id ?? "new"} initial={seed ?? emptyModel()} editing={!!modelId} />)}
    </div>
  );
}

// ------------------------------------------------------------------------- upload

interface ConvertOptions { topology: string; keep_markers: boolean; system_kind: string }
interface UploadedFile { name: string; models: CanonicalBeamModel[]; error?: string; via?: string; report?: BeamConversionReport }

function Upload({ onEdit }: { onEdit: (m: CanonicalBeamModel) => void }) {
  const qc = useQueryClient();
  const [raw, setRaw] = useState<{ name: string; text: string }[]>([]);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [opts, setOpts] = useState<ConvertOptions>({ topology: "auto", keep_markers: false, system_kind: "" });
  const formats = useQuery({ queryKey: ["beam-formats"], queryFn: beamModelApi.formats });
  const docs = files.flatMap((f) => f.models);
  const check = useQuery({
    queryKey: ["beam-validate", JSON.stringify(docs.map((d) => [d.model?.id, d.elements?.length]))],
    queryFn: () => beamModelApi.validate(docs),
    enabled: docs.length > 0,
  });
  const run = useMutation({
    mutationFn: () => beamModelApi.importModels(docs),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["beam-systems"] }),
  });
  const reports: BeamImportReport[] = run.data ? ("models" in run.data ? run.data.models : [run.data]) : [];
  const allOk = check.data?.models.every((m) => m.ok);

  const read = async (list: FileList | null) => {
    setRaw(await Promise.all(Array.from(list ?? []).map(async (f) => ({ name: f.name, text: await f.text() }))));
    run.reset();
  };
  // Canonical JSON is read as it is; any other file goes through the converter for its simulator, again
  // whenever the options change. Nothing is written until Import.
  useEffect(() => {
    let live = true;
    void Promise.all(raw.map(async ({ name, text }): Promise<UploadedFile> => {
      if (name.toLowerCase().endsWith(".json")) {
        try {
          const parsed = JSON.parse(text);
          const models: CanonicalBeamModel[] = Array.isArray(parsed) ? parsed
            : parsed?.format === "argus.beam-model-bundle/1" ? parsed.models : [parsed];
          return { name, models, via: "argus" };
        } catch (e) {
          return { name, models: [], error: `not JSON: ${e instanceof Error ? e.message : e}` };
        }
      }
      try {
        const out = await beamModelApi.convert(name, text, {
          topology: opts.topology, keep_markers: opts.keep_markers, ...(opts.system_kind ? { system_kind: opts.system_kind } : {}),
        });
        return { name, models: [out.model], via: out.report.converter, report: out.report };
      } catch (e) {
        return { name, models: [], error: errorText(e) };
      }
    })).then((r) => { if (live) setFiles(r); });
    return () => { live = false; };
  }, [raw, opts]);
  const simulators = raw.some((f) => !f.name.toLowerCase().endsWith(".json"));

  return (
    <div className="space-y-3 rounded border border-slate-200 bg-white p-4">
      <label className="block text-sm text-slate-700">
        Model files — ARGUS canonical JSON (one model, or a bundle as exported here) or simulator files, converted on
        upload and shown before anything is imported
        <input type="file" multiple onChange={(e) => void read(e.target.files)} className="mt-2 block text-sm"
               accept={(formats.data ?? []).flatMap((f) => f.extensions).join(",") || ".json"} />
      </label>
      <p className="text-xs text-slate-500">
        Read: {(formats.data ?? []).map((f) => f.label).join(" · ")}. The format is described in{" "}
        <button type="button" className="text-indigo-700 hover:underline"
                onClick={() => void beamModelApi.schema().then((x) => download("argus.beam-model-1.schema.json", x))}>its JSON Schema</button>{" "}
        and docs/beam-model-format.md.
      </p>
      {simulators && (
        <div className="flex flex-wrap items-end gap-3 rounded bg-slate-50 p-2 text-xs">
          <span className="font-medium text-slate-600">Simulator files:</span>
          <label>Topology{" "}
            <select value={opts.topology} onChange={(e) => setOpts({ ...opts, topology: e.target.value })} className="rounded border border-slate-300 px-1 py-0.5">
              <option value="auto">from the bends (a full turn is a ring)</option><option value="closed">closed (ring)</option><option value="open">open (line)</option>
            </select>
          </label>
          <label>System kind{" "}
            <input value={opts.system_kind} placeholder="e.g. Accumulator" onChange={(e) => setOpts({ ...opts, system_kind: e.target.value })}
                   className="w-36 rounded border border-slate-300 px-1 py-0.5" />
          </label>
          <label className="flex items-center gap-1">
            <input type="checkbox" checked={opts.keep_markers} onChange={(e) => setOpts({ ...opts, keep_markers: e.target.checked })} />
            keep markers
          </label>
        </div>
      )}
      {files.some((f) => f.error) && (
        <ul className="text-sm text-rose-700">{files.filter((f) => f.error).map((f) => <li key={f.name}>{f.name}: {f.error}</li>)}</ul>
      )}
      {files.some((f) => f.report) && (
        <ul className="space-y-0.5 text-xs text-slate-600">
          {files.filter((f) => f.report).map((f) => (
            <li key={f.name}>
              <span className="font-medium">{f.name}</span> read as {f.via}: {f.report!.elements} elements
              {f.report!.ring ? `, a ring (bends total ${(f.report!.total_bend * 180 / Math.PI).toFixed(1)}°, layout closes within ${f.report!.survey_closure_m?.toFixed(3)} m)` : ", a line"}
              {f.report!.not_executed?.length ? <span className="text-amber-700"> · not executed: {f.report!.not_executed.join("; ")}</span> : null}
            </li>
          ))}
        </ul>
      )}
      {check.data && (
        <table className="w-full text-sm">
          <thead><tr className="text-left text-xs text-slate-500"><th>Model</th><th>Systems</th><th>Paths</th><th>Elements</th><th>Datasets</th><th>Check</th><th /></tr></thead>
          <tbody>
            {check.data.models.map((m) => (
              <tr key={m.index} className="border-t border-slate-100 align-top">
                <td className="py-1 font-medium">{m.model ?? `#${m.index + 1}`}</td>
                <td>{m.summary?.systems ?? "—"}</td><td>{m.summary?.paths ?? "—"}</td>
                <td>{m.summary?.elements ?? "—"}</td><td>{m.summary?.datasets ?? "—"}</td>
                <td className={m.ok ? "text-emerald-700" : "text-rose-700"}>{m.ok ? "ok" : m.problems.join("; ")}</td>
                <td>
                  <button type="button" onClick={() => onEdit(docs[m.index])} className="text-xs text-indigo-700 hover:underline">open in editor</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {docs.length > 0 && (
        <div className="flex items-center gap-3">
          <button type="button" disabled={!allOk || run.isPending || reports.length > 0} onClick={() => run.mutate()}
                  className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:bg-slate-300">
            {run.isPending ? "Importing…" : `Import ${docs.length} model${docs.length > 1 ? "s" : ""}`}
          </button>
          {!allOk && check.data && <span className="text-xs text-slate-500">All must pass: nothing is imported while one fails.</span>}
          {run.isError && <span className="text-sm text-rose-700">{errorText(run.error)}</span>}
        </div>
      )}
      <ImportReports reports={reports} />
    </div>
  );
}

function ImportReports({ reports }: { reports: BeamImportReport[] }) {
  if (!reports.length) return null;
  return (
    <div className="rounded bg-emerald-50 p-3 text-sm text-emerald-900">
      {reports.map((r) => (
        <div key={r.model}>
          <b>{r.model}</b>: {r.state} — {r.elements} elements, {r.values} dataset values
          {r.awaiting_policy && <span className="text-amber-800"> · waiting for the authority policy to cover this source</span>}
        </div>
      ))}
      <Link to="/beam-model" className="mt-1 inline-block text-indigo-700 hover:underline">Open the beam model →</Link>
    </div>
  );
}

// ------------------------------------------------------------------------- editor

function Editor({ initial, editing }: { initial: CanonicalBeamModel; editing: boolean }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [doc, setDoc] = useState<CanonicalBeamModel>(() => clone(initial));
  const [pathId, setPathId] = useState(initial.paths[0]?.id ?? "");
  const update = (fn: (d: CanonicalBeamModel) => void) => setDoc((d) => { const n = clone(d); fn(n); return n; });
  const save = useMutation({
    mutationFn: () => beamModelApi.importModels(tidy(doc)),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["beam-systems"] });
      void qc.invalidateQueries({ queryKey: ["beam-model-export"] });
    },
  });
  const report = save.data && !("models" in save.data) ? save.data : null;
  const path = doc.paths.find((p) => p.id === pathId);
  const dataset = path ? editDataset(doc, path) : undefined;

  return (
    <div className="space-y-4">
      <Box title="Model">
        <div className="grid gap-2 sm:grid-cols-5">
          <Field label="Id" value={doc.model.id} disabled={editing} placeholder="e.g. sparc-linac"
                 onChange={(v) => update((d) => { d.model.id = v.trim(); })} />
          <Field label="Name" value={doc.model.name ?? ""} onChange={(v) => update((d) => { d.model.name = v; })} />
          <Field label="Version" value={doc.model.version ?? ""} onChange={(v) => update((d) => { d.model.version = v; })} />
          <Field label="Source" value={doc.model.source ?? ""} onChange={(v) => update((d) => { d.model.source = v; })} />
          <Field label="Simulator" value={doc.model.simulator ?? ""} placeholder="madx, elegant…" onChange={(v) => update((d) => { d.model.simulator = v; })} />
        </div>
      </Box>

      <Box title="Systems and beams" action={<Small onClick={() => update((d) => { d.systems.push({ id: `system${d.systems.length + 1}`, kind: "Other", beams: [] }); })}>+ system</Small>}>
        {doc.systems.map((s, i) => (
          <div key={i} className="mb-2 rounded border border-slate-100 p-2">
            <div className="grid gap-2 sm:grid-cols-4">
              <Field label="Id" value={s.id} onChange={(v) => update((d) => renameSystem(d, i, v))} />
              <Field label="Name" value={s.name ?? ""} onChange={(v) => update((d) => { d.systems[i].name = v; })} />
              <Select label="Kind" value={s.kind} options={SYSTEM_KINDS} onChange={(v) => update((d) => { d.systems[i].kind = v; })} />
              <div className="flex items-end gap-2">
                <Small onClick={() => update((d) => { d.systems[i].beams.push({ id: `beam${s.beams.length + 1}`, kind: "particle", parameters: {} }); })}>+ beam</Small>
                {doc.systems.length > 1 && <Small danger onClick={() => update((d) => { d.systems.splice(i, 1); })}>remove</Small>}
              </div>
            </div>
            {s.beams.map((b, j) => (
              <div key={j} className="mt-2 grid gap-2 sm:grid-cols-4">
                <Field label="Beam id" value={b.id} onChange={(v) => update((d) => { d.systems[i].beams[j].id = v; })} />
                <Select label="Kind" value={b.kind} options={["particle", "photon"]} onChange={(v) => update((d) => { d.systems[i].beams[j].kind = v as "particle" | "photon"; })} />
                <Field label={b.kind === "photon" ? "wavelength (nm), pulse_duration (fs)…" : "species, charge, reference_energy (GeV)…"}
                       value={kv(b.parameters)} placeholder={b.kind === "photon" ? "wavelength=800, repetition_rate=10" : "species=electron, reference_energy=0.15"}
                       onChange={(v) => update((d) => { d.systems[i].beams[j].parameters = parseKv(v); })} wide />
              </div>
            ))}
          </div>
        ))}
      </Box>

      <Box title="Paths" action={<Small onClick={() => update((d) => { const id = `path${d.paths.length + 1}`; d.paths.push({ id, system: d.systems[0]?.id ?? "", topology: "open", elements: [] }); setPathId(id); })}>+ path</Small>}>
        <div className="flex flex-wrap gap-2">
          {doc.paths.map((p) => (
            <button key={p.id} type="button" onClick={() => setPathId(p.id)}
                    className={`rounded border px-2 py-1 text-sm ${p.id === pathId ? "border-slate-900 bg-slate-900 text-white" : "border-slate-300"}`}>
              {p.name || p.id} · {p.topology} · {p.elements.length}
            </button>
          ))}
        </div>
        {path && (
          <PathEditor doc={doc} path={path} dataset={dataset!} update={update}
                      onRenamed={(id) => setPathId(id)} onRemoved={() => setPathId(doc.paths.find((p) => p.id !== path.id)?.id ?? "")} />
        )}
      </Box>

      <div className="flex flex-wrap items-center gap-3">
        <button type="button" disabled={!doc.model.id || save.isPending} onClick={() => save.mutate()}
                className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:bg-slate-300">
          {save.isPending ? "Saving…" : editing ? "Save changes" : "Create model"}
        </button>
        <button type="button" onClick={() => download(`${doc.model.id || "beam-model"}.json`, tidy(doc))}
                className="rounded border border-slate-300 px-3 py-2 text-sm">Download JSON</button>
        {save.isError && <span className="text-sm text-rose-700">{errorText(save.error)}</span>}
        {report && (
          <span className="text-sm text-emerald-700">
            Saved: {report.elements} elements, {report.values} values.{" "}
            <button type="button" className="underline" onClick={() => navigate("/beam-model")}>Open the beam model</button>
          </span>
        )}
      </div>
    </div>
  );
}

/** The dataset this editor writes a path's values into: its first, or a design dataset made for it. */
function editDataset(doc: CanonicalBeamModel, path: CanonicalPath): CanonicalDataset {
  return (doc.datasets ?? []).find((d) => d.path === path.id)
    ?? { id: `${path.id}-design`, name: `${path.name || path.id} design`, kind: "design", path: path.id, values: {} };
}

function ensureDataset(d: CanonicalBeamModel, pathId: string): CanonicalDataset {
  d.datasets = d.datasets ?? [];
  let ds = d.datasets.find((x) => x.path === pathId);
  if (!ds) {
    const p = d.paths.find((x) => x.id === pathId)!;
    ds = { id: `${pathId}-design`, name: `${p.name || p.id} design`, kind: "design", path: pathId, values: {} };
    d.datasets.push(ds);
  }
  return ds;
}

function renameSystem(d: CanonicalBeamModel, i: number, v: string) {
  const old = d.systems[i].id;
  d.systems[i].id = v;
  d.paths.forEach((p) => { if (p.system === old) p.system = v; });
}

/** What is sent: empty names dropped, datasets with no values left out, observables declared. */
function tidy(doc: CanonicalBeamModel): CanonicalBeamModel {
  const d = clone(doc);
  const strip = (o: { name?: string }) => { if (!o.name) delete o.name; };
  d.systems.forEach(strip);
  d.paths.forEach(strip);
  d.elements.forEach(strip);
  d.datasets = (d.datasets ?? []).filter((x) => Object.keys(x.values ?? {}).length > 0);
  if (!d.model.name) delete d.model.name;
  const declared = new Set((d.observables ?? []).map((o) => o.quantity));
  for (const q of d.elements.flatMap((e) => e.observes ?? [])) {
    if (!declared.has(q) && !OBSERVABLES.includes(q)) {
      d.observables = [...(d.observables ?? []), { quantity: q }];
      declared.add(q);
    }
  }
  return d;
}

function PathEditor({ doc, path, dataset, update, onRenamed, onRemoved }: {
  doc: CanonicalBeamModel; path: CanonicalPath; dataset: CanonicalDataset;
  update: (fn: (d: CanonicalBeamModel) => void) => void; onRenamed: (id: string) => void; onRemoved: () => void;
}) {
  const byId = useMemo(() => new Map(doc.elements.map((e) => [e.id, e])), [doc.elements]);
  const withPath = (fn: (p: CanonicalPath, d: CanonicalBeamModel) => void) =>
    update((d) => fn(d.paths.find((x) => x.id === path.id)!, d));
  const setValue = (el: string, key: "s" | "length" | string, raw: string) => update((d) => {
    const ds = ensureDataset(d, path.id);
    const v = (ds.values[el] = ds.values[el] ?? {});
    const num = raw.trim() === "" ? null : Number(raw);
    if (key === "s") v.s = num;
    else {
      v.physics = { ...(v.physics ?? {}) };
      if (num == null || Number.isNaN(num)) delete v.physics[key];
      else v.physics[key] = num;
    }
  });
  const addElement = (after: number) => update((d) => {
    const p = d.paths.find((x) => x.id === path.id)!;
    let n = d.elements.length + 1;
    while (d.elements.some((e) => e.id === `E${String(n).padStart(3, "0")}`)) n++;
    const id = `E${String(n).padStart(3, "0")}`;
    d.elements.push({ id, type: "drift" });
    p.elements.splice(after + 1, 0, id);
  });
  const move = (i: number, by: number) => withPath((p) => {
    const j = i + by;
    if (j < 0 || j >= p.elements.length) return;
    [p.elements[i], p.elements[j]] = [p.elements[j], p.elements[i]];
  });
  const remove = (i: number) => update((d) => {
    const p = d.paths.find((x) => x.id === path.id)!;
    const [id] = p.elements.splice(i, 1);
    d.elements = d.elements.filter((e) => e.id !== id);
    (d.datasets ?? []).forEach((ds) => { delete ds.values[id]; });
    d.paths.forEach((q) => { q.branches = (q.branches ?? []).filter((b) => b.at !== id); if (q.reference === id) delete q.reference; });
  });
  const editElement = (id: string, fn: (e: CanonicalElement) => void) => update((d) => { fn(d.elements.find((e) => e.id === id)!); });
  const renameElement = (old: string, v: string) => update((d) => {
    if (!v || d.elements.some((e) => e.id === v)) return;
    d.elements.find((e) => e.id === old)!.id = v;
    d.paths.forEach((p) => {
      p.elements = p.elements.map((x) => (x === old ? v : x));
      if (p.reference === old) p.reference = v;
      (p.branches ?? []).forEach((b) => { if (b.at === old) b.at = v; });
    });
    (d.datasets ?? []).forEach((ds) => { if (ds.values[old]) { ds.values[v] = ds.values[old]; delete ds.values[old]; } });
  });

  return (
    <div className="mt-3 space-y-3">
      <div className="grid gap-2 sm:grid-cols-6">
        <Field label="Path id" value={path.id} onChange={(v) => { if (!v || doc.paths.some((p) => p.id === v)) return; update((d) => {
          d.paths.find((p) => p.id === path.id)!.id = v;
          (d.datasets ?? []).forEach((ds) => { if (ds.path === path.id) ds.path = v; });
          d.paths.forEach((p) => (p.branches ?? []).forEach((b) => { if (b.to_path === path.id) b.to_path = v; }));
        }); onRenamed(v); }} />
        <Field label="Name" value={path.name ?? ""} onChange={(v) => withPath((p) => { p.name = v; })} />
        <Select label="System" value={path.system} options={doc.systems.map((s) => s.id)} onChange={(v) => withPath((p) => { p.system = v; })} />
        <Select label="Topology" value={path.topology} options={["open", "closed"]} onChange={(v) => withPath((p) => { p.topology = v as "open" | "closed"; })} />
        <Field label="Length (m)" value={path.length?.toString() ?? ""} onChange={(v) => withPath((p) => { if (v.trim()) p.length = Number(v); else delete p.length; })} />
        <Select label="Reference (s = 0)" value={path.reference ?? ""} options={["", ...path.elements]} onChange={(v) => withPath((p) => { if (v) p.reference = v; else delete p.reference; })} />
      </div>
      <div className="text-xs text-slate-500">
        Values below go into dataset <b>{dataset.name ?? dataset.id}</b> ({dataset.kind}); other datasets are kept as they are.
        {doc.paths.length > 1 && <Small danger onClick={() => { update((d) => {
          const p = d.paths.find((x) => x.id === path.id)!;
          d.elements = d.elements.filter((e) => !p.elements.includes(e.id));
          d.datasets = (d.datasets ?? []).filter((ds) => ds.path !== path.id);
          d.paths = d.paths.filter((x) => x.id !== path.id);
          d.paths.forEach((q) => { q.branches = (q.branches ?? []).filter((b) => b.to_path !== path.id); });
        }); onRemoved(); }}> remove this path</Small>}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-slate-500">
              <th className="w-6">#</th><th>Id</th><th>Name</th><th>Kind</th><th>s (m)</th><th>Length (m)</th>
              <th>Strength</th><th>Observes</th><th>Branches to</th><th />
            </tr>
          </thead>
          <tbody>
            {path.elements.map((id, i) => {
              const e = byId.get(id);
              if (!e) return null;
              const v = dataset.values[id] ?? {};
              const strength = STRENGTH[e.type];
              const branch = (path.branches ?? []).find((b) => b.at === id);
              return (
                <tr key={id} className="border-t border-slate-100 align-top">
                  <td className="py-1 text-slate-400">{i + 1}</td>
                  <td><Cell value={id} onCommit={(x) => renameElement(id, x.trim())} mono /></td>
                  <td><Cell value={e.name ?? ""} onCommit={(x) => editElement(id, (el) => { el.name = x; })} /></td>
                  <td>
                    <select value={e.type} onChange={(ev) => editElement(id, (el) => { el.type = ev.target.value; delete el.capabilities; if (!DIAGNOSTICS.has(ev.target.value)) delete el.observes; })}
                            className="rounded border border-slate-300 px-1 py-0.5">
                      {KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
                    </select>
                  </td>
                  <td><Cell value={v.s?.toString() ?? ""} onCommit={(x) => setValue(id, "s", x)} narrow /></td>
                  <td><Cell value={(v.physics?.length as number | undefined)?.toString() ?? ""} onCommit={(x) => setValue(id, "length", x)} narrow /></td>
                  <td>
                    {strength ? (
                      <span className="flex items-center gap-1">
                        <span className="text-slate-400">{strength}</span>
                        <Cell value={(v.physics?.[strength] as number | undefined)?.toString() ?? ""} onCommit={(x) => setValue(id, strength, x)} narrow />
                      </span>
                    ) : <span className="text-slate-300">—</span>}
                  </td>
                  <td>
                    {DIAGNOSTICS.has(e.type) ? (
                      <Cell value={(e.observes ?? []).join(", ")} placeholder="beam.position.x, beam.position.y"
                            onCommit={(x) => editElement(id, (el) => { el.observes = x.split(",").map((q) => q.trim()).filter(Boolean); })} />
                    ) : <span className="text-slate-300">—</span>}
                  </td>
                  <td>
                    <select value={branch?.to_path ?? ""} onChange={(ev) => withPath((p) => {
                      p.branches = (p.branches ?? []).filter((b) => b.at !== id);
                      if (ev.target.value) p.branches.push({ at: id, to_path: ev.target.value });
                    })} className="rounded border border-slate-300 px-1 py-0.5">
                      <option value="">—</option>
                      {doc.paths.filter((p) => p.id !== path.id).map((p) => <option key={p.id} value={p.id}>{p.name || p.id}</option>)}
                    </select>
                  </td>
                  <td className="whitespace-nowrap">
                    <Icon onClick={() => move(i, -1)} title="move up">↑</Icon>
                    <Icon onClick={() => move(i, 1)} title="move down">↓</Icon>
                    <Icon onClick={() => addElement(i)} title="add below">+</Icon>
                    <Icon onClick={() => remove(i)} title="remove">✕</Icon>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <Small onClick={() => addElement(path.elements.length - 1)}>+ element at the end</Small>
      <p className="text-xs text-slate-500">
        Order is beam order: each element follows the one above it{path.topology === "closed" ? ", and the last closes to the first" : ""}.
        A branch leaves from the element that names it and goes to the first element of that path. Capabilities follow the kind
        (a quadrupole focuses, a BPM measures position); simulator-specific types and parameters come with an uploaded file.
      </p>
    </div>
  );
}

// ------------------------------------------------------------------------- small pieces

function kv(o: Record<string, unknown>): string {
  return Object.entries(o ?? {}).map(([k, v]) => `${k}=${v}`).join(", ");
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
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function Field({ label, value, onChange, placeholder, disabled, wide }: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string; disabled?: boolean; wide?: boolean;
}) {
  return (
    <label className={`block text-xs text-slate-500 ${wide ? "sm:col-span-2" : ""}`}>
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

/** A table cell edited in place and committed on blur or Enter, so a rename does not happen per keystroke. */
function Cell({ value, onCommit, mono, narrow, placeholder }: {
  value: string; onCommit: (v: string) => void; mono?: boolean; narrow?: boolean; placeholder?: string;
}) {
  const [v, setV] = useState(value);
  useEffect(() => setV(value), [value]);
  return (
    <input value={v} placeholder={placeholder} onChange={(e) => setV(e.target.value)}
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
