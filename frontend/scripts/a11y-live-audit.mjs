#!/usr/bin/env node
// U-04 live accessibility audit (WCAG 2.2 AA) of the running LUNA-OPS interface.
//
// Drives a locally installed Chrome or Edge in headless mode through the Chrome DevTools Protocol (Node's built-in
// WebSocket; no packages). Needs the app running (e.g. `python start.py --no-browser --port 8765`).
//
//   node scripts/a11y-live-audit.mjs --base http://127.0.0.1:8765 --out <dir> [--browser <path>] [--label after] [--release-views-only]
//
// For each view it records: the browser's accessibility tree (controls and images without a name), structure
// (lang, title, landmarks, headings, duplicate ids, positive tabindex, aria-hidden focusables, table headers),
// text contrast of every visible text node (composited backgrounds), a real Tab-key walk (order, focus indicator,
// clipping by overflow containers, obscured focus, traps), target sizes (24 px with the spacing exception), reflow at
// 320 CSS px, text-spacing overrides (1.4.12) and screenshots. Results go to <out>/audit-<label>.json.
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const BASE = arg("--base", "http://127.0.0.1:8765");
const OUT = path.resolve(arg("--out", "a11y-audit"));
const LABEL = arg("--label", "run");
const BROWSERS = [arg("--browser", ""), "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", "/usr/bin/google-chrome", "/usr/bin/chromium"].filter(Boolean);
const BROWSER = BROWSERS.find((b) => fs.existsSync(b));
if (!BROWSER) { console.error("No Chrome/Edge found; pass --browser"); process.exit(2); }
fs.mkdirSync(path.join(OUT, "screenshots"), { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---------------------------------------------------------------- browser + CDP
const PORT = 9300 + Math.floor(Math.random() * 400);
const profile = fs.mkdtempSync(path.join(os.tmpdir(), "luna-a11y-"));
const proc = spawn(BROWSER, [`--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`, "--headless=new", "--no-first-run",
  "--no-default-browser-check", "--disable-extensions", "--hide-scrollbars", "--force-color-profile=srgb",
  "--enable-unsafe-swiftshader", "--window-size=1440,900", "about:blank"], { stdio: "ignore" });
let ws = null;
for (let i = 0; i < 100 && !ws; i++) {
  try {
    const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
    const page = list.find((t) => t.type === "page");
    if (page) ws = new WebSocket(page.webSocketDebuggerUrl);
  } catch { /* not up yet */ }
  if (!ws) await sleep(200);
}
await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
let nextId = 1;
const pending = new Map();
const listeners = [];
ws.onmessage = (m) => {
  const msg = JSON.parse(m.data);
  if (msg.id && pending.has(msg.id)) { const { res, rej } = pending.get(msg.id); pending.delete(msg.id); msg.error ? rej(new Error(msg.error.message)) : res(msg.result); }
  else if (msg.method) for (const l of listeners) l(msg);
};
const send = (method, params = {}) => new Promise((res, rej) => { const id = nextId++; pending.set(id, { res, rej }); ws.send(JSON.stringify({ id, method, params })); });
const evaluate = async (expr) => {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error("page error: " + (r.exceptionDetails.exception?.description || r.exceptionDetails.text));
  return r.result.value;
};
const waitFor = async (cond, timeout = 30000, what = cond) => {
  const t0 = Date.now();
  while (Date.now() - t0 < timeout) { if (await evaluate(`!!(${cond})`)) return true; await sleep(250); }
  throw new Error("timeout waiting for " + what);
};
const viewport = (width, height, scale = 1) => send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: scale, mobile: false });
const KEYS = { Tab: 9, Enter: 13, " ": 32, Escape: 27, ArrowRight: 39, ArrowLeft: 37, ArrowUp: 38, ArrowDown: 40, PageUp: 33, PageDown: 34, Home: 36, End: 35, "+": 187, "-": 189 };
async function press(key, shift = false) {
  const code = key === " " ? "Space" : key;
  const base = { key, code, windowsVirtualKeyCode: KEYS[key], nativeVirtualKeyCode: KEYS[key], modifiers: shift ? 8 : 0 };
  await send("Input.dispatchKeyEvent", { type: "rawKeyDown", ...base });
  if (key === "Enter" || key === " " || key === "+" || key === "-") await send("Input.dispatchKeyEvent", { type: "char", ...base, text: key === "Enter" ? "\r" : key });
  await send("Input.dispatchKeyEvent", { type: "keyUp", ...base });
}
async function shot(name, full = false) {
  let restore = null;
  if (full) {
    const h = await evaluate(`Math.max(document.querySelector('.main')?.scrollHeight||0, document.querySelector('.sidebar')?.scrollHeight||0, innerHeight) + 70`);
    const w = await evaluate("innerWidth");
    restore = [w, await evaluate("innerHeight")];
    await viewport(w, Math.min(h, 7000));
    await sleep(600);
  }
  const { data } = await send("Page.captureScreenshot", { format: "png" });
  fs.writeFileSync(path.join(OUT, "screenshots", `${LABEL}-${name}.png`), Buffer.from(data, "base64"));
  if (restore) { await viewport(restore[0], restore[1]); await sleep(300); }
  return `screenshots/${LABEL}-${name}.png`;
}
// set a React-controlled input/select value
const setValue = (sel, v) => evaluate(`(() => { const el = document.querySelector(${JSON.stringify(sel)});
  const proto = el instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, ${JSON.stringify(v)});
  el.dispatchEvent(new Event(el instanceof HTMLSelectElement ? 'change' : 'input', { bubbles: true })); return true; })()`);
