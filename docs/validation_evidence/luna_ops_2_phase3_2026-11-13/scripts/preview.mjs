// LUNA-OPS 2.0 Phase 3: analysis and comparison preview screenshots (CDP harness from the Phase 1 evidence, cdp_harness.txt).
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

// LUNA-OPS 2.0 Phase 3: short visual preview of the analysis workspace and the comparison workspace (one browser).
// Appended to the Phase 1 CDP harness (cdp_harness.txt). Usage: node preview.mjs --base <url> --out <dir> [--label x]
// One one-week Site01 analysis and one comparison (2 sites x 1 window). Screenshots at 1440, then 1024 and 390 px of
// the same views (resized in place, no reload, so no analysis is repeated).
const LABEL = arg("--label", "phase3");
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const tab = (name) => evaluate(`(() => { const b = [...document.querySelectorAll('button.tab')].find(e => e.textContent.trim() === ${JSON.stringify(name)}); if (b) b.click(); return !!b; })()`);
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
const to = (id, block = "start") => evaluate(`(() => { const e = document.getElementById(${JSON.stringify(id)}); if (e) e.scrollIntoView({ block: ${JSON.stringify(block)} }); return !!e; })()`);
const size = (w, h) => send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
const t0 = Date.now();
const log = (m) => console.log(`[${((Date.now() - t0) / 1000).toFixed(0)} s] ${m}`);
const meta = { label: LABEL };

await size(1440, 900);
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(1000);
await tab("Site"); await sleep(500);
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447");
await evaluate(`(() => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  for (const [id, v] of [['#start', '2026-11-14T00:00'], ['#end', '2026-11-21T00:00']]) { const e = document.querySelector(id); set.call(e, v); e.dispatchEvent(new Event('input', { bubbles: true })); } return true; })()`);
await waitFor("/covers this point/.test(document.querySelector('.explorer .hint[aria-live]')?.textContent || '')", 60000, "coverage");
await evaluate("document.querySelector('.explorer-run').click(); true");
log("analysis started");
await waitFor("document.querySelector('a[href$=\"/result.json\"]') && document.querySelector('.figures')", 900000, "analysis workspace");
log("analysis workspace shown");
await sleep(2500);
const views = async (kind) => {
  await evaluate("document.querySelector('.main')?.scrollTo(0, 0); window.scrollTo(0, 0); true"); await sleep(400);
  await shot(`${LABEL}-${kind}-result-top`, null);
  for (const [id, name, wait] of [["result-summary", "summary", 300], ["result-panorama", "horizon", 500], ["result-timeline", "timeline", 400],
    ["result-visibility", "sunlight", 400], ["result-earth", "earth", 400], ["result-terrain", "terrain", 3500], ["result-validation", "validation", 400]]) {
    await to(id); await sleep(wait);
    await shot(`${LABEL}-${kind}-${name}`, null);
  }
  return evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth");
};
meta.hscroll = { desktop: await views("desktop") };
// hover panels: the sunlight chart and the horizon panorama
await to("result-visibility"); await sleep(400);
const box = await evaluate("(() => { const r = document.querySelector('.vis-sun svg').getBoundingClientRect(); return { x: r.left + r.width * 0.42, y: r.top + r.height * 0.7 }; })()");
await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: box.x, y: box.y }); await sleep(500);
await shot(`${LABEL}-desktop-sunlight-hover`, null);
await to("result-panorama"); await sleep(400);
const pbox = await evaluate("(() => { const r = document.querySelector('.panorama svg').getBoundingClientRect(); return { x: r.left + r.width * 0.55, y: r.top + r.height * 0.5 }; })()");
await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: pbox.x, y: pbox.y }); await sleep(500);
await shot(`${LABEL}-desktop-horizon-hover`, null);
// next-event button moves the shared cursor
const before = await evaluate("document.querySelector('.cursor-time').textContent");
await evaluate("document.querySelectorAll('.event-step')[1].click(); true"); await sleep(600);
meta.nextEvent = { before, after: await evaluate("document.querySelector('.cursor-time').textContent"),
  highlighted: await evaluate("document.querySelector('.event-row.is-next .event-name')?.textContent || ''") };
