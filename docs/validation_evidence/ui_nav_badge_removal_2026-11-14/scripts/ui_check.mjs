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

// UI change check (2026-11-14): navigation without "Data and validation", no validation badges in Mission and Site,
// the Data view still opens at #data, and the responsive layout at 1920/1440/1024/390/320 px. One headless browser.
// Site01 7-day result (cached by earlier runs; requested again through the UI).
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
const size = (w, h) => send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
await size(1440, 900);
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
await evaluate("document.querySelector('#tab-site').click(); true");
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447"); await setValue("#start", "2026-11-13T00:00"); await setValue("#end", "2026-11-20T00:00");
await waitFor("!document.querySelector('.sidebar .run-button').disabled", 60000, "analyse");
await evaluate("document.querySelector('.sidebar .run-button').click(); true");
await waitFor("document.querySelector('.figures')", 600000, "analysis"); await sleep(1000);

const NAV = `(() => { const tabs = [...document.querySelectorAll('#primary-nav .tab')];
  const vis = tabs.filter(t => { const r = t.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
  return { tabs: tabs.map(t => t.textContent.trim()), visible: vis.length, hasDataTab: !!document.querySelector('#tab-data'),
    navText: document.querySelector('#primary-nav').textContent, toggleShown: getComputedStyle(document.querySelector('#nav-toggle')).display !== 'none' }; })()`;
const BADGES = `(() => { const m = document.querySelector('main'); const t = (m?.innerText || '');
  const q = (s) => m ? m.querySelectorAll(s).length : 0;
  return { statusBadges: q('.status-badge'), pendingBadges: q('.status-badge.is-pending'), labelChips: q('.label-row .chip'),
    figureLabels: q('.figure-labels'), missionBadges: q('.mission-badges'), candLabels: q('.cand-labels'),
    pendingValidationText: (t.match(/pending validation/gi) || []).length, pendingCountText: (t.match(/\\d+ validated, \\d+ pending/gi) || []).length }; })()`;
const MEASURE = `(() => {
  const vw = document.documentElement.clientWidth;
  const inScroller = (e) => { let p = e.parentElement; while (p && p !== document.body) { const s = getComputedStyle(p); if (/(auto|scroll|hidden)/.test(s.overflowX) && p.scrollWidth > p.clientWidth + 1) return true; p = p.parentElement; } return false; };
  const all = [...document.querySelectorAll('main *, .topbar *')].filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
  const outside = all.filter(e => e.getBoundingClientRect().right > vw + 1 && !inScroller(e)).slice(0, 5).map(e => e.tagName.toLowerCase() + '.' + (typeof e.className === 'string' ? e.className.split(' ')[0] : ''));
  const clipped = [...document.querySelectorAll('main button, .topbar button, main h1, main h2, main h3, .status-badge, .chip, .tab')]
    .filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflow !== 'visible'; })
    .slice(0, 5).map(e => e.tagName.toLowerCase() + ' "' + e.textContent.trim().slice(0, 40) + '"');
  const cards = [...document.querySelectorAll('main .landing-card, main .card, main section.panel, main .figure, main .mission-card, main .context-card')].map(e => e.getBoundingClientRect()).filter(r => r.width > 0);
  let overlaps = 0;
  for (let i = 0; i < cards.length; i++) for (let j = i + 1; j < cards.length; j++) { const a = cards[i], b = cards[j];
    if (a.left < b.right - 2 && b.left < a.right - 2 && a.top < b.bottom - 2 && b.top < a.bottom - 2) overlaps++; }
  // empty boxes left behind: visible elements with a border or background, no text and no media, at least 24 px high
  const empty = [...document.querySelectorAll('main .result-labels, main .mission-card > div, main .figure-head, main .cand-analysis')]
    .filter(e => { const r = e.getBoundingClientRect(); return r.height >= 24 && r.width > 0 && !e.innerText.trim() && !e.querySelector('svg,canvas,img,table,button,input'); }).length;
  const mainText = (document.querySelector('main')?.innerText || '').trim().length;
  return { hscroll: document.documentElement.scrollWidth > vw, outside, clipped, overlaps, cards: cards.length, emptyBoxes: empty, mainText }; })()`;

