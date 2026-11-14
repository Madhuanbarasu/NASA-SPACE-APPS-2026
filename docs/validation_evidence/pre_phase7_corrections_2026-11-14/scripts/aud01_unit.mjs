// AUD-01 focused unit check: the sidebar's field flags and the store's coverage guard, written exactly as in
// Sidebar.tsx and store.tsx, applied to parseSite from frontend/src/lib/moonGeo.ts (Node strips the TypeScript types).
// Usage: node aud01_unit.mjs   (exit code 1 on any mismatch)
import { parseSite } from "../../../../frontend/src/lib/moonGeo.ts";

const flags = (lat, lon) => ({
  coordsGiven: parseSite(lat, lon) !== null,                     // Sidebar.tsx coordsGiven, store.tsx coverage guard
  latBad: lat.trim() !== "" && parseSite(lat, "0") === null,      // Sidebar.tsx latBad
  lonBad: lon.trim() !== "" && parseSite("0", lon) === null,      // Sidebar.tsx lonBad
});
// [lat, lon, expected coordsGiven (a coverage request is sent), latBad, lonBad]
const CASES = [
  ["-89.463163", "222.510447", true, false, false],
  ["-95", "222.510447", false, true, false],
  ["95", "222.510447", false, true, false],
  ["-90.0001", "0", false, true, false],
  ["-90", "0", true, false, false],
  ["90", "0", true, false, false],
  ["-89.5", "400", false, false, true],
  ["-89.5", "-361", false, false, true],
  ["-85", "360", true, false, false],
  ["-85", "-360", true, false, false],
  ["-85", "-10", true, false, false],
  ["abc", "222.5", false, true, false],
  ["-89.5", "1e3", false, false, true],
  ["-95", "400", false, true, true],
  ["", "222.5", false, false, false],
  ["-89.5", "", false, false, false],
  ["  -89.5 ", " 222.5", true, false, false],
  ["Infinity", "0", false, true, false],
  ["NaN", "0", false, true, false],
];
let bad = 0;
for (const [lat, lon, cg, lb, ob] of CASES) {
  const f = flags(lat, lon);
  const ok = f.coordsGiven === cg && f.latBad === lb && f.lonBad === ob;
  if (!ok) bad++;
  console.log(`${ok ? "PASS" : "FAIL"}  lat=${JSON.stringify(lat)} lon=${JSON.stringify(lon)} -> ${JSON.stringify(f)}`);
}
console.log(`aud01-unit: ${CASES.length - bad}/${CASES.length} passed`);
process.exit(bad ? 1 : 0);
