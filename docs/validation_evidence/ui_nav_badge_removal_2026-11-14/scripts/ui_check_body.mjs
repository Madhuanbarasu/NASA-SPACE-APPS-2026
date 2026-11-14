
// UI change check (2026-11-14): navigation without "Data and validation", no validation badges in Mission and Site,
// the Data view still opens at #data, and the responsive layout at 1920/1440/1024/390/320 px. One headless browser.
// Site01 7-day result (cached by earlier runs; requested again through the UI).
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
await waitFor("document.querySelector('.figures')", 600000, "analysis"); await sleep(1000);

const NAV = `(() => { const tabs = [...document.querySelectorAll('#primary-nav .tab')];
  const vis = tabs.filter(t => { const r = t.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
  return { tabs: tabs.map(t => t.textContent.trim()), visible: vis.length, hasDataTab: !!document.querySelector('#tab-data'),
    navText: document.querySelector('#primary-nav').textContent, toggleShown: getComputedStyle(document.querySelector('#nav-toggle')).display !== 'none' }; })()`;
const BADGES = `(() => { const m = document.querySelector('main'); const t = (m?.innerText || '');
  const q = (s) => m ? m.querySelectorAll(s).length : 0;
  return { statusBadges: q('.status-badge'), pendingBadges: q('.status-badge.is-pending'), labelChips: q('.label-row .chip'),
    figureLabels: q('.figure-labels'), missionBadges: q('.mission-badges'), candLabels: q('.cand-labels'),
    pendingValidationText: (t.match(/pending validation/gi) || []).length, pendingCountText: (t.match(/\\d+ validated, \\d+ pending/gi) || []).length }; })()`;
const MEASURE = `(() => {
  const vw = document.documentElement.clientWidth;
  const inScroller = (e) => { let p = e.parentElement; while (p && p !== document.body) { const s = getComputedStyle(p); if (/(auto|scroll|hidden)/.test(s.overflowX) && p.scrollWidth > p.clientWidth + 1) return true; p = p.parentElement; } return false; };
  const all = [...document.querySelectorAll('main *, .topbar *')].filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
  const outside = all.filter(e => e.getBoundingClientRect().right > vw + 1 && !inScroller(e)).slice(0, 5).map(e => e.tagName.toLowerCase() + '.' + (typeof e.className === 'string' ? e.className.split(' ')[0] : ''));
  const clipped = [...document.querySelectorAll('main button, .topbar button, main h1, main h2, main h3, .status-badge, .chip, .tab')]
    .filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflow !== 'visible'; })
    .slice(0, 5).map(e => e.tagName.toLowerCase() + ' "' + e.textContent.trim().slice(0, 40) + '"');
  const cards = [...document.querySelectorAll('main .landing-card, main .card, main section.panel, main .figure, main .mission-card, main .context-card')].map(e => e.getBoundingClientRect()).filter(r => r.width > 0);
  let overlaps = 0;
  for (let i = 0; i < cards.length; i++) for (let j = i + 1; j < cards.length; j++) { const a = cards[i], b = cards[j];
    if (a.left < b.right - 2 && b.left < a.right - 2 && a.top < b.bottom - 2 && b.top < a.bottom - 2) overlaps++; }
  // empty boxes left behind: visible elements with a border or background, no text and no media, at least 24 px high
  const empty = [...document.querySelectorAll('main .result-labels, main .mission-card > div, main .figure-head, main .cand-analysis')]
    .filter(e => { const r = e.getBoundingClientRect(); return r.height >= 24 && r.width > 0 && !e.innerText.trim() && !e.querySelector('svg,canvas,img,table,button,input'); }).length;
  const mainText = (document.querySelector('main')?.innerText || '').trim().length;
  return { hscroll: document.documentElement.scrollWidth > vw, outside, clipped, overlaps, cards: cards.length, emptyBoxes: empty, mainText }; })()`;