const clickText = (selector, text) => evaluate(`(() => { const el = [...document.querySelectorAll(${JSON.stringify(selector)})]
  .find((e) => e.textContent.trim() === ${JSON.stringify(text)} || e.getAttribute('aria-label') === ${JSON.stringify(text)});
  if (!el) throw new Error('no element ' + ${JSON.stringify(selector + " " + text)}); el.click(); return true; })()`);

// ---------------------------------------------------------------- in-page audits
const PAGE_LIB = String.raw`
window.__a11y = (() => {
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const parse = (s) => { const m = /rgba?\(([^)]+)\)/.exec(s || ''); if (!m) return null;
    const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; };
  const over = (top, bot) => { const a = top[3]; return [0, 1, 2].map((i) => top[i] * a + bot[i] * (1 - a)).concat(1); };
  const hex = (c) => '#' + c.slice(0, 3).map((v) => Math.round(v).toString(16).padStart(2, '0')).join('');
  const visible = (el) => { if (!el.getClientRects().length) return false; const cs = getComputedStyle(el);
    return cs.visibility !== 'hidden' && cs.display !== 'none'; };
  const desc = (el) => { if (!el || el === document.body) return 'body'; const r = el.getAttribute && el.getAttribute('role');
    const name = (el.getAttribute && (el.getAttribute('aria-label') || el.getAttribute('title'))) || (el.textContent || '').trim().replace(/\s+/g, ' ');
    return el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).join('.') : '') + (r ? '[role=' + r + ']' : '') + ' "' + name.slice(0, 50) + '"'; };
  function background(el) {
    let bg = [0, 0, 0, 0], complex = null; const stack = [];
    for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (cs.backgroundImage && cs.backgroundImage !== 'none') complex = complex || ('background-image on ' + desc(e));
      if (['CANVAS', 'IMG', 'VIDEO'].includes(e.tagName)) complex = complex || 'over media';
      const c = parse(cs.backgroundColor); if (c && c[3] > 0) stack.push(c);
      if (c && c[3] >= 1) break;
    }
    let out = parse(getComputedStyle(document.documentElement).backgroundColor) || [255, 255, 255, 1];
    if (out[3] < 1) out = [255, 255, 255, 1];
    for (let i = stack.length - 1; i >= 0; i--) out = over(stack[i], out);
    return { bg: out, complex };
  }
  function opacity(el) { let o = 1; for (let e = el; e && e.nodeType === 1; e = e.parentElement) o *= Number(getComputedStyle(e).opacity); return o; }
  function contrast() {
    const rows = new Map(); const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n = tw.nextNode(); n; n = tw.nextNode()) {
      const text = n.textContent.replace(/\s+/g, ' ').trim(); if (!text) continue;
      const el = n.parentElement; if (!el || !visible(el)) continue;
      if (el.closest('.sr-only, [aria-hidden="true"], option, script, style, title')) continue;
      const inSvg = !!el.closest('svg'); const cs = getComputedStyle(el);
      let fg = parse(inSvg ? cs.fill : cs.color); if (!fg) continue;
      const host = inSvg ? el.closest('svg').parentElement : el;
      const { bg, complex } = background(host);
      const op = opacity(el); fg = over([fg[0], fg[1], fg[2], fg[3] * op], bg);
      const disabled = !!el.closest(':disabled, [aria-disabled="true"]');
      const size = parseFloat(cs.fontSize), weight = Number(cs.fontWeight) || 400;
      const large = size >= 24 || (size >= 18.66 && weight >= 700);
      const r = ratio(fg, bg), need = large ? 3 : 4.5;
      const key = [hex(fg), hex(bg), large, disabled, inSvg].join('|');
      const cur = rows.get(key) || { fg: hex(fg), bg: hex(bg), ratio: Math.round(r * 100) / 100, need, large, disabled, svg: inSvg,
        complex, count: 0, minSizePx: size, samples: [] };
      cur.count++; cur.minSizePx = Math.min(cur.minSizePx, size); if (cur.samples.length < 3) cur.samples.push(text.slice(0, 60) + ' @ ' + desc(el).slice(0, 70));
      rows.set(key, cur);
    }
    const all = [...rows.values()].sort((a, b) => a.ratio - b.ratio);
    return { pairs: all, failures: all.filter((r) => !r.disabled && r.ratio < r.need) };
  }
  function structure() {
    const ids = {}; document.querySelectorAll('[id]').forEach((e) => { ids[e.id] = (ids[e.id] || 0) + 1; });
    const focusSel = 'a[href],button,input,select,textarea,[tabindex],summary,[contenteditable="true"]';
    const hiddenFocusable = [...document.querySelectorAll('[aria-hidden="true"]')].flatMap((h) => [...h.querySelectorAll(focusSel)])
      .filter((e) => !e.disabled && e.tabIndex >= 0).map(desc);
    const tables = [...document.querySelectorAll('table')].filter(visible).map((t) => ({ table: desc(t).slice(0, 60),
      th: t.querySelectorAll('th').length, caption: !!t.querySelector('caption'), rows: t.rows.length }));
    const unlabeled = [...document.querySelectorAll('input,select,textarea')].filter((e) => e.type !== 'hidden' && visible(e))
      .filter((e) => !(e.labels && e.labels.length) && !e.getAttribute('aria-label') && !e.getAttribute('aria-labelledby')).map(desc);
    return {
      lang: document.documentElement.lang, title: document.title,
      landmarks: [...document.querySelectorAll('header,nav,main,aside,footer,[role=banner],[role=navigation],[role=main],[role=complementary],[role=region],section[aria-label],section[aria-labelledby]')]
        .filter(visible).map((e) => (e.getAttribute('role') || e.tagName.toLowerCase()) + ':' + (e.getAttribute('aria-label') || e.getAttribute('aria-labelledby') || '')),
      headings: [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].filter(visible).map((h) => h.tagName + ' ' + h.textContent.trim().replace(/\s+/g, ' ').slice(0, 60)),
      duplicateIds: Object.entries(ids).filter(([, n]) => n > 1).map(([k]) => k),
      positiveTabindex: [...document.querySelectorAll('[tabindex]')].filter((e) => e.tabIndex > 0).map(desc),
      ariaHiddenFocusable: hiddenFocusable, unlabeledFormControls: unlabeled, tables,
      roleApplication: [...document.querySelectorAll('[role=application]')].map(desc),
      liveRegions: [...document.querySelectorAll('[aria-live],[role=alert],[role=status]')].map((e) => desc(e).slice(0, 60) + ' live=' + (e.getAttribute('aria-live') || e.getAttribute('role'))),
    };
  }
  function focusInfo() {
    const el = document.activeElement; if (!el || el === document.body) return { el: 'body' };
    const cs = getComputedStyle(el), r = el.getBoundingClientRect();
    const ow = parseFloat(cs.outlineWidth) || 0, off = parseFloat(cs.outlineOffset) || 0;
    const indicator = (cs.outlineStyle !== 'none' && ow > 0) ? 'outline ' + ow + 'px ' + cs.outlineColor + ' offset ' + off
      : (cs.boxShadow !== 'none' ? 'box-shadow ' + cs.boxShadow : 'NONE');
    // how much of the outline ring survives clipping by overflow ancestors
    const ext = ow > 0 ? off + ow : 0;
    let box = { l: r.left - ext, t: r.top - ext, r: r.right + ext, b: r.bottom + ext };
    const clippedBy = [];
    for (let a = el.parentElement; a; a = a.parentElement) {
      const acs = getComputedStyle(a);
      if (acs.overflowX !== 'visible' || acs.overflowY !== 'visible') {
        const ar = a.getBoundingClientRect();
        const sides = [box.l < ar.left - 0.5 && 'left', box.t < ar.top - 0.5 && 'top', box.r > ar.right + 0.5 && 'right', box.b > ar.bottom + 0.5 && 'bottom'].filter(Boolean);
        if (sides.length) clippedBy.push(desc(a).slice(0, 50) + ' [' + sides.join(',') + ']');
        box = { l: Math.max(box.l, ar.left), t: Math.max(box.t, ar.top), r: Math.min(box.r, ar.right), b: Math.min(box.b, ar.bottom) };
      }
    }
    // ring visibility: an outset ring needs at least one side outside the element and inside every clip
    const ringSides = ow > 0 ? (off >= 0 ? ['l', 't', 'r', 'b'].filter((s) => (s === 'l' ? box.l < r.left - 0.5 : s === 't' ? box.t < r.top - 0.5 : s === 'r' ? box.r > r.right + 0.5 : box.b > r.bottom + 0.5)).length : 4) : 0;
    const cx = Math.min(Math.max(r.left + r.width / 2, 0), innerWidth - 1), cy = Math.min(Math.max(r.top + r.height / 2, 0), innerHeight - 1);
    const top = document.elementFromPoint(cx, cy);
    const inView = r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth;
    return { el: desc(el), tag: el.tagName, rect: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)], indicator,
      ringSidesVisible: ringSides, clippedBy, inView, obscured: inView && top && !(top === el || el.contains(top) || top.contains(el)) ? desc(top).slice(0, 60) : null };
  }
  function targets() {
    const els = [...document.querySelectorAll('a[href],button,input:not([type=hidden]),select,textarea,summary,[tabindex]:not([tabindex="-1"]),[role=button],[role=tab]')]
      .filter((e) => visible(e) && !e.disabled);
    const rects = els.map((e) => ({ e, r: e.getBoundingClientRect() })).filter((x) => x.r.width > 0 && x.r.height > 0);
    const small = rects.filter((x) => x.r.width < 24 - 0.01 || x.r.height < 24 - 0.01);
    const out = [];
    for (const s of small) {
      const cx = s.r.left + s.r.width / 2, cy = s.r.top + s.r.height / 2;
      const hits = rects.filter((o) => o !== s).filter((o) => {
        const dx = Math.max(o.r.left - cx, 0, cx - o.r.right), dy = Math.max(o.r.top - cy, 0, cy - o.r.bottom);
        const smallO = small.includes(o);
        if (smallO) { const ox = o.r.left + o.r.width / 2, oy = o.r.top + o.r.height / 2; return Math.hypot(ox - cx, oy - cy) < 24; }
        return Math.hypot(dx, dy) < 12;
      });
      const inline = !!s.e.closest('p, li, dd') && getComputedStyle(s.e).display.startsWith('inline');
      out.push({ el: desc(s.e).slice(0, 80), size: [Math.round(s.r.width * 10) / 10, Math.round(s.r.height * 10) / 10],
        spacingOk: hits.length === 0, inlineException: inline, conflicts: hits.slice(0, 3).map((h) => desc(h.e).slice(0, 50)),
        pass: hits.length === 0 || inline });
    }
    return { interactive: rects.length, undersized: out, failures: out.filter((o) => !o.pass) };
  }
  function reflow() {
    const vw = innerWidth, doc = document.documentElement;
    const scrollers = ['.main', '.sidebar', '.shell'].map((s) => document.querySelector(s)).filter(Boolean)
      .map((e) => ({ el: desc(e).slice(0, 40), scrollW: e.scrollWidth, clientW: e.clientWidth, overflow: e.scrollWidth > e.clientWidth + 1 }));
    const exempt = (e) => !!e.closest('.table-scroll, table, svg, canvas, .map-host, .three-host, [style*="overflow-x: auto"]');
    const offenders = [...document.querySelectorAll('body *')].filter(visible).filter((e) => !exempt(e)).filter((e) => {
      const r = e.getBoundingClientRect(); return r.right > vw + 1 && r.width > 0; }).map((e) => desc(e).slice(0, 70));
    return { viewport: vw, docScrollW: doc.scrollWidth, horizontalScroll: doc.scrollWidth > vw + 1, scrollers, offenders: offenders.slice(0, 25), offenderCount: offenders.length };
  }
  function clipped() {
    return [...document.querySelectorAll('body *')].filter(visible).filter((e) => {
      const cs = getComputedStyle(e); if (!(e.textContent || '').trim() || e.closest('svg, table, .table-scroll')) return false;
      const hid = /hidden|clip/.test(cs.overflowX + cs.overflowY);
      return hid && (e.scrollWidth > e.clientWidth + 1 || e.scrollHeight > e.clientHeight + 1) && !e.matches('.sr-only');
    }).map((e) => desc(e).slice(0, 80) + ' ' + e.scrollWidth + 'x' + e.scrollHeight + ' in ' + e.clientWidth + 'x' + e.clientHeight);
  }
  return { contrast, structure, focusInfo, targets, reflow, clipped, desc };
})(); true`;

