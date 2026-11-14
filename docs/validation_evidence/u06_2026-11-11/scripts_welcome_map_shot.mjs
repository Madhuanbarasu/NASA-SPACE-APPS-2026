// One screenshot of the welcome map pane, N seconds after load, nothing blocked (U-06 visual check).
//   node scripts_welcome_map_shot.mjs <base> <out.png> <seconds>
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
const [BASE, OUTPNG, SECS] = [process.argv[2], process.argv[3], Number(process.argv[4] || 6)];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const port = 9700 + Math.floor(Math.random() * 200);
const prof = fs.mkdtempSync(path.join(os.tmpdir(), "luna-perf-shot-"));
const p = spawn("C:/Program Files/Google/Chrome/Application/chrome.exe", [`--remote-debugging-port=${port}`, `--user-data-dir=${prof}`, "--headless=new",
  "--hide-scrollbars", "--enable-gpu", "--use-angle=d3d11", "--window-size=1440,900", "about:blank"], { stdio: "ignore" });
let ws; for (let i = 0; i < 100 && !ws; i++) { try { const l = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json(); const t = l.find((x) => x.type === "page"); if (t) ws = new WebSocket(t.webSocketDebuggerUrl); } catch {} if (!ws) await sleep(200); }
await new Promise((r) => (ws.onopen = r));
let id = 1; const pend = new Map();
ws.onmessage = (m) => { const x = JSON.parse(m.data); if (x.id && pend.has(x.id)) { pend.get(x.id)(x.result); pend.delete(x.id); } };
const send = (method, params = {}) => new Promise((r) => { const i = id++; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
await send("Page.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 1300, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url: BASE + "/" });
await sleep(SECS * 1000);
const r = (await send("Runtime.evaluate", { returnByValue: true, expression: "(() => { const b = document.querySelector('.map-host').closest('.pane').getBoundingClientRect(); return { x: b.left, y: b.top, width: b.width, height: b.height, scale: 1 }; })()" })).result.value;
const { data } = await send("Page.captureScreenshot", { format: "png", clip: r });
fs.writeFileSync(OUTPNG, Buffer.from(data, "base64"));
console.log("saved", OUTPNG, JSON.stringify(r));
ws.close(); p.kill();
