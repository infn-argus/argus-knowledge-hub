import { useQuery } from "@tanstack/react-query";
import { metaApi } from "../../api/client";

const EUPL_URL = "https://interoperable-europe.ec.europa.eu/collection/eupl/eupl-text-eupl-12";

interface ApiVersion {
  version: string;
  commit: string | null;
  built_at: string | null;
  api_version: string;
}

const WEB = {
  version: import.meta.env.VITE_APP_VERSION || "dev",
  commit: import.meta.env.VITE_APP_COMMIT || null,
  builtAt: import.meta.env.VITE_APP_BUILT_AT || null,
};

function release(version: string, commit: string | null, builtAt: string | null) {
  const parts = [version === "dev" ? "development build" : version];
  if (commit) parts.push(commit);
  if (builtAt) parts.push(`built ${new Date(builtAt).toLocaleString()}`);
  return parts.join(" · ");
}

/** Who made the hub, under what licence, and which release is running. */
export function AboutPage() {
  const api = useQuery({ queryKey: ["api-version"], queryFn: () => metaApi.version(), staleTime: 60_000 });
  const mismatch = api.data && api.data.version !== WEB.version;
  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">ARGUS Knowledge Hub</h1>
        <p className="mt-1 text-sm text-slate-500">
          Assets, tickets and documentation for the accelerators, in one place.
        </p>
      </div>
      <dl className="divide-y divide-slate-100 rounded border border-slate-200 bg-white text-sm">
        <Row label="Author">Andrea Michelotti</Row>
        <Row label="Email">
          <a className="text-blue-600 hover:underline" href="mailto:andrea.michelotti@infn.it">
            andrea.michelotti@infn.it
          </a>
        </Row>
        <Row label="Web application">{release(WEB.version, WEB.commit, WEB.builtAt)}</Row>
        <Row label="API">
          {api.data ? (
            <>
              {release(api.data.version, api.data.commit, api.data.built_at)}
              <span className="text-slate-500"> · contract v{api.data.api_version}</span>
            </>
          ) : api.isError ? <span className="text-red-600">not reachable</span> : "…"}
        </Row>
        <Row label="Privacy">
          <a className="text-blue-600 hover:underline" href="/privacy.html" target="_blank" rel="noreferrer">
            How ARGUS and ARGUS Field use data
          </a>
        </Row>
        <Row label="Mobile app">
          ARGUS Field, for Android and iOS: the APK is attached to each{" "}
          <a className="text-blue-600 hover:underline" href="https://github.com/infn-argus/argus-knowledge-hub/releases/latest"
             target="_blank" rel="noreferrer">release</a>
          ; see <a className="text-blue-600 hover:underline" href="/help/mobile-app">Help → The mobile app</a>.
        </Row>
        <Row label="Licence">
          <a className="text-blue-600 hover:underline" href={EUPL_URL} target="_blank" rel="noreferrer">
            European Union Public Licence v. 1.2 (EUPL-1.2)
          </a>
        </Row>
      </dl>
      {mismatch && (
        <p className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          The web application ({WEB.version}) and the API ({api.data?.version}) are different releases: an update
          is probably still rolling out. Reload the page in a few minutes.
        </p>
      )}
      <p className="text-xs text-slate-500">
        The web application, the ARGUS Field mobile application and the API are free software under
        the EUPL-1.2: you may use, copy, modify and redistribute them under its terms, which come
        with the source code.
      </p>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-4 px-4 py-3">
      <dt className="w-36 shrink-0 text-slate-500">{label}</dt>
      <dd className="text-slate-900">{children}</dd>
    </div>
  );
}
