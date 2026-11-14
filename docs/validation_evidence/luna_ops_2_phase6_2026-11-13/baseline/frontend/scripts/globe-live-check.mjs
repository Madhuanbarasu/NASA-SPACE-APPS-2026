#!/usr/bin/env node
// Phase 5 live check of the 3D Moon globe in a real browser (Chrome/Edge headless through the DevTools Protocol, Node's
// built-in WebSocket; no packages). Needs the app running (e.g. `python start.py --no-browser --port 8765`).
//
//   node scripts/globe-live-check.mjs --base http://127.0.0.1:8765 --out <dir> [--browser <path>]
//
// Checks (results in <out>/globe-check.json, screenshots in <out>/screenshots/; exit 1 if any check fails):
//  lazy loading     no globe/three.js chunk and no imagery requested before the globe is opened
//  rendering        the globe chunk, the shared three.js chunk and both images load; imagery state "ready"; no errors
//  coordinates      the centre readout and "select centre" agree; a click on the canvas centre selects the centre
//                   location; points right of / above the centre are east / north of it (east right, north up)
//  orientation      with even light, Mare Crisium (dark mare, ~17N 59E) renders darker than its mirror point (17N 301E)
//  rotation         a mouse drag changes the view and the centre longitude
//  zoom             the mouse wheel and the + key enlarge the lunar disc on screen
//  keyboard         arrow keys turn the view by 10 deg, Enter selects the centre, Home returns to the nearside
//  viewpoints       North/South Pole buttons centre the view at +-89.9 deg latitude
//  toggles          grid and even-light buttons toggle aria-pressed and change the image
//  accessibility    no unnamed buttons in the globe pane; the canvas host is focusable with a name
//  responsive       at 390 x 844 the page does not scroll sideways and the toolbar stays inside the stage
//  cleanup          5 map/globe switches leave no canvas behind, no WebGL context warnings, and no heap growth trend
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
// the app shows the globe's selection in the site explorer card (MoonGlobe selectionPanel=false since prompt 2)
const selectedText = () => evaluate(`(document.querySelector('.globe-selected strong') || document.querySelector('.explorer-coords strong'))?.textContent || ''`);
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
const check = (name, ok, detail) => { checks.push({ name, ok: !!ok, detail }); console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail !== undefined ? "  " + JSON.stringify(detail) : ""}`); };
const report = { base: BASE, browser: BROWSER, started: new Date().toISOString() };

await send("Runtime.enable"); await send("Log.enable"); await send("Network.enable"); await send("Page.enable");
const finish = (extra = {}) => { Object.assign(report, extra, { checks, console: consoleMsgs, finished: new Date().toISOString() });
  fs.writeFileSync(path.join(OUT, NO_WEBGL ? "globe-check-no-webgl.json" : "globe-check.json"), JSON.stringify(report, null, 1));
  const failed = checks.filter((c) => !c.ok).length; console.log(`globe-live-check${NO_WEBGL ? " --no-webgl" : ""}: ${checks.length - failed}/${checks.length} checks passed`);
  ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* browser may still hold files */ }
  process.exit(failed ? 1 : 0); };
if (NO_WEBGL) {
  await send("Page.navigate", { url: BASE + "/" });
  await waitFor("document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')", 60000, "status");
  await clickBtn(".view-switch button", "3D Moon globe");
  await waitFor("document.querySelector('.globe-message')", 30000, "fallback message");
  await sleep(500);
  const msg = await evaluate("document.querySelector('.globe-message').textContent");
  await evaluate("document.querySelector('.globe-stage').scrollIntoView({ block: 'center' }); true"); await sleep(300);
  await shot("20-fallback-no-webgl");
  check("fallback: without WebGL the globe shows the no-WebGL message and creates no canvas", /WebGL is not available/.test(msg)
    && await evaluate("document.querySelectorAll('.globe-host canvas').length") === 0, msg);
  await clickBtn(".view-switch button", "South polar map"); await sleep(1500);
  check("fallback: the south polar map still works without WebGL", await evaluate("!!document.querySelector('.map-host')"));
  finish();
}
await send("Network.setCacheDisabled", { cacheDisabled: true });
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url: BASE + "/" });
await waitFor("document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')", 60000, "status");
await sleep(2500);
report.version = await evaluate("navigator.userAgent");
const before = requests.slice();
check("lazy: no globe chunk, three.js chunk or imagery before opening the globe",
  !before.some((u) => /MoonGlobe-|OrbitControls-|\/moon\//.test(u)), before.filter((u) => /assets\/|moon/.test(u)).map((u) => u.replace(BASE, "")));
await shot("01-welcome-map-default");
check("map is the default view", await evaluate(`document.querySelector('.view-switch button[aria-pressed=true]')?.textContent`) !== null
  && await evaluate(`!!document.querySelector('.map-host')`));

// open the globe
await clickBtn(".view-switch button", "3D Moon globe");
await waitFor("document.querySelector('.globe-host canvas')", 30000, "globe canvas");
await waitFor("!document.querySelector('.globe-message')", 30000, "imagery ready");
await sleep(1200);
// pointer input only reaches what is inside the viewport: bring the whole stage into view first
await evaluate("document.querySelector('.globe-stage').scrollIntoView({ block: 'center' }); true");
await sleep(500);
check("layout: the globe stage fits in the viewport", await evaluate(`(() => { const r = document.querySelector('.globe-stage').getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight; })()`));
const after = requests.slice(before.length);
check("rendering: globe chunk, shared three.js chunk and both images requested on demand",
  ["MoonGlobe-", "OrbitControls-", "/moon/lroc_color_2k.jpg", "/moon/ldem_3_8bit.jpg"].every((k) => after.some((u) => u.includes(k))),
  after.filter((u) => /assets\/|moon/.test(u)).map((u) => u.replace(BASE, "")));
const st = await stageRect();
const cx = st.x + st.width / 2, cy = st.y + st.height / 2;
let b64 = await shot("02-globe-nearside", st);
const near0 = await pixelStats(b64);
check("rendering: lunar disc drawn (lit pixels in the stage)", near0.litFraction > 0.05, near0.litFraction);

// coordinates
check("coordinates: initial centre is the nearside (0, 0)", (await centreText()).includes("0.000° N, 0.000° E"), await centreText());
await clickBtn(".globe-nav button", "Select the location under the centre crosshair");
await sleep(300);
check("coordinates: 'select centre' gives the centre readout", await selectedText() === "0.000° N, 0.000° E", await selectedText());
await mouseClick(cx, cy);
const pc = parseLoc(await selectedText());
check("coordinates: click at the canvas centre selects ~(0, 0)", pc && Math.abs(pc.lat) < 0.3 && Math.abs(lonDiff(pc.lon, 0)) < 0.3, pc);
await mouseClick(cx + 120, cy);
const pr = parseLoc(await selectedText());
await mouseClick(cx, cy - 120);
const pu = parseLoc(await selectedText());
check("coordinates: right of centre is east, above centre is north", pr && pu && lonDiff(pr.lon, 0) > 1 && Math.abs(pr.lat) < 0.5 && pu.lat > 1 && Math.abs(lonDiff(pu.lon, 0)) < 0.5, { right: pr, up: pu });
// pixel-to-angle consistency: with vertical FOV 35 deg at the opening distance, compare the clicked offset with the exact
// sphere geometry. LUNA-OPS 2.0 Phase 2: the opening view frames the whole disc at 90 % of the stage height (92 % of its
// width on narrow stages), MoonGlobe fitDistance: d = sqrt(1 + t^2) / t with t = min(0.9, 0.92 w / h) tan(fov / 2).
const fov = 35 * Math.PI / 180;
const fitT = Math.min(0.9, 0.92 * st.width / st.height) * Math.tan(fov / 2), d = Math.sqrt(1 + fitT * fitT) / fitT;
// camera on the axis at distance d; a ray at angle a off the axis meets the unit sphere at central angle asin(d sin a) - a
const expectAngle = (px) => { const a = Math.atan(Math.tan(fov / 2) * (px / (st.height / 2))); return (Math.asin(d * Math.sin(a)) - a) * 180 / Math.PI; };
check("coordinates: picked longitude matches the exact ray-sphere geometry within 0.2 deg", pr && Math.abs(pr.lon - expectAngle(120)) < 0.2,
  { got: pr?.lon, expected: expectAngle(120) });
await shot("03-globe-selected-marker", st);

// orientation (rendered): dark maria vs their mirror points (highlands), even light, zoomed in, crosshair hidden.
// Mare Moscoviense tests east-west mirroring, Mare Imbrium tests north-south flipping (same pairs as the source-image check).
await clickBtn(".segmented-mini button", "Even light");
for (let i = 0; i < 3; i++) await clickBtn(".globe-nav button", "Zoom globe in");
await evaluate("document.querySelector('.globe-host').focus(); true");
const box = [st.width / 2 - 12, st.height / 2 - 12, st.width / 2 + 12, st.height / 2 + 12].map(Math.round);
const sample = async (name) => { await evaluate("document.querySelector('.globe-crosshair').style.visibility = 'hidden'; true"); await sleep(150);
  const b = await shot(name, st); await evaluate("document.querySelector('.globe-crosshair').style.visibility = ''; true");
  return { centre: parseLoc(await centreText()), mean: (await pixelStats(b, box)).boxMean }; };
const keys = async (k, n, shift = false) => { for (let i = 0; i < n; i++) await press(k, shift); };
await press("Home"); await keys("ArrowRight", 15); await keys("ArrowUp", 3); await press("ArrowLeft", true); await press("ArrowDown", true);
const mosc = await sample("04-even-light-mare-moscoviense-28N-148E");
await keys("ArrowRight", 32, true);                                         // 64 deg east: (28N, 212E), farside highlands
const moscM = await sample("05-even-light-mirror-28N-212E");
await press("Home"); await keys("ArrowLeft", 2); await keys("ArrowRight", 2, true); await keys("ArrowUp", 3); await press("ArrowUp", true);
const imb = await sample("05b-even-light-mare-imbrium-32N-344E");
await keys("ArrowDown", 32, true);                                          // 64 deg south: (32S, 344E), southern highlands
const imbM = await sample("05c-even-light-mirror-32S-344E");
check("orientation: Mare Moscoviense renders darker than its east-west mirror; Mare Imbrium darker than its north-south mirror",
  mosc.mean < moscM.mean && imb.mean < imbM.mean, { moscoviense: mosc, mirrorLon: moscM, imbrium: imb, mirrorLat: imbM });
await clickBtn(".segmented-mini button", "Even light");

// keyboard: Home, arrows, +, Enter
await press("Home");
check("keyboard: Home returns to the nearside", (await centreText()).includes("0.000° N, 0.000° E"), await centreText());
await press("ArrowRight");
const k1 = parseLoc(await centreText());
await press("ArrowUp");
const k2 = parseLoc(await centreText());
check("keyboard: ArrowRight turns 10 deg east, ArrowUp 10 deg north", k1 && k2 && Math.abs(lonDiff(k1.lon, 10)) < 1e-6 && Math.abs(k2.lat - 10) < 1e-6, { k1, k2 });
b64 = await shot("06-before-zoom", st);
const z0 = await pixelStats(b64);
await press("+"); await press("+");
b64 = await shot("07-after-plus-zoom", st);
const z1 = await pixelStats(b64);
check("zoom: + key enlarges the lunar disc", z1.litFraction > z0.litFraction * 1.1, { before: z0.litFraction, after: z1.litFraction });
await press("Enter");
check("keyboard: Enter selects the centre location", await selectedText() === (await centreText()).replace(/^Centre /, ""), { selected: await selectedText(), centre: await centreText() });

// mouse wheel zoom and drag rotation
await press("Home");
b64 = await shot("08-before-wheel", st); const w0 = await pixelStats(b64);
await send("Input.dispatchMouseEvent", { type: "mouseWheel", x: cx, y: cy, deltaX: 0, deltaY: -600 });
await sleep(500);
b64 = await shot("09-after-wheel", st); const w1 = await pixelStats(b64);
check("zoom: mouse wheel enlarges the lunar disc", w1.litFraction > w0.litFraction * 1.05, { before: w0.litFraction, after: w1.litFraction });
const r0 = parseLoc(await centreText());
const selBeforeDrag = await selectedText();
await send("Input.dispatchMouseEvent", { type: "mousePressed", x: cx, y: cy, button: "left", buttons: 1, clickCount: 1 });
for (let i = 1; i <= 10; i++) { await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: cx - 20 * i, y: cy, button: "left", buttons: 1 }); await sleep(30); }
await send("Input.dispatchMouseEvent", { type: "mouseReleased", x: cx - 200, y: cy, button: "left", buttons: 0, clickCount: 1 });
await sleep(400);
const r1 = parseLoc(await centreText());
b64 = await shot("10-after-drag", st);
check("rotation: dragging left turns the view east (centre longitude increases)", r0 && r1 && lonDiff(r1.lon, r0.lon) > 5, { before: r0, after: r1 });
check("rotation: a drag does not select (selection unchanged)", await selectedText() === selBeforeDrag, { before: selBeforeDrag, after: await selectedText() });

// viewpoints and toggles
await clickBtn(".segmented-mini button", "South Pole"); await sleep(1000);   // viewpoints fly (650 ms)
check("viewpoints: South Pole centres at 89.900 S", (await centreText()).includes("89.900° S"), await centreText());
await shot("11-south-pole", st);
await clickBtn(".segmented-mini button", "North Pole"); await sleep(1000);   // viewpoints fly (650 ms)
check("viewpoints: North Pole centres at 89.900 N", (await centreText()).includes("89.900° N"), await centreText());
await shot("12-north-pole", st);
await clickBtn(".segmented-mini button", "Farside"); await sleep(1000);   // viewpoints fly (650 ms)
check("viewpoints: Farside centres at (0, 180 E)", (await centreText()).includes("0.000° N, 180.000° E"), await centreText());
await shot("13-farside", st);
await clickBtn(".segmented-mini button", "Nearside"); await sleep(1000);   // viewpoints fly (650 ms)
b64 = await shot("14-grid-on", st); const g0 = await pixelStats(b64);
await clickBtn(".segmented-mini button", "Grid"); await sleep(300);
b64 = await shot("15-grid-off", st); const g1 = await pixelStats(b64);
const gridPressed = await evaluate(`[...document.querySelectorAll('.segmented-mini button')].find(b => b.textContent === 'Grid').getAttribute('aria-pressed')`);
check("toggles: grid button toggles aria-pressed and the image", gridPressed === "false" && g0.hash !== g1.hash, gridPressed);
await clickBtn(".segmented-mini button", "Grid");

// accessibility of the globe pane
const ax = await evaluate(`(() => { const pane = document.querySelector('.globe'); const btns = [...pane.querySelectorAll('button')];
  const unnamed = btns.filter(b => !(b.getAttribute('aria-label') || b.textContent.trim())).length;
  const small = btns.filter(b => { const r = b.getBoundingClientRect(); return r.width < 24 || r.height < 24; }).map(b => b.getAttribute('aria-label') || b.textContent);
  const host = pane.querySelector('.globe-host'); return { buttons: btns.length, unnamed, small, hostTabIndex: host.tabIndex, hostRole: host.getAttribute('role'), hostName: !!host.getAttribute('aria-label') }; })()`);
check("accessibility: every globe button named and >= 24 px; canvas host focusable and named", ax.unnamed === 0 && ax.small.length === 0 && ax.hostTabIndex === 0 && ax.hostName, ax);
const live = await evaluate(`(document.querySelector('.globe .sr-only[aria-live]') || document.querySelector('.explorer .sr-only[aria-live]'))?.textContent`);
check("accessibility: the selection is announced in a polite live region", /^Selected /.test(live || ""), live);

// responsive
await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
await sleep(1200);
await evaluate("document.querySelector('.globe-stage').scrollIntoView({ block: 'center' }); true");
await sleep(600);
const mob = await evaluate(`(() => { const s = document.querySelector('.globe-stage').getBoundingClientRect(); const t = document.querySelector('.globe-toolbar').getBoundingClientRect(); const g = document.querySelector('.globe').getBoundingClientRect();
  return { scrollW: document.documentElement.scrollWidth, clientW: document.documentElement.clientWidth, stageW: s.width, stageH: s.height, toolbarInside: t.right <= g.right + 1 && t.left >= g.left - 1, toolbarAboveStage: t.bottom <= s.top + 1, canvasW: document.querySelector('.globe-host canvas').getBoundingClientRect().width }; })()`);
await shot("16-mobile-390");
check("responsive: no sideways scroll at 390 px; toolbar inside the pane and above (not over) the globe; canvas fills the stage", mob.scrollW <= mob.clientW && mob.toolbarInside && mob.toolbarAboveStage && Math.abs(mob.canvasW - mob.stageW) < 2, mob);
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
await sleep(800);

// cleanup: map <-> globe cycles
await send("HeapProfiler.enable");
const heap = async () => { await send("HeapProfiler.collectGarbage"); await sleep(300); const m = await send("Performance.getMetrics"); return m.metrics.find((x) => x.name === "JSHeapUsedSize").value / 1048576; };
await send("Performance.enable");
const heaps = [];
const warnBefore = consoleMsgs.length;
for (let i = 0; i < 5; i++) {
  await clickBtn(".view-switch button", "South polar map"); await sleep(700);
  heaps.push(await heap());
  await clickBtn(".view-switch button", "3D Moon globe");
  await waitFor("document.querySelector('.globe-host canvas') && !document.querySelector('.globe-message')", 30000, "globe again");
  await sleep(500);
}
await clickBtn(".view-switch button", "South polar map"); await sleep(700);
heaps.push(await heap());
const canvasesLeft = await evaluate(`document.querySelectorAll('.globe-host canvas').length`);
const ctxWarnings = consoleMsgs.slice(warnBefore).filter((m) => /WebGL|context/i.test(m.text));
const growth = heaps[heaps.length - 1] - heaps[0];
check("cleanup: no globe canvas left after switching back; no WebGL context warnings over 5 cycles", canvasesLeft === 0 && ctxWarnings.length === 0, { canvasesLeft, ctxWarnings });
check("cleanup: no heap growth trend over 5 globe mount/unmount cycles (< 2 MB)", growth < 2, { heapsMB: heaps.map((h) => +h.toFixed(2)), growthMB: +growth.toFixed(2) });
await shot("17-back-to-map");

const errors = consoleMsgs.filter((m) => m.type === "exception" || m.type === "error" || m.type === "log-error");
check("no page exceptions or console errors", errors.length === 0, errors.slice(0, 5));

// fallbacks (after the error count, because blocked requests log network errors by design)
await send("Network.setBlockedURLs", { urls: ["*/moon/*"] });
await send("Page.navigate", { url: BASE + "/" });
await waitFor("document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')", 60000, "status");
await clickBtn(".view-switch button", "3D Moon globe");
await waitFor("document.querySelector('.globe .hint.bad')", 30000, "imagery error note");
await evaluate("document.querySelector('.globe-stage').scrollIntoView({ block: 'center' }); true"); await sleep(600);
b64 = await shot("18-fallback-imagery-blocked", await stageRect());
const fb = await pixelStats(b64);
check("fallback: blocked imagery shows a note and an untextured sphere (still rotatable)", fb.litFraction > 0.05
  && /imagery could not be loaded/.test(await evaluate("document.querySelector('.globe .hint.bad').textContent")), fb.litFraction);
await send("Network.setBlockedURLs", { urls: ["*MoonGlobe-*"] });
await send("Page.navigate", { url: BASE + "/" });
await waitFor("document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')", 60000, "status");
await clickBtn(".view-switch button", "3D Moon globe");
await sleep(2500);
const lazyMsg = await evaluate("document.querySelector('.pane .pane-empty')?.textContent || ''");
await shot("19-fallback-chunk-blocked");
check("fallback: a failed globe chunk shows the load-failed message instead of crashing the page",
  /could not be loaded/.test(lazyMsg) && await evaluate("!!document.querySelector('.topbar') && !!document.querySelector('.welcome')"), lazyMsg);
await clickBtn(".view-switch button", "South polar map"); await sleep(800);
check("fallback: switching back to the map after a failed globe works", await evaluate("!!document.querySelector('.map-host')"));
await send("Network.setBlockedURLs", { urls: [] });
finish();
