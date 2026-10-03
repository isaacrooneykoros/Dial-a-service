// X-12 Enter code (10-screens-shared.md), shared by every flow that sends a code
// (forgot password now, invitations in X-14). The code is submitted as soon as the
// sixth digit is in. After 3 wrong tries it says how many attempts are left; after 5
// the code is dead and a new one is needed. "Resend code" waits 60 seconds.
import { useMutation } from "@tanstack/react-query";
import { useEffect, useEffectEvent, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { asApiError, type ApiError } from "@/api/errors";
import { AuthLayout } from "@/apps/shared/signin/AuthLayout";
import { Banner } from "@/components/Banner";
import { Button } from "@/components/Button";
import { CodeInput } from "@/components/CodeInput";
import { ActionError } from "@/components/states";
import { formatPhone } from "@/lib/format";
import { useCountdown } from "@/lib/timers";

export const CODE_LENGTH = 6;
/** Seconds before "Resend code" works (the server allows a new code 60 s apart). */
export const RESEND_SECONDS = 60;
/** Codes allow 5 tries; "attempts left" shows after the third wrong one. */
export const SHOW_ATTEMPTS_LEFT_AT = 2;

const CODE_ERRORS = new Set(["invalid_code", "code_expired", "code_locked"]);
const DEAD_CODE = new Set(["code_expired", "code_locked"]);

export interface X12EnterCodeProps {
  /** E.164 where known, so it shows as 0712 345 678. */
  phone: string;
  /** The previous screen's answer, such as "If this number has an account, we've sent a code". */
  notice?: string;
  onVerify: (code: string) => Promise<unknown>;
  onResend: () => Promise<unknown>;
  /** Absent when the number can't change (an invitation is for one number). */
  onChangeNumber?: () => void;
}

export function X12EnterCode({
  phone,
  notice,
  onVerify,
  onResend,
  onChangeNumber,
}: X12EnterCodeProps) {
  const { t } = useTranslation("shared");
  const errorId = useId();
  const [code, setCode] = useState("");
  const [error, setError] = useState<ApiError | null>(null);
  const [dead, setDead] = useState(false);
  const [resendRound, setResendRound] = useState(0);

  const verify = useMutation({
    mutationFn: onVerify,
    onError: (thrown) => {
      const failure = asApiError(thrown);
      setError(failure);
      if (DEAD_CODE.has(failure.code)) setDead(true);
    },
  });

  const resend = useMutation({
    mutationFn: onResend,
    onSuccess: () => {
      setCode("");
      setError(null);
      setDead(false);
      setResendRound((n) => n + 1);
    },
    onError: (thrown) => setError(asApiError(thrown)),
  });

  function submit(value: string) {
    if (value.length !== CODE_LENGTH || verify.isPending || dead) return;
    setError(null);
    verify.mutate(value);
  }

  // Android Chrome reads the code from the SMS (WebOTP): code messages end with
  // "@{this web address} #{code}" (D-51). Elsewhere the keyboard offers the code
  // instead (autocomplete="one-time-code").
  const fromSms = useEffectEvent((value: string) => {
    setCode(value);
    submit(value);
  });
  useEffect(() => {
    if (!("OTPCredential" in window)) return;
    const controller = new AbortController();
    const options = { otp: { transport: ["sms"] }, signal: controller.signal };
    navigator.credentials
      .get(options as CredentialRequestOptions)
      .then((credential) => {
        const value = (credential as { code?: unknown } | null)?.code;
        if (typeof value === "string" && /^\d{6}$/.test(value)) fromSms(value);
      })
      .catch(() => {
        // Cancelled or not available: the boxes still work.
      });
    return () => controller.abort();
  }, []);

  const codeError = error && CODE_ERRORS.has(error.code) ? error : null;
  const attemptsLeft =
    codeError?.code === "invalid_code" &&
    codeError.attemptsLeft !== null &&
    codeError.attemptsLeft <= SHOW_ATTEMPTS_LEFT_AT
      ? codeError.attemptsLeft
      : null;

  return (
    <AuthLayout title={t("X-12.title")}>
      <div className="flex flex-col gap-4">
        {resendRound > 0 ? (
          <Banner tone="info">{t("X-12.new_code_sent")}</Banner>
        ) : (
          notice && <Banner tone="info">{notice}</Banner>
        )}
        <p className="text-body text-text">{t("X-12.sent_to", { phone: formatPhone(phone) })}</p>
        <CodeInput
          label={t("X-12.code_label")}
          value={code}
          onChange={setCode}
          onComplete={submit}
          length={CODE_LENGTH}
          disabled={dead || verify.isPending}
          invalid={codeError !== null}
          describedBy={codeError ? errorId : undefined}
        />
        {codeError ? (
          <div id={errorId} role="alert" className="text-secondary text-danger">
            <p>{codeError.message}</p>
            {attemptsLeft !== null && <p>{t("X-12.attempts_left", { count: attemptsLeft })}</p>}
          </div>
        ) : (
          <ActionError
            error={error}
            onRetry={() => submit(code)}
            onThrottleDone={() => setError(null)}
          />
        )}
        <div className="flex flex-col items-start">
          <ResendCode
            key={resendRound}
            pending={resend.isPending}
            onResend={() => resend.mutate()}
          />
          {onChangeNumber && (
            <Button variant="text" onClick={onChangeNumber}>
              {t("X-12.change_number")}
            </Button>
          )}
        </div>
        <Button
          fullWidth
          loading={verify.isPending}
          disabled={code.length !== CODE_LENGTH || dead}
          onClick={() => submit(code)}
        >
          {t("X-12.button.continue")}
        </Button>
      </div>
    </AuthLayout>
  );
}

function ResendCode({ pending, onResend }: { pending: boolean; onResend: () => void }) {
  const { t } = useTranslation("shared");
  const left = useCountdown(RESEND_SECONDS);
  if (left > 0) {
    return (
      <p className="flex min-h-11 items-center text-secondary text-text-muted">
        {t("X-12.resend_in", { seconds: left })}
      </p>
    );
  }
  return (
    <Button variant="text" loading={pending} onClick={onResend}>
      {t("X-12.resend")}
    </Button>
  );
}
