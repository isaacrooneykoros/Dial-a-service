// X-15: a registered device locks after 5 idle minutes (11-staff-app.md).
import { useEffect, useEffectEvent } from "react";

import { useLockDevice } from "@/apps/staff/device";

export const IDLE_LOCK_MS = 5 * 60_000;
const ACTIVITY = ["pointerdown", "keydown", "touchstart", "wheel", "scroll"] as const;

export function IdleLock() {
  const lock = useLockDevice();
  const fire = useEffectEvent(() => lock());
  useEffect(() => {
    let timer = window.setTimeout(fire, IDLE_LOCK_MS);
    const reset = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(fire, IDLE_LOCK_MS);
    };
    ACTIVITY.forEach((name) => window.addEventListener(name, reset, { passive: true }));
    return () => {
      window.clearTimeout(timer);
      ACTIVITY.forEach((name) => window.removeEventListener(name, reset));
    };
  }, []);
  return null;
}
