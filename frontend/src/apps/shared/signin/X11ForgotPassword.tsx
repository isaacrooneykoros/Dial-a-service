// X-11 Forgot password: always answers "If this number has an account, we've sent a
// code" (the server's message, shown on X-12), whether or not the number exists.
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router";
import { z } from "zod";

import { api, unwrap } from "@/api/client";
import { asApiError, type ApiError } from "@/api/errors";
import { AuthLayout } from "@/apps/shared/signin/AuthLayout";
import { resetFlow } from "@/apps/shared/signin/session";
import { Banner } from "@/components/Banner";
import { Button } from "@/components/Button";
import { PhoneInput } from "@/components/fields";
import { ActionError } from "@/components/states";
import { homePathFor, type AppId } from "@/lib/apps";
import { applyFieldErrors } from "@/lib/forms";
import { looksLikeKenyanMobile } from "@/lib/phone";

interface Values {
  phone: string;
}

/** Why the user was sent back here (for example an expired reset), if they were. */
export interface X11State {
  notice?: string;
}

export function X11ForgotPassword({ app }: { app: AppId }) {
  const { t } = useTranslation("shared");
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState<ApiError | null>(null);
  const sentBack = (location.state as X11State | null)?.notice;

  const schema = useMemo(
    () => z.object({ phone: z.string().refine(looksLikeKenyanMobile, t("field.phone_invalid")) }),
    [t],
  );
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    // "Wrong number? Change it" on X-12 comes back here with the number filled in.
    defaultValues: { phone: resetFlow.get()?.phone ?? "" },
  });
  const phone = useWatch({ control: form.control, name: "phone" });

  const request = useMutation({
    mutationFn: (values: Values) =>
      unwrap(api.POST("/api/v1/auth/password-reset/request", { body: values })),
    onSuccess: (data, values) => {
      resetFlow.start(values.phone, data.message);
      void navigate(`${homePathFor(app)}/forgot-password/code`);
    },
    onError: (thrown) => {
      const failure = asApiError(thrown);
      setError(failure);
      applyFieldErrors(failure, form.setError, ["phone"]);
    },
  });

  const submit = form.handleSubmit((values) => {
    setError(null);
    request.mutate(values);
  });

  return (
    <AuthLayout title={t("X-11.title")}>
      <form onSubmit={(event) => void submit(event)} noValidate className="flex flex-col gap-4">
        {sentBack && !error && <Banner tone="warning">{sentBack}</Banner>}
        <p className="text-body text-text-muted">{t("X-11.intro")}</p>
        <ActionError
          error={error}
          onRetry={() => void submit()}
          onThrottleDone={() => setError(null)}
        />
        <PhoneInput
          label={t("X-10.phone")}
          error={form.formState.errors.phone?.message}
          {...form.register("phone")}
        />
        <Button
          type="submit"
          fullWidth
          loading={request.isPending}
          disabled={!phone.trim() || error?.code === "throttled"}
        >
          {t("X-11.button.send_code")}
        </Button>
      </form>
    </AuthLayout>
  );
}
