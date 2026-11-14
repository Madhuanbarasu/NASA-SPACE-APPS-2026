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

// LUNA-OPS 2.0 Phase 5: Landing Safety previews and measurements (one headless browser; appended to the Phase 1 CDP
// harness, cdp_harness.txt). Usage: node landing_preview.mjs --base <url> --out <dir>
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable"); await send("Network.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const tab = (name) => evaluate(`(() => { const b = [...document.querySelectorAll('button.tab')].find(e => e.textContent.trim() === ${JSON.stringify(name)}); if (b) b.click(); return !!b; })()`);
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return false; const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
const size = (w, h) => send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
const top0 = () => evaluate("document.querySelector('.main')?.scrollTo(0, 0); window.scrollTo(0, 0); true");
const scrollTo = (sel) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (e) e.scrollIntoView({ block: 'start' }); return !!e; })()`);
const clickText = (sel, text) => evaluate(`(() => { const b = [...document.querySelectorAll(${JSON.stringify(sel)})].find(e => e.textContent.trim() === ${JSON.stringify(text)}); if (b) b.click(); return !!b; })()`);
const out = { views: {} };
const hscroll = () => evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth");
const findings = () => evaluate(`[...document.querySelectorAll('.landing-finding')].map(li => li.querySelector('strong').textContent + ' | ' + li.querySelector('.finding-status').textContent)`);
const imgLoaded = () => evaluate(`(() => { const m = document.querySelector('.landing-map canvas'); return !!m; })()`);

await size(1440, 900);
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
await evaluate("try { localStorage.removeItem('luna-ops.params-docked.v1'); } catch (e) {} true");
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
// select the Site01 point (PGDA 78, 5 m) in the Mission Parameters
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447");
await waitFor("/covers this point/.test([...document.querySelectorAll('#coord-hint, .explorer .hint[aria-live], .landing .hint[aria-live]')].map(e => e.textContent).join(' '))", 60000, "coverage");
out.tabs = await evaluate("[...document.querySelectorAll('button.tab')].map(b => b.textContent.trim())");
await tab("Landing"); await waitFor("document.querySelector('.landing .landing-run')", 30000, "landing view"); await sleep(600);
await shot("01-desktop-landing-before-run", null);
const t0 = Date.now();
await evaluate("document.querySelector('.landing-run').click(); true");
await waitFor("document.querySelectorAll('.landing-finding').length >= 5", 120000, "findings");
out.firstRunMs = Date.now() - t0;
await waitFor("document.querySelector('.landing-map canvas')", 30000, "map"); await sleep(2500);
out.views.desktopDefault = { findings: await findings(), hscroll: await hscroll() };
await top0(); await shot("02-desktop-landing-slope-layer", null);
// user-defined thresholds (assumptions for the demonstration)
await setValue("#ls-tslope", "10"); await setValue("#ls-trough", "0.5"); await setValue("#ls-trelief", "10");
await sleep(1800);
out.views.desktopThresholds = await findings();
// pointer readout over the map centre
const mr = await evaluate("(() => { const r = document.querySelector('.landing-map').getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()");
await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: mr.x + 40, y: mr.y + 30 }); await sleep(1200);
out.readout = await evaluate("document.querySelector('.landing-readout')?.textContent || ''");
await scrollTo(".landing-mapcard"); await sleep(300); await shot("03-desktop-map-readout", null);
// raster layers
for (const [label, name] of [["Roughness", "roughness"], ["Data coverage", "coverage"], ["Height uncertainty", "uncertainty"], ["Elevation", "elevation"],
  ["NASA slope product", "nasa_slope"], ["Slope above threshold", "slope_exceed"]]) {
  await evaluate(`(() => { const l = [...document.querySelectorAll('.layer-options label')].find(e => e.textContent.trim() === ${JSON.stringify(label)}); l?.querySelector('input')?.click(); return !!l; })()`);
  await sleep(1500); await scrollTo(".landing-mapcard"); await sleep(200);
  await shot(`04-desktop-layer-${name}`, null);
}
await evaluate(`(() => { const l = [...document.querySelectorAll('.layer-options label')].find(e => e.textContent.trim() === 'Slope'); l?.querySelector('input')?.click(); return true; })()`);
// drag the footprint on the map (it starts at the window centre, which is the map centre after fit)
await scrollTo(".landing-mapcard"); await sleep(300);
const c2 = await evaluate("(() => { const r = document.querySelector('.landing-map').getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()");
const before = await evaluate("document.querySelector('#ls-fplat').value + ',' + document.querySelector('#ls-fplon').value");
await send("Input.dispatchMouseEvent", { type: "mousePressed", x: c2.x, y: c2.y, button: "left", clickCount: 1 });
for (let i = 1; i <= 8; i++) { await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: c2.x + 10 * i, y: c2.y - 6 * i, button: "left", buttons: 1 }); await sleep(40); }
await send("Input.dispatchMouseEvent", { type: "mouseReleased", x: c2.x + 80, y: c2.y - 48, button: "left", clickCount: 1 });
await sleep(1800);
out.drag = { before, after: await evaluate("document.querySelector('#ls-fplat').value + ',' + document.querySelector('#ls-fplon').value"), findings: await findings() };
await shot("05-desktop-footprint-dragged", null);
// resize the footprint
await setValue("#ls-radius", "150"); await sleep(1800);
out.resize = { pixels: await evaluate("[...document.querySelectorAll('.landing-metrics')].pop()?.textContent.slice(0, 120)"), findings: await findings() };
await scrollTo("#landing-footprint"); await sleep(300); await shot("06-desktop-footprint-findings", null);
// select a depression candidate
const hasCand = await evaluate("!!document.querySelector('.landing-cands .link-button')");
if (hasCand) { await evaluate("document.querySelector('.landing-cands .link-button').click(); true"); await sleep(900); }
await scrollTo("#landing-terrain"); await sleep(300); await shot("07-desktop-terrain-analysis", null);
await scrollTo("#landing-candidates"); await sleep(300); await shot("08-desktop-depression-candidates", null);
await scrollTo("#landing-provenance"); await sleep(300); await shot("09-desktop-provenance", null);
out.provenanceText = (await evaluate("document.querySelector('.landing-prov')?.textContent || ''")).slice(0, 600);
// mission dashboard: add the site as a candidate and show its landing findings
await tab("Mission"); await waitFor("document.querySelector('.mission-strip')", 30000, "mission"); await sleep(700);
await clickText(".mission .quiet-button", "Add the selected site"); await sleep(800);
await scrollTo("section[aria-labelledby=mission-candidates]"); await sleep(400);
out.mission = { landingBlock: await evaluate("document.querySelector('.cand-landing')?.textContent || ''"),
  integrity: await evaluate("/score|probabilit|recommend|rank|best site/i.test([...document.querySelectorAll('.mission-candidates, .mission-card h2, .mission-locator')].map(e => e.textContent).join(' '))"),
  nestedLi: await evaluate("document.querySelectorAll('.mission-candidates li li').length"), h2: await evaluate("document.querySelectorAll('.mission h2').length") };
await shot("10-desktop-mission-candidate-landing", null);
// open the candidate in Landing safety from the dashboard
await evaluate("(() => { const b = [...document.querySelectorAll('.mission-candidates button')].find(e => e.textContent.trim() === 'Landing safety'); b?.click(); return !!b; })()");
await waitFor("document.querySelector('.landing .landing-run')", 30000, "landing again"); await sleep(1500);
out.openedFromMission = await evaluate("document.querySelector('.site-title')?.textContent + ' | ' + (document.querySelector('.landing-run')?.textContent || '')");
// returning to the tab: the inputs show the settings of the screening on screen (radius 150 m, thresholds 10 / 0.5 / 10)
await waitFor("document.querySelector('#ls-radius')", 30000, "footprint inputs");
out.returnInputs = await evaluate("['#ls-radius', '#ls-tslope', '#ls-trough', '#ls-trelief'].map(s => document.querySelector(s)?.value).join(' / ') + ' | ' + (document.querySelector('#ls-radius-hint')?.textContent || '')");
// a 20 m site without a count map (Shackleton rim area)
await setValue("#lat", "-89.9"); await setValue("#lon", "0");
await waitFor("/covers this point/.test([...document.querySelectorAll('#coord-hint, .explorer .hint[aria-live], .landing .hint[aria-live]')].map(e => e.textContent).join(' '))", 60000, "coverage 20m"); await sleep(400);
out.staleBanner = await evaluate("document.querySelector('.landing .hint.warn')?.textContent || ''");
await evaluate("document.querySelector('.landing-run').click(); true");
await waitFor("document.querySelector('.landing-prov') && /LDEM_80S_20MPP/.test(document.querySelector('.landing-prov').textContent)", 120000, "20m run");
await sleep(2500); await top0(); await shot("11-desktop-20m-site", null);
out.views.site20m = { findings: await findings(), measured: await evaluate("[...document.querySelectorAll('.landing-metrics .metric')].map(m => m.textContent).join(' | ')") };
// tablet and phone
for (const [w, h, kind] of [[1024, 768, "tablet"], [390, 844, "phone"], [320, 640, "phone320"]]) {
  await size(w, h); await sleep(1200); await top0(); await sleep(300);
  await shot(`12-${kind}-landing-top`, null);
  await scrollTo(".landing-mapcard"); await sleep(800); await shot(`13-${kind}-landing-map`, null);
  await scrollTo("#landing-footprint"); await sleep(300); await shot(`14-${kind}-landing-footprint`, null);
  out.views[kind] = { hscroll: await hscroll(),
    mapBox: await evaluate("(() => { const r = document.querySelector('.landing-map')?.getBoundingClientRect(); return r ? { w: Math.round(r.width), h: Math.round(r.height) } : null; })()") };
}
out.consoleErrors = consoleMsgs.filter((x) => x.type === "exception" || x.type === "error" || x.type === "log-error").slice(0, 8);
out.landingRequests = requests.filter((u) => u.includes("/api/landing/")).length;
fs.writeFileSync(path.join(OUT, "landing-preview.json"), JSON.stringify(out, null, 1));
console.log(JSON.stringify(out, null, 1));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
