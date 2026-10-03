// Confirm dialog (10-screens-shared.md, components) for destructive actions: a
// question, what happens, and two buttons that say what they do. Escape cancels;
// focus starts on the safe choice.
import { useEffect, useEffectEvent, useId, useRef } from "react";

import { Button } from "@/components/Button";

export interface ConfirmDialogProps {
  title: string;
  body?: string;
  confirmLabel: string;
  cancelLabel: string;
  danger?: boolean;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  title,
  body,
  confirmLabel,
  cancelLabel,
  danger = false,
  loading = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const titleId = useId();
  const cancelRef = useRef<HTMLButtonElement>(null);
  const escape = useEffectEvent((event: KeyboardEvent) => {
    if (event.key === "Escape") onCancel();
  });
  useEffect(() => {
    cancelRef.current?.focus();
    const listener = (event: KeyboardEvent) => escape(event);
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-text/40 p-4 sm:items-center">
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="flex w-full max-w-sm flex-col gap-4 rounded-card bg-surface p-4 shadow-sheet"
      >
        <h2 id={titleId} className="font-heading text-card-title text-text">
          {title}
        </h2>
        {body && <p className="text-body text-text-muted">{body}</p>}
        <div className="flex justify-end gap-2">
          <Button ref={cancelRef} variant="secondary" onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button variant={danger ? "danger" : "primary"} loading={loading} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
