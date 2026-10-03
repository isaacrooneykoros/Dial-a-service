// X-15 Switch user (11-staff-app.md): on a registered device, the branch's people by
// first name and surname initial; tap a name and enter a 4-digit PIN. 5 wrong PINs
// lock the device until a manager (or the owner) signs in on it with a password (D-37).
// M1 shows initials; staff photos replace them in M3 (D-45).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Users } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from "react-router";

import { api, unwrap } from "@/api/client";
import { asApiError, type ApiError } from "@/api/errors";
import { AuthLayout } from "@/apps/shared/signin/AuthLayout";
import { completeSignIn } from "@/apps/shared/signin/session";
import {
  currentDeviceKey,
  fetchCurrentDevice,
  finishSession,
  type RosterEntry,
  type SwitchState,
} from "@/apps/staff/device";
import { Banner } from "@/components/Banner";
import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { PinKeypad } from "@/components/PinKeypad";
import { SkeletonRow } from "@/components/Skeleton";
import { ActionError, FirstLoad, ServerErrorBanner } from "@/components/states";
import { safeReturnTo } from "@/lib/auth";
import { formatName } from "@/lib/format";

export function X15SwitchUser() {
  const { t } = useTranslation("shared");
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const queryClient = useQueryClient();
  const [person, setPerson] = useState<RosterEntry | null>(null);
  const [pin, setPin] = useState("");
  const [error, setError] = useState<ApiError | null>(null);
  const location = useLocation();

  // Arriving from "Switch user", the idle lock or S-02: end the previous session now.
  const endPrevious = (location.state as SwitchState | null)?.endSession;
  useEffect(() => {
    if (!endPrevious) return;
    void finishSession(queryClient, endPrevious).then(() =>
      navigate(location.pathname + location.search, { replace: true, state: null }),
    );
  }, [endPrevious, queryClient, navigate, location.pathname, location.search]);

  const device = useQuery({
    queryKey: currentDeviceKey,
    queryFn: fetchCurrentDevice,
    // Always fresh here: the roster and the lock can change from the console.
    refetchOnMount: "always",
  });

  const pinSwitch = useMutation({
    mutationFn: (body: { user_id: string; pin: string }) =>
      unwrap(api.POST("/api/v1/auth/pin-switch", { body })),
    onSuccess: (signedIn) => {
      completeSignIn(queryClient, signedIn);
      void navigate(safeReturnTo(params.get("returnTo"), "/staff"), { replace: true });
    },
    onError: (thrown) => {
      const failure = asApiError(thrown);
      setError(failure);
      setPin("");
      if (failure.code === "device_locked") void device.refetch();
    },
  });

  if (device.isPending) {
    return (
      <FirstLoad
        skeleton={
          <div className="mx-auto max-w-sm px-4 py-12">
            <SkeletonRow />
            <SkeletonRow />
            <SkeletonRow />
          </div>
        }
      />
    );
  }
  if (device.isError) {
    return (
      <main className="mx-auto max-w-sm p-4">
        <ServerErrorBanner error={asApiError(device.error)} onRetry={() => void device.refetch()} />
      </main>
    );
  }
  // Removed in the console meanwhile: an ordinary browser again.
  if (device.data === null) return <Navigate to="/staff/login" replace />;

  const { device: info, roster } = device.data;
  const locked = device.data.locked || error?.code === "device_locked";
  const passwordLink = (
    <Link
      to="/staff/login"
      className="inline-flex min-h-11 items-center text-secondary font-medium text-brand-primary"
    >
      {t("X-15.log_in_with_password")}
    </Link>
  );

  const title = person ? t("X-15.enter_pin", { name: person.first_name }) : t("X-15.title");

  return (
    <AuthLayout title={title}>
      <div className="flex flex-col gap-4">
        <p className="text-center text-secondary text-text-muted">
          {t("X-15.device", { device: info.name, branch: info.branch.name })}
        </p>

        {locked ? (
          <Banner tone="error">{t("X-15.locked")}</Banner>
        ) : person ? (
          <>
            {error?.code === "wrong_pin" ? (
              <div role="alert" className="text-center text-secondary text-danger">
                <p>{error.message}</p>
                {error.attemptsLeft !== null && (
                  <p>{t("X-15.attempts_left", { count: error.attemptsLeft })}</p>
                )}
              </div>
            ) : (
              <ActionError
                error={error}
                onRetry={() => setError(null)}
                onThrottleDone={() => setError(null)}
              />
            )}
            <PinKeypad
              label={title}
              value={pin}
              onChange={setPin}
              onComplete={(value) => {
                setError(null);
                pinSwitch.mutate({ user_id: person.id, pin: value });
              }}
              disabled={pinSwitch.isPending || error?.code === "throttled"}
            />
            <Button
              variant="text"
              onClick={() => {
                setPerson(null);
                setPin("");
                setError(null);
              }}
            >
              {t("X-15.choose_someone_else")}
            </Button>
          </>
        ) : roster.length === 0 ? (
          <EmptyState icon={Users} message={t("X-15.empty")} />
        ) : (
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {roster.map((entry) => (
              <li key={entry.id}>
                <button
                  type="button"
                  onClick={() => setPerson(entry)}
                  className="flex w-full flex-col items-center gap-2 rounded-card border border-border bg-surface p-4"
                >
                  <span
                    aria-hidden
                    className="flex size-14 items-center justify-center rounded-full bg-brand-primary font-heading text-card-title text-brand-on-primary"
                  >
                    {entry.first_name.charAt(0).toUpperCase()}
                    {entry.last_initial}
                  </span>
                  <span className="text-body text-text">
                    {formatName(entry.first_name, entry.last_initial)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="flex justify-center">{passwordLink}</div>
      </div>
    </AuthLayout>
  );
}
