// Button (10-screens-shared.md, components): primary, secondary, text, danger.
// While `loading`, it shows a spinner inside, is disabled and tells screen readers
// it's busy ("Submitting" shared state).
import { LoaderCircle } from "lucide-react";
import type { ButtonHTMLAttributes } from "react";
import { useTranslation } from "react-i18next";

export type ButtonVariant = "primary" | "secondary" | "text" | "danger";

const VARIANTS: Record<ButtonVariant, string> = {
  primary: "bg-brand-primary text-brand-on-primary",
  secondary: "border border-border bg-surface text-text",
  text: "bg-transparent text-brand-primary",
  danger: "bg-danger text-brand-on-primary",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  loading?: boolean;
  fullWidth?: boolean;
}

export function Button({
  variant = "primary",
  loading = false,
  fullWidth = false,
  disabled,
  type = "button",
  className = "",
  children,
  ...rest
}: ButtonProps) {
  const { t } = useTranslation("shared");
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={[
        // At least 44 x 44 px (WCAG 2.1 AA tap targets)
        "relative inline-flex min-h-11 min-w-11 items-center justify-center gap-2",
        "rounded-control px-4 text-body font-semibold transition-opacity duration-150",
        "disabled:cursor-not-allowed disabled:opacity-50",
        VARIANTS[variant],
        fullWidth ? "w-full" : "",
        className,
      ].join(" ")}
      {...rest}
    >
      {loading && (
        <>
          <LoaderCircle aria-hidden size={20} strokeWidth={1.75} className="animate-spin" />
          <span className="sr-only">{t("state.submitting")}</span>
        </>
      )}
      {children}
    </button>
  );
}
