
// Verification (after the CSS change): Site result "Events and intervals" and "Sunlight" sections at 1920/1440/1024/390/320
// px, for two results: A = 85.3305 S, 285.2104 E, 13-20 Nov 2026 (has rise/set events) and B = Site01, same window (no events).
// Per width: blank space under each column, section padding, event-list scroll, intervals expand/collapse, overflow,
// clipping, overlap; screenshots. One browser.
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
const size = (w, h) => send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
await size(1440, 900);
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
await evaluate("document.querySelector('#tab-site').click(); true");

const MEASURE = `(() => {
  const B = (e) => e.getBoundingClientRect().bottom + scrollY;
  const contentBottom = (e) => Math.max(B(e) - e.getBoundingClientRect().height, ...[...e.querySelectorAll('*')].filter(x => x.getClientRects().length && getComputedStyle(x).visibility !== 'hidden').map(B));
  const padB = (e) => parseFloat(getComputedStyle(e).paddingBottom) + parseFloat(getComputedStyle(e).borderBottomWidth);
  const out = {};
  const tl = document.querySelector('#result-timeline'), grid = tl.querySelector('.timeline-grid');
  const tw = grid.querySelector('.timeline-wrap'), ev = grid.querySelector('.event-list-wrap, .event-empty');
  const list = grid.querySelector('.event-list');
  const twoCol = tw.getBoundingClientRect().top === ev.getBoundingClientRect().top;
  out.timeline = { twoCol, sectionSlack: Math.round(B(tl) - padB(tl) - contentBottom(tl)),
    gridBottom: Math.round(B(grid)), timelineContentBottom: Math.round(contentBottom(tw)), timelineH: Math.round(tw.getBoundingClientRect().height), eventColBottom: Math.round(B(ev)),
    blankUnderTimeline: Math.round(B(grid) - contentBottom(tw)), blankUnderEvents: Math.round(B(grid) - B(ev)),
    events: list ? list.children.length : 0, listVisibleH: list ? Math.round(list.clientHeight) : null, listScrollH: list ? list.scrollHeight : null };
  const sun = document.querySelector('#result-visibility'), bg = sun.querySelector('.body-grid');
  const st = bg.querySelector('.body-stats'), ch = bg.querySelector('.vis-chart');
  const stTwo = st.getBoundingClientRect().top === ch.getBoundingClientRect().top;
  out.sun = { twoCol: stTwo, sectionSlack: Math.round(B(sun) - padB(sun) - contentBottom(sun)), gridBottom: Math.round(B(bg)),
    statsCardBottom: Math.round(B(st)), statsContentBottom: Math.round(contentBottom(st) + padB(st)), chartContentBottom: Math.round(contentBottom(ch)),
    blankUnderChart: Math.round(B(bg) - contentBottom(ch)), blankInsideStats: Math.round(B(st) - (contentBottom(st) + padB(st))),
    statsH: Math.round(st.getBoundingClientRect().height), chartColH: Math.round(ch.getBoundingClientRect().height),
    clippedLabels: [...st.querySelectorAll('.metric dt, .metric dd')].filter(x => x.scrollWidth > x.clientWidth + 1).length };
  const vw = document.documentElement.clientWidth;
  const inScroller = (e) => { let p = e.parentElement; while (p && p !== document.body) { const s = getComputedStyle(p); if (/(auto|scroll|hidden)/.test(s.overflowX) && p.scrollWidth > p.clientWidth + 1) return true; p = p.parentElement; } return false; };
  const scope = [tl, sun];
  out.hscroll = document.documentElement.scrollWidth > vw;
  out.outside = scope.flatMap(s => [...s.querySelectorAll('*')]).filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.right > vw + 1 && !inScroller(e); }).length;
  out.clipped = scope.flatMap(s => [...s.querySelectorAll('button, h2, h3, .chip, .status-badge')]).filter(e => e.getBoundingClientRect().width > 0 && e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflow !== 'visible').length;
  return out; })()`;

