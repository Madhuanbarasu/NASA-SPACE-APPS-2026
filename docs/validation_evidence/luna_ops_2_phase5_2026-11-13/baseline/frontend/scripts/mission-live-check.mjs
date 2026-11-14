#!/usr/bin/env node
// Phase 5 prompt 4: live check of the mission dashboard in a real browser (Chrome/Edge headless through the DevTools
// Protocol, Node's built-in WebSocket; no packages). Needs the app running.
//
//   node scripts/mission-live-check.mjs --base http://127.0.0.1:8765 --out <dir>
//
// Every value the dashboard shows is compared with the API in the same page (GET /api/status, /api/coverage,
// /api/results/{id}). Workflows: Mission tab (lazy chunk, empty states, status, keyboard), selected site and coverage,
// quick navigation to the 3D Moon, map and local terrain (view kept across tab switches), analysis from the dashboard
// (figures, labels and uncertainty against the API result), deep links to the result sections (focus, reduced motion),
// candidate sites (add, select, analyse, reopen, remove), session analyses, an unsupported location, a failed coverage
// request, a real missing-data site (-60.02, 0) with the 3D terrain message fix, the comparison of the candidates,
// public mode, accessibility basics and the 390 px layout. Results in <out>/mission-check.json, screenshots in
// <out>/screenshots/; exit 1 if any check fails.
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const BASE = arg("--base", "http://127.0.0.1:8765");
const OUT = path.resolve(arg("--out", "mission-check"));
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

const text = (sel) => evaluate(`document.querySelector(${JSON.stringify(sel)})?.textContent || ''`);
const fmt3 = (lat, lon) => `${Math.abs(lat).toFixed(3)}° ${lat >= 0 ? "N" : "S"}, ${(((lon % 360) + 360) % 360).toFixed(3)}° E`;
const SEL = "section[aria-labelledby=mission-selected]", STATUS = "section[aria-labelledby=mission-status]",
  CUR = "section[aria-labelledby=mission-current]", CAND = "section[aria-labelledby=mission-candidates]",
  HIST = "section[aria-labelledby=mission-history]", CMP = "section[aria-labelledby=mission-comparison]";
const tab = async (name) => { await clickBtn("button.tab", name); await sleep(500); };
const toMission = async () => { await tab("Mission"); await waitFor("document.querySelector('.mission')", 20000, "mission view"); await sleep(300); };
const inMission = (sel, label) => evaluate(`(() => { const b = [...document.querySelectorAll(${JSON.stringify(sel + " button")})].find(e => e.textContent.trim() === ${JSON.stringify(label)} || e.getAttribute('aria-label') === ${JSON.stringify(label)}); if (!b) return null; if (b.disabled) return 'disabled'; b.click(); return 'clicked'; })()`);
const disabled = (sel, label) => evaluate(`(() => { const b = [...document.querySelectorAll(${JSON.stringify(sel + " button")})].find(e => e.textContent.trim() === ${JSON.stringify(label)} || e.getAttribute('aria-label') === ${JSON.stringify(label)}); return b ? b.disabled : null; })()`);
const resultId = () => evaluate("(document.querySelector('a[href$=\"/result.json\"]')?.getAttribute('href') || '').split('/')[3]");
const waitCoverage = (sel) => waitFor(`(() => { const t = document.querySelector(${JSON.stringify(sel)})?.textContent || ''; return t && !/^Checking/.test(t); })()`, 30000, "coverage " + sel);
const covText = (la, lo) => evaluate(`fetch('/api/coverage?lat=${la}&lon=${lo}').then(x => x.json())`);
async function waitResult(prevId) {
  await waitFor(`(() => { const a = document.querySelector('a[href$="/result.json"]'); return a && a.getAttribute('href').split('/')[3] !== ${JSON.stringify(prevId ?? "")}; })()`, 900000, "analysis result");
  await sleep(1500);
  const id = await resultId();
  const r = await evaluate(`fetch('/api/results/${id}').then(x => x.json())`);
  report.analyses.push({ lat: r.site.lat, lon: r.site.lon, start: r.window.start_utc, end: r.window.end_utc, id });
  return r;
}
const pct = (v) => (v == null ? "n/a" : `${v.toFixed(1)}%`);
const figs = () => evaluate(`Object.fromEntries([...document.querySelectorAll('${CUR} .mission-figures div')].map(d => [d.querySelector('dt').textContent, d.querySelector('dd').childNodes[0].textContent]))`);

