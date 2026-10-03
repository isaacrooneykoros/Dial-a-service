// The sign-in screens of an app area (ADR-0003 section 1): /{area}/login,
// /{area}/forgot-password, …/code and …/new-password. Everything else in the area
// needs a session. One component set serves the staff app and the console now, and
// the rider and customer apps when they arrive (M9).
import type { ReactNode } from "react";
import { Route, Routes } from "react-router";

import { RequireSignIn, SignedOutOnly } from "@/apps/shared/signin/guards";
import { X12ResetCode, X13ResetPassword } from "@/apps/shared/signin/ResetPassword";
import { X10Login } from "@/apps/shared/signin/X10Login";
import { X11ForgotPassword } from "@/apps/shared/signin/X11ForgotPassword";
import type { AppId } from "@/lib/apps";

export interface SignInRoutesProps {
  app: AppId;
  /** The signed-in part of the area. */
  signedIn: ReactNode;
  /** Where signed-out visitors go instead of X-10 (X-15 on a registered device). */
  signedOutPath?: string;
  /** More routes outside the sign-in guard, such as X-15. */
  extraRoutes?: ReactNode;
}

export function SignInRoutes({ app, signedIn, signedOutPath, extraRoutes }: SignInRoutesProps) {
  const signedOut = (screen: ReactNode) => <SignedOutOnly app={app}>{screen}</SignedOutOnly>;
  return (
    <Routes>
      <Route path="login" element={signedOut(<X10Login app={app} />)} />
      <Route path="forgot-password" element={signedOut(<X11ForgotPassword app={app} />)} />
      <Route path="forgot-password/code" element={signedOut(<X12ResetCode app={app} />)} />
      <Route
        path="forgot-password/new-password"
        element={signedOut(<X13ResetPassword app={app} />)}
      />
      {extraRoutes}
      <Route
        path="*"
        element={
          <RequireSignIn app={app} signedOutPath={signedOutPath}>
            {signedIn}
          </RequireSignIn>
        }
      />
    </Routes>
  );
}
