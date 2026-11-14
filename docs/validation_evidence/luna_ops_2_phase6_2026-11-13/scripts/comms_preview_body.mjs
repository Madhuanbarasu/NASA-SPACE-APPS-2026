
// LUNA-OPS 2.0 Phase 6: Communication previews and measurements (one headless browser; appended to the Phase 1 CDP
// harness, cdp_harness.txt). Usage: node comms_preview.mjs --base <url> --out <dir>
// The RF values and the relay orbit typed here are ILLUSTRATIVE demonstration inputs, not hardware or mission data.
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable"); await send("Network.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const tab = (name) => evaluate(`(() => { const b = [...document.querySelectorAll('button.tab')].find(e => e.textContent.trim() === ${JSON.stringify(name)}); if (b) b.click(); return !!b; })()`);
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return false; const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
const setSelect = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return false; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
const size = (w, h) => send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
const top0 = () => evaluate("document.querySelector('.main')?.scrollTo(0, 0); window.scrollTo(0, 0); true");
const scrollTo = (sel) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (e) e.scrollIntoView({ block: 'start' }); return !!e; })()`);
const clickText = (sel, text) => evaluate(`(() => { const b = [...document.querySelectorAll(${JSON.stringify(sel)})].find(e => e.textContent.trim() === ${JSON.stringify(text)}); if (b) b.click(); return !!b; })()`);
const hscroll = () => evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth");
const text = (sel) => evaluate(`document.querySelector(${JSON.stringify(sel)})?.textContent || ''`);
const out = { views: {} };
const LINK = { power: "20", gt: "20", ltx: "1", gr: "60", lrx: "1", ts: "50", lother: "3", freqMHz: "8450", bwkHz: "2000", rbkbps: "1000", ebn0: "2.5" };
const UP = { power: "5", gt: "3", ltx: "1", gr: "20", lrx: "1", ts: "400", lother: "2", freqMHz: "2250", rbkbps: "1000", ebn0: "2.5" };
const DOWN = { power: "50", gt: "30", ltx: "1", gr: "60", lrx: "1", ts: "50", lother: "3", freqMHz: "8450", rbkbps: "1000", ebn0: "2.5" };
const fillLink = async (prefix, vals) => { for (const [k, v] of Object.entries(vals)) await setValue(`#${prefix}-${k}`, v); };

