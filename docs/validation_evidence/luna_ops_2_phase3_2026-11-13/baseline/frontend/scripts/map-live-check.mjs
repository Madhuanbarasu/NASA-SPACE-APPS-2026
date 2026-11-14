#!/usr/bin/env node
// South polar map: live check in a real browser (Chrome/Edge headless through the DevTools Protocol, Node's built-in
// WebSocket; proj4 from the frontend's own node_modules; no packages installed). Needs the app running.
//
//   node scripts/map-live-check.mjs --base http://127.0.0.1:8000 --out <dir>
//
// Checks: loading note; every tile of the default view comes from the server within 10 s (backend tile fix) and no region
// inside the 60 S circle stays empty (canvas pixels sampled); the frontend fallback is kept: a tile held back by browser
// request interception is cancelled at 10 s and drawn from its finer tiles, with a note, and is composed at once after a
// reload; click-to-coordinate accuracy against an
// independent proj4 inverse (inside 60-90 S) and the outside-the-map note (north of 60 S); site selection, local terrain
// and analysis from the map's site; zoom and pan; the view stays on the data square; a typed unsupported location;
// failed tiles and unavailable tile metadata; the 390 px layout; console errors. Results in <out>/map-check.json,
// screenshots in <out>/screenshots/; exit 1 if any check fails.
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const BASE = arg("--base", "http://127.0.0.1:8765");
const OUT = path.resolve(arg("--out", "map-check"));
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





const requireFE = createRequire(path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "package.json"));
const proj4 = requireFE("proj4");
const SPS = "+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +k=1 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs";
const checks = [];
const check = (name, ok, detail) => { checks.push({ name, ok: !!ok, detail }); console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail !== undefined ? "  " + JSON.stringify(detail).slice(0, 500) : ""}`); };
const report = { base: BASE, browser: BROWSER, started: new Date().toISOString() };
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const proto = e instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
  const set = Object.getOwnPropertyDescriptor(proto, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event(e instanceof HTMLSelectElement ? 'change' : 'input', { bubbles: true })); return true; })()`);
