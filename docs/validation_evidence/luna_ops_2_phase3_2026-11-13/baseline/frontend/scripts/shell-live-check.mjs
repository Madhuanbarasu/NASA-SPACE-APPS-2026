#!/usr/bin/env node
// LUNA-OPS 2.0 Phase 1: live check of the responsive shell in a real browser (Chrome/Edge headless through the DevTools
// Protocol, Node's built-in WebSocket; no packages). Needs the app running.
//
//   node scripts/shell-live-check.mjs --base http://127.0.0.1:8000 --out <dir>
//
// Wide screens: tabs in the command bar (WAI-ARIA keyboard), the Mission Parameters panel docked, collapsible, the
// choice remembered, the status line kept for screen readers. Tablet: compact views menu (open, choose, Down/Escape,
// focus return) and the parameters drawer (closed by default, focus in, fields usable, Escape / outside press / close
// button). Phone: the command bar wraps inside the screen. Every view at 1440, 1024, 768, 390 and 320 px without
// sideways scrolling; no console errors. Results in <out>/shell-check.json, screenshots in <out>/screenshots/.
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const BASE = arg("--base", "http://127.0.0.1:8765");
const OUT = path.resolve(arg("--out", "shell-check"));
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

const checks = [];
const check = (name, ok, detail) => { checks.push({ name, ok: !!ok, detail }); console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail !== undefined ? "  " + JSON.stringify(detail).slice(0, 500) : ""}`); };
const report = { base: BASE, browser: BROWSER, started: new Date().toISOString() };
await send("Runtime.enable"); await send("Log.enable"); await send("Page.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const size = (w, h) => send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
const load = async () => { await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(1200); };
const vis = (sel) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return false; const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; })()`);
const active = () => evaluate("document.activeElement?.id || document.activeElement?.className || document.activeElement?.tagName");
const panelShown = () => evaluate("(() => { const p = document.querySelector('.sidebar-panel'); return !!p && !p.hidden; })()");
const mainW = () => evaluate("Math.round(document.querySelector('.main').getBoundingClientRect().width)");

// ---- 1. wide screens (1440): tabs, docked and collapsible parameters
await size(1440, 900);
await load();
await evaluate("try { localStorage.removeItem('luna-ops.params-docked.v1'); } catch (e) {} true"); await load();
const w0 = { tabs: await vis(".tabs"), navToggle: await vis(".nav-toggle"), panel: await panelShown(), mainW: await mainW(), clock: await vis(".utc-clock") };
check("1440 px: tabs in the bar, no compact menu, parameters docked and open, UTC clock shown", w0.tabs && !w0.navToggle && w0.panel && w0.clock, w0);
await evaluate("document.querySelector('#tab-site').focus(); true"); await press("ArrowRight");
const kb = await evaluate("({ focus: document.activeElement.id, stops: [...document.querySelectorAll('button.tab')].filter(b => b.tabIndex === 0).length })");
check("tabs keyboard: ArrowRight from Site selects Compare; the list stays one tab stop", kb.focus === "tab-compare" && kb.stops === 1, kb);
await evaluate("document.querySelector('#tab-site').click(); true"); await sleep(400);
await evaluate("document.querySelector('.params-toggle').click(); true"); await sleep(500);
const w1 = { panel: await panelShown(), expanded: await evaluate("document.querySelector('.params-toggle').getAttribute('aria-expanded')"), mainW: await mainW(),
  status: await evaluate("!!document.querySelector('.sidebar [role=status]')"), latInDom: await evaluate("!!document.querySelector('#lat')") };
check("collapse: the parameters toggle hides the panel and the workspace takes the full width; the status line stays for screen readers",
  !w1.panel && w1.expanded === "false" && w1.mainW > w0.mainW + 300 && w1.status && w1.latInDom, { before: w0.mainW, after: w1 });
await load();
const w2 = { panel: await panelShown(), mainW: await mainW() };
check("collapse is remembered in this browser after a reload", !w2.panel && w2.mainW === w1.mainW, w2);
await evaluate("document.querySelector('.params-toggle').click(); true"); await sleep(500);
check("expand: the toggle brings the docked panel back", await panelShown() && (await mainW()) === w0.mainW);
await shot("shell-1440-docked", null);

