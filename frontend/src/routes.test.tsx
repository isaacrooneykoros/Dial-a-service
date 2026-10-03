import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";

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
  render(<RouterProvider router={router} />);
  return requests;
}

describe("route areas", () => {
  it.each([
    ["/staff", "Staff app", "staff"],
    ["/staff/queue", "Staff app", "staff"],
    ["/console", "Business console", "console"],
    ["/rider", "Rider app", "rider"],
    ["/o/abc123", "Order page", "customer"],
    ["/", "Customer app", "customer"],
    ["/anything-else", "Customer app", "customer"],
  ])("%s opens the %s area as the %s app", async (path, heading, app) => {
    const requests = renderAt(path);
    expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
    const version = requests.find((r) => pathOf(r) === "/api/v1/app/version");
    expect(new URL(version?.url ?? "").searchParams.get("app")).toBe(app);
  });
});
