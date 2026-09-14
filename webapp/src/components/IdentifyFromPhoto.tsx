import { useMutation, useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, aiApi } from "../api/client";
import type { PhotoIdentification } from "../api/types";

const CONFIDENCE_STYLE: Record<string, string> = {
  high: "bg-green-100 text-green-700",
  medium: "bg-amber-100 text-amber-700",
  low: "bg-slate-100 text-slate-600",
};

/** Identify equipment from a photograph, as a draft for the form.
 *
 * Somebody standing at a rack knows more than they will type. A photo
 * carries the kind of thing, often a manufacturer and model, and — if the
 * label is in shot — the key that ties it to what is already recorded.
 *
 * Nothing here fills the form on its own: what came back is shown first,
 * and "Use this" is a button somebody presses.
 */
export function IdentifyFromPhoto({
  onUse,
}: {
  onUse: (result: PhotoIdentification) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const status = useQuery({ queryKey: ["ai-status"], queryFn: aiApi.status });

  const identify = useMutation({
    mutationFn: (file: File) => aiApi.identifyObject(file),
  });

  const ai = status.data;
  if (!ai?.validated || !ai.has_vision) return null;

  const result = identify.data;

  return (
    <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-slate-700">Identify from a photo</p>
          <p className="text-xs text-slate-500">
            A picture of the equipment — with its label in shot, if you can.
          </p>
        </div>
        <button
          type="button"
          onClick={() => input.current?.click()}
          disabled={identify.isPending}
          className="shrink-0 rounded border border-slate-300 bg-white px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50"
        >
          {identify.isPending ? "Looking…" : "Choose a photo"}
        </button>
        <input
          ref={input}
          type="file"
          accept="image/*"
          capture="environment"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (!file) return;
            setPreview(URL.createObjectURL(file));
            identify.mutate(file);
          }}
        />
      </div>

      {identify.isError && (
        <p className="mt-2 rounded border border-red-200 bg-red-50 px-2 py-1.5 text-xs text-red-700">
          {(identify.error as ApiError).detail ?? (identify.error as Error).message}
        </p>
      )}

      {result && (
        <div className="mt-3 flex gap-3">
          {preview && (
            <img
              src={preview}
              alt="The photograph"
              className="h-28 w-28 shrink-0 rounded border border-slate-200 object-cover"
            />
          )}
          <div className="min-w-0 flex-1 text-sm">
            {result.error ? (
              <p className="text-slate-600">{result.error}</p>
            ) : (
              <>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-slate-900">
                    {result.name ?? "Not identified"}
                  </span>
                  {result.type_name && (
                    <span className="rounded bg-indigo-50 px-2 py-0.5 text-xs text-indigo-700">
                      {result.type_name}
                    </span>
                  )}
                  <span
                    className={`rounded px-2 py-0.5 text-[10px] uppercase tracking-wide ${
                      CONFIDENCE_STYLE[result.confidence]
                    }`}
                  >
                    {result.confidence} confidence
                  </span>
                </div>

                {result.description && (
                  <p className="mt-1 text-xs text-slate-600">{result.description}</p>
                )}

                {(result.manufacturer || result.model || result.serial) && (
                  <p className="mt-1 text-xs text-slate-500">
                    {[result.manufacturer, result.model, result.serial]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                )}

                {result.matches.length > 0 && (
                  <p className="mt-2 text-xs text-slate-700">
                    Already recorded:{" "}
                    {result.matches.map((m, i) => (
                      <span key={m.uid}>
                        {i > 0 && ", "}
                        <Link to={`/assets/${m.uid}`} className="text-indigo-600 hover:underline">
                          {m.name} ({m.key})
                        </Link>
                      </span>
                    ))}
                    {" — this may be that object rather than a new one."}
                  </p>
                )}

                {result.unmatched_keys.length > 0 && (
                  <p className="mt-1 text-xs text-slate-500">
                    Read from the label but not in the inventory:{" "}
                    {result.unmatched_keys.join(", ")}
                  </p>
                )}

                <button
                  type="button"
                  onClick={() => onUse(result)}
                  className="mt-2 rounded bg-slate-900 px-3 py-1 text-xs text-white hover:bg-slate-800"
                >
                  Use this
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
