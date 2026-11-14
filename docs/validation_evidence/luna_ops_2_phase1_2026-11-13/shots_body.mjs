
// Screenshots of every existing view at desktop, tablet and phone widths (the same sequence before and after Phase 1).
// Appended to the shared CDP harness by build_shots.py. Usage: node ui-shots.mjs --base <url> --out <dir> --label before|after
const LABEL = arg("--label", "run");
// --essential: skip the one long step (a fresh one-week Site analysis for the result screenshots)
const ESSENTIAL = process.argv.includes("--essential");
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
await send("Runtime.enable"); await send("Page.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const tab = (name) => evaluate(`(() => { const b = [...document.querySelectorAll('button.tab, [role=tab]')].find(e => e.textContent.trim() === ${JSON.stringify(name)}); if (b) b.click(); return !!b; })()`);
const full = async (name) => {
  // whole page: the main area scrolls inside the shell on desktop, so capture its full height by growing the viewport
  const h = await evaluate("Math.max(document.documentElement.scrollHeight, (document.querySelector('.main')?.scrollHeight || 0) + (document.querySelector('.main')?.getBoundingClientRect().top || 0))");
  return h;
};
const sizes = [[1440, 900, "desktop"], [1024, 768, "tablet"], [390, 844, "phone"]];
const meta = [];
for (const [w, h, kind] of sizes) {
  await send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
  await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(1500);
  const views = [
    ["site-welcome-map", async () => { await tab("Site"); await sleep(2500); }],
    ["mission", async () => { await tab("Mission"); await waitFor("document.querySelector('.mission')", 30000, "mission"); await sleep(800); }],
    ["compare", async () => { await tab("Compare"); await sleep(800); }],
    ["data", async () => { await tab("Data and validation"); await sleep(800); }],
    ["guide", async () => { await tab("Guide"); await sleep(800); }],
    ["site-globe", async () => { await tab("Site"); await sleep(500);
      await evaluate("(() => { const b = [...document.querySelectorAll('.view-switch button')].find(e => /globe/i.test(e.textContent)); if (b) b.click(); return true; })()");
      await waitFor("document.querySelector('.globe-host canvas')", 60000, "globe"); await sleep(3500); }],
  ];
  for (const [name, go] of views) {
    await go();
    await evaluate("window.scrollTo(0, 0); document.querySelector('.main') && document.querySelector('.main').scrollTo(0, 0); true");
    await sleep(300);
    await shot(`${LABEL}-${kind}-${name}`, null);
    meta.push({ size: [w, h], view: name, hscroll: await evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth") });
  }
  // navigation states (LUNA-OPS 2.0 Phase 1): sidebar docked/collapsed on desktop; views menu and parameters drawer below
  // 1200 px. Only taken when the shell has them (the 1.0 "before" build has neither).
  if (await evaluate("!!document.querySelector('.params-toggle')")) {
    await tab("Mission"); await sleep(900);
    if (kind === "desktop") {
      await shot(`${LABEL}-${kind}-nav-sidebar-docked`, null);
      await evaluate("document.querySelector('.params-toggle').click(); true"); await sleep(700);
      await shot(`${LABEL}-${kind}-nav-sidebar-collapsed`, null);
      await evaluate("document.querySelector('.params-toggle').click(); true"); await sleep(500);
    } else {
      await evaluate("document.querySelector('#nav-toggle').click(); true"); await sleep(600);
      await shot(`${LABEL}-${kind}-nav-menu-open`, null);
      await evaluate("document.querySelector('#nav-toggle').click(); true"); await sleep(400);
      await evaluate("document.querySelector('.params-toggle').click(); true"); await sleep(700);
      await shot(`${LABEL}-${kind}-nav-drawer-open`, null);
      await evaluate("document.querySelector('#params-close').click(); true"); await sleep(400);
    }
  }
  if (kind === "desktop" && !ESSENTIAL) {
    // a result (Site01, one week): the analysis view, top and lower sections
    await tab("Site"); await sleep(300);
    await evaluate("(() => { const b = [...document.querySelectorAll('.view-switch button')].find(e => /map/i.test(e.textContent)); if (b) b.click(); return true; })()");
    await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447");
    await evaluate(`(() => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
      for (const [id, v] of [['#start', '2026-11-14T00:00'], ['#end', '2026-11-21T00:00']]) { const e = document.querySelector(id); set.call(e, v); e.dispatchEvent(new Event('input', { bubbles: true })); } return true; })()`);
    await waitFor("/covers this point/.test(document.querySelector('.explorer .hint[aria-live]')?.textContent || '')", 60000, "coverage");
    await evaluate("document.querySelector('.explorer-run').click(); true");
    await waitFor("document.querySelector('a[href$=\"/result.json\"]')", 900000, "analysis"); await sleep(4000);
    await evaluate("document.querySelector('.main').scrollTo(0, 0); true"); await sleep(300);
    await shot(`${LABEL}-desktop-site-result-top`, null);
    await evaluate("document.getElementById('result-visibility')?.scrollIntoView({ block: 'start' }); true"); await sleep(800);
    await shot(`${LABEL}-desktop-site-result-charts`, null);
    await evaluate("document.getElementById('result-terrain')?.scrollIntoView({ block: 'start' }); true"); await sleep(2500);
    await shot(`${LABEL}-desktop-site-result-terrain`, null);
    await tab("Mission"); await sleep(1200); await shot(`${LABEL}-desktop-mission-with-result`, null);
  }
}
fs.writeFileSync(path.join(OUT, `shots-${LABEL}.json`), JSON.stringify(meta, null, 1));
console.log(JSON.stringify(meta));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
