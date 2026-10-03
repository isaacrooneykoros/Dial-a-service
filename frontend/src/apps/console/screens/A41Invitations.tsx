// A-41 Team, the M1 part (D-19): invite a person (name, phone, role, branches, and
// the three rights for staff) and the pending invitations with Resend and Cancel.
// The rest of A-41 (people, roles, Reset PIN, Deactivate) arrives in M5.
import { zodResolver } from "@hookform/resolvers/zod";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MailOpen } from "lucide-react";
import { useMemo, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api, unwrap } from "@/api/client";
import { asApiError, type ApiError } from "@/api/errors";
import { nextCursor } from "@/api/query";
import type { components } from "@/api/schema";
import { useBusinessConfig } from "@/apps/shared/startup/BusinessConfigContext";
import { Banner } from "@/components/Banner";
import { Button } from "@/components/Button";
import { Checkbox, ChoiceGroup, Radio } from "@/components/choices";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { PhoneInput, TextInput } from "@/components/fields";
import { SkeletonRow } from "@/components/Skeleton";
import { ActionError, FirstLoad, ServerErrorBanner } from "@/components/states";
import { applyFieldErrors } from "@/lib/forms";
import { formatDate, formatPhone } from "@/lib/format";
import { useActionKey } from "@/lib/idempotency";
import { looksLikeKenyanMobile } from "@/lib/phone";

type Invitation = components["schemas"]["Invitation"];

export const INVITABLE_ROLES = ["manager", "accountant", "staff"] as const;
type InvitableRole = (typeof INVITABLE_ROLES)[number];
const RIGHTS = ["accept_cash", "give_discounts", "correct_prices"] as const;

export const invitationsKey = ["console", "invitations"] as const;

interface Values {
  first_name: string;
  last_name: string;
  phone: string;
  role: string;
  branch_ids: string[];
  rights: Record<(typeof RIGHTS)[number], boolean>;
}

const EMPTY: Values = {
  first_name: "",
  last_name: "",
  phone: "",
  role: "",
  branch_ids: [],
  rights: { accept_cash: false, give_discounts: false, correct_prices: false },
};

export function A41Invitations() {
  const { t } = useTranslation("shared");
  return (
    <section className="flex flex-col gap-6">
      <h2 className="font-heading text-section-title text-text">{t("A-41.title")}</h2>
      <InviteForm />
      <PendingInvitations />
    </section>
  );
}

function InviteForm() {
  const { t } = useTranslation("shared");
  const queryClient = useQueryClient();
  const action = useActionKey();
  const [error, setError] = useState<ApiError | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);
  const branches = useQuery({
    queryKey: ["me", "branches"],
    queryFn: () => unwrap(api.GET("/api/v1/me/branches")),
  });

  const schema = useMemo(
    () =>
      z.object({
        first_name: z.string().trim().min(1, t("A-41.first_name_required")),
        last_name: z.string().trim().min(1, t("A-41.last_name_required")),
        phone: z.string().refine(looksLikeKenyanMobile, t("field.phone_invalid")),
        role: z
          .string()
          .refine(
            (v) => (INVITABLE_ROLES as readonly string[]).includes(v),
            t("A-41.role_required"),
          ),
        branch_ids: z.array(z.string()),
        rights: z.object({
          accept_cash: z.boolean(),
          give_discounts: z.boolean(),
          correct_prices: z.boolean(),
        }),
      }),
    [t],
  );
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: EMPTY,
  });
  const role = useWatch({ control: form.control, name: "role" });

  const invite = useMutation({
    mutationFn: (values: Values) => {
      const body = {
        first_name: values.first_name.trim(),
        last_name: values.last_name.trim(),
        phone: values.phone,
        role: values.role as InvitableRole,
        branch_ids: values.branch_ids,
        // The three rights are for staff only.
        rights: values.role === "staff" ? values.rights : EMPTY.rights,
      };
      return unwrap(
        api.POST("/api/v1/console/invitations", {
          body,
          headers: { "Idempotency-Key": action.for(body) },
        }),
      );
    },
    onSuccess: (invitation) => {
      action.done();
      setSentTo(invitation.phone);
      form.reset(EMPTY);
      void queryClient.invalidateQueries({ queryKey: invitationsKey });
    },
    onError: (thrown) => {
      const failure = asApiError(thrown);
      setError(failure);
      applyFieldErrors(failure, form.setError, [
        "first_name",
        "last_name",
        "phone",
        "role",
        "branch_ids",
      ]);
    },
  });

  const submit = form.handleSubmit((values) => {
    setError(null);
    setSentTo(null);
    invite.mutate(values);
  });
  const errors = form.formState.errors;

  return (
    <form
      onSubmit={(event) => void submit(event)}
      noValidate
      className="flex flex-col gap-4 rounded-card border border-border bg-surface p-4"
    >
      <h3 className="font-heading text-card-title text-text">{t("A-41.invite_title")}</h3>
      {sentTo && <Banner tone="info">{t("A-41.sent", { phone: formatPhone(sentTo) })}</Banner>}
      <ActionError
        error={error}
        onRetry={() => void submit()}
        onThrottleDone={() => setError(null)}
      />
      <div className="grid gap-4 sm:grid-cols-2">
        <TextInput
          label={t("A-41.first_name")}
          autoComplete="off"
          error={errors.first_name?.message}
          {...form.register("first_name")}
        />
        <TextInput
          label={t("A-41.last_name")}
          autoComplete="off"
          error={errors.last_name?.message}
          {...form.register("last_name")}
        />
      </div>
      <PhoneInput
        label={t("X-10.phone")}
        autoComplete="off"
        error={errors.phone?.message}
        {...form.register("phone")}
      />
      <ChoiceGroup legend={t("A-41.role")} error={errors.role?.message}>
        {INVITABLE_ROLES.map((value) => (
          <Radio key={value} value={value} label={t(`roles.${value}`)} {...form.register("role")} />
        ))}
      </ChoiceGroup>
      <ChoiceGroup legend={t("A-41.branches")} error={errors.branch_ids?.message}>
        {branches.isError ? (
          <ServerErrorBanner
            error={asApiError(branches.error)}
            onRetry={() => void branches.refetch()}
          />
        ) : (
          (branches.data ?? []).map((branch) => (
            <Checkbox
              key={branch.id}
              value={branch.id}
              label={branch.name}
              {...form.register("branch_ids")}
            />
          ))
        )}
      </ChoiceGroup>
      {role === "staff" && (
        <ChoiceGroup legend={t("A-41.rights")}>
          {RIGHTS.map((right) => (
            <Checkbox
              key={right}
              label={t(`rights.${right}`)}
              {...form.register(`rights.${right}`)}
            />
          ))}
        </ChoiceGroup>
      )}
      <Button type="submit" fullWidth loading={invite.isPending}>
        {t("A-41.button.send")}
      </Button>
    </form>
  );
}

