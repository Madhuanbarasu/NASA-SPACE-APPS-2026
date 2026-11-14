
// AUD-01 follow-up: valid edge longitudes (360 and -10) in the browser, waiting up to 15 s for the coverage reply.
// Appended to the Phase 1 CDP harness; one headless browser; read only.
await send("Runtime.enable"); await send("Page.enable"); await send("Network.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(1000);
const res = [];
for (const [lat, lon] of [["-85", "360"], ["-85", "-10"], ["-90", "0"], ["-89.463163", "222.510447"]]) {
  const n0 = requests.length, t0 = Date.now();
  await setValue("#lat", lat); await setValue("#lon", lon);
  let hint = "";
  try { await waitFor("/Terrain coverage|No terrain-adjusted/.test(document.querySelector('#coord-hint')?.textContent || '')", 15000, "coverage"); } catch { /* recorded below */ }
  hint = await evaluate("document.querySelector('#coord-hint')?.textContent");
  res.push({ lat, lon, ms: Date.now() - t0, hint, hintClass: await evaluate("document.querySelector('#coord-hint')?.className"),
    latInvalid: await evaluate("document.querySelector('#lat').getAttribute('aria-invalid')"), lonInvalid: await evaluate("document.querySelector('#lon').getAttribute('aria-invalid')"),
    analyseDisabled: await evaluate("document.querySelector('.sidebar .run-button').disabled"),
    coverageRequests: requests.slice(n0).filter((u) => /\/api\/coverage/.test(u)).map((u) => u.replace(BASE, "")) });
}
fs.writeFileSync(path.join(OUT, "aud01-edge.json"), JSON.stringify({ res, console: consoleMsgs.filter((x) => /error|exception|warn/.test(x.type)) }, null, 1));
console.log(JSON.stringify(res, null, 1));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
