
// Diagnosis (before any change): geometry of the Site result's "Events and intervals" and "Sunlight" sections at 1440 px.
await send("Runtime.enable"); await send("Page.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
const W = Number(arg("--width", "1440"));
await send("Emulation.setDeviceMetricsOverride", { width: W, height: 900, deviceScaleFactor: 1, mobile: W < 800 });
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
await evaluate("document.querySelector('#tab-site').click(); true");
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447"); await setValue("#start", "2026-11-13T00:00"); await setValue("#end", "2026-11-20T00:00");
await waitFor("!document.querySelector('.sidebar .run-button').disabled", 60000, "analyse");
await evaluate("document.querySelector('.sidebar .run-button').click(); true");
await waitFor("document.querySelector('.figures')", 600000, "analysis"); await sleep(1500);
const GEO = `(() => {
  const box = (e) => { if (!e) return null; const r = e.getBoundingClientRect(), s = getComputedStyle(e);
    return { tag: e.tagName.toLowerCase(), cls: (typeof e.className === 'string' ? e.className : e.className.baseVal || '').slice(0, 60), top: Math.round(r.top + scrollY), h: Math.round(r.height), w: Math.round(r.width),
      minH: s.minHeight, height: s.height, mt: s.marginTop, mb: s.marginBottom, pt: s.paddingTop, pb: s.paddingBottom, display: s.display, alignSelf: s.alignSelf, aspect: s.aspectRatio }; };
  const kids = (e, depth) => e ? [...e.children].map(c => ({ ...box(c), kids: depth > 0 ? kids(c, depth - 1) : undefined })) : null;
  const tl = document.querySelector('#result-timeline'), sun = document.querySelector('#result-visibility');
  const grid = tl?.querySelector('.timeline-grid'), bg = sun?.querySelector('.body-grid');
  const lastBottom = (e) => Math.max(...[...e.querySelectorAll('*')].filter(x => x.getClientRects().length).map(x => x.getBoundingClientRect().bottom + scrollY));
  return { timelineSection: box(tl), timelineGrid: box(grid), timelineGridKids: kids(grid, 3), timelineContentBottom: tl ? Math.round(lastBottom(tl)) : null,
           sunSection: box(sun), sunGrid: box(bg), sunGridKids: kids(bg, 3), sunContentBottom: sun ? Math.round(lastBottom(sun)) : null,
           nextAfterSun: box(sun?.nextElementSibling) }; })()`;
const g = await evaluate(GEO);
fs.writeFileSync(path.join(OUT, `diag-${W}.json`), JSON.stringify(g, null, 1));
for (const id of ["result-timeline", "result-visibility"]) {
  await evaluate(`document.getElementById('${id}').scrollIntoView({ block: 'start' }); true`); await sleep(600);
  const { data } = await send("Page.captureScreenshot", { format: "png" });
  fs.writeFileSync(path.join(OUT, "screenshots", `before-${W}-${id}.png`), Buffer.from(data, "base64"));
}
const s = (b) => b ? `${b.cls || b.tag} h=${b.h} top=${b.top} minH=${b.minH} mb=${b.mb} pb=${b.pb}` : null;
console.log("timeline section", s(g.timelineSection), "| content bottom", g.timelineContentBottom);
console.log("timeline grid", s(g.timelineGrid)); for (const k of g.timelineGridKids || []) { console.log("  col", s(k)); for (const c of k.kids || []) console.log("    ", s(c)); }
console.log("sun section", s(g.sunSection), "| content bottom", g.sunContentBottom);
console.log("sun grid", s(g.sunGrid)); for (const k of g.sunGridKids || []) { console.log("  col", s(k)); for (const c of k.kids || []) console.log("    ", s(c)); }
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
