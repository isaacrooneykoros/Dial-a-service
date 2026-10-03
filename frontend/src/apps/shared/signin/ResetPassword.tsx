// The forgot-password journey: X-11 -> X-12 (reset code) -> X-13 (new password,
// which signs every other session out and signs in here).
import { useQueryClient } from "@tanstack/react-query";
import { Navigate, useNavigate } from "react-router";

import { api, unwrap } from "@/api/client";
import { ApiError } from "@/api/errors";
import { completeSignIn, resetFlow } from "@/apps/shared/signin/session";
import type { X11State } from "@/apps/shared/signin/X11ForgotPassword";
import { X12EnterCode } from "@/apps/shared/signin/X12EnterCode";
import { X13SetNewPassword } from "@/apps/shared/signin/X13SetNewPassword";
import { homePathFor, type AppId } from "@/lib/apps";
import { normalizeKenyanMobile } from "@/lib/phone";

function forgotPath(app: AppId) {
  return `${homePathFor(app)}/forgot-password`;
}

export function X12ResetCode({ app }: { app: AppId }) {
  const navigate = useNavigate();
  const flow = resetFlow.get();
  if (!flow) return <Navigate to={forgotPath(app)} replace />;
  const { phone } = flow;

  return (
    <X12EnterCode
      phone={normalizeKenyanMobile(phone) ?? phone}
      notice={flow.notice}
      onVerify={async (code) => {
        const { reset_token } = await unwrap(
          api.POST("/api/v1/auth/password-reset/verify", { body: { phone, code } }),
        );
        resetFlow.setToken(reset_token);
        void navigate(`${forgotPath(app)}/new-password`);
      }}
      onResend={() => unwrap(api.POST("/api/v1/auth/password-reset/request", { body: { phone } }))}
      onChangeNumber={() => void navigate(forgotPath(app))}
    />
  );
}

export function X13ResetPassword({ app }: { app: AppId }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const resetToken = resetFlow.get()?.resetToken;
  if (!resetToken) return <Navigate to={forgotPath(app)} replace />;

  return (
    <X13SetNewPassword
      onSave={async (password) => {
        try {
          const signedIn = await unwrap(
            api.POST("/api/v1/auth/password-reset/confirm", {
              body: { reset_token: resetToken, password },
            }),
          );
          resetFlow.clear();
          completeSignIn(queryClient, signedIn);
          void navigate(homePathFor(app), { replace: true });
        } catch (thrown) {
          // The 10 minutes ran out: start again at X-11, saying why.
          if (thrown instanceof ApiError && thrown.code === "invalid_reset_token") {
            resetFlow.clear();
            const state: X11State = { notice: thrown.message };
            void navigate(forgotPath(app), { replace: true, state });
            return;
          }
          throw thrown;
        }
      }}
    />
  );
}
