// X-14 Accept invitation (10-screens-shared.md): "{Business} invited you to join as
// {role}", the invited number (read-only) and Send code. An expired invitation shows
// "Ask {business} to send a new invitation".
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router";

import { api, unwrap } from "@/api/client";
import { asApiError, type ApiError } from "@/api/errors";
import { X04NotFound } from "@/apps/shared/screens/X04NotFound";
import { AuthLayout } from "@/apps/shared/signin/AuthLayout";
import { inviteFlow } from "@/apps/shared/invite/inviteFlow";
import { Button } from "@/components/Button";
import { TextInput } from "@/components/fields";
import { Skeleton } from "@/components/Skeleton";
import { ActionError, FirstLoad, ServerErrorBanner } from "@/components/states";
import { formatPhone } from "@/lib/format";

export function invitationQueryKey(token: string) {
  return ["invitation", token] as const;
}

export function X14AcceptInvitation() {
  const { t } = useTranslation("shared");
  const { token = "" } = useParams();
  const navigate = useNavigate();
  const [error, setError] = useState<ApiError | null>(null);

  const invitation = useQuery({
    queryKey: invitationQueryKey(token),
    queryFn: () =>
      unwrap(api.GET("/api/v1/auth/invitations/{token}", { params: { path: { token } } })),
  });

  const sendCode = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/auth/invitations/{token}/send-code", { params: { path: { token } } }),
      ),
    onSuccess: (data) => {
      inviteFlow.start(token, invitation.data?.phone ?? "", data.message);
      void navigate(`/invite/${token}/code`);
    },
    onError: (thrown) => {
      const failure = asApiError(thrown);
      // Expired in the meantime: show the expired screen.
      if (failure.status === 410) void invitation.refetch();
      setError(failure);
    },
  });

  if (invitation.isPending) {
    return (
      <FirstLoad
        skeleton={
          <div className="mx-auto flex max-w-sm flex-col gap-4 px-4 py-12">
            <Skeleton className="h-8 w-3/4" />
            <Skeleton className="h-11 w-full" />
            <Skeleton className="h-11 w-full" />
          </div>
        }
      />
    );
  }

  if (invitation.isError) {
    const failure = asApiError(invitation.error);
    if (failure.status === 404) return <X04NotFound />;
    if (failure.status === 410) {
      // The server's words: "Ask {business} to send a new invitation".
      return (
        <AuthLayout title={failure.message}>
          <p className="text-body text-text-muted">{t("X-14.expired_hint")}</p>
        </AuthLayout>
      );
    }
    return (
      <main className="mx-auto max-w-sm p-4">
        <ServerErrorBanner error={failure} onRetry={() => void invitation.refetch()} />
      </main>
    );
  }

  const { business_name, role_label, phone } = invitation.data;
  return (
    <AuthLayout title={t("X-14.title", { business: business_name, role: role_label })}>
      <div className="flex flex-col gap-4">
        <ActionError
          error={error}
          onRetry={() => sendCode.mutate()}
          onThrottleDone={() => setError(null)}
        />
        <TextInput label={t("X-10.phone")} value={formatPhone(phone)} readOnly />
        <p className="text-secondary text-text-muted">{t("X-14.code_hint")}</p>
        <Button
          fullWidth
          loading={sendCode.isPending}
          disabled={error?.code === "throttled"}
          onClick={() => {
            setError(null);
            sendCode.mutate();
          }}
        >
          {t("X-11.button.send_code")}
        </Button>
      </div>
    </AuthLayout>
  );
}
