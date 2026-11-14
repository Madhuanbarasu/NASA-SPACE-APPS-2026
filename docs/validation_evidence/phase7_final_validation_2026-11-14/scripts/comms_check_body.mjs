
// T13 rerun: Communication tab, capturing the simulation request from the moment the tab opens and comparing the direct-
// to-Earth summary line with the API response (windows, open hours). Site01, 13-20 Nov 2026 (result cached by T7).
await send("Runtime.enable"); await send("Page.enable"); await send("Network.enable");
const reqs = new Map();
ws.addEventListener("message", (m) => { const msg = JSON.parse(m.data); const p = msg.params;
  if (msg.method === "Network.requestWillBeSent" && /\/api\/comms\/simulate/.test(p.request.url)) reqs.set(p.requestId, { url: p.request.url, body: p.request.postData });
  if (msg.method === "Network.responseReceived" && reqs.has(p.requestId)) reqs.get(p.requestId).status = p.response.status; });
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
await evaluate("document.querySelector('#tab-site').click(); true");
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447"); await setValue("#start", "2026-11-13T00:00"); await setValue("#end", "2026-11-20T00:00");
await waitFor("!document.querySelector('.sidebar .run-button').disabled", 60000, "analyse");
await evaluate("document.querySelector('.sidebar .run-button').click(); true");
await waitFor("document.querySelector('.figures')", 600000, "analysis"); await sleep(1000);
await evaluate("document.querySelector('#tab-comms').click(); true");
if (await evaluate("!!document.querySelector('.comms-run') && !document.querySelector('.comms-run').disabled")) await evaluate("document.querySelector('.comms-run').click(); true");
await waitFor("document.querySelector('section[aria-labelledby=comms-direct] .hint')", 600000, "direct"); await sleep(1500);
const hint = await evaluate("[...document.querySelectorAll('section[aria-labelledby=comms-direct] .hint')].map(e => e.textContent).join(' | ')");
const r = [...reqs.values()].find((x) => x.status);
const api = r ? await evaluate(`fetch('/api/comms/simulate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: ${JSON.stringify(r.body)} }).then(x => x.json())`) : null;
const st = api?.direct?.stats ?? null;
const { data } = await send("Page.captureScreenshot", { format: "png" });
fs.writeFileSync(path.join(OUT, "screenshots", "t13b-communication-direct.png"), Buffer.from(data, "base64"));
const out = { request_status: r?.status ?? null, api_direct_stats: st, api_terrain_blocked: api?.direct?.terrain_blocked_stats ?? null, ui_hint: hint };
console.log(JSON.stringify(out, null, 1));
fs.writeFileSync(path.join(OUT, "comms-check.json"), JSON.stringify(out, null, 1));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
