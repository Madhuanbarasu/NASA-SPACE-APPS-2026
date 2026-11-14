#!/usr/bin/env node
// U-06 frontend performance audit of the running LUNA-OPS interface (no packages: Chrome DevTools Protocol over Node's
// built-in WebSocket, with a locally installed Chrome/Edge in headless mode).
//
//   node scripts/perf-audit.mjs --base http://127.0.0.1:8765 --out <dir> --label <name> --profile native|cpu4x|cpu4x-net10mbps
//        [--cold 3] [--warm 2] [--workflow 0|1] [--leak-cycles 5] [--phase5 0|1] [--block <patterns>] [--browser <path>]
// Results are written to <out>/perf-<label>-<profile>.json after every step, so an interrupted run keeps its data.
//
// Backend computation is not timed here (Phase 4 A7 owns those measurements); the analysis and comparison workloads
// use results already in the server cache, so the numbers are the interface's own cost: transfer, parse, render.
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const BASE = arg("--base", "http://127.0.0.1:8765");
const OUT = path.resolve(arg("--out", "perf-audit"));
const LABEL = arg("--label", "run");
const REPS = Number(arg("--reps", "3"));
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);
const BROWSER = [arg("--browser", ""), "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", "/usr/bin/google-chrome", "/usr/bin/chromium"].filter(Boolean).find((b) => fs.existsSync(b));
fs.mkdirSync(OUT, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const med = (a) => { const s = a.filter((x) => x != null && isFinite(x)).sort((x, y) => x - y); if (!s.length) return null; const m = Math.floor(s.length / 2); return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
const pct = (a, p) => { const s = a.filter((x) => x != null && isFinite(x)).sort((x, y) => x - y); return s.length ? s[Math.min(s.length - 1, Math.ceil((p / 100) * s.length) - 1)] : null; };
const r1 = (x) => (x == null ? null : Math.round(x * 10) / 10);

// ---------------------------------------------------------------- browser + CDP
const PORT = 9300 + Math.floor(Math.random() * 400);
const profileDir = fs.mkdtempSync(path.join(os.tmpdir(), "luna-perf-"));
const proc = spawn(BROWSER, [`--remote-debugging-port=${PORT}`, `--user-data-dir=${profileDir}`, "--headless=new", "--no-first-run",
  "--no-default-browser-check", "--disable-extensions", "--hide-scrollbars", "--enable-gpu", "--use-angle=d3d11", "--ignore-gpu-blocklist",
  "--js-flags=--expose-gc", "--window-size=1440,900", "about:blank"], { stdio: "ignore" });
let ws = null;
for (let i = 0; i < 100 && !ws; i++) {
  try { const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); const p = l.find((t) => t.type === "page"); if (p) ws = new WebSocket(p.webSocketDebuggerUrl); } catch { /* starting */ }
  if (!ws) await sleep(200);
}
await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
let nextId = 1; const pending = new Map(); const listeners = new Set();
ws.onmessage = (m) => { const msg = JSON.parse(m.data);
  if (msg.id && pending.has(msg.id)) { const { res, rej } = pending.get(msg.id); pending.delete(msg.id); msg.error ? rej(new Error(msg.error.message)) : res(msg.result); }
  else if (msg.method) for (const l of listeners) l(msg); };
const send = (method, params = {}) => new Promise((res, rej) => { const id = nextId++; pending.set(id, { res, rej }); ws.send(JSON.stringify({ id, method, params })); });
const evaluate = async (expr, timeout = 120000) => {
  const r = await Promise.race([send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }), sleep(timeout).then(() => ({ timeout: true }))]);
  if (r.timeout) throw new Error("evaluate timeout: " + expr.slice(0, 80));
  if (r.exceptionDetails) throw new Error("page error: " + (r.exceptionDetails.exception?.description || r.exceptionDetails.text));
  return r.result.value;
};
const waitFor = async (cond, timeout = 60000) => { const t0 = Date.now(); while (Date.now() - t0 < timeout) { if (await evaluate(`!!(${cond})`)) return true; await sleep(100); } throw new Error("timeout: " + cond); };
const metrics = async () => Object.fromEntries((await send("Performance.getMetrics")).metrics.map((m) => [m.name, m.value]));

