import { initializeApp } from "firebase/app";
import {
  GoogleAuthProvider,
  getAuth,
  onAuthStateChanged,
  signInWithPopup,
  signOut,
} from "firebase/auth";

// Public/safe to ship in frontend JS — these identify the project, they are
// not secrets. Web app registered under project seraphic-camera-479521-s5
// (the same Firebase project the Flutter app already uses).
const firebaseConfig = {
  apiKey: "AIzaSyCVRXZrnOUMneD0qlHDPfZyFFKZqqXZf44",
  authDomain: "seraphic-camera-479521-s5.firebaseapp.com",
  projectId: "seraphic-camera-479521-s5",
  appId: "1:3066477772:web:f325e33c5e1c913b925669",
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);

// auth.currentUser is null immediately after page load until the SDK finishes
// restoring the persisted session from IndexedDB — reading it synchronously
// on a fresh load/reload races that restoration and wrongly looks signed-out.
// Wait for the first onAuthStateChanged firing (whichever way it resolves)
// once, then every later call sees the real state instantly.
const authReady = new Promise<void>((resolve) => {
  const unsubscribe = onAuthStateChanged(auth, () => {
    unsubscribe();
    resolve();
  });
});

export async function signInWithGoogle() {
  const provider = new GoogleAuthProvider();
  // Always show the account chooser instead of silently reusing whichever
  // Google account this browser last used — otherwise there's no way to
  // switch accounts short of signing out of Google in the browser itself.
  provider.setCustomParameters({ prompt: "select_account" });
  const result = await signInWithPopup(auth, provider);
  return result.user;
}

export async function firebaseSignOut() {
  await signOut(auth);
}

export async function getFreshIdToken(): Promise<string | null> {
  await authReady;
  const user = auth.currentUser;
  if (!user) return null;
  return user.getIdToken();
}