meta.terrain = await evaluate("({ figures: [...document.querySelectorAll('.terrain-figures .metric')].map(m => m.textContent), message: document.querySelector('#result-terrain .pane-message')?.textContent || null })");
meta.figures = await evaluate("[...document.querySelectorAll('.figure .big')].map(e => e.textContent)");
meta.badges = await evaluate("[...document.querySelectorAll('.validation-panel tbody tr')].map(tr => tr.querySelector('th').textContent + ' | ' + tr.querySelectorAll('td')[1].textContent + ' | ' + [...tr.querySelectorAll('.test-list .status-badge')].map(b => b.className.replace('status-badge ', '') + ':' + b.textContent).join(' '))");
for (const [w, h, kind] of [[1024, 768, "tablet"], [390, 844, "phone"]]) {
  await size(w, h); await sleep(1200);
  meta.hscroll[kind] = await views(kind);
}
await size(1440, 900); await sleep(800);
log("result previews done");

// comparison: Site01 and a second site, one window (the panel's dates)
await evaluate("(() => { const b = [...document.querySelectorAll('button')].find(e => e.textContent.trim() === 'Back to the Moon explorer'); if (b) b.click(); return !!b; })()"); await sleep(800);
await evaluate("(() => { const b = [...document.querySelectorAll('.sidebar button')].find(e => e.textContent.trim() === 'Add to comparison'); if (b) b.click(); return !!b; })()"); await sleep(300);
await setValue("#lat", "-89.2"); await setValue("#lon", "200"); await sleep(400);
await waitFor("/covers this point/.test(document.querySelector('.explorer .hint[aria-live]')?.textContent || '')", 60000, "coverage 2");
await evaluate("(() => { const b = [...document.querySelectorAll('.sidebar button')].find(e => e.textContent.trim() === 'Add to comparison'); if (b) b.click(); return !!b; })()"); await sleep(300);
await tab("Compare"); await sleep(600);
await evaluate("(() => { const b = [...document.querySelectorAll('button')].find(e => e.textContent.trim() === \"Add the panel's dates\"); if (b) b.click(); return !!b; })()"); await sleep(300);
await shot(`${LABEL}-desktop-compare-builder`, null);
await evaluate("document.querySelector('.compare-run .run-button').click(); true");
log("comparison started");
await waitFor("document.querySelector('table.matrix') && document.querySelector('.site-cards')", 900000, "comparison");
await waitFor("document.querySelector('.compare-chart svg')", 30000, "comparison charts");
log("comparison shown"); await sleep(1500);
meta.compare = await evaluate("({ cards: document.querySelectorAll('.site-card').length, cells: document.querySelectorAll('table.matrix td').length, scatterPoints: document.querySelectorAll('.compare-chart:nth-child(2) circle').length })");
for (const [w, h, kind] of [[1440, 900, "desktop"], [1024, 768, "tablet"], [390, 844, "phone"]]) {
  await size(w, h); await sleep(1000);
  await evaluate("document.querySelector('.compare-provenance').scrollIntoView({ block: 'start' }); true"); await sleep(400);
  await shot(`${LABEL}-${kind}-compare-cards`, null);
  await evaluate("document.querySelector('table.matrix').scrollIntoView({ block: 'center' }); true"); await sleep(400);
  await shot(`${LABEL}-${kind}-compare-matrix`, null);
  await evaluate("document.querySelector('.compare-charts').scrollIntoView({ block: 'start' }); true"); await sleep(600);
  await shot(`${LABEL}-${kind}-compare-charts`, null);
  meta.hscroll[`compare-${kind}`] = await evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth");
}
const errors = consoleMsgs.filter((x) => x.type === "exception" || x.type === "error" || x.type === "log-error");
meta.consoleErrors = errors.slice(0, 10);
fs.writeFileSync(path.join(OUT, `preview-${LABEL}.json`), JSON.stringify(meta, null, 1));
console.log(JSON.stringify(meta, null, 1));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
