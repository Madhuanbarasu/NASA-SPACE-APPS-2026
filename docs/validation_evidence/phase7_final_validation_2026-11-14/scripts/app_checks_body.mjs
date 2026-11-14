
// Phase 7 targeted application checks: what the existing live suites do not cover, or covered with expectations that
// predate later approved redesigns. One headless browser; appended to the Phase 1 CDP harness. Each check is isolated
// (a failure is recorded, the run continues). RF values and relay orbit are ILLUSTRATIVE inputs, not hardware data.
const results = [];
const T0 = Date.now();
const net = new Map();
ws.addEventListener("message", (m) => { const msg = JSON.parse(m.data); const p = msg.params;
  if (msg.method === "Network.requestWillBeSent") net.set(p.requestId, { url: p.request.url, method: p.request.method, t: Date.now() - T0 });
  else if (msg.method === "Network.responseReceived") { const r = net.get(p.requestId); if (r) r.status = p.response.status; } });
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable"); await send("Network.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return false; const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
const setSelect = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return false; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
const size = (w, h) => send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
const shotVP = async (name) => { const { data } = await send("Page.captureScreenshot", { format: "png" }); fs.writeFileSync(path.join(OUT, "screenshots", `${name}.png`), Buffer.from(data, "base64")); return `screenshots/${name}.png`; };
const hashOf = async (sel) => { const r = await evaluate(`(() => { const b = document.querySelector(${JSON.stringify(sel)})?.getBoundingClientRect(); return b ? { x: b.left, y: b.top, width: b.width, height: b.height } : null; })()`);
  if (!r) return null; const { data } = await send("Page.captureScreenshot", { format: "png", clip: { ...r, scale: 1 } }); let h = 0; for (let i = 0; i < data.length; i += 7) h = (h * 31 + data.charCodeAt(i)) | 0; return h; };
async function drag(sel, dx, dy) {
  const r = await evaluate(`(() => { const b = document.querySelector(${JSON.stringify(sel)}).getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; })()`);
  await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: r[0], y: r[1] });
  await send("Input.dispatchMouseEvent", { type: "mousePressed", x: r[0], y: r[1], button: "left", buttons: 1, clickCount: 1 });
  for (let k = 1; k <= 10; k++) { await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: r[0] + dx * k / 10, y: r[1] + dy * k / 10, button: "left", buttons: 1 }); await sleep(30); }
  await send("Input.dispatchMouseEvent", { type: "mouseReleased", x: r[0] + dx, y: r[1] + dy, button: "left", buttons: 0, clickCount: 1 });
  await sleep(800);
}
async function check(id, area, steps, expected, fn) {
  const c0 = consoleMsgs.length; let actual, ok, err = null;
  try { const r = await fn(); actual = r.actual; ok = !!r.ok; } catch (e) { ok = false; err = String(e.message || e); }
  const cons = consoleMsgs.slice(c0).filter((x) => /error|exception/.test(x.type));
  results.push({ id, area, steps, expected, actual, error: err, console_errors: cons, result: ok ? "Pass" : "Fail" });
  console.log(`${ok ? "PASS" : "FAIL"} ${id} ${area}: ${JSON.stringify(actual ?? err).slice(0, 220)}`);
}
const fresh = async (w = 1440, h = 900) => { await size(w, h); await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(1000); };
const analyse = async (lat, lon, start, end) => {
  await evaluate("document.querySelector('#tab-site').click(); true"); await sleep(400);
  await setValue("#lat", lat); await setValue("#lon", lon); await setValue("#start", start); await setValue("#end", end);
  await waitFor("!document.querySelector('.sidebar .run-button').disabled", 60000, "analyse enabled");
  const before = await evaluate(`[...document.querySelectorAll('a[href*="/api/results/"]')].map(a => a.getAttribute('href')).find(Boolean) || null`);
  await evaluate("document.querySelector('.sidebar .run-button').click(); true");
  await waitFor(`(() => { const h = [...document.querySelectorAll('a[href*="/api/results/"]')].map(a => a.getAttribute('href')).find(Boolean); return h && h !== ${JSON.stringify(before)} && document.querySelector('.figures'); })()`, 900000, "analysis");
  await sleep(1200);
  return evaluate(`[...document.querySelectorAll('a[href*="/api/results/"]')].map(a => a.getAttribute('href').match(/results\\/([0-9a-f]+)/)?.[1]).find(Boolean)`);
};

