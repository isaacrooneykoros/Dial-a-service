// 6-box code input (X-12): typing moves to the next box, Backspace goes back, pasting
// (or the keyboard's one-time-code suggestion) fills every box, and `onComplete` runs
// as soon as the last digit is in. Boxes fill in order, so the value never has gaps.
import { useEffect, useRef, type ClipboardEvent, type KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";

export interface CodeInputProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  onComplete?: (code: string) => void;
  length?: number;
  disabled?: boolean;
  invalid?: boolean;
  /** ID of the element describing the current error, for screen readers. */
  describedBy?: string;
}

export function CodeInput({
  label,
  value,
  onChange,
  onComplete,
  length = 6,
  disabled = false,
  invalid = false,
  describedBy,
}: CodeInputProps) {
  const { t } = useTranslation("shared");
  const boxes = useRef<(HTMLInputElement | null)[]>([]);
  // The latest value, updated before focus moves (the prop catches up a render later).
  const current = useRef(value);
  useEffect(() => {
    current.current = value;
  }, [value]);

  function update(next: string) {
    current.current = next;
    onChange(next);
  }

  function focusBox(index: number) {
    const box = boxes.current[Math.max(0, Math.min(index, length - 1))];
    box?.focus();
    box?.select();
  }

  function fillFrom(index: number, text: string) {
    const digits = text.replace(/\D/g, "");
    if (!digits) return;
    const now = current.current;
    const start = Math.min(index, now.length);
    const next = (now.slice(0, start) + digits + now.slice(start + digits.length)).slice(0, length);
    update(next);
    focusBox(start + digits.length);
    if (next.length === length) onComplete?.(next);
  }

  function onKeyDown(index: number, event: KeyboardEvent<HTMLInputElement>) {
    const now = current.current;
    if (event.key === "Backspace") {
      event.preventDefault();
      if (now[index]) {
        update(now.slice(0, index) + now.slice(index + 1));
        focusBox(index);
      } else if (index > 0) {
        update(now.slice(0, index - 1) + now.slice(index));
        focusBox(index - 1);
      }
    } else if (event.key === "ArrowLeft") {
      focusBox(index - 1);
    } else if (event.key === "ArrowRight") {
      focusBox(Math.min(index + 1, now.length));
    }
  }

  function onPaste(index: number, event: ClipboardEvent<HTMLInputElement>) {
    event.preventDefault();
    fillFrom(index, event.clipboardData.getData("text"));
  }

  return (
    <fieldset aria-describedby={describedBy} disabled={disabled}>
      <legend className="sr-only">{label}</legend>
      <div className="flex justify-between gap-2">
        {Array.from({ length }, (_, index) => (
          <input
            key={index}
            ref={(el) => {
              boxes.current[index] = el;
            }}
            value={value[index] ?? ""}
            onChange={(event) => {
              let text = event.target.value;
              // Typed next to the old digit instead of over it: keep only the new one.
              const old = current.current[index];
              if (old && text.length === 2) text = text.startsWith(old) ? text.slice(1) : text[0]!;
              fillFrom(index, text);
            }}
            onKeyDown={(event) => onKeyDown(index, event)}
            onPaste={(event) => onPaste(index, event)}
            // Boxes fill in order: tapping a later empty box goes to the next one to fill.
            onFocus={(event) => {
              const filled = current.current.length;
              if (index > filled) focusBox(filled);
              else event.target.select();
            }}
            inputMode="numeric"
            pattern="[0-9]*"
            autoComplete={index === 0 ? "one-time-code" : "off"}
            aria-label={t("field.code_digit", { n: index + 1, total: length })}
            aria-invalid={invalid || undefined}
            className={[
              "h-14 w-full min-w-11 rounded-control border bg-surface text-center text-section-title text-text",
              "disabled:opacity-50",
              invalid ? "border-danger" : "border-border",
            ].join(" ")}
          />
        ))}
      </div>
    </fieldset>
  );
}
