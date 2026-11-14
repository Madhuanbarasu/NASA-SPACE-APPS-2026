
await send("Runtime.enable"); await send("Page.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(600);
const res = {};
for (const w of [1600, 1680, 1920]) {
  await send("Emulation.setDeviceMetricsOverride", { width: w, height: 900, deviceScaleFactor: 1, mobile: false }); await sleep(500);
  await evaluate("document.getElementById('tab-comms').click(); true"); await sleep(300);
  res[w] = await evaluate(`(() => { const q = (s) => document.querySelector(s).getBoundingClientRect();
    const tabs = q('.tabs'), right = q('.topbar-right'), brand = q('.brand');
    const clipped = [...document.querySelectorAll('.topbar button, .topbar .brand-mark, .topbar .data-pill')].filter(e => e.scrollWidth > e.clientWidth + 1).map(e => e.className || e.tagName);
    return { tabsRight: Math.round(tabs.right), rightLeft: Math.round(right.left), gapTabsToRight: Math.round(right.left - tabs.right), brandRight: Math.round(brand.right), tabsLeft: Math.round(tabs.left),
      commsW: Math.round(document.getElementById('tab-comms').getBoundingClientRect().width), clipped, overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth }; })()`);
  await shot(`after-topbar-${w}`, { x: 0, y: 0, width: w, height: 70 });
}
console.log(JSON.stringify(res));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
