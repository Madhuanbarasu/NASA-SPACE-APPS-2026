
// Pre-Phase 7 corrections check (AUD-01, AUD-04) and AUD-05 investigation. One headless browser; appended to the
// Phase 1 CDP harness (docs/validation_evidence/luna_ops_2_phase1_2026-11-13/cdp_harness.txt).
// Usage: node corrections.mjs --base <url> --out <dir> --label before|after [--skip-analysis]
// Read only: it types coordinates, runs one landing screening of Site01 (default settings) and reads the page.
const LABEL = arg("--label", "run");
const T0 = Date.now();
const net = new Map();               // requestId -> { url, t, status, done, failed }
ws.addEventListener("message", (m) => {
  const msg = JSON.parse(m.data); const p = msg.params;
  if (msg.method === "Network.requestWillBeSent") net.set(p.requestId, { url: p.request.url, method: p.request.method, t: Date.now() - T0 });
  else if (msg.method === "Network.responseReceived") { const r = net.get(p.requestId); if (r) r.status = p.response.status; }
  else if (msg.method === "Network.loadingFinished") { const r = net.get(p.requestId); if (r) r.done = Date.now() - T0; }
  else if (msg.method === "Network.loadingFailed") { const r = net.get(p.requestId); if (r) r.failed = p.errorText; }
});
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable"); await send("Network.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return false; const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
const size = (w, h) => send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
const shotVP = async (name) => { const { data } = await send("Page.captureScreenshot", { format: "png" }); fs.writeFileSync(path.join(OUT, "screenshots", `${name}.png`), Buffer.from(data, "base64")); };
const shotClip = async (name, sel) => {
  const r = await evaluate(`(() => { const b = document.querySelector(${JSON.stringify(sel)})?.getBoundingClientRect(); return b ? { x: b.left, y: b.top, width: b.width, height: b.height } : null; })()`);
  if (!r) return null;
  const { data } = await send("Page.captureScreenshot", { format: "png", clip: { ...r, scale: 1 } });
  fs.writeFileSync(path.join(OUT, "screenshots", `${name}.png`), Buffer.from(data, "base64")); return r;
};
// the element's nearest scrolling ancestor, so the check works whichever element scrolls the view
const SCROLLER = `(el) => { let e = el; while (e) { const s = getComputedStyle(e); if (/(auto|scroll)/.test(s.overflowY) && e.scrollHeight > e.clientHeight) return e; e = e.parentElement; } return document.scrollingElement; }`;
const scrollEl = (sel, block, extra = 0) => evaluate(`(() => { const el = document.querySelector(${JSON.stringify(sel)}); if (!el) return false;
  el.scrollIntoView({ block: ${JSON.stringify(block)} }); (${SCROLLER})(el).scrollBy(0, ${extra}); return true; })()`);
const out = { label: LABEL, base: BASE, started: new Date().toISOString(), aud01: [], analysis: null, landing: {}, aud05: {} };

await size(1440, 900);
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(1000);

// ------------------------------------------------------------------ AUD-01: coordinate validation in the sidebar
const CASES = [
  ["valid Site01", "-89.463163", "222.510447", "valid"],
  ["latitude -95", "-95", "222.510447", "invalid"],
  ["latitude 95", "95", "222.510447", "invalid"],
  ["latitude -90.0001", "-90.0001", "0", "invalid"],
  ["latitude -90 (edge)", "-90", "0", "valid"],
  ["longitude 400", "-89.463163", "400", "invalid"],
  ["longitude -361", "-89.463163", "-361", "invalid"],
  ["longitude 360 (edge)", "-85", "360", "valid"],
  ["longitude -10 (west, accepted)", "-85", "-10", "valid"],
  ["latitude not a number", "abc", "222.510447", "invalid"],
  ["latitude empty", "", "222.510447", "empty"],
  ["valid again (Site01)", "-89.463163", "222.510447", "valid"],
];
for (const [name, lat, lon, expect] of CASES) {
  const n0 = Date.now() - T0, c0 = consoleMsgs.length;
  await setValue("#lat", lat); await setValue("#lon", lon);
  await sleep(expect === "valid" ? 2500 : 1600);   // > 350 ms debounce plus the server's reply
  const ui = await evaluate(`({ latInvalid: document.querySelector('#lat').getAttribute('aria-invalid'), lonInvalid: document.querySelector('#lon').getAttribute('aria-invalid'),
    latValue: document.querySelector('#lat').value, lonValue: document.querySelector('#lon').value,
    hint: document.querySelector('#coord-hint')?.textContent, hintClass: document.querySelector('#coord-hint')?.className,
    analyseDisabled: document.querySelector('.sidebar .run-button')?.disabled, addToCompareDisabled: document.querySelector('.sidebar .quiet-button')?.disabled })`);
  const cov = [...net.values()].filter((r) => r.t >= n0 && /\/api\/coverage/.test(r.url)).map((r) => ({ url: r.url.replace(BASE, ""), status: r.status ?? null, failed: r.failed ?? null }));
  out.aud01.push({ name, lat, lon, expect, ...ui, coverageRequests: cov, newConsole: consoleMsgs.slice(c0) });
}
await shotVP("aud01-valid-1440");
await setValue("#lat", "-95"); await sleep(1600); await shotVP("aud01-latitude-minus95-1440");
await setValue("#lat", "-89.463163"); await sleep(2500);

