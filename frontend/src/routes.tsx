// Route areas (ADR-0003 section 1). Each area is its own chunk, so a counter
// tablet never downloads console code. Every area starts with X-01 for its app:
// the staff, rider and customer apps and the business console each check their own
// minimum version. Public order pages belong to the customer app but need no session.
import { lazy, Suspense, type ComponentType, type LazyExoticComponent } from "react";
import type { RouteObject } from "react-router";

import { Startup } from "@/apps/shared/startup/Startup";
import type { AppId } from "@/lib/apps";

const StaffArea = lazy(() => import("@/apps/staff/StaffArea"));
const ConsoleArea = lazy(() => import("@/apps/console/ConsoleArea"));
const RiderArea = lazy(() => import("@/apps/rider/RiderArea"));
const CustomerArea = lazy(() => import("@/apps/customer/CustomerArea"));
const PublicArea = lazy(() => import("@/apps/public/PublicArea"));

function area(
  Component: LazyExoticComponent<ComponentType>,
  app: AppId,
  { restoreSession = true } = {},
) {
  // While the chunk loads: nothing (10-screens-shared.md: nothing for 200 ms, then skeletons).
  return (
    <Startup app={app} restoreSession={restoreSession}>
      <Suspense fallback={null}>
        <Component />
      </Suspense>
    </Startup>
  );
}

export const routes: RouteObject[] = [
  { path: "/staff/*", element: area(StaffArea, "staff") },
  { path: "/console/*", element: area(ConsoleArea, "console") },
  { path: "/rider/*", element: area(RiderArea, "rider") },
  { path: "/o/:token", element: area(PublicArea, "customer", { restoreSession: false }) },
  { path: "/*", element: area(CustomerArea, "customer") },
];
