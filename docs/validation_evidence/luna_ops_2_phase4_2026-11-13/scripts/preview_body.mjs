
// LUNA-OPS 2.0 Phase 4: short visual preview of the mission dashboard (one browser). Appended to the Phase 1 CDP
// harness (cdp_harness.txt). Usage: node preview.mjs --base <url> --out <dir> [--label x]
// States: empty; two candidates with session analyses (one-week Site01 and a second site, served from the backend cache);
// a comparison (2 sites x 1 window, cached). Checks recorded: the dashboard wording, six h2 sections, locator
// selection, candidate cards' latest-analysis values against the stored history, comparison cells against the API.
const LABEL = arg("--label", "phase4");
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const tab = (name) => evaluate(`(() => { const b = [...document.querySelectorAll('button.tab')].find(e => e.textContent.trim() === ${JSON.stringify(name)}); if (b) b.click(); return !!b; })()`);
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
const size = (w, h) => send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
const btn = (scope, text) => evaluate(`(() => { const b = [...document.querySelectorAll(${JSON.stringify(scope + " button")})].find(e => e.textContent.trim() === ${JSON.stringify(text)} && !e.disabled); if (b) b.click(); return !!b; })()`);
const top0 = () => evaluate("document.querySelector('.main')?.scrollTo(0, 0); window.scrollTo(0, 0); true");
const to = (sel) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (e) e.scrollIntoView({ block: 'start' }); return !!e; })()`);
const t0 = Date.now(); const log = (m) => console.log(`[${((Date.now() - t0) / 1000).toFixed(0)} s] ${m}`);
const meta = { label: LABEL };
const SEL = "section[aria-labelledby=mission-selected]", CAND = "section[aria-labelledby=mission-candidates]", CMP = "section[aria-labelledby=mission-comparison]";

await size(1440, 900);
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
await tab("Mission"); await waitFor("document.querySelector('.mission-strip')", 30000, "dashboard"); await sleep(600);
await shot(`${LABEL}-desktop-empty`, null);

// two candidates, each analysed (cached), the second analysed from its candidate card
await tab("Site"); await sleep(400);
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447");
await evaluate(`(() => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  for (const [id, v] of [['#start', '2026-11-14T00:00'], ['#end', '2026-11-21T00:00']]) { const e = document.querySelector(id); set.call(e, v); e.dispatchEvent(new Event('input', { bubbles: true })); } return true; })()`);
await waitFor("/covers this point/.test(document.querySelector('.explorer .hint[aria-live]')?.textContent || '')", 60000, "coverage 1");
await btn(".sidebar", "Add to comparison");
await evaluate("document.querySelector('.explorer-run').click(); true");
await waitFor("document.querySelector('.figures')", 900000, "analysis 1"); log("analysis 1");
await evaluate("(() => { const b = [...document.querySelectorAll('button')].find(e => e.textContent.trim() === 'Back to the Moon explorer'); b && b.click(); return true; })()"); await sleep(600);
await setValue("#lat", "-89.2"); await setValue("#lon", "200");
await waitFor("/covers this point/.test(document.querySelector('.explorer .hint[aria-live]')?.textContent || '')", 60000, "coverage 2");
await btn(".sidebar", "Add to comparison");
await tab("Mission"); await waitFor(`document.querySelectorAll('${CAND} li').length === 2`, 30000, "two candidates"); await sleep(800);
await evaluate(`[...document.querySelectorAll('${CAND} button')].find(b => b.getAttribute('aria-label') === 'Analyse 89.200° S, 200.000° E')?.click(); true`);
await waitFor("document.querySelector('.figures')", 900000, "analysis 2"); log("analysis 2");
await tab("Compare"); await sleep(500);
await evaluate("(() => { const b = [...document.querySelectorAll('button')].find(e => e.textContent.trim() === \"Add the panel's dates\"); b && b.click(); return true; })()"); await sleep(300);
await evaluate("document.querySelector('.compare-run .run-button').click(); true");
await waitFor("document.querySelector('table.matrix')", 900000, "comparison"); log("comparison");
await tab("Mission"); await waitFor("document.querySelector('.mission-cmp')", 30000, "dashboard comparison"); await sleep(1200);

// checks on what the dashboard shows
meta.h2 = await evaluate("document.querySelectorAll('.mission h2').length");
meta.wording = await evaluate("(() => { const m = document.querySelector('.mission').cloneNode(true); m.querySelectorAll('.site-coords, .mission-pad').forEach(e => e.remove()); const t = m.textContent; const hit = t.match(/score|probabilit|recommend|rank|best site/i); return hit ? hit[0] : null; })()");
meta.candidates = await evaluate(`[...document.querySelectorAll('${CAND} li')].map(li => ({ name: li.querySelector('strong')?.textContent, coverage: li.querySelector('p.hint')?.textContent,
  window: li.querySelector('.cand-window')?.textContent || null, values: [...li.querySelectorAll('.cand-v')].map(v => v.textContent), none: li.querySelector('.cand-none')?.textContent || null }))`);
meta.history = await evaluate("[...document.querySelectorAll('section[aria-labelledby=mission-history] tbody tr')].map(tr => [...tr.querySelectorAll('td')].slice(0, 5).map(td => td.textContent))");
meta.comparison = await evaluate(`[...document.querySelectorAll('${CMP} tbody tr')].map(tr => [...tr.querySelectorAll('td')].map(td => td.textContent))`);
meta.compareApi = await evaluate(`(async () => { const s = await (await fetch('/api/status')).json(); return null; })()`);
meta.links = await evaluate("[...document.querySelectorAll('section[aria-labelledby=mission-current] .mission-links button')].map(b => b.textContent)");
meta.figures = await evaluate("Object.fromEntries([...document.querySelectorAll('.mission-figures div')].map(d => [d.querySelector('dt').textContent, d.querySelector('dd').firstChild.textContent]))");

for (const [w, h, kind] of [[1440, 900, "desktop"], [1024, 768, "tablet"], [390, 844, "phone"]]) {
  await size(w, h); await sleep(1000); await top0(); await sleep(300);
  await shot(`${LABEL}-${kind}-top`, null);
  await to("section[aria-labelledby=mission-current]"); await sleep(300); await shot(`${LABEL}-${kind}-current`, null);
  await to(CAND); await sleep(300); await shot(`${LABEL}-${kind}-candidates`, null);
  await to("section[aria-labelledby=mission-history]"); await sleep(300); await shot(`${LABEL}-${kind}-history-comparison`, null);
  if (kind === "phone") await to(".mission-locator"), await sleep(300), await shot(`${LABEL}-${kind}-locator`, null);
  meta[`layout-${kind}`] = await evaluate(`({ hscroll: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    columns: new Set([...document.querySelectorAll('.mission-card')].map(e => Math.round(e.getBoundingClientRect().left))).size,
    overflow: [...document.querySelectorAll('.mission *')].filter(e => e.getBoundingClientRect().right > document.documentElement.clientWidth + 1 && !e.closest('.table-scroll')).length })`);
}
await size(1440, 900); await sleep(800);
// locator: choosing the other candidate's mark makes it the selected site
const before = await evaluate(`document.querySelector('${SEL} .explorer-coords')?.textContent`);
const marks = await evaluate("[...document.querySelectorAll('.locator-mark')].map(b => ({ label: b.getAttribute('aria-label'), disabled: b.disabled }))");
await evaluate("document.querySelector('.locator-mark:not([disabled])')?.click(); true"); await sleep(800);
meta.locator = { before, marks, after: await evaluate(`document.querySelector('${SEL} .explorer-coords')?.textContent`),
  sidebar: [await evaluate("document.querySelector('#lat').value"), await evaluate("document.querySelector('#lon').value")] };
await top0(); await sleep(300); await shot(`${LABEL}-desktop-after-locator-select`, null);
meta.consoleErrors = consoleMsgs.filter((x) => x.type === "exception" || x.type === "error" || x.type === "log-error").slice(0, 10);
fs.writeFileSync(path.join(OUT, `preview-${LABEL}.json`), JSON.stringify(meta, null, 1));
console.log(JSON.stringify(meta, null, 1));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
