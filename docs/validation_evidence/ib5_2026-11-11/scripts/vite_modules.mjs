// Exact list of npm packages whose code is in the production bundle, from Vite/Rollup itself (the real pipeline).
// write:false and an outDir in the scratchpad: frontend/dist is never touched.
//   node vite_modules.mjs <frontendDir> <scratchOutDir> <out.json>
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";

const [fe, scratchOut, outFile] = process.argv.slice(2).map((p) => path.resolve(p));
const req = createRequire(path.join(fe, "package.json"));
const vite = await import(pathToFileURL(path.join(fe, "node_modules", "vite", "dist", "node", "index.js")).href);
const distBefore = fs.readdirSync(path.join(fe, "dist", "assets")).sort().join(",");
const res = await vite.build({
  root: fe, configFile: path.join(fe, "vite.config.ts"), logLevel: "silent",
  build: { write: false, outDir: scratchOut, emptyOutDir: false },
});
const outputs = (Array.isArray(res) ? res : [res]).flatMap((r) => r.output);
const pkgs = {};
const assets = [];
for (const o of outputs) {
  if (o.type === "asset") { assets.push({ fileName: o.fileName, bytes: o.source.length ?? Buffer.byteLength(o.source) }); continue; }
  for (const [id, m] of Object.entries(o.modules)) {
    const p = id.replace(/\\/g, "/");
    const mm = /\/node_modules\/((?:@[^/]+\/)?[^/]+)\//.exec(p);
    const key = mm ? mm[1] : "(project source)";
    pkgs[key] ??= { modules: 0, renderedLength: 0, originalLength: 0 };
    pkgs[key].modules++;
    pkgs[key].renderedLength += m.renderedLength;
    pkgs[key].originalLength += m.originalLength;
  }
}
const distAfter = fs.readdirSync(path.join(fe, "dist", "assets")).sort().join(",");
const shipped = Object.entries(pkgs).filter(([, v]) => v.renderedLength > 0).map(([k]) => k).sort();
const graphOnly = Object.entries(pkgs).filter(([, v]) => v.renderedLength === 0).map(([k]) => k).sort();
fs.writeFileSync(outFile, JSON.stringify({ shipped_with_rendered_code: shipped, in_graph_but_fully_tree_shaken: graphOnly,
  packages: pkgs, assets, dist_untouched: distBefore === distAfter }, null, 1));
console.log("shipped (rendered code > 0):", shipped.length, shipped.join(" "));
console.log("in module graph but tree-shaken to 0 bytes:", graphOnly.join(" ") || "-");
console.log("assets:", assets.map((a) => a.fileName).join(" "));
console.log("frontend/dist untouched:", distBefore === distAfter);
