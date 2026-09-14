import { useEffect, useRef, useState } from "react";
import { attachmentsApi } from "../api/client";
import type { Attachment } from "../api/types";

/** A CAD drawing, in the browser.
 *
 * The sheets are rendered on the server and arrive as SVG. That is not a
 * shortcut: the browser DXF renderers do not draw paper space, and an
 * engineering drawing is usually *entirely* paper space — the sheet, its
 * title block, its dimensions. It also means opening a drawing fetches a
 * picture rather than a twenty-megabyte DXF.
 *
 * The original DWG is always what Download gives you.
 */
export function DrawingViewer({
  sheets,
  filename,
  onClose,
}: {
  sheets: Attachment[];
  filename: string;
  onClose: () => void;
}) {
  const [index, setIndex] = useState(0);
  const [svg, setSvg] = useState<string | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "failed">("loading");
  const [view, setView] = useState({ x: 0, y: 0, scale: 1 });
  const drag = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null);

  const sheet = sheets[index];

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    setSvg(null);
    setView({ x: 0, y: 0, scale: 1 });

    attachmentsApi
      .fetchText(sheet.uid)
      .then((text) => {
        if (cancelled) return;
        setSvg(text);
        setStatus("ready");
      })
      .catch(() => {
        if (!cancelled) setStatus("failed");
      });

    return () => {
      cancelled = true;
    };
  }, [sheet.uid]);

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-slate-900/60 p-6" onClick={onClose}>
      <div
        className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-4 border-b border-slate-200 px-4 py-2">
          <div className="min-w-0">
            <h2 className="truncate text-sm font-semibold text-slate-900">{filename}</h2>
            <p className="text-xs text-slate-500">
              Drag to pan, scroll to zoom. A converted preview — download the original to work
              on it.
            </p>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            {sheets.length > 1 && (
              <div className="flex gap-1 rounded bg-slate-100 p-0.5">
                {sheets.map((s, i) => (
                  <button
                    key={s.uid}
                    type="button"
                    onClick={() => setIndex(i)}
                    title={s.filename}
                    className={`max-w-[10rem] truncate rounded px-2 py-0.5 text-xs ${
                      i === index ? "bg-white text-slate-900 shadow-sm" : "text-slate-500"
                    }`}
                  >
                    {/* The sheet's own name, which is what the drawing calls
                        it — "a_1", "Sheet 2", "VISTA1". */}
                    {s.filename.replace(/^.*\(([^)]*)\)\.svg$/, "$1")}
                  </button>
                ))}
              </div>
            )}
            <button
              type="button"
              onClick={() => setView({ x: 0, y: 0, scale: 1 })}
              className="rounded px-2 py-1 text-xs text-slate-500 hover:bg-slate-100"
            >
              Reset
            </button>
            <button
              onClick={onClose}
              className="rounded px-2 py-1 text-sm text-slate-500 hover:bg-slate-100"
            >
              Close
            </button>
          </div>
        </div>

        <div
          className="relative min-h-0 flex-1 cursor-grab overflow-hidden bg-white active:cursor-grabbing"
          onWheel={(e) => {
            const factor = e.deltaY > 0 ? 1 / 1.15 : 1.15;
            setView((v) => ({ ...v, scale: Math.min(40, Math.max(0.2, v.scale * factor)) }));
          }}
          onPointerDown={(e) => {
            drag.current = { x: e.clientX, y: e.clientY, ox: view.x, oy: view.y };
            e.currentTarget.setPointerCapture(e.pointerId);
          }}
          onPointerMove={(e) => {
            const d = drag.current;
            if (!d) return;
            setView((v) => ({ ...v, x: d.ox + (e.clientX - d.x), y: d.oy + (e.clientY - d.y) }));
          }}
          onPointerUp={() => {
            drag.current = null;
          }}
        >
          {status === "loading" && (
            <p className="absolute inset-0 flex items-center justify-center text-sm text-slate-400">
              Opening the drawing…
            </p>
          )}
          {status === "failed" && (
            <p className="absolute inset-0 flex items-center justify-center px-8 text-center text-sm text-slate-500">
              This sheet could not be loaded. The file itself is unaffected — download it and
              open it in CAD.
            </p>
          )}
          {svg && (
            <div
              className="flex h-full w-full items-center justify-center"
              style={{
                transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})`,
              }}
              // Produced by our own renderer from the uploaded drawing —
              // not markup anybody typed.
              dangerouslySetInnerHTML={{ __html: svg }}
            />
          )}
        </div>
      </div>
    </div>
  );
}
