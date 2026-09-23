import { firebaseSignOut } from "./firebase";
import { infnSignOut } from "./infnAuth";
import { clearSession, getActiveProfile } from "./session";

/** Signs out of whichever way this browser is signed in, forgets every saved
 * workspace, and returns to the sign-in screen. */
export async function signOut(): Promise<void> {
  const profile = getActiveProfile();
  const viaInfn = profile?.authType === "oidc" && profile.provider === "infn";
  await firebaseSignOut().catch(() => {});
  clearSession();
  // The provider's own logout is a redirect that comes back to the sign-in
  // screen by itself; a reload after it would race the navigation.
  if (viaInfn && (await infnSignOut().catch(() => false))) return;
  window.location.reload();
}