// ---- T1 keyboard tabs on wide screens (>= 1600 px: tabs in the bar; Phase 6 moved the compact menu below 1600 px)
await fresh(1700, 1000);
await check("T1", "Navigation", ["1700 px", "focus the selected tab", "ArrowRight, ArrowLeft, Home, End"],
  "arrow keys move selection between tabs; exactly one tab is in the Tab order (roving tabindex)", async () => {
  await evaluate("document.querySelector('button.tab[aria-selected=true]').focus(); true");
  const sel = () => evaluate("document.querySelector('button.tab[aria-selected=true]')?.textContent.trim()");
  const s0 = await sel(); await press("ArrowRight"); const s1 = await sel(); await press("ArrowLeft"); const s2 = await sel();
  await press("End"); const s3 = await sel(); await press("Home"); const s4 = await sel();
  const stops = await evaluate("[...document.querySelectorAll('button.tab')].filter(b => b.tabIndex === 0).length");
  const visible = await evaluate("getComputedStyle(document.querySelector('#primary-nav')).display !== 'none' && !document.querySelector('.nav-toggle:not([hidden])')?.offsetParent");
  return { actual: { s0, s1, s2, s3, s4, tabStops: stops, tabsInBar: visible }, ok: s1 !== s0 && s2 === s0 && s3 === "Guide" && s4 === "Mission" && stops === 1 };
});

