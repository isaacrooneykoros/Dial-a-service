import { useTranslation } from "react-i18next";

import { A41Invitations } from "@/apps/console/screens/A41Invitations";
import { MANAGING_ROLES, useLogout, useMe } from "@/apps/shared/signin/session";
import { SignInRoutes } from "@/apps/shared/signin/SignInRoutes";
import { Button } from "@/components/Button";
import { formatName } from "@/lib/format";

/** The console's home until the dashboard arrives: who is signed in and, for owners and managers, invitations (A-41, M1 part). */
function ConsoleHome() {
  const { t } = useTranslation("shared");
  const me = useMe();
  const logout = useLogout("console");
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 p-4">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-page-title font-heading text-text">{t("areas.console")}</h1>
        <Button variant="secondary" onClick={() => void logout()}>
          {t("home.log_out")}
        </Button>
      </header>
      {me.data && (
        <p className="text-body text-text">
          {t("home.signed_in_as", { name: formatName(me.data.first_name, me.data.last_name) })}
        </p>
      )}
      {me.data && MANAGING_ROLES.includes(me.data.role) ? (
        <A41Invitations />
      ) : (
        <p className="text-body text-text-muted">{t("placeholder.coming_soon")}</p>
      )}
    </main>
  );
}

/** The console route area. Loaded only when opened, so other areas never download it. */
export default function ConsoleArea() {
  return <SignInRoutes app="console" signedIn={<ConsoleHome />} />;
}
