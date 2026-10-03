// Server field errors onto react-hook-form (10-screens-shared.md, "Field error"):
// the message goes under the field, focus moves to the first bad field, and what the
// user typed is never cleared. The server's envelope is the authority; client-side
// zod checks are only a convenience.
import type { FieldValues, Path, UseFormSetError } from "react-hook-form";

import type { ApiError } from "@/api/errors";

/**
 * Put each of the error's field messages on the matching form field, focusing the
 * first in form order. Returns the messages that belong to no field on this form
 * (for example "non_field_errors"), for the screen to show in a banner.
 */
export function applyFieldErrors<T extends FieldValues>(
  error: ApiError,
  setError: UseFormSetError<T>,
  formFields: readonly Path<T>[],
): string[] {
  const unmatched: string[] = [];
  for (const [name, messages] of Object.entries(error.fields)) {
    if (!(formFields as readonly string[]).includes(name)) unmatched.push(...messages);
  }
  let focused = false;
  for (const name of formFields) {
    const message = error.fields[name]?.[0];
    if (!message) continue;
    setError(name, { type: "server", message }, { shouldFocus: !focused });
    focused = true;
  }
  return unmatched;
}
