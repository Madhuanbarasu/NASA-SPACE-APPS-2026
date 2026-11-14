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

// LUNA-OPS 2.0 Phase 6: Communication previews and measurements (one headless browser; appended to the Phase 1 CDP
// harness, cdp_harness.txt). Usage: node comms_preview.mjs --base <url> --out <dir>
// The RF values and the relay orbit typed here are ILLUSTRATIVE demonstration inputs, not hardware or mission data.
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable"); await send("Network.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const tab = (name) => evaluate(`(() => { const b = [...document.querySelectorAll('button.tab')].find(e => e.textContent.trim() === ${JSON.stringify(name)}); if (b) b.click(); return !!b; })()`);
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return false; const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
const setSelect = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return false; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
const size = (w, h) => send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
const top0 = () => evaluate("document.querySelector('.main')?.scrollTo(0, 0); window.scrollTo(0, 0); true");
const scrollTo = (sel) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (e) e.scrollIntoView({ block: 'start' }); return !!e; })()`);
const clickText = (sel, text) => evaluate(`(() => { const b = [...document.querySelectorAll(${JSON.stringify(sel)})].find(e => e.textContent.trim() === ${JSON.stringify(text)}); if (b) b.click(); return !!b; })()`);
const hscroll = () => evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth");
const text = (sel) => evaluate(`document.querySelector(${JSON.stringify(sel)})?.textContent || ''`);
const out = { views: {} };
const LINK = { power: "20", gt: "20", ltx: "1", gr: "60", lrx: "1", ts: "50", lother: "3", freqMHz: "8450", bwkHz: "2000", rbkbps: "1000", ebn0: "2.5" };
const UP = { power: "5", gt: "3", ltx: "1", gr: "20", lrx: "1", ts: "400", lother: "2", freqMHz: "2250", rbkbps: "1000", ebn0: "2.5" };
const DOWN = { power: "50", gt: "30", ltx: "1", gr: "60", lrx: "1", ts: "50", lother: "3", freqMHz: "8450", rbkbps: "1000", ebn0: "2.5" };
const fillLink = async (prefix, vals) => { for (const [k, v] of Object.entries(vals)) await setValue(`#${prefix}-${k}`, v); };

