// LUNA-OPS 2.0 Phase 1: screenshots of every view at 1440, 1024 and 390 px, plus the navigation states (CDP harness from frontend/scripts).
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const BASE = arg("--base", "http://127.0.0.1:8765");
const OUT = path.resolve(arg("--out", "ui-shots"));
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

// Screenshots of every existing view at desktop, tablet and phone widths (the same sequence before and after Phase 1).
// Appended to the shared CDP harness by build_shots.py. Usage: node ui-shots.mjs --base <url> --out <dir> --label before|after
const LABEL = arg("--label", "run");
// --essential: skip the one long step (a fresh one-week Site analysis for the result screenshots)
const ESSENTIAL = process.argv.includes("--essential");
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
await send("Runtime.enable"); await send("Page.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const tab = (name) => evaluate(`(() => { const b = [...document.querySelectorAll('button.tab, [role=tab]')].find(e => e.textContent.trim() === ${JSON.stringify(name)}); if (b) b.click(); return !!b; })()`);
const full = async (name) => {
  // whole page: the main area scrolls inside the shell on desktop, so capture its full height by growing the viewport
  const h = await evaluate("Math.max(document.documentElement.scrollHeight, (document.querySelector('.main')?.scrollHeight || 0) + (document.querySelector('.main')?.getBoundingClientRect().top || 0))");
  return h;
};
const sizes = [[1440, 900, "desktop"], [1024, 768, "tablet"], [390, 844, "phone"]];
const meta = [];
for (const [w, h, kind] of sizes) {
  await send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
  await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(1500);
  const views = [
    ["site-welcome-map", async () => { await tab("Site"); await sleep(2500); }],
    ["mission", async () => { await tab("Mission"); await waitFor("document.querySelector('.mission')", 30000, "mission"); await sleep(800); }],
    ["compare", async () => { await tab("Compare"); await sleep(800); }],
    ["data", async () => { await tab("Data and validation"); await sleep(800); }],
    ["guide", async () => { await tab("Guide"); await sleep(800); }],
    ["site-globe", async () => { await tab("Site"); await sleep(500);
      await evaluate("(() => { const b = [...document.querySelectorAll('.view-switch button')].find(e => /globe/i.test(e.textContent)); if (b) b.click(); return true; })()");
      await waitFor("document.querySelector('.globe-host canvas')", 60000, "globe"); await sleep(3500); }],
  ];
  for (const [name, go] of views) {
    await go();
    await evaluate("window.scrollTo(0, 0); document.querySelector('.main') && document.querySelector('.main').scrollTo(0, 0); true");
    await sleep(300);
    await shot(`${LABEL}-${kind}-${name}`, null);
    meta.push({ size: [w, h], view: name, hscroll: await evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth") });
  }
  // navigation states (LUNA-OPS 2.0 Phase 1): sidebar docked/collapsed on desktop; views menu and parameters drawer below
  // 1200 px. Only taken when the shell has them (the 1.0 "before" build has neither).
  if (await evaluate("!!document.querySelector('.params-toggle')")) {
    await tab("Mission"); await sleep(900);
    if (kind === "desktop") {
      await shot(`${LABEL}-${kind}-nav-sidebar-docked`, null);
      await evaluate("document.querySelector('.params-toggle').click(); true"); await sleep(700);
      await shot(`${LABEL}-${kind}-nav-sidebar-collapsed`, null);
      await evaluate("document.querySelector('.params-toggle').click(); true"); await sleep(500);
    } else {
      await evaluate("document.querySelector('#nav-toggle').click(); true"); await sleep(600);
      await shot(`${LABEL}-${kind}-nav-menu-open`, null);
      await evaluate("document.querySelector('#nav-toggle').click(); true"); await sleep(400);
      await evaluate("document.querySelector('.params-toggle').click(); true"); await sleep(700);
      await shot(`${LABEL}-${kind}-nav-drawer-open`, null);
      await evaluate("document.querySelector('#params-close').click(); true"); await sleep(400);
    }
  }
  if (kind === "desktop" && !ESSENTIAL) {
    // a result (Site01, one week): the analysis view, top and lower sections
    await tab("Site"); await sleep(300);
    await evaluate("(() => { const b = [...document.querySelectorAll('.view-switch button')].find(e => /map/i.test(e.textContent)); if (b) b.click(); return true; })()");
    await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447");
    await evaluate(`(() => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
      for (const [id, v] of [['#start', '2026-11-14T00:00'], ['#end', '2026-11-21T00:00']]) { const e = document.querySelector(id); set.call(e, v); e.dispatchEvent(new Event('input', { bubbles: true })); } return true; })()`);
    await waitFor("/covers this point/.test(document.querySelector('.explorer .hint[aria-live]')?.textContent || '')", 60000, "coverage");
    await evaluate("document.querySelector('.explorer-run').click(); true");
    await waitFor("document.querySelector('a[href$=\"/result.json\"]')", 900000, "analysis"); await sleep(4000);
    await evaluate("document.querySelector('.main').scrollTo(0, 0); true"); await sleep(300);
    await shot(`${LABEL}-desktop-site-result-top`, null);
    await evaluate("document.getElementById('result-visibility')?.scrollIntoView({ block: 'start' }); true"); await sleep(800);
    await shot(`${LABEL}-desktop-site-result-charts`, null);
    await evaluate("document.getElementById('result-terrain')?.scrollIntoView({ block: 'start' }); true"); await sleep(2500);
    await shot(`${LABEL}-desktop-site-result-terrain`, null);
    await tab("Mission"); await sleep(1200); await shot(`${LABEL}-desktop-mission-with-result`, null);
  }
}
fs.writeFileSync(path.join(OUT, `shots-${LABEL}.json`), JSON.stringify(meta, null, 1));
console.log(JSON.stringify(meta));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
