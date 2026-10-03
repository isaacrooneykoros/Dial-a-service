// /invite/:token — the link in the invitation SMS (apps/accounts/services/invitations.py):
// X-14, then X-12 (code), X-13 (password; creates the account and signs in), then the
// PIN step for people who use the counter devices, then their app's home.
import { useQueryClient } from "@tanstack/react-query";
import { Navigate, Route, Routes, useNavigate, useParams } from "react-router";

import { api, unwrap } from "@/api/client";
import { X04NotFound } from "@/apps/shared/screens/X04NotFound";
import { completeSignIn, PIN_ROLES, useMe } from "@/apps/shared/signin/session";
import { X12EnterCode } from "@/apps/shared/signin/X12EnterCode";
import { X13SetNewPassword } from "@/apps/shared/signin/X13SetNewPassword";
import { appForRole, inviteFlow } from "@/apps/shared/invite/inviteFlow";
import { PinStep } from "@/apps/shared/invite/PinStep";
import { X14AcceptInvitation } from "@/apps/shared/invite/X14AcceptInvitation";
import { homePathFor } from "@/lib/apps";
import { useAccessToken } from "@/lib/auth";

function InviteCode() {
  const { token = "" } = useParams();
  const navigate = useNavigate();
  const flow = inviteFlow.get(token);
  if (!flow) return <Navigate to={`/invite/${token}`} replace />;
  const path = { params: { path: { token } } };

  return (
    <X12EnterCode
      phone={flow.phone}
      notice={flow.notice}
      onVerify={async (code) => {
        const { setup_token } = await unwrap(
          api.POST("/api/v1/auth/invitations/{token}/verify", { ...path, body: { code } }),
        );
        inviteFlow.setSetupToken(setup_token);
        void navigate(`/invite/${token}/password`);
      }}
      onResend={() => unwrap(api.POST("/api/v1/auth/invitations/{token}/send-code", path))}
    />
  );
}

function InvitePassword() {
  const { token = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const setupToken = inviteFlow.get(token)?.setupToken;
  if (!setupToken) return <Navigate to={`/invite/${token}`} replace />;

  return (
    <X13SetNewPassword
      onSave={async (password) => {
        const signedIn = await unwrap(
          api.POST("/api/v1/auth/invitations/accept", {
            body: { setup_token: setupToken, password },
          }),
        );
        inviteFlow.clear();
        completeSignIn(queryClient, signedIn);
        const { role } = signedIn.user;
        void navigate(
          PIN_ROLES.includes(role) ? `/invite/${token}/pin` : homePathFor(appForRole(role)),
          { replace: true },
        );
      }}
    />
  );
}

function InvitePin() {
  const navigate = useNavigate();
  const token = useAccessToken();
  const me = useMe();
  if (!token) return <Navigate to="/staff/login" replace />;
  if (!me.data) return null;
  const home = homePathFor(appForRole(me.data.role));
  if (me.data.has_pin) return <Navigate to={home} replace />;
  return <PinStep onDone={() => void navigate(home, { replace: true })} />;
}

export function InviteRoutes() {
  return (
    <Routes>
      <Route path=":token" element={<X14AcceptInvitation />} />
      <Route path=":token/code" element={<InviteCode />} />
      <Route path=":token/password" element={<InvitePassword />} />
      <Route path=":token/pin" element={<InvitePin />} />
      <Route path="*" element={<X04NotFound />} />
    </Routes>
  );
}
