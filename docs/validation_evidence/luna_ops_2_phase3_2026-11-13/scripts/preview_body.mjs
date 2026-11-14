
// LUNA-OPS 2.0 Phase 3: short visual preview of the analysis workspace and the comparison workspace (one browser).
// Appended to the Phase 1 CDP harness (cdp_harness.txt). Usage: node preview.mjs --base <url> --out <dir> [--label x]
// One one-week Site01 analysis and one comparison (2 sites x 1 window). Screenshots at 1440, then 1024 and 390 px of
// the same views (resized in place, no reload, so no analysis is repeated).
const LABEL = arg("--label", "phase3");
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const tab = (name) => evaluate(`(() => { const b = [...document.querySelectorAll('button.tab')].find(e => e.textContent.trim() === ${JSON.stringify(name)}); if (b) b.click(); return !!b; })()`);
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
const to = (id, block = "start") => evaluate(`(() => { const e = document.getElementById(${JSON.stringify(id)}); if (e) e.scrollIntoView({ block: ${JSON.stringify(block)} }); return !!e; })()`);
const size = (w, h) => send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
const t0 = Date.now();
const log = (m) => console.log(`[${((Date.now() - t0) / 1000).toFixed(0)} s] ${m}`);
const meta = { label: LABEL };

await size(1440, 900);
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(1000);
await tab("Site"); await sleep(500);
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447");
await evaluate(`(() => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  for (const [id, v] of [['#start', '2026-11-14T00:00'], ['#end', '2026-11-21T00:00']]) { const e = document.querySelector(id); set.call(e, v); e.dispatchEvent(new Event('input', { bubbles: true })); } return true; })()`);
await waitFor("/covers this point/.test(document.querySelector('.explorer .hint[aria-live]')?.textContent || '')", 60000, "coverage");
await evaluate("document.querySelector('.explorer-run').click(); true");
log("analysis started");
await waitFor("document.querySelector('a[href$=\"/result.json\"]') && document.querySelector('.figures')", 900000, "analysis workspace");
log("analysis workspace shown");
await sleep(2500);
const views = async (kind) => {
  await evaluate("document.querySelector('.main')?.scrollTo(0, 0); window.scrollTo(0, 0); true"); await sleep(400);
  await shot(`${LABEL}-${kind}-result-top`, null);
  for (const [id, name, wait] of [["result-summary", "summary", 300], ["result-panorama", "horizon", 500], ["result-timeline", "timeline", 400],
    ["result-visibility", "sunlight", 400], ["result-earth", "earth", 400], ["result-terrain", "terrain", 3500], ["result-validation", "validation", 400]]) {
    await to(id); await sleep(wait);
    await shot(`${LABEL}-${kind}-${name}`, null);
  }
  return evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth");
};
meta.hscroll = { desktop: await views("desktop") };
// hover panels: the sunlight chart and the horizon panorama
await to("result-visibility"); await sleep(400);
const box = await evaluate("(() => { const r = document.querySelector('.vis-sun svg').getBoundingClientRect(); return { x: r.left + r.width * 0.42, y: r.top + r.height * 0.7 }; })()");
await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: box.x, y: box.y }); await sleep(500);
await shot(`${LABEL}-desktop-sunlight-hover`, null);
await to("result-panorama"); await sleep(400);
const pbox = await evaluate("(() => { const r = document.querySelector('.panorama svg').getBoundingClientRect(); return { x: r.left + r.width * 0.55, y: r.top + r.height * 0.5 }; })()");
await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: pbox.x, y: pbox.y }); await sleep(500);
await shot(`${LABEL}-desktop-horizon-hover`, null);
// next-event button moves the shared cursor
const before = await evaluate("document.querySelector('.cursor-time').textContent");
await evaluate("document.querySelectorAll('.event-step')[1].click(); true"); await sleep(600);
meta.nextEvent = { before, after: await evaluate("document.querySelector('.cursor-time').textContent"),
  highlighted: await evaluate("document.querySelector('.event-row.is-next .event-name')?.textContent || ''") };
