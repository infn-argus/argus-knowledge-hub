import { User, UserManager, WebStorageStateStore } from "oidc-client-ts";

/**
 * Sign-in through the institute's own identity provider (OpenID Connect,
 * Authorization Code with PKCE — the browser never holds a client secret).
 *
 * Nothing here knows which provider that is: it is whatever VITE_OIDC_AUTHORITY
 * names. Locally that is the Keycloak from docker-compose; in production it is
 * INFN's. Both hand back the same thing, an ID token the API verifies against
 * the provider's published keys.
 */
const authority = import.meta.env.VITE_OIDC_AUTHORITY;
const clientId = import.meta.env.VITE_OIDC_CLIENT_ID;

export const infnLoginLabel = import.meta.env.VITE_OIDC_LABEL || "INFN login";
/** Off unless a provider is configured, so a build with none simply doesn't show the button. */
export const infnLoginEnabled = Boolean(authority && clientId);

export const CALLBACK_PATH = "/auth/callback";

let manager: UserManager | null = null;

function getManager(): UserManager {
  if (!authority || !clientId) throw new Error("INFN login is not configured for this build.");
  if (!manager) {
    manager = new UserManager({
      authority,
      client_id: clientId,
      redirect_uri: `${window.location.origin}${CALLBACK_PATH}`,
      post_logout_redirect_uri: `${window.location.origin}/`,
      response_type: "code",
      scope: "openid email profile",
      // localStorage, not the default sessionStorage: a new tab, or a reload
      // after the tab was discarded, must not mean signing in again.
      userStore: new WebStorageStateStore({ store: window.localStorage }),
      automaticSilentRenew: false,
    });
  }
  return manager;
}

/** Sends the browser to the identity provider. Never returns: the page navigates away. */
export async function startInfnLogin(): Promise<void> {
  await getManager().signinRedirect();
}

// React's StrictMode runs an effect twice in development, and the provider's
// answer (a one-time code) can be exchanged only once. Both runs share this.
let callback: Promise<User> | null = null;

/** Called on the way back from the provider, on CALLBACK_PATH. */
export function completeInfnLogin(): Promise<User> {
  if (!callback) callback = getManager().signinRedirectCallback();
  return callback;
}

/** A current ID token for the signed-in person, renewed with the refresh token
 * when it is about to lapse, or null if there is no session left to renew. */
export async function getInfnIdToken(): Promise<string | null> {
  if (!infnLoginEnabled) return null;
  const m = getManager();
  let user = await m.getUser();
  if (!user) return null;
  if (user.expired || (user.expires_in !== undefined && user.expires_in < 30)) {
    try {
      user = await m.signinSilent();
    } catch {
      return null;
    }
  }
  return user?.id_token ?? null;
}

/** Ends the session at the provider too — without that, its own single sign-on
 * cookie would sign the same person straight back in, and switching to another
 * account would be impossible short of clearing the browser. Navigates away
 * when there is a session to end. */
export async function infnSignOut(): Promise<boolean> {
  if (!infnLoginEnabled) return false;
  const m = getManager();
  if (!(await m.getUser())) return false;
  await m.signoutRedirect();
  return true;
}