// network accounting
const net = new Map(); let netLog = [];
listeners.add((m) => {
  if (m.method === "Network.requestWillBeSent") net.set(m.params.requestId, { url: m.params.request.url, start: performance.now(), type: m.params.type });
  if (m.method === "Network.responseReceived") { const r = net.get(m.params.requestId); if (r) { r.resp = performance.now(); r.mime = m.params.response.mimeType; r.fromCache = m.params.response.fromDiskCache || m.params.response.fromMemoryCache; } }
  // images served from Chrome's memory cache may never get loadingFinished: count them as done when served
  if (m.method === "Network.requestServedFromCache") { const r = net.get(m.params.requestId); if (r) { r.resp = r.resp ?? performance.now(); r.fromCache = true; } }
  if (m.method === "Network.loadingFinished") { const r = net.get(m.params.requestId); if (r) { r.end = performance.now(); r.bytes = m.params.encodedDataLength; netLog.push(r); } }
  if (m.method === "Network.loadingFailed") { const r = net.get(m.params.requestId); if (r) { r.end = performance.now(); r.failed = true; netLog.push(r); } }
});
const consoleMsgs = [];
listeners.add((m) => {
  if (m.method === "Runtime.consoleAPICalled" && ["warning", "error"].includes(m.params.type)) consoleMsgs.push(m.params.args.map((a) => a.value ?? a.description ?? "").join(" ").slice(0, 200));
  if (m.method === "Log.entryAdded" && ["warning", "error"].includes(m.params.entry.level)) consoleMsgs.push((m.params.entry.text || "").slice(0, 200));
});

// observers injected before any page script
const OBSERVERS = `window.__perf = { longtasks: [], lcp: null, cls: 0, events: [] };
try { new PerformanceObserver((l) => { for (const e of l.getEntries()) __perf.longtasks.push([e.startTime, e.duration]); }).observe({ type: 'longtask', buffered: true }); } catch (e) {}
try { new PerformanceObserver((l) => { const e = l.getEntries().at(-1); if (e) __perf.lcp = e.startTime; }).observe({ type: 'largest-contentful-paint', buffered: true }); } catch (e) {}
try { new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) __perf.cls += e.value; }).observe({ type: 'layout-shift', buffered: true }); } catch (e) {}
try { new PerformanceObserver((l) => { for (const e of l.getEntries()) __perf.events.push({ name: e.name, start: e.startTime, duration: e.duration, id: e.interactionId, input: e.processingStart - e.startTime, processing: e.processingEnd - e.processingStart }); }).observe({ type: 'event', buffered: true, durationThreshold: 16 }); } catch (e) {}
// run fn, then resolve at the first frame after cond() holds (frame-accurate, in page time)
window.__timeTo = (fn, cond, timeout = 600000) => new Promise((res, rej) => { const t0 = performance.now(); fn();
  const tick = () => { if (performance.now() - t0 > timeout) return rej(new Error('timeout')); if (cond()) requestAnimationFrame(() => setTimeout(() => res(performance.now() - t0), 0)); else requestAnimationFrame(tick); };
  requestAnimationFrame(tick); });
window.__click = (sel, text) => { const el = [...document.querySelectorAll(sel)].find((e) => text == null || e.textContent.trim() === text || e.getAttribute('aria-label') === text); if (!el) throw new Error('no ' + sel + ' ' + text); el.click(); };
window.__set = (sel, v) => { const el = document.querySelector(sel); const proto = el instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, v); el.dispatchEvent(new Event(el instanceof HTMLSelectElement ? 'change' : 'input', { bubbles: true })); };`;
await send("Page.enable"); await send("Runtime.enable"); await send("Network.enable"); await send("Performance.enable"); await send("Log.enable"); await send("HeapProfiler.enable");
await send("Page.addScriptToEvaluateOnNewDocument", { source: OBSERVERS });
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
const READY = "document.querySelector('.data-pill') && !/Connecting/.test(document.querySelector('.data-pill').textContent) && document.querySelector('.welcome h1')";

