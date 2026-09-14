import { useMutation, useQuery } from "@tanstack/react-query";
import { ApiError, aiApi } from "../api/client";
import type { DraftTicketResult } from "../api/types";

/** Fills in the fields a fault report implies.
 *
 * These are the fields the hub reasons over — category, operational
 * impact, how it was noticed, cause and cure — and the ones a tracker
 * never had, so 524 imported tickets carry the answers only in their
 * prose. Reading them out is work worth doing; deciding them is not.
 *
 * Values arrive in the form. Nothing is saved, nothing is overwritten,
 * and a field the report does not actually answer stays empty rather than
 * being guessed: a fabricated root cause gets read as a finding.
 */
export function TicketAssistant({
  title,
  description,
  onFields,
}: {
  title: string;
  description: string;
  onFields: (result: DraftTicketResult) => void;
}) {
  const status = useQuery({ queryKey: ["ai-status"], queryFn: aiApi.status });

  const draft = useMutation({
    mutationFn: () => aiApi.draftTicket({ title, description }),
    onSuccess: onFields,
  });

  if (!status.data?.validated) return null;
  const result = draft.data;

  return (
    <div className="rounded border border-dashed border-slate-300 bg-slate-50 p-2">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => draft.mutate()}
          disabled={(!title.trim() && !description.trim()) || draft.isPending}
          className="rounded border border-slate-300 bg-white px-2.5 py-1 text-xs hover:bg-slate-50 disabled:opacity-50"
        >
          {draft.isPending ? "Reading…" : "Fill in from the report"}
        </button>
        <span className="text-[11px] text-slate-500">
          Reads the description for category, impact, cause and the objects it names.
        </span>
      </div>

      {draft.isError && (
        <p className="mt-2 rounded border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-700">
          {(draft.error as ApiError).detail ?? (draft.error as Error).message}
        </p>
      )}

      {result && (
        <div className="mt-2 text-xs text-slate-600">
          {[
            result.category && `category ${result.category}`,
            result.impact && `impact ${result.impact}`,
            result.detected_by && `detected by ${result.detected_by}`,
            result.system && `system ${result.system}`,
            result.root_cause && "a root cause",
            result.corrective_action && "a corrective action",
          ].filter(Boolean).length === 0 ? (
            <p>
              The report doesn’t say enough to fill anything in — which is an answer, not a
              failure.
            </p>
          ) : (
            <p>
              Filled in:{" "}
              {[
                result.category && "category",
                result.impact && "impact",
                result.detected_by && "detected by",
                result.system && "system",
                result.subsystem && "subsystem",
                result.root_cause && "root cause",
                result.corrective_action && "corrective action",
              ]
                .filter(Boolean)
                .join(", ")}
              . Empty fields are ones the report doesn’t answer.
            </p>
          )}
          {result.mentioned_objects.length > 0 && (
            <p className="mt-1">
              Objects named:{" "}
              {result.mentioned_objects.map((o) => o.name).join(", ")} — added to the
              objects field.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
