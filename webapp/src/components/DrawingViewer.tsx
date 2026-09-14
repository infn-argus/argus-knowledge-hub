import { useEffect, useRef, useState } from "react";
import { attachmentsApi } from "../api/client";

/** A CAD drawing, in the browser.
 *
 * Nothing renders DWG directly, so the server converts each one to DXF on
 * upload and this shows that — with layers, dimensions and text, because a
 * drawing stripped of its labels answers no question anyone actually has.
 * The original DWG is always what the Download button gives you.
 *
 * The renderer and its 3D dependency are loaded only when a drawing is
 * opened: they are large, and most visits to a document never open one.
 */
export function DrawingViewer({
  attachmentUid,
  filename,
  onClose,
}: {
  attachmentUid: string;
  filename: string;
  onClose: () => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "failed">("loading");
  const [error, setError] = useState<string | null>(null);
  const [layers, setLayers] = useState<{ name: string; visible: boolean }[]>([]);
  const viewerRef = useRef<{ Destroy: () => void; ShowLayer: (n: string, s: boolean) => void } | null>(
    null,
  );

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;

    (async () => {
      try {
        const [{ DxfViewer }, three, blobUrl] = await Promise.all([
          import("dxf-viewer"),
          import("three"),
          attachmentsApi.fetchBlobUrl(attachmentUid),
        ]);
        objectUrl = blobUrl;
        if (cancelled || !container.current) return;

        const viewer = new DxfViewer(container.current, {
          // A real three.Color: the viewer reads .getHex() off it and also
          // hands it to the renderer, so a stand-in object is silently
          // ignored and you get its default black instead.
          clearColor: new three.Color("#ffffff"),
          autoResize: true,
          // Re-maps entity colours for contrast against that background,
          // so a drawing authored white-on-black stays readable on paper
          // white rather than turning invisible.
          colorCorrection: true,
        } as never);
        viewerRef.current = viewer as never;

        await viewer.Load({
          url: blobUrl,
          // Text in a DXF is glyph references; without a font file the
          // renderer silently draws nothing where the labels should be.
          fonts: ["/fonts/RobotoMono.ttf"],
        });
        if (cancelled) return;

        // The bundled types declare GetLayers() without its nonEmptyOnly
        // argument, so empty layers are filtered here instead.
        const found: string[] = [];
        for (const layer of viewer.GetLayers() ?? []) {
          const name = typeof layer === "string" ? layer : layer.name;
          if (name) found.push(name);
        }
        setLayers(found.map((name) => ({ name, visible: true })));
        setStatus("ready");
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : String(e));
        setStatus("failed");
      }
    })();

    return () => {
      cancelled = true;
      try {
        viewerRef.current?.Destroy();
      } catch {
        // Tearing down a viewer that never finished loading is not an error.
      }
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [attachmentUid]);

  const toggleLayer = (name: string) => {
    setLayers((current) =>
      current.map((layer) => {
        if (layer.name !== name) return layer;
        viewerRef.current?.ShowLayer(name, !layer.visible);
        return { ...layer, visible: !layer.visible };
      }),
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-slate-900/60 p-6" onClick={onClose}>
      <div
        className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-2">
          <div>
            <h2 className="text-sm font-semibold text-slate-900">{filename}</h2>
            <p className="text-xs text-slate-500">
              Scroll to zoom, drag to pan. This is a converted preview — download the original
              to work on it.
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded px-2 py-1 text-sm text-slate-500 hover:bg-slate-100"
          >
            Close
          </button>
        </div>

        <div className="flex min-h-0 flex-1">
          <div className="relative min-w-0 flex-1">
            <div ref={container} className="h-full w-full bg-white" />
            {status === "loading" && (
              <p className="absolute inset-0 flex items-center justify-center text-sm text-slate-400">
                Opening the drawing…
              </p>
            )}
            {status === "failed" && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-8 text-center">
                <p className="text-sm text-slate-700">This drawing could not be displayed.</p>
                <p className="max-w-md text-xs text-slate-500">{error}</p>
                <p className="max-w-md text-xs text-slate-500">
                  The file itself is unaffected — download it and open it in CAD.
                </p>
              </div>
            )}
          </div>

          {layers.length > 0 && (
            <aside className="w-56 shrink-0 overflow-y-auto border-l border-slate-200 p-3">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                Layers
              </p>
              <ul className="mt-1 space-y-0.5">
                {layers.map((layer) => (
                  <li key={layer.name}>
                    <label className="flex items-center gap-2 text-xs text-slate-700">
                      <input
                        type="checkbox"
                        checked={layer.visible}
                        onChange={() => toggleLayer(layer.name)}
                      />
                      <span className="truncate">{layer.name}</span>
                    </label>
                  </li>
                ))}
              </ul>
            </aside>
          )}
        </div>
      </div>
    </div>
  );
}
