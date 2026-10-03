import { api, unwrap } from "@/api/client";
import { ApiError } from "@/api/errors";
import i18n from "@/i18n";
import { getAccessToken, setAccessToken, setSessionExpiredNavigator } from "@/lib/auth";
import { isOnline, reportNetworkSuccess } from "@/lib/online";
import { envelope, json, mockFetch, pathOf } from "@/test/fetch";

const REFRESH = "/api/v1/auth/refresh";
const navigate = vi.fn();

beforeEach(() => {
  setAccessToken(null);
  reportNetworkSuccess();
  navigate.mockReset();
  setSessionExpiredNavigator(navigate);
  window.history.replaceState(null, "", "/");
});

function apiRequests(requests: Request[]) {
  return requests.filter((r) => pathOf(r) !== REFRESH);
}

describe("request headers", () => {
  it("sends the access token, the language and, on POST, an idempotency key", async () => {
    setAccessToken("token-1");
    await i18n.changeLanguage("sw");
    const { requests } = mockFetch(() => json({}));

    await api.GET("/api/v1/me");
    await api.POST("/api/v1/auth/logout");

    const [get, post] = requests;
    expect(get?.headers.get("Authorization")).toBe("Bearer token-1");
    expect(get?.headers.get("Accept-Language")).toBe("sw");
    expect(get?.headers.has("Idempotency-Key")).toBe(false);
    expect(post?.headers.get("Idempotency-Key")).toMatch(/^[0-9a-f-]{36}$/);
    await i18n.changeLanguage("en");
  });

  it("keeps the idempotency key the screen gives for its action", async () => {
    const { requests } = mockFetch(() => json({}));
    await api.POST("/api/v1/auth/logout", { headers: { "Idempotency-Key": "action-key" } });
    expect(requests[0]?.headers.get("Idempotency-Key")).toBe("action-key");
  });

  it("sends no Authorization header when signed out", async () => {
    const { requests } = mockFetch(() => json({}));
    await api.GET("/api/v1/me");
    expect(requests[0]?.headers.has("Authorization")).toBe(false);
  });
});