// analysis still works for valid coordinates (Site01, default window; cached on this server when available)
if (!process.argv.includes("--skip-analysis")) {
  const t = Date.now();
  await waitFor("!document.querySelector('.sidebar .run-button')?.disabled", 30000, "Analyse enabled");
  await evaluate("document.querySelector('.sidebar .run-button').click(); true");
  try {
    await waitFor("document.querySelector('.figures')", 300000, "analysis");
    await sleep(800);
    out.analysis = { ok: true, ms: Date.now() - t, figures: await evaluate(`[...document.querySelectorAll('.figures .figure')].map(f => (f.querySelector('h3')?.textContent || '') + ' ' + (f.querySelector('.big')?.textContent || ''))`),
      labels: await evaluate(`[...document.querySelectorAll('.label-chip, .chip')].slice(0, 8).map(e => e.textContent.trim())`) };
  } catch (e) { out.analysis = { ok: false, error: String(e.message || e) }; }
}

// ------------------------------------------------------------------ Landing: one screening of Site01 (defaults)
await evaluate("document.querySelector('#tab-landing').click(); true"); await sleep(800);
await waitFor("document.querySelector('.landing-run') && !document.querySelector('.landing-run').disabled", 60000, "landing run enabled");
const tRun = Date.now();
await evaluate("document.querySelector('.landing-run').click(); true");
await waitFor("document.querySelector('section[aria-labelledby=landing-footprint]') && document.querySelector('.landing-map canvas')", 300000, "landing screening");
out.landing.runMs = Date.now() - tRun;
const assessReq = [...net.entries()].filter(([, r]) => /\/api\/landing\/assess/.test(r.url)).pop();
let assessment = null;
if (assessReq) { try { const b = await send("Network.getResponseBody", { requestId: assessReq[0] }); assessment = JSON.parse(b.body); } catch { /* body evicted */ } }
out.landing.assessment = assessment ? { id: assessment.id, extent_xy_m: assessment.extent_xy_m, config: assessment.config } : null;

const MEASURE = `(() => {
  const r = (e) => e.getBoundingClientRect();
  const cards = [...document.querySelectorAll('.landing .landing-card')];
  const res = {};
  for (const c of cards) {
    const id = (c.getAttribute('aria-labelledby') || 'card').replace('landing-', ''); const b = r(c);
    const below = cards.map(r).filter(o => o.top >= b.bottom - 1 && o.left < b.right - 1 && o.right > b.left + 1).map(o => o.top);
    const content = [...c.children].reduce((m, k) => Math.max(m, r(k).bottom), b.top);
    const pad = parseFloat(getComputedStyle(c).paddingBottom) || 0;
    res[id] = { top: Math.round(b.top), h: Math.round(b.height), left: Math.round(b.left), w: Math.round(b.width),
      blankBelow: below.length ? Math.round(Math.min(...below) - b.bottom) : null, emptyInsideBelowContent: Math.round(b.bottom - content - pad) };
  }
  const cols = [...document.querySelectorAll('.landing-col')].map(c => { const b = r(c); const last = c.lastElementChild ? r(c.lastElementChild) : b;
    return { cls: c.className, top: Math.round(b.top), bottom: Math.round(b.bottom), lastCardBottom: Math.round(last.bottom), spaceBelowLastCard: Math.round(b.bottom - last.bottom) }; });
  const overlaps = [];
  for (let i = 0; i < cards.length; i++) for (let j = i + 1; j < cards.length; j++) {
    const a = r(cards[i]), b = r(cards[j]);
    if (a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1) overlaps.push(i + '-' + j);
  }
  const outside = [...document.querySelectorAll('.landing *')].filter(e => { const b = r(e); return b.width > 0 && b.right > document.documentElement.clientWidth + 1; }).length;
  const pane = document.querySelector('.landing-map.pane-body');
  return { cards: res, cols, overlaps, outside, mapPaneH: pane ? Math.round(r(pane).height) : null, twoColumn: !!document.querySelector('.landing-band'),
    hscroll: document.documentElement.scrollWidth > document.documentElement.clientWidth }; })()`;