async function axCheck() {
  await send("Accessibility.enable");
  const { nodes } = await send("Accessibility.getFullAXTree");
  const INTERACTIVE = new Set(["button", "link", "textbox", "combobox", "listbox", "slider", "spinbutton", "tab", "checkbox", "radio",
    "switch", "menuitem", "searchbox", "treeitem", "gridcell"]);
  const rows = nodes.filter((n) => !n.ignored).map((n) => ({ role: n.role?.value, name: (n.name?.value || "").trim(),
    focusable: !!(n.properties || []).find((p) => p.name === "focusable" && p.value.value),
    valuetext: (n.properties || []).find((p) => p.name === "valuetext")?.value?.value ?? null, value: n.value?.value ?? null }));
  const unnamed = rows.filter((r) => (INTERACTIVE.has(r.role) || r.role === "image" || r.role === "img") && !r.name);
  const focusableGeneric = rows.filter((r) => r.focusable && ["generic", "cell", "none", "group"].includes(r.role));
  const roles = {}; for (const r of rows) roles[r.role] = (roles[r.role] || 0) + 1;
  return { nodes: rows.length, unnamed, focusableWithoutWidgetRole: focusableGeneric.map((r) => r.role + ' "' + r.name.slice(0, 60) + '"'),
    sliders: rows.filter((r) => r.role === "slider").map((r) => ({ name: r.name, value: r.value, valuetext: r.valuetext })), roles };
}

