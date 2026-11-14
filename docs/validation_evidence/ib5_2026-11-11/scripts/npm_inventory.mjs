// IB-5: npm inventory from package-lock.json and installed node_modules (no network).
// Also bundles src/main.tsx with the project's own esbuild (output to the scratchpad only) to learn exactly which
// packages ship in the browser bundle.
//   node npm_inventory.mjs <frontendDir> <out.json> <licenceCopyDir>
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const [fe, outFile, copyDir] = process.argv.slice(2).map((p) => path.resolve(p));
const lock = JSON.parse(fs.readFileSync(path.join(fe, "package-lock.json"), "utf8"));
const rootPkg = JSON.parse(fs.readFileSync(path.join(fe, "package.json"), "utf8"));
const LIC = /^(licen[cs]e|copying|notice|copyright|authors|third[-_]?party)/i;
const COPY = /^\s*(?:Copyright|\(c\)|©)\s.*$/gim;

// which packages ship: bundle the app entry and read the metafile
const req = createRequire(path.join(fe, "package.json"));
const esbuild = req("esbuild");
const meta = (await esbuild.build({
  entryPoints: [path.join(fe, "src", "main.tsx")], bundle: true, write: false, metafile: true, platform: "browser",
  format: "esm", jsx: "automatic", logLevel: "silent", absWorkingDir: fe, outdir: path.join(path.dirname(outFile), "bundle-probe"),
  loader: { ".css": "css", ".woff2": "file", ".woff": "file" },
})).metafile;
const shipped = new Map();   // package dir (relative to frontend) -> bytes of input
for (const [inp, v] of Object.entries(meta.inputs)) {
  const m = /^(node_modules\/(?:@[^/]+\/)?[^/]+(?:\/node_modules\/(?:@[^/]+\/)?[^/]+)*)\//.exec(inp.replace(/\\/g, "/"));
  if (m) shipped.set(m[1], (shipped.get(m[1]) ?? 0) + v.bytes);
}

const rows = [];
for (const [k, v] of Object.entries(lock.packages)) {
  if (!k) continue;
  const dir = path.join(fe, k);
  const name = k.replace(/^.*node_modules\//, "");
  let pj = null;
  try { pj = JSON.parse(fs.readFileSync(path.join(dir, "package.json"), "utf8")); } catch { /* not installed */ }
  const licFiles = fs.existsSync(dir) ? fs.readdirSync(dir).filter((f) => LIC.test(f) && fs.statSync(path.join(dir, f)).isFile()) : [];
  const copyrights = [];
  for (const f of licFiles) {
    const text = fs.readFileSync(path.join(dir, f), "utf8");
    copyrights.push(...(text.match(COPY) ?? []).map((s) => s.trim().slice(0, 200)));
    const dest = path.join(copyDir, k.replace(/node_modules\//g, ""), f);
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.copyFileSync(path.join(dir, f), dest);
  }
  const author = pj?.author ? (typeof pj.author === "string" ? pj.author : [pj.author.name, pj.author.email].filter(Boolean).join(" ")) : null;
  const repo = pj?.repository ? (typeof pj.repository === "string" ? pj.repository : pj.repository.url) : null;
  rows.push({
    path: k, name, version: v.version, installed: !!pj, installed_version: pj?.version ?? null,
    dev: !!v.dev, optional: !!v.optional, lock_license: v.license ?? null,
    package_json_license: pj ? (pj.license ?? (pj.licenses ? JSON.stringify(pj.licenses) : null)) : null,
    licence_files: licFiles, copyright_lines: [...new Set(copyrights)].slice(0, 20),
    author, homepage: pj?.homepage ?? null, repository: repo, resolved: v.resolved ?? null, integrity: v.integrity ?? null,
    direct: !!(rootPkg.dependencies?.[name] || rootPkg.devDependencies?.[name]) && k === `node_modules/${name}`,
    shipped_in_bundle: shipped.has(k), bundled_input_bytes: shipped.get(k) ?? 0,
  });
}
const summary = {
  lockfileVersion: lock.lockfileVersion, packages: rows.length, installed: rows.filter((r) => r.installed).length,
  dev: rows.filter((r) => r.dev).length, runtime: rows.filter((r) => !r.dev).length, shipped: rows.filter((r) => r.shipped_in_bundle).length,
  licence_mismatch: rows.filter((r) => r.installed && r.lock_license && r.package_json_license && r.lock_license !== r.package_json_license).map((r) => r.path),
  version_mismatch: rows.filter((r) => r.installed && r.installed_version !== r.version).map((r) => r.path),
  no_licence_file: rows.filter((r) => r.installed && !r.licence_files.length).map((r) => `${r.name}@${r.version}${r.shipped_in_bundle ? " (shipped)" : ""}`),
  not_installed: rows.filter((r) => !r.installed).map((r) => `${r.name}@${r.version}${r.optional ? " (optional)" : ""}`),
  licences: rows.reduce((a, r) => { const l = r.package_json_license ?? r.lock_license ?? "UNKNOWN"; a[l] = (a[l] ?? 0) + 1; return a; }, {}),
  shipped_licences: rows.filter((r) => r.shipped_in_bundle).reduce((a, r) => { const l = r.package_json_license ?? r.lock_license ?? "UNKNOWN"; a[l] = (a[l] ?? 0) + 1; return a; }, {}),
  bundle_inputs_outside_node_modules: Object.keys(meta.inputs).filter((i) => !i.replace(/\\/g, "/").startsWith("node_modules/")).length,
};
fs.writeFileSync(outFile, JSON.stringify({ summary, packages: rows }, null, 1));
console.log(JSON.stringify(summary, null, 1));
for (const r of rows.filter((r) => r.shipped_in_bundle)) {
  console.log(`SHIPPED ${r.name}@${r.version}  ${r.package_json_license ?? r.lock_license}  files=${r.licence_files.join(",") || "-"}  ${r.copyright_lines[0] ?? ""}`);
}
