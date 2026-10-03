// The PIN step at the end of X-14 (owner decision D-19): people who use the counter
// devices choose a 4-digit PIN, entered twice, for switching in on X-15.
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { api, unwrap } from "@/api/client";
import { asApiError, type ApiError } from "@/api/errors";
import { AuthLayout } from "@/apps/shared/signin/AuthLayout";
import { PinKeypad } from "@/components/PinKeypad";
import { ActionError } from "@/components/states";

export const PIN_LENGTH = 4;

export function PinStep({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation("shared");
  const [first, setFirst] = useState<string | null>(null);
  const [pin, setPin] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  const save = useMutation({
    mutationFn: (value: string) => unwrap(api.POST("/api/v1/me/pin", { body: { pin: value } })),
    onSuccess: onDone,
    onError: (thrown) => {
      const failure = asApiError(thrown);
      const pinMessage = failure.fields.pin?.[0];
      // A rule the PIN broke ("too easy to guess"): choose again. Anything else: show it.
      if (pinMessage) setProblem(pinMessage);
      else setError(failure);
      setFirst(null);
      setPin("");
    },
  });

  function complete(value: string) {
    if (first === null) {
      setFirst(value);
      setPin("");
      setProblem(null);
      return;
    }
    if (value !== first) {
      setProblem(t("X-14.pin.mismatch"));
      setFirst(null);
      setPin("");
      return;
    }
    setError(null);
    save.mutate(value);
  }

  const confirming = first !== null;
  return (
    <AuthLayout title={confirming ? t("X-14.pin.confirm_title") : t("X-14.pin.title")}>
      <div className="flex flex-col items-center gap-6">
        <p className="text-center text-body text-text-muted">{t("X-14.pin.intro")}</p>
        {problem && (
          <p role="alert" className="text-center text-secondary text-danger">
            {problem}
          </p>
        )}
        <ActionError
          error={error}
          onRetry={() => setError(null)}
          onThrottleDone={() => setError(null)}
        />
        <PinKeypad
          // A fresh keypad for each entry.
          key={confirming ? "confirm" : "choose"}
          label={confirming ? t("X-14.pin.confirm_title") : t("X-14.pin.title")}
          value={pin}
          onChange={setPin}
          onComplete={complete}
          length={PIN_LENGTH}
          disabled={save.isPending}
        />
      </div>
    </AuthLayout>
  );
}