meta.terrain = await evaluate("({ figures: [...document.querySelectorAll('.terrain-figures .metric')].map(m => m.textContent), message: document.querySelector('#result-terrain .pane-message')?.textContent || null })");
meta.figures = await evaluate("[...document.querySelectorAll('.figure .big')].map(e => e.textContent)");
meta.badges = await evaluate("[...document.querySelectorAll('.validation-panel tbody tr')].map(tr => tr.querySelector('th').textContent + ' | ' + tr.querySelectorAll('td')[1].textContent + ' | ' + [...tr.querySelectorAll('.test-list .status-badge')].map(b => b.className.replace('status-badge ', '') + ':' + b.textContent).join(' '))");
for (const [w, h, kind] of [[1024, 768, "tablet"], [390, 844, "phone"]]) {
  await size(w, h); await sleep(1200);
  meta.hscroll[kind] = await views(kind);
}
await size(1440, 900); await sleep(800);
log("result previews done");

// comparison: Site01 and a second site, one window (the panel's dates)
await evaluate("(() => { const b = [...document.querySelectorAll('button')].find(e => e.textContent.trim() === 'Back to the Moon explorer'); if (b) b.click(); return !!b; })()"); await sleep(800);
await evaluate("(() => { const b = [...document.querySelectorAll('.sidebar button')].find(e => e.textContent.trim() === 'Add to comparison'); if (b) b.click(); return !!b; })()"); await sleep(300);
await setValue("#lat", "-89.2"); await setValue("#lon", "200"); await sleep(400);
await waitFor("/covers this point/.test(document.querySelector('.explorer .hint[aria-live]')?.textContent || '')", 60000, "coverage 2");
await evaluate("(() => { const b = [...document.querySelectorAll('.sidebar button')].find(e => e.textContent.trim() === 'Add to comparison'); if (b) b.click(); return !!b; })()"); await sleep(300);
await tab("Compare"); await sleep(600);
await evaluate("(() => { const b = [...document.querySelectorAll('button')].find(e => e.textContent.trim() === \"Add the panel's dates\"); if (b) b.click(); return !!b; })()"); await sleep(300);
await shot(`${LABEL}-desktop-compare-builder`, null);
await evaluate("document.querySelector('.compare-run .run-button').click(); true");
log("comparison started");
await waitFor("document.querySelector('table.matrix') && document.querySelector('.site-cards')", 900000, "comparison");
await waitFor("document.querySelector('.compare-chart svg')", 30000, "comparison charts");
log("comparison shown"); await sleep(1500);
meta.compare = await evaluate("({ cards: document.querySelectorAll('.site-card').length, cells: document.querySelectorAll('table.matrix td').length, scatterPoints: document.querySelectorAll('.compare-chart:nth-child(2) circle').length })");
for (const [w, h, kind] of [[1440, 900, "desktop"], [1024, 768, "tablet"], [390, 844, "phone"]]) {
  await size(w, h); await sleep(1000);
  await evaluate("document.querySelector('.compare-provenance').scrollIntoView({ block: 'start' }); true"); await sleep(400);
  await shot(`${LABEL}-${kind}-compare-cards`, null);
  await evaluate("document.querySelector('table.matrix').scrollIntoView({ block: 'center' }); true"); await sleep(400);
  await shot(`${LABEL}-${kind}-compare-matrix`, null);
  await evaluate("document.querySelector('.compare-charts').scrollIntoView({ block: 'start' }); true"); await sleep(600);
  await shot(`${LABEL}-${kind}-compare-charts`, null);
  meta.hscroll[`compare-${kind}`] = await evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth");
}
const errors = consoleMsgs.filter((x) => x.type === "exception" || x.type === "error" || x.type === "log-error");
meta.consoleErrors = errors.slice(0, 10);
fs.writeFileSync(path.join(OUT, `preview-${LABEL}.json`), JSON.stringify(meta, null, 1));
console.log(JSON.stringify(meta, null, 1));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