// tile requests seen by the browser (status, duration, failure)
const tiles = new Map(); const t0 = Date.now();
ws.addEventListener("message", (m) => {
  const msg = JSON.parse(m.data);
  if (msg.method === "Network.requestWillBeSent" && /\/api\/tiles\/\d+\/\d+\/\d+\.png/.test(msg.params.request.url))
    tiles.set(msg.params.requestId, { url: msg.params.request.url.replace(/^.*\/api\/tiles\//, "").replace(".png", ""), start: Date.now() - t0 });
  if (msg.method === "Network.loadingFinished" && tiles.has(msg.params.requestId)) { const r = tiles.get(msg.params.requestId); r.done = true; r.end = Date.now() - t0; }
  if (msg.method === "Network.responseReceived" && tiles.has(msg.params.requestId)) tiles.get(msg.params.requestId).status = msg.params.response.status;
  if (msg.method === "Network.loadingFailed" && tiles.has(msg.params.requestId)) { const r = tiles.get(msg.params.requestId); r.failed = msg.params.errorText; r.end = Date.now() - t0; }
});
const tileList = () => [...tiles.values()];
await send("Runtime.enable"); await send("Log.enable"); await send("Network.enable"); await send("Page.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status");
await evaluate("try { sessionStorage.clear(); } catch (e) {} true");
tiles.clear();
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status");
await waitFor("document.querySelector('.map-host canvas')", 30000, "map canvas");
const note = () => evaluate("document.querySelector('.pane-note')?.textContent || ''");
const hostRect = () => evaluate("(() => { const e = document.querySelector('.map-host'); e.scrollIntoView({ block: 'center' }); const r = e.getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height }; })()");
const clip = async () => { const r = await hostRect(); await sleep(300); const q = await hostRect(); return { x: q.x, y: q.y - 0, width: q.w, height: q.h + 34 }; };
const meta = await evaluate("fetch('/api/tiles/meta').then(r => r.json())");
await evaluate("try { localStorage.removeItem('luna-ops.map.slow-tiles.v1'); } catch (e) {} true");
await send("Page.reload"); await waitFor(READY, 60000, "status"); await waitFor("document.querySelector('.map-host canvas')", 30000, "map canvas");
tiles.clear();
await send("Page.reload"); await waitFor(READY, 60000, "status"); await waitFor("document.querySelector('.map-host canvas')", 30000, "map canvas");
const coverRes = (h) => Math.min((meta.extent[2] - meta.extent[0]) / h.w, (meta.extent[3] - meta.extent[1]) / h.h);
// share of sampled points inside the 60 S circle (and inside the pane) that the tile layer leaves transparent
const transparentShare = (res) => evaluate(`(() => {
  const host = document.querySelector('.map-host'); const c = host.querySelector('.ol-layer canvas');
  const g = c.getContext('2d', { willReadFrequently: true }); const d = g.getImageData(0, 0, c.width, c.height).data;
  const k = c.width / host.clientWidth, R = ${meta.extent[2]} / ${res} * k * 0.97; let n = 0, empty = 0;
  for (let y = 4; y < c.height - 4; y += 6) for (let x = 4; x < c.width - 4; x += 6) {
    const dx = x - c.width / 2, dy = y - c.height / 2; if (dx * dx + dy * dy > R * R) continue;
    n++; if (d[4 * (y * c.width + x) + 3] < 200) empty++; }
  return { n, empty, share: n ? empty / n : null }; })()`);

// ---- 1. loading state; the server renders every tile of the default view promptly (backend tile fix)
await sleep(1500);
const early = await note();
check("loading state: while tiles are in flight the note says how many are loading", /Loading \d+ terrain tiles?\./.test(early), early);
let h1 = await hostRect(); await sleep(300); h1 = await hostRect();
const res1 = coverRes(h1);
let fill = null;
for (let i = 0; i < 40; i++) { await sleep(2000); fill = await transparentShare(res1); if (fill.share !== null && fill.share < 0.01 && !/Loading \d+/.test(await note())) break; }
const n1 = await note();
const zStart = Math.min(...tileList().map((r) => Number(r.url.split("/")[0])));
const z1 = tileList().filter((r) => r.url.startsWith(zStart + "/"));
report.freshTiles = tileList();
const slowest = Math.max(...tileList().map((r) => (r.end ?? 1e9) - r.start));
check("fresh map: every tile of the default view comes from the server (200) within 10 s, so none needs composing (backend tile fix)",
  z1.length >= 2 && tileList().every((r) => r.status === 200 && r.end - r.start < 10000), { zStart, slowestMs: slowest, tiles: tileList().map((r) => [r.url, r.status, r.end - r.start]) });
check("no empty region: inside the 60 S circle the whole visible map is drawn (sampled points left transparent < 1 %)", fill.share !== null && fill.share < 0.01, fill);
check("message: no 'drawn from the next finer zoom' note when the server renders the tiles itself", !/drawn from the next finer zoom/.test(n1), n1);
report.fillFresh = fill;
await shot("01-fresh-map-1440", await clip());

// ---- 2. the frontend fallback is kept: a tile held back for more than 10 s (browser request interception, no backend
//         involvement) is cancelled and drawn from its finer tiles; after a reload it is composed at once
const HELD = `${zStart}/${z1.map((r) => r.url).find((u) => u)?.split("/")[1] ?? 0}/${z1[0]?.url.split("/")[2] ?? 0}`;
const heldUrl = z1.map((r) => r.url).sort()[0];
const held = [];
const onPaused = (m) => { const msg = JSON.parse(m.data); if (msg.method === "Fetch.requestPaused") held.push(msg.params.requestId); };
ws.addEventListener("message", onPaused);
await evaluate("try { localStorage.removeItem('luna-ops.map.slow-tiles.v1'); } catch (e) {} true");
await send("Network.setCacheDisabled", { cacheDisabled: true });
await send("Fetch.enable", { patterns: [{ urlPattern: `*/api/tiles/${heldUrl}.png`, requestStage: "Request" }] });
tiles.clear();
await send("Page.reload"); await waitFor(READY, 60000, "status"); await waitFor("document.querySelector('.map-host canvas')", 30000, "canvas");
let fillH = null;
for (let i = 0; i < 30; i++) { await sleep(1500); fillH = await transparentShare(res1); if (fillH.share !== null && fillH.share < 0.01 && !/Loading \d+/.test(await note())) break; }
const nH = await note();
const heldReq = tileList().filter((r) => r.url === heldUrl);
const [hz, hx, hy] = heldUrl.split("/").map(Number);
const kids = tileList().filter((r) => [`${hz + 1}/${2 * hx}/${2 * hy}`, `${hz + 1}/${2 * hx + 1}/${2 * hy}`, `${hz + 1}/${2 * hx}/${2 * hy + 1}`, `${hz + 1}/${2 * hx + 1}/${2 * hy + 1}`].includes(r.url));
check("fallback kept: a tile held back for more than 10 s is cancelled at about 10 s and its four finer tiles are requested",
  held.length >= 1 && heldReq.length === 1 && heldReq[0].failed && heldReq[0].end - heldReq[0].start >= 9000 && heldReq[0].end - heldReq[0].start <= 13000 && kids.length === 4 && kids.every((r) => r.status === 200),
  { heldUrl, held: held.length, heldReq, kids: kids.map((r) => [r.url, r.status]) });
check("fallback kept: the area is drawn from the finer tiles (no empty region) and the note says so",
  fillH.share !== null && fillH.share < 0.01 && /drawn from the next finer zoom/.test(nH) && /same LOLA hillshade, downscaled/.test(nH), { fillH, nH });
await shot("01a-fallback-composed-1440", await clip());
for (const id of held) { try { await send("Fetch.failRequest", { requestId: id, errorReason: "Aborted" }); } catch { /* already cancelled */ } }
await send("Fetch.disable");
ws.removeEventListener("message", onPaused);
tiles.clear();
await send("Page.reload"); await waitFor(READY, 60000, "status"); await waitFor("document.querySelector('.map-host canvas')", 30000, "canvas");
let fill2 = null;
for (let i = 0; i < 20; i++) { await sleep(1500); fill2 = await transparentShare(res1); if (fill2.share !== null && fill2.share < 0.01 && !/Loading \d+/.test(await note())) break; }
const again = tileList().filter((r) => r.url === heldUrl);
check("fallback memory: after a reload the remembered tile is composed at once without being requested again",
  again.length === 0 && fill2.share < 0.01 && /drawn from the next finer zoom/.test(await note()), { again, fill2 });
report.fallback = { heldUrl, fillH, fill2 };
// leave no fallback memory behind for the rest of the check
await evaluate("try { localStorage.removeItem('luna-ops.map.slow-tiles.v1'); } catch (e) {} true");
await send("Network.setCacheDisabled", { cacheDisabled: false });
await send("Page.reload"); await waitFor(READY, 60000, "status"); await waitFor("document.querySelector('.map-host canvas')", 30000, "canvas"); await sleep(3000);

// ---- 2b. every zoom level from the default view: no empty region inside the 60 S circle
const waitTiles = async () => { for (let i = 0; i < 40; i++) { await sleep(1000); if (!/Loading \d+/.test(await note())) return; } };
const zoomFill = [];
for (let k = 0; k <= 4; k++) {
  if (k) { await evaluate("document.querySelector('.ol-zoom-in').click(); true"); await sleep(600); }
  await waitTiles(); await sleep(800);
  const f = await transparentShare(res1 / 2 ** k);
  zoomFill.push({ zoomSteps: k, ...f, note: (await note()).replace(/^.*coordinates\. ?/, "") });
  if (k === 2) await shot("01b-zoomed-in-2-1440", await clip());
}
report.zoomFill = zoomFill;
check("every zoom level (default view and 4 zoom-in steps): no empty region inside the 60 S circle (transparent < 1 %)",
  zoomFill.every((z) => z.share !== null && z.share < 0.01), zoomFill);

// ---- 2c. resizing: the view keeps filling the pane after the window is resized
const sizes = [[1100, 800], [1920, 1080], [1440, 900]];
const resizeFill = [];
for (const [w, hh] of sizes) {
  await send("Emulation.setDeviceMetricsOverride", { width: w, height: hh, deviceScaleFactor: 1, mobile: false });
  await send("Page.reload"); await waitFor(READY, 60000, "status"); await waitFor("document.querySelector('.map-host canvas')", 30000, "canvas");
  await sleep(1500); await waitTiles();
  let hr = await hostRect(); await sleep(300); hr = await hostRect();
  // live resize as well: shrink and grow the window without reloading
  await send("Emulation.setDeviceMetricsOverride", { width: w + 200, height: hh, deviceScaleFactor: 1, mobile: false }); await sleep(1500); await waitTiles();
  let h2 = await hostRect(); await sleep(300); h2 = await hostRect();
  const live = await evaluate(`(() => { const host = document.querySelector('.map-host'); const c = host.querySelector('.ol-layer canvas');
    const d = c.getContext('2d', { willReadFrequently: true }).getImageData(0, 0, c.width, c.height).data; const k = c.width / host.clientWidth;
    const a = (x, y) => d[4 * (Math.round(y * k) * c.width + Math.round(x * k)) + 3];
    return { leftMid: a(host.clientWidth * 0.12, host.clientHeight / 2), rightMid: a(host.clientWidth * 0.88, host.clientHeight / 2) }; })()`);
  await send("Emulation.setDeviceMetricsOverride", { width: w, height: hh, deviceScaleFactor: 1, mobile: false }); await sleep(1200);
  const f = await transparentShare(coverRes(hr));
  resizeFill.push({ size: [w, hh], pane: [Math.round(hr.w), Math.round(hr.h)], afterLiveResize: live, ...f });
}
report.resizeFill = resizeFill;
await shot("01c-after-resize-1440", await clip());
check("resizing (1100 x 800, 1920 x 1080, 1440 x 900, plus a live widening of each): the map fills the pane, no empty region",
  resizeFill.every((r) => r.share !== null && r.share < 0.01 && r.afterLiveResize.leftMid > 200 && r.afterLiveResize.rightMid > 200), resizeFill);

// ---- 3. coordinates: clicks against an independent proj4 inverse of the fitted view
const clicks = [];
for (const [dx, dy] of [[60, 40], [-120, 0], [0, 0], [30, 30], [345, 140], [-345, 140]]) {
  await send("Page.reload"); await waitFor(READY, 60000, "status"); await waitFor("document.querySelector('.map-host canvas')", 30000, "canvas"); await sleep(2500);
  await hostRect(); await sleep(300); const h = await hostRect();
  const res = coverRes(h);
  await mouseClick(h.x + h.w / 2 + dx, h.y + h.h / 2 + dy); await sleep(600);
  const f = await evaluate("({ lat: document.querySelector('#lat').value, lon: document.querySelector('#lon').value, explorer: document.querySelector('.explorer-coords')?.textContent || '' })");
  const [lo, la] = proj4(SPS, "+proj=longlat +R=1737400 +no_defs", [dx * res, -dy * res]);
  const exp = { lat: Number(la.toFixed(6)), lon: Number((((lo % 360) + 360) % 360).toFixed(6)) };
  const tol = (res / 1737400) * 180 / Math.PI;
  const nt = await note();
  const ok = la > -60 ? f.lat === "" && /outside the south polar map/.test(nt)
    : Math.abs(Number(f.lat) - exp.lat) <= tol && Math.abs(((Number(f.lon) - exp.lon + 540) % 360) - 180) * Math.cos(exp.lat * Math.PI / 180) <= tol && !/outside the south polar map/.test(nt);
  clicks.push({ dx, dy, got: f, expected: exp, northOf60: la > -60, ok });
}
report.clicks = clicks;
check("coordinates: every click inside 60-90 S gives the proj4 inverse of the click point (within one display pixel) in the sidebar and explorer",
  clicks.filter((c) => !c.northOf60).every((c) => c.ok), clicks.filter((c) => !c.northOf60));
check("unsupported: a click north of 60 S sets no site and the note says why (instead of nothing happening)",
  clicks.filter((c) => c.northOf60).length >= 2 && clicks.filter((c) => c.northOf60).every((c) => c.ok), clicks.filter((c) => c.northOf60));
await shot("02-outside-60S-note-1440", await clip());

// ---- 4. selection -> marker -> local terrain -> analysis
tiles.clear();
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447"); await setValue("#start", "2026-11-14T00:00"); await setValue("#end", "2026-11-21T00:00");
await waitFor("/covers this point/.test(document.querySelector('.explorer .hint[aria-live]')?.textContent || '')", 30000, "coverage");
for (let i = 0; i < 30; i++) { await sleep(1000); if (tileList().length && tileList().every((r) => r.done || r.failed)) break; }
const n4 = await note();
const z6 = tileList().filter((r) => r.url.startsWith("6/"));
check("site selection: the map zooms to the site and its tiles load (zoom 6, all 200); no stalled message for this view",
  z6.length > 0 && z6.every((r) => r.status === 200) && !/not rendered by the server in time/.test(n4), { z6: z6.map((r) => [r.url, r.status, r.failed]).filter((x) => x[1] !== 200), n4 });
await shot("03-site01-1440", await clip());
await clickBtn(".explorer button", "Inspect local terrain");
await waitFor("document.querySelector('.terrain-stats')", 60000, "terrain preview"); await sleep(1000);
check("navigation: Inspect local terrain opens the registered-terrain preview for the map's site",
  (await evaluate("document.querySelector('.pane-head h3').textContent")).includes("89.463° S, 222.510° E"));
await clickBtn(".view-switch button", "South polar map"); await sleep(1500);
await evaluate("document.querySelector('.explorer-run').click(); true");
await waitFor("document.querySelector('a[href$=\"/result.json\"]')", 900000, "analysis"); await sleep(4000);
const resMap = await evaluate("(() => { const p = document.getElementById('result-terrain').querySelector('.map-host canvas'); return !!p; })()");
check("navigation: Analyse runs the analysis for the map's site; the result view's map renders", resMap && (await evaluate("document.querySelector('.site-coords').textContent")).includes("-89.46316"));
await evaluate("document.getElementById('result-terrain').scrollIntoView({ block: 'center' }); true"); await sleep(1500);
const rr = await evaluate("(() => { const r = document.getElementById('result-terrain').getBoundingClientRect(); return { x: r.left, y: r.top, width: r.width, height: r.height }; })()");
await shot("04-result-map-and-3d-1440", rr);
await clickBtn("button", "Back to the Moon explorer"); await sleep(1500);

// ---- 5. zoom and pan
const pix = async () => { const c = await clip(); const { data } = await send("Page.captureScreenshot", { format: "png", clip: { ...c, height: c.height - 34, scale: 1 } }); let hh = 0; for (let i = 0; i < data.length; i += 7) hh = (hh * 31 + data.charCodeAt(i)) | 0; return hh; };
await sleep(3000);
const p0 = await pix();
await evaluate("document.querySelector('.ol-zoom-in').click(); true"); await sleep(1500); const p1 = await pix();
await evaluate("document.querySelector('.ol-zoom-out').click(); true"); await sleep(400);
await evaluate("document.querySelector('.ol-zoom-out').click(); true"); await sleep(1500); const p2 = await pix();
await evaluate("document.querySelector('.map-host').focus(); true");
for (const k of ["ArrowRight", "ArrowRight", "ArrowUp"]) await press(k);
await sleep(1500); const p3 = await pix();
check("zoom and pan: zoom-in and zoom-out buttons and keyboard arrows each change the map view", p1 !== p0 && p2 !== p1 && p3 !== p2);
for (let i = 0; i < 6; i++) { await evaluate("document.querySelector('.ol-zoom-out').click(); true"); await sleep(300); }
await evaluate("document.querySelector('.map-host').focus(); true");
for (let i = 0; i < 12; i++) await press("ArrowLeft");
await sleep(2500);
const edge = await evaluate(`(() => { const host = document.querySelector('.map-host'); const c = host.querySelector('.ol-layer canvas');
  const d = c.getContext('2d', { willReadFrequently: true }).getImageData(0, 0, c.width, c.height).data; const k = c.width / host.clientWidth;
  const a = (x, y) => d[4 * (Math.round(y * k) * c.width + Math.round(x * k)) + 3];
  return { leftMid: a(host.clientWidth * 0.12, host.clientHeight / 2), rightMid: a(host.clientWidth * 0.88, host.clientHeight / 2), centre: a(host.clientWidth / 2, host.clientHeight / 2) }; })()`);
await shot("05b-zoomed-out-panned-left-1440", await clip());
check("bounded view: zooming out fully and panning far left still shows terrain at the pane's left and right (no empty space beyond the data square)",
  edge.leftMid > 200 && edge.rightMid > 200 && edge.centre > 200, edge);

// ---- 6. unsupported coverage typed in; tile and metadata errors
await setValue("#lat", "-30"); await setValue("#lon", "10");
await waitFor("(() => { const t = document.querySelector('.explorer .hint[aria-live]')?.textContent || ''; return t && !/^Checking/.test(t); })()", 30000, "coverage");
const unsup = await evaluate("({ explorer: document.querySelector('.explorer .hint[aria-live]').textContent, analyse: document.querySelector('.explorer-run').disabled, inspect: [...document.querySelectorAll('.explorer button')].find(b => b.textContent === 'Inspect local terrain')?.disabled })");
check("unsupported coverage: a typed point north of 60 S shows the backend's reason; local terrain and analysis are disabled (a data-coverage limit, not an error)",
  /60-90 S only/.test(unsup.explorer) && unsup.analyse && unsup.inspect, unsup);
// failed tiles: with the browser cache off, block the zoom levels drawn around a newly selected site
await send("Network.setCacheDisabled", { cacheDisabled: true });
await send("Network.setBlockedURLs", { urls: ["*/api/tiles/5/*", "*/api/tiles/6/*", "*/api/tiles/7/*"] });
tiles.clear();
await setValue("#lat", "-85"); await setValue("#lon", "90");
for (let i = 0; i < 15; i++) { await sleep(1000); if (/terrain tiles? could not be loaded/.test(await note())) break; }
const n6 = await note();
report.errorPhaseTiles = tileList();
check("error state: tiles that fail to load are counted and reported in the note", /terrain tiles? could not be loaded/.test(n6), n6);
await shot("05-tile-error-note-1440", await clip());
await send("Network.setCacheDisabled", { cacheDisabled: false });
await send("Network.setBlockedURLs", { urls: ["*/api/tiles/meta"] });
await send("Page.reload"); await waitFor(READY, 60000, "status"); await sleep(3000);
const n7 = await note();
check("error state: tile metadata unavailable shows 'Terrain tiles unavailable' and the graticule still works", /Terrain tiles unavailable/.test(n7) && await evaluate("!!document.querySelector('.map-host canvas')"), n7);
await send("Network.setBlockedURLs", { urls: [] });

// ---- 7. mobile
await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
await send("Page.reload"); await waitFor(READY, 60000, "status"); await waitFor("document.querySelector('.map-host canvas')", 30000, "canvas"); await sleep(5000);
const mob = await evaluate("({ hscroll: document.documentElement.scrollWidth > document.documentElement.clientWidth, w: Math.round(document.querySelector('.map-host').getBoundingClientRect().width), h: Math.round(document.querySelector('.map-host').getBoundingClientRect().height) })");
await shot("06-mobile-390", await clip());
check("mobile (390 px): the map renders at full pane width without sideways scrolling", !mob.hscroll && mob.w > 300 && mob.h >= 250, mob);
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });

const errors = consoleMsgs.filter((m) => m.type === "exception" || m.type === "error" || (m.type === "log-error" && !/ERR_BLOCKED_BY_CLIENT/.test(m.text)));
check("no page exceptions or console errors (apart from the deliberately blocked requests)", errors.length === 0, errors.slice(0, 5));
report.checks = checks; report.console = consoleMsgs; report.tilesLast = tileList(); report.finished = new Date().toISOString();
fs.writeFileSync(path.join(OUT, "map-check.json"), JSON.stringify(report, null, 1));
const failed = checks.filter((c) => !c.ok).length;
console.log(`map-live-check: ${checks.length - failed}/${checks.length} checks passed`);
ws.close(); proc.kill();
try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(failed ? 1 : 0);
