import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { documentsApi } from "../../api/client";

const AUTHORITY_STYLES: Record<string, string> = {
  ufficiale: "bg-indigo-100 text-indigo-700",
  informativo: "bg-slate-100 text-slate-600",
  bozza_interna: "bg-amber-100 text-amber-700",
};

export function DocumentList() {
  const { data, isLoading } = useQuery({ queryKey: ["documents"], queryFn: () => documentsApi.list() });

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Documents</h1>
        <Link
          to="/documents/new"
          className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          New document
        </Link>
      </div>

      {isLoading && <p className="mt-4 text-sm text-slate-500">Loading…</p>}

      {data && (
        <div className="mt-4 overflow-hidden rounded-lg border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-2">Code</th>
                <th className="px-4 py-2">Title</th>
                <th className="px-4 py-2">Authority</th>
                <th className="px-4 py-2">Confidentiality</th>
                <th className="px-4 py-2">Published</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.map((d) => (
                <tr key={d.uid} className="hover:bg-slate-50">
                  <td className="px-4 py-2 font-mono text-xs text-slate-500">
                    <Link to={`/documents/${d.uid}`} className="hover:underline">
                      {d.code}
                    </Link>
                  </td>
                  <td className="px-4 py-2 font-medium text-slate-900">
                    <Link to={`/documents/${d.uid}`} className="hover:underline">
                      {d.title}
                    </Link>
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={`rounded px-2 py-0.5 text-xs ${AUTHORITY_STYLES[d.authority_level] ?? ""}`}
                    >
                      {d.authority_level}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-slate-500">{d.confidentiality}</td>
                  <td className="px-4 py-2">
                    {d.current_revision_uid ? (
                      <span className="rounded bg-green-100 px-2 py-0.5 text-xs text-green-700">
                        published
                      </span>
                    ) : (
                      <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
                        unpublished
                      </span>
                    )}
                  </td>
                </tr>
              ))}
              {data.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
                    No documents yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