// ---- 1. tab, lazy loading, empty states, status
const tabs = await evaluate("[...document.querySelectorAll('button.tab')].map(b => b.textContent)");
check("tabs: Mission is listed first and the app still opens on the Site tab", tabs[0] === "Mission" && (await evaluate("document.querySelector('#tab-site').getAttribute('aria-selected')")) === "true", tabs);
const missionReqBefore = requests.filter((u) => /MissionView-/.test(u)).length;
await toMission();
const missionReq = requests.filter((u) => /MissionView-/.test(u)).length;
check("lazy loading: the dashboard chunk loads only when the Mission tab is first opened, and opening it loads no three.js",
  missionReqBefore === 0 && missionReq === 1 && !requests.some((u) => /OrbitControls-/.test(u)), { missionReqBefore, missionReq });
const empty = await evaluate(`({ sel: document.querySelector('${SEL}').textContent, cand: document.querySelector('${CAND}').textContent, hist: document.querySelector('${HIST}').textContent, cur: document.querySelector('${CUR}').textContent, cmp: document.querySelector('${CMP}').textContent })`);
check("empty states: no site, no candidates, no analyses, no comparison, each explained",
  /No site selected/.test(empty.sel) && /No candidate sites yet/.test(empty.cand) && /appear here/.test(empty.hist) && /No analysis open/.test(empty.cur) && /No comparison has been run yet/.test(empty.cmp), empty);
check("empty states: Local terrain and Analysis are unavailable until there is a covered site or a result",
  (await disabled(".mission-nav", "Local terrain")) === true && (await disabled(".mission-nav", "Analysis")) === true);
const st = await evaluate("fetch('/api/status').then(x => x.json())");
const stLab = Object.values(st.labels ?? {}); const stOk = stLab.filter((l) => l.validation.startsWith("Validated")).length;
const stText = await text(STATUS);
check("status: kernels, terrain products, report and label counts come from GET /api/status", stText.includes(`frame ${st.kernels.frame}`)
  && stText.includes(Object.keys(st.terrain.levels).join(", ")) && (!st.validation || stText.includes(st.validation.run_utc))
  && stText.includes(`${stOk} validated, ${stLab.length - stOk} pending validation`), { stText: stText.slice(0, 300), stOk, n: stLab.length });
await shot("01-mission-empty");

// ---- 2. keyboard: the tab list stays one tab stop, arrows reach the new tab
await tab("Site");
await evaluate("document.querySelector('#tab-site').focus(); true");
await press("ArrowLeft");
const kb1 = await evaluate("({ active: document.activeElement.id, mission: !!document.querySelector('.mission') })");
await press("ArrowRight"); await press("ArrowRight");
const kb2 = await evaluate("({ active: document.activeElement.id, tabStops: [...document.querySelectorAll('button.tab')].filter(b => b.tabIndex === 0).length })");
check("keyboard: ArrowLeft from Site selects Mission, ArrowRight goes back through Site to Compare; one tab stop", kb1.active === "tab-mission" && kb1.mission && kb2.active === "tab-compare" && kb2.tabStops === 1, { kb1, kb2 });

// ---- 3. select Site01; overview of the selected site
await tab("Site");
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447"); await setValue("#start", "2026-11-14T00:00"); await setValue("#end", "2026-11-21T00:00");
await sleep(500);
await toMission();
await waitCoverage(`${SEL} .hint[aria-live]`);
const cov1 = await covText(-89.463163, 222.510447);
const sel1 = await text(SEL);
check("selected site: coordinates and the registered terrain levels from GET /api/coverage", sel1.includes(fmt3(-89.463163, 222.510447)) && sel1.includes(`Registered LOLA terrain covers this point: ${cov1.levels.join(", ")}.`), sel1.slice(0, 260));

