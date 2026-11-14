// Build summary.json (before vs after, per profile) from the raw U-06 result files. Read-only over raw/.
//   node summarize.mjs
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
const HERE = path.dirname(fileURLToPath(import.meta.url));
const raw = (f) => JSON.parse(fs.readFileSync(path.join(HERE, "raw", f), "utf8"));
const med = (a) => { const s = a.filter((x) => x != null && isFinite(x)).sort((x, y) => x - y); if (!s.length) return null; const m = Math.floor(s.length / 2); return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
const r1 = (x) => (x == null ? null : Math.round(x * 10) / 10);
const LOAD = ["fcp", "lcp", "appReadyMs", "domContentLoaded", "tbt", "longTasks", "longestTask", "scriptMs", "heapMB", "domNodes", "cls"];
const loads = (runs) => ({ n: runs.length, ...Object.fromEntries(LOAD.map((k) => [k, r1(med(runs.map((r) => r[k])))])),
  min_fcp: Math.min(...runs.map((r) => r.fcp)), max_fcp: Math.max(...runs.map((r) => r.fcp)), jsKB: runs[0].transfer.jsKB, totalKB: runs[0].transfer.totalKB });
const sets = { before: "before-clean", after: "variant-noprefetch" };
const out = { generated: new Date().toISOString(), note: "before = U-04 production build (index-gL-Ccy3m.js); after = final U-06 build (index-kvDT7UBF.js + lazy MapView/Terrain3D chunks); zoom-0 (and, after, zoom-1 1/0/1) basemap tiles blocked in both so the pathological backend tile render does not load the server; medians", profiles: {} };
for (const p of ["native", "cpu4x", "cpu4x-net10mbps"]) {
  const e = {};
  for (const [k, label] of Object.entries(sets)) {
    const r = raw(`perf-${label}-${p}.json`);
    e[k] = { complete: r.complete, cold: loads(r.coldLoad.runs), warm: loads(r.warmLoad.runs), interactions: r.interactions ?? null, memory: r.memory ?? null, blocked: r.plan.blockedUrls };
  }
  out.profiles[p] = e;
}
out.bundle = { before: raw("bundle_baseline_build.json").initialJs, after: raw("bundle_final_build.json").initialJs, afterLazy: raw("bundle_final_build.json").lazyJs,
  afterFiles: raw("bundle_final_build.json").files.filter((f) => f.type === "js").map((f) => ({ file: f.file, initial: f.initial, raw: f.raw, gzip: f.gzip, brotli: f.brotli, libraries: f.libraries })) };
fs.writeFileSync(path.join(HERE, "summary.json"), JSON.stringify(out, null, 1));
const row = (p, k) => { const b = out.profiles[p].before[k], a = out.profiles[p].after[k];
  return `${p.padEnd(16)} ${k}: FCP ${b.fcp} -> ${a.fcp} | ready ${b.appReadyMs} -> ${a.appReadyMs} | DCL ${b.domContentLoaded} -> ${a.domContentLoaded} | TBT ${b.tbt} -> ${a.tbt} | longest ${b.longestTask} -> ${a.longestTask} | script ${b.scriptMs} -> ${a.scriptMs} | heap ${b.heapMB} -> ${a.heapMB} | JS ${b.jsKB} -> ${a.jsKB} KB`; };
for (const p of Object.keys(out.profiles)) for (const k of ["cold", "warm"]) console.log(row(p, k));
for (const p of ["native", "cpu4x"]) { const b = out.profiles[p].before.interactions, a = out.profiles[p].after.interactions;
  for (const k of ["analysisToResultMs", "analysisTo3DDataMs", "dataToResultMs", "compareToMatrixMs", "cellToResultMs", "modeToPublicMs", "metricSwitchMs"]) console.log(p, k, b[k], "->", a[k]);
  console.log(p, "tabs", JSON.stringify(b.tabs), "->", JSON.stringify(a.tabs));
  console.log(p, "cursorStep", JSON.stringify(b.cursorStep), "->", JSON.stringify(a.cursorStep));
  console.log(p, "playback", JSON.stringify(b.playback), "\n   ->", JSON.stringify(a.playback));
  console.log(p, "playbackTablesOpen", JSON.stringify(b.playbackTablesOpen), "\n   ->", JSON.stringify(a.playbackTablesOpen));
  console.log(p, "rotate3D", JSON.stringify(b.rotate3D), "->", JSON.stringify(a.rotate3D), "heapAfterWorkflow", b.heapAfterWorkflowMB, "->", a.heapAfterWorkflowMB); }
console.log("memory before", JSON.stringify(out.profiles.native.before.memory)); console.log("memory after", JSON.stringify(out.profiles.native.after.memory));
console.log("bundle", JSON.stringify(out.bundle.before), "->", JSON.stringify(out.bundle.after), "lazy", JSON.stringify(out.bundle.afterLazy));
