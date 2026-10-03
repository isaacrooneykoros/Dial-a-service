// Route areas (ADR-0003 section 1). Each area is its own chunk, so a counter
// tablet never downloads console code.
import { lazy, Suspense, type ComponentType, type LazyExoticComponent } from "react";
import type { RouteObject } from "react-router";

const StaffArea = lazy(() => import("@/apps/staff/StaffArea"));
const ConsoleArea = lazy(() => import("@/apps/console/ConsoleArea"));
const RiderArea = lazy(() => import("@/apps/rider/RiderArea"));
const CustomerArea = lazy(() => import("@/apps/customer/CustomerArea"));
const PublicArea = lazy(() => import("@/apps/public/PublicArea"));

function area(Component: LazyExoticComponent<ComponentType>) {
  // First load shows nothing (10-screens-shared.md: nothing for 200 ms, then skeletons).
  return (
    <Suspense fallback={null}>
      <Component />
    </Suspense>
  );
}

export const routes: RouteObject[] = [
  { path: "/staff/*", element: area(StaffArea) },
  { path: "/console/*", element: area(ConsoleArea) },
  { path: "/rider/*", element: area(RiderArea) },
  { path: "/o/:token", element: area(PublicArea) },
  { path: "/*", element: area(CustomerArea) },
];
