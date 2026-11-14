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

await send("Runtime.enable"); await send("Page.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const out = [];
for (const [w, h] of [[1440, 900], [1024, 768], [768, 1024], [390, 844], [320, 640]]) {
  await send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
  await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
  await clickBtn("button.tab", "Guide"); await sleep(800);
  const m = await evaluate(`(() => {
    const a = document.querySelector('.prose'); const ar = a.getBoundingClientRect(); const main = document.querySelector('.main').getBoundingClientRect();
    const cs = getComputedStyle(a);
    const els = [...a.children].map(e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return { tag: e.tagName.toLowerCase(), left: Math.round(r.left - ar.left), top: Math.round(r.top - ar.top), w: Math.round(r.width), h: Math.round(r.height), mt: s.marginTop, mb: s.marginBottom, ml: s.marginLeft, pl: s.paddingLeft }; });
    // inside definition lists
    const dl = [...a.querySelectorAll('dl > *')].slice(0, 6).map(e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return { tag: e.tagName.toLowerCase(), left: Math.round(r.left - ar.left), w: Math.round(r.width), ml: s.marginLeft, mt: s.marginTop }; });
    // overlaps between consecutive blocks
    const blocks = [...a.querySelectorAll('h1,h2,p,dt,dd')]; let overlaps = 0;
    for (let i = 1; i < blocks.length; i++) if (blocks[i].getBoundingClientRect().top < blocks[i - 1].getBoundingClientRect().bottom - 1) overlaps++;
    const site = document.querySelector('.site-header');
    return { article: { left: Math.round(ar.left - main.left), width: Math.round(ar.width), mainWidth: Math.round(main.width), padding: cs.padding, maxWidth: cs.maxWidth },
      hscroll: document.documentElement.scrollWidth > document.documentElement.clientWidth, overlaps, children: els.slice(0, 8), dl }; })()`);
  out.push({ size: [w, h], ...m });
  console.log(`== ${w}x${h}`, JSON.stringify(m.article), "hscroll", m.hscroll, "overlaps", m.overlaps);
  console.log("   blocks", JSON.stringify(m.children.map(c => `${c.tag}@${c.left},${c.top} w${c.w} mt${c.mt} mb${c.mb}`)));
  console.log("   dl", JSON.stringify(m.dl.map(c => `${c.tag}@${c.left} w${c.w} ml${c.ml} mt${c.mt}`)));
  await shot(`guide-${w}`, null);
}
// for comparison: where other views place their page heading and text (same main area)
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
for (const t of ["Mission", "Compare", "Data and validation"]) {
  await clickBtn("button.tab", t); await sleep(900);
  const r = await evaluate(`(() => { const main = document.querySelector('.main').getBoundingClientRect(); const h = document.querySelector('.main h1'); const r = h.getBoundingClientRect(); const s = getComputedStyle(h);
    return { h1Left: Math.round(r.left - main.left), h1Top: Math.round(r.top - main.top), fontSize: s.fontSize, stretch: s.fontStretch, container: h.parentElement.className || h.parentElement.tagName }; })()`);
  console.log("compare", t, JSON.stringify(r));
}
const g = await evaluate(`(() => { document.querySelectorAll('button.tab')[4].click(); return true; })()`); await sleep(800);
console.log("guide h1", JSON.stringify(await evaluate(`(() => { const main = document.querySelector('.main').getBoundingClientRect(); const h = document.querySelector('.prose h1'); const r = h.getBoundingClientRect(); const s = getComputedStyle(h); return { h1Left: Math.round(r.left - main.left), h1Top: Math.round(r.top - main.top), fontSize: s.fontSize, stretch: s.fontStretch }; })()`)));
fs.writeFileSync(path.join(OUT, "guide-layout.json"), JSON.stringify(out, null, 1));
ws.close(); proc.kill(); process.exit(0);
