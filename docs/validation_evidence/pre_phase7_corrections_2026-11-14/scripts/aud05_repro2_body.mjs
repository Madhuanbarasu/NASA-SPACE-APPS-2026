
// AUD-05 reproduction (variant 2): the screening is run at 1920 px and the new hazard map is captured while its backdrop tiles arrive.
// Screenshots of the map pane at fixed delays after the resize to 1920 px, each with the list of zoom-11 backdrop tiles
// that had finished loading by then. One headless browser; appended to the Phase 1 CDP harness. Read only.
const T0 = Date.now();
const net = new Map();
ws.addEventListener("message", (m) => {
  const msg = JSON.parse(m.data); const p = msg.params;
  if (msg.method === "Network.requestWillBeSent") net.set(p.requestId, { url: p.request.url, t: Date.now() - T0 });
  else if (msg.method === "Network.responseReceived") { const r = net.get(p.requestId); if (r) r.status = p.response.status; }
  else if (msg.method === "Network.loadingFinished") { const r = net.get(p.requestId); if (r) r.done = Date.now() - T0; }
});
await send("Runtime.enable"); await send("Page.enable"); await send("Network.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return false; const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
const size = (w, h) => send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: false });
await size(1920, 1080);
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447");
await evaluate("document.querySelector('#tab-landing').click(); true");
await waitFor("document.querySelector('.landing-run') && !document.querySelector('.landing-run').disabled", 60000, "landing run enabled");
await evaluate("document.querySelector('.landing-run').click(); true");
await waitFor("document.querySelector('.landing-map canvas')", 300000, "landing screening");
const out = { shots: [] };
const tResize = Date.now() - T0;   // here: the moment the new hazard map appeared
for (const ms of [0, 120, 250, 400, 600, 900, 1500, 4000]) {
  const wait = tResize + ms - (Date.now() - T0); if (wait > 0) await sleep(wait);
  await evaluate("(() => { document.querySelector('section[aria-labelledby=landing-map]').scrollIntoView({ block: 'start' }); return true; })()");
  const t = Date.now() - T0;
  const rect = await evaluate(`(() => { const b = document.querySelector('.landing-map.pane-body').getBoundingClientRect(); return { x: b.left, y: b.top, width: b.width, height: b.height }; })()`);
  const { data } = await send("Page.captureScreenshot", { format: "png", clip: { ...rect, scale: 1 } });
  const name = `aud05-repro2-after-map-${ms}ms`;
  fs.writeFileSync(path.join(OUT, "screenshots", `${name}.png`), Buffer.from(data, "base64"));
  const z11 = [...net.values()].filter((r) => /\/api\/tiles\/11\//.test(r.url) && r.t >= tResize);
  out.shots.push({ name, msAfterResize: t - tResize, rect, z11Requested: z11.length,
    z11Done: z11.filter((r) => r.done != null && r.done <= t).map((r) => r.url.replace(/.*\/tiles\//, "")) });
}
out.extent = await evaluate("null");
fs.writeFileSync(path.join(OUT, "aud05-repro2.json"), JSON.stringify(out, null, 1));
console.log(JSON.stringify(out.shots.map((s) => [s.name, s.msAfterResize, s.z11Requested, s.z11Done.length, s.z11Done.join(" ")]), null, 1));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
