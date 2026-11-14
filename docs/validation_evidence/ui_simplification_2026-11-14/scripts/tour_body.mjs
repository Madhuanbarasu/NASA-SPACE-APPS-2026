
// Screenshot tour of every view (baseline before the UI redesign, repeated after it). One headless browser.
// Prepares: Site01 analysis (13-20 Nov 2026), a landing screening, a 2-site x 1-window comparison; then captures each
// view at 1920/1440/1024/390/320 px (viewport) and, at 1440 px, the view scrolled to the middle and the end.
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return false; const proto = e.tagName === 'SELECT' ? HTMLSelectElement.prototype : HTMLInputElement.prototype; Object.getOwnPropertyDescriptor(proto, 'value').set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
const clickText = (sel, re) => evaluate(`(() => { const b = [...document.querySelectorAll(${JSON.stringify(sel)})].find((x) => new RegExp(${JSON.stringify(re)}).test(x.textContent.trim()) && !x.disabled); if (!b) return false; b.click(); return true; })()`);
const size = (w, h) => send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
const withTimeout = (pr, ms) => Promise.race([pr, new Promise((r) => setTimeout(() => r(null), ms))]);
const timeouts = [];
const snap = async (name) => { for (let k = 0; k < 2; k++) { const r = await withTimeout(send("Page.captureScreenshot", { format: "png" }), 15000);
  if (r && r.data) { fs.writeFileSync(path.join(OUT, "screenshots", name + ".png"), Buffer.from(r.data, "base64")); return; } await sleep(1000); } timeouts.push(name); };
const until = async (expr, ms, what) => { const t = Date.now(); while (Date.now() - t < ms) { if (await evaluate(expr)) return true; await sleep(1000); } console.log("timeout waiting for", what); return false; };
const tab = async (id) => { if (id === "data") await evaluate("location.hash = '#data'; true");
  else await evaluate(`(() => { if (location.hash) { history.replaceState(null, '', location.pathname); } const t = document.querySelector('#tab-${id}'); if (t) t.click(); return !!t; })()`);
  await sleep(1500); };
const scrollTo = (frac) => evaluate(`(() => { const m = document.querySelector('.main'); const tgt = m && m.scrollHeight > m.clientHeight + 4 ? m : document.scrollingElement; tgt.scrollTop = Math.round((tgt.scrollHeight - tgt.clientHeight) * ${frac}); return tgt.scrollHeight; })()`);

await size(1440, 900);
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(1000);
await tab("site");
await setValue("#start", "2026-11-13T00:00"); await setValue("#end", "2026-11-20T00:00");
// two comparison sites, then Site01 selected
await setValue("#lat", "-84.313534"); await setValue("#lon", "359.048681"); await sleep(1200);
await clickText("aside button", "^Add to comparison$"); await sleep(400);
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447"); await sleep(1500);
await clickText("aside button", "^Add to comparison$"); await sleep(400);
await snap("prep-site-explorer");
// Site01 analysis
await until("(() => { const b = document.querySelector('aside .run-button'); return !!b && !b.disabled; })()", 120000, "run enabled");
await evaluate("(() => { const b = document.querySelector('aside .run-button'); b && b.click(); return !!b; })()");
await until("/What the horizon looks like/.test(document.querySelector('main')?.innerText || '')", 600000, "analysis");
await sleep(2000);
// landing screening
await tab("landing");
await until("(() => { const b = document.querySelector('.landing-run'); return !!b && !b.disabled; })()", 120000, "landing run enabled");
await evaluate("(() => { const b = document.querySelector('.landing-run'); b && b.click(); return !!b; })()");
await until("!!document.querySelector('.landing-map canvas')", 300000, "landing"); await sleep(3000);
// comparison 2 sites x 1 window
await tab("compare");
await clickText("main button", "^Add the panel's dates$"); await sleep(500);
await until("(() => { const b = [...document.querySelectorAll('main .run-button')].find((x) => /^Compare /.test(x.textContent.trim())); return !!b && !b.disabled; })()", 60000, "compare run enabled");
await clickText("main .run-button", "^Compare ");
await until("/Comparison matrix|Which site is better for what/i.test(document.querySelector('main')?.innerText || '')", 900000, "comparison"); await sleep(2000);
await tab("comms"); await sleep(4000);

const layout = [];
const VIEWS = ["mission", "site", "landing", "comms", "compare", "guide", "data"];
for (const [w, h] of [[1920, 1080], [1440, 900], [1024, 768], [390, 844], [320, 640]]) {
  await size(w, h); await sleep(1200);
  for (const v of VIEWS) {
    await tab(v); await scrollTo(0); await sleep(1500);
    await snap(`${v}-${w}`);
    layout.push({ view: v, width: w, ...(await evaluate(`(() => { const vw = document.documentElement.clientWidth;
      const inScroller = (e) => { let p = e.parentElement; while (p && p !== document.body) { const s = getComputedStyle(p); if (/(auto|scroll|hidden)/.test(s.overflowX) && p.scrollWidth > p.clientWidth + 1) return true; p = p.parentElement; } return false; };
      const all = [...document.querySelectorAll('main *')].filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
      return { hscroll: document.documentElement.scrollWidth > vw, outside: all.filter((e) => e.getBoundingClientRect().right > vw + 1 && !inScroller(e)).length }; })()`)) });
    if (w === 1440) { await scrollTo(0.5); await sleep(800); await snap(`${v}-${w}-mid`); await scrollTo(1); await sleep(800); await snap(`${v}-${w}-end`); }
  }
  console.log("width done", w);
}
const errs = consoleMsgs.filter((x) => /error|exception/.test(x.type));
fs.writeFileSync(path.join(OUT, "tour.json"), JSON.stringify({ consoleErrors: errs, screenshotTimeouts: timeouts, layout }, null, 1));
console.log("console errors", errs.length, "screenshot timeouts", timeouts.length, "layout problems", layout.filter((l) => l.hscroll || l.outside).length, JSON.stringify(layout.filter((l) => l.hscroll || l.outside)));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
