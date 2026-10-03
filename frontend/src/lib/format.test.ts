import {
  formatDate,
  formatMoney,
  formatName,
  formatPhone,
  formatRecent,
  formatTime,
  formatTimeWindow,
  formatWeight,
  maskPhone,
} from "@/lib/format";

describe("formatMoney", () => {
  it.each([
    ["1250.00", "KSh 1,250"],
    ["1250", "KSh 1,250"],
    ["0.00", "KSh 0"],
    ["999.49", "KSh 999"],
    ["999.50", "KSh 1,000"], // half-up, as pricing.py
    ["1234567.00", "KSh 1,234,567"],
    ["-450.00", "-KSh 450"],
    ["-0.40", "KSh 0"],
    ["0007.00", "KSh 7"],
    ["9999999999.99", "KSh 10,000,000,000"],
  ])("%s -> %s", (amount, expected) => {
    expect(formatMoney(amount)).toBe(expected);
  });

  it("keeps the code for other currencies", () => {
    expect(formatMoney("10.00", "UGX")).toBe("UGX 10");
  });

  it("never accepts anything but a decimal string", () => {
    expect(() => formatMoney("12,50")).toThrow("Not a decimal amount");
    expect(() => formatMoney("abc")).toThrow();
    expect(() => formatMoney("")).toThrow();
  });

  it("is exact where floats are not", () => {
    // 0.1 + 0.2 style errors can't happen: digits are rounded as text.
    expect(formatMoney("1000000000000.50")).toBe("KSh 1,000,000,000,001");
  });
});

describe("formatWeight", () => {
  it.each([
    ["6.40", "6.4 kg"],
    ["6.45", "6.5 kg"],
    ["6.44", "6.4 kg"],
    ["0.05", "0.1 kg"],
    ["12", "12.0 kg"],
    ["9.96", "10.0 kg"],
  ])("%s -> %s", (kg, expected) => {
    expect(formatWeight(kg)).toBe(expected);
  });
});

describe("dates and times (Africa/Nairobi)", () => {
  const now = new Date("2026-10-02T09:00:00Z"); // Fri 2 Oct, 12:00 in Nairobi

  it("shows weekday, day and month this year", () => {
    expect(formatDate("2026-10-01T07:30:00Z", { now })).toBe("Thu 1 Oct");
  });

  it("adds the year only when it isn't this year", () => {
    expect(formatDate("2025-12-24T07:30:00Z", { now })).toBe("Wed 24 Dec 2025");
  });

  it("uses the business's timezone, not the phone's", () => {
    // 22:30 UTC on 1 Oct is already 2 Oct in Nairobi.
    expect(formatDate("2026-10-01T22:30:00Z", { now })).toBe("Fri 2 Oct");
  });

  it.each([
    ["2026-10-02T07:00:00Z", "10am"],
    ["2026-10-02T09:00:00Z", "12pm"],
    ["2026-10-02T07:30:00Z", "10:30am"],
    ["2026-10-02T21:00:00Z", "12am"],
  ])("time %s -> %s", (iso, expected) => {
    expect(formatTime(iso)).toBe(expected);
  });

  it("formats a time window with an en dash", () => {
    expect(formatTimeWindow("2026-10-02T07:00:00Z", "2026-10-02T09:00:00Z")).toBe("10am–12pm");
  });

  it.each([
    ["2026-10-02T08:59:40Z", "Just now"],
    ["2026-10-02T08:59:00Z", "1 min ago"],
    ["2026-10-02T08:55:00Z", "5 min ago"],
    ["2026-10-02T08:00:01Z", "59 min ago"],
    ["2026-10-02T08:00:00Z", "11am"],
    ["2026-09-30T08:00:00Z", "Wed 30 Sept"],
  ])("recent %s -> %s", (iso, expected) => {
    expect(formatRecent(iso, { now })).toBe(expected.replace("Sept", formatMonthOfSeptember()));
  });
});

/** Intl prints September as "Sep" or "Sept" depending on the ICU version. */
function formatMonthOfSeptember(): string {
  return new Intl.DateTimeFormat("en-GB", { month: "short" }).format(
    new Date("2026-09-15T12:00:00Z"),
  );
}

describe("people", () => {
  it.each([
    ["+254712345678", "0712 345 678", "0712 ••• 678"],
    ["+254110345678", "0110 345 678", "0110 ••• 678"],
  ])("%s", (e164, local, masked) => {
    expect(formatPhone(e164)).toBe(local);
    expect(maskPhone(e164)).toBe(masked);
  });

  it("leaves numbers it doesn't recognise alone, and never shows them when masking", () => {
    expect(formatPhone("+14155550123")).toBe("+14155550123");
    expect(maskPhone("+14155550123")).toBe("•••");
  });

  it.each([
    [["Wanjiru", "Kamau"], "Wanjiru K."],
    [["Juma", "otieno"], "Juma O."],
    [["Achieng", ""], "Achieng"],
    [[" Achieng ", " "], "Achieng"],
  ])("%j -> %s", ([first, last], expected) => {
    expect(formatName(first as string, last as string)).toBe(expected);
  });
});