async function setProfile(p) {
  await send("Emulation.setCPUThrottlingRate", { rate: p.cpu });
  await send("Network.emulateNetworkConditions", p.net ? { offline: false, latency: p.net.latencyMs, downloadThroughput: p.net.kbps * 125, uploadThroughput: p.net.kbps * 125 }
    : { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
}

async function quiet(filter, quietMs = 800, timeout = 60000) {   // first matching request seen, then none in flight for quietMs
  const t0 = performance.now();
  while (![...net.values()].some((r) => filter(r.url))) { if (performance.now() - t0 > 20000) return null; await sleep(25); }
  let lastBusy = performance.now();
  while (performance.now() - t0 < timeout) {
    const inflight = [...net.values()].some((r) => filter(r.url) && r.end == null && r.resp == null);
    if (inflight) lastBusy = performance.now(); else if (performance.now() - lastBusy > quietMs) return Math.max(...[...net.values()].filter((r) => filter(r.url) && (r.end ?? r.resp) != null).map((r) => r.end ?? r.resp));
    await sleep(50);
  }
  return null;
}

// ---------------------------------------------------------------- 1. initial load
async function loadOnce(cold) {
  await send("Network.setCacheDisabled", { cacheDisabled: cold });
  if (cold) await send("Network.clearBrowserCache");
  await send("Page.navigate", { url: "about:blank" }); await sleep(300);
  net.clear(); netLog = [];
  const t0 = performance.now();
  await send("Page.navigate", { url: BASE + "/" });
  await waitFor(READY, 120000);
  const readyAt = performance.now() - t0;
  const tilesQuietAt = await quiet((u) => /\/api\/tiles\/\d+\/\d+\/\d+\.png/.test(u), 800, 30000);
  await sleep(300);
  const page = await evaluate(`(() => { const n = performance.getEntriesByType('navigation')[0]; const p = Object.fromEntries(performance.getEntriesByType('paint').map((e) => [e.name, e.startTime]));
    const res = performance.getEntriesByType('resource'); const fcp = p['first-contentful-paint'];
    const tbt = __perf.longtasks.filter(([s]) => s >= fcp).reduce((a, [, d]) => a + Math.max(0, d - 50), 0);
    return { ttfb: n.responseStart, domContentLoaded: n.domContentLoadedEventEnd, load: n.loadEventEnd, fcp, lcp: __perf.lcp, cls: __perf.cls,
      longTasks: __perf.longtasks.length, longestTask: Math.max(0, ...__perf.longtasks.map((t) => t[1])), tbt,
      jsDecoded: res.filter((r) => r.initiatorType === 'script' || /\\.js$/.test(r.name)).reduce((a, r) => a + r.decodedBodySize, 0) + (n.decodedBodySize || 0) * 0 }; })()`);
  const m = await metrics();
  const by = (re) => netLog.filter((r) => re.test(r.url));
  const sum = (a) => a.reduce((s, r) => s + (r.bytes || 0), 0);
  return { cold, appReadyMs: r1(readyAt), mapTilesDoneMs: tilesQuietAt == null ? null : r1(tilesQuietAt - t0), ...Object.fromEntries(Object.entries(page).map(([k, v]) => [k, typeof v === "number" ? r1(v) : v])),
    transfer: { totalKB: r1(sum(netLog) / 1024), jsKB: r1(sum(by(/\.js(\?|$)/)) / 1024), cssKB: r1(sum(by(/\.css(\?|$)/)) / 1024), fontKB: r1(sum(by(/\.woff2?(\?|$)/)) / 1024),
      apiKB: r1(sum(by(/\/api\/(?!tiles\/\d)/)) / 1024), tiles: [...net.values()].filter((r) => /\/api\/tiles\/\d+\/\d+\/\d+\.png/.test(r.url)).length, tilesKB: r1(sum(by(/\/api\/tiles\/\d/)) / 1024), requests: net.size },
    heapMB: r1(m.JSHeapUsedSize / 1048576), domNodes: m.Nodes, scriptMs: r1(m.ScriptDuration * 1000), layoutMs: r1(m.LayoutDuration * 1000), styleMs: r1(m.RecalcStyleDuration * 1000), taskMs: r1(m.TaskDuration * 1000) };
}

// ---------------------------------------------------------------- 2. interactions on the real workloads
async function workflow() {
  await send("Network.setCacheDisabled", { cacheDisabled: false });
  await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 120000); await quiet((u) => u.includes("/api/"), 600, 30000);
  const w = {};
  const T = (fn, cond, timeout) => evaluate(`__timeTo(() => { ${fn} }, () => ${cond}${timeout ? ", " + timeout : ""})`, (timeout || 600000) + 5000);
  // view transitions from the welcome state
  w.tabs = {};
  for (const [tab, sel] of [["Compare", "h1.site-title"], ["Data and validation", ".prose h1"], ["Guide", ".prose h1"], ["Site", ".welcome h1"]])
    w.tabs[tab] = r1(await T(`__click('button.tab', ${JSON.stringify(tab)})`, `!!document.querySelector(${JSON.stringify(sel)}) && document.querySelector('button.tab[aria-selected=true]').textContent === ${JSON.stringify(tab)}`));
  // cached Site01 analysis (14-21 Nov 2026)
  await evaluate(`__set('#lat', '-89.463163'); __set('#lon', '222.510447'); __set('#start', '2026-11-14T00:00'); __set('#end', '2026-11-21T00:00'); true`);
  await waitFor("/Terrain coverage/.test(document.querySelector('#coord-hint')?.textContent || '')", 60000);
  net.clear(); netLog = [];
  const tClick = performance.now();
  w.analysisToResultMs = r1(await T(`document.querySelector('.run-button').click()`, `!!document.querySelector('.site-title')`));
  const terrainQuiet = await quiet((u) => u.includes("/api/terrain"), 300, 60000);
  w.analysisTo3DDataMs = terrainQuiet == null ? null : r1(terrainQuiet - tClick);
  const tq = await quiet((u) => /\/api\/tiles\/\d+\/\d+\/\d+\.png/.test(u), 800, 30000);
  w.analysisToMapTilesMs = tq == null ? null : r1(tq - tClick);
  const res = netLog.find((r) => /\/api\/results\/[^/]+$/.test(r.url));
  const ter = netLog.find((r) => r.url.includes("/api/terrain"));
  w.resultJsonKB = res ? r1(res.bytes / 1024) : null;
  w.resultFetchMs = res ? r1(res.end - res.start) : null;
  w.terrainGridKB = ter ? r1(ter.bytes / 1024) : null;
  w.series = await evaluate("document.querySelectorAll('.scrubber input')[0]?.max");
  // time-cursor stepping by keyboard: Event Timing per interaction
  await evaluate("__perf.events = []; document.querySelector('.scrubber input').focus(); true");
  for (let i = 0; i < 20; i++) { for (const type of ["rawKeyDown", "keyUp"]) await send("Input.dispatchKeyEvent", { type, key: "ArrowRight", code: "ArrowRight", windowsVirtualKeyCode: 39 }); await sleep(120); }
  await sleep(400);
  const ev = await evaluate("__perf.events.filter((e) => e.name === 'keydown').map((e) => e.duration)");
  w.cursorStep = { interactions: ev.length, medianMs: med(ev), p95Ms: pct(ev, 95), maxMs: ev.length ? Math.max(...ev) : null };
  // playback: frame intervals and long tasks over 5 s, tables collapsed then expanded
  for (const expanded of [false, true]) {
    if (expanded) { await evaluate("__click('button.toggle-table', 'Show'); __click('button.toggle-table', 'Show table'); true"); await sleep(500); }
    const m0 = await metrics();
    const pb = await evaluate(`new Promise((res) => { const lt0 = __perf.longtasks.length; const c0 = Number(document.querySelector('.scrubber input').value); const frames = []; let last = performance.now(); const t0 = last;
      __click('button.play', 'Play animation');
      const f = (t) => { frames.push(t - last); last = t; if (t - t0 < 5000) requestAnimationFrame(f); else { __click('button.play', 'Pause animation');
        const c1 = Number(document.querySelector('.scrubber input').value); const lts = __perf.longtasks.slice(lt0);
        res({ steps: (c1 - c0 + Number(document.querySelector('.scrubber input').max) + 1) % (Number(document.querySelector('.scrubber input').max) + 1), frames: frames.length, fps: frames.length / ((t - t0) / 1000),
          frameP95: frames.slice().sort((a, b) => a - b)[Math.floor(frames.length * 0.95)], frameMax: Math.max(...frames), longTasks: lts.length, longestTask: Math.max(0, ...lts.map((x) => x[1])),
          blockingMs: lts.reduce((a, [, d]) => a + Math.max(0, d - 50), 0) }); } };
      requestAnimationFrame(f); })`);
    const m1 = await metrics();
    w[expanded ? "playbackTablesOpen" : "playback"] = { ...Object.fromEntries(Object.entries(pb).map(([k, v]) => [k, r1(v)])), expectedSteps: Math.floor(5000 / 140),
      scriptMsPerStep: r1(((m1.ScriptDuration - m0.ScriptDuration) * 1000) / Math.max(1, pb.steps)), layoutMs: r1((m1.LayoutDuration - m0.LayoutDuration) * 1000), domNodes: m1.Nodes };
    if (expanded) { await evaluate("__click('button.toggle-table', 'Hide'); __click('button.toggle-table', 'Hide table'); true"); await sleep(300); }
  }
  // 3D: rotate button -> next frame
  const rot = [];
  for (let i = 0; i < 12; i++) rot.push(await T(`__click('.view-controls button', 'Rotate view left')`, "true"));
  w.rotate3D = { medianMs: r1(med(rot)), maxMs: r1(Math.max(...rot)) };
  // Technical <-> Public
  w.modeToPublicMs = r1(await T(`__click('.mode-switch button', 'Public')`, "!!document.querySelector('.public-summary')"));
  w.modeToTechnicalMs = r1(await T(`__click('.mode-switch button', 'Technical')`, "!document.querySelector('.public-summary')"));
  // tab away from and back to the result (unmount/mount of map, 3D, charts)
  w.resultToDataMs = r1(await T(`__click('button.tab', 'Data and validation')`, "!!document.querySelector('.prose h1')"));
  w.dataToResultMs = r1(await T(`__click('button.tab', 'Site')`, "!!document.querySelector('.site-title') && !!document.querySelector('.three-host canvas')"));
  // cached 2 x 2 comparison
  await evaluate(`__click('button.quiet-button', 'Add to comparison'); __set('#lat', '-89.9'); __set('#lon', '0'); true`); await sleep(500);
  await evaluate(`__click('button.quiet-button', 'Add to comparison'); __click('button.tab', 'Compare'); true`); await sleep(400);
  await evaluate(`__click('button.quiet-button', "Add the panel's dates"); __click('button.quiet-button', 'Add one synodic month later'); true`); await sleep(200);
  w.compareToMatrixMs = r1(await T(`[...document.querySelectorAll('button.run-button')].find((b) => /^Compare/.test(b.textContent)).click()`, "!!document.querySelector('table.matrix .cell-open')"));
  w.metricSwitchMs = r1(await T(`__click('.segmented-wrap button', 'Longest darkness')`, "true"));
  w.cellToResultMs = r1(await T(`document.querySelector('table.matrix .cell-open').click()`, "!!document.querySelector('.site-title') && document.querySelector('button.tab[aria-selected=true]').textContent === 'Site'"));
  const m = await metrics(); w.heapAfterWorkflowMB = r1(m.JSHeapUsedSize / 1048576); w.domNodesAfterWorkflow = m.Nodes;
  return w;
}

// ---------------------------------------------------------------- 3. memory / leak check over repeated mounts
async function leakCheck(cycles = 10) {
  const snap = async () => { await send("HeapProfiler.collectGarbage"); await sleep(400); await send("HeapProfiler.collectGarbage"); await sleep(300); const m = await metrics(); return { heapMB: r1(m.JSHeapUsedSize / 1048576), nodes: m.Nodes, listeners: m.JSEventListeners }; };
  await evaluate("__click('button.tab', 'Site'); true"); await waitFor("document.querySelector('.three-host canvas')", 60000); await sleep(1500);
  const before = await snap(); const c0 = consoleMsgs.length;
  for (let i = 0; i < cycles; i++) {
    await evaluate("__click('button.tab', 'Compare'); true"); await sleep(400);
    await evaluate("__click('button.tab', 'Site'); true"); await waitFor("document.querySelector('.three-host canvas')", 60000); await sleep(600);
  }
  const after = await snap();
  const contexts = await evaluate("document.querySelectorAll('canvas').length");
  return { cycles, before, after, heapGrowthMB: r1(after.heapMB - before.heapMB), nodeGrowth: after.nodes - before.nodes, listenerGrowth: after.listeners - before.listeners,
    canvasesInDom: contexts, newConsoleWarnings: consoleMsgs.slice(c0) };
}

// ---------------------------------------------------------------- 4. Phase 5 supplement (--phase5 1): mission tab, globe, local terrain
// On a fresh page: Mission tab switch; opening the 3D globe (canvas, then its imagery requests quiet) and the local
// terrain preview (canvas and /api/terrain quiet); Event Timing over 10 keyboard steps on the globe and on the terrain
// preview; and mount/unmount cycles (forced GC) of the globe and of the terrain preview against the map view.
async function phase5Workflow(cycles = 5) {
  await send("Network.setCacheDisabled", { cacheDisabled: false });
  await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 120000); await quiet((u) => u.includes("/api/"), 600, 30000);
  const w = {};
  const T = (fn, cond, timeout) => evaluate(`__timeTo(() => { ${fn} }, () => ${cond}${timeout ? ", " + timeout : ""})`, (timeout || 600000) + 5000);
  w.tabToMissionMs = r1(await T(`__click('button.tab', 'Mission')`, "!!document.querySelector('.mission h1')"));
  w.tabMissionToSiteMs = r1(await T(`__click('button.tab', 'Site')`, "!!document.querySelector('.welcome h1')"));
  await evaluate(`__set('#lat', '-89.463163'); __set('#lon', '222.510447'); true`);
  await waitFor("/Terrain coverage/.test(document.querySelector('#coord-hint')?.textContent || '')", 60000);
  await sleep(500);
  net.clear(); netLog = [];
  const tg = performance.now();
  w.globeToCanvasMs = r1(await T(`__click('.view-switch button', '3D Moon globe')`, "!!document.querySelector('.globe-host canvas')"));
  const gq = await quiet((u) => /\/moon\//.test(u), 800, 60000);
  w.globeToImageryMs = gq == null ? null : r1(gq - tg);
  w.globeImageryKB = r1(netLog.filter((r) => /\/moon\//.test(r.url)).reduce((a, r) => a + (r.bytes || 0), 0) / 1024);
  const keySteps = async (sel, key, shift) => {
    await evaluate(`__perf.events = []; document.querySelector(${JSON.stringify(sel)}).focus(); true`);
    for (let i = 0; i < 10; i++) { for (const type of ["rawKeyDown", "keyUp"]) await send("Input.dispatchKeyEvent", { type, key, code: key, windowsVirtualKeyCode: key === "ArrowLeft" ? 37 : 39, modifiers: shift ? 8 : 0 }); await sleep(150); }
    await sleep(400);
    const ev = await evaluate("__perf.events.filter((e) => e.name === 'keydown').map((e) => e.duration)");
    return { interactions: ev.length, medianMs: med(ev), p95Ms: pct(ev, 95), maxMs: ev.length ? Math.max(...ev) : null };
  };
  await sleep(1500);
  w.globeKeySteps = await keySteps(".globe-host", "ArrowLeft", false);
  net.clear(); netLog = [];
  const tt = performance.now();
  w.terrainToCanvasMs = r1(await T(`__click('.view-switch button', 'Local terrain')`, "!!document.querySelector('.terrain-preview .three-host canvas')"));
  const tdq = await quiet((u) => u.includes("/api/terrain"), 300, 60000);
  w.terrainToDataMs = tdq == null ? null : r1(tdq - tt);
  await sleep(1500);
  w.terrainKeySteps = await keySteps(".terrain-preview .three-host", "ArrowLeft", true);
  // mount/unmount cycles against the map view, forced GC before and after
  const snap = async () => { await send("HeapProfiler.collectGarbage"); await sleep(400); await send("HeapProfiler.collectGarbage"); await sleep(300); const m = await metrics(); return { heapMB: r1(m.JSHeapUsedSize / 1048576), nodes: m.Nodes, listeners: m.JSEventListeners }; };
  const cyclesOf = async (label, ready) => {
    await evaluate(`__click('.view-switch button', 'South polar map'); true`); await sleep(800);
    await evaluate(`__click('.view-switch button', ${JSON.stringify(label)}); true`); await waitFor(ready, 90000); await sleep(1500);
    const before = await snap(); const c0 = consoleMsgs.length;
    for (let i = 0; i < cycles; i++) {
      await evaluate(`__click('.view-switch button', 'South polar map'); true`); await sleep(600);
      await evaluate(`__click('.view-switch button', ${JSON.stringify(label)}); true`); await waitFor(ready, 90000); await sleep(1200);
    }
    const after = await snap();
    return { cycles, before, after, heapGrowthMB: r1(after.heapMB - before.heapMB), nodeGrowth: after.nodes - before.nodes, listenerGrowth: after.listeners - before.listeners,
      canvasesInDom: await evaluate("document.querySelectorAll('canvas').length"), newConsoleWarnings: consoleMsgs.slice(c0) };
  };
  w.globeRemount = await cyclesOf("3D Moon globe", "document.querySelector('.globe-host canvas')");
  w.terrainRemount = await cyclesOf("Local terrain", "document.querySelector('.terrain-preview .three-host canvas') && document.querySelector('.terrain-stats')");
  const m = await metrics(); w.heapAfterPhase5MB = r1(m.JSHeapUsedSize / 1048576);
  return w;
}

// ---------------------------------------------------------------- run (one profile per invocation; saved after every step)
const PROFILES = {
  native: { name: "native", cpu: 1, net: null },
  cpu4x: { name: "cpu4x", cpu: 4, net: null },
  "cpu4x-net10mbps": { name: "cpu4x-net10mbps", cpu: 4, net: { kbps: 10000, latencyMs: 40 } },
};
const PROFILE = PROFILES[arg("--profile", "native")];
if (!PROFILE) { console.error("unknown --profile; use " + Object.keys(PROFILES).join(", ")); process.exit(2); }
const COLD = Number(arg("--cold", String(REPS))), WARM = Number(arg("--warm", "2"));
// --block "<pattern>[,<pattern>]": Chrome refuses these requests (e.g. the pathological zoom-0 basemap tile), so the
// frontend can be measured without starting that backend render on every load
const BLOCK = (arg("--block", "") || "").split(",").filter(Boolean);
const DO_WORKFLOW = arg("--workflow", PROFILE.net ? "0" : "1") === "1", LEAK_CYCLES = Number(arg("--leak-cycles", PROFILE.cpu === 1 && !PROFILE.net ? "5" : "0"));
const PHASE5 = arg("--phase5", "0") === "1";
const FILE = path.join(OUT, `perf-${LABEL}-${PROFILE.name}.json`);
const report = { label: LABEL, profile: PROFILE, base: BASE, browser: (await send("Browser.getVersion")).product, started: new Date().toISOString(),
  plan: { coldLoads: COLD, warmLoads: WARM, workflow: DO_WORKFLOW, leakCycles: LEAK_CYCLES, phase5: PHASE5, blockedUrls: BLOCK }, complete: false, steps: [] };
const save = () => { report.consoleWarnings = [...new Set(consoleMsgs)].slice(0, 40); report.saved = new Date().toISOString(); fs.writeFileSync(FILE, JSON.stringify(report, null, 1)); };
const keys = ["appReadyMs", "mapTilesDoneMs", "ttfb", "domContentLoaded", "load", "fcp", "lcp", "cls", "tbt", "longTasks", "longestTask", "heapMB", "domNodes", "scriptMs"];
const summarize = (runs) => (runs.length ? { n: runs.length, ...Object.fromEntries(keys.map((k) => [k, r1(med(runs.map((r) => r[k])))])), transfer: runs[0].transfer } : null);
try {
  if (BLOCK.length) await send("Network.setBlockedURLs", { urls: BLOCK });
  await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 120000);
  report.webgl = await evaluate("(() => { const gl = document.createElement('canvas').getContext('webgl'); const e = gl && gl.getExtension('WEBGL_debug_renderer_info'); return gl ? (e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER)) : null; })()");
  report.userAgent = await evaluate("navigator.userAgent"); report.hardwareConcurrency = await evaluate("navigator.hardwareConcurrency");
  await setProfile(PROFILE);
  report.coldLoad = { runs: [] }; report.warmLoad = { runs: [] }; save();
  for (let i = 0; i < COLD; i++) { report.coldLoad.runs.push(await loadOnce(true)); report.coldLoad.median = summarize(report.coldLoad.runs); report.steps.push(`cold ${i + 1}`); save(); log(PROFILE.name, "cold", i + 1); }
  for (let i = 0; i < WARM; i++) { report.warmLoad.runs.push(await loadOnce(false)); report.warmLoad.median = summarize(report.warmLoad.runs); report.steps.push(`warm ${i + 1}`); save(); log(PROFILE.name, "warm", i + 1); }
  if (DO_WORKFLOW) { report.interactions = await workflow(); report.steps.push("workflow"); save(); log(PROFILE.name, "workflow done"); }
  if (LEAK_CYCLES > 0) { report.memory = await leakCheck(LEAK_CYCLES); report.steps.push("leak check"); save(); log(PROFILE.name, "leak check done"); }
  if (PHASE5) { report.phase5 = await phase5Workflow(); report.steps.push("phase5"); save(); log(PROFILE.name, "phase5 done"); }
  report.complete = true;
} catch (e) {
  report.error = String(e && e.stack || e); log("stopped:", report.error.split("\n")[0]);
} finally {
  report.finished = new Date().toISOString(); save();
  await setProfile(PROFILES.native).catch(() => {});
  ws.close(); proc.kill();
  try { fs.rmSync(profileDir, { recursive: true, force: true }); } catch { /* browser may hold files */ }
}
const c = report.coldLoad?.median, w = report.warmLoad?.median;
console.log(`${PROFILE.name}: cold appReady ${c?.appReadyMs} ms, FCP ${c?.fcp}, LCP ${c?.lcp}, TBT ${c?.tbt}, JS ${c?.transfer?.jsKB} KB; warm appReady ${w?.appReadyMs}; complete=${report.complete}`);
if (report.interactions) console.log("interactions", JSON.stringify(report.interactions));
if (report.memory) console.log("memory", JSON.stringify(report.memory));
if (report.phase5) console.log("phase5", JSON.stringify(report.phase5));
process.exit(report.complete ? 0 : 1);
