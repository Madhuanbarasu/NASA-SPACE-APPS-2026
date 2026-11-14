
// Probe (read only): which element inside a result figure card is wider than the card under the WCAG 1.4.12 text-spacing
// override used by the U-04 audit. Opens a cached Site01 result.
await send("Runtime.enable"); await send("Page.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
await evaluate("document.querySelector('#tab-site').click(); true");
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447");
await setValue("#start", "2026-11-13T00:00"); await setValue("#end", "2026-11-14T00:00");
await waitFor("!document.querySelector('.sidebar .run-button').disabled", 60000, "analyse");
await evaluate("document.querySelector('.sidebar .run-button').click(); true");
await waitFor("document.querySelector('.figures .figure')", 300000, "figures"); await sleep(1500);
await evaluate(`(() => { const s = document.createElement('style'); s.textContent = '* { line-height: 1.5 !important; letter-spacing: 0.12em !important; word-spacing: 0.16em !important; } p { margin-bottom: 2em !important; }'; document.head.appendChild(s); return true; })()`);
await sleep(400);
const out = await evaluate(`[...document.querySelectorAll('.figures .figure')].map(f => { const fr = f.getBoundingClientRect();
  const wide = [...f.querySelectorAll('*')].map(e => { const r = e.getBoundingClientRect(); return { e, r, sw: e.scrollWidth, cw: e.clientWidth }; })
    .filter(x => x.r.right > fr.right - 1 + 0.5 || x.sw > x.cw + 1)
    .map(x => ({ tag: x.e.tagName.toLowerCase() + (x.e.className && typeof x.e.className === 'string' ? '.' + x.e.className.split(' ').join('.') : ''), text: x.e.textContent.slice(0, 40),
      right_over: Math.round(x.r.right - fr.right), sw: x.sw, cw: x.cw, width: Math.round(x.r.width), ws: getComputedStyle(x.e).whiteSpace, disp: getComputedStyle(x.e).display }));
  return { fig: f.className, sw: f.scrollWidth, cw: f.clientWidth, wide: wide.slice(0, 8) }; })`);
console.log(JSON.stringify(out, null, 1));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