const out = { combos: [], nav: [], data: [] };
for (const [w, h] of [[1920, 1080], [1440, 900], [1024, 768], [390, 844], [320, 640]]) {
  await size(w, h); await sleep(1200);
  const nav = await evaluate(NAV);
  let menu = null;
  if (nav.toggleShown) {   // compact menu: open it, list the items, close it with Escape
    await evaluate("document.querySelector('#nav-toggle').click(); true"); await sleep(500);
    menu = await evaluate(NAV);
    const { data } = await send("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(path.join(OUT, "screenshots", `menu-${w}.png`), Buffer.from(data, "base64"));
    await evaluate("document.querySelector('#nav-toggle').click(); true"); await sleep(400);
  }
  const navOk = nav.tabs.length === 6 && !nav.hasDataTab && !/Data and validation/.test(nav.navText) && (!menu || (menu.visible === 6 && !/Data and validation/.test(menu.navText)));
  out.nav.push({ width: w, ...nav, menu, result: navOk ? "Pass" : "Fail" });
  console.log(`${navOk ? "PASS" : "FAIL"} nav ${w}: ${nav.tabs.join(" | ")}${menu ? ` (menu items visible ${menu.visible})` : ""}`);
  for (const tab of ["mission", "site", "landing", "comms", "compare", "guide"]) {
    await evaluate(`document.querySelector('#tab-${tab}').click(); true`); await sleep(1300);
    await evaluate("document.querySelector('.main')?.scrollTo(0, 0); window.scrollTo(0, 0); true");
    const m = await evaluate(MEASURE); const b = await evaluate(BADGES);
    const layoutOk = !m.hscroll && m.outside.length === 0 && m.clipped.length === 0 && m.overlaps === 0 && m.emptyBoxes === 0 && m.mainText > 20;
    const scoped = tab === "mission" || tab === "site";
    const badgesOk = !scoped || ((tab === "mission" ? b.statusBadges === 0 : true) && b.pendingBadges === 0 && b.labelChips === 0 && b.figureLabels === 0 && b.missionBadges === 0 && b.candLabels === 0
      && b.pendingCountText === 0);
    const name = `ui-${w}-${tab}`;
    const { data } = await send("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(path.join(OUT, "screenshots", `${name}.png`), Buffer.from(data, "base64"));
    out.combos.push({ width: w, tab, layout: m, badges: b, screenshot: `screenshots/${name}.png`, result: layoutOk && badgesOk ? "Pass" : "Fail" });
    console.log(`${layoutOk && badgesOk ? "PASS" : "FAIL"} ${w} ${tab} layout ${JSON.stringify(m).slice(0, 150)} badges ${JSON.stringify(b)}`);
  }
  // the unlisted Data and validation view opens from the address bar (#data); the tab list stays keyboard-reachable
  await evaluate("location.hash = ''; true"); await sleep(200); await evaluate("location.hash = '#data'; true"); await sleep(1500);
  const d = await evaluate(`(() => ({ title: document.querySelector('#view-panel h1, #view-panel h2')?.textContent.trim(),
    panelLabel: document.querySelector('#view-panel').getAttribute('aria-label'), labelledby: document.querySelector('#view-panel').getAttribute('aria-labelledby'),
    reportRows: document.querySelectorAll('#view-panel table tr').length, focusableTabs: [...document.querySelectorAll('#primary-nav .tab')].filter(t => t.tabIndex === 0).length }))()`);
  const dm = await evaluate(MEASURE);
  const { data } = await send("Page.captureScreenshot", { format: "png" });
  fs.writeFileSync(path.join(OUT, "screenshots", `ui-${w}-data-hash.png`), Buffer.from(data, "base64"));
  const dOk = /Data and validation/i.test(d.title || "") && d.panelLabel && !d.labelledby && d.reportRows > 0 && d.focusableTabs === 1 && !dm.hscroll && dm.outside.length === 0;
  out.data.push({ width: w, ...d, layout: dm, result: dOk ? "Pass" : "Fail" });
  console.log(`${dOk ? "PASS" : "FAIL"} ${w} #data ${JSON.stringify(d)}`);
  await evaluate("location.hash = ''; document.querySelector('#tab-site').click(); true"); await sleep(600);
}
out.console = consoleMsgs.filter((x) => /error|exception/.test(x.type));
const all = [...out.nav, ...out.combos, ...out.data];
out.summary = { pass: all.filter((c) => c.result === "Pass").length, total: all.length, consoleErrors: out.console.length };
fs.writeFileSync(path.join(OUT, "ui_check.json"), JSON.stringify(out, null, 1));
console.log(JSON.stringify(out.summary));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
