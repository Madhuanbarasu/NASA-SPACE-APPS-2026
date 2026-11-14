
// Functional check of the UI simplification (one headless browser, 1440 px): mission-site catalogue, date presets,
// advanced settings, Mission journey, Guide steps, Compare (2 sites x 2 windows) Summary with criteria, terrain
// screening, RF not-assessed / evaluated, Matrix and Charts views, then the Communication and Landing tabs still work.
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable"); await send("Network.enable");
const net = []; const reqs = new Map();
ws.addEventListener("message", (m) => { const msg = JSON.parse(m.data); const p = msg.params || {};
  if (msg.method === "Network.requestWillBeSent" && /\/api\//.test(p.request.url)) reqs.set(p.requestId, { url: p.request.url.replace(BASE, "").slice(0, 80) });
  if (msg.method === "Network.responseReceived" && reqs.has(p.requestId)) reqs.get(p.requestId).status = p.response.status;
  if ((msg.method === "Network.loadingFinished" || msg.method === "Network.loadingFailed") && reqs.has(p.requestId)) { const r = reqs.get(p.requestId); if (p.errorText) r.failed = p.errorText; net.push(r); reqs.delete(p.requestId); } });
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return false; const proto = e.tagName === 'SELECT' ? HTMLSelectElement.prototype : HTMLInputElement.prototype; Object.getOwnPropertyDescriptor(proto, 'value').set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
const clickText = (sel, re) => evaluate(`(() => { const b = [...document.querySelectorAll(${JSON.stringify(sel)})].find((x) => new RegExp(${JSON.stringify(re)}).test(x.textContent.trim()) && !x.disabled); if (!b) return false; b.click(); return true; })()`);
const text = (sel) => evaluate(`(document.querySelector(${JSON.stringify(sel)})?.innerText || '').replace(/\\s+/g, ' ').trim()`);
const withTimeout = (pr, ms) => Promise.race([pr, new Promise((r) => setTimeout(() => r(null), ms))]);
const snap = async (name) => { const r = await withTimeout(send("Page.captureScreenshot", { format: "png" }), 15000); if (r?.data) fs.writeFileSync(path.join(OUT, "screenshots", name + ".png"), Buffer.from(r.data, "base64")); };
const until = async (expr, ms, what) => { const t = Date.now(); while (Date.now() - t < ms) { if (await evaluate(expr)) return true; await sleep(800); } console.log("TIMEOUT", what); return false; };
const tab = async (id) => { await evaluate(`(() => { if (location.hash) history.replaceState(null, '', location.pathname); document.querySelector('#tab-${id}')?.click(); return true; })()`); await sleep(1200); };
const scrollTo = (sel) => evaluate(`(() => { document.querySelector(${JSON.stringify(sel)})?.scrollIntoView({ block: 'start' }); return true; })()`);
const R = []; const ok = (name, cond, detail = "") => { R.push({ name, pass: !!cond, detail }); console.log(`${cond ? "PASS" : "FAIL"} ${name} ${detail}`); };

await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(1000);
// tabs renamed
const tabsTxt = await evaluate("[...document.querySelectorAll('#primary-nav [role=tab]')].map((t) => t.textContent.trim()).join(' | ')");
ok("navigation tab names", /Explore & analyse/.test(tabsTxt) && /Compare sites/.test(tabsTxt), tabsTxt);
await tab("site");
// catalogue
await evaluate("document.querySelector('.ref-sites').open = true; true"); await sleep(300);
const nRef = await evaluate("document.querySelectorAll('.ref-list li').length");
await setValue("#ref-search", "chandrayaan"); await sleep(400);
const hit = await evaluate("[...document.querySelectorAll('.ref-list li')].map((l) => l.innerText.replace(/\\s+/g, ' ')).join(' || ')");
ok("catalogue lists sourced sites, search works", nRef === 30 && /Chandrayaan-3/.test(hit) && /Source/.test(hit), `${nRef} entries; hit: ${hit.slice(0, 120)}`);
const srcHref = await evaluate("document.querySelector('.ref-list li a.ref-source')?.href || ''");
ok("catalogue entry links its source", /lroc\.im-ldi\.com\/images\/1314/.test(srcHref), srcHref);
await evaluate("document.querySelector('.ref-list li button').click(); true"); await sleep(1500);
const latlon = [await evaluate("document.querySelector('#lat').value"), await evaluate("document.querySelector('#lon').value"), await evaluate("document.querySelector('#sname').value")];
await until("/Terrain coverage/.test(document.querySelector('#coord-hint')?.textContent || '')", 30000, "coverage");
ok("selecting a catalogue site fills coordinates and name; coverage checked", latlon[0] === "-69.374100" && latlon[2].startsWith("Chandrayaan-3") && /240m/.test(await text("#coord-hint")), latlon.join(" ") + " / " + await text("#coord-hint"));
await snap("01-catalogue-chandrayaan-1440");
await setValue("#ref-search", "apollo 11"); await sleep(300);
await evaluate("document.querySelector('.ref-list li button').click(); true"); await sleep(1500);
await until("!/Checking/.test(document.querySelector('#coord-hint')?.textContent || 'Checking')", 30000, "coverage2");
const refOnly = await text("#coord-hint");
const runDisabled = await evaluate("document.querySelector('aside .run-button').disabled");
ok("reference-only site: no analysis possible", runDisabled && /No terrain-adjusted results/.test(refOnly) && /reference only/i.test(await text(".ref-list")), refOnly.slice(0, 100));
// presets and advanced settings
await setValue("#lat", "-84.313534"); await setValue("#lon", "359.048681"); await setValue("#sname", "");
await setValue("#start", "2026-11-13T00:00"); await clickText(".date-presets button", "^7 days$"); await sleep(300);
ok("7-day preset sets the end", (await evaluate("document.querySelector('#end').value")) === "2026-11-20T00:00", await evaluate("document.querySelector('#end').value"));
await clickText(".date-presets button", "^1 day$"); await sleep(200);
ok("1-day preset", (await evaluate("document.querySelector('#end').value")) === "2026-11-14T00:00");
await clickText(".date-presets button", "Lunar day"); await sleep(200);
const lunarEnd = await evaluate("document.querySelector('#end').value");
ok("lunar-day preset (29.53 d)", lunarEnd === "2026-12-12T12:44", lunarEnd);
await clickText(".date-presets button", "^7 days$"); await sleep(300);
const advClosed = await evaluate("!document.querySelector('.side-advanced').open && !!document.querySelector('#obsh') && /Surface observer/.test(document.querySelector('.side-advanced summary').textContent)");
ok("advanced settings folded with a summary; fields still present", advClosed, await text(".side-advanced summary"));
// Mission journey
await tab("mission"); await sleep(800);
const steps = await evaluate("[...document.querySelectorAll('.journey-step')].map((s) => s.className + ':' + s.querySelector('.journey-title').textContent).join(' | ')");
ok("mission journey: 4 steps, next step highlighted", (steps.match(/journey-step/g) || []).length === 4 && /is-next/.test(steps), steps);
ok("system status folded into one line", /System status: NAIF kernels production/.test(await text(".mission-system summary")), await text(".mission-system summary"));
await snap("02-mission-journey-1440");
// Guide
await tab("guide");
ok("guide: five steps and a Data link", (await evaluate("document.querySelectorAll('.guide-step').length")) === 5 && (await evaluate("document.querySelector('.guide-data-link')?.getAttribute('href')")) === "#data");
await snap("03-guide-1440");
await evaluate("document.querySelectorAll('.guide-step')[4].click(); true"); await sleep(800);
ok("guide step opens its tab", /Compare sites/.test(await evaluate("document.querySelector('[role=tab][aria-selected=true]')?.textContent || ''")));
// map and globe: mission-site markers and legends (increment C)
await tab("site");
await setValue("#lat", "-84.313534"); await setValue("#lon", "359.048681"); await sleep(1500);
await clickText(".view-switch button", "^South polar map$"); await sleep(3000);
const mapLegend = await evaluate("[...document.querySelectorAll('.stage-legend, .map-legend, details')].map((d) => d.textContent).join(' ')");
ok("map legend lists sourced mission sites", /Mission sites \(sourced; analysable here\)/.test(mapLegend));
await snap("07-map-missions-1440");
await clickText(".view-switch button", "^3D Moon globe$"); await sleep(8000);
const globeLegend = await evaluate("[...document.querySelectorAll('.stage-legend, details')].map((d) => d.textContent).join(' ')");
ok("globe legend: mission sites inside and outside coverage", /Mission sites inside 60-90° S/.test(globeLegend) && /outside LUNA-OPS terrain coverage/.test(globeLegend));
await snap("08-globe-missions-1440");
// analysis result: section bar and folded validation details (increment E)
await setValue("#start", "2026-11-13T00:00"); await setValue("#end", "2026-11-20T00:00"); await sleep(500);
await until("(() => { const b = document.querySelector('aside .run-button'); return !!b && !b.disabled; })()", 60000, "run enabled");
await evaluate("document.querySelector('aside .run-button').click(); true");
await until("/What the horizon looks like/.test(document.querySelector('main')?.innerText || '')", 600000, "analysis");
await sleep(2000);
ok("result: section bar present", await evaluate("document.querySelectorAll('.section-nav a').length >= 7"));
const valClosed = await evaluate("(() => { const d = document.querySelector('#result-validation details'); return !!d && !d.open; })()");
await evaluate("document.querySelector('#result-validation details').open = true; true"); await sleep(500);
ok("result: validation details folded, open on request", valClosed && /Pending validation|Validated|test/i.test(await text("#result-validation")));
await snap("09-result-1440");
// Compare: 2 sites x 2 windows
await tab("site");
await setValue("#lat", "-84.313534"); await setValue("#lon", "359.048681"); await sleep(800);
await tab("compare");
await clickText("main button", "^Add the selected site"); await sleep(300);
await evaluate("document.querySelector('.builder-more').open = true; true"); await sleep(200);
await clickText(".builder-more li button", "^Add$");   // the first analysable mission site (Chandrayaan-3)
await sleep(300);
const nSites = await evaluate("document.querySelectorAll('.compare-builder section:first-child > .list-edit > li').length");
ok("builder: selected site + a mission site added", nSites >= 2, `${nSites} sites`);
await clickText("main button", "^Add the panel's dates$"); await sleep(200);
await clickText("main button", "^Add one synodic month later$"); await sleep(200);
await until("(() => { const b = [...document.querySelectorAll('main .run-button')].find((x) => /^Compare /.test(x.textContent.trim())); return !!b && !b.disabled; })()", 30000, "compare enabled");
await clickText("main .run-button", "^Compare ");
await until("!!document.querySelector('.cmp-summary') || /could not/i.test(document.querySelector('main')?.innerText || '')", 1500000, "comparison");
await sleep(3000);
const sumTxt = await text(".cmp-summary");
ok("compare opens on the Summary", !!sumTxt && /Trade-offs at a glance/.test(sumTxt) && /Sunlight:/.test(sumTxt), sumTxt.slice(0, 160));
ok("leads stated with values", /Most sunlight: .* \(.*% vs .*%/.test(sumTxt) || /no clear difference/.test(sumTxt), (sumTxt.match(/Most sunlight[^.]*\./) || [""])[0]);
ok("without criteria: Not assessed, values still shown", /Not assessed/.test(sumTxt) && /Set criteria above/.test(sumTxt));
ok("RF: Not assessed without a link budget", /Not assessed: enter a direct-to-Earth link budget/.test(sumTxt));
await snap("04-compare-summary-1440");
// criteria
await evaluate("document.querySelector('.cmp-criteria').open = true; true"); await sleep(200);
await setValue("#crit-sunPctMin", "50"); await setValue("#crit-earthPctMin", "50"); await sleep(800);
const sum2 = await text(".cmp-summary");
ok("criteria give Favourable / Needs review with reasons", /Favourable|Needs review/.test(sum2) && /Sunlit at least \(%\): .* (≥|≤) .* \((met|not met)\)/.test(sum2), (sum2.match(/Sunlit at least[^)]*\)[^)]*\)/) || [""])[0]);
// terrain screening
await setValue("#crit-slopeMax", "15"); await sleep(300);
await clickText(".obj-terrain button", "^Screen the terrain");
await until("!/Screening site/.test(document.querySelector('.obj-terrain')?.innerText || '') && !!document.querySelector('.obj-terrain table')", 900000, "terrain");
await sleep(1000);
const terrTxt = await text(".obj-terrain");
ok("terrain screened at every site with product and findings", /m:|5m|20m|240m/.test(terrTxt) && /(Favourable|Needs review|Insufficient data)/.test(terrTxt), terrTxt.slice(0, 260));
ok("coarse 240 m site reported as Insufficient data / too coarse", /Insufficient data/.test(terrTxt) && /coarse|higher-resolution/i.test(terrTxt));
ok("never claims safety", !/certified safe|safe landing site/i.test(terrTxt));
await scrollTo(".obj-terrain"); await sleep(500); await snap("05-compare-terrain-1440");
// RF with a link budget (Communication tab inputs), then back
await tab("comms"); await sleep(3000);
for (const [k, v] of Object.entries({ power: "50", gt: "30", ltx: "1", gr: "60", lrx: "1", ts: "50", lother: "3", freqMHz: "8450", rbkbps: "1000", ebn0: "2.5" })) await setValue(`#cl-direct-${k}`, v);
await sleep(1500);
await tab("compare"); await sleep(1500);
await clickText(".obj-earth button", "^Evaluate RF");
await until("!/Evaluating RF/.test(document.querySelector('.obj-earth')?.innerText || '')", 300000, "rf");
await sleep(800);
const rfTxt = await text(".obj-earth");
ok("RF evaluated per site from the user's link budget", /RF-feasible time/.test(rfTxt) && /\d+ (d|h|min).*\(\d/.test(rfTxt), (rfTxt.match(/RF-feasible[^.]*\./) || [""])[0]);
await scrollTo(".obj-earth"); await sleep(400); await snap("06-compare-earth-rf-1440");
// Matrix and Charts views
await clickText(".cmp-views button", "^Matrix$"); await sleep(1000);
ok("Matrix view keeps cards, matrix and CSV", await evaluate("!!document.querySelector('.matrix') && !!document.querySelector('a[href$=\"compare.csv\"]') && !!document.querySelector('.site-cards')"));
await clickText(".cmp-views button", "^Charts$"); await sleep(2000);
ok("Charts view renders charts", (await evaluate("document.querySelectorAll('main svg').length")) > 0);
// Landing and Communication still work
await tab("landing");
await until("(() => { const b = document.querySelector('.landing-run'); return !!b && !b.disabled; })()", 60000, "landing enabled");
await evaluate("document.querySelector('.landing-run').click(); true");
await until("!!document.querySelector('.landing-map canvas')", 300000, "landing");
await sleep(2000);
ok("Landing screening still works; provenance folded", await evaluate("!!document.querySelector('.landing-map canvas') && !!document.querySelector('[aria-labelledby=landing-provenance] details:not([open])')"));
await tab("comms"); await sleep(1500);
ok("Communication tab still shows direct-to-Earth; provenance folded", /Direct to Earth/i.test(await text("main")) && await evaluate("!!document.querySelector('[aria-labelledby=comms-provenance] details:not([open])')"));
const errs = consoleMsgs.filter((x) => /error|exception/.test(x.type));
const bad = net.filter((r) => (r.status && r.status >= 400) || (r.failed && !/ERR_ABORTED/.test(r.failed)));
ok("no console errors", errs.length === 0, JSON.stringify(errs.slice(0, 3)));
ok("no failed API requests", bad.length === 0, JSON.stringify(bad.slice(0, 5)));
fs.writeFileSync(path.join(OUT, "func.json"), JSON.stringify({ results: R, failedRequests: bad, console: errs }, null, 1));
console.log(`SUMMARY ${R.filter((x) => x.pass).length}/${R.length}`);
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
