// Per-area first-load budget (10-screens-shared.md: under 200 KB of gzipped
// JavaScript per app at first load). Run after `npm run build`.
// First load of an area = the entry chunk + that area's chunk.
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { gzipSync } from "node:zlib";

const BUDGET = 200 * 1024;
const dir = join(import.meta.dirname, "..", "dist", "assets");
const files = readdirSync(dir).filter((name) => name.endsWith(".js"));
const size = (name) => gzipSync(readFileSync(join(dir, name))).length;

const entry = files.find((name) => /^index-.*\.js$/.test(name));
if (!entry) throw new Error("No entry chunk (index-*.js) in dist/assets. Run npm run build.");
const entrySize = size(entry);

let failed = false;
for (const area of ["Staff", "Console", "Rider", "Customer", "Public"]) {
  const chunk = files.find((name) => name.startsWith(`${area}Area-`));
  if (!chunk) throw new Error(`No chunk for the ${area} area.`);
  const total = entrySize + size(chunk);
  const ok = total <= BUDGET;
  failed ||= !ok;
  console.log(`${ok ? "ok  " : "OVER"} ${area.padEnd(9)} ${(total / 1024).toFixed(1)} KB gzipped`);
}
if (failed) {
  console.error(`An area is over the ${BUDGET / 1024} KB first-load budget.`);
  process.exit(1);
}
