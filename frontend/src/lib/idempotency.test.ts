import { renderHook } from "@testing-library/react";

import { ActionKey, fingerprint, useActionKey } from "@/lib/idempotency";

describe("ActionKey", () => {
  it("reuses the key when the same action is retried", () => {
    const action = new ActionKey();
    const first = action.for({ phone: "0712345678", amount: "450.00" });
    expect(action.for({ amount: "450.00", phone: "0712345678" })).toBe(first);
  });

  it("starts a new action when the input changes", () => {
    const action = new ActionKey();
    const first = action.for({ amount: "450.00" });
    expect(action.for({ amount: "500.00" })).not.toBe(first);
  });

  it("starts a new action after success", () => {
    const action = new ActionKey();
    const first = action.for({ amount: "450.00" });
    action.done();
    expect(action.for({ amount: "450.00" })).not.toBe(first);
  });

  it("handles actions with no body", () => {
    const action = new ActionKey();
    expect(action.for(undefined)).toBe(action.for(undefined));
  });

  it("keeps one action key per component across renders", () => {
    const { result, rerender } = renderHook(() => useActionKey());
    const first = result.current;
    rerender();
    expect(result.current).toBe(first);
  });
});

describe("fingerprint", () => {
  it("ignores key order at every depth but not array order", () => {
    expect(fingerprint({ a: 1, b: { d: 2, c: 3 } })).toBe(fingerprint({ b: { c: 3, d: 2 }, a: 1 }));
    expect(fingerprint([1, 2])).not.toBe(fingerprint([2, 1]));
  });
});
