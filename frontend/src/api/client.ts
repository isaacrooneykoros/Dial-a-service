// The typed API client (ADR-0003 section 3). Types come from src/api/schema.d.ts,
// generated from backend/openapi.yaml with `npm run api:gen`.
//
// Every request goes through apiFetch, which:
// 1. adds the in-memory access token;
// 2. adds Accept-Language, so server messages come back in the user's language;
// 3. adds an Idempotency-Key to mutating requests that don't carry one already
//    (screens pass their action's key, so a retry reuses it: src/lib/idempotency.ts);
// 4. on 401, refreshes the session once (shared by parallel requests) and retries;
//    if the session has ended, goes to X-10 and comes back afterwards;
// 5. turns a failed connection into ApiError("network") and feeds the offline banner.
import createClient from "openapi-fetch";

import { ApiError } from "@/api/errors";
import type { paths } from "@/api/schema";
import i18n from "@/i18n";
import { getAccessToken, handleSessionExpired, refreshAccessToken } from "@/lib/auth";
import { IDEMPOTENCY_HEADER, newIdempotencyKey } from "@/lib/idempotency";
import { reportNetworkFailure, reportNetworkSuccess } from "@/lib/online";

const MUTATING = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/** Sign-in endpoints answer 401 for their own reasons; refreshing wouldn't help. */
function isAuthEndpoint(url: string): boolean {
  return new URL(url, window.location.origin).pathname.startsWith("/api/v1/auth/");
}

function prepare(request: Request): Request {
  const headers = new Headers(request.headers);
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  else headers.delete("Authorization");
  headers.set("Accept-Language", i18n.language || "en");
  if (MUTATING.has(request.method) && !headers.has(IDEMPOTENCY_HEADER)) {
    headers.set(IDEMPOTENCY_HEADER, newIdempotencyKey());
  }
  return new Request(request, { headers, credentials: "same-origin" });
}

async function send(request: Request): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(request);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    reportNetworkFailure();
    throw ApiError.network();
  }
  reportNetworkSuccess();
  return response;
}

export async function apiFetch(input: Request): Promise<Response> {
  const tokenSent = getAccessToken();
  const request = prepare(input);
  // Kept unread, so the retry after a refresh can send the same body and key.
  const retry = request.clone();
  const response = await send(request);
  if (response.status !== 401 || isAuthEndpoint(request.url)) return response;

  // Another request refreshed while this one was out: just retry with the new token.
  const current = getAccessToken();
  if (current && current !== tokenSent) return send(prepare(retry));

  const refreshed = await refreshAccessToken();
  if (!refreshed) {
    handleSessionExpired();
    return response;
  }
  return send(prepare(retry));
}

// Same-origin: the page's own address (Vite proxies /api to Django in development).
export const api = createClient<paths>({ baseUrl: window.location.origin, fetch: apiFetch });

type Result<T> = { data?: T; error?: unknown; response: Response };

/**
 * The data of a successful call, or throw its ApiError. Use with TanStack Query:
 * `queryFn: () => unwrap(api.GET("/api/v1/me"))`.
 */
export async function unwrap<T>(call: Promise<Result<T>>): Promise<T> {
  const { data, error, response } = await call;
  if (!response.ok) throw ApiError.fromBody(error, response);
  return data as T;
}
