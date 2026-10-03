// The access token store and session refresh (ADR-0003 section 4, ADR-0002).
//
// The access token lives only in this module's memory: never localStorage or
// sessionStorage, where any injected script could read it. The refresh token is an
// httpOnly cookie on /api/v1/auth, so JavaScript never sees it; a page reload gets a
// new access token through a silent refresh (X-01).
import { useSyncExternalStore } from "react";

import { ApiError } from "@/api/errors";
import { appForPath, loginPathForApp } from "@/lib/apps";

export const REFRESH_URL = "/api/v1/auth/refresh";

let accessToken: string | null = null;
const listeners = new Set<() => void>();

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  if (token === accessToken) return;
  accessToken = token;
  listeners.forEach((listener) => listener());
}

/** For useSyncExternalStore: re-render when someone signs in or out. */
export function subscribeAccessToken(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** The current access token, re-rendering on sign-in and sign-out. */
export function useAccessToken(): string | null {
  return useSyncExternalStore(subscribeAccessToken, getAccessToken, () => null);
}

// --- Single-flight refresh ----------------------------------------------------------

let inflight: Promise<boolean> | null = null;

/**
 * Get a new access token from the refresh cookie. Requests that fail with 401 at the
 * same time share one refresh: the backend rotates the refresh token on every use and
 * treats reuse of an old one as theft, so two parallel refreshes would sign the user out.
 *
 * Resolves true with a new token, false when the session has ended. Throws ApiError
 * (network) when the server can't be reached, so being offline never signs anyone out.
 */
export function refreshAccessToken(): Promise<boolean> {
  inflight ??= doRefresh().finally(() => {
    inflight = null;
  });
  return inflight;
}

async function doRefresh(): Promise<boolean> {
  let response: Response;
  try {
    response = await fetch(REFRESH_URL, {
      method: "POST",
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
  } catch {
    throw ApiError.network();
  }
  // Throttled or a server fault: the session may be fine, so keep it and report the error.
  if (response.status >= 500 || response.status === 429) {
    throw await ApiError.fromResponse(response);
  }
  if (!response.ok) {
    setAccessToken(null);
    return false;
  }
  const body = (await response.json().catch(() => null)) as { access?: unknown } | null;
  if (typeof body?.access !== "string") {
    setAccessToken(null);
    return false;
  }
  setAccessToken(body.access);
  return true;
}

// --- Session expired ----------------------------------------------------------------

/** The log-in page (X-10) of the app a path belongs to. */
export function loginPathFor(pathname: string): string {
  return loginPathForApp(appForPath(pathname));
}

/**
 * Only same-site paths are allowed as a return address, so a crafted link like
 * /staff/login?returnTo=https://evil.example can't send someone elsewhere after login.
 */
export function safeReturnTo(value: string | null | undefined, fallback: string): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) {
    return fallback;
  }
  return value;
}

type Navigate = (url: string) => void;

let navigate: Navigate = (url) => window.location.assign(url);

/** The app registers the router's navigate, so going to X-10 keeps in-memory drafts. */
export function setSessionExpiredNavigator(next: Navigate): void {
  navigate = next;
}

/** Send the user to X-10, coming back to this page after logging in. */
export function handleSessionExpired(): void {
  setAccessToken(null);
  const { pathname, search } = window.location;
  const login = loginPathFor(pathname);
  if (pathname === login) return;
  navigate(`${login}?returnTo=${encodeURIComponent(pathname + search)}`);
}
