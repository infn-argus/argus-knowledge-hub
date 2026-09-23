import { useEffect, useState } from "react";
import { completeInfnLogin, infnLoginLabel } from "../api/infnAuth";
import { addOidcProfile, defaultApiBaseUrl } from "../api/session";

/** The page the identity provider sends the browser back to. Exchanges the
 * one-time code for tokens, saves the signed-in person as a profile, and
 * reloads at the root — a full load, not a client-side navigation, so the
 * router starts from "/" instead of the callback address it was opened on. */
export function InfnCallback() {
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    completeInfnLogin()
      .then((user) => {
        const who = user.profile.email ?? user.profile.preferred_username ?? user.profile.sub;
        addOidcProfile(who, defaultApiBaseUrl(), "infn");
        window.location.replace("/");
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <div className="w-full max-w-md space-y-3 rounded-lg border border-slate-200 bg-white p-8 shadow-sm">
        {error ? (
          <>
            <h1 className="text-xl font-semibold text-slate-900">{infnLoginLabel} did not complete</h1>
            <p className="text-sm text-red-600">{error}</p>
            <a href="/" className="text-sm text-slate-600 underline">
              Back to sign-in
            </a>
          </>
        ) : (
          <p className="text-sm text-slate-500">Signing you in…</p>
        )}
      </div>
    </div>
  );
}
