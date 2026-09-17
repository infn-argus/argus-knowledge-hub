import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { iconsApi } from "../../api/client";
import { ApiError } from "../../api/client";
import { useCurrentWorkspaceId } from "../../api/useCurrentWorkspaceId";
import { AuthenticatedImage } from "../../components/AuthenticatedImage";

/** The shared icon library, managed as a visual gallery — unlike every other
 * "pick one" control in the app, browsing icons by their picture rather
 * than a name in a list is the whole point of this page. */
export function IconLibrary() {
  const queryClient = useQueryClient();
  const currentWorkspaceId = useCurrentWorkspaceId();
  const icons = useQuery({ queryKey: ["icons"], queryFn: iconsApi.list });
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploadName, setUploadName] = useState("");
  const [renaming, setRenaming] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["icons"] });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => iconsApi.upload(file, uploadName || undefined),
    onSuccess: () => {
      invalidate();
      setUploadName("");
    },
    onError: () => alert("Upload failed."),
  });

  const updateMutation = useMutation({
    mutationFn: ({ uid, ...input }: { uid: string; name?: string; is_global?: boolean }) =>
      iconsApi.update(uid, input),
    onSuccess: invalidate,
  });

  const deleteMutation = useMutation({
    mutationFn: (uid: string) => iconsApi.delete(uid),
    onSuccess: invalidate,
    onError: (err) => {
      const detail = err instanceof ApiError ? err.detail : null;
      alert(detail ?? "Could not delete this icon.");
    },
  });

  const rows = icons.data ?? [];

  return (
    <div className="max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Icon library</h1>
          <p className="mt-1 text-sm text-slate-500">
            Pictures any object, ticket or document type can use — uploaded once, reused
            everywhere. Removing one here only works once no type is using it anymore.
          </p>
        </div>
      </div>

      <div className="mt-4 flex items-center gap-3 rounded border border-slate-200 bg-white px-3 py-3">
        <input
          value={uploadName}
          onChange={(e) => setUploadName(e.target.value)}
          placeholder="Name (optional)"
          className="rounded border border-slate-300 px-2 py-1.5 text-sm"
        />
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) uploadMutation.mutate(file);
            e.target.value = "";
          }}
        />
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={uploadMutation.isPending}
          className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {uploadMutation.isPending ? "Uploading…" : "Upload icon"}
        </button>
      </div>

      {icons.isLoading && <p className="mt-4 text-sm text-slate-500">Loading…</p>}
      {icons.data && rows.length === 0 && <p className="mt-4 text-sm text-slate-400">No icons yet.</p>}

      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
        {rows.map((icon) => {
          const owned = icon.workspace_id === currentWorkspaceId;
          return (
            <div key={icon.uid} className="rounded-lg border border-slate-200 bg-white p-3">
              <AuthenticatedImage
                uid={icon.uid}
                alt={icon.name}
                fetchBlobUrl={iconsApi.fetchBlobUrl}
                className="mx-auto h-16 w-16 rounded border border-slate-100 object-contain"
              />
              {renaming === icon.uid ? (
                <div className="mt-2 flex items-center gap-1">
                  <input
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    className="w-full rounded border border-slate-300 px-1.5 py-0.5 text-xs"
                    autoFocus
                  />
                  <button
                    type="button"
                    onClick={() => {
                      updateMutation.mutate({ uid: icon.uid, name: renameValue });
                      setRenaming(null);
                    }}
                    className="text-xs text-indigo-600 hover:text-indigo-800"
                  >
                    Save
                  </button>
                </div>
              ) : (
                <p className="mt-2 truncate text-center text-xs font-medium text-slate-700" title={icon.name}>
                  {icon.name}
                </p>
              )}
              <div className="mt-1 flex items-center justify-center gap-1">
                {icon.is_global && (
                  <span className="rounded bg-amber-50 px-1 py-0.5 text-[10px] font-medium text-amber-700">
                    global
                  </span>
                )}
                {!owned && (
                  <span className="rounded bg-slate-100 px-1 py-0.5 text-[10px] text-slate-500">
                    ws {icon.workspace_id.slice(0, 8)}
                  </span>
                )}
              </div>
              {owned && (
                <div className="mt-2 flex items-center justify-center gap-2 text-xs">
                  <button
                    type="button"
                    onClick={() => {
                      setRenaming(icon.uid);
                      setRenameValue(icon.name);
                    }}
                    className="text-slate-500 hover:text-slate-800"
                  >
                    Rename
                  </button>
                  <button
                    type="button"
                    onClick={() => updateMutation.mutate({ uid: icon.uid, is_global: !icon.is_global })}
                    className="text-slate-500 hover:text-slate-800"
                  >
                    {icon.is_global ? "Unshare" : "Share"}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (confirm(`Delete "${icon.name}"? This only works if no type is using it.`)) {
                        deleteMutation.mutate(icon.uid);
                      }
                    }}
                    className="text-red-500 hover:text-red-700"
                  >
                    Delete
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
