// Numerical check of the map scale bar: ground metres per pixel from the inverse projection and great-circle distance
// (what MapView does) against the analytic point scale of the south polar stereographic projection, k = 1 / cos^2(chi/2)
// (chi = angular distance from the pole; lat_ts = -90, k0 = 1): ground m/px = resolution / k.
import proj4 from "proj4";
import ts from "typescript";
import fs from "node:fs";
const src = ts.transpileModule(fs.readFileSync("src/lib/mapScale.ts", "utf8"), { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { greatCircleM, niceScale, MOON_RADIUS_M } = await import("data:text/javascript;base64," + Buffer.from(src).toString("base64"));
proj4.defs("SPS", "+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +k=1 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs");
proj4.defs("GEO", "+proj=longlat +R=1737400 +no_defs");
let worst = 0;
for (const [lat, lon, res] of [[-89.9, 0, 50], [-89.463163, 222.510447, 5], [-85, 45, 200], [-75, 300, 1000], [-62, 120, 2000], [-90, 0, 2000]]) {
  const [cx, cy] = proj4("GEO", "SPS", [lon > 180 ? lon - 360 : lon, lat]);
  const a = proj4("SPS", "GEO", [cx - 50 * res, cy]), b = proj4("SPS", "GEO", [cx + 50 * res, cy]);
  const mpp = greatCircleM(a[1], a[0], b[1], b[0]) / 100;
  const chi = (90 + lat) * Math.PI / 180;
  const exact = res * Math.cos(chi / 2) ** 2;
  const err = Math.abs(mpp - exact) / exact;
  worst = Math.max(worst, err);
  console.log(`lat ${lat} res ${res}: numeric ${mpp.toFixed(4)} m/px, analytic ${exact.toFixed(4)} m/px, rel. diff ${err.toExponential(2)}; bar ${JSON.stringify(niceScale(mpp))}`);
}
console.log("radius", MOON_RADIUS_M, "worst relative difference", worst.toExponential(2), worst < 1e-3 ? "OK" : "FAIL");
process.exit(worst < 1e-3 ? 0 : 1);
