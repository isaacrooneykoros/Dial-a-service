// The only place money, weights, dates, times and phone numbers are formatted
// (CLAUDE.md section 6.8). Formats follow 10-screens-shared.md, "Content, accessibility
// and performance rules".
//
// Money arrives from the API as a decimal string ("1250.00") and is never turned into
// a floating-point number: rounding and digit grouping work on the digits themselves.
import i18n from "@/i18n";

/** A decimal amount as the API sends it, e.g. "1250.00". Never a number. */
export type Money = string;

const CURRENCY_LABELS: Record<string, string> = { KES: "KSh" };
const DECIMAL = /^(-)?(\d+)(?:\.(\d+))?$/;

interface DecimalParts {
  negative: boolean;
  whole: string;
  fraction: string;
}

function parseDecimal(value: string): DecimalParts {
  const match = DECIMAL.exec(value.trim());
  if (!match) throw new Error(`Not a decimal amount: ${JSON.stringify(value)}`);
  const whole = (match[2] ?? "0").replace(/^0+(?=\d)/, "");
  return { negative: match[1] === "-", whole, fraction: match[3] ?? "" };
}

/** Add one to a string of digits ("199" -> "200"). */
function incrementDigits(digits: string): string {
  const out = digits.split("");
  for (let i = out.length - 1; i >= 0; i -= 1) {
    if (out[i] !== "9") {
      out[i] = String(Number(out[i]) + 1);
      return out.join("");
    }
    out[i] = "0";
  }
  return `1${out.join("")}`;
}

/** Round to `places` decimals, half away from zero (half-up, as pricing.py does). */
function roundDigits(parts: DecimalParts, places: number): { whole: string; fraction: string } {
  const padded = parts.fraction.padEnd(places + 1, "0");
  const kept = padded.slice(0, places);
  const roundUp = Number(padded[places]) >= 5;
  if (!roundUp) return { whole: parts.whole, fraction: kept };
  const combined = incrementDigits(parts.whole + kept);
  const wholeLength = combined.length - places;
  return { whole: combined.slice(0, wholeLength) || "0", fraction: combined.slice(wholeLength) };
}

function groupThousands(digits: string): string {
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/** "1250.00" -> "KSh 1,250". Whole shillings, as everywhere a customer pays. */
export function formatMoney(amount: Money, currency = "KES"): string {
  const parts = parseDecimal(amount);
  const { whole } = roundDigits(parts, 0);
  const isZero = /^0+$/.test(whole);
  const sign = parts.negative && !isZero ? "-" : "";
  const label = CURRENCY_LABELS[currency] ?? currency;
  return `${sign}${label} ${groupThousands(whole)}`;
}

/** "6.40" -> "6.4 kg" (one decimal). */
export function formatWeight(kilograms: string): string {
  const { whole, fraction } = roundDigits(parseDecimal(kilograms), 1);
  return `${groupThousands(whole)}.${fraction} kg`;
}

// --- Dates and times ---------------------------------------------------------------

/** The business's timezone comes from /business/config; Kenya by default. */
export const DEFAULT_TIME_ZONE = "Africa/Nairobi";

function partsIn(date: Date, timeZone: string, options: Intl.DateTimeFormatOptions) {
  const parts = new Intl.DateTimeFormat("en-GB", { timeZone, ...options }).formatToParts(date);
  return Object.fromEntries(parts.map((part) => [part.type, part.value])) as Record<string, string>;
}

function yearIn(date: Date, timeZone: string): string {
  return partsIn(date, timeZone, { year: "numeric" }).year ?? "";
}

/** "Thu 2 Oct"; adds the year only if it isn't this year. */
export function formatDate(
  value: string | Date,
  { timeZone = DEFAULT_TIME_ZONE, now = new Date() }: { timeZone?: string; now?: Date } = {},
): string {
  const date = typeof value === "string" ? new Date(value) : value;
  const p = partsIn(date, timeZone, { weekday: "short", day: "numeric", month: "short" });
  const base = `${p.weekday} ${p.day} ${p.month}`;
  const year = yearIn(date, timeZone);
  return year === yearIn(now, timeZone) ? base : `${base} ${year}`;
}

/** "10am", "10:30am", "12pm" in the business's timezone. */
export function formatTime(
  value: string | Date,
  { timeZone = DEFAULT_TIME_ZONE }: { timeZone?: string } = {},
): string {
  const date = typeof value === "string" ? new Date(value) : value;
  const p = partsIn(date, timeZone, { hour: "numeric", minute: "2-digit", hour12: true });
  const minutes = p.minute === "00" ? "" : `:${p.minute}`;
  const period = (p.dayPeriod ?? "").toLowerCase().replace(/\./g, "").replace(/\s/g, "");
  return `${Number(p.hour)}${minutes}${period}`;
}

/** "10am–12pm" (an en dash, as in the content rules). */
export function formatTimeWindow(
  start: string | Date,
  end: string | Date,
  options: { timeZone?: string } = {},
): string {
  return `${formatTime(start, options)}–${formatTime(end, options)}`;
}

/** "5 min ago" up to one hour, then the time (or the date if it wasn't today). */
export function formatRecent(
  value: string | Date,
  { timeZone = DEFAULT_TIME_ZONE, now = new Date() }: { timeZone?: string; now?: Date } = {},
): string {
  const date = typeof value === "string" ? new Date(value) : value;
  const minutes = Math.floor((now.getTime() - date.getTime()) / 60_000);
  if (minutes < 1) return i18n.t("shared:time.just_now");
  if (minutes < 60) return i18n.t("shared:time.minutes_ago", { count: minutes });
  const sameDay = formatDate(date, { timeZone, now }) === formatDate(now, { timeZone, now });
  return sameDay ? formatTime(date, { timeZone }) : formatDate(date, { timeZone, now });
}

// --- People -------------------------------------------------------------------------

const E164_KE = /^\+254(\d{9})$/;

/** "+254712345678" -> "0712 345 678". Anything else is returned unchanged. */
export function formatPhone(e164: string): string {
  const match = E164_KE.exec(e164);
  if (!match?.[1]) return e164;
  const national = `0${match[1]}`;
  return `${national.slice(0, 4)} ${national.slice(4, 7)} ${national.slice(7)}`;
}

/** "+254712345678" -> "0712 ••• 678" (lists and public pages). */
export function maskPhone(e164: string): string {
  const match = E164_KE.exec(e164);
  if (!match?.[1]) return "•••";
  const national = `0${match[1]}`;
  return `${national.slice(0, 4)} ••• ${national.slice(7)}`;
}

/** Other people's names: first name and surname initial, "Wanjiru K.". */
export function formatName(firstName: string, lastName = ""): string {
  const initial = lastName.trim().charAt(0).toUpperCase();
  return initial ? `${firstName.trim()} ${initial}.` : firstName.trim();
}
