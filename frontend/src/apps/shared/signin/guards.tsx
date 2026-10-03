// Route guards. They only decide what to show; the API checks every request anyway.
import { useState, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router";

import { homePathFor, loginPathForApp, type AppId } from "@/lib/apps";
import { getAccessToken, useAccessToken } from "@/lib/auth";

/** Signed-out visitors go to X-10 and come back here afterwards. */
export function RequireSignIn({ app, children }: { app: AppId; children: ReactNode }) {
  const token = useAccessToken();
  const location = useLocation();
  if (!token) {
    const returnTo = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`${loginPathForApp(app)}?returnTo=${returnTo}`} replace />;
  }
  return children;
}

/**
 * Sign-in screens send someone who arrives already signed in to the app's home. Only
 * on arrival: signing in on the screen itself must not race the screen's own
 * navigation (to returnTo, for example).
 */
export function SignedOutOnly({ app, children }: { app: AppId; children: ReactNode }) {
  const [signedInOnArrival] = useState(() => getAccessToken() !== null);
  if (signedInOnArrival) return <Navigate to={homePathFor(app)} replace />;
  return children;
}