async function tabWalk(max = 160, fromTop = false) {
  await evaluate("document.activeElement && document.activeElement.blur(); window.scrollTo(0,0); true");
  await send("Runtime.evaluate", { expression: "document.body.focus()" });
  // Phase 5 views: start the walk at the top of the page (focus the skip link), so the cycle closes on a top-bar control
  // whose position does not depend on the main area's scroll; otherwise the walk starts at the last clicked control
  if (fromTop) await evaluate("(() => { document.querySelector('.main')?.scrollTo(0, 0); document.querySelector('a.skip-link')?.focus(); return true; })()");
  const stops = []; let first = null;
  for (let i = 0; i < max; i++) {
    await press("Tab"); await sleep(40);
    let f = await evaluate("__a11y.focusInfo()");
    if (f.indicator === "NONE") { await sleep(250); f = await evaluate("__a11y.focusInfo()"); f.remeasured = true;
      if (f.indicator === "NONE" && f.rect) { const [x, y, w, h] = f.rect; const { data } = await send("Page.captureScreenshot", { format: "png", clip: { x: Math.max(0, x - 8), y: Math.max(0, y - 8), width: w + 16, height: h + 16, scale: 2 } });
        const fn = `screenshots/${LABEL}-noindicator-${i}.png`; fs.writeFileSync(path.join(OUT, fn), Buffer.from(data, "base64")); f.evidence = fn; } }
    if (f.el === "body") { stops.push(f); continue; }
    const key = f.el + "@" + f.rect.join(",");
    if (first === null) first = key; else if (key === first) break;
    stops.push(f);
  }
  const real = stops.filter((s) => s.el !== "body");
  return { stops: real.length, cycled: real.length < max, list: real,
    noIndicator: real.filter((s) => s.indicator === "NONE").map((s) => s.el),
    clipped: real.filter((s) => s.indicator.startsWith("outline") && s.ringSidesVisible < 4).map((s) => ({ el: s.el, ringSidesVisible: s.ringSidesVisible, clippedBy: s.clippedBy })),
    obscured: real.filter((s) => s.obscured).map((s) => ({ el: s.el, by: s.obscured })), notInView: real.filter((s) => !s.inView).map((s) => s.el) };
}

