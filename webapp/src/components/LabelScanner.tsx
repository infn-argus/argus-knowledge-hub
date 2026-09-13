import { useCallback, useEffect, useRef, useState } from "react";

/** Chrome and Edge decode barcodes natively; Safari and Firefox don't, and
 * pulling a decoder into the main bundle for a feature most sessions never
 * open isn't worth ~300KB — so the fallback is imported only when the
 * scanner actually runs. */
interface DetectedBarcode {
  rawValue: string;
}
type BarcodeDetectorLike = { detect(source: CanvasImageSource): Promise<DetectedBarcode[]> };
type BarcodeDetectorCtor = {
  new (options?: { formats?: string[] }): BarcodeDetectorLike;
  getSupportedFormats?: () => Promise<string[]>;
};

const WANTED_FORMATS = [
  "qr_code",
  "code_128",
  "code_39",
  "data_matrix",
  "ean_13",
  "ean_8",
  "itf",
  "upc_a",
  "upc_e",
];

function nativeDetectorCtor(): BarcodeDetectorCtor | null {
  const ctor = (window as unknown as { BarcodeDetector?: BarcodeDetectorCtor }).BarcodeDetector;
  return typeof ctor === "function" ? ctor : null;
}

export function LabelScanner({
  onScan,
  onClose,
  title = "Scan a code",
}: {
  onScan: (value: string) => void;
  onClose: () => void;
  title?: string;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(true);
  // A scan fires exactly once: the decode loop keeps running for a frame or
  // two after a hit, and a duplicated onScan would add the label twice.
  const doneRef = useRef(false);

  const handleHit = useCallback(
    (value: string) => {
      if (doneRef.current || !value) return;
      doneRef.current = true;
      onScan(value);
    },
    [onScan],
  );

  useEffect(() => {
    let stream: MediaStream | null = null;
    let frame = 0;
    let cancelled = false;
    let stopFallback: (() => void) | null = null;

    async function start() {
      if (!window.isSecureContext) {
        setError("The camera needs a secure connection (https or localhost).");
        setStarting(false);
        return;
      }
      if (!navigator.mediaDevices?.getUserMedia) {
        setError("This browser doesn't expose a camera to web pages.");
        setStarting(false);
        return;
      }

      try {
        stream = await navigator.mediaDevices.getUserMedia({
          // The rear camera is the one pointed at equipment; browsers fall
          // back to whatever they have when there's no choice.
          video: { facingMode: { ideal: "environment" } },
          audio: false,
        });
      } catch {
        setError("No camera available, or permission was declined.");
        setStarting(false);
        return;
      }
      if (cancelled) {
        stream.getTracks().forEach((t) => t.stop());
        return;
      }

      const video = videoRef.current;
      if (!video) return;
      video.srcObject = stream;
      await video.play().catch(() => undefined);
      setStarting(false);

      const ctor = nativeDetectorCtor();
      if (ctor) {
        let formats = WANTED_FORMATS;
        try {
          const supported = await ctor.getSupportedFormats?.();
          if (supported) formats = WANTED_FORMATS.filter((f) => supported.includes(f));
        } catch {
          // Keep the full list; an unsupported format is ignored anyway.
        }
        const detector = new ctor({ formats });
        const tick = async () => {
          if (cancelled || doneRef.current) return;
          try {
            const codes = await detector.detect(video);
            if (codes.length > 0) {
              handleHit(codes[0].rawValue);
              return;
            }
          } catch {
            // A frame can fail to decode while the video is still settling.
          }
          frame = requestAnimationFrame(tick);
        };
        frame = requestAnimationFrame(tick);
        return;
      }

      try {
        const { BrowserMultiFormatReader } = await import("@zxing/browser");
        if (cancelled) return;
        const reader = new BrowserMultiFormatReader();
        const controls = await reader.decodeFromVideoElement(video, (result) => {
          if (result) handleHit(result.getText());
        });
        stopFallback = () => controls.stop();
      } catch {
        setError("Could not start the barcode decoder in this browser.");
      }
    }

    start();
    return () => {
      cancelled = true;
      cancelAnimationFrame(frame);
      stopFallback?.();
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, [handleHit]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 p-4">
      <div className="w-full max-w-md rounded-lg bg-white p-4 shadow-xl">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
          <button
            onClick={onClose}
            className="text-sm text-slate-500 hover:text-slate-900"
            aria-label="Close scanner"
          >
            ✕
          </button>
        </div>

        <div className="relative mt-3 overflow-hidden rounded bg-slate-900">
          <video
            ref={videoRef}
            className="h-64 w-full object-cover"
            muted
            playsInline
            aria-label="Camera preview"
          />
          {/* A frame to aim with — the decoder reads the whole image, this is
              only there to tell people where to point. */}
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <div className="h-40 w-40 rounded border-2 border-white/70" />
          </div>
          {starting && !error && (
            <p className="absolute inset-0 flex items-center justify-center text-xs text-white">
              Starting the camera…
            </p>
          )}
        </div>

        {error ? (
          <p className="mt-3 text-xs text-red-600">{error}</p>
        ) : (
          <p className="mt-3 text-xs text-slate-500">
            Point the camera at a QR code or barcode. Press Esc to close.
          </p>
        )}
      </div>
    </div>
  );
}