await size(1440, 900);
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
await evaluate("try { localStorage.removeItem('luna-ops.params-docked.v1'); sessionStorage.clear(); } catch (e) {} true");
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447");
await evaluate(`(() => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  for (const [id, v] of [['#start', '2026-12-13T00:00'], ['#end', '2026-12-20T00:00']]) { const e = document.querySelector(id); set.call(e, v); e.dispatchEvent(new Event('input', { bubbles: true })); } return true; })()`);
await waitFor("/covers this point/.test([...document.querySelectorAll('#coord-hint, .explorer .hint[aria-live]')].map(e => e.textContent).join(' '))", 60000, "coverage");
out.tabs = await evaluate("[...document.querySelectorAll('button.tab')].map(b => b.textContent.trim())");
out.topbarOverflow1440 = await evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth");
await tab("Comms"); await waitFor("document.querySelector('.comms')", 30000, "comms view"); await sleep(500);
await shot("01-desktop-comms-before-analysis", null);
const t0 = Date.now();
await evaluate("document.querySelector('.comms-run')?.click(); true");
await waitFor("document.querySelector('.comms-timeline svg')", 300000, "simulation");
out.firstSimulationMs = Date.now() - t0;
await sleep(1200); await top0(); await shot("02-desktop-comms-direct-geometry", null);
out.engineLabels = await evaluate("[...document.querySelectorAll('.comms .mission-badges .status-badge')].map(b => b.textContent)");
out.directRfBefore = await text(".comms .metrics .metric:nth-of-type(8) dd");
// direct link budget (illustrative values)
await scrollTo("#comms-link"); await fillLink("cl-direct", LINK); await sleep(2200);
out.directBudget = await evaluate("[...document.querySelectorAll('.comms-breakdown table')].slice(0,1).map(t => [...t.querySelectorAll('tbody tr')].map(r => r.textContent.replace(/\\s+/g, ' ').trim()))[0]");
out.directStatus = await text(".comms-linkstatus");
await scrollTo("#comms-link"); await sleep(300); await shot("03-desktop-link-budget-direct", null);
// an invalid value is reported and not used
await setValue("#cl-direct-rbkbps", "0"); await sleep(1800);
out.invalidRate = { status: await text(".comms-linkstatus"), problems: await text(".comms-breakdown ul.bad") };
await shot("04-desktop-link-budget-invalid", null);
await setValue("#cl-direct-rbkbps", "1000"); await sleep(1500);
// hypothetical relay H1 (apoapsis over the lunar south; illustrative)
await scrollTo("#comms-relay");
await evaluate("document.querySelector('.comms-toggle input').click(); true"); await sleep(400);
for (const [k, v] of [["name", "H1 illustrative"], ["a", "6000"], ["e", "0.6"], ["i", "60"], ["raan", "0"], ["argp", "90"], ["m0", "0"], ["step", "60"]]) await setValue(`#cr-${k}`, v);
await setSelect("#cr-frame", "LME_EPOCH");
await waitFor("document.querySelector('section[aria-labelledby=comms-relay] table')", 120000, "relay"); await sleep(1500);
out.relayTable = await evaluate("[...document.querySelectorAll('#comms-relay ~ * table tbody tr, section[aria-labelledby=comms-relay] table tbody tr')].map(r => r.textContent.replace(/\\s+/g, ' ').trim())");
await scrollTo("#comms-relay"); await sleep(300); await shot("05-desktop-relay", null);
// relay link budgets
await clickText(".comms-linktabs button", "Lander to relay"); await sleep(300); await fillLink("cl-up", UP);
await clickText(".comms-linktabs button", "Relay to Earth"); await sleep(300); await fillLink("cl-down", DOWN); await sleep(2500);
out.relayDownStatus = await text(".comms-linkstatus");
await clickText(".comms-linktabs button", "Lander to relay"); await sleep(500);
out.relayUpStatus = await text(".comms-linkstatus");
await scrollTo("#comms-link"); await sleep(300); await shot("06-desktop-link-budget-uplink", null);
// timeline with everything
await scrollTo("#comms-timeline"); await sleep(400); await shot("07-desktop-timeline", null);
out.timelineRows = await evaluate("[...document.querySelectorAll('.comms-timeline .ct-label')].map(t => t.textContent)");
// cursor
await evaluate(`(() => { const r = document.querySelector('#comms-cursor'); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(r, String(Math.floor(r.max * 0.6))); r.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
await sleep(500);
out.directAtCursor = await evaluate("[...document.querySelectorAll('section[aria-labelledby=comms-direct] .metric')].map(m => m.textContent.replace(/\\s+/g, ' ').trim())");
await scrollTo("#comms-direct"); await sleep(300); await shot("08-desktop-direct-cursor", null);
// store and forward + comparison
await setValue("#cd-vol", "20000"); await setValue("#cd-rate", "1000"); await setSelect("#cd-path", "any_rf"); await sleep(2200);
out.dtn = await evaluate("[...document.querySelectorAll('section[aria-labelledby=comms-dtn] .metric')].map(m => m.textContent.replace(/\\s+/g, ' ').trim())");
out.comparison = await evaluate("[...document.querySelectorAll('.comms-cmp tbody tr')].map(r => r.textContent.replace(/\\s+/g, ' ').trim())");
await scrollTo("#comms-compare"); await sleep(300); await shot("09-desktop-comparison-dtn", null);
await scrollTo("#comms-provenance"); await sleep(300); await shot("10-desktop-provenance", null);
out.provenance = (await text(".comms .landing-prov")).slice(0, 700);
// mission dashboard: candidate card block and the Communication action
await tab("Mission"); await waitFor("document.querySelector('.mission-strip')", 30000, "mission"); await sleep(700);
await clickText(".mission .quiet-button", "Add the selected site"); await sleep(800);
await scrollTo("section[aria-labelledby=mission-candidates]"); await sleep(400);
out.mission = { commsBlock: await evaluate("[...document.querySelectorAll('.cand-landing')].map(e => e.textContent).join(' || ')"),
  integrity: await evaluate("/score|probabilit|recommend|rank|best site/i.test([...document.querySelectorAll('.mission-candidates, .mission-card h2, .mission-locator')].map(e => e.textContent).join(' '))"),
  nestedLi: await evaluate("document.querySelectorAll('.mission-candidates li li').length"), h2: await evaluate("document.querySelectorAll('.mission h2').length") };
await shot("11-desktop-mission-candidate-comms", null);
await evaluate("(() => { const b = [...document.querySelectorAll('.mission-candidates button')].find(e => e.textContent.trim() === 'Communication'); b?.click(); return !!b; })()");
await waitFor("document.querySelector('.comms-timeline svg')", 60000, "comms again"); await sleep(1500);
out.returnInputs = await evaluate("['#cr-a', '#cr-argp', '#cd-vol'].map(s => document.querySelector(s)?.value).join(' / ')");
// widths
for (const [w, h, kind] of [[1920, 1000, "wide"], [1024, 768, "tablet"], [390, 844, "phone"], [320, 640, "phone320"]]) {
  await size(w, h); await sleep(1200); await top0(); await sleep(300);
  await shot(`12-${kind}-comms-top`, null);
  await scrollTo("#comms-timeline"); await sleep(500); await shot(`13-${kind}-comms-timeline`, null);
  await scrollTo("#comms-link"); await sleep(300); await shot(`14-${kind}-comms-link`, null);
  out.views[kind] = { hscroll: await hscroll(), overflowPx: await evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth"),
    timelineW: await evaluate("Math.round(document.querySelector('.comms-timeline svg')?.getBoundingClientRect().width || 0)") };
}
out.consoleErrors = consoleMsgs.filter((x) => x.type === "exception" || x.type === "error" || x.type === "log-error").slice(0, 8);
out.commsRequests = requests.filter((u) => u.includes("/api/comms/")).length;
fs.writeFileSync(path.join(OUT, "comms-preview.json"), JSON.stringify(out, null, 1));
console.log(JSON.stringify(out, null, 1));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