function PendingInvitations() {
  const { t } = useTranslation("shared");
  const pending = useInfiniteQuery({
    queryKey: invitationsKey,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/api/v1/console/invitations", {
          params: { query: pageParam ? { cursor: pageParam } : {} },
        }),
      ),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: nextCursor,
  });

  const rows = pending.data?.pages.flatMap((page) => page.results) ?? [];
  return (
    <div className="flex flex-col gap-2">
      <h3 className="font-heading text-card-title text-text">{t("A-41.pending_title")}</h3>
      {pending.isPending ? (
        <FirstLoad
          skeleton={
            <div>
              <SkeletonRow />
              <SkeletonRow />
              <SkeletonRow />
            </div>
          }
        />
      ) : pending.isError ? (
        <ServerErrorBanner
          error={asApiError(pending.error)}
          onRetry={() => void pending.refetch()}
        />
      ) : rows.length === 0 ? (
        <EmptyState icon={MailOpen} message={t("A-41.pending_empty")} />
      ) : (
        <>
          <ul className="flex flex-col">
            {rows.map((invitation) => (
              <InvitationRow key={invitation.id} invitation={invitation} />
            ))}
          </ul>
          {pending.hasNextPage && (
            <Button
              variant="secondary"
              loading={pending.isFetchingNextPage}
              onClick={() => void pending.fetchNextPage()}
            >
              {t("A-41.show_more")}
            </Button>
          )}
        </>
      )}
    </div>
  );
}

function InvitationRow({ invitation }: { invitation: Invitation }) {
  const { t } = useTranslation("shared");
  const { business } = useBusinessConfig();
  const queryClient = useQueryClient();
  const resendKey = useActionKey();
  const cancelKey = useActionKey();
  const [confirming, setConfirming] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const path = { params: { path: { id: invitation.id } } };

  const resend = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/console/invitations/{id}/resend", {
          ...path,
          headers: { "Idempotency-Key": resendKey.for(invitation.id) },
        }),
      ),
    onSuccess: () => {
      resendKey.done();
      setError(null);
      setNotice(t("A-41.resent"));
      void queryClient.invalidateQueries({ queryKey: invitationsKey });
    },
    onError: (thrown) => setError(asApiError(thrown)),
  });

  const cancel = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/console/invitations/{id}/cancel", {
          ...path,
          headers: { "Idempotency-Key": cancelKey.for(invitation.id) },
        }),
      ),
    onSuccess: () => {
      cancelKey.done();
      setConfirming(false);
      void queryClient.invalidateQueries({ queryKey: invitationsKey });
    },
    onError: (thrown) => {
      setConfirming(false);
      setError(asApiError(thrown));
    },
  });

  const name = `${invitation.first_name} ${invitation.last_name}`;
  return (
    <li className="flex flex-col gap-2 border-b border-border py-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex flex-col">
          <span className="text-body font-medium text-text">{name}</span>
          <span className="text-secondary text-text-muted">
            {formatPhone(invitation.phone)} · {t(`roles.${invitation.role}`)}
          </span>
          <span className="text-caption text-text-muted">
            {t("A-41.expires", {
              date: formatDate(invitation.expires_at, { timeZone: business.timezone }),
            })}
          </span>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" loading={resend.isPending} onClick={() => resend.mutate()}>
            {t("A-41.button.resend")}
          </Button>
          <Button variant="text" onClick={() => setConfirming(true)}>
            {t("A-41.button.cancel")}
          </Button>
        </div>
      </div>
      {notice && !error && <p className="text-secondary text-success">{notice}</p>}
      <ActionError error={error} onRetry={() => resend.mutate()} />
      {confirming && (
        <ConfirmDialog
          title={t("A-41.cancel_confirm.title", { name })}
          body={t("A-41.cancel_confirm.body")}
          confirmLabel={t("A-41.cancel_confirm.confirm")}
          cancelLabel={t("A-41.cancel_confirm.keep")}
          danger
          loading={cancel.isPending}
          onConfirm={() => cancel.mutate()}
          onCancel={() => setConfirming(false)}
        />
      )}
    </li>
  );
}
