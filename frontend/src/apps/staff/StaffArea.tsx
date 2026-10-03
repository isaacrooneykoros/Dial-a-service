// The staff app (/staff). On a registered counter device, signed-out people land on
// X-15 to switch in with a PIN, and the device locks after 5 idle minutes; anywhere
// else they log in with X-10.
import { Navigate, Route, Routes } from "react-router";

import { asApiError } from "@/api/errors";
import { SignInRoutes } from "@/apps/shared/signin/SignInRoutes";
import { SWITCH_PATH, useCurrentDevice } from "@/apps/staff/device";
import { IdleLock } from "@/apps/staff/IdleLock";
import { S02RegisterDevice } from "@/apps/staff/screens/S02RegisterDevice";
import { X15SwitchUser } from "@/apps/staff/screens/X15SwitchUser";
import { StaffHome } from "@/apps/staff/StaffHome";
import { FirstLoad, ServerErrorBanner } from "@/components/states";

/** Loaded only when opened, so other areas never download it. */
export default function StaffArea() {
  const device = useCurrentDevice();
  if (device.isPending) return <FirstLoad skeleton={null} />;
  if (device.isError) {
    return (
      <main className="mx-auto max-w-sm p-4">
        <ServerErrorBanner error={asApiError(device.error)} onRetry={() => void device.refetch()} />
      </main>
    );
  }
  const registered = device.data !== null;

  return (
    <SignInRoutes
      app="staff"
      signedOutPath={registered ? SWITCH_PATH : undefined}
      extraRoutes={
        <Route
          path="switch"
          element={registered ? <X15SwitchUser /> : <Navigate to="/staff/login" replace />}
        />
      }
      signedIn={
        <>
          {registered && <IdleLock />}
          <Routes>
            <Route path="register-device" element={<S02RegisterDevice />} />
            <Route path="*" element={<StaffHome registered={registered} />} />
          </Routes>
        </>
      }
    />
  );
}
