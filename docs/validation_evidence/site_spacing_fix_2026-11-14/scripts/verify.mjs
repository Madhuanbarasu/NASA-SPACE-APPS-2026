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

// Verification (after the CSS change): Site result "Events and intervals" and "Sunlight" sections at 1920/1440/1024/390/320
// px, for two results: A = 85.3305 S, 285.2104 E, 13-20 Nov 2026 (has rise/set events) and B = Site01, same window (no events).
// Per width: blank space under each column, section padding, event-list scroll, intervals expand/collapse, overflow,
// clipping, overlap; screenshots. One browser.
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
const size = (w, h) => send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
await size(1440, 900);
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
await evaluate("document.querySelector('#tab-site').click(); true");

const MEASURE = `(() => {
  const B = (e) => e.getBoundingClientRect().bottom + scrollY;
  const contentBottom = (e) => Math.max(B(e) - e.getBoundingClientRect().height, ...[...e.querySelectorAll('*')].filter(x => x.getClientRects().length && getComputedStyle(x).visibility !== 'hidden').map(B));
  const padB = (e) => parseFloat(getComputedStyle(e).paddingBottom) + parseFloat(getComputedStyle(e).borderBottomWidth);
  const out = {};
  const tl = document.querySelector('#result-timeline'), grid = tl.querySelector('.timeline-grid');
  const tw = grid.querySelector('.timeline-wrap'), ev = grid.querySelector('.event-list-wrap, .event-empty');
  const list = grid.querySelector('.event-list');
  const twoCol = tw.getBoundingClientRect().top === ev.getBoundingClientRect().top;
  out.timeline = { twoCol, sectionSlack: Math.round(B(tl) - padB(tl) - contentBottom(tl)),
    gridBottom: Math.round(B(grid)), timelineContentBottom: Math.round(contentBottom(tw)), timelineH: Math.round(tw.getBoundingClientRect().height), eventColBottom: Math.round(B(ev)),
    blankUnderTimeline: Math.round(B(grid) - contentBottom(tw)), blankUnderEvents: Math.round(B(grid) - B(ev)),
    events: list ? list.children.length : 0, listVisibleH: list ? Math.round(list.clientHeight) : null, listScrollH: list ? list.scrollHeight : null };
  const sun = document.querySelector('#result-visibility'), bg = sun.querySelector('.body-grid');
  const st = bg.querySelector('.body-stats'), ch = bg.querySelector('.vis-chart');
  const stTwo = st.getBoundingClientRect().top === ch.getBoundingClientRect().top;
  out.sun = { twoCol: stTwo, sectionSlack: Math.round(B(sun) - padB(sun) - contentBottom(sun)), gridBottom: Math.round(B(bg)),
    statsCardBottom: Math.round(B(st)), statsContentBottom: Math.round(contentBottom(st) + padB(st)), chartContentBottom: Math.round(contentBottom(ch)),
    blankUnderChart: Math.round(B(bg) - contentBottom(ch)), blankInsideStats: Math.round(B(st) - (contentBottom(st) + padB(st))),
    statsH: Math.round(st.getBoundingClientRect().height), chartColH: Math.round(ch.getBoundingClientRect().height),
    clippedLabels: [...st.querySelectorAll('.metric dt, .metric dd')].filter(x => x.scrollWidth > x.clientWidth + 1).length };
  const vw = document.documentElement.clientWidth;
  const inScroller = (e) => { let p = e.parentElement; while (p && p !== document.body) { const s = getComputedStyle(p); if (/(auto|scroll|hidden)/.test(s.overflowX) && p.scrollWidth > p.clientWidth + 1) return true; p = p.parentElement; } return false; };
  const scope = [tl, sun];
  out.hscroll = document.documentElement.scrollWidth > vw;
  out.outside = scope.flatMap(s => [...s.querySelectorAll('*')]).filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.right > vw + 1 && !inScroller(e); }).length;
  out.clipped = scope.flatMap(s => [...s.querySelectorAll('button, h2, h3, .chip, .status-badge')]).filter(e => e.getBoundingClientRect().width > 0 && e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflow !== 'visible').length;
  return out; })()`;

