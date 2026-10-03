// Per-area first-load budget (10-screens-shared.md: under 200 KB of gzipped
// JavaScript per app at first load). Run after `npm run build`.
// First load of an area = the entry chunk, the area's chunk, and every chunk either
// of them imports statically (shared code such as the sign-in screens), counted once.
// The chunk graph comes from Vite's build manifest.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { gzipSync } from "node:zlib";

const BUDGET = 200 * 1024;
const dist = join(import.meta.dirname, "..", "dist");
const manifest = JSON.parse(readFileSync(join(dist, ".vite", "manifest.json"), "utf8"));
const size = (file) => gzipSync(readFileSync(join(dist, file))).length;

/** The JS files `key` loads before running: itself and its static imports, transitively. */
function closure(key, seen = new Set()) {
  const chunk = manifest[key];
  if (!chunk || seen.has(key)) return seen;
  seen.add(key);
  for (const imported of chunk.imports ?? []) closure(imported, seen);
  return seen;
}

const entryKey = Object.keys(manifest).find((key) => manifest[key].isEntry);
if (!entryKey) throw new Error("No entry in the build manifest. Run npm run build.");

const AREAS = {
  Staff: "src/apps/staff/StaffArea.tsx",
  Console: "src/apps/console/ConsoleArea.tsx",
  Rider: "src/apps/rider/RiderArea.tsx",
  Customer: "src/apps/customer/CustomerArea.tsx",
  Public: "src/apps/public/PublicArea.tsx",
  Invite: "src/apps/invite/InviteArea.tsx",
};

let failed = false;
for (const [area, source] of Object.entries(AREAS)) {
  if (!manifest[source]) throw new Error(`No chunk for the ${area} area (${source}).`);
  const keys = closure(source, closure(entryKey));
  const total = [...keys].reduce((sum, key) => sum + size(manifest[key].file), 0);
  const ok = total <= BUDGET;
  failed ||= !ok;
  console.log(`${ok ? "ok  " : "OVER"} ${area.padEnd(9)} ${(total / 1024).toFixed(1)} KB gzipped`);
}
if (failed) {
  console.error(`An area is over the ${BUDGET / 1024} KB first-load budget.`);
  process.exit(1);
}
