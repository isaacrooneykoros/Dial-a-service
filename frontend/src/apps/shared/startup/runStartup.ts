// X-01 start-up (10-screens-shared.md; ADR-0003 section 2): load the business config
// and this app's version in parallel, decide where to go, and restore the session.
import { api, unwrap } from "@/api/client";
import { ApiError } from "@/api/errors";
import type { components } from "@/api/schema";
import { PLATFORM, type AppId } from "@/lib/apps";
import { getAccessToken, refreshAccessToken } from "@/lib/auth";
import { APP_VERSION, isBelowMinimum } from "@/lib/version";

export type BusinessConfig = components["schemas"]["BusinessConfig"];

/** After this long without an answer, X-01 shows "Can't connect" with Retry. */
export const STARTUP_TIMEOUT_MS = 8_000;

export type StartupResult =
  | { kind: "ready"; config: BusinessConfig; offline: boolean }
  | { kind: "update_required" }
  | { kind: "maintenance"; config: BusinessConfig }
  | { kind: "not_found" }
  | { kind: "cant_connect" };

// --- Cached config ------------------------------------------------------------------
// localStorage belongs to one address, and each business has its own subdomain, so a
// cached config never crosses businesses. It holds nothing secret.
const CACHE_KEY = "das.business-config.v1";

export function saveCachedConfig(config: BusinessConfig): void {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(config));
  } catch {
    // Storage full or blocked (private mode): carry on without a cache.
  }
}

export function loadCachedConfig(): BusinessConfig | null {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(CACHE_KEY) ?? "null");
    if (isConfig(value)) return value;
  } catch {
    // Unreadable cache: ignore it.
  }
  return null;
}

function isConfig(value: unknown): value is BusinessConfig {
  if (typeof value !== "object" || value === null) return false;
  const { business, branding, maintenance } = value as Record<string, unknown>;
  return [business, branding, maintenance].every((part) => typeof part === "object" && part);
}

// --- The start-up sequence -----------------------------------------------------------

function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => reject(ApiError.network()), ms);
    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (error: unknown) => {
        clearTimeout(timer);
        reject(error);
      },
    );
  });
}

export interface StartupOptions {
  app: AppId;
  /** Try a silent refresh to restore a session. Off for public order pages. */
  restoreSession?: boolean;
  timeoutMs?: number;
}

export async function runStartup({
  app,
  restoreSession = true,
  timeoutMs = STARTUP_TIMEOUT_MS,
}: StartupOptions): Promise<StartupResult> {
  const [configResult, versionResult] = await Promise.allSettled([
    withTimeout(unwrap(api.GET("/api/v1/business/config")), timeoutMs),
    withTimeout(
      unwrap(api.GET("/api/v1/app/version", { params: { query: { app, platform: PLATFORM } } })),
      timeoutMs,
    ),
  ]);

  // X-02 blocks everything, even maintenance.
  if (
    versionResult.status === "fulfilled" &&
    isBelowMinimum(APP_VERSION, versionResult.value.minimum)
  ) {
    return { kind: "update_required" };
  }

  if (configResult.status === "rejected") {
    const error = configResult.reason as unknown;
    // An address no business uses: X-04, which says nothing about what exists.
    if (error instanceof ApiError && error.status === 404) return { kind: "not_found" };
    const cached = loadCachedConfig();
    return cached ? { kind: "ready", config: cached, offline: true } : { kind: "cant_connect" };
  }

  const config = configResult.value;
  saveCachedConfig(config);
  if (config.maintenance.active) return { kind: "maintenance", config };

  if (restoreSession && !getAccessToken()) {
    // The last step: a refresh cookie, if any, gives back the session. Offline or
    // signed out just means the app opens signed out.
    await refreshAccessToken().catch(() => false);
  }
  return { kind: "ready", config, offline: false };
}
