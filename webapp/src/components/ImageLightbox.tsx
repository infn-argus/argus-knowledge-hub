import { useEffect, useState } from "react";
import { AuthenticatedImage } from "./AuthenticatedImage";

/** One image, full size over the page: closed by Esc, the button or a click outside it. */
export function ImageLightbox({ uid, alt, onClose }: { uid: string; alt: string; onClose: () => void }) {
  useEffect(() => {
    const key = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [onClose]);
  return (
    <div
      role="dialog"
      aria-label={alt || "Image"}
      onClick={onClose}
      className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-slate-900/80 p-4"
    >
      <button
        type="button"
        onClick={onClose}
        className="absolute right-4 top-4 rounded bg-white/90 px-3 py-1 text-sm text-slate-800 hover:bg-white"
      >
        Close
      </button>
      <div onClick={(e) => e.stopPropagation()} className="max-h-full max-w-full">
        <AuthenticatedImage uid={uid} alt={alt} className="max-h-[85vh] max-w-[95vw] rounded bg-white object-contain" />
        {alt && <p className="mt-2 text-center text-sm text-white">{alt}</p>}
      </div>
    </div>
  );
}

/** A grid of small images; each opens full size. */
export function ImageGallery({ images }: { images: { uid: string; filename: string }[] }) {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      {images.map((img) => (
        <GalleryItem key={img.uid} uid={img.uid} filename={img.filename} />
      ))}
    </div>
  );
}


function GalleryItem({ uid, filename }: { uid: string; filename: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        title={filename}
        className="group overflow-hidden rounded border border-slate-200 bg-slate-50 hover:border-indigo-300"
      >
        <AuthenticatedImage uid={uid} alt={filename} className="h-28 w-full object-cover transition group-hover:opacity-90" />
        <span className="block truncate px-1 py-0.5 text-left text-[11px] text-slate-500">{filename}</span>
      </button>
      {open && <ImageLightbox uid={uid} alt={filename} onClose={() => setOpen(false)} />}
    </>
  );
}
