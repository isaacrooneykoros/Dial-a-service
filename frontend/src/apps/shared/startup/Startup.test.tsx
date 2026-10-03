import { act, fireEvent, render, screen } from "@testing-library/react";

import { useBusinessConfig } from "@/apps/shared/startup/BusinessConfigContext";
import { saveCachedConfig, type BusinessConfig } from "@/apps/shared/startup/runStartup";
import { Startup } from "@/apps/shared/startup/Startup";
import { getAccessToken, setAccessToken } from "@/lib/auth";
import { reportNetworkSuccess } from "@/lib/online";
import { businessConfig } from "@/test/config";
import { envelope, json, mockFetch, pathOf } from "@/test/fetch";

const CONFIG = "/api/v1/business/config";
const VERSION = "/api/v1/app/version";
const REFRESH = "/api/v1/auth/refresh";

function Home() {
  const config = useBusinessConfig();
  return <h1>{config.business.name}</h1>;
}

interface Answers {
  config?: () => Response | Promise<Response>;
  minimum?: string;
  refresh?: () => Response;
}

function serve({ config, minimum = "0.0.0", refresh }: Answers = {}) {
  return mockFetch((request) => {
    switch (pathOf(request)) {
      case CONFIG:
        return config ? config() : json(businessConfig());
      case VERSION:
        return json({ app: "x", platform: "web", minimum, latest: minimum });
      case REFRESH:
        return refresh ? refresh() : json(envelope("session_expired", "x"), 401);
      default:
        return json(envelope("not_found", "x"), 404);
    }
  });
}

function start(app: "staff" | "console" | "rider" | "customer" = "staff", restoreSession = true) {
  return render(
    <Startup app={app} restoreSession={restoreSession}>
      <Home />
    </Startup>,
  );
}

beforeEach(() => {
  localStorage.clear();
  setAccessToken(null);
  reportNetworkSuccess();
  document.documentElement.removeAttribute("style");
});
afterEach(() => vi.useRealTimers());

describe("X-01 start-up", () => {
  it("loads config and this app's version together, brands the app and opens it", async () => {
    const { requests } = serve();
    start("rider");

    expect(await screen.findByRole("heading", { name: "Mama Safi Laundry" })).toBeInTheDocument();
    const style = document.documentElement.style;
    expect(style.getPropertyValue("--brand-primary")).toBe("#7A1F5C");
    expect(document.title).toBe("Mama Safi");

    const version = requests.find((r) => pathOf(r) === VERSION);
    expect(new URL(version?.url ?? "").searchParams.get("app")).toBe("rider");
    expect(new URL(version?.url ?? "").searchParams.get("platform")).toBe("web");
  });

  it.each(["staff", "console", "rider", "customer"] as const)(
    "the %s app asks for its own minimum version",
    async (app) => {
      const { requests } = serve();
      start(app);
      await screen.findByRole("heading");
      const version = requests.find((r) => pathOf(r) === VERSION);
      expect(new URL(version?.url ?? "").searchParams.get("app")).toBe(app);
    },
  );

  it("restores the session with a silent refresh as its last step", async () => {
    serve({ refresh: () => json({ access: "restored" }) });
    start();
    await screen.findByRole("heading");
    expect(getAccessToken()).toBe("restored");
  });

  it("opens signed out when there is no session, without sending anyone to log in", async () => {
    serve();
    start();
    expect(await screen.findByRole("heading", { name: "Mama Safi Laundry" })).toBeInTheDocument();
    expect(getAccessToken()).toBeNull();
  });

  it("doesn't try to restore a session on public order pages", async () => {
    const { requests } = serve();
    start("customer", false);
    await screen.findByRole("heading");
    expect(requests.map(pathOf)).not.toContain(REFRESH);
  });

  it("brands the splash from the last visit while loading", async () => {
    saveCachedConfig(businessConfig());
    mockFetch(() => new Promise<Response>(() => {}));
    start();
    expect(document.documentElement.style.getPropertyValue("--brand-primary")).toBe("#7A1F5C");
    expect(screen.getByText("Mama Safi")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Loading");
  });

  it("uses the cached config when offline", async () => {
    saveCachedConfig(businessConfig());
    mockFetch(() => {
      throw new TypeError("Failed to fetch");
    });
    start();
    expect(await screen.findByRole("heading", { name: "Mama Safi Laundry" })).toBeInTheDocument();
  });

  it("shows Can't connect after 8 seconds with no answer and no cache, and Retry works", async () => {
    vi.useFakeTimers();
    let answer = false;
    serve({ config: () => (answer ? json(businessConfig()) : new Promise<Response>(() => {})) });
    start();

    await act(() => vi.advanceTimersByTimeAsync(7_999));
    expect(screen.queryByText("Can't connect")).not.toBeInTheDocument();
    await act(() => vi.advanceTimersByTimeAsync(1));
    expect(screen.getByRole("alert")).toHaveTextContent("Can't connect");

    answer = true;
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await act(() => vi.advanceTimersByTimeAsync(0));
    expect(screen.getByRole("heading", { name: "Mama Safi Laundry" })).toBeInTheDocument();
  });

  it("shows X-04 for an address no business uses", async () => {
    serve({ config: () => json(envelope("not_found", "We couldn't find that"), 404) });
    start();
    expect(
      await screen.findByRole("heading", { name: "We couldn't find that" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("X-02 update required", () => {
  it("blocks the app when this build is below the minimum", async () => {
    serve({ minimum: "99.0.0" });
    start();
    expect(
      await screen.findByRole("heading", { name: "This version needs an update to keep working" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Update now" })).toBeInTheDocument();
    expect(screen.queryByText("Mama Safi Laundry")).not.toBeInTheDocument();
  });

  it("wins over maintenance", async () => {
    serve({
      minimum: "99.0.0",
      config: () => json(businessConfig({ maintenance: { active: true, expected_return: "" } })),
    });
    start();
    expect(await screen.findByRole("button", { name: "Update now" })).toBeInTheDocument();
  });
});

describe("X-03 maintenance", () => {
  function underMaintenance(expected_return: string): BusinessConfig {
    return businessConfig({ maintenance: { active: true, expected_return } });
  }

  it("shows the expected return time in the business's timezone", async () => {
    serve({ config: () => json(underMaintenance("2026-10-02T06:00:00+03:00")) });
    start();
    expect(
      await screen.findByText(/^We expect to be back at 6am on \w{3} 2 Oct\.$/),
    ).toBeInTheDocument();
  });

  it("says soon when there is no time", async () => {
    serve({ config: () => json(underMaintenance("")) });
    start();
    expect(await screen.findByText("We'll be back soon.")).toBeInTheDocument();
  });

  it("checks again every 60 seconds and carries on by itself", async () => {
    vi.useFakeTimers();
    let active = true;
    // The config answer follows `active` at the time of each request.
    serve({
      config: () => json(businessConfig({ maintenance: { active, expected_return: "" } })),
    });
    start();
    await act(() => vi.advanceTimersByTimeAsync(0));
    expect(
      screen.getByRole("heading", { name: "We're doing planned maintenance" }),
    ).toBeInTheDocument();

    await act(() => vi.advanceTimersByTimeAsync(60_000));
    expect(
      screen.getByRole("heading", { name: "We're doing planned maintenance" }),
    ).toBeInTheDocument();

    active = false;
    await act(() => vi.advanceTimersByTimeAsync(60_000));
    expect(screen.getByRole("heading", { name: "Mama Safi Laundry" })).toBeInTheDocument();
  });
});
