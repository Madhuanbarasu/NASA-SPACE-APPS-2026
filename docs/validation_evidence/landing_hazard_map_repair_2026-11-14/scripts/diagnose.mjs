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

// Diagnosis: the landing hazard map at several terrain products / windows. Records every tile and landing-layer
// request (status, duration, failures), console errors, and how much of the map canvas is actually painted.
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable"); await send("Network.enable");
const reqs = new Map(); const net = [];
ws.addEventListener("message", (m) => { const msg = JSON.parse(m.data); const p = msg.params || {};
  if (msg.method === "Network.requestWillBeSent" && /\/api\/(display\/tiles|landing|tiles)/.test(p.request.url)) reqs.set(p.requestId, { url: p.request.url.replace(BASE, ""), t0: p.timestamp });
  if (msg.method === "Network.responseReceived" && reqs.has(p.requestId)) Object.assign(reqs.get(p.requestId), { status: p.response.status });
  if (msg.method === "Network.loadingFinished" && reqs.has(p.requestId)) { const r = reqs.get(p.requestId); r.ms = Math.round((p.timestamp - r.t0) * 1000); net.push(r); reqs.delete(p.requestId); }
  if (msg.method === "Network.loadingFailed" && reqs.has(p.requestId)) { const r = reqs.get(p.requestId); r.failed = p.errorText; r.ms = Math.round((p.timestamp - r.t0) * 1000); net.push(r); reqs.delete(p.requestId); } });
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const proto = e.tagName === 'SELECT' ? HTMLSelectElement.prototype : HTMLInputElement.prototype; Object.getOwnPropertyDescriptor(proto, 'value').set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
// painted share of the map: OpenLayers draws each layer on its own canvas inside .map-host
const PAINT = `(() => { const host = document.querySelector('.landing-map .map-host'); if (!host) return null;
  const r = host.getBoundingClientRect(); const cv = [...host.querySelectorAll('canvas')];
  const per = cv.map((c) => { try { const g = c.getContext('2d'); const d = g.getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 3; i < d.length; i += 16) if (d[i] > 0) n++; return { w: c.width, h: c.height, painted: +(100 * n / (d.length / 16)).toFixed(1) }; } catch (e) { return { err: String(e) }; } });
  return { host: [Math.round(r.width), Math.round(r.height)], canvases: per,
    notes: [...document.querySelectorAll('.landing-mapcard .pane-note, .landing-mapcard .pane-empty')].map((e) => e.textContent),
    findings: [...document.querySelectorAll('.landing-findings > li')].map((li) => li.innerText.replace(/\s+/g, ' ').slice(0, 160)),
    product: document.querySelector('#ls-product')?.value, productOptions: [...(document.querySelector('#ls-product')?.options || [])].map((o) => o.value) }; })()`;
const out = [];
const cases = [["s85-auto", "-85.3305", "285.2104", null, "3000"], ["s85-240m", "-85.3305", "285.2104", "240m:LDEM_60S_240MPP_ADJ.TIF", "3000"],
  ["s85-80m", "-85.3305", "285.2104", "80m:LDEM_80S_80MPP_ADJ.tiff", "3000"], ["s88-auto", "-88.5", "60", null, "3000"],
  ["site01-auto", "-89.463163", "222.510447", null, "3000"], ["s85-auto-12km", "-85.3305", "285.2104", null, "12000"]];
for (const [tag, lat, lon, prod, win] of cases) {
  await evaluate("document.querySelector('#tab-site').click(); true"); await sleep(400);
  await setValue("#lat", lat); await setValue("#lon", lon);
  await evaluate("document.querySelector('#tab-landing').click(); true");
  await waitFor("document.querySelector('.landing-run') && !document.querySelector('.landing-run').disabled", 60000, "landing");
  await sleep(600);
  const winHalf = String(Number(win) / 2);
  await setValue("#ls-window", winHalf);
  if (prod) await setValue("#ls-product", prod); else await setValue("#ls-product", "auto");
  const n0 = net.length;
  await evaluate("document.querySelector('.landing-run').click(); true");
  for (let i = 0; i < 600 && !net.slice(n0).some((r) => /\/api\/landing\/assess/.test(r.url)); i++) await sleep(500);
  await waitFor("document.querySelector('.landing-map .map-host canvas')", 60000, "map " + tag); await sleep(6000);
  await evaluate("document.querySelector('.landing-mapcard').scrollIntoView({ block: 'start' }); true"); await sleep(1500);
  const p = await evaluate(PAINT);
  const { data } = await send("Page.captureScreenshot", { format: "png" });
  fs.writeFileSync(path.join(OUT, "screenshots", `diag-${tag}.png`), Buffer.from(data, "base64"));
  const mine = net.slice(n0); const pend = [...reqs.values()].map((r) => r.url);
  const tiles = mine.filter((r) => /display\/tiles/.test(r.url));
  const rec = { tag, paint: p, tiles: { n: tiles.length, codes: [...new Set(tiles.map((t) => t.status ?? t.failed))], maxMs: Math.max(0, ...tiles.map((t) => t.ms)), pendingAfter6s: pend.filter((u) => /tiles/.test(u)).length },
    landing: mine.filter((r) => /landing/.test(r.url)).map((r) => `${r.status ?? r.failed} ${r.ms}ms ${r.url.slice(0, 90)}`) };
  out.push(rec); console.log(JSON.stringify(rec));
}
fs.writeFileSync(path.join(OUT, "diagnosis.json"), JSON.stringify({ cases: out, console: consoleMsgs.filter((x) => /error|exception|warn/.test(x.type)) }, null, 1));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
