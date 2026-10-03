// The backend's error envelope, {code, message, fields, request_id} (CLAUDE.md section
// 6.5), as a typed error. Server messages are safe to show and already in the user's
// language (the client sends Accept-Language); anything else gets our own wording.
import i18n from "@/i18n";

export type FieldErrors = Record<string, string[]>;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fields: FieldErrors;
  readonly requestId: string | null;
  /** Seconds until a throttled action can be tried again (429 only). */
  readonly retryAfter: number | null;
  /** Tries left on a code (X-12), when the server says. */
  readonly attemptsLeft: number | null;

  constructor(init: {
    status: number;
    code: string;
    message: string;
    fields?: FieldErrors;
    requestId?: string | null;
    retryAfter?: number | null;
    attemptsLeft?: number | null;
  }) {
    super(init.message);
    this.name = "ApiError";
    this.status = init.status;
    this.code = init.code;
    this.fields = init.fields ?? {};
    this.requestId = init.requestId ?? null;
    this.retryAfter = init.retryAfter ?? null;
    this.attemptsLeft = init.attemptsLeft ?? null;
  }

  /** No response at all: offline, DNS, connection reset. Safe to retry. */
  get isNetwork(): boolean {
    return this.code === "network";
  }

  /** 5xx or a response we couldn't read: show the server error banner. */
  get isServer(): boolean {
    return this.status >= 500 || this.code === "unexpected_response";
  }

  static network(): ApiError {
    return new ApiError({ status: 0, code: "network", message: i18n.t("shared:error.network") });
  }

  /** Build from a parsed response body (openapi-fetch has already read it). */
  static fromBody(body: unknown, response: Response): ApiError {
    const headerId = response.headers.get("X-Request-ID");
    if (!isEnvelope(body)) {
      return new ApiError({
        status: response.status,
        code: "unexpected_response",
        message: i18n.t("shared:error.server"),
        requestId: headerId,
      });
    }
    return new ApiError({
      status: response.status,
      code: body.code,
      message: body.message,
      fields: cleanFields(body.fields),
      requestId: typeof body.request_id === "string" ? body.request_id : headerId,
      retryAfter: typeof body.retry_after === "number" ? body.retry_after : null,
      attemptsLeft: typeof body.attempts_left === "number" ? body.attempts_left : null,
    });
  }

  static async fromResponse(response: Response): Promise<ApiError> {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      // Not JSON (a proxy's HTML error page, for example).
    }
    return ApiError.fromBody(body, response);
  }
}

interface Envelope {
  code: string;
  message: string;
  fields?: unknown;
  request_id?: unknown;
  retry_after?: unknown;
  attempts_left?: unknown;
}

function isEnvelope(body: unknown): body is Envelope {
  if (typeof body !== "object" || body === null) return false;
  const candidate = body as Record<string, unknown>;
  return typeof candidate.code === "string" && typeof candidate.message === "string";
}

function cleanFields(fields: unknown): FieldErrors {
  if (typeof fields !== "object" || fields === null) return {};
  const result: FieldErrors = {};
  for (const [name, messages] of Object.entries(fields)) {
    if (Array.isArray(messages)) {
      result[name] = messages.filter((m): m is string => typeof m === "string");
    }
  }
  return result;
}

/** The support reference shown on the server error banner: the request ID, shortened. */
export function shortReference(requestId: string | null): string | null {
  return requestId ? requestId.slice(0, 8).toUpperCase() : null;
}

/** Whatever a mutation threw, as an ApiError (a bug in our code reads as a server error). */
export function asApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  return new ApiError({
    status: 0,
    code: "unexpected_response",
    message: i18n.t("shared:error.server"),
  });
}
