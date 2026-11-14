#!/usr/bin/env node
// 3D Moon globe geometry check: src/lib/moonGeo.ts against three.js itself (no browser, no new packages).
//
//   node scripts/check-moon-geo.mjs            exit 1 on any failure
//
// Node 22.18+/24 strips TypeScript types natively, so the module under test is imported as written.
// 1. latitude/longitude -> unit vector -> latitude/longitude round trip over the whole sphere;
// 2. every vertex of a three.js SphereGeometry: its texture coordinate equals textureUV(unitToLatLon(vertex)),
//    i.e. the equirectangular image, the mesh and the coordinate readout use one and the same mapping;
// 3. exact ray-sphere picking returns the aimed-at location, including a South Pole site;
// 4. conventions: +y north pole, (0, 0) on +x, 90 deg east on -z, east longitudes in [0, 360).
import * as THREE from "three";
import { angularDistance, latLonToUnit, lon180, lon360, parseSite, raySphere, siteCoords, textureUV, unitToLatLon } from "../src/lib/moonGeo.ts";

const failures = [];
const near = (a, b, tol) => Math.abs(a - b) <= tol;
const expect = (ok, msg) => { if (!ok) failures.push(msg); };
let checks = 0;

// 1. round trip
let worstRT = 0;
for (let lat = -89.5; lat <= 89.5; lat += 0.5) {
  for (let lon = 0; lon < 360; lon += 0.75) {
    const [x, y, z] = latLonToUnit(lat, lon);
    const p = unitToLatLon(x, y, z);
    const err = angularDistance({ lat, lon }, p);
    worstRT = Math.max(worstRT, Math.abs(p.lat - lat), Math.abs(lon180(p.lon - lon)));
    checks++;
    expect(near(Math.hypot(x, y, z), 1, 1e-12) && err < 1e-9, `round trip (${lat}, ${lon}) -> (${p.lat}, ${p.lon})`);
  }
}
expect(unitToLatLon(0, -1, 0).lat === -90 && unitToLatLon(0, 1, 0).lat === 90, "poles map to +-90");
checks++;

// 2. three.js SphereGeometry UVs
const geo = new THREE.SphereGeometry(1, 360, 180);
const pos = geo.attributes.position, uv = geo.attributes.uv;
let worstUV = 0, nUV = 0;
for (let i = 0; i < pos.count; i++) {
  const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
  if (Math.abs(y) > 1 - 1e-9) continue;                       // pole vertices: longitude undefined
  const { lat, lon } = unitToLatLon(x, y, z);
  const [u, v] = textureUV(lat, lon);
  let du = Math.abs(u - uv.getX(i));
  du = Math.min(du, Math.abs(du - 1));                        // the 0/1 seam is the same meridian (180 deg)
  const dv = Math.abs(v - uv.getY(i));
  worstUV = Math.max(worstUV, du, dv);
  nUV++;
}
checks += nUV;
expect(worstUV < 1e-6, `SphereGeometry UV mismatch ${worstUV}`);

// 3. ray picking from outside the globe
const sites = [{ lat: -89.463163, lon: 222.510447 }, { lat: 0, lon: 0 }, { lat: 45, lon: 90 }, { lat: -30, lon: 300 }, { lat: 89.99, lon: 10 }];
let worstPick = 0;
for (const s of sites) {
  const p = latLonToUnit(s.lat, s.lon);
  const cam = [p[0] * 3.4 + 0.3, p[1] * 3.4 - 0.2, p[2] * 3.4 + 0.1];
  const hit = raySphere(cam, [p[0] - cam[0], p[1] - cam[1], p[2] - cam[2]]);
  const got = hit ? unitToLatLon(...hit) : null;
  const d = got ? angularDistance(s, got) : 999;
  worstPick = Math.max(worstPick, d);
  checks++;
  expect(d < 1e-9, `pick ${JSON.stringify(s)} -> ${JSON.stringify(got)}`);
}
expect(raySphere([0, 0, 3], [0, 1, 0]) === null, "ray that misses returns null");
checks++;

