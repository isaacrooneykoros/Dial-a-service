// Shared sign-in plumbing: finishing a sign-in, and the forgot-password journey's state.
import { useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema";
import { loginPathForApp, type AppId } from "@/lib/apps";
import { setAccessToken } from "@/lib/auth";

export type Me = components["schemas"]["Me"];

export const meQueryKey = ["me"] as const;

/** Roles that use the counter devices and so have a PIN (apps/accounts/services/pins.py). */
export const PIN_ROLES: readonly string[] = ["owner", "manager", "staff"];

/** Roles that manage the team and devices (the API's IsOwnerOrManager). */
export const MANAGING_ROLES: readonly string[] = ["owner", "manager"];

/** The signed-in person (primed at sign-in, fetched after a reload). */
export function useMe() {
  return useQuery({ queryKey: meQueryKey, queryFn: () => unwrap(api.GET("/api/v1/me")) });
}

/** End the session on the server, forget everything about it here, and go to X-10. */
export function useLogout(app: AppId) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  return async () => {
    await endSession(queryClient);
    void navigate(loginPathForApp(app), { replace: true });
  };
}

/** Log out on the server (best effort: offline still signs out here) and clear local state. */
export async function endSession(queryClient: QueryClient): Promise<void> {
  try {
    await api.POST("/api/v1/auth/logout");
  } catch {
    // Offline: the access token is dropped anyway and expires within 15 minutes.
  }
  setAccessToken(null);
  queryClient.removeQueries({ queryKey: meQueryKey });
}

/** Keep the access token (in memory) and the signed-in person after a sign-in. */
export function completeSignIn(queryClient: QueryClient, body: { access: string; user: Me }) {
  setAccessToken(body.access);
  queryClient.setQueryData(meQueryKey, body.user);
}

// --- Forgot password: X-11 -> X-12 -> X-13 -------------------------------------------
// Held in memory only: the reset token is a 10-minute single-use grant and must not
// sit in storage. Reloading mid-way starts again at X-11.

interface ResetFlow {
  phone: string;
  /** X-11's answer, shown on X-12. */
  notice: string;
  resetToken: string | null;
}

let flow: ResetFlow | null = null;

export const resetFlow = {
  get: (): ResetFlow | null => flow,
  start(phone: string, notice: string): void {
    flow = { phone, notice, resetToken: null };
  },
  setToken(resetToken: string): void {
    if (flow) flow = { ...flow, resetToken };
  },
  clear(): void {
    flow = null;
  },
};
