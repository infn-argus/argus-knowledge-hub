import { useEffect, useState } from "react";
import { attachmentsApi } from "../api/client";

export function AuthenticatedImage({
  uid,
  alt,
  className,
}: {
  uid: string;
  alt: string;
  className?: string;
}) {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    attachmentsApi
      .fetchBlobUrl(uid)
      .then((url) => {
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        objectUrl = url;
        setSrc(url);
      })
      .catch(() => setSrc(null));
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [uid]);

  if (!src) {
    return (
      <div
        className={`flex items-center justify-center bg-slate-100 text-slate-400 ${className ?? ""}`}
      >
        …
      </div>
    );
  }
  return <img src={src} alt={alt} className={className} />;
}
