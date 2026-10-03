import { ApiError } from "@/api/errors";
import { createQueryClient, nextCursor, shouldRetryQuery } from "@/api/query";

describe("query retries", () => {
  const server = new ApiError({ status: 500, code: "server_error", message: "x" });

  it("retries network failures twice and nothing else", () => {
    expect(shouldRetryQuery(0, ApiError.network())).toBe(true);
    expect(shouldRetryQuery(1, ApiError.network())).toBe(true);
    expect(shouldRetryQuery(2, ApiError.network())).toBe(false);
    expect(shouldRetryQuery(0, server)).toBe(false);
    expect(shouldRetryQuery(0, new Error("boom"))).toBe(false);
  });

  it("never retries mutations on its own", () => {
    expect(createQueryClient().getDefaultOptions().mutations?.retry).toBe(false);
  });
});

describe("nextCursor", () => {
  it("reads the cursor from DRF's next link", () => {
    expect(
      nextCursor({ next: "http://mamasafi.localhost/api/v1/x?cursor=cD0yMDI2&page_size=20" }),
    ).toBe("cD0yMDI2");
  });

  it("is undefined on the last page", () => {
    expect(nextCursor({ next: null })).toBeUndefined();
    expect(nextCursor({})).toBeUndefined();
  });
});
