// X-13 Set new password, shared by password reset and accepting an invitation.
// The live checklist mirrors the server's rules (settings AUTH_PASSWORD_VALIDATORS):
// at least 8 characters and not only numbers are checked as you type; "not a common
// password" needs the server's list, so it's checked when you save.
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { Check, Circle, ShieldCheck, type LucideIcon } from "lucide-react";
import { useMemo, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { asApiError, type ApiError } from "@/api/errors";
import { AuthLayout } from "@/apps/shared/signin/AuthLayout";
import { Button } from "@/components/Button";
import { PasswordInput } from "@/components/fields";
import { ActionError } from "@/components/states";
import { applyFieldErrors } from "@/lib/forms";

export const MIN_PASSWORD_LENGTH = 8;

interface Values {
  password: string;
  confirm: string;
}

export function passwordChecks(password: string) {
  return {
    length: password.length >= MIN_PASSWORD_LENGTH,
    notNumeric: password.length > 0 && !/^\d+$/.test(password),
  };
}

export interface X13SetNewPasswordProps {
  /** Save the password; throws ApiError. Field errors for "password" go under the field. */
  onSave: (password: string) => Promise<unknown>;
}

export function X13SetNewPassword({ onSave }: X13SetNewPasswordProps) {
  const { t } = useTranslation("shared");
  const [error, setError] = useState<ApiError | null>(null);

  const schema = useMemo(
    () =>
      z
        .object({ password: z.string(), confirm: z.string() })
        .refine((v) => v.password === v.confirm, {
          path: ["confirm"],
          message: t("X-13.mismatch"),
        }),
    [t],
  );
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { password: "", confirm: "" },
  });
  const [password, confirm] = useWatch({ control: form.control, name: ["password", "confirm"] });
  const checks = passwordChecks(password);

  const save = useMutation({
    mutationFn: (values: Values) => onSave(values.password),
    onError: (thrown) => {
      const failure = asApiError(thrown);
      setError(failure);
      applyFieldErrors(failure, form.setError, ["password"]);
    },
  });

  const submit = form.handleSubmit((values) => {
    setError(null);
    save.mutate(values);
  });
  const errors = form.formState.errors;

  return (
    <AuthLayout title={t("X-13.title")}>
      <form onSubmit={(event) => void submit(event)} noValidate className="flex flex-col gap-4">
        <ActionError
          error={error}
          onRetry={() => void submit()}
          onThrottleDone={() => setError(null)}
        />
        <PasswordInput
          label={t("X-13.new_password")}
          autoComplete="new-password"
          error={errors.password?.message}
          {...form.register("password")}
        />
        <ul className="flex flex-col gap-1" aria-label={t("X-13.rules")}>
          <Rule met={checks.length} label={t("X-13.rule.length")} />
          <Rule met={checks.notNumeric} label={t("X-13.rule.not_numeric")} />
          <Rule
            met={null}
            label={t("X-13.rule.not_common")}
            hint={t("X-13.rule.checked_on_save")}
          />
        </ul>
        <PasswordInput
          label={t("X-13.confirm_password")}
          autoComplete="new-password"
          error={errors.confirm?.message}
          {...form.register("confirm")}
        />
        <Button
          type="submit"
          fullWidth
          loading={save.isPending}
          disabled={!checks.length || !checks.notNumeric || !confirm || error?.code === "throttled"}
        >
          {t("X-13.button.save")}
        </Button>
      </form>
    </AuthLayout>
  );
}

/** One checklist line: an icon and words, so it reads without colour. */
function Rule({ met, label, hint }: { met: boolean | null; label: string; hint?: string }) {
  const { t } = useTranslation("shared");
  const Icon: LucideIcon = met === null ? ShieldCheck : met ? Check : Circle;
  const status = met === null ? hint : met ? t("X-13.rule_met") : t("X-13.rule_unmet");
  return (
    <li
      className={`flex items-center gap-2 text-secondary ${met ? "text-success" : "text-text-muted"}`}
    >
      <Icon aria-hidden size={20} strokeWidth={1.75} />
      <span className="text-text">{label}</span>
      {met === null ? (
        <span className="text-caption text-text-muted">{hint}</span>
      ) : (
        <span className="sr-only">{status}</span>
      )}
    </li>
  );
}