async function auditView(name, opts = {}) {
  await evaluate(PAGE_LIB);
  const res = { view: name, at: new Date().toISOString() };
  res.structure = await evaluate("__a11y.structure()");
  res.ax = await axCheck();
  res.contrast = await evaluate("__a11y.contrast()");
  res.targets = await evaluate("__a11y.targets()");
  res.screenshot = await shot(name, true);
  // LUNA-OPS 2.0 Phase 1: every walk starts at the top of the page (the skip link) so it is one deterministic full cycle;
  // before, a walk started wherever the previous step left the browser's focus starting point (see the Phase 1 evidence)
  if (opts.tab !== false) res.keyboard = await tabWalk(opts.maxTabs || 160, opts.fromTop !== false);
  // text spacing (1.4.12)
  await evaluate(`(() => { const s = document.createElement('style'); s.id = '__ts'; s.textContent = '* { line-height: 1.5 !important; letter-spacing: 0.12em !important; word-spacing: 0.16em !important; } p { margin-bottom: 2em !important; }'; document.head.appendChild(s); return true; })()`);
  await sleep(300);
  res.textSpacing = { clipped: await evaluate("__a11y.clipped()"), screenshot: await shot(name + "-textspacing", false) };
  await evaluate("document.getElementById('__ts').remove(); true");
  // reflow at 320 CSS px (= 1280 px at 400 %)
  await viewport(320, 640); await sleep(700); await evaluate(PAGE_LIB);
  res.reflow320 = { ...(await evaluate("__a11y.reflow()")), screenshot: await shot(name + "-320", false) };
  await viewport(1440, 900); await sleep(500);
  return res;
}

// ---------------------------------------------------------------- scenario
const report = { label: LABEL, base: BASE, browser: BROWSER, browserVersion: (await send("Browser.getVersion")).product, views: [], functional: {} };
await send("Page.enable"); await send("Runtime.enable");
await viewport(1440, 900);
await send("Page.navigate", { url: BASE + "/" });
await waitFor("document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')", 60000, "status");
await sleep(1500);
report.views.push(await auditView("site-welcome"));
// skip link: first Tab stop after a fresh load, Enter moves focus to the main landmark (2.4.1)
await send("Page.navigate", { url: BASE + "/" });
await waitFor("document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')", 60000, "status");
await sleep(800); await evaluate(PAGE_LIB);
await press("Tab"); await sleep(100);
const skipFirst = await evaluate("__a11y.desc(document.activeElement)");
await press("Enter"); await sleep(300);
report.functional.skipLink = { firstTabStop: skipFirst, afterEnter: await evaluate("document.activeElement.id || document.activeElement.tagName") };
// tabs: arrow keys move and select (WAI-ARIA tabs pattern)
await evaluate("document.querySelector('button.tab[aria-selected=true]').focus(); true");
await press("ArrowRight"); await sleep(300);
const afterRight = await evaluate("({ selected: document.querySelector('button.tab[aria-selected=true]')?.textContent, focused: document.activeElement.textContent, tabStops: [...document.querySelectorAll('button.tab')].filter(b => b.tabIndex === 0).length })");
await press("ArrowLeft"); await sleep(300);
report.functional.tabsArrowKeys = { afterRight, afterLeft: await evaluate("document.querySelector('button.tab[aria-selected=true]')?.textContent") };

