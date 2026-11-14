import { createRequire } from "node:module";
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const BASE = arg("--base", "http://127.0.0.1:8765");
const OUT = path.resolve(arg("--out", "map-diag"));
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

const requireFE = createRequire("E:/LUNA-OPS/frontend/package.json");
const proj4 = requireFE("proj4");
const SPS = "+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +k=1 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs";
const W = Number(arg("--w", "1440")), H = Number(arg("--h", "900"));
const WAIT = Number(arg("--wait", "25000"));
const tiles = new Map();
await send("Runtime.enable"); await send("Log.enable"); await send("Network.enable"); await send("Page.enable");
const t0 = Date.now();
ws.addEventListener("message", (m) => {
  const msg = JSON.parse(m.data);
  if (msg.method === "Network.requestWillBeSent" && /\/api\/tiles\/\d+\/\d+\/\d+\.png/.test(msg.params.request.url))
    tiles.set(msg.params.requestId, { url: msg.params.request.url.replace(/^.*\/api\/tiles\//, ""), start: Date.now() - t0 });
  if (msg.method === "Network.responseReceived" && tiles.has(msg.params.requestId)) { const r = tiles.get(msg.params.requestId); r.status = msg.params.response.status; r.end = Date.now() - t0; }
  if (msg.method === "Network.loadingFailed" && tiles.has(msg.params.requestId)) { const r = tiles.get(msg.params.requestId); r.failed = msg.params.errorText + (msg.params.canceled ? " (canceled)" : ""); r.end = Date.now() - t0; }
});
const tileSummary = (label) => {
  const all = [...tiles.values()];
  const byZ = {};
  for (const r of all) { const z = r.url.split("/")[0]; byZ[z] ??= { n: 0, ok: 0, failed: 0, pending: 0, maxMs: 0 }; const b = byZ[z]; b.n++;
    if (r.failed) b.failed++; else if (r.status) b.ok++; else b.pending++; if (r.end) b.maxMs = Math.max(b.maxMs, r.end - r.start); }
  const pending = all.filter((r) => !r.status && !r.failed).map((r) => `${r.url} (${Math.round((Date.now() - t0 - r.start) / 1000)} s)`);
  const bad = all.filter((r) => r.failed || (r.status && r.status >= 400)).map((r) => `${r.url} ${r.status ?? ""} ${r.failed ?? ""}`);
  const slow = all.filter((r) => r.end && r.end - r.start > 3000).map((r) => `${r.url} ${r.end - r.start} ms`);
  console.log(`[${label}] tiles by zoom ${JSON.stringify(byZ)}\n   pending: ${JSON.stringify(pending)}\n   failed/4xx/5xx: ${JSON.stringify(bad)}\n   slow (>3 s): ${JSON.stringify(slow.slice(0, 12))}`);
};
await send("Emulation.setDeviceMetricsOverride", { width: W, height: H, deviceScaleFactor: 1, mobile: W < 600 });
await send("Page.navigate", { url: BASE + "/" });
await waitFor("document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')", 60000, "status");
await waitFor("document.querySelector('.map-host canvas')", 30000, "map canvas");
await sleep(WAIT);
const host = await evaluate("(() => { const e = document.querySelector('.map-host'); e.scrollIntoView({ block: 'center' }); const r = e.getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height }; })()");
await sleep(500);
const host2 = await evaluate("(() => { const r = document.querySelector('.map-host').getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height }; })()");
console.log("map host", JSON.stringify(host2), "note:", await evaluate("document.querySelector('.pane-note')?.textContent"));
tileSummary("fresh load, after " + WAIT / 1000 + " s");
await shot(`01-fresh-${W}`, { x: host2.x, y: host2.y, width: host2.w, height: host2.h });
// click accuracy on the initial (fitted) view: centre [0,0], resolution = max(extent / size)
const meta = await evaluate("fetch('/api/tiles/meta').then(r => r.json())");
const ext = meta.extent; const res = Math.max((ext[2] - ext[0]) / host2.w, (ext[3] - ext[1]) / host2.h);
const clicks = [];
const hostRect = () => evaluate("(() => { const e = document.querySelector('.map-host'); e.scrollIntoView({ block: 'center' }); const r = e.getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height }; })()");
for (const [dx, dy] of [[60, 40], [-120, 0], [0, -150], [30, 30], [-200, 100], [150, -60], [0, 0], [250, 120]]) {
  await send("Page.reload"); await waitFor("document.querySelector('.map-host canvas')", 30000, "map canvas"); await sleep(3000);
  const hr = await hostRect(); await sleep(400);
  const hr2 = await hostRect();
  const r0 = Math.max((ext[2] - ext[0]) / hr2.w, (ext[3] - ext[1]) / hr2.h);
  await mouseClick(hr2.x + hr2.w / 2 + dx, hr2.y + hr2.h / 2 + dy); await sleep(500);
  const f = await evaluate("({ lat: document.querySelector('#lat').value, lon: document.querySelector('#lon').value })");
  const [lo, la] = proj4(SPS, "+proj=longlat +R=1737400 +no_defs", [dx * r0, -dy * r0]);
  const exp = { lat: Number(la.toFixed(6)), lon: Number((((lo % 360) + 360) % 360).toFixed(6)) };
  const tolDeg = (r0 / 1737400) * 180 / Math.PI;   // one display pixel
  const ok = la > -60 ? f.lat === "" : Math.abs(Number(f.lat) - exp.lat) <= tolDeg && Math.abs(((Number(f.lon) - exp.lon + 540) % 360) - 180) * Math.cos(exp.lat * Math.PI / 180) <= tolDeg;
  clicks.push({ dx, dy, got: f, expected: exp, northOf60: la > -60, ok });
}
console.log("click accuracy", JSON.stringify(clicks));
// select Site01 by typing, wait, inspect the zoomed view and its tiles
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
tiles.clear();
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447");
await sleep(WAIT);
const h3 = await evaluate("(() => { const e = document.querySelector('.map-host'); e.scrollIntoView({ block: 'center' }); const r = e.getBoundingClientRect(); return { x: r.left, y: r.top, width: r.width, height: r.height }; })()");
await sleep(500);
tileSummary("Site01 selected (auto-zoom)");
await shot(`02-site01-${W}`, h3);
// zoom out with the button three times, pan with the keyboard
tiles.clear();
for (let i = 0; i < 3; i++) { await evaluate("document.querySelector('.ol-zoom-out').click(); true"); await sleep(600); }
await evaluate("document.querySelector('.map-host').focus(); true");
for (const k of ["ArrowRight", "ArrowRight", "ArrowDown"]) await press(k);
await sleep(WAIT / 2);
tileSummary("zoom out x3 + keyboard pan");
await shot(`03-zoomout-pan-${W}`, h3);
const errors = consoleMsgs.filter((m) => m.type === "exception" || m.type === "error" || m.type.startsWith("log-"));
console.log("console:", JSON.stringify(errors.slice(0, 20)));
ws.close(); proc.kill();
try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);