import {
  getAccessToken,
  handleSessionExpired,
  loginPathFor,
  refreshAccessToken,
  safeReturnTo,
  setAccessToken,
  setSessionExpiredNavigator,
  subscribeAccessToken,
} from "@/lib/auth";
import { json, mockFetch } from "@/test/fetch";

beforeEach(() => setAccessToken(null));

describe("token store", () => {
  it("keeps the token in memory only", () => {
    setAccessToken("secret-token");
    expect(getAccessToken()).toBe("secret-token");
    expect(JSON.stringify({ ...localStorage })).not.toContain("secret-token");
    expect(JSON.stringify({ ...sessionStorage })).not.toContain("secret-token");
  });

  it("tells subscribers when the token changes", () => {
    const listener = vi.fn();
    const unsubscribe = subscribeAccessToken(listener);
    setAccessToken("a");
    setAccessToken("a");
    setAccessToken(null);
    unsubscribe();
    setAccessToken("b");
    expect(listener).toHaveBeenCalledTimes(2);
  });
});

describe("refreshAccessToken", () => {
  it("shares one request between callers and allows a new one afterwards", async () => {
    const { spy } = mockFetch(() => json({ access: "fresh" }));
    const results = await Promise.all([refreshAccessToken(), refreshAccessToken()]);
    expect(results).toEqual([true, true]);
    expect(spy).toHaveBeenCalledTimes(1);
    await refreshAccessToken();
    expect(spy).toHaveBeenCalledTimes(2);
  });

  it("clears the token when the session has ended", async () => {
    setAccessToken("old");
    mockFetch(() => json({ code: "session_expired", message: "x" }, 401));
    await expect(refreshAccessToken()).resolves.toBe(false);
    expect(getAccessToken()).toBeNull();
  });

  it("treats a reply without a token as an ended session", async () => {
    mockFetch(() => json({}));
    await expect(refreshAccessToken()).resolves.toBe(false);
  });

  it("throws (and keeps the session) when the server is down", async () => {
    setAccessToken("old");
    mockFetch(() => json({ code: "server_error", message: "Something went wrong" }, 503));
    await expect(refreshAccessToken()).rejects.toMatchObject({ status: 503 });
    expect(getAccessToken()).toBe("old");
  });

  it("keeps the session when the refresh is throttled", async () => {
    setAccessToken("old");
    mockFetch(() =>
      json({ code: "throttled", message: "Too many attempts.", retry_after: 30 }, 429),
    );
    await expect(refreshAccessToken()).rejects.toMatchObject({ status: 429, retryAfter: 30 });
    expect(getAccessToken()).toBe("old");
  });
});

describe("log-in redirects", () => {
  it.each([
    ["/staff/orders", "/staff/login"],
    ["/console", "/console/login"],
    ["/rider/jobs/1", "/rider/login"],
    ["/", "/login"],
    ["/orders/DAS-7K3P9Q", "/login"],
  ])("%s logs in at %s", (path, login) => {
    expect(loginPathFor(path)).toBe(login);
  });

  it.each([
    ["/staff/orders?tab=ready", "/staff/orders?tab=ready"],
    [null, "/staff"],
    ["", "/staff"],
    ["https://evil.example/", "/staff"],
    ["//evil.example/", "/staff"],
    ["/\\evil.example", "/staff"],
    ["javascript:alert(1)", "/staff"],
  ])("returnTo %j becomes %s", (value, expected) => {
    expect(safeReturnTo(value, "/staff")).toBe(expected);
  });

  it("does nothing on the log-in page itself", () => {
    const navigate = vi.fn();
    setSessionExpiredNavigator(navigate);
    window.history.replaceState(null, "", "/console/login");
    handleSessionExpired();
    expect(navigate).not.toHaveBeenCalled();
    window.history.replaceState(null, "", "/");
  });
});
