import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, intakeApi, type IntakeKind, type IntakeProfileView } from "../api/client";

/** Model profiles for guided entry (asset-model-revision §23.8, §23.12): a candidate model is evaluated on
 * the golden dataset and becomes the one used only once it passes the gate, or with a stated exception. */
export function IntakeProfiles() {
  const queryClient = useQueryClient();
  const q = useQuery({ queryKey: ["intake-profiles"], queryFn: intakeApi.profiles });
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["intake-profiles"] });
    queryClient.invalidateQueries({ queryKey: ["intake-status"] });
  };
  const [kind, setKind] = useState<IntakeKind>("asset");
  const [model, setModel] = useState("");
  const [vision, setVision] = useState("");
  const create = useMutation({
    mutationFn: () => intakeApi.createProfile({ kind, model, vision_model: vision || undefined }),
    onSuccess: () => { setModel(""); setVision(""); refresh(); },
  });
  const evaluate = useMutation({ mutationFn: intakeApi.evaluateProfile, onSuccess: refresh });
  const activate = useMutation({
    mutationFn: (v: { id: string; reason: string; exception?: string }) => intakeApi.activateProfile(v.id, v.reason, v.exception),
    onSuccess: refresh,
  });
  const retire = useMutation({ mutationFn: (v: { id: string; reason: string }) => intakeApi.retireProfile(v.id, v.reason), onSuccess: refresh });
  const error = [create, evaluate, activate, retire].find((m) => m.isError)?.error;
  if (!q.data) return null;

  const onActivate = (p: IntakeProfileView) => {
    const reason = prompt(`Why use ${p.model} for ${p.kind} entry?`);
    if (!reason) return;
    const exception = p.evaluation?.passed ? undefined
      : prompt(`The evaluation did not pass:\n${(p.evaluation?.failures ?? []).join("\n")}\n\nState the exception, or cancel:`) ?? undefined;
    if (!p.evaluation?.passed && !exception) return;
    activate.mutate({ id: p.id, reason, exception });
  };

  return (
    <section className="mt-8 rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="text-lg font-semibold text-slate-900">Models for guided entry</h2>
      <p className="mt-1 text-sm text-slate-500">
        A model is used for describing assets, tickets or documents once it has been evaluated on the golden dataset
        (accuracy per field and language, injected instructions, secrets) and activated. Without an active profile the
        endpoint's default model is used, and every suggestion is marked as unevaluated.
      </p>
      <p className="mt-1 text-xs text-slate-400">
        Prompt version {q.data.prompt_version} · datasets:{" "}
        {Object.entries(q.data.datasets).map(([k, d]) => `${k} ${d.cases} cases (${d.version})`).join(", ")}
      </p>

      <div className="mt-3 flex flex-wrap items-end gap-2 text-sm">
        <select value={kind} onChange={(e) => setKind(e.target.value as IntakeKind)} className="rounded border border-slate-300 px-2 py-1.5">
          <option value="asset">assets</option>
          <option value="ticket">tickets</option>
          <option value="document">documents</option>
        </select>
        <input value={model} onChange={(e) => setModel(e.target.value)} placeholder="model name" className="rounded border border-slate-300 px-2 py-1.5" />
        {kind === "asset" && (
          <input value={vision} onChange={(e) => setVision(e.target.value)} placeholder="vision model (optional)" className="rounded border border-slate-300 px-2 py-1.5" />
        )}
        <button disabled={!model.trim() || create.isPending} onClick={() => create.mutate()}
                className="rounded bg-slate-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40">Add candidate</button>
      </div>
      {error && <p className="mt-2 text-xs text-red-600">{(error instanceof ApiError && (error.detail ?? JSON.stringify(error.body))) || (error as Error).message}</p>}

      <ul className="mt-3 divide-y divide-slate-100 text-sm">
        {q.data.profiles.map((p) => {
          const ev = p.evaluation;
          const stale = ev && ev.dataset_version !== p.current_dataset;
          return (
            <li key={p.id} className="py-2.5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{p.model}</span>
                <span className="text-xs text-slate-500">{p.kind}{p.vision_model ? ` · vision ${p.vision_model}` : ""}</span>
                <span className={`rounded px-1.5 text-[11px] ${p.status === "active" ? "bg-emerald-50 text-emerald-700" : p.status === "retired" ? "bg-slate-100 text-slate-500" : "bg-sky-50 text-sky-800"}`}>{p.status}</span>
                {ev && (
                  <span className={`rounded px-1.5 text-[11px] ${ev.passed && !stale ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-800"}`}>
                    {stale ? "evaluated on an older dataset" : ev.passed ? `passed · ${Math.round((ev.overall ?? 0) * 100)}%` : `did not pass · ${Math.round((ev.overall ?? 0) * 100)}%`}
                  </span>
                )}
                <span className="flex-1" />
                {p.status !== "retired" && (
                  <button onClick={() => evaluate.mutate(p.id)} disabled={evaluate.isPending}
                          className="rounded border border-slate-300 px-2 py-0.5 text-xs disabled:opacity-40">
                    {evaluate.isPending && evaluate.variables === p.id ? "Evaluating…" : "Evaluate"}
                  </button>
                )}
                {p.status === "candidate" && ev && !stale && (
                  <button onClick={() => onActivate(p)} className="rounded border border-slate-300 px-2 py-0.5 text-xs">Activate</button>
                )}
                {p.status === "active" && (
                  <button onClick={() => { const r = prompt("Why suspend it?"); if (r) retire.mutate({ id: p.id, reason: r }); }}
                          className="rounded border border-slate-300 px-2 py-0.5 text-xs">Suspend</button>
                )}
              </div>
              {ev && (
                <div className="mt-1 text-xs text-slate-600">
                  {Object.entries(ev.fields).map(([f, r]) => `${f.replace(/^attributes\./, "")} ${r.accuracy === null ? "–" : Math.round(r.accuracy * 100) + "%"}`).join(" · ")}
                  {Object.keys(ev.by_tag).length > 0 && <div className="text-slate-400">by tag: {Object.entries(ev.by_tag).map(([t, a]) => `${t} ${Math.round(a * 100)}%`).join(" · ")}</div>}
                  <div className="text-slate-400">
                    injected instructions {ev.security.injection_cases - ev.security.injection_failures.length}/{ev.security.injection_cases} held ·
                    secrets {ev.security.secret_cases - ev.security.secret_failures.length}/{ev.security.secret_cases} kept out
                    {ev.latency_ms_p95 !== null ? ` · p95 ${ev.latency_ms_p95} ms` : ""}
                  </div>
                  {ev.failures.map((f) => <div key={f} className="text-amber-800">{f}</div>)}
                </div>
              )}
              {p.exception_reason && <p className="mt-1 text-xs text-amber-800">Activated with an exception: {p.exception_reason}</p>}
            </li>
          );
        })}
        {q.data.profiles.length === 0 && <li className="py-2 text-sm text-slate-500">No profile yet.</li>}
      </ul>
    </section>
  );
}
