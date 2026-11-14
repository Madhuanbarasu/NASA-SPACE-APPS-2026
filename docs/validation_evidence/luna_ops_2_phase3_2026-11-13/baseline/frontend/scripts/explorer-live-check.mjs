#!/usr/bin/env node
// Phase 5 prompt 2: live check of the South Pole explorer (globe -> site -> local terrain -> analysis) in a real browser
// (Chrome/Edge headless through the DevTools Protocol, Node's built-in WebSocket; no packages). Needs the app running.
//
//   node scripts/explorer-live-check.mjs --base http://127.0.0.1:8765 --out <dir>
//
// Results in <out>/explorer-check.json, screenshots in <out>/screenshots/; exit 1 if any check fails. Checks:
//  transfer     a globe pick fills the sidebar coordinates through the shared conversion; the explorer, the globe marker
//               and the sidebar show the same site; typed coordinates move the globe selection (one source of truth)
//  edges        South Pole and North Pole picks; longitudes typed west-negative, 360, 359.9999996 and the 0/360 seam
//  coverage     covered points list the registered levels from GET /api/coverage; an unsupported point shows the
//               backend's reason and disables local terrain and analysis
//  terrain      "Inspect local terrain" loads GET /api/terrain for the selected site: product, grid, heights, data share
//  analysis     "Analyse this site" runs the existing analysis (Site01, cached dates) and opens the result with the same
//               coordinates, the map and the local 3D terrain; "Back to the Moon explorer" returns with the site kept
//  responsive   the explorer stacks under the pane at 390 px without sideways scrolling
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const BASE = arg("--base", "http://127.0.0.1:8765");
const OUT = path.resolve(arg("--out", "explorer-check"));
const BROWSERS = [arg("--browser", ""), "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", "/usr/bin/google-chrome", "/usr/bin/chromium"].filter(Boolean);
const BROWSER = BROWSERS.find((b) => fs.existsSync(b));
if (!BROWSER) { console.error("No Chrome/Edge found; pass --browser"); process.exit(2); }
fs.mkdirSync(path.join(OUT, "screenshots"), { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const PORT = 9700 + Math.floor(Math.random() * 200);
const profile = fs.mkdtempSync(path.join(os.tmpdir(), "luna-globe-"));
const NO_WEBGL = process.argv.includes("--no-webgl");
const proc = spawn(BROWSER, [`--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`, "--headless=new", "--no-first-run",
  "--no-default-browser-check", "--disable-extensions", "--hide-scrollbars", "--force-color-profile=srgb",
  ...(NO_WEBGL ? ["--disable-webgl", "--disable-3d-apis"] : ["--enable-unsafe-swiftshader"]), "--window-size=1440,900", "about:blank"], { stdio: "ignore" });
let ws = null;
for (let i = 0; i < 100 && !ws; i++) {
  try { const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
    const page = list.find((t) => t.type === "page"); if (page) ws = new WebSocket(page.webSocketDebuggerUrl); } catch { /* not up */ }
  if (!ws) await sleep(200);
}
await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
let nextId = 1;
const pending = new Map();
const consoleMsgs = [], requests = [];
ws.onmessage = (m) => {
  const msg = JSON.parse(m.data);
  if (msg.id && pending.has(msg.id)) { const { res, rej } = pending.get(msg.id); pending.delete(msg.id); msg.error ? rej(new Error(msg.error.message)) : res(msg.result); return; }
  if (msg.method === "Runtime.consoleAPICalled") consoleMsgs.push({ type: msg.params.type, text: msg.params.args.map((a) => a.value ?? a.description ?? "").join(" ") });
  if (msg.method === "Runtime.exceptionThrown") consoleMsgs.push({ type: "exception", text: msg.params.exceptionDetails?.exception?.description ?? msg.params.exceptionDetails?.text });
  if (msg.method === "Log.entryAdded") consoleMsgs.push({ type: `log-${msg.params.entry.level}`, text: msg.params.entry.text });
  if (msg.method === "Network.requestWillBeSent") requests.push(msg.params.request.url);
};
const send = (method, params = {}) => new Promise((res, rej) => { const id = nextId++; pending.set(id, { res, rej }); ws.send(JSON.stringify({ id, method, params })); });
const evaluate = async (expr) => {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error("page error: " + (r.exceptionDetails.exception?.description || r.exceptionDetails.text));
  return r.result.value;
};
const waitFor = async (cond, timeout = 30000, what = cond) => {
  const t0 = Date.now();
  while (Date.now() - t0 < timeout) { if (await evaluate(`!!(${cond})`)) return true; await sleep(200); }
  throw new Error("timeout waiting for " + what);
};
const KEYS = { ArrowRight: 39, ArrowLeft: 37, ArrowUp: 38, ArrowDown: 40, Enter: 13, Home: 36, "+": 187, "-": 189, Tab: 9 };
async function press(key, shift = false) {
  const base = { key, code: key, windowsVirtualKeyCode: KEYS[key], nativeVirtualKeyCode: KEYS[key], modifiers: shift ? 8 : 0 };
  await send("Input.dispatchKeyEvent", { type: "rawKeyDown", ...base });
  if (key === "Enter" || key === "+" || key === "-") await send("Input.dispatchKeyEvent", { type: "char", ...base, text: key === "Enter" ? "\r" : key });
  await send("Input.dispatchKeyEvent", { type: "keyUp", ...base });
  await sleep(250);
}
const shot = async (name, clip) => { const { data } = await send("Page.captureScreenshot", { format: "png", ...(clip ? { clip: { ...clip, scale: 1 } } : {}) });
  fs.writeFileSync(path.join(OUT, "screenshots", `${name}.png`), Buffer.from(data, "base64")); return data; };
const stageRect = () => evaluate(`(() => { const r = document.querySelector('.globe-stage').getBoundingClientRect(); return { x: r.left, y: r.top, width: r.width, height: r.height }; })()`);
// pixel statistics of a screenshot, computed in the page (no image library needed)
const pixelStats = (b64, box) => evaluate(`(async () => { const img = new Image(); img.src = 'data:image/png;base64,${b64}'; await img.decode();
  const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; const g = c.getContext('2d'); g.drawImage(img, 0, 0);
  const d = g.getImageData(0, 0, c.width, c.height).data; let lit = 0, sum = 0, n = 0, h = 0;
  const b = ${JSON.stringify(box ?? null)};
  for (let y = 0; y < c.height; y++) for (let x = 0; x < c.width; x++) { const i = 4 * (y * c.width + x); const l = 0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2];
    if (l > 40) lit++; if (b && x >= b[0] && x < b[2] && y >= b[1] && y < b[3]) { sum += l; n++; } h = (h * 31 + d[i] + d[i + 1] * 7 + d[i + 2] * 13) | 0; }
  return { litFraction: lit / (c.width * c.height), boxMean: n ? sum / n : null, hash: h, w: c.width, h: c.height }; })()`);
const centreText = () => evaluate(`document.querySelector('.globe-readout-mini span')?.textContent || ''`);
const selectedText = () => evaluate(`document.querySelector('.globe-selected strong')?.textContent || ''`);
const parseLoc = (t) => { const m = /([\d.]+)° ([NS]),\s*([\d.]+)° E/.exec(t); return m ? { lat: (m[2] === "S" ? -1 : 1) * Number(m[1]), lon: Number(m[3]) } : null; };
const clickBtn = (sel, text) => evaluate(`(() => { const b = [...document.querySelectorAll(${JSON.stringify(sel)})].find(e => e.textContent.trim() === ${JSON.stringify(text)} || e.getAttribute('aria-label') === ${JSON.stringify(text)}); if (!b) return false; b.click(); return true; })()`);
async function mouseClick(x, y) {
  await send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y });
  await send("Input.dispatchMouseEvent", { type: "mousePressed", x, y, button: "left", clickCount: 1, buttons: 1 });
  await send("Input.dispatchMouseEvent", { type: "mouseReleased", x, y, button: "left", clickCount: 1, buttons: 0 });
  await sleep(300);
}
const lonDiff = (a, b) => ((a - b + 540) % 360) - 180;

