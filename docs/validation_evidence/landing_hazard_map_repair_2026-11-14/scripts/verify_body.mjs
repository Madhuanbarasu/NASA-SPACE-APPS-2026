
// Landing hazard map and footprint findings. --part evict: the assessment on screen is pushed out of the server's
// 3-entry cache by other screenings, then the layer is switched, the footprint changed and the tab left and re-entered
// (the failure reproduced before the fix, and its recovery after). --part all additionally checks three sites at five
// widths, the 240 m product case and a product selection carried to a site the product does not cover. One browser.
const PART = arg("--part", "all");
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable"); await send("Network.enable");
const reqs = new Map(); const net = [];
ws.addEventListener("message", (m) => { const msg = JSON.parse(m.data); const p = msg.params || {};
  if (msg.method === "Network.requestWillBeSent" && /\/api\/(display\/tiles|landing)/.test(p.request.url)) reqs.set(p.requestId, { url: p.request.url.replace(BASE, ""), t0: p.timestamp });
  if (msg.method === "Network.responseReceived" && reqs.has(p.requestId)) reqs.get(p.requestId).status = p.response.status;
  if ((msg.method === "Network.loadingFinished" || msg.method === "Network.loadingFailed") && reqs.has(p.requestId)) {
    const r = reqs.get(p.requestId); r.ms = Math.round((p.timestamp - r.t0) * 1000); if (p.errorText) r.failed = p.errorText; net.push(r); reqs.delete(p.requestId); } });
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const proto = e.tagName === 'SELECT' ? HTMLSelectElement.prototype : HTMLInputElement.prototype; Object.getOwnPropertyDescriptor(proto, 'value').set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
const size = (w, h) => send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
const until = async (fn, ms, what) => { const t = Date.now(); while (Date.now() - t < ms) { if (await fn()) return true; await sleep(300); } throw new Error("timeout " + what); };
const STATE = `(() => { const card = document.querySelector('.landing-mapcard'); const host = card?.querySelector('.map-host'); const r = host?.getBoundingClientRect();
  return { host: r ? [Math.round(r.width), Math.round(r.height)] : null, raster: document.querySelector('input[name=ls-raster]:checked')?.value ?? null,
    mapStatus: [...(card?.querySelectorAll('.landing-map-status, .pane-note, .pane-empty') || [])].map((e) => e.textContent.trim()),
    legend: (card?.querySelector('.landing-legend')?.textContent || card?.querySelector('.landing-legend-none')?.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 90),
    error: document.querySelector('.landing-pad[role=alert]')?.textContent || null,
    findings: [...document.querySelectorAll('.landing-findings > li')].map((li) => li.innerText.replace(/\\s+/g, ' ').slice(0, 170)),
    fpHints: [...document.querySelectorAll('.landing-footprint-hint')].map((e) => e.textContent),
    product: document.querySelector('#ls-product')?.value ?? null }; })()`;
const MEASURE = `(() => { const vw = document.documentElement.clientWidth;
  const inScroller = (e) => { let p = e.parentElement; while (p && p !== document.body) { const s = getComputedStyle(p); if (/(auto|scroll|hidden)/.test(s.overflowX) && p.scrollWidth > p.clientWidth + 1) return true; p = p.parentElement; } return false; };
  const all = [...document.querySelectorAll('main *')].filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
  return { hscroll: document.documentElement.scrollWidth > vw, outside: all.filter((e) => e.getBoundingClientRect().right > vw + 1 && !inScroller(e)).length }; })()`;
const nAssess = () => net.filter((r) => /\/api\/landing\/assess/.test(r.url)).length;
async function shotTo(name) { const { data } = await send("Page.captureScreenshot", { format: "png" }); fs.writeFileSync(path.join(OUT, "screenshots", `${name}.png`), Buffer.from(data, "base64")); }
async function screen(lat, lon, prod) {
  await evaluate("document.querySelector('#tab-site').click(); true"); await sleep(400);
  await setValue("#lat", lat); await setValue("#lon", lon);
  await evaluate("document.querySelector('#tab-landing').click(); true");
  await waitFor("document.querySelector('.landing-run') && !document.querySelector('.landing-run').disabled && document.querySelector('#ls-product')", 60000, "landing"); await sleep(1500);
  if (prod) await setValue("#ls-product", prod);
  const n = nAssess();
  await evaluate("document.querySelector('.landing-run').click(); true");
  await until(async () => nAssess() > n, 300000, "assess");
  await waitFor("document.querySelector('.landing-map .map-host canvas')", 60000, "map"); await sleep(3500);
}
const layerList = (list) => list.filter((r) => /\/layer\//.test(r.url)).map((r) => `${r.status ?? r.failed} ${r.url.replace(/^.*\/landing\//, "")}`);
const lastCode = (list) => (list.length ? Number(list[list.length - 1].split(" ")[0]) : null);
const out = { evict: null, sites: [], coarse: null, carry: null };
await size(1440, 900);
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);

