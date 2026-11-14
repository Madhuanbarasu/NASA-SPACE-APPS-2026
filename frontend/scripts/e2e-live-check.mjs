#!/usr/bin/env node
// Phase 5 final: end-to-end live check of the integrated interface in a real browser (Chrome/Edge headless through the
// DevTools Protocol, Node's built-in WebSocket; no packages). Needs the app running.
//
//   node scripts/e2e-live-check.mjs --base http://127.0.0.1:8765 --out <dir>
//
// Workflow: loading state of the lazy dashboard on a slow connection; globe pick at the South Pole viewpoint -> the same
// site in the sidebar, explorer and dashboard; local terrain preview; analysis for exactly those coordinates; leaving the
// result and returning to it at the same time step without refetching (dashboard and explorer); candidates -> 2 x 2
// comparison -> cell result -> dashboard; the session list restored after a reload for the same build and validation
// report, discarded for another build; a result missing on the server (real 404) reported in place; the status API
// unreachable; no sideways scrolling on any tab at 1440, 390 and 320 px; no console errors. Results in
// <out>/e2e-check.json, screenshots in <out>/screenshots/; exit 1 if any check fails.
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const BASE = arg("--base", "http://127.0.0.1:8765");
const OUT = path.resolve(arg("--out", "e2e-check"));
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

