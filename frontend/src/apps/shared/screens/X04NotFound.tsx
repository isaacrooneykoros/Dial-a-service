// X-04 Not found: the same screen for "doesn't exist" and "not yours" (403 and 404),
// so nobody learns what exists.
import { useTranslation } from "react-i18next";

import { Button } from "@/components/Button";

export interface X04NotFoundProps {
  /** Where "Back to home" goes; none for an address no business uses. */
  homePath?: string;
  onHome?: (path: string) => void;
}

export function X04NotFound({
  homePath,
  onHome = (path) => window.location.assign(path),
}: X04NotFoundProps) {
  const { t } = useTranslation("shared");
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-surface p-4 text-center">
      <h1 className="font-heading text-section-title text-text">{t("X-04.title")}</h1>
      {homePath && <Button onClick={() => onHome(homePath)}>{t("X-04.button.home")}</Button>}
    </main>
  );
}