// ---- 4. quick navigation; the explorer view survives tab switches
await inMission(".mission-nav", "3D Moon");
await waitFor("document.querySelector('.globe-stage canvas')", 30000, "globe");
const g1 = await evaluate("({ tab: document.querySelector('#tab-site').getAttribute('aria-selected'), pressed: [...document.querySelectorAll('.view-switch button')].find(b => b.getAttribute('aria-pressed') === 'true')?.textContent, focus: document.activeElement.id })");
await sleep(2500); await shot("02-nav-3d-moon");
await toMission(); await tab("Site");
const g2 = await evaluate("({ globe: !!document.querySelector('.globe-stage'), lat: document.querySelector('#lat').value, explorer: document.querySelector('.explorer-coords')?.textContent })");
check("navigation: 3D Moon opens the globe for the selected site; focus moves to the main region", g1.tab === "true" && /globe/i.test(g1.pressed ?? "") && g1.focus === "main", g1);
check("navigation state: the globe view and the selected site are kept after leaving and returning to the Site tab", g2.globe && g2.lat === "-89.463163" && g2.explorer === fmt3(-89.463163, 222.510447), g2);
await toMission(); await inMission(".mission-nav", "South polar map");
await waitFor("document.querySelector('.ol-viewport')", 30000, "map");
check("navigation: South polar map opens the map view", await evaluate("[...document.querySelectorAll('.view-switch button')].find(b => b.getAttribute('aria-pressed') === 'true')?.textContent === 'South polar map'"));
await toMission(); await inMission(".mission-nav", "Local terrain");
await waitFor("document.querySelector('.terrain-stats') || /Local terrain at/.test(document.querySelector('.pane-head h3')?.textContent || '')", 60000, "terrain preview");
await sleep(2500);
check("navigation: Local terrain opens the registered-terrain preview of the selected site", (await text(".pane-head h3")).includes(fmt3(-89.463163, 222.510447)), await text(".pane-head h3"));
await shot("03-nav-local-terrain");

// ---- 5. analyse from the dashboard; current analysis summary equals the API result
await toMission();
await inMission(SEL, "Analyse this site");
const r1 = await waitResult(null);
const resFigs = await evaluate("[...document.querySelectorAll('.figure')].map(f => Object.fromEntries([...f.querySelectorAll('dt')].map(dt => [dt.textContent, dt.nextElementSibling.textContent])))");
await toMission();
const f1 = await figs();
const sr = r1.provenance.parameters.rules.sunlit, dr = r1.provenance.parameters.rules.dte;
const s1 = r1.summary[`sun_${sr}`], e1 = r1.summary[`earth_${dr}`];
report.siteO1 = { figures: f1, resultViewFigures: resFigs };
check("current analysis: percentages equal the API summary (sunlit, Earth in view, both)", f1["Sunlit time"] === pct(s1.percent) && f1["Earth in view"] === pct(e1.percent) && f1["Sunlit and Earth in view"] === pct(r1.summary.overlap.percent), { f1, api: [s1.percent, e1.percent, r1.summary.overlap.percent] });
check("current analysis: durations equal the result view's figures (same API fields, same formatter)", f1["Longest darkness"] === resFigs[0]["Longest darkness"] && f1["Longest Earth gap"] === resFigs[1]["Longest gap"], { f1, dark: resFigs[0]["Longest darkness"], gap: resFigs[1]["Longest gap"] });
const chips = await evaluate(`[...document.querySelectorAll('${CUR} .label-row .chip')].map(c => c.textContent)`);
const apiOk = Object.values(r1.labels).filter((l) => l.validation.startsWith("Validated")).length;
check("current analysis: validation labels exactly as the API gives them (nothing Pending shown as Validated)", chips.length === Object.keys(r1.labels).length
  && chips.filter((c) => /validated$/i.test(c) && !/pending/i.test(c)).length === apiOk, { chips, apiOk });
const flags1 = await evaluate(`[...document.querySelectorAll('${CUR} .mission-flags li')].map(l => l.textContent)`);
check("current analysis: uncertainty from the API (unknown time, uncertain and near-field windows, sigma statement)",
  flags1[0].includes(`Uncertain sunlit windows: ${s1.uncertain_windows}.`) && flags1[0].includes(`near-field terrain: ${s1.near_field_windows ?? "n/a"}.`)
  && flags1.some((f) => (r1.horizon.sigma_deg ? /L_corr/.test(f) : /No horizon uncertainty/.test(f))), flags1);
const words = await evaluate("(() => { const m = document.querySelector('.mission').cloneNode(true); m.querySelectorAll('.site-coords, .mission-pad').forEach(e => e.remove()); return m.textContent; })()");
check("integrity: no score, probability, ranking or recommendation anywhere on the dashboard (outside the disclaimer)", !/score|probabilit|recommend|rank|best site/i.test(words));
await evaluate(`document.querySelector('${CUR}').scrollIntoView({ block: 'start' }); true`); await sleep(300);
await shot("04-mission-current-analysis");

