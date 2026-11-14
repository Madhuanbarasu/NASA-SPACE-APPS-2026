// LUNA-OPS 2.0 Phase 4 second UI review: measurement and screenshots (CDP harness from the Phase 1 evidence, cdp_harness.txt).
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

// LUNA-OPS 2.0 Phase 4, second UI review: before/after measurements and screenshots (one browser, cached results).
// Appended to the Phase 1 CDP harness (cdp_harness.txt). Usage: node ui_fixes2.mjs --base <url> --out <dir> --label before|after
//  1+2. Mission Overview: blank space below Selected site and Candidate sites (0 candidates, then 2 candidates and a result)
//  3.   Data and validation, Guide: container against the workspace with the Mission Parameters panel docked and collapsed
//  4.   South polar map on phones (390 and 320 px): the Legend button against the readout and scale bar
const LABEL = arg("--label", "run");
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const tab = (name) => evaluate(`(() => { const b = [...document.querySelectorAll('button.tab')].find(e => e.textContent.trim() === ${JSON.stringify(name)}); if (b) b.click(); return !!b; })()`);
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
const size = (w, h) => send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
const top0 = () => evaluate("document.querySelector('.main')?.scrollTo(0, 0); window.scrollTo(0, 0); true");
const out = { label: LABEL, mission: {}, prose: {}, map: {} };

// blank space under each dashboard card: the distance from the card's bottom edge to the next card below it in the same
// column (or to the end of the grid), i.e. space no content uses
const missionMeasure = () => evaluate(`(() => { const cards = [...document.querySelectorAll('.mission .mission-card')];
  const r = (e) => e.getBoundingClientRect(); const grid = r(document.querySelector('.mission-grid'));
  const res = {};
  for (const c of cards) {
    const id = c.getAttribute('aria-labelledby') || (c.classList.contains('mission-locator') ? 'locator' : 'card'); const b = r(c);
    const below = cards.map(r).filter(o => o.top >= b.bottom - 1 && o.left < b.right - 1 && o.right > b.left + 1).map(o => o.top);
    const nextTop = below.length ? Math.min(...below) : grid.bottom;
    res[id] = { h: Math.round(b.height), w: Math.round(b.width), left: Math.round(b.left), blankBelow: Math.round(nextTop - b.bottom) };
  }
  return { cards: res, hscroll: document.documentElement.scrollWidth > document.documentElement.clientWidth }; })()`);

await size(1440, 900);
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
await evaluate("try { localStorage.removeItem('luna-ops.params-docked.v1'); } catch (e) {} true");
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);

// ---- 1+2: mission, zero candidates
for (const [w, h, kind] of [[1440, 900, "desktop"], [1024, 768, "tablet"], [390, 844, "phone"]]) {
  await size(w, h); await sleep(500);
  await tab("Mission"); await waitFor("document.querySelector('.mission-strip')", 30000, "mission"); await sleep(700); await top0();
  out.mission[`empty-${kind}`] = await missionMeasure();
  await shot(`${LABEL}-${kind}-mission-empty`, null);
}
// ---- 3: Data and Guide, panel docked and collapsed (1440), drawer layout (1024), phone
await size(1440, 900); await sleep(400);
const proseMeasure = () => evaluate(`(() => { const p = document.querySelector('.prose'), m = document.querySelector('.main'); const pr = p.getBoundingClientRect(), mr = m.getBoundingClientRect();
  const h2 = p.querySelector('h2').getBoundingClientRect(); const tbl = p.querySelector('table'); const tr = tbl ? tbl.getBoundingClientRect() : null;
  return { mainLeft: Math.round(mr.left), mainW: Math.round(mr.width), proseLeft: Math.round(pr.left), proseW: Math.round(pr.width), gapLeft: Math.round(pr.left - mr.left), gapRight: Math.round(mr.right - pr.right),
    h2Left: Math.round(h2.left), h2W: Math.round(h2.width), tableRight: tr ? Math.round(tr.right) : null, overflowX: document.documentElement.scrollWidth > document.documentElement.clientWidth || m.scrollWidth > m.clientWidth + 1 }; })()`);
for (const page of ["Data and validation", "Guide"]) {
  const key = page === "Guide" ? "guide" : "data";
  await size(1440, 900); await sleep(300);
  await tab(page); await waitFor("document.querySelector('.prose h2')", 30000, page); await sleep(500); await top0();
  out.prose[`${key}-1440-docked`] = await proseMeasure(); await shot(`${LABEL}-desktop-${key}-docked`, null);
  await evaluate("document.querySelector('.params-toggle').click(); true"); await sleep(600);
  out.prose[`${key}-1440-collapsed`] = await proseMeasure(); await shot(`${LABEL}-desktop-${key}-collapsed`, null);
  await evaluate("document.querySelector('.params-toggle').click(); true"); await sleep(500);
  await size(1024, 768); await sleep(600); await top0();
  out.prose[`${key}-1024`] = await proseMeasure(); await shot(`${LABEL}-tablet-${key}`, null);
  await evaluate("document.querySelector('.params-toggle').click(); true"); await sleep(600);
  out.prose[`${key}-1024-drawer-open`] = await proseMeasure(); await shot(`${LABEL}-tablet-${key}-drawer-open`, null);
  await evaluate("document.querySelector('#params-close')?.click(); true"); await sleep(400);
  await size(390, 844); await sleep(600); await top0();
  out.prose[`${key}-390`] = await proseMeasure(); await shot(`${LABEL}-phone-${key}`, null);
}