const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
const fields = () => evaluate(`({ lat: document.querySelector('#lat').value, lon: document.querySelector('#lon').value })`);
const explorerCoords = () => evaluate(`document.querySelector('.explorer-coords strong')?.textContent || ''`);
const coverageText = () => evaluate(`document.querySelector('.explorer .hint[aria-live]')?.textContent || ''`);
const waitCoverage = async () => {
  await sleep(450);
  await waitFor(`(() => { const t = document.querySelector('.explorer .hint[aria-live]')?.textContent || ''; return t && !/^Checking/.test(t); })()`, 30000, "coverage");
  return coverageText();
};
const btnState = (text) => evaluate(`(() => { const b = [...document.querySelectorAll('button')].find(e => e.textContent.trim() === ${JSON.stringify(text)}); return b ? (b.disabled ? 'disabled' : 'enabled') : 'missing'; })()`);
const openGlobe = async () => {
  await clickBtn(".view-switch button", "3D Moon globe");
  await waitFor("document.querySelector('.globe-host canvas') && !document.querySelector('.globe-message')", 30000, "globe");
  await evaluate("document.querySelector('.globe-stage').scrollIntoView({ block: 'center' }); true"); await sleep(600);
};

const checks = [];
const check = (name, ok, detail) => { checks.push({ name, ok: !!ok, detail }); console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail !== undefined ? "  " + JSON.stringify(detail) : ""}`); };
const report = { base: BASE, browser: BROWSER, started: new Date().toISOString() };
await send("Runtime.enable"); await send("Log.enable"); await send("Network.enable"); await send("Page.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url: BASE + "/" });
await waitFor("document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')", 60000, "status");
await sleep(1500);
check("explorer: no site selected at start; local terrain view disabled", /No site selected/.test(await evaluate("document.querySelector('.explorer').textContent"))
  && await btnState("Local terrain") === "disabled", await btnState("Local terrain"));
await shot("01-welcome-explorer");

// globe -> South Pole -> select centre -> sidebar, explorer, coverage
await openGlobe();
await clickBtn(".segmented-mini button", "South Pole"); await sleep(1100);
await clickBtn(".globe-nav button", "Select the location under the centre crosshair"); await sleep(300);
const f1 = await fields();
const cov1 = await waitCoverage();
check("transfer: globe pick at the South Pole viewpoint fills the sidebar (-89.9, 0) through siteCoords", f1.lat === "-89.9" && f1.lon === "0", f1);
check("transfer: the explorer shows the same site", await explorerCoords() === "89.900° S, 0.000° E", await explorerCoords());
check("coverage: the polar point is covered by the registered levels from the API", /covers this point: .*20m.*80m.*240m/.test(cov1), cov1);
check("coverage: local terrain and analysis enabled for a covered point", await btnState("Inspect local terrain") === "enabled" && await btnState("Analyse this site") === "enabled"
  && await btnState("Local terrain") === "enabled");
await shot("02-globe-south-pole-pick", await stageRect());
await shot("03-explorer-covered");

// a click on the globe canvas (not the centre button): the same transfer, east longitude 0-360 on the west side
const st = await stageRect();
await clickBtn(".segmented-mini button", "Nearside"); await sleep(1100);
await mouseClick(st.x + st.width / 2 - 100, st.y + st.height / 2 + 60);
await sleep(300);
const f2 = await fields(); const c2 = await explorerCoords();
const lon2 = Number(f2.lon), lat2 = Number(f2.lat);
check("edges: a click west of the prime meridian gives an east longitude in (180, 360) and a southern latitude, consistent in sidebar and explorer",
  lon2 > 300 && lon2 < 360 && lat2 < 0 && c2 === `${Math.abs(lat2).toFixed(3)}° S, ${lon2.toFixed(3)}° E`, { fields: f2, explorer: c2 });
const cov2 = await waitCoverage();
check("coverage: a nearside point north of 60 S is refused with the backend's reason", /Not covered by the registered terrain: The registered LOLA products cover 60-90 S only/.test(cov2), cov2);
check("coverage: local terrain and analysis disabled for an unsupported point", await btnState("Inspect local terrain") === "disabled" && await btnState("Analyse this site") === "disabled"
  && await btnState("Local terrain") === "disabled");
await shot("04-explorer-unsupported");

// North Pole edge
await clickBtn(".segmented-mini button", "North Pole"); await sleep(1100);
await clickBtn(".globe-nav button", "Select the location under the centre crosshair"); await sleep(300);
const f3 = await fields(); const cov3 = await waitCoverage();
check("edges: North Pole pick (89.9 N) transfers and is refused with the backend's reason", f3.lat === "89.9" && /60-90 S only/.test(cov3), { fields: f3, coverage: cov3 });
await shot("05-globe-north-pole-unsupported", await stageRect());

// typed coordinates -> globe (one source of truth), longitude edges
const typed = async (lat, lon) => { await setValue("#lat", lat); await setValue("#lon", lon); await sleep(200); return explorerCoords(); };
check("edges: west-negative longitude -137.489553 shows as 222.510 E", await typed("-89.463163", "-137.489553") === "89.463° S, 222.510° E", await explorerCoords());
check("edges: longitude 360 shows as 0.000 E", await typed("-85", "360") === "85.000° S, 0.000° E", await explorerCoords());
check("edges: longitude 359.9999996 shows as 0.000 E (never 360.000)", await typed("-85", "359.9999996") === "85.000° S, 0.000° E", await explorerCoords());
check("edges: latitude -90 (the pole) is accepted", await typed("-90", "45") === "90.000° S, 45.000° E", await explorerCoords());
const covPole = await waitCoverage();
check("coverage: the exact South Pole is covered", /covers this point/.test(covPole), covPole);
check("edges: invalid latitude -91 shows no site", (await typed("-91", "0")) === "" && /No site selected/.test(await evaluate("document.querySelector('.explorer').textContent")));

// Site01 typed -> globe centre on selection agrees
await typed("-89.463163", "222.510447");
const cov4 = await waitCoverage();
check("coverage: Site01 is covered including the 5 m site product", /covers this point: 5m/.test(cov4) && /Finest: 5m, PGDA 78/.test(await evaluate("document.querySelector('.explorer').textContent")), cov4);
await clickBtn(".globe-nav button", "Centre the view on the selected site"); await sleep(1200);
const cc = await evaluate(`document.querySelector('.globe-readout-mini span')?.textContent || ''`);
check("transfer: typed Site01 -> 'Centre on selection' centres the globe on the same site", cc === "Centre 89.463° S, 222.510° E", cc);
await shot("06-globe-site01-centred", await stageRect());

// local terrain for Site01
await clickBtn(".explorer button", "Inspect local terrain");
await waitFor("document.querySelector('.terrain-preview .three-host canvas') && document.querySelector('.terrain-stats ul')", 60000, "terrain preview");
await sleep(1200);
await evaluate("document.querySelector('.terrain-preview').scrollIntoView({ block: 'center' }); true"); await sleep(500);
const stats = await evaluate("[...document.querySelectorAll('.terrain-stats li')].map(l => l.textContent)");
const heading = await evaluate("document.querySelector('.explore-grid .pane-head h3').textContent");
check("terrain: local terrain opens for the selected site (8 km window: finest product covering the whole window) and explains the coarser window", heading === "Local terrain at 89.463° S, 222.510° E" && /^20m product: PGDA 90/.test(stats[0]) && /covered at 5m/.test(await evaluate("document.querySelector('.terrain-stats').textContent"))
  && /160 × 160 display grid, 101 m cells, 8 km radius/.test(stats[1]) && /Heights -?\d+ to -?\d+ m/.test(stats[2]) && /% of the window has data/.test(stats[4]), { heading, stats });
check("terrain: no error or no-data message over the 3D view", await evaluate("!document.querySelector('.terrain-preview-stage .pane-empty')"));
await evaluate("(() => { const s = document.querySelector('select[aria-label=\"Local terrain window radius\"]'); const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set; set.call(s, '4'); s.dispatchEvent(new Event('change', { bubbles: true })); return true; })()");
await sleep(800); await waitFor("/^5m product/.test(document.querySelector('.terrain-stats li')?.textContent || '')", 60000, "5m window");
check("terrain: a 4 km window shows the registered 5 m site product", /^5m product: PGDA 78/.test(await evaluate("document.querySelector('.terrain-stats li').textContent")));
await shot("07-local-terrain-site01");

// local terrain for a 240 m-only point (60-80 S)
await typed("-70", "100");
const cov5 = await waitCoverage();
check("coverage: a point at 70 S, 100 E is covered by the 240 m product only", /covers this point: 240m\./.test(cov5), cov5);
await sleep(1500);
await waitFor("document.querySelector('.terrain-stats ul') || document.querySelector('.terrain-preview-stage .pane-empty')", 60000, "terrain 240m");
await sleep(1500);
const stats240 = await evaluate("[...document.querySelectorAll('.terrain-stats li')].map(l => l.textContent)");
check("terrain: the local terrain switches to the 240 m product for that point", /^240m product: PGDA 90/.test(stats240[0] || ""), stats240);
await shot("08-local-terrain-70S-100E-240m");

// analysis for Site01 (dates already analysed by the audits: cached), then back
await typed("-89.463163", "222.510447"); await waitCoverage();
await setValue("#start", "2026-11-14T00:00"); await setValue("#end", "2026-11-21T00:00"); await sleep(300);
await clickBtn(".explorer button", "Analyse this site");
await waitFor("document.querySelector('.site-title')", 900000, "analysis result");
await sleep(2500);
const rc = await evaluate("document.querySelector('.site-coords').textContent");
check("analysis: the explorer's 'Analyse this site' opens the result for the same coordinates", /-89\.46316°, 222\.51045° E/.test(rc), rc);
check("analysis: result view has the map, the local 3D terrain (Terrain3D) and the validation labels",
  await evaluate("!!document.querySelector('.map-host') && !!document.querySelector('.three-host canvas') && document.querySelectorAll('.label-row .chip').length >= 5"));
report.resultLabels = await evaluate("[...document.querySelectorAll('.label-row .chip')].map(c => c.textContent)");
await shot("09-analysis-result");
await clickBtn("button", "Back to the Moon explorer"); await sleep(800);
check("analysis: 'Back to the Moon explorer' returns with the site kept in the sidebar and the explorer",
  !await evaluate("!!document.querySelector('.site-title')") && await explorerCoords() === "89.463° S, 222.510° E" && (await fields()).lat === "-89.463163", await explorerCoords());

// responsive
await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
await sleep(1200);
const mob = await evaluate(`(() => { const p = document.querySelector('.explore-grid > .pane').getBoundingClientRect(), e = document.querySelector('.explorer').getBoundingClientRect();
  return { scrollW: document.documentElement.scrollWidth, clientW: document.documentElement.clientWidth, stacked: e.top >= p.bottom - 1 }; })()`);
await evaluate("document.querySelector('.explorer').scrollIntoView({ block: 'center' }); true"); await sleep(400);
await shot("10-mobile-390-explorer");
check("responsive: at 390 px the explorer stacks under the pane without sideways scrolling", mob.scrollW <= mob.clientW && mob.stacked, mob);
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });

const errors = consoleMsgs.filter((m) => m.type === "exception" || m.type === "error" || (m.type === "log-error" && !/status of 422/.test(m.text)));
check("no page exceptions or console errors (422 answers for refused coordinates are expected API replies)", errors.length === 0, errors.slice(0, 5));
report.checks = checks; report.console = consoleMsgs; report.finished = new Date().toISOString();
fs.writeFileSync(path.join(OUT, "explorer-check.json"), JSON.stringify(report, null, 1));
const failed = checks.filter((c) => !c.ok).length;
console.log(`explorer-live-check: ${checks.length - failed}/${checks.length} checks passed`);
ws.close(); proc.kill();
try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* browser may still hold files */ }
process.exit(failed ? 1 : 0);
