// The X-14 journey's state: X-14 -> X-12 (code) -> X-13 (password) -> the PIN step.
// Held in memory only: the setup token is a 10-minute single-use grant. Reloading
// mid-way starts again at X-14 (the SMS link still works until the invitation is used).
import type { AppId } from "@/lib/apps";

interface InviteFlow {
  token: string;
  phone: string;
  /** X-14's answer, shown on X-12. */
  notice: string;
  setupToken: string | null;
}

let flow: InviteFlow | null = null;

export const inviteFlow = {
  /** The flow for this invitation link, if it was started from it. */
  get: (token: string): InviteFlow | null => (flow?.token === token ? flow : null),
  start(token: string, phone: string, notice: string): void {
    flow = { token, phone, notice, setupToken: null };
  },
  setSetupToken(setupToken: string): void {
    if (flow) flow = { ...flow, setupToken };
  },
  clear(): void {
    flow = null;
  },
};

/** Where a newly joined person lands: the console for accountants, otherwise the staff app. */
export function appForRole(role: string): AppId {
  if (role === "accountant") return "console";
  if (role === "rider") return "rider";
  return "staff";
}