// ---- 6. deep links to the detailed views (focus and scroll), also under reduced motion
for (const [label, id] of [["Visibility chart", "result-visibility"], ["Horizon panorama", "result-panorama"], ["3D terrain and map", "result-terrain"]]) {
  await toMission(); await inMission(CUR, label); await sleep(1500);
  const d = await evaluate(`({ active: document.activeElement.id, top: Math.round(document.getElementById('${id}').getBoundingClientRect().top), sameResult: (document.querySelector('a[href$="/result.json"]')?.getAttribute('href') || '').split('/')[3] })`);
  check(`deep link "${label}": opens the result at that section and moves focus to it`, d.active === id && d.top > -10 && d.top < 250 && d.sameResult === r1.id, d);
}
await shot("05-deep-link-terrain");
// scroll positions sampled every frame for 2.5 s after the click: smooth scrolling passes through many positions,
// reduced motion jumps once
const sampleScroll = async (label) => {
  await toMission();
  await evaluate("window.__s = []; (() => { const t0 = performance.now(); const f = () => { window.__s.push(document.getElementById('main').scrollTop + window.scrollY); if (performance.now() - t0 < 2500) requestAnimationFrame(f); }; requestAnimationFrame(f); })(); true");
  await inMission(CUR, label); await sleep(2800);
  return evaluate(`({ active: document.activeElement.id, top: Math.round(document.getElementById('result-tables').getBoundingClientRect().top), moves: window.__s.filter((v, i, a) => i > 0 && v !== a[i - 1]).length,
    maxStepShare: (() => { const a = window.__s, d = a.slice(1).map((v, i) => Math.abs(v - a[i])), tot = Math.abs(a[a.length - 1] - Math.min(...a)); return tot ? Math.round(100 * Math.max(...d) / tot) / 100 : 0; })(), reduce: matchMedia('(prefers-reduced-motion: reduce)').matches })`);
};
const sm = await sampleScroll("Events and data tables");
await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] });
const rm = await sampleScroll("Events and data tables");
check("reduced motion: the deep link scrolls smoothly by default (many positions) but jumps in one step (one move covers the whole distance) when reduced motion is preferred", !sm.reduce && sm.moves > 4 && rm.reduce && rm.maxStepShare >= 0.9 && rm.active === "result-tables" && rm.top > -10 && rm.top < 900 - 40, { smooth: sm, reduced: rm });
// (the section is last in the result view, so after the empty-space layout fix it ends in view rather than at the top:
//  only .main scrolls, the page itself no longer does; the requirement is that it is in view, focused, and reached in one step)
await send("Emulation.setEmulatedMedia", { features: [] });

