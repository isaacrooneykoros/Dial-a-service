// X-10 Log in (10-screens-shared.md). The error is always "Phone number or password is
// incorrect" (the server's message), never which part. Log in stays disabled until
// both fields are filled. Success goes to the page the user was trying to reach.
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useSearchParams } from "react-router";
import { z } from "zod";

import { api, unwrap } from "@/api/client";
import { asApiError, type ApiError } from "@/api/errors";
import { AuthLayout } from "@/apps/shared/signin/AuthLayout";
import { completeSignIn } from "@/apps/shared/signin/session";
import { Button } from "@/components/Button";
import { PasswordInput, PhoneInput } from "@/components/fields";
import { ActionError } from "@/components/states";
import { homePathFor, type AppId } from "@/lib/apps";
import { safeReturnTo } from "@/lib/auth";
import { applyFieldErrors } from "@/lib/forms";
import { looksLikeKenyanMobile } from "@/lib/phone";

interface Values {
  phone: string;
  password: string;
}

export function X10Login({ app }: { app: AppId }) {
  const { t } = useTranslation("shared");
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const queryClient = useQueryClient();
  const [error, setError] = useState<ApiError | null>(null);
  const home = homePathFor(app);

  const schema = useMemo(
    () =>
      z.object({
        phone: z.string().refine(looksLikeKenyanMobile, t("field.phone_invalid")),
        password: z.string(),
      }),
    [t],
  );
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { phone: "", password: "" },
  });
  const [phone, password] = useWatch({ control: form.control, name: ["phone", "password"] });

  const login = useMutation({
    mutationFn: (values: Values) => unwrap(api.POST("/api/v1/auth/login", { body: values })),
    onSuccess: (data) => {
      completeSignIn(queryClient, data);
      void navigate(safeReturnTo(params.get("returnTo"), home), { replace: true });
    },
    onError: (thrown) => {
      const failure = asApiError(thrown);
      setError(failure);
      applyFieldErrors(failure, form.setError, ["phone", "password"]);
    },
  });

  const submit = form.handleSubmit((values) => {
    setError(null);
    login.mutate(values);
  });
  const throttled = error?.code === "throttled";
  const errors = form.formState.errors;

  return (
    <AuthLayout title={t("X-10.title")}>
      <form onSubmit={(event) => void submit(event)} noValidate className="flex flex-col gap-4">
        <ActionError
          error={error}
          onRetry={() => void submit()}
          onThrottleDone={() => setError(null)}
        />
        <PhoneInput
          label={t("X-10.phone")}
          error={errors.phone?.message}
          {...form.register("phone")}
        />
        <PasswordInput
          label={t("X-10.password")}
          autoComplete="current-password"
          error={errors.password?.message}
          {...form.register("password")}
        />
        <Link
          to={`${home}/forgot-password`}
          className="inline-flex min-h-11 items-center self-start text-secondary font-medium text-brand-primary"
        >
          {t("X-10.forgot_password")}
        </Link>
        <Button
          type="submit"
          fullWidth
          loading={login.isPending}
          disabled={!phone.trim() || !password || throttled}
        >
          {t("X-10.button.log_in")}
        </Button>
      </form>
    </AuthLayout>
  );
}