// ---- 1+2: mission with a site, two candidates and a (cached) result
await size(1440, 900); await sleep(400);
await tab("Site"); await sleep(400);
await setValue("#lat", "-89.2"); await setValue("#lon", "200");
await waitFor("/covers this point/.test(document.querySelector('.explorer .hint[aria-live]')?.textContent || '')", 60000, "coverage 2");
await evaluate("(() => { const b = [...document.querySelectorAll('.sidebar button')].find(e => e.textContent.trim() === 'Add to comparison'); b && b.click(); return true; })()");
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447");
await evaluate(`(() => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  for (const [id, v] of [['#start', '2026-11-14T00:00'], ['#end', '2026-11-21T00:00']]) { const e = document.querySelector(id); set.call(e, v); e.dispatchEvent(new Event('input', { bubbles: true })); } return true; })()`);
await waitFor("/covers this point/.test(document.querySelector('.explorer .hint[aria-live]')?.textContent || '')", 60000, "coverage 1");
await evaluate("(() => { const b = [...document.querySelectorAll('.sidebar button')].find(e => e.textContent.trim() === 'Add to comparison'); b && b.click(); return true; })()");
// ---- 4: the explorer's south polar map on phones (selected site, so the readout shows its line and the scale)
const mapMeasure = () => evaluate(`(() => { const st = document.querySelector('.map-stage'); if (!st) return null; const lg = st.querySelector('.map-legend summary'), ro = st.querySelector('.stage-readout'), sc = st.querySelector('.scale-bar');
  const r = (e) => e && e.getBoundingClientRect(); const a = r(lg), b = r(ro), s = r(sc);
  const inter = (p, q) => p && q ? Math.max(0, Math.min(p.right, q.right) - Math.max(p.left, q.left)) * Math.max(0, Math.min(p.bottom, q.bottom) - Math.max(p.top, q.top)) : 0;
  return { stageW: Math.round(r(st).width), legend: a && { w: Math.round(a.width), h: Math.round(a.height) }, overlapReadout: Math.round(inter(a, b)), overlapScale: Math.round(inter(a, s)),
    scaleVisible: !!s && s.width > 0, readoutInside: !!b && b.right <= r(st).right + 0.5 && b.left >= r(st).left - 0.5, hscroll: document.documentElement.scrollWidth > document.documentElement.clientWidth }; })()`);
for (const [w, h] of [[390, 844], [360, 740], [320, 640]]) {
  await size(w, h); await sleep(900);
  await evaluate("(() => { const b = [...document.querySelectorAll('.view-switch button')].find(e => e.textContent.trim() === 'South polar map'); b && b.click(); return true; })()");
  await waitFor("document.querySelector('.map-stage .map-host canvas')", 60000, "map"); await sleep(2500);
  await evaluate("document.querySelector('.explore-pane').scrollIntoView({ block: 'start' }); true"); await sleep(400);
  out.map[`explorer-${w}`] = await mapMeasure();
  await evaluate("document.querySelector('.map-stage').scrollIntoView({ block: 'end' }); true"); await sleep(300);
  await shot(`${LABEL}-${w}-explorer-map`, null);
}
await size(1440, 900); await sleep(600);
await evaluate("document.querySelector('.explorer-run').click(); true");
await waitFor("document.querySelector('.figures')", 900000, "analysis"); await sleep(1500);
for (const [w, h] of [[390, 844], [320, 640]]) {
  await size(w, h); await sleep(1500);
  await evaluate("document.querySelector('#result-terrain .map-stage').scrollIntoView({ block: 'end' }); true"); await sleep(1500);
  out.map[`result-${w}`] = await mapMeasure();
  await shot(`${LABEL}-${w}-result-map`, null);
}
await size(1440, 900); await sleep(500);
await tab("Mission"); await waitFor("document.querySelectorAll('section[aria-labelledby=mission-candidates] li').length === 2", 30000, "candidates"); await sleep(800);
for (const [w, h, kind] of [[1440, 900, "desktop"], [1024, 768, "tablet"], [390, 844, "phone"]]) {
  await size(w, h); await sleep(800); await top0(); await sleep(300);
  out.mission[`populated-${kind}`] = await missionMeasure();
  await shot(`${LABEL}-${kind}-mission-top`, null);
  await evaluate("document.querySelector('section[aria-labelledby=mission-candidates]').scrollIntoView({ block: 'start' }); true"); await sleep(300);
  await shot(`${LABEL}-${kind}-mission-candidates`, null);
}
out.consoleErrors = consoleMsgs.filter((x) => x.type === "exception" || x.type === "error" || x.type === "log-error").slice(0, 5);
fs.writeFileSync(path.join(OUT, `ui-fixes2-${LABEL}.json`), JSON.stringify(out, null, 1));
console.log(JSON.stringify(out, null, 1));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
