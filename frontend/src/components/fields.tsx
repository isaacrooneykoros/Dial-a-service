// Inputs (10-screens-shared.md, components): text input, phone input with a fixed
// +254 prefix, password input with show/hide. Every input has a visible label, its
// error under it in plain words, and is at least 44 px tall and 16 px text.
import { Eye, EyeOff } from "lucide-react";
import { useId, useState, type InputHTMLAttributes, type ReactNode, type Ref } from "react";
import { useTranslation } from "react-i18next";

export interface TextInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "prefix"> {
  label: string;
  error?: string;
  hint?: string;
  /** Fixed text before the input, such as +254. */
  prefix?: string;
  /** A control inside the box after the input, such as show/hide. */
  trailing?: ReactNode;
  ref?: Ref<HTMLInputElement>;
}

export function TextInput({
  label,
  error,
  hint,
  prefix,
  trailing,
  id,
  className = "",
  ...rest
}: TextInputProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const hintId = `${inputId}-hint`;
  const errorId = `${inputId}-error`;
  const describedBy = [hint ? hintId : "", error ? errorId : ""].filter(Boolean).join(" ");
  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      <label htmlFor={inputId} className="text-secondary font-medium text-text">
        {label}
      </label>
      <div
        className={[
          "flex min-h-11 items-center rounded-control border bg-surface",
          "focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-brand-primary",
          error ? "border-danger" : "border-border",
        ].join(" ")}
      >
        {prefix && (
          <span className="pl-3 text-body text-text-muted" aria-hidden>
            {prefix}
          </span>
        )}
        <input
          id={inputId}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy || undefined}
          className="min-w-0 flex-1 bg-transparent px-3 py-2 text-body text-text focus-visible:outline-none"
          {...rest}
        />
        {trailing}
      </div>
      {hint && (
        <p id={hintId} className="text-caption text-text-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className="text-secondary text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

/** Phone input: +254 shown before it; accepts 07…, 01…, 7… and 1… (the server normalises). */
export function PhoneInput(props: Omit<TextInputProps, "prefix" | "type">) {
  return (
    <TextInput
      prefix="+254"
      type="tel"
      inputMode="tel"
      autoComplete="tel-national"
      maxLength={16}
      {...props}
    />
  );
}

export function PasswordInput(props: Omit<TextInputProps, "type" | "trailing">) {
  const { t } = useTranslation("shared");
  const [shown, setShown] = useState(false);
  const Icon = shown ? EyeOff : Eye;
  return (
    <TextInput
      type={shown ? "text" : "password"}
      autoCapitalize="off"
      spellCheck={false}
      trailing={
        <button
          type="button"
          onClick={() => setShown((s) => !s)}
          aria-label={shown ? t("field.hide_password") : t("field.show_password")}
          aria-pressed={shown}
          className="flex min-h-11 min-w-11 items-center justify-center text-text-muted"
        >
          <Icon aria-hidden size={24} strokeWidth={1.75} />
        </button>
      }
      {...props}
    />
  );
}
