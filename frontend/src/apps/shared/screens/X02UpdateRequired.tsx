// X-02 Update required: blocks the app. On the web, reloading fetches the new build.
import { useTranslation } from "react-i18next";

import { Button } from "@/components/Button";

export function X02UpdateRequired({ onUpdate = () => window.location.reload() }) {
  const { t } = useTranslation("shared");
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-surface p-4 text-center">
      <h1 className="font-heading text-section-title text-text">{t("X-02.title")}</h1>
      <Button onClick={onUpdate}>{t("X-02.button.update")}</Button>
    </main>
  );
}
