
// LUNA-OPS 2.0 Phase 4 UI corrections: short measurement and screenshot run (one browser), used before and after the
// fixes. Appended to the Phase 1 CDP harness (cdp_harness.txt). Usage: node ui_fixes.mjs --base <url> --out <dir> --label before|after
//  1. Data and validation: the validation report table (column widths, whether a status wraps, horizontal scroll on phones)
//  2. Analysis result (custom site): blank space under the South Polar Map in the terrain section
//  3. Guide against Data and validation: container position and width at 1440, 1024 and 390 px
const LABEL = arg("--label", "run");
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const tab = (name) => evaluate(`(() => { const b = [...document.querySelectorAll('button.tab')].find(e => e.textContent.trim() === ${JSON.stringify(name)}); if (b) b.click(); return !!b; })()`);
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
const size = (w, h) => send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
const top0 = () => evaluate("document.querySelector('.main')?.scrollTo(0, 0); window.scrollTo(0, 0); true");
const out = { label: LABEL, report: {}, map: {}, layout: {} };

// the validation report table: the table that follows the report heading on the Data page
const REPORT = "(() => { const h = [...document.querySelectorAll('.prose h2')].find(e => /Validation report/i.test(e.textContent)); let n = h && h.nextElementSibling; while (n && !n.querySelector('table')) n = n.nextElementSibling; return n; })()";
const measureReport = () => evaluate(`(() => { const box = ${REPORT}; if (!box) return null; const t = box.querySelector('table');
  const heads = [...t.querySelectorAll('thead th')].map(th => ({ text: th.textContent.trim(), w: Math.round(th.getBoundingClientRect().width) }));
  const statusCells = [...t.querySelectorAll('tbody tr')].map(tr => tr.children[2]);
  const lines = (el) => { const tw = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); const ys = new Set(); for (let n = tw.nextNode(); n; n = tw.nextNode()) { if (!n.textContent.trim()) continue; const r = document.createRange(); r.selectNodeContents(n); for (const q of r.getClientRects()) ys.add(Math.round(q.top)); } return ys.size; };
  const wrapped = statusCells.filter(c => lines(c) > 1).map(c => c.textContent.trim());
  return { heads, rows: statusCells.length, statusWords: [...new Set(statusCells.map(c => c.textContent.trim()))], wrappedStatuses: wrapped.length, wrappedExamples: wrapped.slice(0, 3),
    scrollable: box.scrollWidth > box.clientWidth + 1, boxW: Math.round(box.clientWidth), tableW: Math.round(t.scrollWidth) }; })()`);
const container = () => evaluate("(() => { const p = document.querySelector('.prose'); const r = p.getBoundingClientRect(); const h2 = p.querySelector('h2').getBoundingClientRect(); const para = p.querySelector('h2 ~ p, h2 ~ dl dd'); const pr = para ? para.getBoundingClientRect() : null; const head = p.querySelector('.site-header').getBoundingClientRect(); return { left: Math.round(r.left), width: Math.round(r.width), headerLeft: Math.round(head.left), h2Left: Math.round(h2.left), h2Width: Math.round(h2.width), firstTextWidth: pr ? Math.round(pr.width) : null, hscroll: document.documentElement.scrollWidth > document.documentElement.clientWidth }; })()");

await size(1440, 900);
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);

// 1 + 3: Data and Guide at three widths
for (const [w, h, kind] of [[1440, 900, "desktop"], [1024, 768, "tablet"], [390, 844, "phone"]]) {
  await size(w, h); await sleep(600);
  await tab("Data and validation"); await waitFor("document.querySelector('.prose h2')", 30000, "data"); await sleep(500); await top0(); await sleep(200);
  out.layout[`data-${kind}`] = await container();
  await shot(`${LABEL}-${kind}-data-top`, null);
  if (kind !== "tablet") {
    out.report[kind] = await measureReport();
    await evaluate(`(${REPORT}).scrollIntoView({ block: 'center' }); true`); await sleep(300);
    await shot(`${LABEL}-${kind}-validation-report`, null);
  }
  await tab("Guide"); await waitFor("document.querySelector('.prose h2')", 30000, "guide"); await sleep(500); await top0(); await sleep(200);
  out.layout[`guide-${kind}`] = await container();
  await shot(`${LABEL}-${kind}-guide-top`, null);
}

// 2: the analysis result's terrain section (cached Site01 one-week analysis)
await size(1440, 900); await sleep(400);
await tab("Site"); await sleep(400);
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447");
await evaluate(`(() => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  for (const [id, v] of [['#start', '2026-11-14T00:00'], ['#end', '2026-11-21T00:00']]) { const e = document.querySelector(id); set.call(e, v); e.dispatchEvent(new Event('input', { bubbles: true })); } return true; })()`);
await waitFor("/covers this point/.test(document.querySelector('.explorer .hint[aria-live]')?.textContent || '')", 60000, "coverage");
await evaluate("document.querySelector('.explorer-run').click(); true");
await waitFor("document.querySelector('#result-terrain .map-host canvas') && document.querySelector('.terrain-figures')", 900000, "result terrain");
await sleep(2500);
const mapMeasure = () => evaluate(`(() => { const panes = [...document.querySelectorAll('#result-terrain .terrain-grid > .pane')]; const m = panes[0], t = panes[1];
  const stage = m.querySelector('.pane-body').getBoundingClientRect(), note = m.querySelector('.pane-note').getBoundingClientRect(), pr = m.getBoundingClientRect();
  return { mapPaneH: Math.round(pr.height), terrainPaneH: Math.round(t.getBoundingClientRect().height), stageH: Math.round(stage.height), stageW: Math.round(stage.width),
    blankBelowCaption: Math.round(pr.bottom - note.bottom), canvasH: Math.round(m.querySelector('.map-host canvas')?.getBoundingClientRect().height ?? 0),
    controls: !!m.querySelector('.ol-zoom') && !!m.querySelector('.map-tools') && !!m.querySelector('.map-legend') && !!m.querySelector('.map-readout') }; })()`);
for (const [w, h, kind] of [[1440, 900, "desktop"], [1024, 768, "tablet"], [390, 844, "phone"]]) {
  await size(w, h); await sleep(1500);
  await evaluate("document.getElementById('result-terrain').scrollIntoView({ block: 'start' }); true"); await sleep(1200);
  out.map[kind] = await mapMeasure();
  await shot(`${LABEL}-${kind}-result-terrain`, null);
  if (kind === "phone") { await evaluate("document.querySelector('#result-terrain .terrain-grid > .pane .pane-note').scrollIntoView({ block: 'center' }); true"); await sleep(500); await shot(`${LABEL}-${kind}-result-map-caption`, null); }
}
out.consoleErrors = consoleMsgs.filter((x) => x.type === "exception" || x.type === "error" || x.type === "log-error").slice(0, 5);
fs.writeFileSync(path.join(OUT, `ui-fixes-${LABEL}.json`), JSON.stringify(out, null, 1));
console.log(JSON.stringify(out, null, 1));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