// ---- A. eviction: the screening on screen is no longer held by the server (it keeps the latest 3)
await screen("-85.3305", "285.2104", null);
const aid = await evaluate("(() => { const u = performance.getEntriesByType('resource').map((e) => e.name).filter((n) => /\\/api\\/landing\\/[0-9a-f]+\\/layer\\//.test(n)).pop(); return u ? u.match(/landing\\/([0-9a-f]+)\\//)[1] : null; })()");
const ev = await evaluate(`(async () => { const codes = []; for (const h of [500, 1000, 2500]) { const r = await fetch('/api/landing/assess', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ lat: -88.5, lon: 60, window_half_m: h }) }); codes.push(r.status); }
  const chk = await fetch('/api/landing/' + ${JSON.stringify(aid)} + '/layer/slope.png'); return { evictingRuns: codes, layerStatusAfterEviction: chk.status }; })()`);
let n0 = net.length;
await evaluate("document.querySelector('input[name=ls-raster][value=elevation]').click(); true"); await sleep(6000);
const afterLayer = await evaluate(STATE);
const switchReqs = layerList(net.slice(n0)); const switchAssess = net.slice(n0).filter((r) => /\/assess/.test(r.url)).map((r) => r.status);
await evaluate("document.querySelector('.landing-mapcard').scrollIntoView({ block: 'start' }); true"); await sleep(800);
await shotTo("evict-after-layer-switch-1440");
// evict again, then change the footprint radius
await evaluate(`(async () => { for (const h of [600, 1200, 2400]) await fetch('/api/landing/assess', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ lat: -88.5, lon: 60, window_half_m: h }) }); return true; })()`);
n0 = net.length;
await setValue("#ls-radius", "60"); await sleep(6000);
const afterFp = await evaluate(STATE);
const fpReqs = net.slice(n0).filter((r) => /\/(footprint|assess)/.test(r.url)).map((r) => `${r.status} ${r.url.replace(/^.*\/landing\//, "")}`);
// evict again, then leave the tab and return (the map is rebuilt and requests its layer again)
await evaluate(`(async () => { for (const h of [700, 1400, 2800]) await fetch('/api/landing/assess', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ lat: -88.5, lon: 60, window_half_m: h }) }); return true; })()`);
n0 = net.length;
await evaluate("document.querySelector('#tab-site').click(); true"); await sleep(600);
await evaluate("document.querySelector('#tab-landing').click(); true"); await sleep(7000);
const afterRemount = await evaluate(STATE);
const remountReqs = layerList(net.slice(n0));
await evaluate("document.querySelector('.landing-mapcard').scrollIntoView({ block: 'start' }); true"); await sleep(800);
await shotTo("evict-after-tab-return-1440");
out.evict = { assessmentId: aid, ...ev, layerSwitch: { layerRequests: switchReqs, reRunCodes: switchAssess, state: afterLayer },
  footprintChange: { requests: fpReqs, state: afterFp }, tabReturn: { layerRequests: remountReqs, state: afterRemount } };
out.evict.verdict = lastCode(switchReqs) === 200 && !afterFp.error && lastCode(remountReqs) === 200 && afterRemount.host?.[1] > 200 ? "Pass" : "Fail";
console.log("EVICT", JSON.stringify(out.evict));

