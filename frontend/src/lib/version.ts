// This build's version (VITE_APP_VERSION, set by CI) and the X-02 comparison.

export const APP_VERSION: string = import.meta.env.VITE_APP_VERSION || "0.0.0";

function parts(version: string): number[] {
  // "1.4.2-beta.1" compares as 1.4.2: the minimum is always a release.
  const release = version.trim().split(/[-+]/)[0] ?? "";
  return release.split(".").map((part) => {
    const n = Number.parseInt(part, 10);
    return Number.isNaN(n) ? 0 : n;
  });
}

/** Negative if a < b, 0 if equal, positive if a > b ("1.10.0" > "1.9.3"). */
export function compareVersions(a: string, b: string): number {
  const left = parts(a);
  const right = parts(b);
  for (let i = 0; i < Math.max(left.length, right.length); i += 1) {
    const diff = (left[i] ?? 0) - (right[i] ?? 0);
    if (diff !== 0) return diff;
  }
  return 0;
}

export function isBelowMinimum(current: string, minimum: string): boolean {
  return compareVersions(current, minimum) < 0;
}
