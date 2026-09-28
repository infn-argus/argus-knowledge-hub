import { useQuery } from "@tanstack/react-query";
import { Navigate, useLocation } from "react-router-dom";
import { ApiError, linksApi } from "../../api/client";

/** The stable universal links (/asset/<uid>, /position/<uid>, /installation/<uid>, /document/<uid>,
 * /ticket/<key>, /review/<uid>): the same URL opens the record here and in the field client
 * (asset-model-revision §24.7). A record the viewer cannot read looks exactly like a missing one. */
export function LinkRedirect() {
  const { pathname } = useLocation();
  const q = useQuery({ queryKey: ["link", pathname], queryFn: () => linksApi.resolve(pathname), retry: false });
  if (q.data) return <Navigate to={q.data.web_path} replace />;
  if (q.isError) {
    return (
      <div className="max-w-xl">
        <h1 className="text-xl font-semibold text-slate-900">Not found</h1>
        <p className="mt-2 text-sm text-slate-600">
          {q.error instanceof ApiError && q.error.status === 404
            ? "This link does not open anything you can see in ARGUS."
            : "The link could not be opened."}
        </p>
      </div>
    );
  }
  return <p className="text-sm text-slate-500">Opening…</p>;
}
