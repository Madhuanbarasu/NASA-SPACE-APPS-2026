
// LUNA-OPS 2.0 Phase 3 correction: the sticky time bar on phones. Short preview (one browser): opens the cached one-week
// Site01 analysis, then at 390 px measures the bar, follows every section link and checks that the section heading lands
// below the bar, and scrolls through the page to show the bar over content. 1024 and 1440 px are measured as controls.
// Appended to the Phase 1 CDP harness (cdp_harness.txt). Usage: node timebar.mjs --base <url> --out <dir>
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
const size = (w, h) => send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
const bar = () => evaluate("(() => { const r = document.querySelector('.timebar').getBoundingClientRect(); const s = getComputedStyle(document.querySelector('.timebar .scrubber')); return { h: Math.round(r.height), top: Math.round(r.top), bottom: Math.round(r.bottom), display: s.display, rows: s.gridTemplateRows }; })()");
const out = { sizes: {} };

await size(1440, 900);
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
await evaluate("(() => { const b = [...document.querySelectorAll('button.tab')].find(e => e.textContent.trim() === 'Site'); b && b.click(); return true; })()"); await sleep(400);
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447");
await evaluate(`(() => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  for (const [id, v] of [['#start', '2026-11-14T00:00'], ['#end', '2026-11-21T00:00']]) { const e = document.querySelector(id); set.call(e, v); e.dispatchEvent(new Event('input', { bubbles: true })); } return true; })()`);
await waitFor("/covers this point/.test(document.querySelector('.explorer .hint[aria-live]')?.textContent || '')", 60000, "coverage");
await evaluate("document.querySelector('.explorer-run').click(); true");
await waitFor("document.querySelector('.timebar') && document.querySelector('.figures')", 900000, "analysis workspace");
await sleep(2000);

for (const [w, h, kind] of [[1440, 900, "desktop"], [1024, 768, "tablet"], [390, 844, "phone"]]) {
  await size(w, h); await sleep(1000);
  const m = { links: [] };
  // follow every section link; once the bar is stuck, the heading must start at or below the bar's bottom edge
  const ids = await evaluate("[...document.querySelectorAll('.section-nav a')].map(a => a.getAttribute('href').slice(1))");
  for (const id of ids) {
    await evaluate(`document.querySelector('.section-nav a[href="#${id}"]').click(); true`); await sleep(500);
    const r = await evaluate(`(() => { const sec = document.getElementById(${JSON.stringify(id)}); const hd = sec.querySelector('h2') || sec; const b = document.querySelector('.timebar').getBoundingClientRect();
      const t = hd.getBoundingClientRect(); const stuck = b.top <= 1; return { id: ${JSON.stringify(id)}, headingTop: Math.round(t.top), barBottom: Math.round(b.bottom), stuck, clear: !stuck || t.top >= b.bottom - 0.5 }; })()`);
    m.links.push(r);
    if (kind === "phone" && ["result-panorama", "result-visibility", "result-validation"].includes(id)) await shot(`timebar-${kind}-${id}`, null);
  }
  m.bar = await bar();
  if (kind === "phone") {
    // the bar itself, stuck over content mid-page, and its controls still operable
    await evaluate("document.getElementById('result-timeline').scrollIntoView({ block: 'start' }); window.scrollBy(0, 260); true"); await sleep(500);
    await shot(`timebar-${kind}-scrolled-mid`, null);
    const before = await evaluate("document.querySelector('.cursor-time').textContent");
    await evaluate("document.querySelectorAll('.timebar .event-step')[1].click(); true"); await sleep(500);
    m.nextEvent = { before, after: await evaluate("document.querySelector('.cursor-time').textContent") };
    m.controls = await evaluate("[...document.querySelectorAll('.timebar button, .timebar input')].map(e => { const r = e.getBoundingClientRect(); return { name: e.getAttribute('aria-label'), w: Math.round(r.width), h: Math.round(r.height), visible: r.width > 0 && r.height > 0 }; })");
  }
  m.hscroll = await evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth");
  out.sizes[kind] = m;
}
out.consoleErrors = consoleMsgs.filter((x) => x.type === "exception" || x.type === "error" || x.type === "log-error").slice(0, 5);
fs.writeFileSync(path.join(OUT, "timebar-check.json"), JSON.stringify(out, null, 1));
console.log(JSON.stringify(out, null, 1));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
