import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { aiApi, ApiError, intakeApi, type ProposeResult } from "../api/client";
import { portBody, ProposedPorts, type PortChoice } from "./ProposedPorts";

/** What a datasheet, a nameplate photo or a note says about this asset,
 * as proposals for its owner (asset-model-revision §23.11). Nothing on the
 * record changes here: every value that differs waits in the review queue. */
export function SuggestFromFile({ assetUid }: { assetUid: string }) {
  const status = useQuery({ queryKey: ["ai-status"], queryFn: aiApi.status, staleTime: 60_000 });
  const input = useRef<HTMLInputElement>(null);
  const [text, setText] = useState("");
  const [ports, setPorts] = useState<PortChoice[]>([]);
  const [addresses, setAddresses] = useState<{ ip?: string; hostname?: string; on: boolean }[]>([]);
  const queryClient = useQueryClient();
  const propose = useMutation({
    mutationFn: (file?: File) => intakeApi.propose(assetUid, { file, text }),
    onSuccess: (res: ProposeResult) => {
      const offered = res.companions ?? [];
      setPorts(offered.filter((c) => c.kind === "port").map((c) => ({ ...c.attributes, on: c.selected })));
      setAddresses(offered.filter((c) => c.kind === "address")
        .map((c) => ({ ip: c.attributes.ip, hostname: c.attributes.hostname, on: c.selected })));
      add.reset();
    },
  });
  const add = useMutation({
    mutationFn: () => intakeApi.addCompanions(assetUid, {
      ports: ports.filter((p) => p.on).map(portBody),
      addresses: addresses.filter((a) => a.on).map(({ on: _on, ...a }) => a),
      run_id: propose.data?.run_id,
    }),
    onSuccess: () => {
      setPorts([]);
      setAddresses([]);
      void queryClient.invalidateQueries({ queryKey: ["assets"] });
      void queryClient.invalidateQueries({ queryKey: ["relations"] });
    },
  });
  if (!status.data?.validated) return null;
  const r = propose.data;
  const chosen = ports.filter((p) => p.on).length + addresses.filter((a) => a.on).length;
  const portChanges = r?.port_changes ?? [];
  const accept = (status.data.has_vision ? "image/*," : "") + ".pdf,.docx,.xlsx,.xlsm,.eml,.txt,.md,.csv";
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-slate-800">Complete from a file</h2>
      <p className="mt-0.5 text-xs text-slate-500">
        A datasheet, a nameplate photo or a note. What differs from this record is proposed for review; nothing
        changes until someone confirms it.
      </p>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={2}
        placeholder="Or write what you know, e.g. “the nameplate says model VacIon Plus 75, inventory LNF-7”"
        className="mt-2 w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
      />
      <div className="mt-2 flex gap-2">
        <button
          type="button"
          disabled={propose.isPending}
          onClick={() => input.current?.click()}
          className="rounded border border-slate-300 px-3 py-1.5 text-xs disabled:opacity-40"
        >
          {propose.isPending ? "Reading…" : "Choose a file"}
        </button>
        <button
          type="button"
          disabled={propose.isPending || !text.trim()}
          onClick={() => propose.mutate(undefined)}
          className="rounded bg-slate-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40"
        >
          Propose from the text
        </button>
        <input
          ref={input}
          type="file"
          accept={accept}
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            e.target.value = "";
            if (f) propose.mutate(f);
          }}
        />
      </div>
      {propose.isError && (
        <p className="mt-2 text-xs text-red-600">
          {(propose.error instanceof ApiError && propose.error.detail) || (propose.error as Error).message}
        </p>
      )}
      {r && (
        <div className="mt-3 text-xs">
          {r.proposed.length === 0 && !portChanges.length && !ports.length && !addresses.length ? (
            <p className="text-slate-600">{r.message ?? "Nothing new: what it says is already on the record."}</p>
          ) : r.proposed.length > 0 && (
            <>
              <p className="text-slate-700">
                {r.proposed.length} value(s) proposed.{" "}
                <Link to="/review" className="text-indigo-700 hover:underline">
                  Review them
                </Link>
              </p>
              <ul className="mt-1 space-y-0.5 text-slate-600">
                {r.proposed.map((p) => (
                  <li key={p.field}>
                    {p.field.replace(/^attributes\./, "")}: <span className="font-medium">{p.label ?? String(p.value)}</span>
                    {p.current ? <span className="text-slate-400"> (now {String(p.current)})</span> : null}
                  </li>
                ))}
              </ul>
            </>
          )}
          {r.unchanged.length > 0 && <p className="mt-1 text-slate-400">{r.unchanged.length} already matched the record.</p>}
          {portChanges.length > 0 && (
            <div className="mt-2">
              <p className="text-slate-700">
                {portChanges.length} value(s) proposed on its ports.{" "}
                <Link to="/review" className="text-indigo-700 hover:underline">Review them</Link>
              </p>
              <ul className="mt-1 space-y-0.5 text-slate-600">
                {portChanges.map((c) => (
                  <li key={`${c.port.uid}-${c.field}`}>
                    {c.port.label ?? c.port.key} · {c.field}: <span className="font-medium">{String(c.value)}</span>
                    {c.current != null && c.current !== "" ? <span className="text-slate-400"> (now {String(c.current)})</span> : null}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {(ports.length > 0 || addresses.length > 0) && (
            <div className="mt-3 space-y-2">
              <ProposedPorts title="Ports it does not have yet" ports={ports}
                             onToggle={(i, on) => setPorts((all) => all.map((p, j) => (j === i ? { ...p, on } : p)))} />
              {addresses.map((a, i) => (
                <label key={`${a.ip}-${a.hostname}`} className="flex items-center gap-2 text-slate-700">
                  <input type="checkbox" checked={a.on}
                         onChange={(e) => setAddresses((all) => all.map((x, j) => (j === i ? { ...x, on: e.target.checked } : x)))} />
                  Add its address <span className="font-mono">{[a.ip, a.hostname].filter(Boolean).join(" · ")}</span>
                </label>
              ))}
              <button type="button" disabled={!chosen || add.isPending} onClick={() => add.mutate()}
                      className="rounded bg-slate-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40">
                {add.isPending ? "Adding…" : `Add ${chosen} to this unit`}
              </button>
            </div>
          )}
          {add.isSuccess && (
            <p className="mt-2 text-green-800">
              Added {add.data.ports.length + add.data.addresses.length}:{" "}
              {[...add.data.ports, ...add.data.addresses].map((x) => x.key).join(", ")}
            </p>
          )}
          {add.isError && (
            <p className="mt-2 text-red-600">
              {(add.error instanceof ApiError && add.error.detail) || (add.error as Error).message}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
