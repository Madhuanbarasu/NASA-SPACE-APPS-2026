
// Phase 5: top-bar overflow per width, with the new Landing tab hidden in the page (the five-tab bar) and shown.
// The compact-menu rule (shell.css, < 1440 px) applies in both runs; the measurement of the five-tab bar under the
// previous < 1200 px rule is in README (taken before the shell.css change).

await send("Runtime.enable"); await send("Page.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const res = {};
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(600);
for (const hide of [true, false]) for (const w of [1200, 1280, 1366, 1439, 1440, 1600, 1920, 1024, 390, 320]) {
  await send("Emulation.setDeviceMetricsOverride", { width: w, height: 900, deviceScaleFactor: 1, mobile: w < 800 }); await sleep(500);
  await evaluate(`document.getElementById('tab-landing').style.display = ${hide ? "'none'" : "''"}; true`); await sleep(200);
  res[(hide ? 'withoutLanding-' : 'withLanding-') + w] = await evaluate(`(() => { const vw = document.documentElement.clientWidth; const bar = document.querySelector('.topbar');
    const over = [...bar.querySelectorAll('*')].filter(e => e.getBoundingClientRect().right > vw + 1).map(e => e.className || e.tagName).slice(0, 4);
    return { sw: document.documentElement.scrollWidth, vw, over, kids: [...bar.children].map(e => (e.className || e.tagName).toString().slice(0, 24) + ':' + Math.round(e.getBoundingClientRect().width)) }; })()`);
}
await send("Emulation.setDeviceMetricsOverride", { width: 1280, height: 800, deviceScaleFactor: 1, mobile: false }); await sleep(300);
await evaluate("document.getElementById('nav-toggle').click(); true"); await sleep(400);
res.menu1280 = await evaluate("({ open: document.querySelector('.tabs').getAttribute('data-open'), items: [...document.querySelectorAll('button.tab')].map(b => b.textContent.trim() + ':' + Math.round(b.getBoundingClientRect().height)) })");
await shot("topbar-menu-1280", null);
fs.writeFileSync(path.join(OUT, "topbar.json"), JSON.stringify(res, null, 1)); console.log(JSON.stringify(res));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
