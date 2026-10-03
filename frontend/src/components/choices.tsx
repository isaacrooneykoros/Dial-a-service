// Checkbox and radio choices: the whole row is the tap target (at least 44 px).
import { useId, type InputHTMLAttributes, type ReactNode, type Ref } from "react";

interface ChoiceProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label: ReactNode;
  hint?: string;
  ref?: Ref<HTMLInputElement>;
}

function Choice({ type, label, hint, id, ...rest }: ChoiceProps & { type: "checkbox" | "radio" }) {
  const autoId = useId();
  const inputId = id ?? autoId;
  return (
    <label htmlFor={inputId} className="flex min-h-11 cursor-pointer items-start gap-3 py-2">
      <input
        id={inputId}
        type={type}
        className="mt-0.5 size-5 shrink-0 accent-brand-primary"
        aria-describedby={hint ? `${inputId}-hint` : undefined}
        {...rest}
      />
      <span className="flex flex-col">
        <span className="text-body text-text">{label}</span>
        {hint && (
          <span id={`${inputId}-hint`} className="text-secondary text-text-muted">
            {hint}
          </span>
        )}
      </span>
    </label>
  );
}

export function Checkbox(props: ChoiceProps) {
  return <Choice type="checkbox" {...props} />;
}

export function Radio(props: ChoiceProps) {
  return <Choice type="radio" {...props} />;
}

/** A labelled group of choices, with its error under it. */
export function ChoiceGroup({
  legend,
  error,
  children,
}: {
  legend: string;
  error?: string;
  children: ReactNode;
}) {
  const errorId = useId();
  return (
    <fieldset aria-describedby={error ? errorId : undefined} className="flex flex-col">
      <legend className="text-secondary font-medium text-text">{legend}</legend>
      {children}
      {error && (
        <p id={errorId} className="text-secondary text-danger">
          {error}
        </p>
      )}
    </fieldset>
  );
}
