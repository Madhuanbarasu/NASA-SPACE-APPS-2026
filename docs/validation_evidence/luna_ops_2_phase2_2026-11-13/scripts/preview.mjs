// LUNA-OPS 2.0 Phase 2: explorer preview screenshots (CDP harness from the Phase 1 evidence, cdp_harness.txt).
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

// LUNA-OPS 2.0 Phase 2: short visual preview of the explorer stage (one browser, a few screenshots per width).
// Appended to the Phase 1 CDP harness (cdp_harness.txt). Usage: node preview.mjs --base <url> --out <dir> [--label x]
// Also measures the lunar disc on screen (Even light, centre column and row of the stage) and the layout, for the report.
const LABEL = arg("--label", "phase2");
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const tab = (name) => evaluate(`(() => { const b = [...document.querySelectorAll('button.tab')].find(e => e.textContent.trim() === ${JSON.stringify(name)}); if (b) b.click(); return !!b; })()`);
const mode = (name) => evaluate(`(() => { const b = [...document.querySelectorAll('.view-switch button')].find(e => e.textContent.trim() === ${JSON.stringify(name)}); if (b && !b.disabled) b.click(); return !!b && !b.disabled; })()`);
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
const top0 = () => evaluate("window.scrollTo(0, 0); document.querySelector('.main')?.scrollTo(0, 0); true");
const globeReady = async () => { await waitFor("document.querySelector('.globe-host canvas') && !document.querySelector('.globe-message')", 60000, "globe imagery"); await sleep(1500); };
const tilesIdle = async () => { const t0 = Date.now(); while (Date.now() - t0 < 25000) { if (!(await evaluate("!!document.querySelector('.map-status .is-busy')"))) break; await sleep(500); } await sleep(1200); };
// lunar disc on screen: longest lit run (even light) along the stage's centre column and centre row
const disc = async () => {
  await clickBtn(".segmented-mini button", "Even light"); await sleep(600);
  const r = await stageRect();
  const b64 = await shot("_measure", null);
  const m = await evaluate(`(async () => { const img = new Image(); img.src = 'data:image/png;base64,${b64}'; await img.decode();
    const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; const g = c.getContext('2d'); g.drawImage(img, 0, 0);
    const R = ${JSON.stringify(r)}; const cx = Math.round(R.x + R.width / 2) + 40, cy = Math.round(R.y + R.height / 2) + 40;
    const lum = (x, y) => { const d = g.getImageData(x, y, 1, 1).data; return 0.2126 * d[0] + 0.7152 * d[1] + 0.0722 * d[2]; };
    const run = (n, f) => { let best = 0, cur = 0; for (let i = 0; i < n; i++) { if (f(i) > 30) { cur++; best = Math.max(best, cur); } else cur = 0; } return best; };
    return { stageW: Math.round(R.width), stageH: Math.round(R.height), stageTop: Math.round(R.y), discV: run(Math.round(R.height), (i) => lum(cx, Math.round(R.y) + i)),
      discH: run(Math.round(R.width), (i) => lum(Math.round(R.x) + i, cy)) }; })()`);
  await clickBtn(".segmented-mini button", "Even light"); await sleep(400);
  fs.rmSync(path.join(OUT, "screenshots", "_measure.png"), { force: true });
  return m;
};
const meta = { label: LABEL, sizes: {} };
for (const [w, h, kind] of [[1440, 900, "desktop"], [1024, 768, "tablet"], [390, 844, "phone"]]) {
  await send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
  await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(1200);
  await tab("Site"); await sleep(600);
  const m = { hscroll: [] };
  // 3D Moon, opening view
  await mode("3D Moon globe"); await globeReady(); await top0(); await sleep(300);
  if (kind === "phone") await evaluate("document.querySelector('.explore-pane').scrollIntoView({ block: 'start' }); true");
  await sleep(400);
  await shot(`${LABEL}-${kind}-globe`, null);
  m.globe = await disc();
  m.hscroll.push(await evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"));
  if (kind === "desktop") {
    await evaluate("document.querySelector('.globe-legend summary').click(); true"); await sleep(400);
    await shot(`${LABEL}-${kind}-globe-legend-open`, null);
    await evaluate("document.querySelector('.globe-legend summary').click(); true"); await sleep(300);
  }
  // South polar map
  await mode("South polar map"); await waitFor("document.querySelector('.map-host canvas')", 60000, "map"); await tilesIdle(); await top0();
  if (kind === "phone") await evaluate("document.querySelector('.explore-pane').scrollIntoView({ block: 'start' }); true");
  await sleep(400);
  await shot(`${LABEL}-${kind}-map`, null);
  m.map = await evaluate("(() => { const r = document.querySelector('.map-stage').getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height), top: Math.round(r.top) }; })()");
  m.hscroll.push(await evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"));
  if (kind === "desktop") {
    // a registered site (Site01): one selection shared by the map, the globe and the local terrain
    await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447");
    await waitFor("/covers this point/.test(document.querySelector('.explorer .hint[aria-live]')?.textContent || '')", 60000, "coverage");
    await tilesIdle(); await top0(); await sleep(600);
    await shot(`${LABEL}-${kind}-map-site`, null);
    await mode("3D Moon globe"); await globeReady(); await top0(); await sleep(400);
    await shot(`${LABEL}-${kind}-globe-site`, null);
    m.globeSiteCentre = await evaluate("document.querySelector('.globe-readout-mini span')?.textContent || ''");
    await mode("Local terrain"); await waitFor("document.querySelector('.terrain-stats li') && !document.querySelector('.terrain-preview-stage .pane-empty')", 120000, "terrain"); await sleep(1500); await top0();
    await shot(`${LABEL}-${kind}-terrain`, null);
    m.terrain = await evaluate("(() => { const r = document.querySelector('.terrain-preview-stage').getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height) }; })()");
    // under the stage: the introduction, readiness board and steps
    await evaluate("document.querySelector('.welcome-details').scrollIntoView({ block: 'start' }); true"); await sleep(500);
    await shot(`${LABEL}-${kind}-below-stage`, null);
    // a comparison candidate (Site01) and a new selection: the candidate ring on the map and on the globe
    await clickBtn("button", "Add to comparison"); await sleep(400);
    await setValue("#lat", "-89.2"); await setValue("#lon", "200");
    await mode("South polar map"); await waitFor("document.querySelector('.map-host canvas')", 60000, "map"); await sleep(800);
    await evaluate("(() => { const b = document.querySelector('.map-tools button[aria-label^=\"Centre\"]'); if (b) b.click(); return true; })()"); await sleep(800);
    await tilesIdle(); await top0(); await sleep(500);
    await shot(`${LABEL}-${kind}-map-candidate`, null);
    await mode("3D Moon globe"); await globeReady(); await top0(); await sleep(400);
    await evaluate("(() => { const b = document.querySelector('.globe-nav button[aria-label^=\"Centre the view\"]'); if (b) b.click(); return true; })()"); await sleep(1200);
    await evaluate("document.querySelector('.globe-legend summary').click(); true"); await sleep(400);
    await shot(`${LABEL}-${kind}-globe-candidate`, null);
    m.candidateCentre = await evaluate("document.querySelector('.globe-readout-mini span')?.textContent || ''");
    await setValue("#lat", ""); await setValue("#lon", ""); await mode("South polar map"); await sleep(500);
  }
  meta.sizes[kind] = m;
}
const errors = consoleMsgs.filter((x) => x.type === "exception" || x.type === "error" || x.type === "log-error");
meta.consoleErrors = errors.slice(0, 10);
fs.writeFileSync(path.join(OUT, `preview-${LABEL}.json`), JSON.stringify(meta, null, 1));
console.log(JSON.stringify(meta, null, 1));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
