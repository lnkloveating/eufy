import { useId, type ReactNode } from "react";
import { AlertCircle } from "lucide-react";

export interface FieldProps {
  label: string;
  required?: boolean;
  hint?: ReactNode;
  error?: string | null;
  /** Render prop receives the id + aria attributes to spread on the control. */
  children: (props: {
    id: string;
    "aria-invalid": boolean;
    "aria-describedby": string | undefined;
  }) => ReactNode;
}

/**
 * Labelled form field wrapper. Wires up `htmlFor`, `aria-describedby` and
 * `aria-invalid` for accessibility so every control has an associated label
 * and error announcement.
 */
export function Field({ label, required, hint, error, children }: FieldProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy =
    [error ? errorId : null, hint ? hintId : null].filter(Boolean).join(" ") ||
    undefined;

  return (
    <div className="field">
      <label className="field-label" htmlFor={id}>
        {label}
        {required && (
          <span className="field-req" aria-hidden="true">
            *
          </span>
        )}
      </label>
      {hint && (
        <span className="field-hint" id={hintId}>
          {hint}
        </span>
      )}
      {children({
        id,
        "aria-invalid": Boolean(error),
        "aria-describedby": describedBy,
      })}
      {error && (
        <span className="field-error" id={errorId} role="alert">
          <AlertCircle size={13} aria-hidden="true" />
          {error}
        </span>
      )}
    </div>
  );
}
