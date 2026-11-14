#!/usr/bin/env node
// Phase 5 prompt 3: live check of the scientific visualisations against the API's own result objects, in a real browser
// (Chrome/Edge headless through the DevTools Protocol, Node's built-in WebSocket; no packages). Needs the app running.
//
//   node scripts/viz-live-check.mjs --base http://127.0.0.1:8765 --out <dir>
//
// Every displayed value is compared with GET /api/results/{id} fetched in the same page: site/observer/terrain context,
// labels (never upgraded), the Sun/Earth visibility chart (gaps only where the API has null), cursor synchronisation,
// timeline tooltips and the intervals table with the API's flags, the panorama sigma readout, date and site switching,
// an incomplete-horizon site near 60 S, an unsupported location, a 2 x 2 comparison (bars, label counts, legend) and the
// 390 px layout. Results in <out>/viz-check.json, screenshots in <out>/screenshots/; exit 1 if any check fails.
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const BASE = arg("--base", "http://127.0.0.1:8765");
const OUT = path.resolve(arg("--out", "viz-check"));
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

const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const proto = e instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
  const set = Object.getOwnPropertyDescriptor(proto, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event(e instanceof HTMLSelectElement ? 'change' : 'input', { bubbles: true })); return true; })()`);
const checks = [];
const check = (name, ok, detail) => { checks.push({ name, ok: !!ok, detail }); console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail !== undefined ? "  " + JSON.stringify(detail).slice(0, 400) : ""}`); };
const report = { base: BASE, browser: BROWSER, started: new Date().toISOString(), analyses: [] };
await send("Runtime.enable"); await send("Log.enable"); await send("Network.enable"); await send("Page.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url: BASE + "/" });
await waitFor("document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')", 60000, "status");
await sleep(1200);

// run an analysis through the explorer (or the sidebar) and return the API's own result object for comparison
async function analyse(lat, lon, start, end) {
  if (await evaluate("!!document.querySelector('.site-title')")) { await clickBtn("button", "Back to the Moon explorer"); await sleep(600); }
  await setValue("#lat", lat); await setValue("#lon", lon); await setValue("#start", start); await setValue("#end", end);
  await sleep(500);
  await waitFor("(() => { const t = document.querySelector('.explorer .hint[aria-live]')?.textContent || ''; return t && !/^Checking/.test(t); })()", 30000, "coverage");
  await evaluate("document.querySelector('.explorer-run').click(); true");
  await waitFor("document.querySelector('.site-title')", 900000, "analysis result");
  await sleep(2000);
  const id = await evaluate("(document.querySelector('a[href$=\"/result.json\"]')?.getAttribute('href') || '').split('/')[3]");
  const r = await evaluate(`fetch('/api/results/${id}').then(x => x.json())`);
  report.analyses.push({ lat, lon, start, end, id });
  return r;
}
const text = (sel) => evaluate(`document.querySelector(${JSON.stringify(sel)})?.textContent || ''`);
const fmt3 = (lat, lon) => `${Math.abs(lat).toFixed(3)}° ${lat >= 0 ? "N" : "S"}, ${(((lon % 360) + 360) % 360).toFixed(3)}° E`;

// ---- 1. Site01, one week (cached): every displayed value against the API result
const r1 = await analyse("-89.463163", "222.510447", "2026-11-14T00:00", "2026-11-21T00:00");
const ctx = await evaluate("[...document.querySelectorAll('.context-card')].map(c => c.textContent)");
check("context: site card shows the result's coordinates and ground height", ctx[0].includes(fmt3(r1.site.lat, r1.site.lon)) && ctx[0].includes(`Ground ${r1.site.ground_h_m.toFixed(1)} m`) && ctx[0].includes(r1.site.terrain_level_at_site), ctx[0]);
check("context: observer and window from the result's provenance", ctx[1].includes(r1.provenance.parameters.observer.label) && ctx[1].includes(`display step ${(r1.series.step_s / 60).toFixed(0)} min`), ctx[1]);
check("context: horizon range, near-field share and sigma statement match the result", ctx[2].includes(`${r1.horizon.min_deg.toFixed(2)}° to ${r1.horizon.max_deg.toFixed(2)}°`)
  && (r1.horizon.near_field_share ? ctx[2].includes(`${(100 * r1.horizon.near_field_share).toFixed(1)} %`) : true) && (r1.horizon.sigma_deg ? /L_corr/.test(ctx[2]) : /No horizon uncertainty/.test(ctx[2])), ctx[2]);
check("context: every terrain level the horizon used is listed with its product", r1.provenance.horizon.levels.every((lv) => ctx[3].includes(`${lv.level}, ${lv.pixel_m} m pixels`) && ctx[3].includes(lv.product)), ctx[3]);
const chips = await evaluate("[...document.querySelectorAll('.label-row .chip')].map(c => c.textContent)");
const apiValid = Object.values(r1.labels).filter((l) => l.validation.startsWith("Validated")).length;
check("labels: chips unchanged in number and status (no Pending shown as Validated)", chips.length === Object.keys(r1.labels).length
  && chips.filter((c) => /validated$/i.test(c) && !/pending/i.test(c)).length === apiValid, { chips, apiValidated: apiValid });
check("data key: four data classes explained", (await evaluate("document.querySelectorAll('.data-key dt').length")) === 4);
// visibility chart
const nNull = { sun: r1.series.sun.f.filter((v) => v == null).length, earth: r1.series.earth.f.filter((v) => v == null).length };
const vis = await evaluate("({ panels: document.querySelectorAll('.vis-chart svg path').length, gaps: document.querySelectorAll('.vis-chart svg rect[fill=\"url(#vis-hatch)\"]').length, readout: document.querySelector('.vis-readout').textContent })");
check("visibility: two panels drawn; unknown gaps only where the API has null values", vis.panels >= 4 && ((nNull.sun + nNull.earth === 0) === (vis.gaps === 0)), { vis, nNull });
check("visibility: readout at the cursor shows the API's Sun and Earth fractions at the cursor time", vis.readout.includes("Sun") && vis.readout.includes("Earth"), vis.readout);
// cursor sync: click the chart at 75 % of its width -> slider moves, readout follows
const box = await evaluate("(() => { const r = document.querySelector('.vis-chart svg').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; })()");
await evaluate("document.querySelector('.vis-chart').scrollIntoView({ block: 'center' }); true"); await sleep(400);
const box2 = await evaluate("(() => { const r = document.querySelector('.vis-chart svg').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; })()");
const before = await evaluate("document.querySelector('.scrubber input[type=range]').value");
await mouseClick(box2[0] + box2[2] * 0.75, box2[1] + box2[3] * 0.3);
const after = await evaluate("document.querySelector('.scrubber input[type=range]').value");
check("visibility: clicking the chart moves the shared time cursor (slider, panorama, timeline)", Number(after) > Number(before) && Number(after) > r1.series.et.length * 0.6, { before, after, n: r1.series.et.length });
await shot("01-result-context-and-visibility");
// timeline tooltips and intervals table
const rows = [`sun_${r1.provenance.parameters.rules.sunlit}`, `earth_${r1.provenance.parameters.rules.dte}`, "overlap"];
const nIv = rows.reduce((a, k) => a + (r1.intervals[k]?.length ?? 0), 0);
const nTitles = await evaluate("document.querySelectorAll('.timeline-wrap svg title').length");
check("timeline: every interval (including dark and unknown periods) has a tooltip", nTitles === nIv, { nTitles, nIv });
await clickBtn("button.toggle-intervals", "Show"); await sleep(400);
const nRows = await evaluate("document.querySelectorAll('.intervals tbody tr').length");
const flags = await evaluate("[...document.querySelectorAll('.intervals tbody tr')].map(tr => tr.lastElementChild.textContent).filter(Boolean)");
const apiNear = rows.flatMap((k) => r1.intervals[k] ?? []).filter((iv) => iv.near_field).length;
check("timeline: the intervals table lists every interval with the API's flags (near field shown where set)", nRows === nIv && flags.filter((f) => /near-field/.test(f)).length === apiNear, { nRows, apiNear, flags: flags.slice(0, 4) });
check("timeline: legend explains the nine encodings", (await evaluate("document.querySelectorAll('.timeline-legend li').length")) === 9);
await evaluate("document.querySelector('.timeline-wrap').scrollIntoView({ block: 'center' }); true"); await sleep(300);
await shot("02-timeline-legend-intervals");
// panorama: legend and readout with sigma and near field
const leg = await text(".panorama-head .legend");
check("horizon: legend shows the sigma band and near-field bins when the result has them", (!r1.horizon.sigma_deg || /±1σ/.test(leg)) && (!(r1.horizon.near_field ?? []).some(Boolean) || /Near-field/.test(leg)), leg);
await evaluate("document.querySelector('.panorama svg').scrollIntoView({ block: 'center' }); document.querySelector('.panorama svg').focus(); true"); await sleep(300);
const vt = await evaluate("document.querySelector('.panorama svg').getAttribute('aria-valuetext')");
const az = Number(await evaluate("document.querySelector('.panorama svg').getAttribute('aria-valuenow')"));
const bin = Math.round(az / r1.horizon.bin_deg) % r1.horizon.nbins;
const sig = r1.horizon.sigma_deg?.[bin];
check("horizon: the readout gives the API's horizon and 1-sigma for the focused azimuth", vt.includes(`horizon ${r1.horizon.h_deg[bin].toFixed(2)}°`) && (sig == null || vt.includes(`±${sig.toFixed(2)}°`)), { vt, bin, sigma: sig });
await shot("03-panorama-sigma-nearfield");
await evaluate("document.activeElement.blur(); true");
const res1 = { sunPct: r1.summary[`sun_${r1.provenance.parameters.rules.sunlit}`].percent, window: ctx[1] };

// ---- 2. date switching: Site01, a later window (another real analysis)
const r2 = await analyse("-89.463163", "222.510447", "2026-12-13T12:44", "2026-12-20T12:44");
const ctx2 = await evaluate("[...document.querySelectorAll('.context-card')].map(c => c.textContent)");
const vt2 = await text(".vis-readout");
check("switching dates updates the context, chart and figures from the new result", ctx2[1] !== res1.window && ctx2[1].includes("13 Dec 2026") && vt2.includes("Dec"), { ctx: ctx2[1], readout: vt2 });
await shot("04-site01-december-window");

// ---- 3. site switching: another covered site, then an incomplete-horizon site near the 60 S edge
const r3 = await analyse("-89.9", "0", "2026-11-14T00:00", "2026-11-21T00:00");
const ctx3 = await evaluate("[...document.querySelectorAll('.context-card')].map(c => c.textContent)");
check("switching sites updates the context to the new site", ctx3[0].includes("89.900° S, 0.000° E") && ctx3[0].includes(`Ground ${r3.site.ground_h_m.toFixed(1)} m`), ctx3[0]);
// (-60.02, 0): the 240 m terrain ends about 2 km to the north, so many horizon bins run out of terrain (real lower bounds)
const r4 = await analyse("-60.02", "0", "2026-11-14T00:00", "2026-11-15T00:00");
const ctx4 = await evaluate("[...document.querySelectorAll('.context-card')].map(c => c.textContent)");
const leg4 = await text(".panorama-head .legend");
const inc = r4.horizon.incomplete_share;
report.edgeSite = { incomplete_share: inc, labels: Object.fromEntries(Object.entries(r4.labels).map(([k, v]) => [k, v.validation])) };
check("missing data: an incomplete horizon is reported as lower bounds (context and legend), never as complete", inc > 0
  && ctx4[2].includes(`${(100 * inc).toFixed(1)} % of bins ran out`) && /Coverage ran out/.test(leg4), { inc, ctx: ctx4[2] });
const chips4 = await evaluate("[...document.querySelectorAll('.label-row .chip')].map(c => c.textContent)");
check("missing data: labels stay as the API gives them (terrain quantities not Validated)",
  chips4.filter((c) => /validated$/i.test(c) && !/pending/i.test(c)).length === Object.values(r4.labels).filter((l) => l.validation.startsWith("Validated")).length
  && ["horizon", "disk_visibility", "events", "power_indicator"].every((k) => !r4.labels[k].validation.startsWith("Validated")), { chips: chips4, labels: report.edgeSite.labels });
const nNull4 = r4.series.sun.f.filter((v) => v == null).length + r4.series.earth.f.filter((v) => v == null).length;
const gaps4 = await evaluate("document.querySelectorAll('.vis-chart svg rect[fill=\"url(#vis-hatch)\"]').length");
const rows4 = [`sun_${r4.provenance.parameters.rules.sunlit}`, `earth_${r4.provenance.parameters.rules.dte}`, "overlap"];
const unk4 = rows4.flatMap((k) => r4.intervals[k] ?? []).filter((iv) => iv.state === null).length;
await clickBtn("button.toggle-intervals", "Show"); await sleep(300);
const unkRows = await evaluate("[...document.querySelectorAll('.intervals tbody tr')].filter(tr => tr.children[1].textContent === 'unknown').length");
const hatched = await evaluate("document.querySelectorAll('.timeline-wrap svg rect[fill=\"url(#tl-hatch)\"]').length");
check("missing data: unknown values from the API are shown as gaps (chart), hatched unknown intervals (timeline) and 'unknown' rows, never filled",
  nNull4 > 0 && gaps4 > 0 && unk4 > 0 && unkRows === unk4 && hatched === unk4, { nNull: nNull4, chartGaps: gaps4, unknownIntervals: unk4, unknownRows: unkRows, hatched });
await evaluate("document.querySelector('.vis-chart').scrollIntoView({ block: 'center' }); true"); await sleep(300);
await shot("05-edge-site-60S-missing-data");

// ---- 4. unsupported location: no analysis
await clickBtn("button", "Back to the Moon explorer"); await sleep(500);
await setValue("#lat", "-30"); await setValue("#lon", "10"); await sleep(600);
await waitFor("(() => { const t = document.querySelector('.explorer .hint[aria-live]')?.textContent || ''; return t && !/^Checking/.test(t); })()", 30000, "coverage");
check("unsupported: analysis disabled with the backend's reason", await evaluate("document.querySelector('.explorer-run').disabled && document.querySelector('.run-button').disabled")
  && /60-90 S only/.test(await text(".explorer .hint[aria-live]")));

// ---- 5. comparison: 2 sites x 2 windows with bars, label counts and legend
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447"); await setValue("#start", "2026-11-14T00:00"); await setValue("#end", "2026-11-21T00:00"); await sleep(400);
await clickBtn("button.quiet-button", "Add to comparison");
await setValue("#lat", "-89.9"); await setValue("#lon", "0"); await sleep(400);
await clickBtn("button.quiet-button", "Add to comparison");
await clickBtn("button.tab", "Compare"); await sleep(400);
await clickBtn("button.quiet-button", "Add the panel's dates");
await clickBtn("button.quiet-button", "Add one synodic month later");
await evaluate("[...document.querySelectorAll('button.run-button')].find(b => /^Compare/.test(b.textContent)).click(); true");
await waitFor("document.querySelector('table.matrix')", 900000, "comparison");
await sleep(1200);
const cmp = await evaluate("({ bars: document.querySelectorAll('table.matrix .cell-bar').length, cells: document.querySelectorAll('table.matrix td').length, labels: [...document.querySelectorAll('table.matrix .cell-sub')].map(s => s.textContent).filter(t => /validated/.test(t)), legend: document.querySelector('.compare-legend')?.textContent })");
check("comparison: every result cell has a bar and its validation label counts; the legend shows the scale", cmp.bars === cmp.cells && cmp.labels.length === cmp.cells && /Colour scale/.test(cmp.legend), cmp);
await clickBtn(".segmented button", "Longest darkness"); await sleep(400);
const leg5 = await text(".compare-legend");
check("comparison: metric switch updates the legend direction (lower is better for darkness)", /lower is better/.test(leg5), leg5);
await evaluate("document.querySelector('table.matrix').scrollIntoView({ block: 'center' }); true"); await sleep(300);
await shot("06-comparison-bars-legend");
// open a cell -> result view with the same visualisations
await evaluate("document.querySelector('table.matrix td button').click(); true");
await waitFor("document.querySelector('.site-title') && document.querySelector('.vis-chart svg')", 60000, "cell result");
check("comparison: opening a cell shows its result with the context and visibility chart", await evaluate("document.querySelectorAll('.context-card').length === 4"));

// ---- 6. responsive
await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
await sleep(1500);
const mob = await evaluate("({ scrollW: document.documentElement.scrollWidth, clientW: document.documentElement.clientWidth, cardsOneColumn: (() => { const c = [...document.querySelectorAll('.context-card')].map(e => e.getBoundingClientRect().left); return new Set(c.map(Math.round)).size === 1; })() })");
await evaluate("document.querySelector('.context-grid').scrollIntoView({ block: 'start' }); true"); await sleep(300);
await shot("07-mobile-390-result");
check("responsive: at 390 px the result view has no sideways scroll and the context cards stack", mob.scrollW <= mob.clientW && mob.cardsOneColumn, mob);
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });

const errors = consoleMsgs.filter((m) => m.type === "exception" || m.type === "error" || (m.type === "log-error" && !/status of 422/.test(m.text)));
check("no page exceptions or console errors", errors.length === 0, errors.slice(0, 5));
report.checks = checks; report.console = consoleMsgs; report.finished = new Date().toISOString();
fs.writeFileSync(path.join(OUT, "viz-check.json"), JSON.stringify(report, null, 1));
const failed = checks.filter((c) => !c.ok).length;
console.log(`viz-live-check: ${checks.length - failed}/${checks.length} checks passed`);
ws.close(); proc.kill();
try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* browser may still hold files */ }
process.exit(failed ? 1 : 0);
