
// Read the Site tab's analysis figures (Direct-to-Earth and Operational overlap) for given sites and compare them with the
// engine result JSON returned by /api/results/<id>. One headless browser; appended to the Phase 1 CDP harness.
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return false; const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
const out = [];
for (const [lat, lon] of [["-84.313534", "359.048681"], ["-78.398411", "21.869043"], ["-72.087426", "329.736798"]]) {
  await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(600);
  await setValue("#lat", lat); await setValue("#lon", lon);
  await evaluate(`(() => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    for (const [id, v] of [['#start', '2026-11-13T00:00'], ['#end', '2026-12-13T00:00']]) { const e = document.querySelector(id); set.call(e, v); e.dispatchEvent(new Event('input', { bubbles: true })); } return true; })()`);
  await waitFor("/covers this point/.test([...document.querySelectorAll('#coord-hint, .explorer .hint[aria-live]')].map(e => e.textContent).join(' '))", 60000, "coverage");
  await evaluate("document.querySelector('.explorer-run').click(); true");
  await waitFor("document.querySelector('.figures')", 600000, "analysis"); await sleep(1500);
  const ui = await evaluate(`[...document.querySelectorAll('.figures .figure')].map(f => ({ title: f.querySelector('h3')?.textContent, big: f.querySelector('.big')?.textContent,
    metrics: [...f.querySelectorAll('.metric')].map(m => m.querySelector('dt').textContent + ': ' + m.querySelector('dd').textContent) }))`);
  const rid = await evaluate("(() => { const m = [...document.querySelectorAll('a[href*=\"/api/results/\"]')].map(a => a.getAttribute('href').match(/results\\/([0-9a-f]+)/)?.[1]).find(Boolean); return m || null; })()");
  out.push({ lat, lon, resultIdFromExportLink: rid, ui: ui.filter((f) => /Direct-to-Earth|Operational overlap/.test(f.title || "")) });
}
out.forEach((o) => console.log(JSON.stringify(o)));
console.log(JSON.stringify({ consoleErrors: consoleMsgs.filter((x) => x.type === "exception" || x.type === "error").slice(0, 5) }));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