// ---- T2 / T3 map: click north of 60 S; loading note with a slow network
await fresh(1440, 900);
await evaluate("document.querySelector('#tab-site').click(); true"); await sleep(600);
await check("T2", "South polar map", ["default map view", "click 6 px inside the pane's top-left corner (outside the 60 S circle)"],
  "no site is set; the note says the point is north of 60 S", async () => {
  await waitFor("document.querySelector('.map-host canvas')", 30000, "map"); await sleep(2500);
  const before = await evaluate("document.querySelector('#lat').value");
  const r = await evaluate("(() => { const b = document.querySelector('.map-host').getBoundingClientRect(); return [b.left + 6, b.top + 6]; })()");
  await mouseClick(r[0], r[1]); await sleep(800);
  const after = await evaluate("document.querySelector('#lat').value");
  const note = await evaluate("document.querySelector('.pane-note')?.textContent || ''");
  return { actual: { latBefore: before, latAfter: after, note: note.slice(-140) }, ok: after === before && /north of 60° S, outside the south polar map/.test(note) };
});
await check("T3", "South polar map", ["emulate 1.5 s latency", "reload", "read the map note while tiles are in flight"],
  "the note says how many terrain tiles are loading", async () => {
  await send("Network.emulateNetworkConditions", { offline: false, latency: 1500, downloadThroughput: 200000, uploadThroughput: 200000 });
  await send("Network.setCacheDisabled", { cacheDisabled: true });
  await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 90000, "status");
  await evaluate("document.querySelector('#tab-site').click(); true");
  let seen = null; const t = Date.now();
  while (Date.now() - t < 20000) { const n = await evaluate("document.querySelector('.pane-note')?.textContent || ''"); if (/Loading \d+ terrain tiles?/.test(n)) { seen = n; break; } await sleep(150); }
  const chip = await evaluate("document.querySelector('.map-status')?.textContent || null");
  await send("Network.emulateNetworkConditions", { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
  await send("Network.setCacheDisabled", { cacheDisabled: false });
  return { actual: { note: seen?.slice(-120) ?? null, statusChip: chip }, ok: !!seen };
});

// ---- T4-T6 dragging: map, globe, local terrain
await fresh(1440, 900);
await evaluate("document.querySelector('#tab-site').click(); true");
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447"); await sleep(2500);
await check("T4", "South polar map", ["drag the map 150 px right and 80 px down"], "the view moves (map image changes); no site is set by a drag", async () => {
  await waitFor("document.querySelector('.map-host canvas')", 30000, "map"); await sleep(2500);
  const h0 = await hashOf(".map-host"); const lat0 = await evaluate("document.querySelector('#lat').value");
  await drag(".map-host", 150, 80); await sleep(1500);
  const h1 = await hashOf(".map-host"); const lat1 = await evaluate("document.querySelector('#lat').value");
  return { actual: { imageChanged: h0 !== h1, latBefore: lat0, latAfter: lat1 }, ok: h0 !== h1 && lat0 === lat1 };
});
await check("T5", "3D Moon globe", ["switch to the globe", "drag 200 px left"], "the globe rotates: the centre readout changes", async () => {
  await evaluate("(() => { const b = [...document.querySelectorAll('.view-switch button')].find(x => x.textContent.trim() === '3D Moon globe'); b.click(); return true; })()");
  await waitFor("document.querySelector('.globe-host canvas')", 90000, "globe"); await sleep(3500);
  const c0 = await evaluate("document.querySelector('.globe-readout-mini span')?.textContent || ''");
  await drag(".globe-host", -200, 0); await sleep(1500);
  const c1 = await evaluate("document.querySelector('.globe-readout-mini span')?.textContent || ''");
  return { actual: { before: c0, after: c1 }, ok: !!c0 && c0 !== c1 };
});
await check("T6", "Local terrain", ["switch to Local terrain", "drag 160 px left"], "the 3D terrain view rotates (image changes)", async () => {
  await evaluate("(() => { const b = [...document.querySelectorAll('.view-switch button')].find(x => x.textContent.trim() === 'Local terrain'); b.click(); return true; })()");
  await waitFor("document.querySelector('.terrain-preview .three-host canvas')", 120000, "terrain"); await sleep(3500);
  const h0 = await hashOf(".terrain-preview .three-host"); await drag(".terrain-preview .three-host", -160, 0); await sleep(1200);
  const h1 = await hashOf(".terrain-preview .three-host");
  return { actual: { imageChanged: h0 !== h1 }, ok: h0 !== h1 };
});

// ---- T7-T9 result: downloads, readouts and legends, Public mode
let rid = null;
await check("T7", "Downloads", ["analyse Site01, 13-20 Nov 2026", "fetch Series CSV, Events CSV, Intervals CSV and Full result JSON from the result's links"],
  "each download returns 200 with the right type; CSV row counts equal the result's series, events and intervals; JSON id equals the result", async () => {
  await evaluate("(() => { const b = [...document.querySelectorAll('.view-switch button')].find(x => x.textContent.trim() === 'South polar map'); b?.click(); return true; })()");
  rid = await analyse("-89.463163", "222.510447", "2026-11-13T00:00", "2026-11-20T00:00");
  const links = await evaluate(`[...document.querySelectorAll('a[href*="/api/results/"]')].map(a => ({ text: a.textContent.trim(), href: a.getAttribute('href') }))`);
  const r = await evaluate(`fetch('/api/results/${rid}').then(x => x.json())`);
  const got = {};
  for (const l of links) got[l.text] = await evaluate(`fetch(${JSON.stringify(l.href)}).then(async x => ({ status: x.status, type: x.headers.get('content-type'), disp: x.headers.get('content-disposition'), body: (await x.text()) }))
    .then(o => ({ status: o.status, type: o.type, disp: o.disp, lines: o.body.trim().split('\\n').length, jsonId: o.type && o.type.includes('json') ? (JSON.parse(o.body).id || null) : null }))`);
  const nIv = Object.values(r.intervals).reduce((a, v) => a + v.length, 0);
  const g = (re) => Object.entries(got).find(([k]) => re.test(k))?.[1];
  const series = g(/Series/), events = g(/Events/), ints = g(/Intervals/), json = g(/JSON/);
  const ok = [series, events, ints, json].every((x) => x && x.status === 200)
    && series.lines - 1 === r.series.et.length && events.lines - 1 === r.events.length && ints.lines - 1 === nIv && json.jsonId === rid;
  return { actual: { links: links.map((l) => l.text), series, events, intervals: ints, json, expected_rows: { series: r.series.et.length, events: r.events.length, intervals: nIv } }, ok };
});
await check("T8", "Charts", ["result view: Sunlight and Earth visibility sections", "read both readouts, chart gaps, timeline and horizon legends"],
  "each per-body chart has its own readout naming its body; the timeline legend lists 11 encodings including Unknown; the horizon legend shows the 1-sigma band and near-field bins (Site01 has both)", async () => {
  const readouts = await evaluate("[...document.querySelectorAll('.vis-readout')].map(e => e.textContent)");
  const tl = await evaluate("[...document.querySelectorAll('.timeline-legend li')].map(e => e.textContent.trim())");
  const hz = await evaluate("[...document.querySelectorAll('.panorama, .panorama-wrap, [class*=panorama]')].map(e => e.textContent).join(' ')");
  const r = await evaluate(`fetch('/api/results/${rid}').then(x => x.json())`);
  const ok = readouts.length >= 2 && readouts.some((t) => /Sun/.test(t)) && readouts.some((t) => /Earth/.test(t)) && tl.length === 11 && tl.includes("Unknown")
    && (!r.horizon.sigma_deg || /±1σ/.test(hz)) && (!(r.horizon.near_field ?? []).some(Boolean) || /Near-field/.test(hz));
  return { actual: { readouts, timelineLegend: tl, horizonLegendHasSigma: /±1σ/.test(hz), horizonLegendHasNearField: /Near-field/.test(hz) }, ok };
});
await check("T9", "Public/Technical mode", ["switch to Public", "then back to Technical"], "Public shows the plain-language result and hides the data tables link; Technical restores them", async () => {
  const pub = await evaluate("(() => { const b = [...document.querySelectorAll('.mode-switch button, .topbar button')].find(x => x.textContent.trim() === 'Public'); b.click(); return true; })()");
  await sleep(1200);
  const p = await evaluate("({ pressed: [...document.querySelectorAll('.topbar button')].find(x => x.textContent.trim() === 'Public')?.getAttribute('aria-pressed'), text: document.querySelector('main')?.innerText.slice(0, 400), tables: [...document.querySelectorAll('button, a')].some(e => e.textContent.trim() === 'Data tables') })");
  await evaluate("(() => { const b = [...document.querySelectorAll('.topbar button')].find(x => x.textContent.trim() === 'Technical'); b.click(); return true; })()"); await sleep(1000);
  const t = await evaluate("({ tables: [...document.querySelectorAll('button, a')].some(e => e.textContent.trim() === 'Data tables') })");
  return { actual: { publicPressed: p.pressed, publicHasTablesLink: p.tables, technicalHasTablesLink: t.tables }, ok: p.pressed === "true" && !p.tables && t.tables };
});

// ---- T10 UTC clock; T11 compact menu
await check("T10", "Top bar", ["read the UTC clock twice, 2.5 s apart"], "the UTC clock advances and is in UTC", async () => {
  const a = await evaluate("document.querySelector('.utc-clock, .clock, [class*=utc]')?.textContent || ''"); await sleep(2500);
  const b = await evaluate("document.querySelector('.utc-clock, .clock, [class*=utc]')?.textContent || ''");
  const now = new Date().toISOString().slice(0, 10);
  return { actual: { a, b }, ok: a !== b && /UTC/.test(a) && a.includes(now) };
});
await check("T11", "Navigation", ["1280 px", "open the compact menu", "choose Landing"], "the menu opens, the choice selects Landing and closes the menu", async () => {
  await size(1280, 800); await sleep(800);
  await evaluate("document.querySelector('.nav-toggle').click(); true"); await sleep(400);
  const open = await evaluate("document.querySelector('#primary-nav').getAttribute('data-open')");
  await evaluate("document.querySelector('#tab-landing').click(); true"); await sleep(600);
  const after = await evaluate("({ open: document.querySelector('#primary-nav').getAttribute('data-open'), selected: document.querySelector('button.tab[aria-selected=true]')?.textContent.trim(), toggle: document.querySelector('.nav-toggle')?.textContent.trim() })");
  await size(1440, 900); await sleep(600);
  return { actual: { openedTo: open, ...after }, ok: open === "true" && after.open !== "true" && after.selected === "Landing" };
});

// ---- T12 Landing; T13 Communication (direct and relay)
await check("T12", "Landing Safety", ["Site01", "Run screening", "radius 50 -> 120 m", "layer Roughness", "inspect backdrop tile requests"],
  "findings shown; footprint re-assessed with the new radius (API 200); layer image requested; the hazard-map backdrop uses /api/display/tiles/", async () => {
  await evaluate("document.querySelector('#tab-landing').click(); true");
  await waitFor("document.querySelector('.landing-run') && !document.querySelector('.landing-run').disabled", 60000, "landing run");
  const n0 = net.size;
  await evaluate("document.querySelector('.landing-run').click(); true");
  await waitFor("document.querySelector('section[aria-labelledby=landing-footprint]') && document.querySelector('.landing-map canvas')", 300000, "screening"); await sleep(3000);
  const findings = await evaluate("document.querySelectorAll('section[aria-labelledby=landing-footprint] .finding, section[aria-labelledby=landing-footprint] li').length");
  const radiusSel = await evaluate("(() => { const i = [...document.querySelectorAll('section[aria-labelledby=landing-footprint] input')].find(e => /radius/i.test(e.closest('.field, label, div')?.textContent || '')); return i ? '#' + i.id : null; })()");
  const n1 = net.size;
  if (radiusSel) { await setValue(radiusSel, "120"); await sleep(2500); }
  const fpReq = [...net.values()].slice(n1).filter((r) => /\/footprint$/.test(r.url));
  await evaluate("document.querySelector('input[name=ls-raster][value=roughness]')?.click(); true"); await sleep(2000);
  const layerReq = [...net.values()].slice(n0).filter((r) => /\/layer\/roughness\.png/.test(r.url));
  const tiles = [...net.values()].slice(n0).filter((r) => /\/tiles\/\d+\/\d+\/\d+\.png/.test(r.url));
  const display = tiles.filter((r) => /\/api\/display\/tiles\//.test(r.url));
  const shot = await shotVP("t12-landing");
  return { actual: { findings, radiusInput: radiusSel, footprintRequests: fpReq.map((r) => r.status), roughnessLayer: layerReq.map((r) => r.status), backdropTiles: tiles.length, onDisplayRoute: display.length, evidence: shot },
           ok: findings > 0 && !!radiusSel && fpReq.some((r) => r.status === 200) && layerReq.some((r) => r.status === 200) && tiles.length > 0 && display.length === tiles.length };
});
await check("T13", "Communication", ["Site01", "Simulate", "compare direct-to-Earth windows with the API", "relay on with an illustrative orbit", "RF direction buttons"],
  "direct windows equal the API's; the relay three-leg table appears; Lander to relay / Relay to Earth / Direct to Earth each select their link", async () => {
  await evaluate("document.querySelector('#tab-comms').click(); true"); await sleep(1500);
  const n0 = net.size;
  if (await evaluate("!!document.querySelector('.comms-run') && !document.querySelector('.comms-run').disabled")) await evaluate("document.querySelector('.comms-run').click(); true");
  await waitFor("document.querySelector('.comms-windows') || document.querySelector('section[aria-labelledby=comms-direct] table')", 600000, "simulation"); await sleep(2000);
  const req = [...net.values()].slice(n0).find((r) => /\/api\/comms\/simulate/.test(r.url) && r.method === "POST");
  const uiWindows = await evaluate("document.querySelectorAll('section[aria-labelledby=comms-direct] table tbody tr').length");
  await evaluate("document.querySelector('.comms-toggle input')?.click(); true"); await sleep(400);
  for (const [k, v] of [["name", "H1 illustrative"], ["a", "6000"], ["e", "0.6"], ["i", "60"], ["raan", "0"], ["argp", "90"], ["m0", "0"], ["step", "60"]]) await setValue(`#cr-${k}`, v);
  await setSelect("#cr-frame", "LME_EPOCH");
  let relayTable = false;
  try { await waitFor("document.querySelector('section[aria-labelledby=comms-relay] table')", 180000, "relay"); relayTable = true; } catch { /* recorded */ }
  const legs = await evaluate("document.querySelectorAll('section[aria-labelledby=comms-relay] table tbody tr').length");
  const seq = [];
  for (const t of ["Lander to relay", "Relay to Earth", "Direct to Earth"]) {
    await evaluate(`(() => { const b = [...document.querySelectorAll('.comms-linktabs button')].find(e => e.textContent.trim() === ${JSON.stringify(t)}); b?.click(); return true; })()`); await sleep(400);
    seq.push([t, await evaluate("[...document.querySelectorAll('.comms-linktabs button')].find(b => b.getAttribute('aria-pressed') === 'true')?.textContent.trim()")]);
  }
  const shot = await shotVP("t13-communication");
  return { actual: { simulateStatus: req?.status ?? null, uiDirectWindowRows: uiWindows, relayTable, relayRows: legs, linkSwitching: seq, evidence: shot },
           ok: req?.status === 200 && relayTable && legs >= 3 && seq.every(([a, b]) => a === b) };
});

const out = { base: BASE, run_utc: new Date().toISOString(), results, console_all: consoleMsgs.filter((x) => /error|exception/.test(x.type)) };
fs.writeFileSync(path.join(OUT, "app-checks.json"), JSON.stringify(out, null, 1));
console.log(JSON.stringify({ summary: results.map((r) => [r.id, r.result]), console: out.console_all.length }));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
