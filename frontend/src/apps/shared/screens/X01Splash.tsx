// X-01 Splash: the business logo on the brand colour while start-up runs; after
// 8 seconds without an answer (and no cached config), "Can't connect" with Retry.
import { useTranslation } from "react-i18next";

import { Button } from "@/components/Button";

export interface X01SplashProps {
  logoUrl?: string;
  appName?: string;
  cantConnect?: boolean;
  onRetry?: () => void;
}

export function X01Splash({ logoUrl, appName, cantConnect = false, onRetry }: X01SplashProps) {
  const { t } = useTranslation("shared");
  return (
    <main
      aria-busy={!cantConnect}
      className="flex min-h-screen flex-col items-center justify-center gap-6 bg-brand-primary p-4 text-brand-on-primary"
    >
      {logoUrl ? (
        <img src={logoUrl} alt={appName ?? ""} className="max-h-24 max-w-48 object-contain" />
      ) : (
        appName && <p className="font-heading text-page-title">{appName}</p>
      )}
      {cantConnect ? (
        <div role="alert" className="flex flex-col items-center gap-4 text-center">
          <h1 className="font-heading text-section-title">{t("X-01.cant_connect.title")}</h1>
          <p className="text-body">{t("X-01.cant_connect.body")}</p>
          <Button variant="secondary" onClick={onRetry}>
            {t("error.retry")}
          </Button>
        </div>
      ) : (
        <span className="sr-only" role="status">
          {t("state.loading")}
        </span>
      )}
    </main>
  );
}
