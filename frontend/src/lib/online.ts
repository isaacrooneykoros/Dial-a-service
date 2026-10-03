// Online state for the offline banner (10-screens-shared.md, "Offline"): the browser's
// own flag plus what our requests saw. Phones often report "online" on a dead network,
// so a failed fetch counts as offline until the next request gets through.
import { useSyncExternalStore } from "react";

let fetchFailed = false;
const listeners = new Set<() => void>();

function notify() {
  listeners.forEach((listener) => listener());
}

export function reportNetworkFailure(): void {
  if (!fetchFailed) {
    fetchFailed = true;
    notify();
  }
}

export function reportNetworkSuccess(): void {
  if (fetchFailed) {
    fetchFailed = false;
    notify();
  }
}

export function isOnline(): boolean {
  return navigator.onLine && !fetchFailed;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  window.addEventListener("online", listener);
  window.addEventListener("offline", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("online", listener);
    window.removeEventListener("offline", listener);
  };
}

export function useOnline(): boolean {
  return useSyncExternalStore(subscribe, isOnline, () => true);
}
