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

// Browser verification of the date-range correction and panel-azimuth normalisation (one cycle).
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable"); await send("Network.enable");
const posts = [];
ws.addEventListener("message", (m) => { const msg = JSON.parse(m.data);
  if (msg.method === "Network.requestWillBeSent" && /\/api\/analysis$/.test(msg.params.request.url))
    posts.push({ t: Date.now(), body: msg.params.request.postData ? JSON.parse(msg.params.request.postData) : null }); });
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const setInput = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
const setSelect = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
const shotVP = async (name) => { const { data } = await send("Page.captureScreenshot", { format: "png" }); fs.writeFileSync(path.join(OUT, "screenshots", `${name}.png`), Buffer.from(data, "base64")); return `screenshots/${name}.png`; };
const state = () => evaluate(`({ endInvalid: document.querySelector('#end').getAttribute('aria-invalid'), describedBy: document.querySelector('#end').getAttribute('aria-describedby'),
  hint: document.querySelector('#window-hint')?.textContent || null, sidebarAnalyseDisabled: document.querySelector('.sidebar .run-button').disabled,
  explorerAnalyseDisabled: document.querySelector('.explorer-run')?.disabled ?? null })`);
await send("Emulation.setDeviceMetricsOverride", { width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
await evaluate("document.querySelector('#tab-site').click(); true");
await setInput("#lat", "-89.463163"); await setInput("#lon", "222.510447"); await sleep(1500);
const out = { cases: [] };
for (const [name, a, b, expectValid] of [["valid 30-day window", "2026-11-13T00:00", "2026-12-13T00:00", true],
                                         ["equal start and end", "2026-11-13T00:00", "2026-11-13T00:00", false],
                                         ["reversed", "2026-12-13T00:00", "2026-11-13T00:00", false],
                                         ["reversed by one minute", "2026-11-13T00:01", "2026-11-13T00:00", false],
                                         ["one minute (boundary, valid)", "2026-11-13T00:00", "2026-11-13T00:01", true]]) {
  await setInput("#start", a); await setInput("#end", b); await sleep(1200);
  const n0 = posts.length;
  const st = await state();
  // try to start an analysis anyway (clicking a disabled button does nothing; the store guard covers other callers)
  if (!expectValid) { await evaluate("document.querySelector('.sidebar .run-button').click(); document.querySelector('.explorer-run')?.click(); true"); await sleep(1500); }
  const sent = posts.length - n0;
  const shot = expectValid ? null : await shotVP(`window-${name.replace(/[^a-z0-9]+/gi, "-")}`);
  const ok = expectValid ? (st.endInvalid === null && st.hint === null && st.sidebarAnalyseDisabled === false)
                         : (st.endInvalid === "true" && /end must be after the start/i.test(st.hint || "") && st.sidebarAnalyseDisabled === true
                            && st.explorerAnalyseDisabled !== false && sent === 0);
  out.cases.push({ name, start: a, end: b, expectValid, ...st, analysis_requests_sent: sent, evidence: shot, result: ok ? "Pass" : "Fail" });
  console.log(JSON.stringify(out.cases.at(-1)));
}
// panel azimuth 400 -> 40: hint, request, stored result, displayed value
await setInput("#start", "2026-11-13T00:00"); await setInput("#end", "2026-11-14T00:00");
await setSelect("#panel", "fixed_vertical"); await sleep(300); await setInput("#paz", "400"); await sleep(500);
const azHint = await evaluate("[...document.querySelectorAll('.sidebar .hint')].map(e => e.textContent).find(t => /modulo 360/.test(t)) || null");
await waitFor("!document.querySelector('.sidebar .run-button').disabled", 60000, "Analyse enabled");
const before = await evaluate(`[...document.querySelectorAll('a[href*="/api/results/"]')].map(a => a.getAttribute('href')).find(Boolean) || null`);
const n0 = posts.length;
await evaluate("document.querySelector('.sidebar .run-button').click(); true");
await waitFor(`(() => { const h = [...document.querySelectorAll('a[href*="/api/results/"]')].map(a => a.getAttribute('href')).find(Boolean); return h && h !== ${JSON.stringify(before)} && document.querySelector('.figures'); })()`, 600000, "analysis");
await sleep(1200);
const rid = await evaluate(`[...document.querySelectorAll('a[href*="/api/results/"]')].map(a => a.getAttribute('href').match(/results\\/([0-9a-f]+)/)?.[1]).find(Boolean)`);
const r = await evaluate(`fetch('/api/results/${rid}').then(x => x.json())`);
const ui = await evaluate("({ big: document.querySelector('.figures .figure.is-power .big')?.textContent, rule: document.querySelector('.figures .figure.is-power .rule')?.textContent })");
const shotAz = await shotVP("panel-azimuth-400-used-as-40");
const sentAz = posts.slice(n0).map((p) => p.body?.panel_az_deg);
const azOk = /used as 40/.test(azHint || "") && sentAz.length === 1 && sentAz[0] === 40 && r.provenance.parameters.panel.azimuth_deg === 40
  && Math.abs(parseFloat(ui.big) - r.summary.power.fixed_vertical.mean) <= 0.0005;
out.azimuth = { hint: azHint, request_panel_az_deg: sentAz, result_id: rid, stored_panel: r.provenance.parameters.panel,
  backend_fixed_vertical_mean: r.summary.power.fixed_vertical.mean, displayed: ui, evidence: shotAz, result: azOk ? "Pass" : "Fail" };
console.log(JSON.stringify(out.azimuth));
await setSelect("#panel", "vertical_tracking"); await setInput("#paz", "0");
out.console = consoleMsgs.filter((x) => /error|exception/.test(x.type));
fs.writeFileSync(path.join(OUT, "browser-results.json"), JSON.stringify(out, null, 1));
console.log(JSON.stringify({ summary: [...out.cases.map((c) => [c.name, c.result]), ["azimuth 400 -> 40", out.azimuth.result]], console: out.console.length }));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
