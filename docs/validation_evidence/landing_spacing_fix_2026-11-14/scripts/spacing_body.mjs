
// Landing tab spacing check (Selected landing site, Terrain analysis): blank space below each card, overlap and
// horizontal overflow at 1440, 1024 and 390 px, before and after a screening. One headless browser; appended to the
// Phase 1 CDP harness (cdp_harness.txt). Usage: node spacing.mjs --base <url> --out <dir> --label before|after
const LABEL = arg("--label", "run");
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return false; const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
const size = (w, h) => send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
const scrollTo = (sel) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (e) e.scrollIntoView({ block: 'start' }); return !!e; })()`);
const top0 = () => evaluate("document.querySelector('.main')?.scrollTo(0, 0); window.scrollTo(0, 0); true");
// blank space below a card: from its bottom edge to the next card below it in the same column (or the next full-width
// section); 16 px is the layout gap
const measure = () => evaluate(`(() => {
  const cards = [...document.querySelectorAll('.landing .landing-card')];
  const r = (e) => e.getBoundingClientRect();
  const res = {};
  for (const c of cards) {
    const id = (c.getAttribute('aria-labelledby') || 'card').replace('landing-', ''); const b = r(c);
    const below = cards.map(r).filter(o => o.top >= b.bottom - 1 && o.left < b.right - 1 && o.right > b.left + 1).map(o => o.top);
    const content = [...c.children].reduce((m, k) => Math.max(m, r(k).bottom), b.top);
    res[id] = { top: Math.round(b.top), h: Math.round(b.height), left: Math.round(b.left), w: Math.round(b.width),
      blankBelow: below.length ? Math.round(Math.min(...below) - b.bottom) : null,
      emptyInside: Math.round(b.bottom - content) };
  }
  const overlaps = [];
  for (let i = 0; i < cards.length; i++) for (let j = i + 1; j < cards.length; j++) {
    const a = r(cards[i]), b = r(cards[j]);
    if (a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1) overlaps.push(i + '-' + j);
  }
  return { cards: res, overlaps, hscroll: document.documentElement.scrollWidth > document.documentElement.clientWidth }; })()`);
const out = { label: LABEL, before_run: {}, after_run: {} };

await size(1440, 900);
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
await evaluate("try { localStorage.removeItem('luna-ops.params-docked.v1'); } catch (e) {} true");
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447");
await waitFor("/covers this point/.test([...document.querySelectorAll('#coord-hint, .explorer .hint[aria-live]')].map(e => e.textContent).join(' '))", 60000, "coverage");
await evaluate("[...document.querySelectorAll('button.tab')].find(e => e.textContent.trim() === 'Landing')?.click(); true");
await waitFor("document.querySelector('.landing-run') && !document.querySelector('.landing-run').disabled", 60000, "landing");
await sleep(500);
for (const [w, h, kind] of [[1440, 900, "desktop"], [1024, 768, "tablet"], [390, 844, "phone"]]) {
  await size(w, h); await sleep(600); await top0();
  out.before_run[kind] = await measure();
  await shot(`${LABEL}-${kind}-before-run`, null);
}
await size(1440, 900); await sleep(400);
await evaluate("document.querySelector('.landing-run').click(); true");
await waitFor("document.querySelectorAll('.landing-finding').length >= 5", 120000, "findings");
await setValue("#ls-tslope", "10"); await setValue("#ls-trough", "0.5"); await setValue("#ls-trelief", "10");
await waitFor("document.querySelector('.landing-map canvas')", 30000, "map"); await sleep(2500);
for (const [w, h, kind] of [[1440, 900, "desktop"], [1024, 768, "tablet"], [390, 844, "phone"]]) {
  await size(w, h); await sleep(1500); await top0();
  out.after_run[kind] = await measure();
  await shot(`${LABEL}-${kind}-top`, null);
  await scrollTo("#landing-footprint"); await sleep(400); await shot(`${LABEL}-${kind}-footprint-terrain`, null);
  await scrollTo("#landing-terrain"); await sleep(400); await shot(`${LABEL}-${kind}-terrain`, null);
}
out.consoleErrors = consoleMsgs.filter((x) => x.type === "exception" || x.type === "error" || x.type === "log-error").slice(0, 5);
fs.writeFileSync(path.join(OUT, `spacing-${LABEL}.json`), JSON.stringify(out, null, 1));
console.log(JSON.stringify(out, null, 1));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