if (PART === "all") {
  // ---- B. three sites x five widths (finest product covering the window)
  for (const [tag, lat, lon] of [["site01", "-89.463163", "222.510447"], ["s85", "-85.3305", "285.2104"], ["s88", "-88.5", "60"]]) {
    await size(1440, 900); await sleep(300);
    const nA = net.length;
    await screen(lat, lon, "auto");
    const assessCode = net.slice(nA).filter((r) => /\/assess/.test(r.url)).map((r) => r.status);
    for (const [w, h] of [[1920, 1080], [1440, 900], [1024, 768], [390, 844], [320, 640]]) {
      await size(w, h); await sleep(1200);
      const nW = net.length;
      const layersSeen = [];
      for (const v of ["elevation", "roughness", "coverage", "uncertainty", "slope"]) {
        await evaluate(`document.querySelector('input[name=ls-raster][value=${v}]').click(); true`); await sleep(1100);
        const st = await evaluate(STATE); layersSeen.push({ v, legend: st.legend, mapStatus: st.mapStatus });
      }
      await evaluate("document.querySelector('.landing-mapcard').scrollIntoView({ block: 'start' }); true"); await sleep(2500);
      await shotTo(`landing-${tag}-${w}`);
      const st = await evaluate(STATE); const m = await evaluate(MEASURE);
      const mine = net.slice(nW);
      const tiles = mine.filter((r) => /display\/tiles/.test(r.url)); const lay = mine.filter((r) => /\/layer\//.test(r.url));
      const findingsOk = st.findings.length === 5 && st.findings.slice(0, 4).every((f) => !/No DEM pixel centre/.test(f));
      const legendOk = layersSeen.every((x) => x.legend.length > 0);
      const ok = st.host && st.host[0] > 200 && st.host[1] > 200 && lay.length >= 5 && lay.every((r) => r.status === 200)
        && tiles.every((r) => r.status === 200 || /ERR_ABORTED/.test(r.failed || "")) && findingsOk && legendOk && !m.hscroll && m.outside === 0 && !st.error
        && /Not available - manual review required/i.test(st.findings[4] || "");
      const rec = { site: tag, width: w, assessCode, state: st, layersSeen, layerCodes: lay.map((r) => `${r.status} ${r.url.replace(/^.*\/layer\//, "")}`),
        tiles: { n: tiles.length, codes: [...new Set(tiles.map((t) => t.status ?? t.failed))] }, layout: m, verdict: ok ? "Pass" : "Fail" };
      out.sites.push(rec);
      console.log(`${rec.verdict} ${tag} ${w} host ${st.host} layers ${rec.layerCodes.join(",")} tiles ${tiles.length}/${rec.tiles.codes} ${JSON.stringify(m)} findings ${st.findings.map((f) => f.slice(0, 70)).join(" | ")}`);
    }
  }
  // ---- C. the coarse 240 m product chosen at 85.33 S
  await size(1440, 900); await sleep(300);
  await screen("-85.3305", "285.2104", "240m:LDEM_60S_240MPP_ADJ.TIF");
  await evaluate("document.querySelector('.landing-mapcard').scrollIntoView({ block: 'start' }); true"); await sleep(2500);
  await shotTo("coarse-240m-map-1440");
  const cs = await evaluate(STATE);
  await evaluate("document.querySelector('.landing-findings').scrollIntoView({ block: 'center' }); true"); await sleep(600);
  await shotTo("coarse-240m-findings-1440");
  out.coarse = { state: cs, verdict: cs.host?.[1] > 200 && cs.findings.slice(0, 4).every((f) => /Requires higher-resolution data/.test(f)) && cs.fpHints.some((x) => /20m:LDEM_80S_20MPP_ADJ/.test(x)) ? "Pass" : "Fail" };
  console.log("COARSE", JSON.stringify(out.coarse));
  // ---- D. a product chosen at Site01 (5 m) carried to 88.5 S, 60 E, which it does not cover
  await screen("-89.463163", "222.510447", "5m:Site01_final_adj_5mpp_surf.tif");
  await evaluate("document.querySelector('#tab-site').click(); true"); await sleep(400);
  await setValue("#lat", "-88.5"); await setValue("#lon", "60");
  await evaluate("document.querySelector('#tab-landing').click(); true");
  await waitFor("document.querySelector('.landing-run') && !document.querySelector('.landing-run').disabled && document.querySelector('#ls-product')", 60000, "landing"); await sleep(2500);
  const prodShown = await evaluate("document.querySelector('#ls-product').value");
  const nD = nAssess(); const nN = net.length;
  await evaluate("document.querySelector('.landing-run').click(); true");
  await until(async () => nAssess() > nD, 300000, "assess carry"); await sleep(3500);
  const ds = await evaluate(STATE);
  const code = net.slice(nN).filter((r) => /\/assess/.test(r.url)).map((r) => r.status);
  out.carry = { productShownAfterSiteChange: prodShown, assessCodes: code, state: ds, verdict: prodShown === "auto" && code.every((c) => c === 200) && !ds.error ? "Pass" : "Fail" };
  console.log("CARRY", JSON.stringify(out.carry));
}
out.console = consoleMsgs.filter((x) => /error|exception/.test(x.type));
out.summary = { evict: out.evict.verdict, sites: `${out.sites.filter((r) => r.verdict === "Pass").length}/${out.sites.length}`, coarse: out.coarse?.verdict ?? "not run", carry: out.carry?.verdict ?? "not run", consoleErrors: out.console.length };
fs.writeFileSync(path.join(OUT, "verify.json"), JSON.stringify(out, null, 1));
console.log(JSON.stringify(out.summary));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