const snapSection = async (name, id) => {
  await evaluate(`document.getElementById('${id}').scrollIntoView({ block: 'start' }); true`); await sleep(500);
  const { data } = await send("Page.captureScreenshot", { format: "png" });
  fs.writeFileSync(path.join(OUT, "screenshots", `${name}.png`), Buffer.from(data, "base64"));
};
const results = [];
for (const [tag, lat, lon] of [["A-events", "-85.3305", "285.2104"], ["B-site01", "-89.463163", "222.510447"]]) {
  await size(1440, 900); await sleep(500);
  if (await evaluate("!!document.querySelector('.workspace-result')")) { await evaluate("[...document.querySelectorAll('button')].find(b => /Back to the Moon explorer/.test(b.textContent))?.click(); true"); await sleep(800); }
  await setValue("#lat", lat); await setValue("#lon", lon); await setValue("#start", "2026-11-13T00:00"); await setValue("#end", "2026-11-20T00:00");
  await waitFor("!document.querySelector('.sidebar .run-button').disabled", 60000, "analyse");
  await evaluate("document.querySelector('.sidebar .run-button').click(); true");
  await waitFor("document.querySelector('.workspace-result') && document.querySelector('#result-timeline')", 900000, "analysis " + tag); await sleep(1500);
  for (const [w, h] of [[1920, 1080], [1440, 900], [1024, 768], [390, 844], [320, 640]]) {
    await size(w, h); await sleep(1200);
    const m = await evaluate(MEASURE);
    // intervals: expand, measure, collapse, measure
    await evaluate("document.querySelector('#result-timeline .toggle-intervals').click(); true"); await sleep(600);
    const open = await evaluate(MEASURE);
    await snapSection(`after-${tag}-${w}-timeline-intervals-open`, "result-timeline");
    await evaluate("document.querySelector('#result-timeline .toggle-intervals').click(); true"); await sleep(600);
    const closed = await evaluate(MEASURE);
    await snapSection(`after-${tag}-${w}-timeline`, "result-timeline");
    await snapSection(`after-${tag}-${w}-sunlight`, "result-visibility");
    const t = m.timeline, s = m.sun;
    const TOL = 2;   // px
    const tlOk = t.sectionSlack <= TOL && (!t.twoCol || (t.events === 0 ? true : (Math.abs(t.blankUnderTimeline) <= TOL && Math.abs(t.blankUnderEvents) <= TOL && t.listVisibleH >= 100)))
      && (!t.twoCol || t.events === 0 || t.blankUnderTimeline <= TOL) ;
    // positions move when the screenshots scroll the page, so the toggle is judged on sizes: opening must grow the
    // timeline column (and, in two columns, keep both columns level); closing must restore the list height
    const toggleOk = open.timeline.timelineH > m.timeline.timelineH && Math.abs(closed.timeline.timelineH - m.timeline.timelineH) <= 1
      && (!open.timeline.twoCol || Math.abs(open.timeline.blankUnderTimeline) <= TOL)
      && (closed.timeline.listVisibleH === m.timeline.listVisibleH);
    const sunOk = s.sectionSlack <= TOL && (!s.twoCol || (s.blankUnderChart <= TOL && s.blankInsideStats <= 30)) && s.clippedLabels === 0;
    const layoutOk = !m.hscroll && m.outside === 0 && m.clipped === 0;
    const ok = tlOk && toggleOk && sunOk && layoutOk;
    results.push({ result: tag, width: w, timeline: t, timelineIntervalsOpen: open.timeline, timelineIntervalsClosed: closed.timeline, sun: s,
      hscroll: m.hscroll, outside: m.outside, clipped: m.clipped, checks: { tlOk, toggleOk, sunOk, layoutOk }, verdict: ok ? "Pass" : "Fail" });
    console.log(`${ok ? "PASS" : "FAIL"} ${tag} ${w}: timeline ${JSON.stringify({ two: t.twoCol, ev: t.events, slack: t.sectionSlack, underTl: t.blankUnderTimeline, underEv: t.blankUnderEvents, listH: t.listVisibleH })} toggle ${toggleOk} sun ${JSON.stringify({ two: s.twoCol, slack: s.sectionSlack, underChart: s.blankUnderChart, insideStats: s.blankInsideStats, statsH: s.statsH, chartH: s.chartColH, clipped: s.clippedLabels })} layout ${JSON.stringify({ h: m.hscroll, o: m.outside, c: m.clipped })}`);
  }
}
const out = { results, console: consoleMsgs.filter((x) => /error|exception/.test(x.type)) };
out.summary = { pass: results.filter((r) => r.verdict === "Pass").length, total: results.length, consoleErrors: out.console.length };
fs.writeFileSync(path.join(OUT, "verify.json"), JSON.stringify(out, null, 1));
console.log(JSON.stringify(out.summary));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