// ---- 7. candidates: add, switch, analyse, reopen
await toMission();
await inMission(CAND, "Add the selected site");
await tab("Site");
if (await evaluate("!!document.querySelector('a[href$=\"/result.json\"]')")) { await clickBtn("button", "Back to the Moon explorer"); await sleep(500); }
await setValue("#lat", "-89.9"); await setValue("#lon", "0"); await sleep(500);
await toMission(); await waitCoverage(`${SEL} .hint[aria-live]`);
await inMission(CAND, "Add the selected site");
await waitFor(`document.querySelectorAll('${CAND} li').length === 2 && ![...document.querySelectorAll('${CAND} li .hint')].some(h => /^Checking/.test(h.textContent))`, 30000, "candidate coverage");
const cov2 = await covText(-89.9, 0);
const cand = await evaluate(`[...document.querySelectorAll('${CAND} li')].map(li => ({ t: li.textContent, sel: li.classList.contains('is-selected') }))`);
check("candidates: both sites listed with coverage from GET /api/coverage; the selected one is marked", cand.length === 2 && cand[0].t.includes(cov1.levels.join(", ")) && cand[1].t.includes(cov2.levels.join(", ")) && !cand[0].sel && cand[1].sel, cand);
check("candidates: the selected site cannot be added twice", (await disabled(CAND, "Add the selected site")) === true);
await evaluate(`document.querySelector('${CAND}').scrollIntoView({ block: 'start' }); true`); await sleep(300);
await shot("06-candidates");
await inMission(CAND, `Select ${fmt3(-89.463163, 222.510447)}`); await sleep(500);
const sw = await evaluate(`({ lat: document.querySelector('#lat').value, lon: document.querySelector('#lon').value, sel: document.querySelector('${SEL} .explorer-coords').textContent, marked: [...document.querySelectorAll('${CAND} li')].map(li => li.classList.contains('is-selected')) })`);
check("site switching: Select makes a candidate the selected site everywhere (sidebar, overview, marker)", sw.lat === "-89.463163" && sw.lon === "222.510447" && sw.sel === fmt3(-89.463163, 222.510447) && sw.marked[0] && !sw.marked[1], sw);
const prev = r1.id;
await inMission(CAND, `Analyse ${fmt3(-89.9, 0)}`);
const r2 = await waitResult(prev);
check("candidates: Analyse selects that candidate and runs its analysis (result for the candidate's coordinates)", Math.abs(r2.site.lat + 89.9) < 1e-6 && Math.abs(r2.site.lon) < 1e-6 && (await evaluate("document.querySelector('#lat').value")) === "-89.900000", { site: r2.site });
await toMission();
const hist = await evaluate(`[...document.querySelectorAll('${HIST} tbody tr')].map(tr => [...tr.cells].map(c => c.textContent))`);
const s2 = r2.summary[`sun_${r2.provenance.parameters.rules.sunlit}`], e2 = r2.summary[`earth_${r2.provenance.parameters.rules.dte}`];
check("session analyses: newest first, each row's figures and label counts equal its API result", hist.length === 2
  && hist[0][2] === pct(s2.percent) && hist[0][4] === pct(e2.percent) && hist[0][5] === pct(r2.summary.overlap.percent)
  && hist[1][2] === pct(s1.percent) && hist[1][4] === pct(e1.percent)
  && hist[1][6] === `${apiOk} validated, ${Object.keys(r1.labels).length - apiOk} pending`, hist);
await inMission(CAND, `Open the latest result for ${fmt3(-89.463163, 222.510447)}`);
await waitFor(`(document.querySelector('a[href$="/result.json"]')?.getAttribute('href') || '').includes('${r1.id}')`, 30000, "reopen");
check("candidates: Open result reopens that site's analysis from this session", true);
await toMission();
await inMission(HIST, `Open the result for ${r2.site.name ?? fmt3(-89.9, 0)}`);
await waitFor(`(document.querySelector('a[href$="/result.json"]')?.getAttribute('href') || '').includes('${r2.id}')`, 30000, "history open");
check("session analyses: Open shows that result in the Site tab", (await evaluate("document.querySelector('#tab-site').getAttribute('aria-selected')")) === "true");

// ---- 8. unsupported location and an API error
await clickBtn("button", "Back to the Moon explorer"); await sleep(400);
await setValue("#lat", "-30"); await setValue("#lon", "10"); await sleep(400);
await toMission(); await waitCoverage(`${SEL} .hint[aria-live]`);
const covU = await covText(-30, 10);
const u = await evaluate(`({ t: document.querySelector('${SEL} .hint[aria-live]').textContent })`);
check("unsupported location: the backend's reason is shown and terrain and analysis are unavailable", u.t.includes(covU.reason) && !covU.covered
  && (await disabled(SEL, "Analyse this site")) && (await disabled(SEL, "Inspect local terrain")) && (await disabled(".mission-nav", "Local terrain")), { u, reason: covU.reason });
await inMission(CAND, "Add the selected site");
await waitFor(`document.querySelectorAll('${CAND} li').length === 3 && !/^Checking/.test(document.querySelector('${CAND} li:nth-child(3) p.hint').textContent)`, 30000, "unsupported candidate");
const cu = await evaluate(`document.querySelector('${CAND} li:nth-child(3)').textContent`);
check("unsupported candidate: listed with the backend's reason; its Analyse is disabled", cu.includes(covU.reason) && (await disabled(CAND, `Analyse ${fmt3(-30, 10)}`)) === true, cu.slice(0, 200));
await shot("07-unsupported");
await inMission(CAND, `Remove ${fmt3(-30, 10)} from the candidates`); await sleep(300);
check("candidates: Remove takes a site off the list", (await evaluate(`document.querySelectorAll('${CAND} li').length`)) === 2);
await send("Network.setBlockedURLs", { urls: ["*/api/coverage*"] });
await tab("Site"); await setValue("#lat", "-75"); await setValue("#lon", "20"); await sleep(300);
await toMission(); await waitCoverage(`${SEL} .hint[aria-live]`);
const errT = await text(`${SEL} .hint[aria-live]`);
check("error state: a failed coverage request is reported, and terrain and analysis stay unavailable", /Coverage could not be checked/.test(errT) && (await disabled(SEL, "Analyse this site")), errT);
await send("Network.setBlockedURLs", { urls: [] });

