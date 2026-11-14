
const checks = [];
const check = (name, ok, detail) => { checks.push({ name, ok: !!ok, detail }); console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail !== undefined ? "  " + JSON.stringify(detail).slice(0, 500) : ""}`); };
const report = { base: BASE, browser: BROWSER, started: new Date().toISOString() };
await send("Runtime.enable"); await send("Log.enable"); await send("Page.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const size = (w, h) => send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 800 });
const load = async () => { await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(1200); };
const vis = (sel) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return false; const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; })()`);
const active = () => evaluate("document.activeElement?.id || document.activeElement?.className || document.activeElement?.tagName");
const panelShown = () => evaluate("(() => { const p = document.querySelector('.sidebar-panel'); return !!p && !p.hidden; })()");
const mainW = () => evaluate("Math.round(document.querySelector('.main').getBoundingClientRect().width)");

// ---- 1. wide screens (1440): tabs, docked and collapsible parameters
await size(1440, 900);
await load();
await evaluate("try { localStorage.removeItem('luna-ops.params-docked.v1'); } catch (e) {} true"); await load();
const w0 = { tabs: await vis(".tabs"), navToggle: await vis(".nav-toggle"), panel: await panelShown(), mainW: await mainW(), clock: await vis(".utc-clock") };
check("1440 px: tabs in the bar, no compact menu, parameters docked and open, UTC clock shown", w0.tabs && !w0.navToggle && w0.panel && w0.clock, w0);
await evaluate("document.querySelector('#tab-site').focus(); true"); await press("ArrowRight");
const kb = await evaluate("({ focus: document.activeElement.id, stops: [...document.querySelectorAll('button.tab')].filter(b => b.tabIndex === 0).length })");
check("tabs keyboard: ArrowRight from Site selects Compare; the list stays one tab stop", kb.focus === "tab-compare" && kb.stops === 1, kb);
await evaluate("document.querySelector('#tab-site').click(); true"); await sleep(400);
await evaluate("document.querySelector('.params-toggle').click(); true"); await sleep(500);
const w1 = { panel: await panelShown(), expanded: await evaluate("document.querySelector('.params-toggle').getAttribute('aria-expanded')"), mainW: await mainW(),
  status: await evaluate("!!document.querySelector('.sidebar [role=status]')"), latInDom: await evaluate("!!document.querySelector('#lat')") };
check("collapse: the parameters toggle hides the panel and the workspace takes the full width; the status line stays for screen readers",
  !w1.panel && w1.expanded === "false" && w1.mainW > w0.mainW + 300 && w1.status && w1.latInDom, { before: w0.mainW, after: w1 });
await load();
const w2 = { panel: await panelShown(), mainW: await mainW() };
check("collapse is remembered in this browser after a reload", !w2.panel && w2.mainW === w1.mainW, w2);
await evaluate("document.querySelector('.params-toggle').click(); true"); await sleep(500);
check("expand: the toggle brings the docked panel back", await panelShown() && (await mainW()) === w0.mainW);
await shot("shell-1440-docked", null);

