// TanStack Query set-up (ADR-0003 section 3).
import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/api/errors";

/** Network failures are retried twice; a server's answer (4xx, 5xx) is not. */
export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  return error instanceof ApiError && error.isNetwork && failureCount < 2;
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: shouldRetryQuery },
      // Never retried automatically: the user retries, with the same idempotency key.
      mutations: { retry: false },
    },
  });
}

/** DRF cursor pagination, 20 per page (CLAUDE.md section 6.5). */
export interface CursorPage<T> {
  next: string | null;
  previous: string | null;
  results: T[];
}

/** The cursor for the next page, for useInfiniteQuery's getNextPageParam. */
export function nextCursor(page: { next?: string | null }): string | undefined {
  if (!page.next) return undefined;
  return new URL(page.next, window.location.origin).searchParams.get("cursor") ?? undefined;
}
