// A small fetch mock (ADR-0003 section 10: no MSW). Each test gives a handler that
// answers requests; every request is recorded (as an unread copy) for assertions.
import { vi } from "vitest";

export type Handler = (request: Request) => Response | Promise<Response>;

export function mockFetch(handler: Handler) {
  const requests: Request[] = [];
  const spy = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const request =
      input instanceof Request ? input : new Request(new URL(String(input), location.origin), init);
    requests.push(request.clone());
    return handler(request);
  });
  vi.stubGlobal("fetch", spy);
  return { requests, spy };
}

export function json(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

export function envelope(
  code: string,
  message: string,
  extra: Record<string, unknown> = {},
): Record<string, unknown> {
  return { code, message, fields: {}, request_id: "0123456789abcdef0123456789abcdef", ...extra };
}

export function pathOf(request: Request): string {
  return new URL(request.url).pathname;
}
