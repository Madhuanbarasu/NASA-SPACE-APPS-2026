import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const BASE = arg("--base", "http://127.0.0.1:8765");
const OUT = path.resolve(arg("--out", "globe-check"));
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

// AUD-06 browser check: South Polar Map at several zoom levels around Site01 and the Landing hazard map's backdrop,
// with the tile requests the page made (route, status, renderer header, served from cache or not).
// --cache-test (after the fix): first loads an engine tile URL so the browser caches it, then shows the app requests the
// new /api/display/tiles/ URLs from the network (never the cached engine tiles).
// One headless browser; appended to the Phase 1 CDP harness. Read only.
// Usage: node maps.mjs --base <url> --out <dir> --label before|after [--cache-test]
const LABEL = arg("--label", "run");
const T0 = Date.now();
const net = new Map();
ws.addEventListener("message", (m) => {
  const msg = JSON.parse(m.data); const p = msg.params;
  if (msg.method === "Network.requestWillBeSent") net.set(p.requestId, { url: p.request.url, t: Date.now() - T0 });
  else if (msg.method === "Network.requestServedFromCache") { const r = net.get(p.requestId); if (r) r.servedFromCache = true; }
  else if (msg.method === "Network.responseReceived") { const r = net.get(p.requestId); if (r) { r.status = p.response.status;
    r.fromDiskCache = !!p.response.fromDiskCache; r.fromMemoryCache = !!p.response.fromMemoryCache;
    const h = Object.fromEntries(Object.entries(p.response.headers || {}).map(([k, v]) => [k.toLowerCase(), v]));
    r.renderer = h["x-lunaops-renderer"] || null; r.cacheControl = h["cache-control"] || null; } }
  else if (msg.method === "Network.loadingFinished") { const r = net.get(p.requestId); if (r) r.done = Date.now() - T0; }
});
await send("Runtime.enable"); await send("Page.enable"); await send("Network.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
const out = { label: LABEL, base: BASE, shots: [], cacheTest: null };
const tiles = (since) => [...net.values()].filter((r) => r.t >= since && /\/tiles\/\d+\/\d+\/\d+\.png/.test(r.url))
  .map((r) => ({ url: r.url.replace(BASE, ""), status: r.status ?? null, renderer: r.renderer ?? null, fromDiskCache: r.fromDiskCache ?? null,
    fromMemoryCache: r.fromMemoryCache ?? null, servedFromCache: !!r.servedFromCache, ms: r.done != null ? r.done - r.t : null }));

if (process.argv.includes("--cache-test")) {
  // a browser that already holds engine tiles (max-age 86400) from before the fix
  await send("Page.navigate", { url: BASE + "/api/tiles/7/63/64.png" }); await sleep(1500);
  await send("Page.navigate", { url: BASE + "/api/tiles/7/63/64.png" }); await sleep(1500);
  out.cacheTest = { engineUrlTwice: tiles(0) };
}
const tApp = Date.now() - T0;
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447");
await evaluate("document.querySelector('#tab-site').click(); true"); await sleep(500);
await evaluate("(() => { const b = [...document.querySelectorAll('.view-switch button')].find(x => x.textContent.trim() === 'South polar map'); b?.click(); return !!b; })()");
await waitFor("document.querySelector('.map-host canvas')", 60000, "map");
const settle = async () => { await sleep(800); try { await waitFor("!document.querySelector('.map-status .is-busy')", 60000, "tiles"); } catch { /* recorded */ } await sleep(1200); };
const mshot = async (name) => {
  const r = await evaluate(`(() => { const b = document.querySelector('.map-host').getBoundingClientRect(); return { x: b.left, y: b.top, width: b.width, height: b.height }; })()`);
  const { data } = await send("Page.captureScreenshot", { format: "png", clip: { ...r, scale: 1 } });
  fs.writeFileSync(path.join(OUT, "screenshots", `${name}.png`), Buffer.from(data, "base64"));
  out.shots.push({ name, scale: await evaluate("document.querySelector('.map-readout .scale-bar')?.textContent || null"),
    readout: await evaluate("[...document.querySelectorAll('.map-readout > span:not(.scale-bar)')].map(s => s.textContent).join(' | ') || null"),
    status: await evaluate("document.querySelector('.map-status')?.textContent || null") });
};
await evaluate("document.querySelector('.map-tools button').click(); true"); await settle(); await mshot("map-1-whole");     // reset view
await evaluate("document.querySelector('.map-tools button:nth-child(2)').click(); true"); await settle(); await mshot("map-2-site");   // centre on site
for (let i = 3; i <= 6; i++) {
  await evaluate("document.querySelector('.map-host .ol-zoom-in').click(); true"); await settle(); await mshot(`map-${i}-zoom-in-${i - 2}`);
}
out.siteTiles = tiles(tApp);

// Landing hazard map: the backdrop alone (no raster) and with the default slope raster
const tL = Date.now() - T0;
await evaluate("document.querySelector('#tab-landing').click(); true");
await waitFor("document.querySelector('.landing-run') && !document.querySelector('.landing-run').disabled", 60000, "landing run");
await evaluate("document.querySelector('.landing-run').click(); true");
await waitFor("document.querySelector('.landing-map canvas')", 300000, "landing map");
await sleep(6000);
await evaluate("document.querySelector('section[aria-labelledby=landing-map]').scrollIntoView({ block: 'start' }); true"); await sleep(500);
const lshot = async (name) => {
  const r = await evaluate(`(() => { const b = document.querySelector('.landing-map.pane-body').getBoundingClientRect(); return { x: b.left, y: b.top, width: b.width, height: b.height }; })()`);
  const { data } = await send("Page.captureScreenshot", { format: "png", clip: { ...r, scale: 1 } });
  fs.writeFileSync(path.join(OUT, "screenshots", `${name}.png`), Buffer.from(data, "base64")); out.shots.push({ name });
};
await lshot("landing-slope-default");
await evaluate("document.querySelector('input[name=ls-raster][value=none]').click(); true"); await sleep(3000); await lshot("landing-backdrop-only");
out.landingTiles = tiles(tL);
out.console = consoleMsgs.filter((x) => /error|exception|warn/.test(x.type));
const all = [...out.siteTiles, ...out.landingTiles];
out.summary = { tileRequests: all.length, routes: [...new Set(all.map((t) => t.url.replace(/\/\d+\/\d+\/\d+\.png$/, "")))],
  renderers: [...new Set(all.map((t) => t.renderer))], statuses: [...new Set(all.map((t) => t.status))],
  fromCache: all.filter((t) => t.fromDiskCache || t.fromMemoryCache || t.servedFromCache).length,
  msMedian: (() => { const v = all.map((t) => t.ms).filter((x) => x != null).sort((a, b) => a - b); return v.length ? v[Math.floor(v.length / 2)] : null; })(),
  msMax: Math.max(...all.map((t) => t.ms ?? 0)) };
fs.writeFileSync(path.join(OUT, `maps-${LABEL}.json`), JSON.stringify(out, null, 1));
console.log(JSON.stringify({ summary: out.summary, shots: out.shots, cacheTest: out.cacheTest, console: out.console.length }, null, 1));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
