
// E2E-07b: what the user sees when the analysis end is before the start (UI click, not a direct API call).
await send("Runtime.enable"); await send("Page.enable"); await send("Network.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const setInput = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
await send("Emulation.setDeviceMetricsOverride", { width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
await evaluate("document.querySelector('#tab-site').click(); true");
await setInput("#lat", "-89.463163"); await setInput("#lon", "222.510447");
await setInput("#start", "2026-12-13T00:00"); await setInput("#end", "2026-11-13T00:00");
await waitFor("!document.querySelector('.sidebar .run-button')?.disabled", 30000, "Analyse enabled");
const n0 = requests.length;
await evaluate("document.querySelector('.sidebar .run-button').click(); true");
let shown = null;
try {
  await waitFor("/end time must be after|must be after the start/i.test(document.body.innerText)", 30000, "error shown");
  shown = await evaluate("[...document.querySelectorAll('[role=alert], .note, .error, .hint.bad, .job-error, p')].map(e => e.textContent).find(t => /end time must be after/i.test(t)) || null");
} catch { shown = null; }
await sleep(800);
const { data } = await send("Page.captureScreenshot", { format: "png" });
fs.writeFileSync(path.join(OUT, "screenshots", "e2e07b-end-before-start.png"), Buffer.from(data, "base64"));
const figuresShown = await evaluate("!!document.querySelector('.figures')");
const out = { error_message_shown: shown, figures_shown: figuresShown,
  requests: requests.slice(n0).filter((u) => /\/api\/(analysis|jobs)/.test(u)).map((u) => u.replace(BASE, "")) };
fs.writeFileSync(path.join(OUT, "e2e07b.json"), JSON.stringify(out, null, 1));
console.log(JSON.stringify(out));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
