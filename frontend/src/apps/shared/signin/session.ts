// Shared sign-in plumbing: finishing a sign-in, and the forgot-password journey's state.
import type { QueryClient } from "@tanstack/react-query";

import type { components } from "@/api/schema";
import { setAccessToken } from "@/lib/auth";

export type Me = components["schemas"]["Me"];

export const meQueryKey = ["me"] as const;

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
