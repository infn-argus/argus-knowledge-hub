import { ApiError, problemText } from "../../../api/client";
import { infnLoginEnabled, startStepUp } from "../../../api/infnAuth";
import { getActiveProfile } from "../../../api/session";

/** An error, and when it is a step-up refusal (the sign-in is too old for a sensitive change), the way to
 *  prove it is you again: a fresh sign-in, back to this page, then repeat the action. */
export function ProblemWithStepUp({ error }: { error: unknown }) {
  const body = error instanceof ApiError ? (error.body as { detail?: { code?: string } } | undefined) : undefined;
  if (body?.detail?.code !== "step_up_required") {
    return <span className="text-xs text-rose-700">{problemText(error)}</span>;
  }
  const keycloak = infnLoginEnabled && getActiveProfile()?.provider === "infn";
  return (
    <span className="inline-flex flex-wrap items-center gap-2 text-xs text-amber-800">
      This change needs a recent sign-in, to be sure it is you.
      {keycloak ? (
        <button type="button" className="rounded bg-amber-600 px-2 py-1 font-medium text-white hover:bg-amber-700"
                onClick={() => void startStepUp(window.location.pathname + window.location.search)}>
          Sign in again to confirm it is you
        </button>
      ) : (
        <span>Sign out and sign in again, then repeat it within five minutes.</span>
      )}
    </span>
  );
}