const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const proto = e instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
  const set = Object.getOwnPropertyDescriptor(proto, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event(e instanceof HTMLSelectElement ? 'change' : 'input', { bubbles: true })); return true; })()`);
const checks = [];
const check = (name, ok, detail) => { checks.push({ name, ok: !!ok, detail }); console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail !== undefined ? "  " + JSON.stringify(detail).slice(0, 400) : ""}`); };
const report = { base: BASE, browser: BROWSER, started: new Date().toISOString(), analyses: [] };
await send("Runtime.enable"); await send("Log.enable"); await send("Network.enable"); await send("Page.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const load = async () => { await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(1200); };
await load();
await evaluate("try { sessionStorage.clear(); } catch (e) {} true");
await load();

const text = (sel) => evaluate(`document.querySelector(${JSON.stringify(sel)})?.textContent || ''`);
const tab = async (name) => { await clickBtn("button.tab", name); await sleep(500); };
const SEL = "section[aria-labelledby=mission-selected]", CUR = "section[aria-labelledby=mission-current]", HIST = "section[aria-labelledby=mission-history]",
  CAND = "section[aria-labelledby=mission-candidates]", CMP = "section[aria-labelledby=mission-comparison]", STATUS = "section[aria-labelledby=mission-status]";
const toMission = async () => { await tab("Mission"); await waitFor("document.querySelector('.mission')", 30000, "mission"); await sleep(300); };
const fields = () => evaluate("({ lat: document.querySelector('#lat').value, lon: document.querySelector('#lon').value })");
const resultId = () => evaluate("(document.querySelector('a[href$=\"/result.json\"]')?.getAttribute('href') || '').split('/')[3]");
const btn = (sel, label) => evaluate(`(() => { const b = [...document.querySelectorAll(${JSON.stringify(sel + " button")})].find(e => e.textContent.trim() === ${JSON.stringify(label)} || e.getAttribute('aria-label') === ${JSON.stringify(label)} || e.textContent.trim().startsWith(${JSON.stringify(label)})); if (!b) return null; if (b.disabled) return 'disabled'; b.click(); return 'clicked'; })()`);
const waitCov = () => waitFor("(() => { const t = document.querySelector('.explorer .hint[aria-live]')?.textContent || ''; return t && !/^Checking/.test(t); })()", 30000, "coverage");
const fmt3 = (lat, lon) => `${Math.abs(lat).toFixed(3)}° ${lat >= 0 ? "N" : "S"}, ${(((lon % 360) + 360) % 360).toFixed(3)}° E`;
const errorsAllowed = /status of 404|status of 422|ERR_BLOCKED_BY_CLIENT/;

// ---- 1. loading state: the dashboard's lazy chunk on a slow connection shows its loading text, then the dashboard
await send("Network.emulateNetworkConditions", { offline: false, latency: 1500, downloadThroughput: 200000, uploadThroughput: 200000 });
await evaluate("[...document.querySelectorAll('button.tab')].find(b => b.textContent === 'Mission').click(); true");
let sawLoading = false;
for (let i = 0; i < 30 && !sawLoading; i++) { sawLoading = /Loading the mission overview/.test(await text("#view-panel")); if (!sawLoading) await sleep(50); }
await waitFor("document.querySelector('.mission')", 60000, "mission after slow load");
await send("Network.emulateNetworkConditions", { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
check("loading state: on a slow connection the Mission tab shows its loading text, then the dashboard", sawLoading);

// ---- 2. globe selection -> one site in every view
await tab("Site");
await clickBtn(".view-switch button", "3D Moon globe");
let sawGlobeLoading = false;
for (let i = 0; i < 20 && !sawGlobeLoading; i++) { sawGlobeLoading = /Loading the 3D globe|Loading/.test(await text(".explore-grid .pane")); if (!sawGlobeLoading) await sleep(30); }
await waitFor("document.querySelector('.globe-host canvas')", 60000, "globe"); await sleep(2500);
await clickBtn(".segmented-mini button", "South Pole"); await sleep(1100);
await clickBtn(".globe-nav button", "Select the location under the centre crosshair"); await sleep(300);
await waitCov();
const f1 = await fields();
const exp1 = await text(".explorer-coords");
await toMission();
const mis1 = await text(`${SEL} .explorer-coords`);
await tab("Site");
const globeSel = await evaluate("document.querySelector('.globe-selected strong, .globe-readout-mini span')?.textContent || ''");
report.globeLoadingTextSeen = sawGlobeLoading;
check("globe selection: the pick reaches the sidebar, the explorer and the dashboard as the same site", f1.lat === "-89.9" && f1.lon === "0" && exp1 === fmt3(-89.9, 0) && mis1 === exp1,
  { f1, exp1, mis1, globeSel });
await shot("01-globe-pick");

// ---- 3. local terrain, then analysis
await clickBtn(".explorer button", "Inspect local terrain");
await waitFor("document.querySelector('.terrain-stats') && document.querySelector('.terrain-preview .three-host canvas')", 90000, "terrain preview");
// wait for the registered-terrain request itself (its time depends on server load), then read the stats
await waitFor("!/Loading registered terrain/.test(document.querySelector('.terrain-stats')?.textContent || '')", 120000, "terrain data"); await sleep(1500);
const tStats = await text(".terrain-stats");
const ter = await evaluate("fetch('/api/terrain?lat=-89.9&lon=0').then(r => r.ok ? r.json() : null).catch(() => null)");
check("terrain: the local terrain preview opens for the picked site with the registered product", /20m/.test(tStats) && (!ter || tStats.includes(ter.product)), { tStats: tStats.slice(0, 200), product: ter?.product });
await shot("02-local-terrain");
await setValue("#start", "2026-11-14T00:00"); await setValue("#end", "2026-11-21T00:00"); await sleep(300);
await evaluate("document.querySelector('.explorer-run').click(); true");
await waitFor("document.querySelector('a[href$=\"/result.json\"]')", 900000, "analysis"); await sleep(2000);
const id1 = await resultId();
const r1 = await evaluate(`fetch('/api/results/${id1}').then(x => x.json())`);
report.analyses.push({ id: id1, lat: r1.site.lat, lon: r1.site.lon });
check("analysis: the result is for exactly the picked coordinates", Math.abs(r1.site.lat + 89.9) < 1e-9 && Math.abs(r1.site.lon) < 1e-9, r1.site);

// ---- 4. result preservation: leave for the explorer, come back at the same time step without refetching
await setValue(".scrubber input[type=range]", "57"); await sleep(400);
const curBefore = await evaluate("document.querySelector('.scrubber input[type=range]').value");
await clickBtn("button", "Back to the Moon explorer"); await sleep(800);
const returnBtn = await evaluate("[...document.querySelectorAll('.explorer button')].map(b => b.textContent).find(t => /^Return to the result/.test(t)) || null");
await toMission();
const parkedCard = await text(CUR);
const resReqs0 = requests.filter((u) => /\/api\/results\/[^/]+$/.test(u)).length;
await btn(".mission-nav", "Analysis"); await sleep(1200);
const back = await evaluate("({ id: (document.querySelector('a[href$=\"/result.json\"]')?.getAttribute('href') || '').split('/')[3], cursor: document.querySelector('.scrubber input[type=range]')?.value })");
const resReqs1 = requests.filter((u) => /\/api\/results\/[^/]+$/.test(u)).length;
check("result preservation: leaving the result keeps it (explorer offers to return; dashboard shows it as kept)", curBefore === "57" && /89\.900° S, 0\.000° E/.test(returnBtn ?? "") && /Kept while you explore/.test(parkedCard), { returnBtn, curBefore });
check("result preservation: Analysis returns to the same result at the same time step without fetching it again", back.id === id1 && back.cursor === "57" && resReqs1 === resReqs0, { back, resReqs0, resReqs1 });
await clickBtn("button", "Back to the Moon explorer"); await sleep(600);
await btn(".explorer", "Return to the result"); await sleep(1000);
check("result preservation: the explorer's Return button restores it too", (await resultId()) === id1 && (await evaluate("document.querySelector('.scrubber input[type=range]').value")) === "57");

// ---- 5. candidates and comparison: the picked site and Site01
await toMission();
await btn(CAND, "Add the selected site");
await tab("Site"); await clickBtn("button", "Back to the Moon explorer"); await sleep(400);
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447"); await sleep(400); await waitCov();
await toMission(); await btn(CAND, "Add the selected site"); await sleep(300);
await btn(CAND, "Compare candidates"); await sleep(500);
await clickBtn("button.quiet-button", "Add the panel's dates");
await clickBtn("button.quiet-button", "Add one synodic month later");
await evaluate("[...document.querySelectorAll('button.run-button')].find(b => /^Compare/.test(b.textContent)).click(); true");
await waitFor("document.querySelector('table.matrix')", 900000, "comparison"); await sleep(800);
const cells = await evaluate("document.querySelectorAll('table.matrix .cell-open').length");
await evaluate("document.querySelector('table.matrix .cell-open').click(); true");
await waitFor("document.querySelector('a[href$=\"/result.json\"]')", 60000, "cell result"); await sleep(1500);
const cellId = await resultId();
await toMission();
const cmpText = await text(CMP);
const histIds = await evaluate(`[...document.querySelectorAll('${HIST} tbody tr')].length`);
check("comparison: candidates compared (2 × 2), a cell opens its result, the dashboard reports the comparison and lists the results", cells === 4 && !!cellId && /2 sites × 2 windows compared/.test(cmpText) && histIds >= 2, { cells, cellId, histIds });
await shot("03-mission-after-comparison");

// ---- 6. session list kept on reload (same build and report), discarded for another build
const rowsBefore = await evaluate(`[...document.querySelectorAll('${HIST} tbody tr')].map(tr => tr.cells[0].textContent + '|' + tr.cells[1].textContent + '|' + tr.cells[2].textContent)`);
await load(); await toMission();
await waitFor(`document.querySelectorAll('${HIST} tbody tr').length > 0`, 15000, "restored list");
const rowsAfter = await evaluate(`[...document.querySelectorAll('${HIST} tbody tr')].map(tr => tr.cells[0].textContent + '|' + tr.cells[1].textContent + '|' + tr.cells[2].textContent)`);
check("persistence: after a reload the session list is restored unchanged (same build and validation report)", JSON.stringify(rowsAfter) === JSON.stringify(rowsBefore), { n: rowsAfter.length });
const stored = await evaluate("JSON.parse(sessionStorage.getItem('luna-ops.session-results.v1'))");
const st = await evaluate("fetch('/api/status').then(x => x.json())");
check("persistence: the saved list is tied to the backend code fingerprint and the validation report time", stored.code === st.code_fingerprint && stored.report === (st.validation?.run_utc ?? null), { code: stored.code.slice(0, 12), report: stored.report });
await btn(HIST, "Open"); await sleep(1500);
check("persistence: a restored entry opens its result from the server", !!(await resultId()));
await evaluate("(() => { const v = JSON.parse(sessionStorage.getItem('luna-ops.session-results.v1')); v.code = 'another-build'; sessionStorage.setItem('luna-ops.session-results.v1', JSON.stringify(v)); })(); true");
await load(); await toMission(); await sleep(800);
const afterMismatch = await evaluate(`({ rows: document.querySelectorAll('${HIST} tbody tr').length, stored: sessionStorage.getItem('luna-ops.session-results.v1') })`);
check("persistence: a list saved by another build is discarded, never shown (no stale figures or labels)", afterMismatch.rows === 0 && afterMismatch.stored === null, afterMismatch);

// ---- 7. error state: an entry whose result no longer exists on the server
const fake = { ...stored, items: [{ ...stored.items[0], id: "0000000000000000deadbeef" }] };
await evaluate(`sessionStorage.setItem('luna-ops.session-results.v1', ${JSON.stringify(JSON.stringify(fake))}); true`);
await load(); await toMission();
await waitFor(`document.querySelectorAll('${HIST} tbody tr').length === 1`, 15000, "fake entry");
await btn(HIST, "Open");
await waitFor(`/could not be opened/.test(document.querySelector('${HIST} [role=alert]')?.textContent || '')`, 20000, "open error").catch(() => {});
const err = await evaluate(`({ alert: document.querySelector('${HIST} [role=alert]')?.textContent || '', tab: document.querySelector('button.tab[aria-selected=true]').textContent })`);
check("error state: a missing result is reported in place (Run the analysis again), the dashboard stays usable", /could not be opened/.test(err.alert) && err.tab === "Mission", err);
await shot("04-open-error");

// ---- 8. error state: API unreachable
await evaluate("try { sessionStorage.clear(); } catch (e) {} true");
await send("Network.setBlockedURLs", { urls: ["*/api/status"] });
await send("Page.navigate", { url: BASE + "/" }); await sleep(2500);
await toMission(); await sleep(500);
const down = await evaluate(`({ status: document.querySelector('${STATUS}').textContent, sidebar: document.querySelector('.sidebar').textContent })`);
check("error state: with the status API unreachable the dashboard and sidebar say so; no readiness is invented", /The API is not reachable/.test(down.status) && /The API is not reachable/.test(down.sidebar), { status: down.status.slice(0, 160) });
await shot("05-api-unreachable");
await send("Network.setBlockedURLs", { urls: [] });

// ---- 9. layouts: every tab at 1440, 390 and 320 px without sideways scrolling
await load();
const layout = {};
for (const [w, h] of [[1440, 900], [390, 844], [320, 640]]) {
  await send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: w < 500 ? 2 : 1, mobile: w < 500 });
  for (const t of ["Mission", "Site", "Compare", "Data and validation", "Guide"]) {
    await tab(t); await sleep(600);
    layout[`${w}:${t}`] = await evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth");
  }
  await tab("Mission"); await sleep(300); await shot(`06-mission-${w}`);
}
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
check("layout: no sideways scrolling on any tab at 1440, 390 and 320 px", Object.values(layout).every(Boolean), layout);

const errors = consoleMsgs.filter((m) => m.type === "exception" || m.type === "error" || (m.type === "log-error" && !errorsAllowed.test(m.text)));
check("no page exceptions or console errors (apart from the deliberate 404 and blocked request)", errors.length === 0, errors.slice(0, 5));
report.checks = checks; report.console = consoleMsgs; report.finished = new Date().toISOString();
fs.writeFileSync(path.join(OUT, "e2e-check.json"), JSON.stringify(report, null, 1));
const failed = checks.filter((c) => !c.ok).length;
console.log(`e2e-live-check: ${checks.length - failed}/${checks.length} checks passed`);
ws.close(); proc.kill();
try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* browser may still hold files */ }
process.exit(failed ? 1 : 0);
