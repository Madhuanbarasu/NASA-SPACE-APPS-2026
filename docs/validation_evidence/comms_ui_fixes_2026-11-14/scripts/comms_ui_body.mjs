
// Communication tab UI check: blank space below each card, the RF link-direction buttons, the tab label, overlap and
// horizontal overflow at 1440, 1024 and 390 px. One headless browser; appended to the Phase 1 CDP harness.
// Usage: node comms_ui.mjs --base <url> --out <dir> --label before|after
// The RF values and relay orbit typed here are ILLUSTRATIVE demonstration inputs (Phase 6 SOURCES.md), not hardware data.
const LABEL = arg("--label", "run");
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return false; const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
const setSelect = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return false; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
const size = (w, h) => send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
const top0 = () => evaluate("document.querySelector('.main')?.scrollTo(0, 0); window.scrollTo(0, 0); true");
const scrollTo = (sel) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (e) e.scrollIntoView({ block: 'start' }); return !!e; })()`);
const LINK = { power: "20", gt: "20", ltx: "1", gr: "60", lrx: "1", ts: "50", lother: "3", freqMHz: "8450", rbkbps: "1000", ebn0: "2.5" };
const UP = { power: "5", gt: "3", ltx: "1", gr: "20", lrx: "1", ts: "400", lother: "2", freqMHz: "2250", rbkbps: "1000", ebn0: "2.5" };
const DOWN = { power: "50", gt: "30", ltx: "1", gr: "60", lrx: "1", ts: "50", lother: "3", freqMHz: "8450", rbkbps: "1000", ebn0: "2.5" };
const measure = () => evaluate(`(() => {
  const cards = [...document.querySelectorAll('.comms .landing-card')];
  const r = (e) => e.getBoundingClientRect();
  const res = {};
  for (const c of cards) {
    const id = (c.getAttribute('aria-labelledby') || 'card').replace('comms-', ''); const b = r(c);
    const below = cards.map(r).filter(o => o.top >= b.bottom - 1 && o.left < b.right - 1 && o.right > b.left + 1).map(o => o.top);
    const content = [...c.children].reduce((m, k) => Math.max(m, r(k).bottom), b.top);
    res[id] = { h: Math.round(b.height), left: Math.round(b.left), w: Math.round(b.width),
      blankBelow: below.length ? Math.round(Math.min(...below) - b.bottom) : null, emptyInside: Math.round(b.bottom - content) };
  }
  const overlaps = [];
  for (let i = 0; i < cards.length; i++) for (let j = i + 1; j < cards.length; j++) {
    const a = r(cards[i]), b = r(cards[j]);
    if (a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1) overlaps.push(i + '-' + j);
  }
  return { cards: res, overlaps, hscroll: document.documentElement.scrollWidth > document.documentElement.clientWidth }; })()`);
// RF direction buttons: state of each, which link the form and breakdown show after a click
const tabs = () => evaluate(`[...document.querySelectorAll('.comms-linktabs button')].map(b => ({ text: b.textContent.trim(), pressed: b.getAttribute('aria-pressed'), disabled: b.disabled }))`);
const clickTab = (t) => evaluate(`(() => { const b = [...document.querySelectorAll('.comms-linktabs button')].find(e => e.textContent.trim() === ${JSON.stringify(t)}); if (!b) return 'missing'; b.click(); return b.disabled ? 'disabled' : 'clicked'; })()`);
const linkState = () => evaluate(`({ pressed: [...document.querySelectorAll('.comms-linktabs button')].find(b => b.getAttribute('aria-pressed') === 'true')?.textContent.trim(),
  formId: document.querySelector('section[aria-labelledby=comms-link] .comms-linkform input')?.id,
  power: document.querySelector('section[aria-labelledby=comms-link] .comms-linkform input')?.value,
  status: document.querySelector('section[aria-labelledby=comms-link] .comms-linkstatus')?.textContent || '',
  note: [...document.querySelectorAll('section[aria-labelledby=comms-link] .comms-relay-needed')].map(e => e.textContent).join(' '),
  marginRow: [...document.querySelectorAll('section[aria-labelledby=comms-link] table.comms-budget tbody tr')].find(r => /Link margin/.test(r.textContent))?.textContent.replace(/\\s+/g, ' ').trim() || '' })`);
const fillLink = async (prefix, vals) => { for (const [k, v] of Object.entries(vals)) await setValue(`#${prefix}-${k}`, v); };
const out = { label: LABEL, layout: {}, buttons: {} };

