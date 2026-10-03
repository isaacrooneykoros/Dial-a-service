// Kenyan mobile numbers on the client: shape checks and display only. The server
// normalises and is the authority (apps/accounts/phones.py accepts the same forms:
// 07…, 01…, 7…, 1…, +254…, 254…).
const SEPARATORS = /[\s()-]/g;
const KE_MOBILE = /^(?:\+?254|0)?([17]\d{8})$/;

/** "0712 345 678" -> "+254712345678"; null if it isn't shaped like a Kenyan mobile. */
export function normalizeKenyanMobile(value: string): string | null {
  const match = KE_MOBILE.exec(value.replace(SEPARATORS, ""));
  return match?.[1] ? `+254${match[1]}` : null;
}

export function looksLikeKenyanMobile(value: string): boolean {
  return normalizeKenyanMobile(value) !== null;
}
