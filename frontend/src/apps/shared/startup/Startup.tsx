// Wraps each app area: runs X-01, then shows X-02, X-03, X-04, "Can't connect" or the
// app itself with the business config available through useBusinessConfig().
import { useEffect, useState, type ReactNode } from "react";

import { X01Splash } from "@/apps/shared/screens/X01Splash";
import { X02UpdateRequired } from "@/apps/shared/screens/X02UpdateRequired";
import { X03Maintenance } from "@/apps/shared/screens/X03Maintenance";
import { X04NotFound } from "@/apps/shared/screens/X04NotFound";
import { BusinessConfigContext } from "@/apps/shared/startup/BusinessConfigContext";
import {
  loadCachedConfig,
  runStartup,
  type BusinessConfig,
  type StartupResult,
} from "@/apps/shared/startup/runStartup";
import i18n, { SUPPORTED_LANGUAGES } from "@/i18n";
import type { AppId } from "@/lib/apps";
import { applyBranding } from "@/lib/branding";

function applyConfig(config: BusinessConfig): void {
  applyBranding(config.branding);
  document.title = config.branding.app_name || config.business.name;
  const language = config.business.language;
  if ((SUPPORTED_LANGUAGES as readonly string[]).includes(language) && i18n.language !== language) {
    void i18n.changeLanguage(language);
  }
}

export interface StartupProps {
  app: AppId;
  restoreSession?: boolean;
  children: ReactNode;
}

export function Startup({ app, restoreSession = true, children }: StartupProps) {
  const [result, setResult] = useState<StartupResult | null>(null);
  const [attempt, setAttempt] = useState(0);
  // The splash is branded from the last visit, if there was one.
  const [cached] = useState(loadCachedConfig);

  useEffect(() => {
    if (cached) applyBranding(cached.branding);
  }, [cached]);

  useEffect(() => {
    let cancelled = false;
    runStartup({ app, restoreSession })
      .catch((): StartupResult => ({ kind: "cant_connect" }))
      .then((next) => {
        if (cancelled) return;
        if (next.kind === "ready" || next.kind === "maintenance") applyConfig(next.config);
        setResult(next);
      });
    return () => {
      cancelled = true;
    };
  }, [app, restoreSession, attempt]);

  const branding = cached?.branding;
  if (!result) return <X01Splash logoUrl={branding?.logo_url} appName={branding?.app_name} />;

  switch (result.kind) {
    case "ready":
      return <BusinessConfigContext value={result.config}>{children}</BusinessConfigContext>;
    case "update_required":
      return <X02UpdateRequired />;
    case "maintenance":
      return (
        <X03Maintenance
          expectedReturn={result.config.maintenance.expected_return}
          timeZone={result.config.business.timezone}
          // Rechecks in the background: X-03 stays until the answer changes.
          onRecheck={() => setAttempt((n) => n + 1)}
        />
      );
    case "not_found":
      return <X04NotFound />;
    case "cant_connect":
      return (
        <X01Splash
          logoUrl={branding?.logo_url}
          appName={branding?.app_name}
          cantConnect
          onRetry={() => {
            setResult(null);
            setAttempt((n) => n + 1);
          }}
        />
      );
  }
}
