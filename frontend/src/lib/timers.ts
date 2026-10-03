// Small timer hooks shared by screens: the first-load delay and countdowns
// ("Try again in N minutes", X-12's resend timer).
import { useEffect, useState } from "react";

/** False for `ms` after mount, then true. */
export function useDelayed(ms: number): boolean {
  const [passed, setPassed] = useState(ms <= 0);
  useEffect(() => {
    if (ms <= 0) return;
    const timer = window.setTimeout(() => setPassed(true), ms);
    return () => window.clearTimeout(timer);
  }, [ms]);
  return passed;
}

/**
 * Seconds left of a countdown that started at mount, down to 0. It follows the clock,
 * not the number of ticks, so it stays right when a phone slows background timers.
 * To restart it, remount the component (give it a new `key`).
 */
export function useCountdown(seconds: number): number {
  const [endsAt] = useState(() => Date.now() + seconds * 1000);
  const [remaining, setRemaining] = useState(Math.max(0, Math.ceil(seconds)));
  useEffect(() => {
    // Checked four times a second; setting the same value doesn't re-render.
    const timer = window.setInterval(() => {
      const left = Math.max(0, Math.ceil((endsAt - Date.now()) / 1000));
      setRemaining(left);
      if (left <= 0) window.clearInterval(timer);
    }, 250);
    return () => window.clearInterval(timer);
  }, [endsAt]);
  return remaining;
}
