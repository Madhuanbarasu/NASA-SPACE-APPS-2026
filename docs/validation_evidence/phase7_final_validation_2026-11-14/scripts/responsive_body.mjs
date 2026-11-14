
// Responsive design check: 7 tabs x 5 widths with real content (Site01 7-day result, Landing screening, Communication
// simulation). Per combination: horizontal page scroll, elements extending past the viewport (outside scroll containers),
// clipped controls (buttons, tabs, headings, badges: scrollWidth > clientWidth), overlapping sibling cards, empty pane.
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
const size = (w, h) => send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
await size(1440, 900);
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
await evaluate("document.querySelector('#tab-site').click(); true");
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447"); await setValue("#start", "2026-11-13T00:00"); await setValue("#end", "2026-11-20T00:00");
await waitFor("!document.querySelector('.sidebar .run-button').disabled", 60000, "analyse");
await evaluate("document.querySelector('.sidebar .run-button').click(); true");
await waitFor("document.querySelector('.figures')", 600000, "analysis"); await sleep(800);
await evaluate("document.querySelector('#tab-landing').click(); true");
await waitFor("document.querySelector('.landing-run') && !document.querySelector('.landing-run').disabled", 60000, "landing");
await evaluate("document.querySelector('.landing-run').click(); true");
await waitFor("document.querySelector('section[aria-labelledby=landing-footprint]')", 300000, "screening"); await sleep(1500);
await evaluate("document.querySelector('#tab-comms').click(); true"); await sleep(800);
if (await evaluate("!!document.querySelector('.comms-run') && !document.querySelector('.comms-run').disabled")) await evaluate("document.querySelector('.comms-run').click(); true");
await waitFor("document.querySelector('section[aria-labelledby=comms-direct] .hint')", 600000, "comms"); await sleep(1500);
const MEASURE = `(() => {
  const vw = document.documentElement.clientWidth;
  const inScroller = (e) => { let p = e.parentElement; while (p && p !== document.body) { const s = getComputedStyle(p); if (/(auto|scroll|hidden)/.test(s.overflowX) && p.scrollWidth > p.clientWidth + 1) return true; p = p.parentElement; } return false; };
  const all = [...document.querySelectorAll('main *, .topbar *, .sidebar *')].filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
  const outside = all.filter(e => e.getBoundingClientRect().right > vw + 1 && !inScroller(e)).slice(0, 5).map(e => e.tagName.toLowerCase() + '.' + (typeof e.className === 'string' ? e.className.split(' ')[0] : ''));
  const clipped = [...document.querySelectorAll('main button, .topbar button, main h1, main h2, main h3, .status-badge, .chip, .tab')]
    .filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflow !== 'visible'; })
    .slice(0, 5).map(e => e.tagName.toLowerCase() + ' "' + e.textContent.trim().slice(0, 40) + '"');
  const cards = [...document.querySelectorAll('main .landing-card, main .card, main section.panel, main .figure, main .context-card')].map(e => e.getBoundingClientRect()).filter(r => r.width > 0);
  let overlaps = 0;
  for (let i = 0; i < cards.length; i++) for (let j = i + 1; j < cards.length; j++) { const a = cards[i], b = cards[j];
    if (a.left < b.right - 2 && b.left < a.right - 2 && a.top < b.bottom - 2 && b.top < a.bottom - 2) overlaps++; }
  const mainText = (document.querySelector('main')?.innerText || '').trim().length;
  return { hscroll: document.documentElement.scrollWidth > vw, outside, clipped, overlaps, cards: cards.length, mainText }; })()`;
const out = { combos: [] };
for (const [w, h] of [[1920, 1080], [1440, 900], [1024, 768], [390, 844], [320, 640]]) {
  await size(w, h); await sleep(1200);
  for (const tab of ["mission", "site", "landing", "comms", "compare", "data", "guide"]) {
    await evaluate(`document.querySelector('#tab-${tab}').click(); true`); await sleep(1300);
    await evaluate("document.querySelector('.main')?.scrollTo(0, 0); window.scrollTo(0, 0); true");
    const m = await evaluate(MEASURE);
    const name = `responsive-${w}-${tab}`;
    const { data } = await send("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(path.join(OUT, "screenshots", `${name}.png`), Buffer.from(data, "base64"));
    const ok = !m.hscroll && m.outside.length === 0 && m.clipped.length === 0 && m.overlaps === 0 && m.mainText > 20;
    out.combos.push({ width: w, tab, ...m, screenshot: `screenshots/${name}.png`, result: ok ? "Pass" : "Fail" });
    console.log(`${ok ? "PASS" : "FAIL"} ${w} ${tab} ${JSON.stringify(m).slice(0, 200)}`);
  }
}
out.console = consoleMsgs.filter((x) => /error|exception/.test(x.type));
fs.writeFileSync(path.join(OUT, "responsive.json"), JSON.stringify(out, null, 1));
console.log(JSON.stringify({ pass: out.combos.filter((c) => c.result === "Pass").length, total: out.combos.length, console: out.console.length }));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
