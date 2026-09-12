import { useEffect, useState } from "react";

let listener: ((message: string) => void) | null = null;

export function showToast(message: string) {
  listener?.(message);
}

/** Mounted once near the root. Any code can call showToast() to display a message. */
export function ToastHost() {
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    listener = (m) => setMessage(m);
    return () => {
      listener = null;
    };
  }, []);

  useEffect(() => {
    if (!message) return;
    const timer = setTimeout(() => setMessage(null), 4000);
    return () => clearTimeout(timer);
  }, [message]);

  if (!message) return null;

  return (
    <div className="fixed bottom-4 left-1/2 z-50 -translate-x-1/2 rounded-lg bg-slate-900 px-4 py-2 text-sm text-white shadow-lg">
      {message}
    </div>
  );
}
