import { useSyncExternalStore } from "react";

/** Whether records are shown with their key (SPARC-IP-01, PROC-0042) or by name and title only: a
 *  preference of this browser (the account menu's "Show keys"). */
const KEY = "argus.showKeys";
const listeners = new Set<() => void>();

export function getShowKeys(): boolean {
  try {
    return localStorage.getItem(KEY) !== "0";
  } catch {
    return true;
  }
}

export function setShowKeys(show: boolean): void {
  try {
    localStorage.setItem(KEY, show ? "1" : "0");
  } catch {
    // storage unavailable: the choice lasts until the page is reloaded
  }
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useShowKeys(): boolean {
  return useSyncExternalStore(subscribe, getShowKeys, () => true);
}
