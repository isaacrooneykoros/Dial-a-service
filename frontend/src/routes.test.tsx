import { render, screen } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { createMemoryRouter, RouterProvider } from "react-router";

import { createQueryClient } from "@/api/query";
import { routes } from "@/routes";
import { businessConfig } from "@/test/config";
import { envelope, json, mockFetch, pathOf } from "@/test/fetch";

function renderAt(path: string) {
  const { requests } = mockFetch((request) => {
    if (pathOf(request) === "/api/v1/business/config") return json(businessConfig());
    if (pathOf(request) === "/api/v1/app/version") {
      return json({ app: "x", platform: "web", minimum: "0.0.0", latest: "0.0.0" });
    }
    return json(envelope("session_expired", "x"), 401);
  });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <QueryClientProvider client={createQueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return requests;
}

describe("route areas", () => {
  it.each([
    // Signed out, the staff app and the console open at X-10.
    ["/staff", "Log in", "staff"],
    ["/staff/queue", "Log in", "staff"],
    ["/console", "Log in", "console"],
    ["/rider", "Rider app", "rider"],
    ["/o/abc123", "Order page", "customer"],
    ["/", "Customer app", "customer"],
    ["/anything-else", "Customer app", "customer"],
  ])("%s opens the %s area as the %s app", async (path, heading, app) => {
    const requests = renderAt(path);
    // Each area is a lazy chunk compiled on first use; under a full parallel run that
    // can take longer than findBy's 1 s default.
    expect(
      await screen.findByRole("heading", { name: heading }, { timeout: 5_000 }),
    ).toBeInTheDocument();
    const version = requests.find((r) => pathOf(r) === "/api/v1/app/version");
    expect(new URL(version?.url ?? "").searchParams.get("app")).toBe(app);
  });
});