const snapSection = async (name, id) => {
  await evaluate(`document.getElementById('${id}').scrollIntoView({ block: 'start' }); true`); await sleep(500);
  const { data } = await send("Page.captureScreenshot", { format: "png" });
  fs.writeFileSync(path.join(OUT, "screenshots", `${name}.png`), Buffer.from(data, "base64"));
};
const results = [];
for (const [tag, lat, lon] of [["A-events", "-85.3305", "285.2104"], ["B-site01", "-89.463163", "222.510447"]]) {
  await size(1440, 900); await sleep(500);
  if (await evaluate("!!document.querySelector('.workspace-result')")) { await evaluate("[...document.querySelectorAll('button')].find(b => /Back to the Moon explorer/.test(b.textContent))?.click(); true"); await sleep(800); }
  await setValue("#lat", lat); await setValue("#lon", lon); await setValue("#start", "2026-11-13T00:00"); await setValue("#end", "2026-11-20T00:00");
  await waitFor("!document.querySelector('.sidebar .run-button').disabled", 60000, "analyse");
  await evaluate("document.querySelector('.sidebar .run-button').click(); true");
  await waitFor("document.querySelector('.workspace-result') && document.querySelector('#result-timeline')", 900000, "analysis " + tag); await sleep(1500);
  for (const [w, h] of [[1920, 1080], [1440, 900], [1024, 768], [390, 844], [320, 640]]) {
    await size(w, h); await sleep(1200);
    const m = await evaluate(MEASURE);
    // intervals: expand, measure, collapse, measure
    await evaluate("document.querySelector('#result-timeline .toggle-intervals').click(); true"); await sleep(600);
    const open = await evaluate(MEASURE);
    await snapSection(`after-${tag}-${w}-timeline-intervals-open`, "result-timeline");
    await evaluate("document.querySelector('#result-timeline .toggle-intervals').click(); true"); await sleep(600);
    const closed = await evaluate(MEASURE);
    await snapSection(`after-${tag}-${w}-timeline`, "result-timeline");
    await snapSection(`after-${tag}-${w}-sunlight`, "result-visibility");
    const t = m.timeline, s = m.sun;
    const TOL = 2;   // px
    const tlOk = t.sectionSlack <= TOL && (!t.twoCol || (t.events === 0 ? true : (Math.abs(t.blankUnderTimeline) <= TOL && Math.abs(t.blankUnderEvents) <= TOL && t.listVisibleH >= 100)))
      && (!t.twoCol || t.events === 0 || t.blankUnderTimeline <= TOL) ;
    // positions move when the screenshots scroll the page, so the toggle is judged on sizes: opening must grow the
    // timeline column (and, in two columns, keep both columns level); closing must restore the list height
    const toggleOk = open.timeline.timelineH > m.timeline.timelineH && Math.abs(closed.timeline.timelineH - m.timeline.timelineH) <= 1
      && (!open.timeline.twoCol || Math.abs(open.timeline.blankUnderTimeline) <= TOL)
      && (closed.timeline.listVisibleH === m.timeline.listVisibleH);
    const sunOk = s.sectionSlack <= TOL && (!s.twoCol || (s.blankUnderChart <= TOL && s.blankInsideStats <= 30)) && s.clippedLabels === 0;
    const layoutOk = !m.hscroll && m.outside === 0 && m.clipped === 0;
    const ok = tlOk && toggleOk && sunOk && layoutOk;
    results.push({ result: tag, width: w, timeline: t, timelineIntervalsOpen: open.timeline, timelineIntervalsClosed: closed.timeline, sun: s,
      hscroll: m.hscroll, outside: m.outside, clipped: m.clipped, checks: { tlOk, toggleOk, sunOk, layoutOk }, verdict: ok ? "Pass" : "Fail" });
    console.log(`${ok ? "PASS" : "FAIL"} ${tag} ${w}: timeline ${JSON.stringify({ two: t.twoCol, ev: t.events, slack: t.sectionSlack, underTl: t.blankUnderTimeline, underEv: t.blankUnderEvents, listH: t.listVisibleH })} toggle ${toggleOk} sun ${JSON.stringify({ two: s.twoCol, slack: s.sectionSlack, underChart: s.blankUnderChart, insideStats: s.blankInsideStats, statsH: s.statsH, chartH: s.chartColH, clipped: s.clippedLabels })} layout ${JSON.stringify({ h: m.hscroll, o: m.outside, c: m.clipped })}`);
  }
}
const out = { results, console: consoleMsgs.filter((x) => /error|exception/.test(x.type)) };
out.summary = { pass: results.filter((r) => r.verdict === "Pass").length, total: results.length, consoleErrors: out.console.length };
fs.writeFileSync(path.join(OUT, "verify.json"), JSON.stringify(out, null, 1));
console.log(JSON.stringify(out.summary));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