// error identification for coordinates (3.3.1)
await setValue("#lat", "abc"); await setValue("#lon", "10"); await sleep(900);
report.functional.invalidCoordinates = await evaluate(`({ hint: document.querySelector('.sidebar p[aria-live]')?.textContent, latInvalid: document.querySelector('#lat').getAttribute('aria-invalid'),
  describedBy: document.querySelector('#lat').getAttribute('aria-describedby'), runDisabled: document.querySelector('.run-button').disabled })`);
await shot("invalid-coordinates");

// analyse Site01 (production kernels, registered terrain)
await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447");
await waitFor("/Terrain coverage/.test(document.querySelector('.sidebar p[aria-live]')?.textContent || '')", 60000, "coverage");
await setValue("#start", "2026-11-14T00:00"); await setValue("#end", "2026-11-21T00:00");
await evaluate("document.querySelector('.run-button').click(); true");
await waitFor("document.querySelector('.site-title')", 900000, "analysis result");
await sleep(2500);
report.functional.slider = await evaluate(`(() => { const s = document.querySelector('.scrubber input[type=range]'); return { valuenow: s.value, valuetext: s.getAttribute('aria-valuetext') }; })()`);
report.functional.readoutLive = await evaluate("document.querySelector('.readout').getAttribute('aria-live')");
// panorama hover readout dismissible with Escape (1.4.13)
const pr = await evaluate("(() => { const r = document.querySelector('.panorama svg').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; })()");
await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: pr[0], y: pr[1] }); await sleep(300);
const hoverShown = await evaluate("[...document.querySelectorAll('.panorama svg text')].some(t => /horizon/.test(t.textContent))");
await press("Escape"); await sleep(300);
report.functional.panoramaHoverEscape = { shown: hoverShown, afterEscape: await evaluate("[...document.querySelectorAll('.panorama svg text')].some(t => /horizon/.test(t.textContent))") };
await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 5, y: 5 });
await clickText("button.toggle-table", "Show"); await clickText("button.toggle-table", "Show table"); await sleep(500);
report.views.push(await auditView("site-result-technical", { maxTabs: 400 }));
// playing state: the live region must not chatter
await clickText("button.play", "Play animation"); await sleep(400);
report.functional.readoutLiveWhilePlaying = await evaluate("document.querySelector('.readout').getAttribute('aria-live')");
await clickText("button.play", "Pause animation");
// keyboard operation of the map, the 3D view and the panorama (2.1.1): compare element pixels before/after keys
const elemHash = async (sel) => { const r = await evaluate(`(() => { const b = document.querySelector(${JSON.stringify(sel)}).getBoundingClientRect(); return { x: b.left, y: b.top, width: b.width, height: b.height, scale: 1 }; })()`);
  const { data } = await send("Page.captureScreenshot", { format: "png", clip: r }); let h = 0; for (let i = 0; i < data.length; i += 7) h = (h * 31 + data.charCodeAt(i)) | 0; return h; };