for (const [w, h] of [[1920, 1080], [1600, 900], [1440, 900], [1280, 800], [1024, 768], [390, 844], [320, 640]]) {
  await size(w, h); await sleep(1500);
  await scrollEl(".landing", "start");
  await sleep(300);
  out.landing[`${w}`] = await evaluate(MEASURE);
  if ([1920, 1440, 1024, 390].includes(w)) {
    // the bottom of the selected-site/footprint column with what follows it in view
    await scrollEl("section[aria-labelledby=landing-footprint]", "end", Math.round(h * 0.35)); await sleep(400);
    await shotVP(`landing-${w}-footprint-bottom`);
  }
}

// ------------------------------------------------------------------ AUD-05: the hazard map at 1920 px (investigation)
await size(1920, 1080); await sleep(1500);
await scrollEl("section[aria-labelledby=landing-map]", "start"); await sleep(400);
const radio = (v) => evaluate(`(() => { const e = document.querySelector('input[name=ls-raster][value=${v}]'); if (!e || e.disabled) return false; e.click(); return true; })()`);
const opacity = (v) => evaluate(`(() => { const e = document.querySelector('.landing-layers input[type=range]'); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  set.call(e, ${JSON.stringify(String(v))}); e.dispatchEvent(new Event('input', { bubbles: true })); return e.value; })()`);
const host = ".landing-map.pane-body";
const a5 = out.aud05;
a5.hostRect = await evaluate(`(() => { const b = document.querySelector(${JSON.stringify(host)}).getBoundingClientRect(); return { x: b.left, y: b.top, width: b.width, height: b.height }; })()`);
a5.defaultOpacity = await evaluate("document.querySelector('.landing-layers input[type=range]')?.value");
a5.defaultRaster = await evaluate("document.querySelector('input[name=ls-raster]:checked')?.value");
a5.tileMeta = await evaluate("fetch('/api/tiles/meta').then(r => r.json())");
const shots = [];
const snap = async (name) => { const t = Date.now() - T0; const r = await shotClip(`aud05-${name}`, host); shots.push({ name: `aud05-${name}`, t, rect: r }); };
await snap("slope-default-t0");
await sleep(15000); await snap("slope-default-t15s");
await radio("none"); await sleep(2000); await snap("none-t2s");
await sleep(20000); await snap("none-t22s");
await radio("slope"); await opacity(1); await sleep(2000); await snap("slope-opacity100");
await opacity(0.2); await sleep(1500); await snap("slope-opacity20");
await radio("coverage"); await opacity(1); await sleep(2000); await snap("coverage-opacity100");
await radio("elevation"); await sleep(2000); await snap("elevation-opacity100");
await radio("slope"); await opacity(a5.defaultOpacity); await sleep(1500);
a5.shots = shots;
a5.tileRequests = [...net.values()].filter((r) => /\/api\/tiles\/\d+\//.test(r.url)).map((r) => ({ url: r.url.replace(BASE, ""), t: r.t, done: r.done ?? null, status: r.status ?? null, failed: r.failed ?? null }));
a5.layerRequests = [...net.values()].filter((r) => /\/api\/landing\/.*\/layer\//.test(r.url)).map((r) => ({ url: r.url.replace(BASE, ""), status: r.status ?? null }));
// save the tiles and layer PNGs the page used, for offline analysis (plain GETs of the same URLs)
fs.mkdirSync(path.join(OUT, "tiles"), { recursive: true });
for (const u of new Set([...a5.tileRequests.map((r) => r.url), ...a5.layerRequests.map((r) => r.url)])) {
  try { const res = await fetch(BASE + u); const b = Buffer.from(await res.arrayBuffer());
    fs.writeFileSync(path.join(OUT, "tiles", u.replace(/^\/api\//, "").replace(/[/?=]/g, "_")), b); } catch { /* skip */ }
}

out.console = consoleMsgs.filter((x) => x.type === "exception" || x.type === "error" || x.type === "log-error" || x.type === "warning" || x.type === "log-warning");
out.failedRequests = [...net.values()].filter((r) => (r.status ?? 0) >= 400 || r.failed).map((r) => ({ url: r.url.replace(BASE, ""), status: r.status ?? null, failed: r.failed ?? null }));
out.finished = new Date().toISOString();
fs.writeFileSync(path.join(OUT, `corrections-${LABEL}.json`), JSON.stringify(out, null, 1));
console.log(JSON.stringify({ label: LABEL, aud01: out.aud01.map((c) => [c.name, c.latInvalid, c.lonInvalid, c.coverageRequests.length, c.analyseDisabled]),
  analysis: out.analysis && { ok: out.analysis.ok, ms: out.analysis.ms }, landing1920: out.landing["1920"]?.cols, runMs: out.landing.runMs,
  tiles: a5.tileRequests.length, failed: out.failedRequests, console: out.console.length }, null, 1));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
