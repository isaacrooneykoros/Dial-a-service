// The staff app's home until the counter screens arrive (M2 onwards): who is signed
// in, and the M1 actions — register this device (S-02, managers and owners), switch
// user on a registered device (X-15), or log out.
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { MANAGING_ROLES, useLogout, useMe } from "@/apps/shared/signin/session";
import { useLockDevice } from "@/apps/staff/device";
import { Button } from "@/components/Button";
import { formatName } from "@/lib/format";

export function StaffHome({ registered }: { registered: boolean }) {
  const { t } = useTranslation("shared");
  const me = useMe();
  const logout = useLogout("staff");
  const lock = useLockDevice();
  const canRegister = !registered && me.data && MANAGING_ROLES.includes(me.data.role);

  return (
    <main className="mx-auto flex max-w-xl flex-col gap-4 p-4">
      <h1 className="text-page-title font-heading text-text">{t("areas.staff")}</h1>
      {me.data && (
        <p className="text-body text-text">
          {t("home.signed_in_as", { name: formatName(me.data.first_name, me.data.last_name) })}
        </p>
      )}
      <p className="text-body text-text-muted">{t("placeholder.coming_soon")}</p>
      <div className="flex flex-wrap gap-2">
        {canRegister && (
          <Link
            to="/staff/register-device"
            className="inline-flex min-h-11 items-center rounded-control border border-border bg-surface px-4 text-body font-semibold text-text"
          >
            {t("S-02.title")}
          </Link>
        )}
        {registered ? (
          <Button onClick={lock}>{t("X-15.button.switch_user")}</Button>
        ) : (
          <Button variant="secondary" onClick={() => void logout()}>
            {t("home.log_out")}
          </Button>
        )}
      </div>
    </main>
  );
}
