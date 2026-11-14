
// LUNA-OPS 2.0 Phase 2: short visual preview of the explorer stage (one browser, a few screenshots per width).
// Appended to the Phase 1 CDP harness (cdp_harness.txt). Usage: node preview.mjs --base <url> --out <dir> [--label x]
// Also measures the lunar disc on screen (Even light, centre column and row of the stage) and the layout, for the report.
const LABEL = arg("--label", "phase2");
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const tab = (name) => evaluate(`(() => { const b = [...document.querySelectorAll('button.tab')].find(e => e.textContent.trim() === ${JSON.stringify(name)}); if (b) b.click(); return !!b; })()`);
const mode = (name) => evaluate(`(() => { const b = [...document.querySelectorAll('.view-switch button')].find(e => e.textContent.trim() === ${JSON.stringify(name)}); if (b && !b.disabled) b.click(); return !!b && !b.disabled; })()`);
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
const top0 = () => evaluate("window.scrollTo(0, 0); document.querySelector('.main')?.scrollTo(0, 0); true");
const globeReady = async () => { await waitFor("document.querySelector('.globe-host canvas') && !document.querySelector('.globe-message')", 60000, "globe imagery"); await sleep(1500); };
const tilesIdle = async () => { const t0 = Date.now(); while (Date.now() - t0 < 25000) { if (!(await evaluate("!!document.querySelector('.map-status .is-busy')"))) break; await sleep(500); } await sleep(1200); };
// lunar disc on screen: longest lit run (even light) along the stage's centre column and centre row
const disc = async () => {
  await clickBtn(".segmented-mini button", "Even light"); await sleep(600);
  const r = await stageRect();
  const b64 = await shot("_measure", null);
  const m = await evaluate(`(async () => { const img = new Image(); img.src = 'data:image/png;base64,${b64}'; await img.decode();
    const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; const g = c.getContext('2d'); g.drawImage(img, 0, 0);
    const R = ${JSON.stringify(r)}; const cx = Math.round(R.x + R.width / 2) + 40, cy = Math.round(R.y + R.height / 2) + 40;
    const lum = (x, y) => { const d = g.getImageData(x, y, 1, 1).data; return 0.2126 * d[0] + 0.7152 * d[1] + 0.0722 * d[2]; };
    const run = (n, f) => { let best = 0, cur = 0; for (let i = 0; i < n; i++) { if (f(i) > 30) { cur++; best = Math.max(best, cur); } else cur = 0; } return best; };
    return { stageW: Math.round(R.width), stageH: Math.round(R.height), stageTop: Math.round(R.y), discV: run(Math.round(R.height), (i) => lum(cx, Math.round(R.y) + i)),
      discH: run(Math.round(R.width), (i) => lum(Math.round(R.x) + i, cy)) }; })()`);
  await clickBtn(".segmented-mini button", "Even light"); await sleep(400);
  fs.rmSync(path.join(OUT, "screenshots", "_measure.png"), { force: true });
  return m;
};
const meta = { label: LABEL, sizes: {} };
for (const [w, h, kind] of [[1440, 900, "desktop"], [1024, 768, "tablet"], [390, 844, "phone"]]) {
  await send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
  await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(1200);
  await tab("Site"); await sleep(600);
  const m = { hscroll: [] };
  // 3D Moon, opening view
  await mode("3D Moon globe"); await globeReady(); await top0(); await sleep(300);
  if (kind === "phone") await evaluate("document.querySelector('.explore-pane').scrollIntoView({ block: 'start' }); true");
  await sleep(400);
  await shot(`${LABEL}-${kind}-globe`, null);
  m.globe = await disc();
  m.hscroll.push(await evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"));
  if (kind === "desktop") {
    await evaluate("document.querySelector('.globe-legend summary').click(); true"); await sleep(400);
    await shot(`${LABEL}-${kind}-globe-legend-open`, null);
    await evaluate("document.querySelector('.globe-legend summary').click(); true"); await sleep(300);
  }
  // South polar map
  await mode("South polar map"); await waitFor("document.querySelector('.map-host canvas')", 60000, "map"); await tilesIdle(); await top0();
  if (kind === "phone") await evaluate("document.querySelector('.explore-pane').scrollIntoView({ block: 'start' }); true");
  await sleep(400);
  await shot(`${LABEL}-${kind}-map`, null);
  m.map = await evaluate("(() => { const r = document.querySelector('.map-stage').getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height), top: Math.round(r.top) }; })()");
  m.hscroll.push(await evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"));
  if (kind === "desktop") {
    // a registered site (Site01): one selection shared by the map, the globe and the local terrain
    await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447");
    await waitFor("/covers this point/.test(document.querySelector('.explorer .hint[aria-live]')?.textContent || '')", 60000, "coverage");
    await tilesIdle(); await top0(); await sleep(600);
    await shot(`${LABEL}-${kind}-map-site`, null);
    await mode("3D Moon globe"); await globeReady(); await top0(); await sleep(400);
    await shot(`${LABEL}-${kind}-globe-site`, null);
    m.globeSiteCentre = await evaluate("document.querySelector('.globe-readout-mini span')?.textContent || ''");
    await mode("Local terrain"); await waitFor("document.querySelector('.terrain-stats li') && !document.querySelector('.terrain-preview-stage .pane-empty')", 120000, "terrain"); await sleep(1500); await top0();
    await shot(`${LABEL}-${kind}-terrain`, null);
    m.terrain = await evaluate("(() => { const r = document.querySelector('.terrain-preview-stage').getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height) }; })()");
    // under the stage: the introduction, readiness board and steps
    await evaluate("document.querySelector('.welcome-details').scrollIntoView({ block: 'start' }); true"); await sleep(500);
    await shot(`${LABEL}-${kind}-below-stage`, null);
    // a comparison candidate (Site01) and a new selection: the candidate ring on the map and on the globe
    await clickBtn("button", "Add to comparison"); await sleep(400);
    await setValue("#lat", "-89.2"); await setValue("#lon", "200");
    await mode("South polar map"); await waitFor("document.querySelector('.map-host canvas')", 60000, "map"); await sleep(800);
    await evaluate("(() => { const b = document.querySelector('.map-tools button[aria-label^=\"Centre\"]'); if (b) b.click(); return true; })()"); await sleep(800);
    await tilesIdle(); await top0(); await sleep(500);
    await shot(`${LABEL}-${kind}-map-candidate`, null);
    await mode("3D Moon globe"); await globeReady(); await top0(); await sleep(400);
    await evaluate("(() => { const b = document.querySelector('.globe-nav button[aria-label^=\"Centre the view\"]'); if (b) b.click(); return true; })()"); await sleep(1200);
    await evaluate("document.querySelector('.globe-legend summary').click(); true"); await sleep(400);
    await shot(`${LABEL}-${kind}-globe-candidate`, null);
    m.candidateCentre = await evaluate("document.querySelector('.globe-readout-mini span')?.textContent || ''");
    await setValue("#lat", ""); await setValue("#lon", ""); await mode("South polar map"); await sleep(500);
  }
  meta.sizes[kind] = m;
}
const errors = consoleMsgs.filter((x) => x.type === "exception" || x.type === "error" || x.type === "log-error");
meta.consoleErrors = errors.slice(0, 10);
fs.writeFileSync(path.join(OUT, `preview-${LABEL}.json`), JSON.stringify(meta, null, 1));
console.log(JSON.stringify(meta, null, 1));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