// ---- 9. missing data: (-60.02, 0), real lower-bound horizon and null Earth fractions; the 3D terrain message
await tab("Site"); await setValue("#lat", "-60.02"); await setValue("#lon", "0"); await setValue("#start", "2026-11-14T00:00"); await setValue("#end", "2026-11-15T00:00");
await sleep(500); await toMission(); await waitCoverage(`${SEL} .hint[aria-live]`);
await inMission(SEL, "Analyse this site");
const r3 = await waitResult(r2.id);
await waitFor("document.querySelector('#result-terrain .pane-message')", 60000, "terrain message");
const tm = await evaluate(`(() => { const pane = document.getElementById('result-terrain').children[1]; const msg = pane.querySelector('.pane-message'); if (!msg) return { msg: false };
  pane.scrollIntoView({ block: 'center' }); const body = msg.parentElement.getBoundingClientRect(), r = msg.getBoundingClientRect(); const cs = getComputedStyle(msg);
  const pts = [[0.5, 0.5], [0.2, 0.3], [0.8, 0.7], [0.5, 0.15], [0.5, 0.85]].map(([fx, fy]) => document.elementFromPoint(r.left + fx * r.width, r.top + fy * r.height));
  return { msg: true, text: msg.textContent, role: msg.getAttribute('role'), covers: Math.abs(r.width - body.width) < 2 && Math.abs(r.height - body.height) < 2, bg: cs.backgroundColor, z: cs.zIndex,
    onTop: pts.every(e => msg.contains(e)) }; })()`);
await sleep(600);
await shot("08-terrain3d-message-no-marker-overlap");
check("3D terrain fix: when no product covers the window, the backend's message covers the pane (opaque, on top) so no Earth or Sun marker is drawn over it",
  tm.msg && tm.role === "status" && tm.covers && tm.onTop && !/rgba\(.*, 0\)|transparent/.test(tm.bg) && tm.z === "3", tm);
await toMission();
const flags3 = await evaluate(`[...document.querySelectorAll('${CUR} .mission-flags li')].map(l => l.textContent)`);
const e3 = r3.summary[`earth_${r3.provenance.parameters.rules.dte}`];
check("missing data: lower-bound horizon share and unknown Earth time reported from the API, never filled", r3.horizon.incomplete_share > 0
  && flags3.some((f) => f.includes(`${(100 * r3.horizon.incomplete_share).toFixed(1)} % of bins`)) && (e3.unknown_hours > 0 ? flags3.some((f) => /Earth-in-view time unknown/.test(f)) : true), { flags3, inc: r3.horizon.incomplete_share, eu: e3.unknown_hours });
const chips3 = await evaluate(`[...document.querySelectorAll('${CUR} .label-row .chip')].map(c => c.textContent)`);
check("missing data: terrain-dependent quantities stay Pending exactly as the API gives them", ["horizon", "disk_visibility", "events", "power_indicator"].every((k) => !r3.labels[k].validation.startsWith("Validated"))
  && chips3.filter((c) => /pending/i.test(c)).length === Object.values(r3.labels).filter((l) => !l.validation.startsWith("Validated")).length, chips3);
await shot("09-mission-missing-data");

// ---- 10. comparison of the candidates
await inMission(CAND, "Compare candidates"); await sleep(500);
check("comparison: Compare candidates opens the Compare tab with the candidate sites", (await evaluate("document.querySelector('#tab-compare').getAttribute('aria-selected')")) === "true");
await tab("Site"); await setValue("#start", "2026-11-14T00:00"); await setValue("#end", "2026-11-21T00:00"); await sleep(300); await tab("Compare");
await clickBtn("button.quiet-button", "Add the panel's dates");
await clickBtn("button.quiet-button", "Add one synodic month later");
await evaluate("[...document.querySelectorAll('button.run-button')].find(b => /^Compare/.test(b.textContent)).click(); true");
await waitFor("document.querySelector('table.matrix')", 900000, "comparison");
await sleep(800);
await toMission();
const cmpT = await text(CMP);
check("comparison: the dashboard reports the comparison that ran (2 sites × 2 windows) and links to it", /2 sites × 2 windows compared/.test(cmpT), cmpT);
await inMission(CMP, "Open the comparison"); await sleep(400);
check("comparison: Open the comparison returns to its table", await evaluate("!!document.querySelector('table.matrix') && document.querySelector('#tab-compare').getAttribute('aria-selected') === 'true'"));

