
// LUNA-OPS 2.0 Phase 4, second UI review: before/after measurements and screenshots (one browser, cached results).
// Appended to the Phase 1 CDP harness (cdp_harness.txt). Usage: node ui_fixes2.mjs --base <url> --out <dir> --label before|after
//  1+2. Mission Overview: blank space below Selected site and Candidate sites (0 candidates, then 2 candidates and a result)
//  3.   Data and validation, Guide: container against the workspace with the Mission Parameters panel docked and collapsed
//  4.   South polar map on phones (390 and 320 px): the Legend button against the readout and scale bar
const LABEL = arg("--label", "run");
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const tab = (name) => evaluate(`(() => { const b = [...document.querySelectorAll('button.tab')].find(e => e.textContent.trim() === ${JSON.stringify(name)}); if (b) b.click(); return !!b; })()`);
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
const size = (w, h) => send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
const top0 = () => evaluate("document.querySelector('.main')?.scrollTo(0, 0); window.scrollTo(0, 0); true");
const out = { label: LABEL, mission: {}, prose: {}, map: {} };

// blank space under each dashboard card: the distance from the card's bottom edge to the next card below it in the same
// column (or to the end of the grid), i.e. space no content uses
const missionMeasure = () => evaluate(`(() => { const cards = [...document.querySelectorAll('.mission .mission-card')];
  const r = (e) => e.getBoundingClientRect(); const grid = r(document.querySelector('.mission-grid'));
  const res = {};
  for (const c of cards) {
    const id = c.getAttribute('aria-labelledby') || (c.classList.contains('mission-locator') ? 'locator' : 'card'); const b = r(c);
    const below = cards.map(r).filter(o => o.top >= b.bottom - 1 && o.left < b.right - 1 && o.right > b.left + 1).map(o => o.top);
    const nextTop = below.length ? Math.min(...below) : grid.bottom;
    res[id] = { h: Math.round(b.height), w: Math.round(b.width), left: Math.round(b.left), blankBelow: Math.round(nextTop - b.bottom) };
  }
  return { cards: res, hscroll: document.documentElement.scrollWidth > document.documentElement.clientWidth }; })()`);

await size(1440, 900);
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
await evaluate("try { localStorage.removeItem('luna-ops.params-docked.v1'); } catch (e) {} true");
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);

// ---- 1+2: mission, zero candidates
for (const [w, h, kind] of [[1440, 900, "desktop"], [1024, 768, "tablet"], [390, 844, "phone"]]) {
  await size(w, h); await sleep(500);
  await tab("Mission"); await waitFor("document.querySelector('.mission-strip')", 30000, "mission"); await sleep(700); await top0();
  out.mission[`empty-${kind}`] = await missionMeasure();
  await shot(`${LABEL}-${kind}-mission-empty`, null);
}
// ---- 3: Data and Guide, panel docked and collapsed (1440), drawer layout (1024), phone
await size(1440, 900); await sleep(400);
const proseMeasure = () => evaluate(`(() => { const p = document.querySelector('.prose'), m = document.querySelector('.main'); const pr = p.getBoundingClientRect(), mr = m.getBoundingClientRect();
  const h2 = p.querySelector('h2').getBoundingClientRect(); const tbl = p.querySelector('table'); const tr = tbl ? tbl.getBoundingClientRect() : null;
  return { mainLeft: Math.round(mr.left), mainW: Math.round(mr.width), proseLeft: Math.round(pr.left), proseW: Math.round(pr.width), gapLeft: Math.round(pr.left - mr.left), gapRight: Math.round(mr.right - pr.right),
    h2Left: Math.round(h2.left), h2W: Math.round(h2.width), tableRight: tr ? Math.round(tr.right) : null, overflowX: document.documentElement.scrollWidth > document.documentElement.clientWidth || m.scrollWidth > m.clientWidth + 1 }; })()`);
for (const page of ["Data and validation", "Guide"]) {
  const key = page === "Guide" ? "guide" : "data";
  await size(1440, 900); await sleep(300);
  await tab(page); await waitFor("document.querySelector('.prose h2')", 30000, page); await sleep(500); await top0();
  out.prose[`${key}-1440-docked`] = await proseMeasure(); await shot(`${LABEL}-desktop-${key}-docked`, null);
  await evaluate("document.querySelector('.params-toggle').click(); true"); await sleep(600);
  out.prose[`${key}-1440-collapsed`] = await proseMeasure(); await shot(`${LABEL}-desktop-${key}-collapsed`, null);
  await evaluate("document.querySelector('.params-toggle').click(); true"); await sleep(500);
  await size(1024, 768); await sleep(600); await top0();
  out.prose[`${key}-1024`] = await proseMeasure(); await shot(`${LABEL}-tablet-${key}`, null);
  await evaluate("document.querySelector('.params-toggle').click(); true"); await sleep(600);
  out.prose[`${key}-1024-drawer-open`] = await proseMeasure(); await shot(`${LABEL}-tablet-${key}-drawer-open`, null);
  await evaluate("document.querySelector('#params-close')?.click(); true"); await sleep(400);
  await size(390, 844); await sleep(600); await top0();
  out.prose[`${key}-390`] = await proseMeasure(); await shot(`${LABEL}-phone-${key}`, null);
}

