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

// Communication tab UI check: blank space below each card, the RF link-direction buttons, the tab label, overlap and
// horizontal overflow at 1440, 1024 and 390 px. One headless browser; appended to the Phase 1 CDP harness.
// Usage: node comms_ui.mjs --base <url> --out <dir> --label before|after
// The RF values and relay orbit typed here are ILLUSTRATIVE demonstration inputs (Phase 6 SOURCES.md), not hardware data.
const LABEL = arg("--label", "run");
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return false; const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
const setSelect = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return false; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
const size = (w, h) => send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
const top0 = () => evaluate("document.querySelector('.main')?.scrollTo(0, 0); window.scrollTo(0, 0); true");
const scrollTo = (sel) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (e) e.scrollIntoView({ block: 'start' }); return !!e; })()`);
const LINK = { power: "20", gt: "20", ltx: "1", gr: "60", lrx: "1", ts: "50", lother: "3", freqMHz: "8450", rbkbps: "1000", ebn0: "2.5" };
const UP = { power: "5", gt: "3", ltx: "1", gr: "20", lrx: "1", ts: "400", lother: "2", freqMHz: "2250", rbkbps: "1000", ebn0: "2.5" };
const DOWN = { power: "50", gt: "30", ltx: "1", gr: "60", lrx: "1", ts: "50", lother: "3", freqMHz: "8450", rbkbps: "1000", ebn0: "2.5" };
const measure = () => evaluate(`(() => {
  const cards = [...document.querySelectorAll('.comms .landing-card')];
  const r = (e) => e.getBoundingClientRect();
  const res = {};
  for (const c of cards) {
    const id = (c.getAttribute('aria-labelledby') || 'card').replace('comms-', ''); const b = r(c);
    const below = cards.map(r).filter(o => o.top >= b.bottom - 1 && o.left < b.right - 1 && o.right > b.left + 1).map(o => o.top);
    const content = [...c.children].reduce((m, k) => Math.max(m, r(k).bottom), b.top);
    res[id] = { h: Math.round(b.height), left: Math.round(b.left), w: Math.round(b.width),
      blankBelow: below.length ? Math.round(Math.min(...below) - b.bottom) : null, emptyInside: Math.round(b.bottom - content) };
  }
  const overlaps = [];
  for (let i = 0; i < cards.length; i++) for (let j = i + 1; j < cards.length; j++) {
    const a = r(cards[i]), b = r(cards[j]);
    if (a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1) overlaps.push(i + '-' + j);
  }
  return { cards: res, overlaps, hscroll: document.documentElement.scrollWidth > document.documentElement.clientWidth }; })()`);
// RF direction buttons: state of each, which link the form and breakdown show after a click
const tabs = () => evaluate(`[...document.querySelectorAll('.comms-linktabs button')].map(b => ({ text: b.textContent.trim(), pressed: b.getAttribute('aria-pressed'), disabled: b.disabled }))`);
const clickTab = (t) => evaluate(`(() => { const b = [...document.querySelectorAll('.comms-linktabs button')].find(e => e.textContent.trim() === ${JSON.stringify(t)}); if (!b) return 'missing'; b.click(); return b.disabled ? 'disabled' : 'clicked'; })()`);
const linkState = () => evaluate(`({ pressed: [...document.querySelectorAll('.comms-linktabs button')].find(b => b.getAttribute('aria-pressed') === 'true')?.textContent.trim(),
  formId: document.querySelector('section[aria-labelledby=comms-link] .comms-linkform input')?.id,
  power: document.querySelector('section[aria-labelledby=comms-link] .comms-linkform input')?.value,
  status: document.querySelector('section[aria-labelledby=comms-link] .comms-linkstatus')?.textContent || '',
  note: [...document.querySelectorAll('section[aria-labelledby=comms-link] .comms-relay-needed')].map(e => e.textContent).join(' '),
  marginRow: [...document.querySelectorAll('section[aria-labelledby=comms-link] table.comms-budget tbody tr')].find(r => /Link margin/.test(r.textContent))?.textContent.replace(/\\s+/g, ' ').trim() || '' })`);
const fillLink = async (prefix, vals) => { for (const [k, v] of Object.entries(vals)) await setValue(`#${prefix}-${k}`, v); };
const out = { label: LABEL, layout: {}, buttons: {} };

await size(1440, 900);
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
await evaluate("try { localStorage.removeItem('luna-ops.params-docked.v1'); sessionStorage.clear(); } catch (e) {} true");
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
out.tabLabels = await evaluate("[...document.querySelectorAll('button.tab')].map(b => b.textContent.trim())");
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447");
await evaluate(`(() => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  for (const [id, v] of [['#start', '2026-12-13T00:00'], ['#end', '2026-12-20T00:00']]) { const e = document.querySelector(id); set.call(e, v); e.dispatchEvent(new Event('input', { bubbles: true })); } return true; })()`);
await waitFor("/covers this point/.test([...document.querySelectorAll('#coord-hint, .explorer .hint[aria-live]')].map(e => e.textContent).join(' '))", 60000, "coverage");
await evaluate("document.getElementById('tab-comms').click(); true");
await waitFor("document.querySelector('.comms')", 30000, "comms view"); await sleep(400);
out.activeTab = await evaluate("document.querySelector('button.tab[aria-selected=true]')?.textContent.trim()");
await evaluate("document.querySelector('.comms-run')?.click(); true");
await waitFor("document.querySelector('.comms-timeline svg')", 300000, "simulation"); await sleep(1500);