describe("session refresh on 401", () => {
  it("refreshes once for many failing requests, then retries each with the new token", async () => {
    setAccessToken("old");
    let refreshes = 0;
    const { requests } = mockFetch(async (request) => {
      if (pathOf(request) === REFRESH) {
        refreshes += 1;
        await new Promise((resolve) => setTimeout(resolve, 10));
        return json({ access: "new" });
      }
      const auth = request.headers.get("Authorization");
      return auth === "Bearer new"
        ? json({ ok: true })
        : json(envelope("not_authenticated", "x"), 401);
    });

    const results = await Promise.all([
      api.GET("/api/v1/me"),
      api.GET("/api/v1/me/branches"),
      api.GET("/api/v1/business/config"),
    ]);

    expect(refreshes).toBe(1);
    expect(results.map((r) => r.response.status)).toEqual([200, 200, 200]);
    expect(getAccessToken()).toBe("new");
    expect(apiRequests(requests)).toHaveLength(6);
  });

  it("retries a POST with the same body and the same idempotency key", async () => {
    setAccessToken("old");
    const { requests } = mockFetch((request) => {
      if (pathOf(request) === REFRESH) return json({ access: "new" });
      return request.headers.get("Authorization") === "Bearer new"
        ? json({}, 201)
        : json(envelope("not_authenticated", "x"), 401);
    });

    await api.POST("/api/v1/me/pin", { body: { pin: "4826" } });

    const [first, retry] = apiRequests(requests);
    expect(retry?.headers.get("Idempotency-Key")).toBe(first?.headers.get("Idempotency-Key"));
    expect(await retry?.json()).toEqual({ pin: "4826" });
  });

  it("skips the refresh when another request already got a new token", async () => {
    setAccessToken("old");
    let refreshes = 0;
    mockFetch((request) => {
      if (pathOf(request) === REFRESH) refreshes += 1;
      // The token changes while this request is out.
      if (request.headers.get("Authorization") === "Bearer old") {
        setAccessToken("new");
        return json(envelope("not_authenticated", "x"), 401);
      }
      return json({});
    });

    const { response } = await api.GET("/api/v1/me");
    expect(response.status).toBe(200);
    expect(refreshes).toBe(0);
  });

  it("goes to log in with returnTo when the session has ended", async () => {
    window.history.replaceState(null, "", "/staff/orders?tab=ready");
    setAccessToken("old");
    mockFetch((request) =>
      pathOf(request) === REFRESH
        ? json(envelope("session_expired", "Your session has ended. Please log in again."), 401)
        : json(envelope("not_authenticated", "Please log in to continue."), 401),
    );

    const call = unwrap(api.GET("/api/v1/me"));

    await expect(call).rejects.toMatchObject({ status: 401, code: "not_authenticated" });
    expect(getAccessToken()).toBeNull();
    expect(navigate).toHaveBeenCalledWith(
      `/staff/login?returnTo=${encodeURIComponent("/staff/orders?tab=ready")}`,
    );
  });

  it("does not refresh for sign-in endpoints, which answer 401 for their own reasons", async () => {
    const { requests } = mockFetch(() => json(envelope("invalid_credentials", "x"), 401));
    await api.POST("/api/v1/auth/login", { body: { phone: "0712345678", password: "x" } });
    expect(requests.map(pathOf)).toEqual(["/api/v1/auth/login"]);
    expect(navigate).not.toHaveBeenCalled();
  });

  it("stays signed in when the refresh can't reach the server", async () => {
    setAccessToken("old");
    mockFetch((request) => {
      if (pathOf(request) === REFRESH) throw new TypeError("Failed to fetch");
      return json(envelope("not_authenticated", "x"), 401);
    });

    await expect(api.GET("/api/v1/me")).rejects.toMatchObject({ code: "network" });
    expect(getAccessToken()).toBe("old");
    expect(navigate).not.toHaveBeenCalled();
  });
});

describe("errors", () => {
  it("turns the error envelope into an ApiError", async () => {
    mockFetch(() =>
      json(
        envelope("throttled", "Too many attempts. Try again in 3 minutes.", {
          fields: { phone: ["Enter a valid number."] },
          retry_after: 170,
        }),
        429,
      ),
    );

    const error = await unwrap(
      api.POST("/api/v1/auth/password-reset/request", { body: { phone: "0712345678" } }),
    ).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 429,
      code: "throttled",
      message: "Too many attempts. Try again in 3 minutes.",
      fields: { phone: ["Enter a valid number."] },
      requestId: "0123456789abcdef0123456789abcdef",
      retryAfter: 170,
    });
  });

  it("shows our own message for a response that isn't an envelope", async () => {
    mockFetch(
      () =>
        new Response("<html>Bad gateway</html>", {
          status: 502,
          headers: { "X-Request-ID": "feedface" },
        }),
    );

    const error = await unwrap(api.GET("/api/v1/me")).catch((e: unknown) => e);

    expect(error).toMatchObject({
      status: 502,
      code: "unexpected_response",
      message: "Something went wrong on our side. Please try again.",
      requestId: "feedface",
      isServer: true,
    });
  });

  it("reports a failed connection as a network error and as offline", async () => {
    mockFetch(() => {
      throw new TypeError("Failed to fetch");
    });
    const error = await api.GET("/api/v1/me").catch((e: unknown) => e);
    expect(error).toMatchObject({ code: "network", isNetwork: true, status: 0 });
    expect(isOnline()).toBe(false);

    mockFetch(() => json({}));
    await api.GET("/api/v1/me");
    expect(isOnline()).toBe(true);
  });

  it("returns the data of a successful call", async () => {
    mockFetch(() => json({ id: "u1" }));
    await expect(unwrap(api.GET("/api/v1/me"))).resolves.toEqual({ id: "u1" });
  });
});
