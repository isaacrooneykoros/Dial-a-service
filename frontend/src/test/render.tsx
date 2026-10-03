// Render an app area for screen tests: a fresh query client, the business config
// (as X-01 provides it) and a memory router at `path`.
import { QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { createMemoryRouter, RouterProvider, useLocation } from "react-router";

import { createQueryClient } from "@/api/query";
import { BusinessConfigContext } from "@/apps/shared/startup/BusinessConfigContext";
import { businessConfig } from "@/test/config";

/** Shows the current path and query in the page, for asserting where we ended up. */
export function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname + location.search}</output>;
}

export function renderArea(path: string, routes: { path: string; element: ReactNode }[]) {
  const router = createMemoryRouter(
    routes.map((route) => ({
      path: route.path,
      element: (
        <>
          {route.element}
          <LocationProbe />
        </>
      ),
    })),
    { initialEntries: [path] },
  );
  const queryClient = createQueryClient();
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <BusinessConfigContext value={businessConfig()}>
        <RouterProvider router={router} />
      </BusinessConfigContext>
    </QueryClientProvider>,
  );
  return { ...utils, router, queryClient };
}