// ---- RF direction buttons with the relay OFF (the reported case)
out.buttons.relayOff_initial = await tabs();
out.buttons.relayOff_clickUp = await clickTab("Lander to relay"); await sleep(400);
out.buttons.relayOff_afterUp = await linkState();
out.buttons.relayOff_clickDown = await clickTab("Relay to Earth"); await sleep(400);
out.buttons.relayOff_afterDown = await linkState();
await clickTab("Direct to Earth"); await sleep(300);
await fillLink("cl-direct", LINK); await sleep(2200);
out.buttons.direct = await linkState();
await scrollTo("#comms-link"); await sleep(300); await shot(`${LABEL}-desktop-rf-direct`, null);
await clickTab("Lander to relay"); await sleep(500);
out.buttons.relayOff_up_after_direct = await linkState();
await scrollTo("#comms-link"); await sleep(300); await shot(`${LABEL}-desktop-rf-up-relay-off`, null);
await clickTab("Direct to Earth"); await sleep(300);
// layout with the relay off
for (const [w, h, kind] of [[1440, 900, "desktop"], [1024, 768, "tablet"], [390, 844, "phone"]]) {
  await size(w, h); await sleep(900); await top0();
  out.layout[`relayOff-${kind}`] = await measure();
  await shot(`${LABEL}-${kind}-top-relay-off`, null);
}
await size(1440, 900); await sleep(600);
// ---- relay ON
await scrollTo("#comms-relay");
await evaluate("document.querySelector('.comms-toggle input').click(); true"); await sleep(400);
for (const [k, v] of [["name", "H1 illustrative"], ["a", "6000"], ["e", "0.6"], ["i", "60"], ["raan", "0"], ["argp", "90"], ["m0", "0"], ["step", "60"]]) await setValue(`#cr-${k}`, v);
await setSelect("#cr-frame", "LME_EPOCH");
await waitFor("document.querySelector('section[aria-labelledby=comms-relay] table')", 120000, "relay"); await sleep(1200);
out.buttons.relayOn_initial = await tabs();
await clickTab("Lander to relay"); await sleep(400); await fillLink("cl-up", UP);
await clickTab("Relay to Earth"); await sleep(400); await fillLink("cl-down", DOWN); await sleep(2500);
// switch repeatedly: up, down, direct, up, down
const seq = [];
for (const t of ["Lander to relay", "Relay to Earth", "Direct to Earth", "Lander to relay", "Relay to Earth", "Lander to relay"]) {
  const r = await clickTab(t); await sleep(500); seq.push({ click: t, result: r, ...(await linkState()) });
}
out.buttons.relayOn_switching = seq;
await scrollTo("#comms-link"); await sleep(300); await shot(`${LABEL}-desktop-rf-up-relay-on`, null);
await clickTab("Relay to Earth"); await sleep(500); await scrollTo("#comms-link"); await sleep(300); await shot(`${LABEL}-desktop-rf-down-relay-on`, null);
for (const [w, h, kind] of [[1440, 900, "desktop"], [1024, 768, "tablet"], [390, 844, "phone"]]) {
  await size(w, h); await sleep(1200); await top0();
  out.layout[`relayOn-${kind}`] = await measure();
  await shot(`${LABEL}-${kind}-top-relay-on`, null);
  await scrollTo("#comms-link"); await sleep(400); await shot(`${LABEL}-${kind}-link-relay`, null);
}
// top bar at the checked widths and the compact menu
out.topbar = {};
for (const w of [1920, 1600, 1599, 1440, 1024, 390]) {
  await size(w, 900); await sleep(400);
  out.topbar[w] = await evaluate("({ overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth, inline: getComputedStyle(document.querySelector('.tabs')).display !== 'none', label: document.getElementById('tab-comms')?.textContent.trim(), selected: document.getElementById('tab-comms')?.getAttribute('aria-selected'), toggle: document.querySelector('.nav-toggle')?.textContent.trim() })");
}
await size(1920, 1000); await sleep(400); await top0(); await shot(`${LABEL}-1920-topbar`, { x: 0, y: 0, width: 1920, height: 70 });
out.consoleErrors = consoleMsgs.filter((x) => x.type === "exception" || x.type === "error" || x.type === "log-error").slice(0, 5);
fs.writeFileSync(path.join(OUT, `comms-ui-${LABEL}.json`), JSON.stringify(out, null, 1));
console.log(JSON.stringify(out, null, 1));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
