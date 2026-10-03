// S-02 Register this device (11-staff-app.md): device name and branch; managers and
// owners only. Registering signs the manager out of the device, leaving it on X-15.
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MapPin } from "lucide-react";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";
import { z } from "zod";

import { api, unwrap } from "@/api/client";
import { asApiError, type ApiError } from "@/api/errors";
import { X04NotFound } from "@/apps/shared/screens/X04NotFound";
import { AuthLayout } from "@/apps/shared/signin/AuthLayout";
import { MANAGING_ROLES, useMe } from "@/apps/shared/signin/session";
import {
  currentDeviceKey,
  fetchCurrentDevice,
  SWITCH_PATH,
  type SwitchState,
} from "@/apps/staff/device";
import { Banner } from "@/components/Banner";
import { Button } from "@/components/Button";
import { ChoiceGroup, Radio } from "@/components/choices";
import { EmptyState } from "@/components/EmptyState";
import { TextInput } from "@/components/fields";
import { SkeletonRow } from "@/components/Skeleton";
import { ActionError, FirstLoad, ServerErrorBanner } from "@/components/states";
import { applyFieldErrors } from "@/lib/forms";
import { useActionKey } from "@/lib/idempotency";

interface Values {
  name: string;
  branch_id: string;
}

export const myBranchesKey = ["me", "branches"] as const;

type Branch = { id: string; name: string };

export function S02RegisterDevice() {
  const { t } = useTranslation("shared");
  const navigate = useNavigate();
  const me = useMe();
  const branches = useQuery({
    queryKey: myBranchesKey,
    queryFn: () => unwrap(api.GET("/api/v1/me/branches")),
  });

  if (me.data && !MANAGING_ROLES.includes(me.data.role)) {
    // Managers and owners only; the same screen as "not found" for everyone else.
    return <X04NotFound homePath="/staff" onHome={(path) => void navigate(path)} />;
  }

  return (
    <AuthLayout title={t("S-02.title")}>
      {branches.isPending ? (
        <FirstLoad
          skeleton={
            <div>
              <SkeletonRow />
              <SkeletonRow />
            </div>
          }
        />
      ) : branches.isError ? (
        <ServerErrorBanner
          error={asApiError(branches.error)}
          onRetry={() => void branches.refetch()}
        />
      ) : branches.data.length === 0 ? (
        <EmptyState icon={MapPin} message={t("S-02.no_branches")} />
      ) : (
        <RegisterForm branches={branches.data} />
      )}
    </AuthLayout>
  );
}

function RegisterForm({ branches }: { branches: Branch[] }) {
  const { t } = useTranslation("shared");
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const action = useActionKey();
  const [error, setError] = useState<ApiError | null>(null);

  const schema = useMemo(
    () =>
      z.object({
        name: z.string().trim().min(1, t("S-02.name_required")),
        branch_id: z.string().min(1, t("S-02.branch_required")),
      }),
    [t],
  );
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    // One branch: chosen already.
    defaultValues: { name: "", branch_id: branches.length === 1 ? branches[0]!.id : "" },
  });

  const register = useMutation({
    mutationFn: (values: Values) =>
      unwrap(
        api.POST("/api/v1/staff/devices", {
          body: values,
          headers: { "Idempotency-Key": action.for(values) },
        }),
      ),
    onSuccess: async () => {
      action.done();
      // The device cookie is set now; X-15 needs the device's roster.
      await queryClient.fetchQuery({ queryKey: currentDeviceKey, queryFn: fetchCurrentDevice });
      // The server signed this person out of the device; X-15 forgets them here.
      const state: SwitchState = { endSession: "forget" };
      void navigate(SWITCH_PATH, { replace: true, state });
    },
    onError: (thrown) => {
      const failure = asApiError(thrown);
      setError(failure);
      applyFieldErrors(failure, form.setError, ["name", "branch_id"]);
    },
  });

  const submit = form.handleSubmit((values) => {
    setError(null);
    register.mutate(values);
  });
  const errors = form.formState.errors;

  return (
    <form onSubmit={(event) => void submit(event)} noValidate className="flex flex-col gap-4">
      <Banner tone="info">{t("S-02.explainer")}</Banner>
      <ActionError
        error={error}
        onRetry={() => void submit()}
        onThrottleDone={() => setError(null)}
      />
      <TextInput
        label={t("S-02.name")}
        hint={t("S-02.name_hint")}
        maxLength={60}
        error={errors.name?.message}
        {...form.register("name")}
      />
      <ChoiceGroup legend={t("S-02.branch")} error={errors.branch_id?.message}>
        {branches.map((branch) => (
          <Radio
            key={branch.id}
            value={branch.id}
            label={branch.name}
            {...form.register("branch_id")}
          />
        ))}
      </ChoiceGroup>
      <Button type="submit" fullWidth loading={register.isPending}>
        {t("S-02.button.register")}
      </Button>
    </form>
  );
}
