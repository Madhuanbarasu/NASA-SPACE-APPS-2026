
// Diagnosis: the landing hazard map at several terrain products / windows. Records every tile and landing-layer
// request (status, duration, failures), console errors, and how much of the map canvas is actually painted.
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable"); await send("Network.enable");
const reqs = new Map(); const net = [];
ws.addEventListener("message", (m) => { const msg = JSON.parse(m.data); const p = msg.params || {};
  if (msg.method === "Network.requestWillBeSent" && /\/api\/(display\/tiles|landing|tiles)/.test(p.request.url)) reqs.set(p.requestId, { url: p.request.url.replace(BASE, ""), t0: p.timestamp });
  if (msg.method === "Network.responseReceived" && reqs.has(p.requestId)) Object.assign(reqs.get(p.requestId), { status: p.response.status });
  if (msg.method === "Network.loadingFinished" && reqs.has(p.requestId)) { const r = reqs.get(p.requestId); r.ms = Math.round((p.timestamp - r.t0) * 1000); net.push(r); reqs.delete(p.requestId); }
  if (msg.method === "Network.loadingFailed" && reqs.has(p.requestId)) { const r = reqs.get(p.requestId); r.failed = p.errorText; r.ms = Math.round((p.timestamp - r.t0) * 1000); net.push(r); reqs.delete(p.requestId); } });
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const proto = e.tagName === 'SELECT' ? HTMLSelectElement.prototype : HTMLInputElement.prototype; Object.getOwnPropertyDescriptor(proto, 'value').set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
// painted share of the map: OpenLayers draws each layer on its own canvas inside .map-host
const PAINT = `(() => { const host = document.querySelector('.landing-map .map-host'); if (!host) return null;
  const r = host.getBoundingClientRect(); const cv = [...host.querySelectorAll('canvas')];
  const per = cv.map((c) => { try { const g = c.getContext('2d'); const d = g.getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 3; i < d.length; i += 16) if (d[i] > 0) n++; return { w: c.width, h: c.height, painted: +(100 * n / (d.length / 16)).toFixed(1) }; } catch (e) { return { err: String(e) }; } });
  return { host: [Math.round(r.width), Math.round(r.height)], canvases: per,
    notes: [...document.querySelectorAll('.landing-mapcard .pane-note, .landing-mapcard .pane-empty')].map((e) => e.textContent),
    findings: [...document.querySelectorAll('.landing-findings > li')].map((li) => li.innerText.replace(/\s+/g, ' ').slice(0, 160)),
    product: document.querySelector('#ls-product')?.value, productOptions: [...(document.querySelector('#ls-product')?.options || [])].map((o) => o.value) }; })()`;
const out = [];
const cases = [["s85-auto", "-85.3305", "285.2104", null, "3000"], ["s85-240m", "-85.3305", "285.2104", "240m:LDEM_60S_240MPP_ADJ.TIF", "3000"],
  ["s85-80m", "-85.3305", "285.2104", "80m:LDEM_80S_80MPP_ADJ.tiff", "3000"], ["s88-auto", "-88.5", "60", null, "3000"],
  ["site01-auto", "-89.463163", "222.510447", null, "3000"], ["s85-auto-12km", "-85.3305", "285.2104", null, "12000"]];
for (const [tag, lat, lon, prod, win] of cases) {
  await evaluate("document.querySelector('#tab-site').click(); true"); await sleep(400);
  await setValue("#lat", lat); await setValue("#lon", lon);
  await evaluate("document.querySelector('#tab-landing').click(); true");
  await waitFor("document.querySelector('.landing-run') && !document.querySelector('.landing-run').disabled", 60000, "landing");
  await sleep(600);
  const winHalf = String(Number(win) / 2);
  await setValue("#ls-window", winHalf);
  if (prod) await setValue("#ls-product", prod); else await setValue("#ls-product", "auto");
  const n0 = net.length;
  await evaluate("document.querySelector('.landing-run').click(); true");
  for (let i = 0; i < 600 && !net.slice(n0).some((r) => /\/api\/landing\/assess/.test(r.url)); i++) await sleep(500);
  await waitFor("document.querySelector('.landing-map .map-host canvas')", 60000, "map " + tag); await sleep(6000);
  await evaluate("document.querySelector('.landing-mapcard').scrollIntoView({ block: 'start' }); true"); await sleep(1500);
  const p = await evaluate(PAINT);
  const { data } = await send("Page.captureScreenshot", { format: "png" });
  fs.writeFileSync(path.join(OUT, "screenshots", `diag-${tag}.png`), Buffer.from(data, "base64"));
  const mine = net.slice(n0); const pend = [...reqs.values()].map((r) => r.url);
  const tiles = mine.filter((r) => /display\/tiles/.test(r.url));
  const rec = { tag, paint: p, tiles: { n: tiles.length, codes: [...new Set(tiles.map((t) => t.status ?? t.failed))], maxMs: Math.max(0, ...tiles.map((t) => t.ms)), pendingAfter6s: pend.filter((u) => /tiles/.test(u)).length },
    landing: mine.filter((r) => /landing/.test(r.url)).map((r) => `${r.status ?? r.failed} ${r.ms}ms ${r.url.slice(0, 90)}`) };
  out.push(rec); console.log(JSON.stringify(rec));
}
fs.writeFileSync(path.join(OUT, "diagnosis.json"), JSON.stringify({ cases: out, console: consoleMsgs.filter((x) => /error|exception|warn/.test(x.type)) }, null, 1));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