const out = { combos: [], nav: [], data: [] };
for (const [w, h] of [[1920, 1080], [1440, 900], [1024, 768], [390, 844], [320, 640]]) {
  await size(w, h); await sleep(1200);
  const nav = await evaluate(NAV);
  let menu = null;
  if (nav.toggleShown) {   // compact menu: open it, list the items, close it with Escape
    await evaluate("document.querySelector('#nav-toggle').click(); true"); await sleep(500);
    menu = await evaluate(NAV);
    const { data } = await send("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(path.join(OUT, "screenshots", `menu-${w}.png`), Buffer.from(data, "base64"));
    await evaluate("document.querySelector('#nav-toggle').click(); true"); await sleep(400);
  }
  const navOk = nav.tabs.length === 6 && !nav.hasDataTab && !/Data and validation/.test(nav.navText) && (!menu || (menu.visible === 6 && !/Data and validation/.test(menu.navText)));
  out.nav.push({ width: w, ...nav, menu, result: navOk ? "Pass" : "Fail" });
  console.log(`${navOk ? "PASS" : "FAIL"} nav ${w}: ${nav.tabs.join(" | ")}${menu ? ` (menu items visible ${menu.visible})` : ""}`);
  for (const tab of ["mission", "site", "landing", "comms", "compare", "guide"]) {
    await evaluate(`document.querySelector('#tab-${tab}').click(); true`); await sleep(1300);
    await evaluate("document.querySelector('.main')?.scrollTo(0, 0); window.scrollTo(0, 0); true");
    const m = await evaluate(MEASURE); const b = await evaluate(BADGES);
    const layoutOk = !m.hscroll && m.outside.length === 0 && m.clipped.length === 0 && m.overlaps === 0 && m.emptyBoxes === 0 && m.mainText > 20;
    const scoped = tab === "mission" || tab === "site";
    const badgesOk = !scoped || ((tab === "mission" ? b.statusBadges === 0 : true) && b.pendingBadges === 0 && b.labelChips === 0 && b.figureLabels === 0 && b.missionBadges === 0 && b.candLabels === 0
      && b.pendingCountText === 0);
    const name = `ui-${w}-${tab}`;
    const { data } = await send("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(path.join(OUT, "screenshots", `${name}.png`), Buffer.from(data, "base64"));
    out.combos.push({ width: w, tab, layout: m, badges: b, screenshot: `screenshots/${name}.png`, result: layoutOk && badgesOk ? "Pass" : "Fail" });
    console.log(`${layoutOk && badgesOk ? "PASS" : "FAIL"} ${w} ${tab} layout ${JSON.stringify(m).slice(0, 150)} badges ${JSON.stringify(b)}`);
  }
  // the unlisted Data and validation view opens from the address bar (#data); the tab list stays keyboard-reachable
  await evaluate("location.hash = ''; true"); await sleep(200); await evaluate("location.hash = '#data'; true"); await sleep(1500);
  const d = await evaluate(`(() => ({ title: document.querySelector('#view-panel h1, #view-panel h2')?.textContent.trim(),
    panelLabel: document.querySelector('#view-panel').getAttribute('aria-label'), labelledby: document.querySelector('#view-panel').getAttribute('aria-labelledby'),
    reportRows: document.querySelectorAll('#view-panel table tr').length, focusableTabs: [...document.querySelectorAll('#primary-nav .tab')].filter(t => t.tabIndex === 0).length }))()`);
  const dm = await evaluate(MEASURE);
  const { data } = await send("Page.captureScreenshot", { format: "png" });
  fs.writeFileSync(path.join(OUT, "screenshots", `ui-${w}-data-hash.png`), Buffer.from(data, "base64"));
  const dOk = /Data and validation/i.test(d.title || "") && d.panelLabel && !d.labelledby && d.reportRows > 0 && d.focusableTabs === 1 && !dm.hscroll && dm.outside.length === 0;
  out.data.push({ width: w, ...d, layout: dm, result: dOk ? "Pass" : "Fail" });
  console.log(`${dOk ? "PASS" : "FAIL"} ${w} #data ${JSON.stringify(d)}`);
  await evaluate("location.hash = ''; document.querySelector('#tab-site').click(); true"); await sleep(600);
}
out.console = consoleMsgs.filter((x) => /error|exception/.test(x.type));
const all = [...out.nav, ...out.combos, ...out.data];
out.summary = { pass: all.filter((c) => c.result === "Pass").length, total: all.length, consoleErrors: out.console.length };
fs.writeFileSync(path.join(OUT, "ui_check.json"), JSON.stringify(out, null, 1));
console.log(JSON.stringify(out.summary));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
