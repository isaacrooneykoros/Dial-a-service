// 4-digit keypad (X-15 and the PIN step): dots for what's entered, big keys, and a
// physical keyboard works too (counter tablets often have one). `onComplete` runs on
// the last digit. The digits are never shown.
import { Delete } from "lucide-react";
import { useEffect, useEffectEvent } from "react";
import { useTranslation } from "react-i18next";

export interface PinKeypadProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  onComplete?: (pin: string) => void;
  length?: number;
  disabled?: boolean;
}

const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "back"] as const;

export function PinKeypad({
  label,
  value,
  onChange,
  onComplete,
  length = 4,
  disabled = false,
}: PinKeypadProps) {
  const { t } = useTranslation("shared");

  function press(key: string) {
    if (disabled) return;
    if (key === "back") {
      onChange(value.slice(0, -1));
      return;
    }
    if (value.length >= length) return;
    const next = value + key;
    onChange(next);
    if (next.length === length) onComplete?.(next);
  }

  const onKey = useEffectEvent((event: KeyboardEvent) => {
    if (/^\d$/.test(event.key)) press(event.key);
    else if (event.key === "Backspace") press("back");
  });
  useEffect(() => {
    const listener = (event: KeyboardEvent) => onKey(event);
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);

  return (
    <div className="flex flex-col items-center gap-6">
      <div
        role="status"
        aria-label={t("field.pin_progress", { count: value.length, total: length, label })}
        className="flex gap-4"
      >
        {Array.from({ length }, (_, index) => (
          <span
            key={index}
            aria-hidden
            className={`size-4 rounded-full border-2 border-brand-primary ${
              index < value.length ? "bg-brand-primary" : "bg-transparent"
            }`}
          />
        ))}
      </div>
      <div className="grid w-full max-w-xs grid-cols-3 gap-3">
        {KEYS.map((key, index) =>
          key === "" ? (
            <span key={index} aria-hidden />
          ) : (
            <button
              key={index}
              type="button"
              disabled={disabled}
              onClick={() => press(key)}
              aria-label={key === "back" ? t("field.delete_digit") : undefined}
              className="flex h-16 items-center justify-center rounded-card border border-border bg-surface text-section-title text-text disabled:opacity-50"
            >
              {key === "back" ? <Delete aria-hidden size={24} strokeWidth={1.75} /> : key}
            </button>
          ),
        )}
      </div>
    </div>
  );
}