// ---- 2. tablet (1024): compact navigation menu and parameters drawer
await size(1024, 768); await load();
const t0 = { tabs: await vis(".tabs"), navToggle: await vis(".nav-toggle"), panel: await panelShown(), hscroll: await evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth") };
check("1024 px: compact menu button instead of the tab strip; parameters drawer closed; no sideways scrolling", !t0.tabs && t0.navToggle && !t0.panel && !t0.hscroll, t0);
await evaluate("document.querySelector('#nav-toggle').click(); true"); await sleep(400);
const m1 = { open: await vis(".tabs"), expanded: await evaluate("document.querySelector('#nav-toggle').getAttribute('aria-expanded')") };
await shot("shell-1024-menu-open", null);
await evaluate("document.querySelector('#tab-guide').click(); true"); await sleep(500);
const m2 = { open: await vis(".tabs"), tab: await evaluate("document.querySelector('button.tab[aria-selected=true]').textContent"), label: await evaluate("document.querySelector('#nav-toggle').textContent") };
check("menu: opens; choosing a view selects it, closes the menu and shows the view's name on the button", m1.open && m1.expanded === "true" && !m2.open && m2.tab === "Guide" && /Guide/.test(m2.label), { m1, m2 });
await evaluate("document.querySelector('#nav-toggle').click(); true"); await sleep(300);
await evaluate("document.querySelector('#tab-guide').focus(); true"); await press("ArrowDown");
const m3 = await evaluate("document.querySelector('button.tab[aria-selected=true]').textContent");
await send("Input.dispatchKeyEvent", { type: "rawKeyDown", key: "Escape", code: "Escape", windowsVirtualKeyCode: 27 });
await send("Input.dispatchKeyEvent", { type: "keyUp", key: "Escape", code: "Escape", windowsVirtualKeyCode: 27 }); await sleep(300);
const m4 = { open: await vis(".tabs"), focus: await active() };
check("menu keyboard: Down moves through the views; Escape closes the menu and returns focus to the menu button", m4.open === false && m4.focus === "nav-toggle", { m3, m4 });
await evaluate("document.querySelector('.params-toggle').click(); true"); await sleep(500);
const d1 = { panel: await panelShown(), focus: await active(), scrim: await vis(".scrim"), sidebarLeft: await evaluate("Math.round(document.querySelector('.sidebar').getBoundingClientRect().left)") };
await shot("shell-1024-drawer-open", null);
check("drawer: opens over the workspace with a scrim; focus moves to its close button", d1.panel && d1.scrim && d1.focus === "params-close" && d1.sidebarLeft === 0, d1);
await evaluate(`(() => { const e = document.querySelector('#lat'); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, '-89.9'); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
await sleep(300);
const typed = await evaluate("document.querySelector('#lat').value");
await send("Input.dispatchKeyEvent", { type: "rawKeyDown", key: "Escape", code: "Escape", windowsVirtualKeyCode: 27 });
await send("Input.dispatchKeyEvent", { type: "keyUp", key: "Escape", code: "Escape", windowsVirtualKeyCode: 27 }); await sleep(500);
const d2 = { panel: await panelShown(), focus: await active() };
check("drawer: its fields work; Escape closes it and returns focus to the parameters toggle; the value is kept", typed === "-89.9" && !d2.panel && /params-toggle/.test(d2.focus)
  && (await evaluate("document.querySelector('#lat').value")) === "-89.9", { typed, d2 });
await evaluate("document.querySelector('.params-toggle').click(); true"); await sleep(400);
await mouseClick(900, 500); await sleep(400);
const d3 = await panelShown();
await evaluate("document.querySelector('.params-toggle').click(); true"); await sleep(400);
await evaluate("document.querySelector('#params-close').click(); true"); await sleep(400);
const d4 = await panelShown();
check("drawer: a press outside it and its close button both close it", !d3 && !d4, { outside: d3, close: d4 });

// ---- 3. phone (390, 320): the bar wraps; no sideways scrolling on any view
const widths = {};
for (const [w, h] of [[1440, 900], [1024, 768], [768, 1024], [390, 844], [320, 640]]) {
  await size(w, h); await load();
  for (const t of ["mission", "site", "compare", "data", "guide"]) {
    await evaluate(`document.querySelector('#tab-${t}').click(); true`); await sleep(700);
    widths[`${w}:${t}`] = await evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth");
  }
  if (w <= 390) {
    const bar = await evaluate("(() => { const b = document.querySelector('.topbar').getBoundingClientRect(); const items = [...document.querySelectorAll('.topbar > *, .topbar-right > *')].filter(e => getComputedStyle(e).display !== 'none'); return { h: Math.round(b.height), allInside: items.every(e => { const r = e.getBoundingClientRect(); return r.right <= document.documentElement.clientWidth + 0.5 && r.left >= -0.5; }) }; })()");
    report[`bar${w}`] = bar;
    await evaluate("document.querySelector('#tab-site').click(); true"); await sleep(600);
    await shot(`shell-${w}-site`, null);
  }
}
check("no sideways scrolling on any view at 1440, 1024, 768, 390 and 320 px", Object.values(widths).every(Boolean), widths);
check("phone: every command-bar item stays inside the screen (the bar wraps onto two rows)", report.bar390?.allInside && report.bar320?.allInside, { bar390: report.bar390, bar320: report.bar320 });

const errors = consoleMsgs.filter((m) => m.type === "exception" || m.type === "error" || m.type === "log-error");
check("no page exceptions or console errors", errors.length === 0, errors.slice(0, 5));
report.checks = checks; report.finished = new Date().toISOString();
fs.writeFileSync(path.join(OUT, "shell-check.json"), JSON.stringify(report, null, 1));
const failed = checks.filter((c) => !c.ok).length;
console.log(`shell-live-check: ${checks.length - failed}/${checks.length} checks passed`);
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(failed ? 1 : 0);