await size(1440, 900);
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
await evaluate("try { localStorage.removeItem('luna-ops.params-docked.v1'); sessionStorage.clear(); } catch (e) {} true");
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447");
await evaluate(`(() => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  for (const [id, v] of [['#start', '2026-12-13T00:00'], ['#end', '2026-12-20T00:00']]) { const e = document.querySelector(id); set.call(e, v); e.dispatchEvent(new Event('input', { bubbles: true })); } return true; })()`);
await waitFor("/covers this point/.test([...document.querySelectorAll('#coord-hint, .explorer .hint[aria-live]')].map(e => e.textContent).join(' '))", 60000, "coverage");
out.tabs = await evaluate("[...document.querySelectorAll('button.tab')].map(b => b.textContent.trim())");
out.topbarOverflow1440 = await evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth");
await tab("Comms"); await waitFor("document.querySelector('.comms')", 30000, "comms view"); await sleep(500);
await shot("01-desktop-comms-before-analysis", null);
const t0 = Date.now();
await evaluate("document.querySelector('.comms-run')?.click(); true");
await waitFor("document.querySelector('.comms-timeline svg')", 300000, "simulation");
out.firstSimulationMs = Date.now() - t0;
await sleep(1200); await top0(); await shot("02-desktop-comms-direct-geometry", null);
out.engineLabels = await evaluate("[...document.querySelectorAll('.comms .mission-badges .status-badge')].map(b => b.textContent)");
out.directRfBefore = await text(".comms .metrics .metric:nth-of-type(8) dd");
// direct link budget (illustrative values)
await scrollTo("#comms-link"); await fillLink("cl-direct", LINK); await sleep(2200);
out.directBudget = await evaluate("[...document.querySelectorAll('.comms-breakdown table')].slice(0,1).map(t => [...t.querySelectorAll('tbody tr')].map(r => r.textContent.replace(/\\s+/g, ' ').trim()))[0]");
out.directStatus = await text(".comms-linkstatus");
await scrollTo("#comms-link"); await sleep(300); await shot("03-desktop-link-budget-direct", null);
// an invalid value is reported and not used
await setValue("#cl-direct-rbkbps", "0"); await sleep(1800);
out.invalidRate = { status: await text(".comms-linkstatus"), problems: await text(".comms-breakdown ul.bad") };
await shot("04-desktop-link-budget-invalid", null);
await setValue("#cl-direct-rbkbps", "1000"); await sleep(1500);
// hypothetical relay H1 (apoapsis over the lunar south; illustrative)
await scrollTo("#comms-relay");
await evaluate("document.querySelector('.comms-toggle input').click(); true"); await sleep(400);
for (const [k, v] of [["name", "H1 illustrative"], ["a", "6000"], ["e", "0.6"], ["i", "60"], ["raan", "0"], ["argp", "90"], ["m0", "0"], ["step", "60"]]) await setValue(`#cr-${k}`, v);
await setSelect("#cr-frame", "LME_EPOCH");
await waitFor("document.querySelector('section[aria-labelledby=comms-relay] table')", 120000, "relay"); await sleep(1500);
out.relayTable = await evaluate("[...document.querySelectorAll('#comms-relay ~ * table tbody tr, section[aria-labelledby=comms-relay] table tbody tr')].map(r => r.textContent.replace(/\\s+/g, ' ').trim())");
await scrollTo("#comms-relay"); await sleep(300); await shot("05-desktop-relay", null);
// relay link budgets
await clickText(".comms-linktabs button", "Lander to relay"); await sleep(300); await fillLink("cl-up", UP);
await clickText(".comms-linktabs button", "Relay to Earth"); await sleep(300); await fillLink("cl-down", DOWN); await sleep(2500);
out.relayDownStatus = await text(".comms-linkstatus");
await clickText(".comms-linktabs button", "Lander to relay"); await sleep(500);
out.relayUpStatus = await text(".comms-linkstatus");
await scrollTo("#comms-link"); await sleep(300); await shot("06-desktop-link-budget-uplink", null);
// timeline with everything
await scrollTo("#comms-timeline"); await sleep(400); await shot("07-desktop-timeline", null);
out.timelineRows = await evaluate("[...document.querySelectorAll('.comms-timeline .ct-label')].map(t => t.textContent)");
// cursor
await evaluate(`(() => { const r = document.querySelector('#comms-cursor'); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(r, String(Math.floor(r.max * 0.6))); r.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
await sleep(500);
out.directAtCursor = await evaluate("[...document.querySelectorAll('section[aria-labelledby=comms-direct] .metric')].map(m => m.textContent.replace(/\\s+/g, ' ').trim())");
await scrollTo("#comms-direct"); await sleep(300); await shot("08-desktop-direct-cursor", null);
// store and forward + comparison
await setValue("#cd-vol", "20000"); await setValue("#cd-rate", "1000"); await setSelect("#cd-path", "any_rf"); await sleep(2200);
out.dtn = await evaluate("[...document.querySelectorAll('section[aria-labelledby=comms-dtn] .metric')].map(m => m.textContent.replace(/\\s+/g, ' ').trim())");
out.comparison = await evaluate("[...document.querySelectorAll('.comms-cmp tbody tr')].map(r => r.textContent.replace(/\\s+/g, ' ').trim())");
await scrollTo("#comms-compare"); await sleep(300); await shot("09-desktop-comparison-dtn", null);
await scrollTo("#comms-provenance"); await sleep(300); await shot("10-desktop-provenance", null);
out.provenance = (await text(".comms .landing-prov")).slice(0, 700);
// mission dashboard: candidate card block and the Communication action
await tab("Mission"); await waitFor("document.querySelector('.mission-strip')", 30000, "mission"); await sleep(700);
await clickText(".mission .quiet-button", "Add the selected site"); await sleep(800);
await scrollTo("section[aria-labelledby=mission-candidates]"); await sleep(400);
out.mission = { commsBlock: await evaluate("[...document.querySelectorAll('.cand-landing')].map(e => e.textContent).join(' || ')"),
  integrity: await evaluate("/score|probabilit|recommend|rank|best site/i.test([...document.querySelectorAll('.mission-candidates, .mission-card h2, .mission-locator')].map(e => e.textContent).join(' '))"),
  nestedLi: await evaluate("document.querySelectorAll('.mission-candidates li li').length"), h2: await evaluate("document.querySelectorAll('.mission h2').length") };
await shot("11-desktop-mission-candidate-comms", null);
await evaluate("(() => { const b = [...document.querySelectorAll('.mission-candidates button')].find(e => e.textContent.trim() === 'Communication'); b?.click(); return !!b; })()");
await waitFor("document.querySelector('.comms-timeline svg')", 60000, "comms again"); await sleep(1500);
out.returnInputs = await evaluate("['#cr-a', '#cr-argp', '#cd-vol'].map(s => document.querySelector(s)?.value).join(' / ')");
// widths
for (const [w, h, kind] of [[1920, 1000, "wide"], [1024, 768, "tablet"], [390, 844, "phone"], [320, 640, "phone320"]]) {
  await size(w, h); await sleep(1200); await top0(); await sleep(300);
  await shot(`12-${kind}-comms-top`, null);
  await scrollTo("#comms-timeline"); await sleep(500); await shot(`13-${kind}-comms-timeline`, null);
  await scrollTo("#comms-link"); await sleep(300); await shot(`14-${kind}-comms-link`, null);
  out.views[kind] = { hscroll: await hscroll(), overflowPx: await evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth"),
    timelineW: await evaluate("Math.round(document.querySelector('.comms-timeline svg')?.getBoundingClientRect().width || 0)") };
}
out.consoleErrors = consoleMsgs.filter((x) => x.type === "exception" || x.type === "error" || x.type === "log-error").slice(0, 8);
out.commsRequests = requests.filter((u) => u.includes("/api/comms/")).length;
fs.writeFileSync(path.join(OUT, "comms-preview.json"), JSON.stringify(out, null, 1));
console.log(JSON.stringify(out, null, 1));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
