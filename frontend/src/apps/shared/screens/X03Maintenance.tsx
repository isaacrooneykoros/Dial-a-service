// X-03 Maintenance: the expected return time from config; checks again every 60
// seconds and carries on by itself when maintenance ends.
import { useEffect, useEffectEvent } from "react";
import { useTranslation } from "react-i18next";

import { formatDate, formatTime } from "@/lib/format";

export const MAINTENANCE_RECHECK_MS = 60_000;

export interface X03MaintenanceProps {
  /** ISO 8601, or empty when no time was given. */
  expectedReturn: string;
  timeZone: string;
  onRecheck: () => void;
}

export function X03Maintenance({ expectedReturn, timeZone, onRecheck }: X03MaintenanceProps) {
  const { t } = useTranslation("shared");
  const recheck = useEffectEvent(onRecheck);
  useEffect(() => {
    const timer = window.setInterval(() => recheck(), MAINTENANCE_RECHECK_MS);
    return () => window.clearInterval(timer);
  }, []);

  const back = expectedReturn ? new Date(expectedReturn) : null;
  const when =
    back && !Number.isNaN(back.getTime())
      ? t("X-03.back_at", {
          time: formatTime(back, { timeZone }),
          date: formatDate(back, { timeZone }),
        })
      : t("X-03.back_soon");

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-surface p-4 text-center">
      <h1 className="font-heading text-section-title text-text">{t("X-03.title")}</h1>
      <p className="text-body text-text">{when}</p>
      <p className="text-secondary text-text-muted">{t("X-03.continues")}</p>
    </main>
  );
}
