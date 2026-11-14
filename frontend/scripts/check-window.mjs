#!/usr/bin/env node
// Analysis window and panel-azimuth checks (E2E-07 correction): src/lib/timeWindow.ts and the azimuth normalisation
// (lib/moonGeo lon360, used for panel_az_deg). Node 22.18+/24 strips TypeScript types natively; no new packages.
//
//   node scripts/check-window.mjs            exit 1 on any failure
import { windowValid } from "../src/lib/timeWindow.ts";
import { lon360 } from "../src/lib/moonGeo.ts";

const cases = [
  // [start, end, expected, name]
  ["2026-11-13T00:00:00Z", "2026-12-13T00:00:00Z", true, "valid 30-day window"],
  ["2026-11-13T00:00:00Z", "2026-11-13T00:01:00Z", true, "one minute (the input's resolution)"],
  ["2026-11-13T00:00:00Z", "2026-11-13T00:00:01Z", true, "one second after the start"],
  ["2026-11-13T00:00:00Z", "2026-11-13T00:00:00Z", false, "equal start and end"],
  ["2026-12-13T00:00:00Z", "2026-11-13T00:00:00Z", false, "reversed (end before start)"],
  ["2026-11-13T00:01:00Z", "2026-11-13T00:00:00Z", false, "reversed by one minute"],
  ["2028-02-28T23:00:00Z", "2028-02-29T01:00:00Z", true, "across a leap day"],
  ["2026-12-31T23:59:00Z", "2027-01-01T00:00:00Z", true, "across the year boundary"],
  ["", "2026-11-13T00:00:00Z", false, "missing start"],
  ["2026-11-13T00:00:00Z", "", false, "missing end"],
  ["not a date", "2026-11-13T00:00:00Z", false, "invalid start"],
  [null, undefined, false, "null / undefined"],
];
let bad = 0;
for (const [a, b, exp, name] of cases) {
  const got = windowValid(a, b);
  if (got !== exp) bad++;
  console.log(`${got === exp ? "PASS" : "FAIL"}  window ${name}: ${JSON.stringify(a)} -> ${JSON.stringify(b)} = ${got}`);
}
// UTC whatever the time zone: the stored values end in "Z"; the same instants written with an offset compare equally
const tz = windowValid("2026-11-13T05:30:00+05:30", "2026-11-13T00:00:01Z");
if (tz !== true) bad++;
console.log(`${tz ? "PASS" : "FAIL"}  window with an explicit offset compares by instant (00:00:00Z -> 00:00:01Z) = ${tz}`);

const az = [[400, 40], [360, 0], [720, 0], [-20, 340], [0, 0], [359.5, 359.5], [40, 40]];
for (const [v, exp] of az) {
  const got = lon360(v);
  const ok = Math.abs(got - exp) < 1e-12;
  if (!ok) bad++;
  console.log(`${ok ? "PASS" : "FAIL"}  panel azimuth ${v} deg -> ${got} deg (modulo 360)`);
}
const total = cases.length + 1 + az.length;
console.log(`check-window: ${total - bad}/${total} passed`);
process.exit(bad ? 1 : 0);
