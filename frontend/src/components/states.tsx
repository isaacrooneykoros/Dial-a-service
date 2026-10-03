// Shared states used by every screen (10-screens-shared.md, "Shared states and
// shared screens"; ADR-0003 section 7). Screen specs only mention a state when it
// differs from these.
import { useEffect, useEffectEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { shortReference, type ApiError } from "@/api/errors";
import { Banner } from "@/components/Banner";
import { Button } from "@/components/Button";
import { useOnline } from "@/lib/online";
import { useDelayed, useCountdown } from "@/lib/timers";

/** First load: nothing for 200 ms, then the skeleton. No full-screen spinners. */
export const FIRST_LOAD_DELAY_MS = 200;

export function FirstLoad({ skeleton }: { skeleton: ReactNode }) {
  const { t } = useTranslation("shared");
  const show = useDelayed(FIRST_LOAD_DELAY_MS);
  return (
    <div role="status" aria-busy="true">
      <span className="sr-only">{t("state.loading")}</span>
      {show && skeleton}
    </div>
  );
}

/** Refreshing: old data stays on screen; a thin bar shows at the top. */
export function RefreshBar({ active }: { active: boolean }) {
  const { t } = useTranslation("shared");
  if (!active) return null;
  return (
    <div
      role="progressbar"
      aria-label={t("state.refreshing")}
      className="fixed inset-x-0 top-0 z-50 h-1 animate-pulse bg-brand-primary motion-reduce:animate-none"
    />
  );
}

/** Server error: what happened, Retry, and a short support reference (the request ID). */
export function ServerErrorBanner({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  const { t } = useTranslation("shared");
  const reference = shortReference(error.requestId);
  return (
    <Banner
      tone={error.isNetwork ? "offline" : "error"}
      action={
        onRetry && (
          <Button variant="text" onClick={onRetry}>
            {t("error.retry")}
          </Button>
        )
      }
    >
      <p>{error.message}</p>
      {reference && (
        <p className="mt-1 text-caption text-text-muted">{t("error.reference", { reference })}</p>
      )}
    </Banner>
  );
}

/**
 * Offline: a banner at the top. Shop and customer screens keep cached data read-only
 * and disable actions; use `useOnline()` for that and this banner gives the reason.
 */
export function OfflineBanner() {
  const { t } = useTranslation("shared");
  const online = useOnline();
  if (online) return null;
  return <Banner tone="offline">{t("offline.banner")}</Banner>;
}

/**
 * Too many attempts: "Too many attempts. Try again in N minutes." counting down from the
 * server's retry_after. `onDone` runs when the wait is over. Remount (new `key`) to restart.
 */
export function Throttled({ retryAfter, onDone }: { retryAfter: number; onDone?: () => void }) {
  const { t } = useTranslation("shared");
  const left = useCountdown(retryAfter);
  const finished = useEffectEvent(() => onDone?.());
  useEffect(() => {
    if (left <= 0) finished();
  }, [left]);
  if (left <= 0) return null;
  const text =
    left < 60
      ? t("throttled.seconds", { count: left })
      : t("throttled.minutes", { count: Math.ceil(left / 60) });
  return (
    <Banner tone="warning">
      <p aria-live="polite">{text}</p>
    </Banner>
  );
}