// ---- 11. public mode, accessibility basics, responsive
await toMission();
await clickBtn(".mode-switch button", "Public"); await sleep(300);
const pub = await evaluate(`[...document.querySelectorAll('${CUR} .mission-links button')].map(b => b.textContent)`);
await clickBtn(".mode-switch button", "Technical"); await sleep(300);
check("public mode: links only to sections that exist in that mode (no data tables link)", !pub.includes("Events and data tables") && pub.length === 4, pub);
const ax = await evaluate(`(() => { const m = document.querySelector('.mission'); const ctl = [...m.querySelectorAll('button, a[href], input, select')];
  const unnamed = ctl.filter(e => !(e.getAttribute('aria-label') || e.textContent.trim())).length;
  const ids = [...document.querySelectorAll('[id]')].map(e => e.id); const dup = ids.filter((x, i) => ids.indexOf(x) !== i);
  const h = [...m.querySelectorAll('h1, h2, h3')].map(e => e.tagName);
  const secs = [...m.querySelectorAll('section[aria-labelledby]')].every(s => document.getElementById(s.getAttribute('aria-labelledby')));
  return { controls: ctl.length, unnamed, dup, h1: h.filter(x => x === 'H1').length, h2: h.filter(x => x === 'H2').length, secs, caption: !!m.querySelector('table caption') }; })()`);
check("accessibility: every control named, unique ids, one h1 with h2 sections, labelled regions, table caption", ax.unnamed === 0 && ax.dup.length === 0 && ax.h1 === 1 && ax.h2 === 6 && ax.secs && ax.caption, ax);
await evaluate("document.querySelector('.mission-nav button:not([disabled])').focus(); true");
const fo = await evaluate("(() => { const cs = getComputedStyle(document.activeElement); return { tag: document.activeElement.tagName, outline: cs.outlineStyle, w: cs.outlineWidth, shadow: cs.boxShadow }; })()");
check("accessibility: dashboard buttons show a focus indicator", fo.tag === "BUTTON" && ((fo.outline !== "none" && fo.w !== "0px") || fo.shadow !== "none"), fo);
await evaluate("window.scrollTo(0, 0); document.querySelector('.main').scrollTo?.(0, 0); true");
await shot("10-mission-desktop");
await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
await sleep(1500);
const mob = await evaluate(`({ scrollW: document.documentElement.scrollWidth, clientW: document.documentElement.clientWidth,
  oneColumn: new Set([...document.querySelectorAll('.mission-card')].map(e => Math.round(e.getBoundingClientRect().left))).size === 1,
  overflow: [...document.querySelectorAll('.mission *')].filter(e => e.getBoundingClientRect().right > document.documentElement.clientWidth + 1 && !e.closest('.table-scroll')).length })`);
await evaluate("document.querySelector('.mission').scrollIntoView({ block: 'start' }); true"); await sleep(300);
await shot("11-mission-mobile-390");
check("responsive: at 390 px the dashboard has no sideways scroll and the cards stack in one column (tables scroll inside their box)", mob.scrollW <= mob.clientW && mob.oneColumn && mob.overflow === 0, mob);
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });

const errors = consoleMsgs.filter((m) => m.type === "exception" || m.type === "error" || (m.type === "log-error" && !/status of 422|ERR_BLOCKED_BY_CLIENT/.test(m.text)));
check("no page exceptions or console errors (apart from the deliberately blocked coverage request)", errors.length === 0, errors.slice(0, 5));
report.checks = checks; report.console = consoleMsgs; report.finished = new Date().toISOString();
fs.writeFileSync(path.join(OUT, "mission-check.json"), JSON.stringify(report, null, 1));
const failed = checks.filter((c) => !c.ok).length;
console.log(`mission-live-check: ${checks.length - failed}/${checks.length} checks passed`);
ws.close(); proc.kill();
try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* browser may still hold files */ }
process.exit(failed ? 1 : 0);
