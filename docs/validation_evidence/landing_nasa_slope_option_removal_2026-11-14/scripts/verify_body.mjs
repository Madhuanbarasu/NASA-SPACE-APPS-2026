
// Landing hazard map after removing the "NASA slope product" raster option: two sites (Site01, where the NASA slope
// product exists, and 85.3305 S 285.2104 E, where it does not) at 1920/1440/1024/390/320 px. Per site and width: the
// raster options offered, the default selection, switching through every enabled option (each loads its own layer
// image), the NASA slope statistics rows still present, and layout (overflow, clipping). One browser.
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable"); await send("Network.enable");
const layerReqs = [];
ws.addEventListener("message", (m) => { const msg = JSON.parse(m.data);
  if (msg.method === "Network.responseReceived" && /\/api\/landing\/[^/]+\/layer\//.test(msg.params.response.url))
    layerReqs.push({ url: msg.params.response.url.replace(/^.*\/layer\//, ""), status: msg.params.response.status }); });
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
const size = (w, h) => send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
await size(1440, 900);
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
const OPTIONS = `(() => { const fs_ = document.querySelector('.landing-layers'); if (!fs_) return null;
  const radios = [...fs_.querySelectorAll('input[name=ls-raster]')];
  return { values: radios.map(r => r.value), enabled: radios.filter(r => !r.disabled).map(r => r.value), checked: radios.find(r => r.checked)?.value ?? null,
    labels: radios.map(r => r.closest('label')?.textContent.trim()), nasaText: /NASA slope product/i.test(fs_.textContent),
    legend: (document.querySelector('.landing-legend, .map-legend, .legend')?.textContent || '').trim().slice(0, 80) }; })()`;
const STATS = `(() => { const t = document.querySelector('main')?.innerText || ''; return { nasaSlopeStatsRow: /NASA PGDA 78 slope product|NASA slope/i.test(t) }; })()`;
const MEASURE = `(() => {
  const vw = document.documentElement.clientWidth;
  const inScroller = (e) => { let p = e.parentElement; while (p && p !== document.body) { const s = getComputedStyle(p); if (/(auto|scroll|hidden)/.test(s.overflowX) && p.scrollWidth > p.clientWidth + 1) return true; p = p.parentElement; } return false; };
  const all = [...document.querySelectorAll('main *')].filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
  const outside = all.filter(e => e.getBoundingClientRect().right > vw + 1 && !inScroller(e)).length;
  const clipped = [...document.querySelectorAll('main button, main h2, main h3, main label, .status-badge, .chip')]
    .filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflow !== 'visible'; }).length;
  return { hscroll: document.documentElement.scrollWidth > vw, outside, clipped }; })()`;
const results = [];
for (const [tag, lat, lon] of [["site01", "-89.463163", "222.510447"], ["no-nasa-product", "-85.3305", "285.2104"]]) {
  await size(1440, 900); await sleep(400);
  await evaluate("document.querySelector('#tab-site').click(); true"); await sleep(400);
  await setValue("#lat", lat); await setValue("#lon", lon);
  await evaluate("document.querySelector('#tab-landing').click(); true");
  await waitFor("document.querySelector('.landing-run') && !document.querySelector('.landing-run').disabled", 60000, "landing");
  await evaluate("document.querySelector('.landing-run').click(); true");
  await waitFor("document.querySelector('.landing-layers')", 300000, "screening " + tag); await sleep(2000);
  for (const [w, h] of [[1920, 1080], [1440, 900], [1024, 768], [390, 844], [320, 640]]) {
    await size(w, h); await sleep(1200);
    const o = await evaluate(OPTIONS);
    // switch through every enabled raster option and back to the default; each must load its own layer image
    const switched = [];
    for (const v of o.enabled.filter((x) => x !== "none")) {
      const before = layerReqs.length;
      await evaluate(`(() => { const r = document.querySelector('input[name=ls-raster][value=${v}]'); r.click(); return true; })()`); await sleep(900);
      const now = await evaluate(OPTIONS);
      const req = layerReqs.slice(before).map((x) => x.url);
      switched.push({ option: v, checked: now.checked === v, legend: now.legend, newLayerRequests: req });
    }
    await evaluate(`document.querySelector('input[name=ls-raster][value=slope]').click(); true`); await sleep(600);
    await evaluate("document.querySelector('.landing-layers').scrollIntoView({ block: 'start' }); true"); await sleep(500);
    const { data } = await send("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(path.join(OUT, "screenshots", `landing-${tag}-${w}.png`), Buffer.from(data, "base64"));
    const m = await evaluate(MEASURE); const st = await evaluate(STATS);
    const optionsOk = !o.values.includes("nasa_slope") && !o.nasaText && o.checked === "slope";
    const switchOk = switched.every((s) => s.checked);
    const ok = optionsOk && switchOk && !m.hscroll && m.outside === 0 && m.clipped === 0 && st.nasaSlopeStatsRow;
    results.push({ site: tag, width: w, options: o, switched, layout: m, stats: st, verdict: ok ? "Pass" : "Fail" });
    console.log(`${ok ? "PASS" : "FAIL"} ${tag} ${w}: offered ${o.values.join(",")} | enabled ${o.enabled.join(",")} | default ${o.checked} | switch ${switched.map((s) => s.option + (s.checked ? "+" : "-")).join(" ")} | layout ${JSON.stringify(m)} | stats ${JSON.stringify(st)}`);
  }
}
const out = { results, layerResponses: layerReqs, console: consoleMsgs.filter((x) => /error|exception/.test(x.type)) };
out.layerResponseCodes = [...new Set(layerReqs.map((x) => x.status))];
out.summary = { pass: results.filter((r) => r.verdict === "Pass").length, total: results.length, consoleErrors: out.console.length, layerResponseCodes: out.layerResponseCodes };
fs.writeFileSync(path.join(OUT, "verify.json"), JSON.stringify(out, null, 1));
console.log(JSON.stringify(out.summary));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
