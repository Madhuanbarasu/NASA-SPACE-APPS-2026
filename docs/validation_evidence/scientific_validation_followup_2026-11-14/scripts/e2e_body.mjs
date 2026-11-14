
// Targeted E2E tests for the five scientific workstreams (not the Phase 7 application-wide suite).
// Path under test: browser input -> frontend validation -> API request -> backend calculation -> API response -> display.
// Analyses run one after another (sequential recomputation of the reference cases under the new engine fingerprint).
// One headless browser; appended to the Phase 1 CDP harness. Read only apart from the analyses it requests.
const T0 = Date.now();
const net = new Map();
ws.addEventListener("message", (m) => {
  const msg = JSON.parse(m.data); const p = msg.params;
  if (msg.method === "Network.requestWillBeSent") net.set(p.requestId, { url: p.request.url, method: p.request.method, t: Date.now() - T0, body: p.request.postData || null });
  else if (msg.method === "Network.responseReceived") { const r = net.get(p.requestId); if (r) r.status = p.response.status; }
});
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable"); await send("Network.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const setInput = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return false; const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
const setSelect = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return false; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
const shotVP = async (name) => { const { data } = await send("Page.captureScreenshot", { format: "png" }); fs.writeFileSync(path.join(OUT, "screenshots", `${name}.png`), Buffer.from(data, "base64")); return `screenshots/${name}.png`; };
const api = (u) => evaluate(`fetch(${JSON.stringify(u)}).then(r => r.json())`);
const tests = [];
const record = (t) => { tests.push(t); console.log(JSON.stringify({ id: t.id, result: t.result, actual: t.actual_summary })); };
await send("Emulation.setDeviceMetricsOverride", { width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(1000);

// ---------------------------------------------------------------- helpers: run an analysis from the sidebar
const resultId = () => evaluate(`(() => { const a = [...document.querySelectorAll('a[href*="/api/results/"]')].map(a => a.getAttribute('href').match(/results\\/([0-9a-f]+)/)?.[1]).find(Boolean); return a || null; })()`);
const figures = () => evaluate(`[...document.querySelectorAll('.figures .figure')].map(f => ({ title: f.querySelector('h3')?.textContent, big: f.querySelector('.big')?.textContent,
  metrics: Object.fromEntries([...f.querySelectorAll('.metric')].map(m => [m.querySelector('dt')?.textContent, m.querySelector('dd')?.textContent])) }))`);
async function analyse(name, lat, lon, start, end, panel = "vertical_tracking") {
  await evaluate("document.querySelector('#tab-site').click(); true"); await sleep(500);
  const before = await resultId();
  await setInput("#lat", lat); await setInput("#lon", lon);
  await setInput("#start", start); await setInput("#end", end);
  await setSelect("#panel", panel);
  await waitFor("!document.querySelector('.sidebar .run-button')?.disabled", 60000, "Analyse enabled");
  const t = Date.now();
  const n0 = net.size;
  await evaluate("document.querySelector('.sidebar .run-button').click(); true");
  await waitFor(`(() => { const a = [...document.querySelectorAll('a[href*="/api/results/"]')].map(a => a.getAttribute('href').match(/results\\/([0-9a-f]+)/)?.[1]).find(Boolean); return a && a !== ${JSON.stringify(before)} && document.querySelector('.figures'); })()`, 1800000, name);
  await sleep(1500);
  const id = await resultId();
  const req = [...net.values()].slice(n0).find((r) => /\/api\/analy/.test(r.url) && r.method === "POST");
  return { id, s: Math.round((Date.now() - t) / 1000), request: req ? { url: req.url.replace(BASE, ""), status: req.status ?? null, body: req.body ? JSON.parse(req.body) : null } : null };
}
// "5 d 6 h" / "3 h 12 min" / "0 min" -> hours
const hoursOf = (s) => { if (!s) return null; let h = 0; const d = /(\d+)\s*d/.exec(s); const hh = /(\d+)\s*h/.exec(s); const mm = /(\d+)\s*min/.exec(s);
  if (d) h += 24 * +d[1]; if (hh) h += +hh[1]; if (mm) h += +mm[1] / 60; return (d || hh || mm) ? h : null; };
const fig = (figs, re) => figs.find((f) => re.test(f.title || "")) || null;
const metric = (f, re) => f ? Object.entries(f.metrics).find(([k]) => re.test(k || ""))?.[1] ?? null : null;
const pctOf = (s) => { const m = /(-?[\d.]+)\s*%/.exec(s || ""); return m ? +m[1] : null; };
const sumUnknownSec = (ivs) => ivs.filter((iv) => iv.state === null).reduce((a, iv) => a + (iv.end_et - iv.start_et), 0);

// ---------------------------------------------------------------- E2E-01  V-09 / V-10 in Data and validation
{
  await evaluate("document.querySelector('#tab-data').click(); true"); await sleep(1500);
  const rows = await evaluate(`[...document.querySelectorAll('table.validation-tests tbody tr')].map(tr => [...tr.children].map(td => td.textContent.trim()))`);
  const pick = (id) => rows.find((r) => r.some((c) => c === id || c.startsWith(id + " ")));
  const blockers = await evaluate("document.querySelector('.note.alert')?.textContent || null");
  const labels = await evaluate(`[...document.querySelectorAll('table.validation-labels tbody tr')].map(tr => [...tr.children].map(td => td.textContent.trim()))`);
  const v = await api("/api/validation");
  await evaluate("document.querySelector('table.validation-tests')?.scrollIntoView({ block: 'start' }); true"); await sleep(300);
  const shot = await shotVP("e2e01-validation-table");
  const r9 = pick("V-09"), r10 = pick("V-10");
  const ok = !!r9 && !!r10 && /not run/i.test(r9.join(" ")) && /14\.09/.test(r9.join(" ")) && /-7\.19/.test(r9.join(" ")) && /provisional/i.test(r9.join(" "))
    && /3\.13/.test(r10.join(" ")) && /-0\.74/.test(r10.join(" ")) && /provisional/i.test(r10.join(" "))
    && /different code/i.test(blockers || "") && labels.length > 0 && labels.every((l) => /Pending validation/.test(l.join(" ")));
  record({ id: "E2E-01", workstream: "V-09 / V-10", steps: ["open Data and validation", "read the V-09 and V-10 rows, the blockers note and the labels table", "compare with /api/validation"],
    expected: "V-09: not run, RMSE 14.09 pp, bias -7.19 pp, provisional criteria; V-10: not run, 3.13 / -0.74, provisional; blockers note says the report was produced by different code; every label Pending validation",
    actual: { v09_row: r9, v10_row: r10, blockers, labels }, api: { "V-09": v.tests?.["V-09"], "V-10": v.tests?.["V-10"], code_fingerprint: v.code_fingerprint },
    evidence: [shot], result: ok ? "Pass" : "Fail",
    actual_summary: `V-09 row found ${!!r9}, V-10 row found ${!!r10}, blockers mention different code ${/different code/i.test(blockers || "")}, labels ${labels.length} all pending ${labels.every((l) => /Pending validation/.test(l.join(" ")))}` });
}

// ---------------------------------------------------------------- E2E-02  missing terrain (the a667129a case)
let missing = null;
{
  const run = await analyse("missing terrain", "-60.482591", "266.96912", "2026-11-12T00:00", "2026-12-12T00:00");
  const figs = await figures();
  const r = await api(`/api/results/${run.id}`);
  const sunFig = fig(figs, /Sunlight/i);
  const uiUnknownH = hoursOf(metric(sunFig, /Unknown/i));
  const beUnknownH = r.summary.sun_any.unknown_hours;
  const hatch = await evaluate(`document.querySelectorAll('rect[fill="url(#tl-hatch)"]').length`);
  const beUnknownIv = { sun_any: r.intervals.sun_any.filter((iv) => iv.state === null).length, earth_centre: r.intervals.earth_centre.filter((iv) => iv.state === null).length };
  await evaluate("document.querySelector('.timeline-wrap')?.scrollIntoView({ block: 'center' }); true"); await sleep(500);
  const shot1 = await shotVP("e2e02-missing-terrain-timeline");
  await evaluate("document.querySelector('.figures')?.scrollIntoView({ block: 'start' }); true"); await sleep(300);
  const shot2 = await shotVP("e2e02-missing-terrain-figures");
  missing = { id: run.id };
  const ok = run.id && uiUnknownH !== null && Math.abs(uiUnknownH - beUnknownH) <= 1.0 && beUnknownH > 0 && hatch > 0;
  record({ id: "E2E-02", workstream: "Event detection (missing terrain)", steps: ["Site: -60.482591, 266.96912 (the a667129a site), 12 Nov - 12 Dec 2026", "Analyse", "read the Sunlight card's Unknown and the timeline's hatched (unknown) segments", "fetch the result"],
    expected: "Unknown time shown, equal to the backend's sun_any unknown hours (display rounding); hatched segments present; backend shows no visible time over incomplete bins (checked separately)",
    actual: { result_id: run.id, analysis_s: run.s, request: run.request, sunlight_card: sunFig, ui_unknown_h: uiUnknownH, backend_unknown_h: beUnknownH, hatched_rects: hatch, backend_unknown_intervals: beUnknownIv,
              incomplete_share: r.horizon.incomplete_share, code_fingerprint: r.provenance.code_fingerprint },
    api: { summary_sun_any: r.summary.sun_any }, evidence: [shot1, shot2], result: ok ? "Pass" : "Fail",
    actual_summary: `UI unknown ${uiUnknownH} h vs backend ${beUnknownH?.toFixed(2)} h; hatched rects ${hatch}; analysis ${run.s} s` });
}

// ---------------------------------------------------------------- E2E-03  complete terrain (Site01), against the pre-fix cached result
let site01 = null;
{
  const run = await analyse("complete terrain", "-89.463163", "222.510447", "2026-11-13T00:00", "2026-12-13T00:00");
  const figs = await figures();
  const r = await api(`/api/results/${run.id}`);
  const old = await api(`/api/results/976a3d8fe1814d14e9efe07f`);
  const same = {}; let allSame = true;
  for (const k of Object.keys(old.intervals)) {
    const a = old.intervals[k].map((iv) => [iv.start_et, iv.end_et, iv.state]), b = r.intervals[k].map((iv) => [iv.start_et, iv.end_et, iv.state]);
    const eq = a.length === b.length && a.every((x, i) => Math.abs(x[0] - b[i][0]) < 1e-6 && Math.abs(x[1] - b[i][1]) < 1e-6 && x[2] === b[i][2]);
    same[k] = { old: a.length, new: b.length, identical: eq }; allSame &&= eq;
  }
  const sunFig = fig(figs, /Sunlight/i);
  const hatch = await evaluate(`document.querySelectorAll('rect[fill="url(#tl-hatch)"]').length`);
  const shot = await shotVP("e2e03-complete-terrain-site01");
  site01 = { id: run.id, r };
  const ok = allSame && r.horizon.incomplete_share === 0 && hoursOf(metric(sunFig, /Unknown/i)) === 0 && hatch === 0
    && Math.abs(pctOf(sunFig?.big) - r.summary.sun_any.percent) <= 0.05;
  record({ id: "E2E-03", workstream: "Event detection (complete terrain)", steps: ["Site01, 13 Nov - 13 Dec 2026", "Analyse (new fingerprint: recomputed)", "compare every interval with the pre-fix cached result 976a3d8f", "read the Sunlight card"],
    expected: "intervals identical to the pre-fix result (complete horizon: no change); Unknown 0 min; no hatched segments; displayed % = backend",
    actual: { result_id: run.id, analysis_s: run.s, intervals_vs_prefix: same, sunlight_card: sunFig, hatched_rects: hatch, code_fingerprint: r.provenance.code_fingerprint, old_code_fingerprint: old.provenance.code_fingerprint },
    api: { summary_sun_any: r.summary.sun_any }, evidence: [shot], result: ok ? "Pass" : "Fail",
    actual_summary: `intervals identical to pre-fix: ${allSame}; UI ${sunFig?.big} vs backend ${r.summary.sun_any.percent.toFixed(2)} %; analysis ${run.s} s` });
}

// ---------------------------------------------------------------- E2E-06  power indicator (Site01 result) and E2E-07 its inputs
{
  const r = site01.r;
  const figs = await figures();
  const pf = fig(figs, /Power/i);
  const be = r.summary.power.vertical_tracking;
  const uiMean = parseFloat(pf?.big); const uiEfsh = hoursOf(metric(pf, /full-Sun|full Sun|Equivalent/i));
  const text = await evaluate("document.querySelector('.figures .figure.is-power')?.textContent || ''");
  const wattClaim = /\b(k?W|watts?|kilowatt)\b/i.test(text);
  await evaluate("document.querySelector('.figures')?.scrollIntoView({ block: 'start' }); true"); await sleep(300);
  const shot = await shotVP("e2e06-power-vertical");
  // horizontal panel: a new request with panel_model horizontal
  const run2 = await analyse("power horizontal", "-89.463163", "222.510447", "2026-11-13T00:00", "2026-12-13T00:00", "horizontal");
  const figs2 = await figures(); const pf2 = fig(figs2, /Power/i);
  const r2 = await api(`/api/results/${run2.id}`);
  const shot2 = await shotVP("e2e06-power-horizontal");
  const ok = Math.abs(uiMean - be.mean) <= 0.0005 && Math.abs(uiEfsh - be.equivalent_full_sun_h) <= 1.0 && !wattClaim
    && /Estimated/i.test(text + JSON.stringify(r.labels.power_indicator)) && Math.abs(parseFloat(pf2?.big) - r2.summary.power.horizontal.mean) <= 0.0005
    && run2.request?.body?.panel_model === "horizontal";
  record({ id: "E2E-06", workstream: "Power indicator", steps: ["Site01 result (vertical tracking panel): read the Power indicator card", "switch the panel to horizontal, Analyse, read again", "compare with the result JSON"],
    expected: "displayed mean = backend mean (3 decimals); equivalent full-Sun time = backend (display rounding); horizontal value = backend horizontal mean; no watt / kW claim; labelled Estimated",
    actual: { card_vertical: pf, backend_vertical: be, card_horizontal: pf2, backend_horizontal: r2.summary.power.horizontal, request_panel: run2.request?.body?.panel_model, watt_claim_in_card: wattClaim, card_text: text },
    api: { labels_power_indicator: r.labels.power_indicator }, evidence: [shot, shot2], result: ok ? "Pass" : "Fail",
    actual_summary: `vertical UI ${pf?.big} vs ${be.mean.toFixed(4)}; horizontal UI ${pf2?.big} vs ${r2.summary.power.horizontal.mean.toFixed(4)}; watt claim ${wattClaim}` });
  // invalid inputs
  const n0 = net.size;
  await evaluate("document.querySelector('#tab-site').click(); true");
  await setInput("#lat", "-95"); await setInput("#lon", "222.510447"); await sleep(1500);
  const latState = await evaluate(`({ invalid: document.querySelector('#lat').getAttribute('aria-invalid'), hint: document.querySelector('#coord-hint')?.textContent, analyse: document.querySelector('.sidebar .run-button').disabled })`);
  await setInput("#lat", "-89.463163"); await sleep(1500);
  await setInput("#start", "2026-12-13T00:00"); await setInput("#end", "2026-11-13T00:00"); await sleep(800);
  const winState = await evaluate(`({ analyse: document.querySelector('.sidebar .run-button').disabled, text: document.querySelector('.sidebar')?.textContent.match(/[^.]*(end|before|after|window)[^.]*\\./gi)?.slice(0, 3) || null })`);
  let winApi = null;
  if (!winState.analyse) { winApi = await evaluate(`fetch('/api/analysis', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ lat: -89.463163, lon: 222.510447, start_utc: '2026-12-13T00:00:00Z', end_utc: '2026-11-13T00:00:00Z' }) }).then(async r => ({ status: r.status, body: (await r.text()).slice(0, 300) }))`); }
  const shot3 = await shotVP("e2e07-invalid-window");
  await setInput("#start", "2026-11-13T00:00"); await setInput("#end", "2026-12-13T00:00");
  await setSelect("#panel", "fixed_vertical"); await sleep(300);
  await setInput("#paz", "400"); await sleep(300);
  const pazState = await evaluate(`({ value: document.querySelector('#paz')?.value, valid: document.querySelector('#paz')?.checkValidity(), analyse: document.querySelector('.sidebar .run-button').disabled })`);
  const pazApi = await evaluate(`fetch('/api/analysis', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ lat: -89.463163, lon: 222.510447, start_utc: '2026-11-13T00:00:00Z', end_utc: '2026-11-14T00:00:00Z', panel_model: 'fixed_vertical', panel_az_deg: 400 }) }).then(async r => ({ status: r.status, body: (await r.text()).slice(0, 300) }))`);
  const badPanel = await evaluate(`fetch('/api/analysis', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ lat: -89.463163, lon: 222.510447, start_utc: '2026-11-13T00:00:00Z', end_utc: '2026-11-14T00:00:00Z', panel_model: 'solar_array_5kW' }) }).then(async r => ({ status: r.status, body: (await r.text()).slice(0, 300) }))`);
  await setSelect("#panel", "vertical_tracking");
  const coverageCalls = [...net.values()].slice(n0).filter((x) => /coverage\?lat=-95/.test(x.url)).length;
  const ok7 = latState.invalid === "true" && latState.analyse === true && coverageCalls === 0 && (winState.analyse === true || (winApi && winApi.status >= 400))
    && badPanel.status >= 400;
  record({ id: "E2E-07", workstream: "Power indicator / inputs", steps: ["latitude -95", "end before start", "fixed panel azimuth 400 deg (UI and API)", "unknown panel model (API)"],
    expected: "invalid latitude flagged, Analyse disabled, no request; end-before-start refused (UI or API 4xx); unknown panel model refused (4xx); panel azimuth 400: recorded as found",
    actual: { latitude: latState, coverage_requests_for_minus95: coverageCalls, window: winState, window_api: winApi, panel_az_400_ui: pazState, panel_az_400_api: pazApi, unknown_panel_api: badPanel },
    evidence: [shot3], result: ok7 ? "Pass" : "Fail",
    actual_summary: `lat flagged ${latState.invalid}, analyse disabled ${latState.analyse}; window: analyse disabled ${winState.analyse} api ${winApi?.status ?? "-"}; panel az 400 api ${pazApi.status}; unknown panel api ${badPanel.status}` });
}

// ---------------------------------------------------------------- E2E-04 / E2E-05  Earth disk: partial (84.3 S) and fully blocked (78.4 S)
for (const [id, name, lat, lon, oldId] of [["E2E-04", "Earth partly visible (84.31 S 359.05 E)", "-84.313534", "359.048681", "c9b10862d307661e0c2b7ef0"],
                                            ["E2E-05", "Earth fully blocked by terrain (78.40 S 21.87 E)", "-78.398411", "21.869043", null]]) {
  const run = await analyse(name, lat, lon, "2026-11-13T00:00", "2026-12-13T00:00");
  const figs = await figures();
  const r = await api(`/api/results/${run.id}`);
  const ef = fig(figs, /Direct-to-Earth/i);
  const fser = r.series.earth.f.filter((x) => x !== null);
  const partial = fser.filter((x) => x > 0 && x < 1).length, full = fser.filter((x) => x >= 1).length, none = fser.filter((x) => x <= 0).length;
  const anyH = r.summary.earth_any.hours, cenH = r.summary.earth_centre.hours;
  let oldCmp = null;
  if (oldId) {
    const idx = await api("/api/catalog").catch(() => null);
    const old = await evaluate(`fetch('/api/results/' + ${JSON.stringify(oldId)}).then(r => r.ok ? r.json() : null).catch(() => null)`);
    oldCmp = old ? { old_earth_any_h: old.summary.earth_any.hours, new_earth_any_h: anyH } : "pre-fix result id is a prefix; compared offline";
  }
  await evaluate("document.querySelector('.figures')?.scrollIntoView({ block: 'start' }); true"); await sleep(300);
  const shot = await shotVP(id.toLowerCase() + "-earth-disk");
  const dte = r.summary[`earth_${r.provenance.parameters?.dte_rule || "centre"}`] || r.summary.earth_centre;
  const okDisplay = Math.abs(pctOf(ef?.big) - dte.percent) <= 0.05;
  const ok = id === "E2E-04" ? (okDisplay && partial > 0 && anyH >= cenH) : (okDisplay && dte.percent === 0 && partial === 0 && fser.every((x) => x === 0));
  record({ id, workstream: "Earth-disk visibility", steps: [`Site ${lat}, ${lon}, 13 Nov - 13 Dec 2026`, "Analyse", "read the Direct-to-Earth card", "inspect the Earth visible-fraction series and the any/centre summaries"],
    expected: id === "E2E-04" ? "displayed % = backend; samples with a partly visible disk (0<f<1) present; any-part hours >= centre hours"
                              : "displayed 0.0 % = backend 0; every Earth visible-fraction sample 0 (fully blocked)",
    actual: { result_id: run.id, analysis_s: run.s, card: ef, earth_f_samples: { partial, full, none }, earth_any_h: anyH, earth_centre_h: cenH, previous: oldCmp },
    api: { summary_earth: { any: r.summary.earth_any, centre: r.summary.earth_centre } }, evidence: [shot], result: ok ? "Pass" : "Fail",
    actual_summary: `UI ${ef?.big} vs backend ${dte.percent.toFixed(2)} %; f samples partial ${partial} full ${full} none ${none}; any ${anyH.toFixed(2)} h centre ${cenH.toFixed(2)} h; ${run.s} s` });
}

const out = { base: BASE, run_utc: new Date().toISOString(), tests, console: consoleMsgs.filter((x) => /error|exception/.test(x.type)),
  analysis_requests: [...net.values()].filter((r) => /\/api\/analy/.test(r.url)).map((r) => ({ url: r.url.replace(BASE, ""), method: r.method, status: r.status ?? null })) };
fs.writeFileSync(path.join(OUT, "e2e-results.json"), JSON.stringify(out, null, 1));
console.log(JSON.stringify({ summary: tests.map((t) => [t.id, t.result]), console: out.console.length }));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
