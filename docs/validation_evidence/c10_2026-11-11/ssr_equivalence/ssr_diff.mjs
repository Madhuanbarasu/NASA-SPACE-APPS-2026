// Bundle harness.tsx against two source trees with the frontend's own esbuild, render, and compare.
//   node ssr_diff.mjs <frontendDir> <baselineSrc> <newSrc> <outDir>
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";

const [frontend, baseSrc, newSrc, outDir] = process.argv.slice(2).map((p) => path.resolve(p));
const require = createRequire(path.join(frontend, "package.json"));
const esbuild = require("esbuild");
const here = path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
fs.mkdirSync(outDir, { recursive: true });
const mockStore = path.join(outDir, "mock-store.js");
fs.writeFileSync(mockStore, "export const useStore = () => globalThis.__MOCK_STORE__;\n");

async function render(label, src) {
  const outfile = path.join(outDir, `bundle-${label}.mjs`);
  await esbuild.build({
    entryPoints: [path.join(here, "harness.tsx")], bundle: true, platform: "node", format: "esm", outfile,
    jsx: "automatic", logLevel: "error", nodePaths: [path.join(frontend, "node_modules")],
    loader: { ".css": "empty" }, define: { "process.env.NODE_ENV": '"production"' },
    banner: { js: "import { createRequire as __cr } from 'module'; const require = __cr(import.meta.url);" },
    plugins: [{ name: "alias", setup(b) {
      b.onResolve({ filter: /^@src\// }, (a) => {
        const base = path.join(src, a.path.slice(5));
        const hit = [".tsx", ".ts"].map((e) => base + e).find((f) => fs.existsSync(f));
        if (!hit) throw new Error("not found: " + base);
        return { path: hit };
      });
      b.onResolve({ filter: /[\\/]state[\\/]store$/ }, () => ({ path: mockStore }));
    } }],
    resolveExtensions: [".tsx", ".ts", ".mjs", ".js"],
  });
  // global shims some browser libraries probe at import time
  globalThis.window ??= globalThis; globalThis.navigator ??= { userAgent: "node" };
  let out = "";
  const write = process.stdout.write.bind(process.stdout);
  process.stdout.write = (s) => { out += s; return true; };
  try { await import(pathToFileURL(outfile).href + "?" + label); } finally { process.stdout.write = write; }
  const parsed = JSON.parse(out);
  fs.writeFileSync(path.join(outDir, `render-${label}.json`), JSON.stringify(parsed, null, 1));
  return parsed;
}

const require2 = require; void require2;
const a = await render("baseline", baseSrc);
const b = await render("c10", newSrc);
const names = [...new Set([...Object.keys(a), ...Object.keys(b)])];
const diffs = [];
let errors = 0;
for (const n of names) {
  if (String(a[n]).startsWith("RENDER ERROR") || String(b[n]).startsWith("RENDER ERROR")) errors++;
  if (a[n] !== b[n]) {
    let i = 0; const x = String(a[n]), y = String(b[n]);
    while (i < x.length && x[i] === y[i]) i++;
    diffs.push({ scenario: n, at: i, baseline: x.slice(Math.max(0, i - 80), i + 120), c10: y.slice(Math.max(0, i - 80), i + 120) });
  }
}
const bytes = names.reduce((s, n) => s + String(b[n] ?? "").length, 0);
const summary = { scenarios: names.length, identical: names.length - diffs.length, different: diffs.length, renderErrors: errors,
  totalMarkupChars: bytes, diffs };
fs.writeFileSync(path.join(outDir, "ssr_diff_summary.json"), JSON.stringify(summary, null, 2));
console.log(JSON.stringify({ ...summary, diffs: diffs.slice(0, 5) }, null, 2));
process.exit(diffs.length || errors ? 1 : 0);