// 4. conventions
const c = (lat, lon, want) => { const v = latLonToUnit(lat, lon); checks++; expect(v.every((a, k) => near(a, want[k], 1e-12)), `latLonToUnit(${lat}, ${lon}) = ${v}`); };
c(0, 0, [1, 0, 0]); c(0, 90, [0, 0, -1]); c(0, 180, [-1, 0, 0]); c(90, 0, [0, 1, 0]); c(-90, 0, [0, -1, 0]);
checks += 2;
expect(lon360(-10) === 350 && lon360(360) === 0 && lon180(222.5) === -137.5, "longitude normalisation");
expect(textureUV(0, 0)[0] === 0.5 && textureUV(90, 0)[1] === 1 && textureUV(-90, 0)[1] === 0, "texture centred on 0 deg, north at the top");

// 5. site-coordinate transfer (globe/map pick -> store) and typed input (store -> globe): poles and longitude edges
const eqLoc = (got, want) => got && want && got.lat === want.lat && got.lon === want.lon;
const sc = [
  [[-89.4631634, 222.5104467], { lat: -89.463163, lon: 222.510447 }],      // Site01 at 1e-6 deg
  [[-90, 123.4], { lat: -90, lon: 123.4 }], [[90, 0], { lat: 90, lon: 0 }], // poles keep their latitude
  [[-90.0000001, 0], { lat: -90, lon: 0 }],                                // clamped
  [[-85, 359.9999996], { lat: -85, lon: 0 }],                              // rounds to 360 -> 0, never 360
  [[-85, -0.0000001], { lat: -85, lon: 0 }],                               // tiny negative -> 0, not -0 or 360
  [[-85, -137.4895533], { lat: -85, lon: 222.510447 }],                    // west -> east 0-360
  [[-85, 720.25], { lat: -85, lon: 0.25 }], [[0, 180], { lat: 0, lon: 180 }],
];
for (const [[la, lo], want] of sc) { checks++; const got = siteCoords(la, lo); expect(eqLoc(got, want) && !Object.is(got.lon, -0), `siteCoords(${la}, ${lo}) = ${JSON.stringify(got)}`); }
const ps = [
  [["-89.463163", "222.510447"], { lat: -89.463163, lon: 222.510447 }], [["-89.5", "-137.5"], { lat: -89.5, lon: 222.5 }],
  [["-90", "360"], { lat: -90, lon: 0 }], [["90", "-360"], { lat: 90, lon: 0 }], [[" -60 ", "0"], { lat: -60, lon: 0 }],
  [["", "10"], null], [["-91", "0"], null], [["-89", "361"], null], [["abc", "0"], null], [["-89", "NaN"], null],
];
for (const [[la, lo], want] of ps) { checks++; const got = parseSite(la, lo); expect(want === null ? got === null : eqLoc(got, want), `parseSite(${la}, ${lo}) = ${JSON.stringify(got)}`); }
// a pick transferred to the store and read back lands within 1e-6 deg of the picked point (round trip through text)
for (let k = 0; k < 2000; k++) {
  const la = -90 + 180 * ((k * 0.6180339887) % 1), lo = 720 * ((k * 0.7548776662) % 1) - 360;
  const c = siteCoords(la, lo); const back = parseSite(String(c.lat), String(c.lon));
  checks++;
  expect(back && angularDistance({ lat: la, lon: lon360(lo) }, back) < 2e-6, `transfer round trip (${la}, ${lo}) -> ${JSON.stringify(back)}`);
}

const summary = { checks, roundTripWorstDeg: worstRT, sphereGeometryVertices: nUV, uvWorst: worstUV, pickWorstDeg: worstPick, failures };
console.log(JSON.stringify(summary, null, 1));
if (failures.length) { console.error(`check-moon-geo: ${failures.length} failure(s)`); process.exit(1); }
console.log(`check-moon-geo: ${checks} checks passed`);
