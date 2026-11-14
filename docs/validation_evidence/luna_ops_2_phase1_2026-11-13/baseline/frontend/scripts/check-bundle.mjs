#!/usr/bin/env node
// U-06 bundle check (manual: `npm run check:bundle` after `vite build`). Not part of the build: no approved or
// documented bundle-size limit exists, and none is invented here (docs/validation_evidence/u06_2026-11-11/README.md).
//
//   node scripts/check-bundle.mjs              report frontend/dist sizes and check the code split
//   node scripts/check-bundle.mjs --json f     also write the measured sizes
//   node scripts/check-bundle.mjs --self-test  prove the checks fail on known-bad input
//
// It checks:
//   1. the code split measured in U-06: three.js (3D view) and OpenLayers (map) load on demand, so their marker strings
//      must not appear in the entry chunk or its modulepreloads;
//   2. a size limit ONLY if scripts/bundle-limit.json exists and states the limit, its source and its approval date
//      ({"initialJsGzipLimit": <bytes>, "source": "...", "approved_date": "YYYY-MM-DD"}). Without it, sizes are reported only.
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DIST = path.join(ROOT, "dist");
const LIMIT_FILE = path.join(ROOT, "scripts", "bundle-limit.json");
// strings that only the named library contributes (checked in the current bundles)
export const MARKERS = {
  "three.js": ["THREE.WebGLRenderer", "WebGLRenderer"],
  OpenLayers: ["ol-viewport", "ol-overlaycontainer"],
};

const sizes = (buf) => ({ raw: buf.length, gzip: zlib.gzipSync(buf, { level: 9 }).length,
  brotli: zlib.brotliCompressSync(buf, { params: { [zlib.constants.BROTLI_PARAM_QUALITY]: 11 } }).length });

export function analyse(distDir) {
  const html = fs.readFileSync(path.join(distDir, "index.html"), "utf8");
  const entry = /<script[^>]+type="module"[^>]+src="\/?([^"]+)"/.exec(html)?.[1];
  if (!entry) throw new Error("no module entry script in dist/index.html");
  const preloads = [...html.matchAll(/<link[^>]+rel="modulepreload"[^>]+href="\/?([^"]+)"/g)].map((m) => m[1]);
  const initial = [entry, ...preloads];
  const assets = fs.readdirSync(path.join(distDir, "assets"));
  const files = assets.map((f) => {
    const buf = fs.readFileSync(path.join(distDir, "assets", f));
    const rel = "assets/" + f;
    return { file: rel, initial: initial.includes(rel), type: path.extname(f).slice(1), ...sizes(buf),
      libraries: f.endsWith(".js") ? Object.entries(MARKERS).filter(([, ms]) => ms.some((m) => buf.includes(m))).map(([k]) => k) : [] };
  });
  const js = files.filter((f) => f.type === "js");
  const sum = (a, k) => a.reduce((s, f) => s + f[k], 0);
  const initialJs = js.filter((f) => f.initial);
  return { entry, preloads, files,
    initialJs: { files: initialJs.length, raw: sum(initialJs, "raw"), gzip: sum(initialJs, "gzip"), brotli: sum(initialJs, "brotli") },
    lazyJs: { files: js.length - initialJs.length, raw: sum(js.filter((f) => !f.initial), "raw"), gzip: sum(js.filter((f) => !f.initial), "gzip") },
    totalJs: { raw: sum(js, "raw"), gzip: sum(js, "gzip") } };
}

export function problems(a, limit) {
  const out = [];
  for (const f of a.files.filter((x) => x.initial))
    for (const lib of f.libraries) out.push(`${lib} is in the initial bundle (${f.file}); it must be loaded on demand`);
  if (limit) {
    if (!Number.isFinite(limit.initialJsGzipLimit) || !limit.source || !/^\d{4}-\d{2}-\d{2}$/.test(limit.approved_date || ""))
      out.push("bundle-limit.json needs initialJsGzipLimit, source and approved_date (YYYY-MM-DD)");
    else if (a.initialJs.gzip > limit.initialJsGzipLimit)
      out.push(`initial JavaScript is ${a.initialJs.gzip} B gzip, over the approved limit of ${limit.initialJsGzipLimit} B (${limit.source}, ${limit.approved_date})`);
  }
  return out;
}

function selfTest() {
  const results = []; const ok = (n, c, d = "") => results.push({ name: n, passed: !!c, detail: d });
  const fake = { files: [{ file: "assets/index.js", initial: true, libraries: ["three.js"] }], initialJs: { gzip: 200000 } };
  ok("fails when three.js is in the initial bundle", problems(fake, null).some((p) => /three\.js/.test(p)));
  const lim = { initialJsGzipLimit: 100000, source: "test", approved_date: "2026-01-01" };
  ok("fails over an approved limit", problems({ files: [], initialJs: { gzip: 120000 } }, lim).length === 1);
  ok("passes under an approved limit", problems({ files: [], initialJs: { gzip: 90000 } }, lim).length === 0);
  ok("refuses a limit without source/approval", problems({ files: [], initialJs: { gzip: 1 } }, { initialJsGzipLimit: 5 }).length === 1);
  ok("no limit file: sizes are not enforced", problems({ files: [], initialJs: { gzip: 9e9 } }, null).length === 0);
  ok("gzip/brotli sizes are computed", sizes(Buffer.from("a".repeat(1000))).gzip < 1000);
  return results;
}

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  if (process.argv.includes("--self-test")) {
    const r = selfTest(); for (const x of r) console.log(`${x.passed ? "PASS" : "FAIL"}  ${x.name}`);
    const failed = r.filter((x) => !x.passed).length; console.log(`check-bundle self-test: ${r.length - failed}/${r.length} passed`); process.exit(failed ? 1 : 0);
  }
  if (!fs.existsSync(path.join(DIST, "index.html"))) { console.log("check-bundle: no dist/ yet (run vite build first); skipped"); process.exit(0); }
  const a = analyse(DIST);
  const limit = fs.existsSync(LIMIT_FILE) ? JSON.parse(fs.readFileSync(LIMIT_FILE, "utf8")) : null;
  const ps = problems(a, limit);
  for (const p of ps) console.log("bundle  " + p);
  const kb = (b) => (b / 1024).toFixed(1) + " KB";
  console.log(`check-bundle: initial JS ${kb(a.initialJs.raw)} (${kb(a.initialJs.gzip)} gzip, ${a.initialJs.files} file(s)); lazy JS ${kb(a.lazyJs.raw)} (${kb(a.lazyJs.gzip)} gzip, ${a.lazyJs.files} file(s)); size limit: ${limit ? "approved file present" : "none approved (sizes reported only)"}; ${ps.length} problem(s)`);
  const j = process.argv.indexOf("--json"); if (j > 0) fs.writeFileSync(process.argv[j + 1], JSON.stringify({ ...a, sizeLimit: limit, problems: ps }, null, 2) + "\n");
  process.exit(ps.length ? 1 : 0);
}
