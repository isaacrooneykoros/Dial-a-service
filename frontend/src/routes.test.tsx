import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";

import { routes } from "@/routes";

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(<RouterProvider router={router} />);
}

describe("route areas", () => {
  it.each([
    ["/staff", "Staff app"],
    ["/staff/queue", "Staff app"],
    ["/console", "Business console"],
    ["/rider", "Rider app"],
    ["/o/abc123", "Order page"],
    ["/", "Customer app"],
    ["/anything-else", "Customer app"],
  ])("%s opens the %s area", async (path, heading) => {
    renderAt(path);
    expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
  });
});
