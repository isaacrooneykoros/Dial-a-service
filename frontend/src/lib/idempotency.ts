// Idempotency keys (CLAUDE.md section 6.5, ADR-0003 section 3).
//
// A key belongs to one user action, not one request: if "Save" fails on a bad
// connection and the user taps it again, the retry carries the same key, so the
// server does the action at most once ("Submitting" in 10-screens-shared.md).
// Changing the input starts a new action with a new key, because the server answers
// 409 when one key arrives with two different bodies.
import { useState } from "react";

export const IDEMPOTENCY_HEADER = "Idempotency-Key";

export function newIdempotencyKey(): string {
  return crypto.randomUUID();
}

/** JSON with sorted object keys, so {a, b} and {b, a} count as the same input. */
export function fingerprint(value: unknown): string {
  return JSON.stringify(value, (_key, item: unknown) => {
    if (item && typeof item === "object" && !Array.isArray(item)) {
      return Object.fromEntries(
        Object.entries(item as Record<string, unknown>).sort(([a], [b]) => (a < b ? -1 : 1)),
      );
    }
    return item;
  });
}

export class ActionKey {
  private key: string | null = null;
  private input: string | null = null;

  /** The key for submitting `input`: the same one again until the action succeeds. */
  for(input: unknown): string {
    const print = fingerprint(input) ?? "";
    if (this.key === null || print !== this.input) {
      this.key = newIdempotencyKey();
      this.input = print;
    }
    return this.key;
  }

  /** The action went through; the next submit is a new action. */
  done(): void {
    this.key = null;
    this.input = null;
  }
}

/** One ActionKey per component, kept across re-renders. */
export function useActionKey(): ActionKey {
  const [action] = useState(() => new ActionKey());
  return action;
}
