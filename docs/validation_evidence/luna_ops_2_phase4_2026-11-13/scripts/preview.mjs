// LUNA-OPS 2.0 Phase 4: mission dashboard preview (CDP harness from the Phase 1 evidence, cdp_harness.txt).
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

// LUNA-OPS 2.0 Phase 4: short visual preview of the mission dashboard (one browser). Appended to the Phase 1 CDP
// harness (cdp_harness.txt). Usage: node preview.mjs --base <url> --out <dir> [--label x]
// States: empty; two candidates with session analyses (one-week Site01 and a second site, served from the backend cache);
// a comparison (2 sites x 1 window, cached). Checks recorded: the dashboard wording, six h2 sections, locator
// selection, candidate cards' latest-analysis values against the stored history, comparison cells against the API.
const LABEL = arg("--label", "phase4");
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const tab = (name) => evaluate(`(() => { const b = [...document.querySelectorAll('button.tab')].find(e => e.textContent.trim() === ${JSON.stringify(name)}); if (b) b.click(); return !!b; })()`);
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
const size = (w, h) => send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
const btn = (scope, text) => evaluate(`(() => { const b = [...document.querySelectorAll(${JSON.stringify(scope + " button")})].find(e => e.textContent.trim() === ${JSON.stringify(text)} && !e.disabled); if (b) b.click(); return !!b; })()`);
const top0 = () => evaluate("document.querySelector('.main')?.scrollTo(0, 0); window.scrollTo(0, 0); true");
const to = (sel) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (e) e.scrollIntoView({ block: 'start' }); return !!e; })()`);
const t0 = Date.now(); const log = (m) => console.log(`[${((Date.now() - t0) / 1000).toFixed(0)} s] ${m}`);
const meta = { label: LABEL };
const SEL = "section[aria-labelledby=mission-selected]", CAND = "section[aria-labelledby=mission-candidates]", CMP = "section[aria-labelledby=mission-comparison]";

await size(1440, 900);
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
await tab("Mission"); await waitFor("document.querySelector('.mission-strip')", 30000, "dashboard"); await sleep(600);
await shot(`${LABEL}-desktop-empty`, null);

// two candidates, each analysed (cached), the second analysed from its candidate card
await tab("Site"); await sleep(400);
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447");
await evaluate(`(() => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  for (const [id, v] of [['#start', '2026-11-14T00:00'], ['#end', '2026-11-21T00:00']]) { const e = document.querySelector(id); set.call(e, v); e.dispatchEvent(new Event('input', { bubbles: true })); } return true; })()`);
await waitFor("/covers this point/.test(document.querySelector('.explorer .hint[aria-live]')?.textContent || '')", 60000, "coverage 1");
await btn(".sidebar", "Add to comparison");
await evaluate("document.querySelector('.explorer-run').click(); true");
await waitFor("document.querySelector('.figures')", 900000, "analysis 1"); log("analysis 1");
await evaluate("(() => { const b = [...document.querySelectorAll('button')].find(e => e.textContent.trim() === 'Back to the Moon explorer'); b && b.click(); return true; })()"); await sleep(600);
await setValue("#lat", "-89.2"); await setValue("#lon", "200");
await waitFor("/covers this point/.test(document.querySelector('.explorer .hint[aria-live]')?.textContent || '')", 60000, "coverage 2");
await btn(".sidebar", "Add to comparison");
await tab("Mission"); await waitFor(`document.querySelectorAll('${CAND} li').length === 2`, 30000, "two candidates"); await sleep(800);
await evaluate(`[...document.querySelectorAll('${CAND} button')].find(b => b.getAttribute('aria-label') === 'Analyse 89.200° S, 200.000° E')?.click(); true`);
await waitFor("document.querySelector('.figures')", 900000, "analysis 2"); log("analysis 2");
await tab("Compare"); await sleep(500);
await evaluate("(() => { const b = [...document.querySelectorAll('button')].find(e => e.textContent.trim() === \"Add the panel's dates\"); b && b.click(); return true; })()"); await sleep(300);
await evaluate("document.querySelector('.compare-run .run-button').click(); true");
await waitFor("document.querySelector('table.matrix')", 900000, "comparison"); log("comparison");
await tab("Mission"); await waitFor("document.querySelector('.mission-cmp')", 30000, "dashboard comparison"); await sleep(1200);

// checks on what the dashboard shows
meta.h2 = await evaluate("document.querySelectorAll('.mission h2').length");
meta.wording = await evaluate("(() => { const m = document.querySelector('.mission').cloneNode(true); m.querySelectorAll('.site-coords, .mission-pad').forEach(e => e.remove()); const t = m.textContent; const hit = t.match(/score|probabilit|recommend|rank|best site/i); return hit ? hit[0] : null; })()");
meta.candidates = await evaluate(`[...document.querySelectorAll('${CAND} li')].map(li => ({ name: li.querySelector('strong')?.textContent, coverage: li.querySelector('p.hint')?.textContent,
  window: li.querySelector('.cand-window')?.textContent || null, values: [...li.querySelectorAll('.cand-v')].map(v => v.textContent), none: li.querySelector('.cand-none')?.textContent || null }))`);
meta.history = await evaluate("[...document.querySelectorAll('section[aria-labelledby=mission-history] tbody tr')].map(tr => [...tr.querySelectorAll('td')].slice(0, 5).map(td => td.textContent))");
meta.comparison = await evaluate(`[...document.querySelectorAll('${CMP} tbody tr')].map(tr => [...tr.querySelectorAll('td')].map(td => td.textContent))`);
meta.compareApi = await evaluate(`(async () => { const s = await (await fetch('/api/status')).json(); return null; })()`);
meta.links = await evaluate("[...document.querySelectorAll('section[aria-labelledby=mission-current] .mission-links button')].map(b => b.textContent)");
meta.figures = await evaluate("Object.fromEntries([...document.querySelectorAll('.mission-figures div')].map(d => [d.querySelector('dt').textContent, d.querySelector('dd').firstChild.textContent]))");

for (const [w, h, kind] of [[1440, 900, "desktop"], [1024, 768, "tablet"], [390, 844, "phone"]]) {
  await size(w, h); await sleep(1000); await top0(); await sleep(300);
  await shot(`${LABEL}-${kind}-top`, null);
  await to("section[aria-labelledby=mission-current]"); await sleep(300); await shot(`${LABEL}-${kind}-current`, null);
  await to(CAND); await sleep(300); await shot(`${LABEL}-${kind}-candidates`, null);
  await to("section[aria-labelledby=mission-history]"); await sleep(300); await shot(`${LABEL}-${kind}-history-comparison`, null);
  if (kind === "phone") await to(".mission-locator"), await sleep(300), await shot(`${LABEL}-${kind}-locator`, null);
  meta[`layout-${kind}`] = await evaluate(`({ hscroll: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    columns: new Set([...document.querySelectorAll('.mission-card')].map(e => Math.round(e.getBoundingClientRect().left))).size,
    overflow: [...document.querySelectorAll('.mission *')].filter(e => e.getBoundingClientRect().right > document.documentElement.clientWidth + 1 && !e.closest('.table-scroll')).length })`);
}
await size(1440, 900); await sleep(800);
// locator: choosing the other candidate's mark makes it the selected site
const before = await evaluate(`document.querySelector('${SEL} .explorer-coords')?.textContent`);
const marks = await evaluate("[...document.querySelectorAll('.locator-mark')].map(b => ({ label: b.getAttribute('aria-label'), disabled: b.disabled }))");
await evaluate("document.querySelector('.locator-mark:not([disabled])')?.click(); true"); await sleep(800);
meta.locator = { before, marks, after: await evaluate(`document.querySelector('${SEL} .explorer-coords')?.textContent`),
  sidebar: [await evaluate("document.querySelector('#lat').value"), await evaluate("document.querySelector('#lon').value")] };
await top0(); await sleep(300); await shot(`${LABEL}-desktop-after-locator-select`, null);
meta.consoleErrors = consoleMsgs.filter((x) => x.type === "exception" || x.type === "error" || x.type === "log-error").slice(0, 10);
fs.writeFileSync(path.join(OUT, `preview-${LABEL}.json`), JSON.stringify(meta, null, 1));
console.log(JSON.stringify(meta, null, 1));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
