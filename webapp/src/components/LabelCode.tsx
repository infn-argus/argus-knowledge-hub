import JsBarcode from "jsbarcode";
import QRCode from "qrcode";
import { useEffect, useRef, useState } from "react";

/** Label types that have a visual representation. A serial number or an RFID
 * tag is just a value — there's nothing to draw for it. */
export function isScannableType(type: string): boolean {
  return type === "qrcode" || type === "barcode";
}

async function toDataUrl(type: string, value: string, scale: number): Promise<string | null> {
  if (!value) return null;
  if (type === "qrcode") {
    return QRCode.toDataURL(value, { margin: 1, scale, errorCorrectionLevel: "M" });
  }
  if (type === "barcode") {
    const canvas = document.createElement("canvas");
    // CODE128 covers the full ASCII range, so it encodes asset keys and
    // serials that CODE39 would reject.
    JsBarcode(canvas, value, { format: "CODE128", displayValue: false, margin: 4, width: scale });
    return canvas.toDataURL("image/png");
  }
  return null;
}

export function LabelCode({
  type,
  value,
  size = 96,
}: {
  type: string;
  value: string;
  size?: number;
}) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setFailed(false);
    toDataUrl(type, value, 4)
      .then((url) => {
        if (!cancelled) setSrc(url);
      })
      .catch(() => {
        // A value can simply be un-encodable (an empty string, or characters
        // the symbology rejects). That's a property of the data, not an
        // error worth interrupting the page for.
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [type, value]);

  if (!isScannableType(type)) return null;
  if (failed) {
    return <span className="text-xs text-slate-400">not encodable</span>;
  }
  if (!src) return <div style={{ width: size, height: size }} />;
  return (
    <img
      src={src}
      alt={`${type} ${value}`}
      className="bg-white object-contain"
      style={{ width: size, height: type === "barcode" ? size / 2 : size }}
    />
  );
}

/** Prints one label through a hidden iframe: no popup to be blocked, and the
 * app's own stylesheet can't leak into the printed sheet. */
export async function printLabel(
  label: { type: string; value: string },
  asset: { name: string; key: string },
): Promise<void> {
  const src = await toDataUrl(label.type, label.value, 8).catch(() => null);

  const frame = document.createElement("iframe");
  frame.setAttribute("aria-hidden", "true");
  frame.style.position = "fixed";
  frame.style.right = "0";
  frame.style.bottom = "0";
  frame.style.width = "0";
  frame.style.height = "0";
  frame.style.border = "0";
  document.body.appendChild(frame);

  const doc = frame.contentDocument;
  if (!doc) {
    frame.remove();
    return;
  }

  const esc = (s: string) =>
    s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);

  doc.open();
  doc.write(`<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>${esc(asset.key)}</title>
    <style>
      @page { margin: 8mm; }
      body {
        margin: 0;
        font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
        color: #000;
      }
      .label {
        display: flex;
        align-items: center;
        gap: 10mm;
        border: 0.4mm solid #000;
        border-radius: 2mm;
        padding: 6mm;
        width: max-content;
      }
      .code { width: 32mm; }
      .name { font-size: 12pt; font-weight: 600; }
      .key { font-size: 10pt; margin-top: 1mm; }
      .value { font-family: ui-monospace, Menlo, monospace; font-size: 8pt; margin-top: 3mm; word-break: break-all; max-width: 70mm; }
    </style>
  </head>
  <body>
    <div class="label">
      ${src ? `<img class="code" src="${src}" alt="" />` : ""}
      <div>
        <div class="name">${esc(asset.name)}</div>
        <div class="key">${esc(asset.key)}</div>
        <div class="value">${esc(label.value)}</div>
      </div>
    </div>
  </body>
</html>`);
  doc.close();

  const run = () => {
    frame.contentWindow?.focus();
    frame.contentWindow?.print();
    // Left in the DOM briefly: removing it synchronously cancels the print
    // dialog in Safari and Firefox.
    window.setTimeout(() => frame.remove(), 60_000);
  };

  if (frame.contentWindow?.document.readyState === "complete") {
    run();
  } else {
    frame.onload = run;
  }
}
