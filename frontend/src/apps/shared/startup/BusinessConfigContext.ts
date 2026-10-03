// The business config loaded by X-01, for every screen below it (name, timezone,
// currency, branding, support contacts).
import { createContext, useContext } from "react";

import type { BusinessConfig } from "@/apps/shared/startup/runStartup";

export const BusinessConfigContext = createContext<BusinessConfig | null>(null);

export function useBusinessConfig(): BusinessConfig {
  const config = useContext(BusinessConfigContext);
  if (!config) throw new Error("useBusinessConfig() is used outside <Startup>.");
  return config;
}
