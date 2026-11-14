// LUNA-OPS 2.0 Phase 4 UI corrections: measurement and screenshots (CDP harness from the Phase 1 evidence, cdp_harness.txt).
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

// LUNA-OPS 2.0 Phase 4 UI corrections: short measurement and screenshot run (one browser), used before and after the
// fixes. Appended to the Phase 1 CDP harness (cdp_harness.txt). Usage: node ui_fixes.mjs --base <url> --out <dir> --label before|after
//  1. Data and validation: the validation report table (column widths, whether a status wraps, horizontal scroll on phones)
//  2. Analysis result (custom site): blank space under the South Polar Map in the terrain section
//  3. Guide against Data and validation: container position and width at 1440, 1024 and 390 px
const LABEL = arg("--label", "run");
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const tab = (name) => evaluate(`(() => { const b = [...document.querySelectorAll('button.tab')].find(e => e.textContent.trim() === ${JSON.stringify(name)}); if (b) b.click(); return !!b; })()`);
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
const size = (w, h) => send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
const top0 = () => evaluate("document.querySelector('.main')?.scrollTo(0, 0); window.scrollTo(0, 0); true");
const out = { label: LABEL, report: {}, map: {}, layout: {} };

// the validation report table: the table that follows the report heading on the Data page
const REPORT = "(() => { const h = [...document.querySelectorAll('.prose h2')].find(e => /Validation report/i.test(e.textContent)); let n = h && h.nextElementSibling; while (n && !n.querySelector('table')) n = n.nextElementSibling; return n; })()";
const measureReport = () => evaluate(`(() => { const box = ${REPORT}; if (!box) return null; const t = box.querySelector('table');
  const heads = [...t.querySelectorAll('thead th')].map(th => ({ text: th.textContent.trim(), w: Math.round(th.getBoundingClientRect().width) }));
  const statusCells = [...t.querySelectorAll('tbody tr')].map(tr => tr.children[2]);
  const lines = (el) => { const tw = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); const ys = new Set(); for (let n = tw.nextNode(); n; n = tw.nextNode()) { if (!n.textContent.trim()) continue; const r = document.createRange(); r.selectNodeContents(n); for (const q of r.getClientRects()) ys.add(Math.round(q.top)); } return ys.size; };
  const wrapped = statusCells.filter(c => lines(c) > 1).map(c => c.textContent.trim());
  return { heads, rows: statusCells.length, statusWords: [...new Set(statusCells.map(c => c.textContent.trim()))], wrappedStatuses: wrapped.length, wrappedExamples: wrapped.slice(0, 3),
    scrollable: box.scrollWidth > box.clientWidth + 1, boxW: Math.round(box.clientWidth), tableW: Math.round(t.scrollWidth) }; })()`);
const container = () => evaluate("(() => { const p = document.querySelector('.prose'); const r = p.getBoundingClientRect(); const h2 = p.querySelector('h2').getBoundingClientRect(); const para = p.querySelector('h2 ~ p, h2 ~ dl dd'); const pr = para ? para.getBoundingClientRect() : null; const head = p.querySelector('.site-header').getBoundingClientRect(); return { left: Math.round(r.left), width: Math.round(r.width), headerLeft: Math.round(head.left), h2Left: Math.round(h2.left), h2Width: Math.round(h2.width), firstTextWidth: pr ? Math.round(pr.width) : null, hscroll: document.documentElement.scrollWidth > document.documentElement.clientWidth }; })()");

await size(1440, 900);
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);

// 1 + 3: Data and Guide at three widths
for (const [w, h, kind] of [[1440, 900, "desktop"], [1024, 768, "tablet"], [390, 844, "phone"]]) {
  await size(w, h); await sleep(600);
  await tab("Data and validation"); await waitFor("document.querySelector('.prose h2')", 30000, "data"); await sleep(500); await top0(); await sleep(200);
  out.layout[`data-${kind}`] = await container();
  await shot(`${LABEL}-${kind}-data-top`, null);
  if (kind !== "tablet") {
    out.report[kind] = await measureReport();
    await evaluate(`(${REPORT}).scrollIntoView({ block: 'center' }); true`); await sleep(300);
    await shot(`${LABEL}-${kind}-validation-report`, null);
  }
  await tab("Guide"); await waitFor("document.querySelector('.prose h2')", 30000, "guide"); await sleep(500); await top0(); await sleep(200);
  out.layout[`guide-${kind}`] = await container();
  await shot(`${LABEL}-${kind}-guide-top`, null);
}

// 2: the analysis result's terrain section (cached Site01 one-week analysis)
await size(1440, 900); await sleep(400);
await tab("Site"); await sleep(400);
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447");
await evaluate(`(() => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  for (const [id, v] of [['#start', '2026-11-14T00:00'], ['#end', '2026-11-21T00:00']]) { const e = document.querySelector(id); set.call(e, v); e.dispatchEvent(new Event('input', { bubbles: true })); } return true; })()`);
await waitFor("/covers this point/.test(document.querySelector('.explorer .hint[aria-live]')?.textContent || '')", 60000, "coverage");
await evaluate("document.querySelector('.explorer-run').click(); true");
await waitFor("document.querySelector('#result-terrain .map-host canvas') && document.querySelector('.terrain-figures')", 900000, "result terrain");
await sleep(2500);
const mapMeasure = () => evaluate(`(() => { const panes = [...document.querySelectorAll('#result-terrain .terrain-grid > .pane')]; const m = panes[0], t = panes[1];
  const stage = m.querySelector('.pane-body').getBoundingClientRect(), note = m.querySelector('.pane-note').getBoundingClientRect(), pr = m.getBoundingClientRect();
  return { mapPaneH: Math.round(pr.height), terrainPaneH: Math.round(t.getBoundingClientRect().height), stageH: Math.round(stage.height), stageW: Math.round(stage.width),
    blankBelowCaption: Math.round(pr.bottom - note.bottom), canvasH: Math.round(m.querySelector('.map-host canvas')?.getBoundingClientRect().height ?? 0),
    controls: !!m.querySelector('.ol-zoom') && !!m.querySelector('.map-tools') && !!m.querySelector('.map-legend') && !!m.querySelector('.map-readout') }; })()`);
for (const [w, h, kind] of [[1440, 900, "desktop"], [1024, 768, "tablet"], [390, 844, "phone"]]) {
  await size(w, h); await sleep(1500);
  await evaluate("document.getElementById('result-terrain').scrollIntoView({ block: 'start' }); true"); await sleep(1200);
  out.map[kind] = await mapMeasure();
  await shot(`${LABEL}-${kind}-result-terrain`, null);
  if (kind === "phone") { await evaluate("document.querySelector('#result-terrain .terrain-grid > .pane .pane-note').scrollIntoView({ block: 'center' }); true"); await sleep(500); await shot(`${LABEL}-${kind}-result-map-caption`, null); }
}
out.consoleErrors = consoleMsgs.filter((x) => x.type === "exception" || x.type === "error" || x.type === "log-error").slice(0, 5);
fs.writeFileSync(path.join(OUT, `ui-fixes-${LABEL}.json`), JSON.stringify(out, null, 1));
console.log(JSON.stringify(out, null, 1));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
