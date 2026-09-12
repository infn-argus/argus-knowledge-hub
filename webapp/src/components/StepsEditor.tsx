import { DocumentStep } from "../api/types";

export function StepsEditor({
  steps,
  onChange,
}: {
  steps: DocumentStep[];
  onChange: (steps: DocumentStep[]) => void;
}) {
  return (
    <div className="space-y-2">
      {steps.map((step, i) => (
        <div key={i} className="flex items-start gap-2">
          <span className="mt-2 w-5 shrink-0 text-right text-xs text-slate-400">{i + 1}.</span>
          <textarea
            value={step.testo}
            onChange={(e) => {
              const next = [...steps];
              next[i] = { ...next[i], testo: e.target.value };
              onChange(next);
            }}
            rows={1}
            className="flex-1 rounded border border-slate-300 px-2 py-1 text-sm"
          />
          <label className="mt-1.5 flex shrink-0 items-center gap-1 text-xs text-slate-500">
            <input
              type="checkbox"
              checked={step.checklist ?? false}
              onChange={(e) => {
                const next = [...steps];
                next[i] = { ...next[i], checklist: e.target.checked };
                onChange(next);
              }}
            />
            checklist
          </label>
          <label className="mt-1.5 flex shrink-0 items-center gap-1 text-xs text-red-500">
            <input
              type="checkbox"
              checked={step.voce_critica ?? false}
              onChange={(e) => {
                const next = [...steps];
                next[i] = { ...next[i], voce_critica: e.target.checked };
                onChange(next);
              }}
            />
            critical
          </label>
          <button
            type="button"
            onClick={() => onChange(steps.filter((_, idx) => idx !== i))}
            className="mt-1 shrink-0 text-xs text-red-500 hover:text-red-700"
          >
            Remove
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={() => onChange([...steps, { testo: "" }])}
        className="text-xs text-slate-600 hover:text-slate-900"
      >
        + Add step
      </button>
    </div>
  );
}
