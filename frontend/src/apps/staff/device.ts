// Is this a registered counter device? The httpOnly das_device cookie decides; the
// browser sends it and GET /devices/current answers (404 when it isn't one).
import { useQuery, type QueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";

import { api, unwrap } from "@/api/client";
import { ApiError } from "@/api/errors";
import type { components } from "@/api/schema";
import { endSession, meQueryKey } from "@/apps/shared/signin/session";
import { setAccessToken } from "@/lib/auth";

export type CurrentDevice = components["schemas"]["CurrentDevice"];
export type RosterEntry = components["schemas"]["RosterEntry"];

export const currentDeviceKey = ["device", "current"] as const;
export const SWITCH_PATH = "/staff/switch";

export async function fetchCurrentDevice(): Promise<CurrentDevice | null> {
  try {
    return await unwrap(api.GET("/api/v1/devices/current"));
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export function useCurrentDevice() {
  return useQuery({ queryKey: currentDeviceKey, queryFn: fetchCurrentDevice });
}

/**
 * How X-15 should end the previous person's session when it opens. Ending it there
 * (X-15 isn't behind the sign-in guard) means the signed-in screen can't react first
 * and redirect to X-15 with a returnTo for the next person.
 * - "logout": end it on the server too (switch user, idle lock);
 * - "forget": the server has ended it already (S-02 registration); just drop it here.
 */
export interface SwitchState {
  endSession?: "logout" | "forget";
}

/**
 * Lock a registered device: back to X-15, ending the person's session so nothing
 * done afterwards is recorded against them (11-staff-app.md, X-15).
 */
export function useLockDevice() {
  const navigate = useNavigate();
  return () => {
    const state: SwitchState = { endSession: "logout" };
    void navigate(SWITCH_PATH, { replace: true, state });
  };
}

/** Run by X-15 on arrival: end the session it was asked to end. */
export async function finishSession(
  queryClient: QueryClient,
  how: NonNullable<SwitchState["endSession"]>,
): Promise<void> {
  if (how === "logout") {
    await endSession(queryClient);
  } else {
    setAccessToken(null);
    queryClient.removeQueries({ queryKey: meQueryKey });
  }
  void queryClient.invalidateQueries({ queryKey: currentDeviceKey });
}
