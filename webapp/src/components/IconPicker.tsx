import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { iconsApi } from "../api/client";
import { useCurrentWorkspaceId } from "../api/useCurrentWorkspaceId";
import { AuthenticatedImage } from "./AuthenticatedImage";

/** Search-as-you-type over the shared icon library, each row showing a
 * thumbnail — the same interaction as RecordPicker, with pictures instead
 * of plain text since picking the wrong-looking icon is the whole risk. */
export function IconPicker({
  onPick,
  placeholder = "Search icons…",
}: {
  onPick: (uid: string) => void;
  placeholder?: string;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const currentWorkspaceId = useCurrentWorkspaceId();
  const icons = useQuery({ queryKey: ["icons"], queryFn: iconsApi.list });

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (icons.data ?? [])
      .filter((i) => !q || i.name.toLowerCase().includes(q))
      .slice(0, 30);
  }, [icons.data, query]);

  return (
    <div className="relative flex-1">
      <input
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder={placeholder}
        className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
      />
      {open && matches.length > 0 && (
        <div className="absolute z-20 mt-1 max-h-64 w-full min-w-[16rem] overflow-y-auto rounded border border-slate-200 bg-white shadow-lg">
          {matches.map((i) => (
            <button
              type="button"
              key={i.uid}
              onMouseDown={(e) => {
                e.preventDefault();
                onPick(i.uid);
                setQuery("");
                setOpen(false);
              }}
              className="flex w-full items-center gap-2 px-2 py-1.5 text-left text-sm hover:bg-slate-50"
            >
              <AuthenticatedImage
                uid={i.uid}
                alt={i.name}
                fetchBlobUrl={iconsApi.fetchBlobUrl}
                className="rounded border border-slate-200 bg-white object-contain"
                style={{ width: 24, height: 24 }}
              />
              <span className="text-slate-800">{i.name}</span>
              {i.is_global && (
                <span className="ml-1 rounded bg-amber-50 px-1 py-0.5 text-[10px] font-medium text-amber-700">
                  global
                </span>
              )}
              {currentWorkspaceId && i.workspace_id !== currentWorkspaceId && (
                <span className="ml-1 rounded bg-slate-100 px-1 py-0.5 text-[10px] text-slate-500">
                  ws {i.workspace_id.slice(0, 8)}
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
