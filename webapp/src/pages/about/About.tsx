const EUPL_URL = "https://interoperable-europe.ec.europa.eu/collection/eupl/eupl-text-eupl-12";

/** Who made the hub and under what licence. */
export function AboutPage() {
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
        <Row label="Licence">
          <a className="text-blue-600 hover:underline" href={EUPL_URL} target="_blank" rel="noreferrer">
            European Union Public Licence v. 1.2 (EUPL-1.2)
          </a>
        </Row>
      </dl>
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
