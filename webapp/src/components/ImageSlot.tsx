import { useRef } from "react";
import { AuthenticatedImage } from "./AuthenticatedImage";

/** A picture with the controls to change it: an object's avatar, a type's
 * icon. Empty, it shows the initial over a tinted square so a list of objects
 * still reads as a list of distinct things rather than a column of blanks. */
export function ImageSlot({
  attachmentUid,
  fallbackText,
  alt,
  size = 64,
  rounded = "rounded",
  busy = false,
  onPick,
  onClear,
  fetchBlobUrl,
  extra,
}: {
  attachmentUid: string | null;
  fallbackText: string;
  alt: string;
  size?: number;
  rounded?: string;
  busy?: boolean;
  onPick: (file: File) => void;
  onClear: () => void;
  /** Defaults to /v1/attachments/{uid}; pass iconsApi.fetchBlobUrl to show a
   * picture from the shared icon library instead of a plain attachment. */
  fetchBlobUrl?: (uid: string) => Promise<string>;
  /** An extra action alongside Upload/Remove — e.g. "Choose from library". */
  extra?: React.ReactNode;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="flex items-center gap-3">
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onPick(file);
          // Reset so picking the same file twice still fires a change.
          e.target.value = "";
        }}
      />
      {attachmentUid ? (
        <AuthenticatedImage
          uid={attachmentUid}
          alt={alt}
          fetchBlobUrl={fetchBlobUrl}
          className={`${rounded} border border-slate-200 bg-white object-contain`}
          style={{ width: size, height: size }}
        />
      ) : (
        <div
          className={`${rounded} flex items-center justify-center border border-dashed border-slate-300 bg-slate-50 font-semibold text-slate-400`}
          style={{ width: size, height: size, fontSize: size / 3 }}
          aria-hidden="true"
        >
          {fallbackText.slice(0, 1).toUpperCase()}
        </div>
      )}
      <div className="flex flex-col items-start gap-1">
        <button
          type="button"
          disabled={busy}
          onClick={() => inputRef.current?.click()}
          className="text-xs text-indigo-600 hover:text-indigo-800 disabled:text-slate-400"
        >
          {busy ? "Uploading…" : attachmentUid ? "Replace" : "Upload"}
        </button>
        {attachmentUid && (
          <button
            type="button"
            disabled={busy}
            onClick={onClear}
            className="text-xs text-red-500 hover:text-red-700 disabled:text-slate-400"
          >
            Remove
          </button>
        )}
        {extra}
      </div>
    </div>
  );
}