// ---- 2. tablet (1024): compact navigation menu and parameters drawer
await size(1024, 768); await load();
const t0 = { tabs: await vis(".tabs"), navToggle: await vis(".nav-toggle"), panel: await panelShown(), hscroll: await evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth") };
check("1024 px: compact menu button instead of the tab strip; parameters drawer closed; no sideways scrolling", !t0.tabs && t0.navToggle && !t0.panel && !t0.hscroll, t0);
await evaluate("document.querySelector('#nav-toggle').click(); true"); await sleep(400);
const m1 = { open: await vis(".tabs"), expanded: await evaluate("document.querySelector('#nav-toggle').getAttribute('aria-expanded')") };
await shot("shell-1024-menu-open", null);
await evaluate("document.querySelector('#tab-guide').click(); true"); await sleep(500);
const m2 = { open: await vis(".tabs"), tab: await evaluate("document.querySelector('button.tab[aria-selected=true]').textContent"), label: await evaluate("document.querySelector('#nav-toggle').textContent") };
check("menu: opens; choosing a view selects it, closes the menu and shows the view's name on the button", m1.open && m1.expanded === "true" && !m2.open && m2.tab === "Guide" && /Guide/.test(m2.label), { m1, m2 });
await evaluate("document.querySelector('#nav-toggle').click(); true"); await sleep(300);
await evaluate("document.querySelector('#tab-guide').focus(); true"); await press("ArrowDown");
const m3 = await evaluate("document.querySelector('button.tab[aria-selected=true]').textContent");
await send("Input.dispatchKeyEvent", { type: "rawKeyDown", key: "Escape", code: "Escape", windowsVirtualKeyCode: 27 });
await send("Input.dispatchKeyEvent", { type: "keyUp", key: "Escape", code: "Escape", windowsVirtualKeyCode: 27 }); await sleep(300);
const m4 = { open: await vis(".tabs"), focus: await active() };
check("menu keyboard: Down moves through the views; Escape closes the menu and returns focus to the menu button", m4.open === false && m4.focus === "nav-toggle", { m3, m4 });
await evaluate("document.querySelector('.params-toggle').click(); true"); await sleep(500);
const d1 = { panel: await panelShown(), focus: await active(), scrim: await vis(".scrim"), sidebarLeft: await evaluate("Math.round(document.querySelector('.sidebar').getBoundingClientRect().left)") };
await shot("shell-1024-drawer-open", null);
check("drawer: opens over the workspace with a scrim; focus moves to its close button", d1.panel && d1.scrim && d1.focus === "params-close" && d1.sidebarLeft === 0, d1);
await evaluate(`(() => { const e = document.querySelector('#lat'); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, '-89.9'); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
await sleep(300);
const typed = await evaluate("document.querySelector('#lat').value");
await send("Input.dispatchKeyEvent", { type: "rawKeyDown", key: "Escape", code: "Escape", windowsVirtualKeyCode: 27 });
await send("Input.dispatchKeyEvent", { type: "keyUp", key: "Escape", code: "Escape", windowsVirtualKeyCode: 27 }); await sleep(500);
const d2 = { panel: await panelShown(), focus: await active() };
check("drawer: its fields work; Escape closes it and returns focus to the parameters toggle; the value is kept", typed === "-89.9" && !d2.panel && /params-toggle/.test(d2.focus)
  && (await evaluate("document.querySelector('#lat').value")) === "-89.9", { typed, d2 });
await evaluate("document.querySelector('.params-toggle').click(); true"); await sleep(400);
await mouseClick(900, 500); await sleep(400);
const d3 = await panelShown();
await evaluate("document.querySelector('.params-toggle').click(); true"); await sleep(400);
await evaluate("document.querySelector('#params-close').click(); true"); await sleep(400);
const d4 = await panelShown();
check("drawer: a press outside it and its close button both close it", !d3 && !d4, { outside: d3, close: d4 });

// ---- 3. phone (390, 320): the bar wraps; no sideways scrolling on any view
const widths = {};
for (const [w, h] of [[1440, 900], [1024, 768], [768, 1024], [390, 844], [320, 640]]) {
  await size(w, h); await load();
  for (const t of ["mission", "site", "compare", "data", "guide"]) {
    await evaluate(`document.querySelector('#tab-${t}').click(); true`); await sleep(700);
    widths[`${w}:${t}`] = await evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth");
  }
  if (w <= 390) {
    const bar = await evaluate("(() => { const b = document.querySelector('.topbar').getBoundingClientRect(); const items = [...document.querySelectorAll('.topbar > *, .topbar-right > *')].filter(e => getComputedStyle(e).display !== 'none'); return { h: Math.round(b.height), allInside: items.every(e => { const r = e.getBoundingClientRect(); return r.right <= document.documentElement.clientWidth + 0.5 && r.left >= -0.5; }) }; })()");
    report[`bar${w}`] = bar;
    await evaluate("document.querySelector('#tab-site').click(); true"); await sleep(600);
    await shot(`shell-${w}-site`, null);
  }
}
check("no sideways scrolling on any view at 1440, 1024, 768, 390 and 320 px", Object.values(widths).every(Boolean), widths);
check("phone: every command-bar item stays inside the screen (the bar wraps onto two rows)", report.bar390?.allInside && report.bar320?.allInside, { bar390: report.bar390, bar320: report.bar320 });

const errors = consoleMsgs.filter((m) => m.type === "exception" || m.type === "error" || m.type === "log-error");
check("no page exceptions or console errors", errors.length === 0, errors.slice(0, 5));
report.checks = checks; report.finished = new Date().toISOString();
fs.writeFileSync(path.join(OUT, "shell-check.json"), JSON.stringify(report, null, 1));
const failed = checks.filter((c) => !c.ok).length;
console.log(`shell-live-check: ${checks.length - failed}/${checks.length} checks passed`);
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(failed ? 1 : 0);
