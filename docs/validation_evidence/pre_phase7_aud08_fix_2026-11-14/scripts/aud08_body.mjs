
// AUD-08 check: the South Polar Map's selected-site marker and readout for typed coordinates (Site tab, 1440 px).
// For each case: the sidebar state (value kept, aria-invalid, hint), the map readout, the "centre on site" button and
// the gold selected-site ring, counted as pixels of the --sun colour in a 120 px box at the map pane's centre (the map
// animates to a selected site). One headless browser; appended to the Phase 1 CDP harness. Read only.
// Usage: node aud08.mjs --base <url> --out <dir> --label before|after
const LABEL = arg("--label", "run");
await send("Runtime.enable"); await send("Page.enable"); await send("Log.enable"); await send("Network.enable");
const READY = "document.querySelector('.topbar') && !/Connecting/.test(document.querySelector('.data-pill')?.textContent || 'Connecting')";
const setValue = (sel, v) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, ${JSON.stringify(v)}); e.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url: BASE + "/" }); await waitFor(READY, 60000, "status"); await sleep(800);
await evaluate("document.querySelector('#tab-site').click(); true"); await sleep(500);
await evaluate("(() => { const b = [...document.querySelectorAll('.view-switch button')].find(x => x.textContent.trim() === 'South polar map'); b?.click(); return !!b; })()");
await waitFor("document.querySelector('.map-host canvas')", 60000, "map");
await sleep(4000);
const sun = await evaluate("getComputedStyle(document.documentElement).getPropertyValue('--sun').trim()");
// gold ring pixels in a 120 px box at the map pane's centre (screenshot of the pane, decoded in the page)
const goldAtCentre = async (name) => {
  const r = await evaluate(`(() => { const b = document.querySelector('.map-host').getBoundingClientRect(); return { x: b.left, y: b.top, width: b.width, height: b.height }; })()`);
  const { data } = await send("Page.captureScreenshot", { format: "png", clip: { ...r, scale: 1 } });
  fs.writeFileSync(path.join(OUT, "screenshots", `${name}.png`), Buffer.from(data, "base64"));
  return evaluate(`(async () => { const img = new Image(); img.src = 'data:image/png;base64,${data}'; await img.decode();
    const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; const g = c.getContext('2d'); g.drawImage(img, 0, 0);
    const t = document.createElement('div'); t.style.color = ${JSON.stringify(sun)}; document.body.appendChild(t);
    const [R, G, B] = getComputedStyle(t).color.match(/\\d+/g).map(Number); t.remove();
    const cx = Math.round(img.width / 2), cy = Math.round(img.height / 2), h = 60;
    const d = g.getImageData(cx - h, cy - h, 2 * h, 2 * h).data; let n = 0;
    for (let i = 0; i < d.length; i += 4) if (Math.abs(d[i] - R) < 40 && Math.abs(d[i + 1] - G) < 40 && Math.abs(d[i + 2] - B) < 40) n++;
    return n; })()`);
};
const CASES = [
  ["valid Site01", "-89.463163", "222.510447"],
  ["invalid latitude -95", "-95", "222.510447"],
  ["valid Site01 (reset)", "-89.463163", "222.510447"],
  ["invalid latitude 95", "95", "222.510447"],
  ["valid Site01 (reset)", "-89.463163", "222.510447"],
  ["invalid latitude -90.0001", "-90.0001", "0"],
  ["valid Site01 (reset)", "-89.463163", "222.510447"],
  ["invalid longitude 400", "-89.463163", "400"],
  ["valid Site01 (reset)", "-89.463163", "222.510447"],
  ["invalid longitude -361", "-89.463163", "-361"],
  ["valid latitude -90 (pole)", "-90", "0"],
  ["valid latitude 90 (north pole, outside this map)", "90", "0"],
  ["valid longitude -360", "-85", "-360"],
  ["valid longitude 360", "-85", "360"],
];
const out = { label: LABEL, base: BASE, sunColour: sun, cases: [] };
let i = 0;
for (const [name, lat, lon] of CASES) {
  i++;
  await setValue("#lat", lat); await setValue("#lon", lon);
  await sleep(1800);                                    // marker update, 300 ms view animation, coverage reply
  const ui = await evaluate(`({
    latValue: document.querySelector('#lat').value, lonValue: document.querySelector('#lon').value,
    latInvalid: document.querySelector('#lat').getAttribute('aria-invalid'), lonInvalid: document.querySelector('#lon').getAttribute('aria-invalid'),
    hint: document.querySelector('#coord-hint')?.textContent, hintClass: document.querySelector('#coord-hint')?.className,
    mapReadout: [...document.querySelectorAll('.map-readout > span:not(.scale-bar)')].map(s => s.textContent).join(' | ') || null,
    centreOnSiteDisabled: document.querySelector('.map-tools button:nth-child(2)')?.disabled,
    explorerSelected: document.querySelector('.explorer')?.textContent.includes('No site selected') ? 'no site selected' : 'site shown' })`);
  const gold = await goldAtCentre(`aud08-${String(i).padStart(2, "0")}-${name.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}`);
  out.cases.push({ name, lat, lon, ...ui, goldPixelsAtMapCentre: gold });
}
out.console = consoleMsgs.filter((x) => /error|exception|warn/.test(x.type));
out.coverageRequests = requests.filter((u) => /\/api\/coverage/.test(u)).map((u) => u.replace(BASE, ""));
fs.writeFileSync(path.join(OUT, `aud08-${LABEL}.json`), JSON.stringify(out, null, 1));
for (const c of out.cases) console.log(`${c.name.padEnd(50)} readout=${JSON.stringify(c.mapReadout)} gold=${c.goldPixelsAtMapCentre} centreBtnDisabled=${c.centreOnSiteDisabled} latInv=${c.latInvalid} lonInv=${c.lonInvalid} kept=${c.latValue},${c.lonValue}`);
console.log(JSON.stringify({ console: out.console.length, coverageRequests: out.coverageRequests }));
ws.close(); proc.kill(); try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* */ }
process.exit(0);
