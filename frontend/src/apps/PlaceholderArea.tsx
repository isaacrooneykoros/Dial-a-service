import { useTranslation } from "react-i18next";

export type AreaName = "staff" | "console" | "rider" | "customer" | "public";

/** Stands in for an app area until its screens are built (M1 builds sign-in only). */
export function PlaceholderArea({ area }: { area: AreaName }) {
  const { t } = useTranslation("shared");
  return (
    <main className="mx-auto max-w-xl p-4">
      <h1 className="text-page-title font-heading text-text">{t(`areas.${area}`)}</h1>
      <p className="mt-2 text-body text-text-muted">{t("placeholder.coming_soon")}</p>
    </main>
  );
}
