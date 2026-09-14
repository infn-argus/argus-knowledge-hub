import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, aiApi } from "../api/client";
import { useCurrentWorkspaceId } from "../api/useCurrentWorkspaceId";
import type { MentionedObject, ReviewFinding } from "../api/types";

const SEVERITY: Record<string, string> = {
  high: "border-red-200 bg-red-50 text-red-800",
  medium: "border-amber-200 bg-amber-50 text-amber-800",
  low: "border-slate-200 bg-slate-50 text-slate-700",
};

function Mentions({ objects, onLink }: { objects: MentionedObject[]; onLink?: (uid: string) => void }) {
  if (objects.length === 0) return null;
  return (
    <div className="mt-2 text-xs text-slate-600">
      <p className="font-medium text-slate-700">Objects this text names:</p>
      <ul className="mt-1 space-y-0.5">
        {objects.map((o) => (
          <li key={o.uid} className="flex items-center gap-2">
            <Link to={`/assets/${o.uid}`} className="text-indigo-600 hover:underline">
              {o.name}
            </Link>
            {o.key && <span className="text-slate-400">{o.key}</span>}
            <span className="text-[10px] uppercase tracking-wide text-slate-400">
              matched on {o.matched_on}
            </span>
            {onLink && (
              <button
                type="button"
                onClick={() => onLink(o.uid)}
                className="text-slate-500 hover:text-slate-900 hover:underline"
              >
                Link
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Drafting and reviewing, next to the editor.
 *
 * Both write into the form and nowhere else: a draft lands in the editor
 * for somebody to edit before it is saved, and a review is a list of
 * remarks rather than a set of changes. The objects it lists are found by
 * matching the inventory, not by asking the model — a link to equipment
 * that does not exist is worse than no link.
 */
export function DocumentAssistant({
  title,
  documentTypeUid,
  body,
  onDraft,
  onLinkObject,
}: {
  title: string;
  documentTypeUid?: string | null;
  body: string;
  /** Absent on a published revision: there is nothing to draft into, but
   * reviewing one is exactly when a review is worth having. */
  onDraft?: (markdown: string) => void;
  onLinkObject?: (uid: string) => void;
}) {
  const status = useQuery({ queryKey: ["ai-status"], queryFn: aiApi.status });
  const workspaceId = useCurrentWorkspaceId();
  const [findings, setFindings] = useState<ReviewFinding[] | null>(null);
  const [mentions, setMentions] = useState<MentionedObject[]>([]);

  const draft = useMutation({
    mutationFn: () =>
      aiApi.draftDocument({
        title,
        document_type_uid: documentTypeUid ?? null,
        notes: body,
      }),
    onSuccess: (result) => {
      onDraft?.(result.body_markdown);
      setMentions(result.mentioned_objects);
      setFindings(null);
    },
  });

  const review = useMutation({
    mutationFn: () =>
      aiApi.reviewDocument({
        title,
        document_type_uid: documentTypeUid ?? null,
        body_markdown: body,
      }),
    onSuccess: (result) => {
      setFindings(result.findings);
      setMentions(result.mentioned_objects);
    },
  });

  // Rendering nothing when AI is unavailable is why "I don't see Draft
  // with AI" is a mystery rather than a message. Say which of the two
  // reasons it is.
  const ai = status.data;
  if (!ai?.validated) {
    if (!ai?.configured) return null;
    return (
      <p className="mt-2 text-xs text-slate-500">
        AI is configured but unavailable: {ai.reason}{" "}
        {workspaceId && (
          <Link to={`/workspaces/${workspaceId}/ai`} className="text-indigo-600 hover:underline">
            Check the endpoint
          </Link>
        )}
      </p>
    );
  }
  const error = (draft.error ?? review.error) as ApiError | Error | null;

  return (
    <div className="mt-2 rounded border border-dashed border-slate-300 bg-slate-50 p-2">
      <div className="flex flex-wrap items-center gap-2">
        {onDraft && (
        <button
          type="button"
          onClick={() => draft.mutate()}
          disabled={!title.trim() || draft.isPending}
          title={title.trim() ? undefined : "Give the document a title first"}
          className="rounded border border-slate-300 bg-white px-2.5 py-1 text-xs hover:bg-slate-50 disabled:opacity-50"
        >
          {draft.isPending
            ? "Writing…"
            : body.trim()
              ? "Redraft from these notes"
              : "Draft with AI"}
        </button>
        )}
        <button
          type="button"
          onClick={() => review.mutate()}
          disabled={!body.trim() || review.isPending}
          className="rounded border border-slate-300 bg-white px-2.5 py-1 text-xs hover:bg-slate-50 disabled:opacity-50"
        >
          {review.isPending ? "Reading…" : "Review"}
        </button>
        <span className="text-[11px] text-slate-500">
          {onDraft
            ? "A draft replaces what is in the editor; nothing is saved until you save it."
            : "A published revision is read-only — a review changes nothing."}
        </span>
      </div>

      {error && (
        <p className="mt-2 rounded border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-700">
          {(error as ApiError).detail ?? error.message}
        </p>
      )}

      {findings && findings.length === 0 && (
        <p className="mt-2 text-xs text-slate-600">
          Nothing flagged. That is not the same as correct — it is one reading.
        </p>
      )}

      {findings && findings.length > 0 && (
        <ul className="mt-2 space-y-1">
          {findings.map((f, i) => (
            <li key={i} className={`rounded border px-2 py-1 text-xs ${SEVERITY[f.severity]}`}>
              <span className="font-medium uppercase tracking-wide">{f.severity}</span>{" "}
              {f.message}
            </li>
          ))}
        </ul>
      )}

      <Mentions objects={mentions} onLink={onLinkObject} />
    </div>
  );
}
