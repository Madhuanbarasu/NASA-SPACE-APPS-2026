
// E2E-07 rerun (pre-Phase 7 preparation): date-range validation and the panel-azimuth hint, one cycle.
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable"); await send("Network.enable");
const posts = [];
ws.addEventListener("message", (m) => { const msg = JSON.parse(m.data);
  if (msg.method === "Network.requestWillBeSent" && /\/api\/analysis$/.test(msg.params.request.url))
    posts.push({ t: Date.now(), body: msg.params.request.postData ? JSON.parse(msg.params.request.postData) : null }); });
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const setInput = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
const setSelect = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
const shotVP = async (name) => { const { data } = await send("Page.captureScreenshot", { format: "png" }); fs.writeFileSync(path.join(OUT, "screenshots", `${name}.png`), Buffer.from(data, "base64")); return `screenshots/${name}.png`; };
const state = () => evaluate(`({ endInvalid: document.querySelector('#end').getAttribute('aria-invalid'), describedBy: document.querySelector('#end').getAttribute('aria-describedby'),
  hint: document.querySelector('#window-hint')?.textContent || null, sidebarAnalyseDisabled: document.querySelector('.sidebar .run-button').disabled,
  explorerAnalyseDisabled: document.querySelector('.explorer-run')?.disabled ?? null })`);
await send("Emulation.setDeviceMetricsOverride", { width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
await evaluate("document.querySelector('#tab-site').click(); true");
await setInput("#lat", "-89.463163"); await setInput("#lon", "222.510447"); await sleep(1500);
const out = { cases: [] };
for (const [name, a, b, expectValid] of [["valid 30-day window", "2026-11-13T00:00", "2026-12-13T00:00", true],
                                         ["equal start and end", "2026-11-13T00:00", "2026-11-13T00:00", false],
                                         ["reversed", "2026-12-13T00:00", "2026-11-13T00:00", false],
                                         ["reversed by one minute", "2026-11-13T00:01", "2026-11-13T00:00", false],
                                         ["one minute (boundary, valid)", "2026-11-13T00:00", "2026-11-13T00:01", true]]) {
  await setInput("#start", a); await setInput("#end", b); await sleep(1200);
  const n0 = posts.length;
  const st = await state();
  // try to start an analysis anyway (clicking a disabled button does nothing; the store guard covers other callers)
  if (!expectValid) { await evaluate("document.querySelector('.sidebar .run-button').click(); document.querySelector('.explorer-run')?.click(); true"); await sleep(1500); }
  const sent = posts.length - n0;
  const shot = expectValid ? null : await shotVP(`window-${name.replace(/[^a-z0-9]+/gi, "-")}`);
  const ok = expectValid ? (st.endInvalid === null && st.hint === null && st.sidebarAnalyseDisabled === false)
                         : (st.endInvalid === "true" && /end must be after the start/i.test(st.hint || "") && st.sidebarAnalyseDisabled === true
                            && st.explorerAnalyseDisabled !== false && sent === 0);
  out.cases.push({ name, start: a, end: b, expectValid, ...st, analysis_requests_sent: sent, evidence: shot, result: ok ? "Pass" : "Fail" });
  console.log(JSON.stringify(out.cases.at(-1)));
}
// panel azimuth 400 -> 40: hint, request, stored result, displayed value
await setInput("#start", "2026-11-13T00:00"); await setInput("#end", "2026-11-14T00:00");
await setSelect("#panel", "fixed_vertical"); await sleep(300); await setInput("#paz", "400"); await sleep(500);
const azHint = await evaluate("[...document.querySelectorAll('.sidebar .hint')].map(e => e.textContent).find(t => /modulo 360/.test(t)) || null");
const azInput = await evaluate("({ staticHint: document.querySelector('#paz-hint')?.textContent || null, describedBy: document.querySelector('#paz')?.getAttribute('aria-describedby'), min: document.querySelector('#paz')?.getAttribute('min'), max: document.querySelector('#paz')?.getAttribute('max'), browserValid: document.querySelector('#paz')?.checkValidity() })");
await waitFor("!document.querySelector('.sidebar .run-button').disabled", 60000, "Analyse enabled");
const before = await evaluate(`[...document.querySelectorAll('a[href*="/api/results/"]')].map(a => a.getAttribute('href')).find(Boolean) || null`);
const n0 = posts.length;
await evaluate("document.querySelector('.sidebar .run-button').click(); true");
await waitFor(`(() => { const h = [...document.querySelectorAll('a[href*="/api/results/"]')].map(a => a.getAttribute('href')).find(Boolean); return h && h !== ${JSON.stringify(before)} && document.querySelector('.figures'); })()`, 600000, "analysis");
await sleep(1200);
const rid = await evaluate(`[...document.querySelectorAll('a[href*="/api/results/"]')].map(a => a.getAttribute('href').match(/results\\/([0-9a-f]+)/)?.[1]).find(Boolean)`);
const r = await evaluate(`fetch('/api/results/${rid}').then(x => x.json())`);
const ui = await evaluate("({ big: document.querySelector('.figures .figure.is-power .big')?.textContent, rule: document.querySelector('.figures .figure.is-power .rule')?.textContent })");
const shotAz = await shotVP("panel-azimuth-400-used-as-40");
const sentAz = posts.slice(n0).map((p) => p.body?.panel_az_deg);
const azOk = /used as 40/.test(azHint || "") && azInput.staticHint === "Azimuth in degrees; values are normalized modulo 360° (400° → 40°)." && azInput.browserValid === true && azInput.max === null && sentAz.length === 1 && sentAz[0] === 40 && r.provenance.parameters.panel.azimuth_deg === 40
  && Math.abs(parseFloat(ui.big) - r.summary.power.fixed_vertical.mean) <= 0.0005;
out.azimuth = { hint: azHint, input: azInput, request_panel_az_deg: sentAz, result_id: rid, stored_panel: r.provenance.parameters.panel,
  backend_fixed_vertical_mean: r.summary.power.fixed_vertical.mean, displayed: ui, evidence: shotAz, result: azOk ? "Pass" : "Fail" };
console.log(JSON.stringify(out.azimuth));
await setInput("#paz", "0"); await setSelect("#panel", "vertical_tracking");   // fixed after the run: #paz exists only for the fixed panel
out.console = consoleMsgs.filter((x) => /error|exception/.test(x.type));
fs.writeFileSync(path.join(OUT, "browser-results.json"), JSON.stringify(out, null, 1));
console.log(JSON.stringify({ summary: [...out.cases.map((c) => [c.name, c.result]), ["azimuth 400 -> 40", out.azimuth.result]], console: out.console.length }));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