const keyTest = async (sel, keys, shift = false) => { await evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); e.scrollIntoView({ block: "center" }); e.focus(); return true; })()`); await sleep(1200);
  const before = await elemHash(sel); for (const k of keys) { await press(k, shift); await sleep(250); } await sleep(900);
  return { focused: await evaluate(`document.activeElement === document.querySelector(${JSON.stringify(sel)})`), changed: (await elemHash(sel)) !== before }; };
report.functional.mapKeyboard = { pan: await keyTest(".map-host", ["ArrowRight", "ArrowRight", "ArrowDown"]), zoom: await keyTest(".map-host", ["+", "+"]) };
report.functional.terrain3dKeyboard = { pan: await keyTest(".three-host", ["ArrowLeft", "ArrowLeft"]), rotate: await keyTest(".three-host", ["ArrowLeft", "ArrowLeft", "ArrowUp"], true), zoom: await keyTest(".three-host", ["+", "+"]) };
await evaluate("document.querySelector('.panorama svg').focus(); true"); await sleep(300);
const pv = async () => evaluate("(() => { const s = document.querySelector('.panorama svg'); return { role: s.getAttribute('role'), now: s.getAttribute('aria-valuenow'), text: s.getAttribute('aria-valuetext'), visibleReadout: [...s.querySelectorAll('text')].some(t => /horizon/.test(t.textContent)) }; })()");
const pv0 = await pv(); await press("ArrowRight"); await sleep(200); const pv1 = await pv(); await press("PageUp"); await sleep(200); const pv2 = await pv();
await evaluate("document.activeElement.blur(); true"); await sleep(200);
report.functional.panoramaKeyboard = { onFocus: pv0, afterArrowRight: pv1, afterPageUp: pv2, afterBlur: await pv() };
// single-pointer alternatives to dragging (2.5.7): click the view buttons, compare pixels
const clickTest = async (paneSel, btnSel) => { await evaluate(`document.querySelector(${JSON.stringify(paneSel)}).scrollIntoView({ block: 'center' }); true`); await sleep(1000);
  const before = await elemHash(paneSel); await evaluate(`document.querySelector(${JSON.stringify(btnSel)}).click(); true`); await sleep(1200);
  return { button: await evaluate(`(() => { const b = document.querySelector(${JSON.stringify(btnSel)}); const r = b.getBoundingClientRect(); return { name: b.getAttribute('aria-label'), size: [Math.round(r.width), Math.round(r.height)] }; })()`), changed: (await elemHash(paneSel)) !== before }; };
report.functional.pointerAlternatives = {
  mapZoomIn: await clickTest('.map-host', '.map-host .ol-zoom-in'), mapZoomOut: await clickTest('.map-host', '.map-host .ol-zoom-out'),
  view3dRotateLeft: await clickTest('.three-host', '.view-controls button:nth-child(1)'), view3dRotateRight: await clickTest('.three-host', '.view-controls button:nth-child(2)'),
  view3dZoomIn: await clickTest('.three-host', '.view-controls button:nth-child(3)'), view3dZoomOut: await clickTest('.three-host', '.view-controls button:nth-child(4)') };
report.functional.statusAfterAnalysis = await evaluate("document.querySelector('.sidebar [role=status]')?.textContent");
await clickText(".mode-switch button", "Public"); await sleep(600);
report.views.push(await auditView("site-result-public", { tab: false }));
await clickText(".mode-switch button", "Technical");

// comparison: this site plus a regional site, two one-week windows
await clickText("button.quiet-button", "Add to comparison");
await setValue("#lat", "-89.9"); await setValue("#lon", "0"); await sleep(600);
await clickText("button.quiet-button", "Add to comparison");
await clickText("button.tab", "Compare"); await sleep(500);
await clickText("button.quiet-button", "Add the panel's dates");
await clickText("button.quiet-button", "Add one synodic month later");
await evaluate("[...document.querySelectorAll('button.run-button')].find(b => /^Compare/.test(b.textContent)).click(); true");
await waitFor("document.querySelector('table.matrix')", 900000, "comparison");
await sleep(1500);
report.functional.statusAfterComparison = await evaluate("document.querySelector('.main [role=status]')?.textContent");
report.views.push(await auditView("compare-matrix", { maxTabs: 200 }));
// keyboard activation of a matrix cell (2.1.1): focus the first result cell, press Space, expect the Site tab
const cellSel = "table.matrix td button, table.matrix td[tabindex]";
for (const key of [" ", "Enter"]) {
  await clickText("button.tab", "Compare"); await sleep(400);
  await evaluate(`document.querySelector(${JSON.stringify(cellSel)}).focus(); true`);
  await press(key); await sleep(1500);
  report.functional[key === " " ? "matrixCellSpace" : "matrixCellEnter"] = await evaluate("document.querySelector('button.tab[aria-selected=true]').textContent");
}

await clickText("button.tab", "Data and validation"); await sleep(800);
report.views.push(await auditView("data", { maxTabs: 200 }));
await clickText("button.tab", "Guide"); await sleep(500);
report.views.push(await auditView("guide"));

// reduced motion (2.3.3 is AAA; recorded for information) and mobile screenshots
await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] });
report.functional.reducedMotionTransition = await evaluate("(() => { const d = document.createElement('div'); d.className = 'progress'; d.innerHTML = '<div></div>'; document.body.appendChild(d); const t = getComputedStyle(d.firstChild).transitionDuration; d.remove(); return t; })()");
await send("Emulation.setEmulatedMedia", { features: [] });
await viewport(390, 844); await clickText("button.tab", "Site"); await sleep(800); report.functional.mobileSite = await shot("mobile-390-site");
await viewport(1440, 900);

// ---------------------------------------------------------------- Phase 5 views (default; --release-views-only skips them)
// Runs after the release scenario, so the six release views above are measured exactly as before. Covers the explorer's
// 3D globe and local terrain views, the populated mission dashboard and, on a fresh page with an empty session, the
// empty dashboard; plus keyboard operation of the globe and the terrain preview and the dashboard's deep-link focus.
if (!process.argv.includes("--release-views-only")) {
  report.phase5 = true;
  await clickText("button.tab", "Site"); await sleep(800);
  if (await evaluate("!!document.querySelector('a[href$=\"/result.json\"]')")) { await clickText("button", "Back to the Moon explorer"); await sleep(800); }
  await clickText(".view-switch button", "3D Moon globe");
  await waitFor("document.querySelector('.globe-host canvas')", 60000, "globe"); await sleep(3000);
  report.views.push(await auditView("site-explorer-globe", { maxTabs: 200, fromTop: true }));
  report.functional.globeKeyboard = { rotate: await keyTest(".globe-host", ["ArrowLeft", "ArrowLeft", "ArrowUp"]), zoom: await keyTest(".globe-host", ["+", "+"]) };
  await clickText(".view-switch button", "Local terrain");
  await waitFor("document.querySelector('.terrain-stats') && document.querySelector('.terrain-preview .three-host canvas')", 90000, "terrain preview"); await sleep(3000);
  report.views.push(await auditView("site-explorer-terrain", { maxTabs: 200, fromTop: true }));
  report.functional.terrainPreviewKeyboard = { pan: await keyTest(".terrain-preview .three-host", ["ArrowLeft", "ArrowLeft"]),
    rotate: await keyTest(".terrain-preview .three-host", ["ArrowLeft", "ArrowUp"], true), zoom: await keyTest(".terrain-preview .three-host", ["+", "+"]) };
  report.functional.returnToResult = await evaluate("[...document.querySelectorAll('.explorer button')].some(b => /^Return to the result/.test(b.textContent))");
  await clickText(".view-switch button", "South polar map"); await sleep(800);
  await clickText("button.tab", "Mission"); await waitFor("document.querySelector('.mission')", 30000, "mission"); await sleep(1500);
  report.views.push(await auditView("mission", { maxTabs: 200, fromTop: true }));
  // a dashboard deep link moves focus to the result section it names
  await clickText(".mission-links button", "Sunlight"); await sleep(2500);   // Phase 7: the dashboard link is now labelled "Sunlight"
  report.functional.missionDeepLinkFocus = await evaluate("document.activeElement.id");
  // fresh page, empty session: the empty dashboard
  await evaluate("try { sessionStorage.clear(); } catch (e) {} true");
  await send("Page.navigate", { url: BASE + "/" });
  await waitFor("document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')", 60000, "status");
  await sleep(1000);
  await clickText("button.tab", "Mission"); await waitFor("document.querySelector('.mission')", 30000, "mission"); await sleep(1000);
  report.views.push(await auditView("mission-empty", { maxTabs: 200, fromTop: true }));
  await viewport(390, 844); await sleep(800); report.functional.mobileMission = await shot("mobile-390-mission"); await viewport(1440, 900);
  // LUNA-OPS 2.0 Phase 7: the Landing (Phase 5) and Communication (Phase 6) views, deferred from their phases
  await setValue("#lat", "-89.463163"); await setValue("#lon", "222.510447"); await sleep(1500);
  await evaluate("document.querySelector('#tab-landing').click(); true");
  await waitFor("document.querySelector('.landing-run') && !document.querySelector('.landing-run').disabled", 60000, "landing run");
  await evaluate("document.querySelector('.landing-run').click(); true");
  await waitFor("document.querySelector('section[aria-labelledby=landing-footprint]') && document.querySelector('.landing-map canvas')", 300000, "landing screening");
  await sleep(3000);
  report.views.push(await auditView("landing", { maxTabs: 300, fromTop: true }));
  await evaluate("document.querySelector('#tab-comms').click(); true"); await sleep(1500);
  if (await evaluate("!!document.querySelector('.comms-run') && !document.querySelector('.comms-run').disabled")) {
    await evaluate("document.querySelector('.comms-run').click(); true");
    await waitFor("document.querySelector('.comms-windows') || document.querySelector('.comms-linkstatus')", 600000, "communication simulation");
    await sleep(2000);
  }
  report.views.push(await auditView("communication", { maxTabs: 300, fromTop: true }));
}

fs.writeFileSync(path.join(OUT, `audit-${LABEL}.json`), JSON.stringify(report, null, 1));
const sum = report.views.map((v) => ({ view: v.view, axUnnamed: v.ax.unnamed.length, focusableNoRole: v.ax.focusableWithoutWidgetRole.length,
  contrastFail: v.contrast.failures.length, targetFail: v.targets.failures.length, tabStops: v.keyboard?.stops ?? "-",
  noFocusIndicator: v.keyboard?.noIndicator.length ?? "-", focusClipped: v.keyboard?.clipped.length ?? "-", obscured: v.keyboard?.obscured.length ?? "-",
  reflowHScroll: v.reflow320.horizontalScroll, reflowOffenders: v.reflow320.offenderCount, spacingClipped: v.textSpacing.clipped.length,
  unlabeled: v.structure.unlabeledFormControls.length, dupIds: v.structure.duplicateIds.length, roleApplication: v.structure.roleApplication.length }));
console.table(sum);
console.log(JSON.stringify(report.functional, null, 1));
ws.close(); proc.kill();
try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* browser may still hold files */ }
