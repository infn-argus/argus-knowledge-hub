/** Document control: how long a released document is kept, what replaced
 * it, and whether an attachment is still the file that was uploaded. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { documentsApi } from "../../api/client";
import type { RetentionClass } from "../../api/ledgerTypes";
import type { AppDocument } from "../../api/types";
import { errorText } from "./LedgerPanels";

const CLASSES: { value: RetentionClass; label: string }[] = [
  { value: "permanent", label: "Permanent" },
  { value: "10y", label: "10 years" },
  { value: "5y", label: "5 years" },
  { value: "2y", label: "2 years" },
  { value: "none", label: "Not retained" },
];

const day = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString() : "—");

export function SupersededBanner({ doc }: { doc: AppDocument }) {
  if (!doc.superseded_by_uid) return null;
  return (
    <div className="mt-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
      Superseded — this document is no longer in force.{" "}
      <Link to={`/documents/${doc.superseded_by_uid}`} className="font-medium underline">
        Open the document that replaces it
      </Link>
    </div>
  );
}

export function DocumentControlCard({ doc }: { doc: AppDocument }) {
  const queryClient = useQueryClient();
  const retention = useQuery({ queryKey: ["document-retention", doc.uid], queryFn: () => documentsApi.retention(doc.uid) });
  const documents = useQuery({ queryKey: ["documents"], queryFn: () => documentsApi.list() });
  const [superseding, setSuperseding] = useState(false);
  const [successor, setSuccessor] = useState("");
  const [reason, setReason] = useState("");
  const refresh = () => {
    for (const key of ["document-retention", "document", "documents", "document-revisions"])
      queryClient.invalidateQueries({ queryKey: [key] });
  };
  const setClass = useMutation({
    mutationFn: (c: RetentionClass) => documentsApi.setRetention(doc.uid, c),
    onSuccess: refresh,
  });
  const supersede = useMutation({
    mutationFn: () => documentsApi.supersede(doc.uid, successor, reason),
    onSuccess: () => {
      setSuperseding(false);
      refresh();
    },
  });
  const r = retention.data;
  if (!r) return null;
  // A successor must itself be in force.
  const candidates = (documents.data ?? []).filter(
    (d) => d.uid !== doc.uid && d.current_revision_uid && !d.superseded_by_uid,
  );
  return (
    <div className="mt-3 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <span className="text-xs font-medium uppercase tracking-wide text-slate-400">Retention</span>
        <select
          value={r.class}
          onChange={(e) => setClass.mutate(e.target.value as RetentionClass)}
          disabled={setClass.isPending}
          className="rounded border border-slate-200 px-2 py-0.5 text-xs"
          title="Released documents can have their retention lengthened, not shortened"
        >
          {CLASSES.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
        <span className="text-xs text-slate-500">
          {r.released_at === null
            ? "Never released — nothing to keep yet"
            : r.permanent
              ? "Kept permanently"
              : r.deletable
                ? "Retention over — may be deleted"
                : `Kept until ${day(r.retain_until)}`}
        </span>
        {r.retired_at && <span className="text-xs text-slate-500">Retired {day(r.retired_at)}</span>}
        {!doc.superseded_by_uid && doc.current_revision_uid && (
          <button onClick={() => setSuperseding(!superseding)} className="ml-auto text-xs text-indigo-700 hover:underline">
            Supersede…
          </button>
        )}
      </div>
      {superseding && (
        <div className="mt-2 space-y-2 rounded border border-slate-200 bg-slate-50 p-2 text-xs">
          <p className="text-slate-700">
            The replacing document must be published. This one retires and points to it; its retention keeps running.
          </p>
          <select value={successor} onChange={(e) => setSuccessor(e.target.value)} className="w-full rounded border border-slate-300 px-2 py-1">
            <option value="">Replaced by…</option>
            {candidates.map((d) => (
              <option key={d.uid} value={d.uid}>
                {d.code} — {d.title}
              </option>
            ))}
          </select>
          <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason" className="w-full rounded border border-slate-300 px-2 py-1" />
          <button
            disabled={!successor || !reason || supersede.isPending}
            onClick={() => supersede.mutate()}
            className="rounded bg-slate-900 px-3 py-1 font-medium text-white disabled:opacity-40"
          >
            Supersede
          </button>
        </div>
      )}
      {(setClass.isError || supersede.isError) && (
        <p className="mt-1 text-xs text-red-600">{errorText(setClass.error ?? supersede.error)}</p>
      )}
    </div>
  );
}

/** Recomputes an attachment's checksum on the server against the one recorded at upload. */
export function VerifyAttachment({ uid }: { uid: string }) {
  const check = useMutation({ mutationFn: () => documentsApi.verifyAttachment(uid) });
  if (check.data) {
    const c = check.data;
    const text = c.missing ? "file missing" : !c.recorded ? "no checksum recorded" : c.ok ? "✓ unchanged" : "✗ changed since upload";
    const tone = c.ok ? "text-emerald-700" : "text-red-600";
    return <span className={tone} title={c.actual ?? undefined}>{text}</span>;
  }
  return (
    <button type="button" onClick={() => check.mutate()} className="text-slate-500 hover:text-slate-900 hover:underline">
      {check.isPending ? "Checking…" : "Verify"}
    </button>
  );
}
