import { QueryClientProvider } from "@tanstack/react-query";
import { createBrowserRouter } from "react-router";
// The DOM RouterProvider wires up react-dom's flushSync (used when locking a device).
import { RouterProvider } from "react-router/dom";

import { createQueryClient } from "@/api/query";
import { setSessionExpiredNavigator } from "@/lib/auth";
import { routes } from "@/routes";

const router = createBrowserRouter(routes);
const queryClient = createQueryClient();

// Going to X-10 through the router (not a page load) keeps drafts in memory.
setSessionExpiredNavigator((url) => void router.navigate(url));

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}
