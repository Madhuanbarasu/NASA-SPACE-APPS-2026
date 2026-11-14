
// AUD-06 browser check: South Polar Map at several zoom levels around Site01 and the Landing hazard map's backdrop,
// with the tile requests the page made (route, status, renderer header, served from cache or not).
// --cache-test (after the fix): first loads an engine tile URL so the browser caches it, then shows the app requests the
// new /api/display/tiles/ URLs from the network (never the cached engine tiles).
// One headless browser; appended to the Phase 1 CDP harness. Read only.
// Usage: node maps.mjs --base <url> --out <dir> --label before|after [--cache-test]
const LABEL = arg("--label", "run");
const T0 = Date.now();
const net = new Map();
ws.addEventListener("message", (m) => {
  const msg = JSON.parse(m.data); const p = msg.params;
  if (msg.method === "Network.requestWillBeSent") net.set(p.requestId, { url: p.request.url, t: Date.now() - T0 });
  else if (msg.method === "Network.requestServedFromCache") { const r = net.get(p.requestId); if (r) r.servedFromCache = true; }
  else if (msg.method === "Network.responseReceived") { const r = net.get(p.requestId); if (r) { r.status = p.response.status;
    r.fromDiskCache = !!p.response.fromDiskCache; r.fromMemoryCache = !!p.response.fromMemoryCache;
    const h = Object.fromEntries(Object.entries(p.response.headers || {}).map(([k, v]) => [k.toLowerCase(), v]));
    r.renderer = h["x-lunaops-renderer"] || null; r.cacheControl = h["cache-control"] || null; } }
  else if (msg.method === "Network.loadingFinished") { const r = net.get(p.requestId); if (r) r.done = Date.now() - T0; }
});
await send("Runtime.enable"); await send("Page.enable"); await send("Network.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
const out = { label: LABEL, base: BASE, shots: [], cacheTest: null };
const tiles = (since) => [...net.values()].filter((r) => r.t >= since && /\/tiles\/\d+\/\d+\/\d+\.png/.test(r.url))
  .map((r) => ({ url: r.url.replace(BASE, ""), status: r.status ?? null, renderer: r.renderer ?? null, fromDiskCache: r.fromDiskCache ?? null,
    fromMemoryCache: r.fromMemoryCache ?? null, servedFromCache: !!r.servedFromCache, ms: r.done != null ? r.done - r.t : null }));

if (process.argv.includes("--cache-test")) {
  // a browser that already holds engine tiles (max-age 86400) from before the fix
  await send("Page.navigate", { url: BASE + "/api/tiles/7/63/64.png" }); await sleep(1500);
  await send("Page.navigate", { url: BASE + "/api/tiles/7/63/64.png" }); await sleep(1500);
  out.cacheTest = { engineUrlTwice: tiles(0) };
}
const tApp = Date.now() - T0;
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447");
await evaluate("document.querySelector('#tab-site').click(); true"); await sleep(500);
await evaluate("(() => { const b = [...document.querySelectorAll('.view-switch button')].find(x => x.textContent.trim() === 'South polar map'); b?.click(); return !!b; })()");
await waitFor("document.querySelector('.map-host canvas')", 60000, "map");
const settle = async () => { await sleep(800); try { await waitFor("!document.querySelector('.map-status .is-busy')", 60000, "tiles"); } catch { /* recorded */ } await sleep(1200); };
const mshot = async (name) => {
  const r = await evaluate(`(() => { const b = document.querySelector('.map-host').getBoundingClientRect(); return { x: b.left, y: b.top, width: b.width, height: b.height }; })()`);
  const { data } = await send("Page.captureScreenshot", { format: "png", clip: { ...r, scale: 1 } });
  fs.writeFileSync(path.join(OUT, "screenshots", `${name}.png`), Buffer.from(data, "base64"));
  out.shots.push({ name, scale: await evaluate("document.querySelector('.map-readout .scale-bar')?.textContent || null"),
    readout: await evaluate("[...document.querySelectorAll('.map-readout > span:not(.scale-bar)')].map(s => s.textContent).join(' | ') || null"),
    status: await evaluate("document.querySelector('.map-status')?.textContent || null") });
};
await evaluate("document.querySelector('.map-tools button').click(); true"); await settle(); await mshot("map-1-whole");     // reset view
await evaluate("document.querySelector('.map-tools button:nth-child(2)').click(); true"); await settle(); await mshot("map-2-site");   // centre on site
for (let i = 3; i <= 6; i++) {
  await evaluate("document.querySelector('.map-host .ol-zoom-in').click(); true"); await settle(); await mshot(`map-${i}-zoom-in-${i - 2}`);
}
out.siteTiles = tiles(tApp);

// Landing hazard map: the backdrop alone (no raster) and with the default slope raster
const tL = Date.now() - T0;
await evaluate("document.querySelector('#tab-landing').click(); true");
await waitFor("document.querySelector('.landing-run') && !document.querySelector('.landing-run').disabled", 60000, "landing run");
await evaluate("document.querySelector('.landing-run').click(); true");
await waitFor("document.querySelector('.landing-map canvas')", 300000, "landing map");
await sleep(6000);
await evaluate("document.querySelector('section[aria-labelledby=landing-map]').scrollIntoView({ block: 'start' }); true"); await sleep(500);
const lshot = async (name) => {
  const r = await evaluate(`(() => { const b = document.querySelector('.landing-map.pane-body').getBoundingClientRect(); return { x: b.left, y: b.top, width: b.width, height: b.height }; })()`);
  const { data } = await send("Page.captureScreenshot", { format: "png", clip: { ...r, scale: 1 } });
  fs.writeFileSync(path.join(OUT, "screenshots", `${name}.png`), Buffer.from(data, "base64")); out.shots.push({ name });
};
await lshot("landing-slope-default");
await evaluate("document.querySelector('input[name=ls-raster][value=none]').click(); true"); await sleep(3000); await lshot("landing-backdrop-only");
out.landingTiles = tiles(tL);
out.console = consoleMsgs.filter((x) => /error|exception|warn/.test(x.type));
const all = [...out.siteTiles, ...out.landingTiles];
out.summary = { tileRequests: all.length, routes: [...new Set(all.map((t) => t.url.replace(/\/\d+\/\d+\/\d+\.png$/, "")))],
  renderers: [...new Set(all.map((t) => t.renderer))], statuses: [...new Set(all.map((t) => t.status))],
  fromCache: all.filter((t) => t.fromDiskCache || t.fromMemoryCache || t.servedFromCache).length,
  msMedian: (() => { const v = all.map((t) => t.ms).filter((x) => x != null).sort((a, b) => a - b); return v.length ? v[Math.floor(v.length / 2)] : null; })(),
  msMax: Math.max(...all.map((t) => t.ms ?? 0)) };
fs.writeFileSync(path.join(OUT, `maps-${LABEL}.json`), JSON.stringify(out, null, 1));
console.log(JSON.stringify({ summary: out.summary, shots: out.shots, cacheTest: out.cacheTest, console: out.console.length }, null, 1));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