await size(1440, 900);
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
await evaluate("try { localStorage.removeItem('luna-ops.params-docked.v1'); sessionStorage.clear(); } catch (e) {} true");
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
out.tabLabels = await evaluate("[...document.querySelectorAll('button.tab')].map(b => b.textContent.trim())");
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447");
await evaluate(`(() => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  for (const [id, v] of [['#start', '2026-12-13T00:00'], ['#end', '2026-12-20T00:00']]) { const e = document.querySelector(id); set.call(e, v); e.dispatchEvent(new Event('input', { bubbles: true })); } return true; })()`);
await waitFor("/covers this point/.test([...document.querySelectorAll('#coord-hint, .explorer .hint[aria-live]')].map(e => e.textContent).join(' '))", 60000, "coverage");
await evaluate("document.getElementById('tab-comms').click(); true");
await waitFor("document.querySelector('.comms')", 30000, "comms view"); await sleep(400);
out.activeTab = await evaluate("document.querySelector('button.tab[aria-selected=true]')?.textContent.trim()");
await evaluate("document.querySelector('.comms-run')?.click(); true");
await waitFor("document.querySelector('.comms-timeline svg')", 300000, "simulation"); await sleep(1500);

// ---- RF direction buttons with the relay OFF (the reported case)
out.buttons.relayOff_initial = await tabs();
out.buttons.relayOff_clickUp = await clickTab("Lander to relay"); await sleep(400);
out.buttons.relayOff_afterUp = await linkState();
out.buttons.relayOff_clickDown = await clickTab("Relay to Earth"); await sleep(400);
out.buttons.relayOff_afterDown = await linkState();
await clickTab("Direct to Earth"); await sleep(300);
await fillLink("cl-direct", LINK); await sleep(2200);
out.buttons.direct = await linkState();
await scrollTo("#comms-link"); await sleep(300); await shot(`${LABEL}-desktop-rf-direct`, null);
await clickTab("Lander to relay"); await sleep(500);
out.buttons.relayOff_up_after_direct = await linkState();
await scrollTo("#comms-link"); await sleep(300); await shot(`${LABEL}-desktop-rf-up-relay-off`, null);
await clickTab("Direct to Earth"); await sleep(300);
// layout with the relay off
for (const [w, h, kind] of [[1440, 900, "desktop"], [1024, 768, "tablet"], [390, 844, "phone"]]) {
  await size(w, h); await sleep(900); await top0();
  out.layout[`relayOff-${kind}`] = await measure();
  await shot(`${LABEL}-${kind}-top-relay-off`, null);
}
await size(1440, 900); await sleep(600);
// ---- relay ON
await scrollTo("#comms-relay");
await evaluate("document.querySelector('.comms-toggle input').click(); true"); await sleep(400);
for (const [k, v] of [["name", "H1 illustrative"], ["a", "6000"], ["e", "0.6"], ["i", "60"], ["raan", "0"], ["argp", "90"], ["m0", "0"], ["step", "60"]]) await setValue(`#cr-${k}`, v);
await setSelect("#cr-frame", "LME_EPOCH");
await waitFor("document.querySelector('section[aria-labelledby=comms-relay] table')", 120000, "relay"); await sleep(1200);
out.buttons.relayOn_initial = await tabs();
await clickTab("Lander to relay"); await sleep(400); await fillLink("cl-up", UP);
await clickTab("Relay to Earth"); await sleep(400); await fillLink("cl-down", DOWN); await sleep(2500);
// switch repeatedly: up, down, direct, up, down
const seq = [];
for (const t of ["Lander to relay", "Relay to Earth", "Direct to Earth", "Lander to relay", "Relay to Earth", "Lander to relay"]) {
  const r = await clickTab(t); await sleep(500); seq.push({ click: t, result: r, ...(await linkState()) });
}
out.buttons.relayOn_switching = seq;
await scrollTo("#comms-link"); await sleep(300); await shot(`${LABEL}-desktop-rf-up-relay-on`, null);
await clickTab("Relay to Earth"); await sleep(500); await scrollTo("#comms-link"); await sleep(300); await shot(`${LABEL}-desktop-rf-down-relay-on`, null);
for (const [w, h, kind] of [[1440, 900, "desktop"], [1024, 768, "tablet"], [390, 844, "phone"]]) {
  await size(w, h); await sleep(1200); await top0();
  out.layout[`relayOn-${kind}`] = await measure();
  await shot(`${LABEL}-${kind}-top-relay-on`, null);
  await scrollTo("#comms-link"); await sleep(400); await shot(`${LABEL}-${kind}-link-relay`, null);
}
// top bar at the checked widths and the compact menu
out.topbar = {};
for (const w of [1920, 1600, 1599, 1440, 1024, 390]) {
  await size(w, 900); await sleep(400);
  out.topbar[w] = await evaluate("({ overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth, inline: getComputedStyle(document.querySelector('.tabs')).display !== 'none', label: document.getElementById('tab-comms')?.textContent.trim(), selected: document.getElementById('tab-comms')?.getAttribute('aria-selected'), toggle: document.querySelector('.nav-toggle')?.textContent.trim() })");
}
await size(1920, 1000); await sleep(400); await top0(); await shot(`${LABEL}-1920-topbar`, { x: 0, y: 0, width: 1920, height: 70 });
out.consoleErrors = consoleMsgs.filter((x) => x.type === "exception" || x.type === "error" || x.type === "log-error").slice(0, 5);
fs.writeFileSync(path.join(OUT, `comms-ui-${LABEL}.json`), JSON.stringify(out, null, 1));
console.log(JSON.stringify(out, null, 1));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
