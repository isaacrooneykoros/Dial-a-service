// i18n (ADR-0003 section 5). Keys are namespaced by screen ID ("X-10.button.log_in");
// shared texts live in the "shared" namespace. Swahili files stay empty until the
// translations exist (owner decision D-23); English is the fallback.
import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import enShared from "./en/shared.json";
import swShared from "./sw/shared.json";

export const resources = {
  en: { shared: enShared },
  sw: { shared: swShared },
} as const;

export const SUPPORTED_LANGUAGES = ["en", "sw"] as const;
export type Language = (typeof SUPPORTED_LANGUAGES)[number];

void i18n.use(initReactI18next).init({
  resources,
  lng: "en",
  fallbackLng: "en",
  defaultNS: "shared",
  ns: ["shared"],
  interpolation: { escapeValue: false }, // React escapes already
  returnNull: false,
});

export default i18n;
