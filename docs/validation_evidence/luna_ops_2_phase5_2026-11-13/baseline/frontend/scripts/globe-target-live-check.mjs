#!/usr/bin/env node
// "Show on the globe": live check in a real browser (Chrome/Edge headless through the DevTools Protocol, Node's built-in
// WebSocket; no packages). Needs the app running.
//
//   node scripts/globe-target-live-check.mjs --base http://127.0.0.1:8000 --out <dir>
//
// For 10 sites (polar, 0/360 seam, west-negative input, 180, the pole, unsupported, northern) the globe opened with
// "Show on the globe" must be centred on the selected site (centre readout) with the marker at the centre; a site typed
// while the globe is open is followed (half-typed values are not); a click on the globe does not move the camera; a map
// pick followed by Show on the globe shows the new site; the dashboard's 3D Moon opens on the site; with no site the
// default viewpoint is kept. Results in <out>/globe-target-check.json; exit 1 if any check fails.
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const BASE = arg("--base", "http://127.0.0.1:8765");
const OUT = path.resolve(arg("--out", "globe-target-check"));
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

const checks = [];
const check = (name, ok, detail) => { checks.push({ name, ok: !!ok, detail }); console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail !== undefined ? "  " + JSON.stringify(detail).slice(0, 600) : ""}`); };
const report = { base: BASE, browser: BROWSER, started: new Date().toISOString(), sites: [] };
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
await send("Runtime.enable"); await send("Log.enable"); await send("Page.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(1200);

const parse = (t) => { const m = /([\d.]+)° ([NS]),\s*([\d.]+)° E/.exec(t || ""); return m ? { lat: (m[2] === "S" ? -1 : 1) * Number(m[1]), lon: Number(m[3]) } : null; };
const centre = async () => parse(await evaluate("document.querySelector('.globe-readout-mini span')?.textContent || ''"));
const toMap = async () => { await clickBtn(".view-switch button", "South polar map"); await sleep(600); };
const showOnGlobe = async () => { await clickBtn(".explorer button", "Show on the globe"); await waitFor("document.querySelector('.globe-host canvas')", 60000, "globe"); await sleep(2500); };
// marker check: the marker's colour (covered green, uncovered orange or neutral gold) within 14 px of the stage centre
const markerAtCentre = async () => {
  const r = await evaluate("(() => { const s = document.querySelector('.globe-stage'); s.scrollIntoView({ block: 'center' }); const b = s.getBoundingClientRect(); return { x: b.left, y: b.top, w: b.width, h: b.height }; })()");
  await sleep(400);
  const b = await evaluate("(() => { const b = document.querySelector('.globe-stage').getBoundingClientRect(); return { x: b.left, y: b.top, w: b.width, h: b.height }; })()");
  const { data } = await send("Page.captureScreenshot", { format: "png", clip: { x: b.x + b.w / 2 - 14, y: b.y + b.h / 2 - 14, width: 28, height: 28, scale: 1 } });
  return evaluate(`(async () => { const img = new Image(); img.src = 'data:image/png;base64,${data}'; await img.decode();
    const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; const g = c.getContext('2d'); g.drawImage(img, 0, 0);
    const d = g.getImageData(0, 0, c.width, c.height).data; const cols = [[0x7f, 0xc8, 0xa9], [0xee, 0x9a, 0x6b], [0xf2, 0xb5, 0x44]]; let n = 0;
    for (let i = 0; i < d.length; i += 4) if (cols.some(([r, gg, bb]) => Math.abs(d[i] - r) < 40 && Math.abs(d[i + 1] - gg) < 40 && Math.abs(d[i + 2] - bb) < 40)) n++;
    return n; })()`);
};
const clampLat = (la) => Math.max(-89.9, Math.min(89.9, la));
const close = (a, e) => a && Math.abs(a.lat - clampLat(e.lat)) <= 0.0011 && (Math.abs(clampLat(e.lat)) >= 89.9 || Math.abs(((a.lon - e.lon + 540) % 360) - 180) <= 0.0011);

// ---- 1. Show on the globe centres on the exact selected site
const SITES = [
  { typed: ["-89.463163", "222.510447"], exp: { lat: -89.463163, lon: 222.510447 }, note: "Site01 (polar, covered)" },
  { typed: ["-85", "0"], exp: { lat: -85, lon: 0 }, note: "longitude 0" },
  { typed: ["-85", "359.999"], exp: { lat: -85, lon: 359.999 }, note: "longitude just below 360" },
  { typed: ["-80", "-20"], exp: { lat: -80, lon: 340 }, note: "west-negative longitude typed: east 340" },
  { typed: ["-75.5", "180"], exp: { lat: -75.5, lon: 180 }, note: "longitude 180" },
  { typed: ["-60.5", "90"], exp: { lat: -60.5, lon: 90 }, note: "near the 60 S coverage edge" },
  { typed: ["-89.95", "45"], exp: { lat: -89.95, lon: 45 }, note: "within 0.1 degree of the pole (camera held at 89.9)" },
  { typed: ["-90", "0"], exp: { lat: -90, lon: 0 }, note: "the South Pole" },
  { typed: ["-30", "10"], exp: { lat: -30, lon: 10 }, note: "unsupported (outside terrain coverage)" },
  { typed: ["10", "300"], exp: { lat: 10, lon: 300 }, note: "northern hemisphere" },
];
for (const s of SITES) {
  await toMap();
  await setValue("#lat", s.typed[0]); await setValue("#lon", s.typed[1]); await sleep(900);
  const sidebar = await evaluate("({ lat: document.querySelector('#lat').value, lon: document.querySelector('#lon').value, explorer: document.querySelector('.explorer-coords')?.textContent })");
  await showOnGlobe();
  const c = await centre();
  const marker = await markerAtCentre();
  const ok = close(c, s.exp) && marker > 4;
  report.sites.push({ ...s, sidebar, centre: c, markerPixels: marker, ok });
  if (s.note.startsWith("Site01")) await shot("01-site01-on-globe", await evaluate("(() => { const b = document.querySelector('.globe-stage').getBoundingClientRect(); return { x: b.left, y: b.top, width: b.width, height: b.height }; })()"));
}
check("Show on the globe centres the 3D Moon on the selected site (centre readout within 0.001 degrees; at the pole within the 89.9 degree camera limit) with the marker at the centre, for 10 sites incl. 0/360, west-negative input, 180, the pole, unsupported and northern points",
  report.sites.every((s) => s.ok), report.sites.map((s) => ({ note: s.note, centre: s.centre, marker: s.markerPixels, ok: s.ok })));
check("conversions: the explorer shows the east longitude 0-360 for a west-negative input (-20 -> 340.000 E)",
  /340\.000° E/.test(report.sites.find((s) => s.typed[1] === "-20").sidebar.explorer ?? ""), report.sites.find((s) => s.typed[1] === "-20").sidebar);

// ---- 2. no stale view: a site typed while the globe is open is followed
await setValue("#lat", "-80"); await setValue("#lon", "120");
await sleep(2200);
const c2 = await centre();
check("no stale coordinates: typing a new site while the globe is open moves the view to it", close(c2, { lat: -80, lon: 120 }) && (await markerAtCentre()) > 4, c2);
// typing in steps ("-8", "-80.", "-80.5"): the view goes to the final value, not to a half-typed one
await setValue("#lat", "-8"); await sleep(100); await setValue("#lat", "-80."); await sleep(100); await setValue("#lat", "-80.5"); await sleep(2200);
const c3 = await centre();
check("typing: half-typed values are not flown to; the view settles on the final value", close(c3, { lat: -80.5, lon: 120 }), c3);

// ---- 3. a click on the globe sets the site there but does not move the camera
const before = await centre();
const st = await evaluate("(() => { const b = document.querySelector('.globe-stage').getBoundingClientRect(); return { x: b.left, y: b.top, w: b.width, h: b.height }; })()");
await mouseClick(st.x + st.w / 2 + 60, st.y + st.h / 2 + 30); await sleep(2000);
const after = await centre();
const picked = await evaluate("({ lat: document.querySelector('#lat').value, lon: document.querySelector('#lon').value })");
check("a click on the globe selects that point (sidebar updated) without moving the camera", picked.lat !== "-80.5" && before && after && Math.abs(before.lat - after.lat) < 1e-9 && Math.abs(before.lon - after.lon) < 1e-9, { before, after, picked });

// ---- 4. map pick, then Show on the globe: the newly picked site, not the previous one
await toMap();
const mh = await evaluate("(() => { const e = document.querySelector('.map-host'); e.scrollIntoView({ block: 'center' }); const r = e.getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height }; })()");
await sleep(500);
const mh2 = await evaluate("(() => { const r = document.querySelector('.map-host').getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height }; })()");
await mouseClick(mh2.x + mh2.w / 2 + 40, mh2.y + mh2.h / 2 - 20); await sleep(800);
const mapPick = await evaluate("({ lat: Number(document.querySelector('#lat').value), lon: Number(document.querySelector('#lon').value) })");
await showOnGlobe();
const c4 = await centre();
check("map pick then Show on the globe: the globe is centred on the newly picked site (no stale coordinates)", close(c4, mapPick), { mapPick, c4 });

// ---- 5. the 3D Moon from the Mission dashboard opens on the selected site too
await setValue("#lat", "-87.5"); await setValue("#lon", "300"); await sleep(800);
await clickBtn("button.tab", "Mission"); await waitFor("document.querySelector('.mission')", 30000, "mission"); await sleep(500);
await toMap(); await clickBtn("button.tab", "Mission"); await sleep(500);
await evaluate("[...document.querySelectorAll('.mission-nav button')].find(b => b.textContent.trim() === '3D Moon').click(); true");
await waitFor("document.querySelector('.globe-host canvas')", 60000, "globe"); await sleep(2500);
const c5 = await centre();
check("Mission dashboard 3D Moon opens the globe centred on the selected site", close(c5, { lat: -87.5, lon: 300 }), c5);

// ---- 6. no site selected: the default viewpoint, as before
await evaluate("try { sessionStorage.clear(); } catch (e) {} true");
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(1000);
await clickBtn(".view-switch button", "3D Moon globe"); await waitFor("document.querySelector('.globe-host canvas')", 60000, "globe"); await sleep(2000);
const c6 = await centre();
check("no site selected: the globe opens at the default nearside viewpoint (0, 0) as before", c6 && Math.abs(c6.lat) < 0.001 && (c6.lon < 0.001 || c6.lon > 359.999), c6);

const errors = consoleMsgs.filter((m) => m.type === "exception" || m.type === "error" || m.type === "log-error");
check("no page exceptions or console errors", errors.length === 0, errors.slice(0, 5));
report.checks = checks; report.finished = new Date().toISOString();
fs.writeFileSync(path.join(OUT, "globe-target-check.json"), JSON.stringify(report, null, 1));
const failed = checks.filter((c) => !c.ok).length;
console.log(`globe-target-live-check: ${checks.length - failed}/${checks.length} checks passed`);
ws.close(); proc.kill();
try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(failed ? 1 : 0);