// ---- 1+2: mission with a site, two candidates and a (cached) result
await size(1440, 900); await sleep(400);
await tab("Site"); await sleep(400);
await setValue("#lat", "-89.2"); await setValue("#lon", "200");
await waitFor("/covers this point/.test(document.querySelector('.explorer .hint[aria-live]')?.textContent || '')", 60000, "coverage 2");
await evaluate("(() => { const b = [...document.querySelectorAll('.sidebar button')].find(e => e.textContent.trim() === 'Add to comparison'); b && b.click(); return true; })()");
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447");
await evaluate(`(() => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  for (const [id, v] of [['#start', '2026-11-14T00:00'], ['#end', '2026-11-21T00:00']]) { const e = document.querySelector(id); set.call(e, v); e.dispatchEvent(new Event('input', { bubbles: true })); } return true; })()`);
await waitFor("/covers this point/.test(document.querySelector('.explorer .hint[aria-live]')?.textContent || '')", 60000, "coverage 1");
await evaluate("(() => { const b = [...document.querySelectorAll('.sidebar button')].find(e => e.textContent.trim() === 'Add to comparison'); b && b.click(); return true; })()");
// ---- 4: the explorer's south polar map on phones (selected site, so the readout shows its line and the scale)
const mapMeasure = () => evaluate(`(() => { const st = document.querySelector('.map-stage'); if (!st) return null; const lg = st.querySelector('.map-legend summary'), ro = st.querySelector('.stage-readout'), sc = st.querySelector('.scale-bar');
  const r = (e) => e && e.getBoundingClientRect(); const a = r(lg), b = r(ro), s = r(sc);
  const inter = (p, q) => p && q ? Math.max(0, Math.min(p.right, q.right) - Math.max(p.left, q.left)) * Math.max(0, Math.min(p.bottom, q.bottom) - Math.max(p.top, q.top)) : 0;
  return { stageW: Math.round(r(st).width), legend: a && { w: Math.round(a.width), h: Math.round(a.height) }, overlapReadout: Math.round(inter(a, b)), overlapScale: Math.round(inter(a, s)),
    scaleVisible: !!s && s.width > 0, readoutInside: !!b && b.right <= r(st).right + 0.5 && b.left >= r(st).left - 0.5, hscroll: document.documentElement.scrollWidth > document.documentElement.clientWidth }; })()`);
for (const [w, h] of [[390, 844], [360, 740], [320, 640]]) {
  await size(w, h); await sleep(900);
  await evaluate("(() => { const b = [...document.querySelectorAll('.view-switch button')].find(e => e.textContent.trim() === 'South polar map'); b && b.click(); return true; })()");
  await waitFor("document.querySelector('.map-stage .map-host canvas')", 60000, "map"); await sleep(2500);
  await evaluate("document.querySelector('.explore-pane').scrollIntoView({ block: 'start' }); true"); await sleep(400);
  out.map[`explorer-${w}`] = await mapMeasure();
  await evaluate("document.querySelector('.map-stage').scrollIntoView({ block: 'end' }); true"); await sleep(300);
  await shot(`${LABEL}-${w}-explorer-map`, null);
}
await size(1440, 900); await sleep(600);
await evaluate("document.querySelector('.explorer-run').click(); true");
await waitFor("document.querySelector('.figures')", 900000, "analysis"); await sleep(1500);
for (const [w, h] of [[390, 844], [320, 640]]) {
  await size(w, h); await sleep(1500);
  await evaluate("document.querySelector('#result-terrain .map-stage').scrollIntoView({ block: 'end' }); true"); await sleep(1500);
  out.map[`result-${w}`] = await mapMeasure();
  await shot(`${LABEL}-${w}-result-map`, null);
}
await size(1440, 900); await sleep(500);
await tab("Mission"); await waitFor("document.querySelectorAll('section[aria-labelledby=mission-candidates] li').length === 2", 30000, "candidates"); await sleep(800);
for (const [w, h, kind] of [[1440, 900, "desktop"], [1024, 768, "tablet"], [390, 844, "phone"]]) {
  await size(w, h); await sleep(800); await top0(); await sleep(300);
  out.mission[`populated-${kind}`] = await missionMeasure();
  await shot(`${LABEL}-${kind}-mission-top`, null);
  await evaluate("document.querySelector('section[aria-labelledby=mission-candidates]').scrollIntoView({ block: 'start' }); true"); await sleep(300);
  await shot(`${LABEL}-${kind}-mission-candidates`, null);
}
out.consoleErrors = consoleMsgs.filter((x) => x.type === "exception" || x.type === "error" || x.type === "log-error").slice(0, 5);
fs.writeFileSync(path.join(OUT, `ui-fixes2-${LABEL}.json`), JSON.stringify(out, null, 1));
console.log(JSON.stringify(out, null, 1));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
