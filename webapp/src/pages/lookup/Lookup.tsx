/** `/lookup/<key or URL>`: an old Jira key, Jira URL, Insight key or objectId
 * goes to the ARGUS record it became; one never migrated shows where it can
 * still be read. */
import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, ledgerApi } from "../../api/client";

export function LookupPage() {
  const params = useParams();
  const identifier = params["*"] ?? "";
  const navigate = useNavigate();
  const hit = useQuery({ queryKey: ["lookup", identifier], queryFn: () => ledgerApi.lookup(identifier), retry: false });

  useEffect(() => {
    if (hit.data) navigate(hit.data.path, { replace: true });
  }, [hit.data, navigate]);

  const detail =
    hit.error instanceof ApiError
      ? ((hit.error.body as { detail?: { status?: string; archive?: string | null } } | null)?.detail ?? null)
      : null;
  return (
    <div className="mx-auto max-w-xl py-10">
      <p className="text-xs uppercase tracking-wide text-slate-400">Looking up</p>
      <h1 className="break-all font-mono text-lg text-slate-900">{identifier}</h1>
      {hit.isLoading && <p className="mt-4 text-sm text-slate-500">Resolving…</p>}
      {detail?.status === "not migrated" && (
        <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <p className="font-medium">Not migrated to ARGUS.</p>
          {detail.archive ? (
            <p className="mt-1">
              It can still be read in the archive:{" "}
              <a href={detail.archive} className="underline" target="_blank" rel="noreferrer">
                {detail.archive}
              </a>
            </p>
          ) : (
            <p className="mt-1">No archive location is recorded for it.</p>
          )}
        </div>
      )}
      <Link to="/" className="mt-6 inline-block text-sm text-indigo-700 hover:underline">
        Back to the cockpit
      </Link>
    </div>
  );
}
