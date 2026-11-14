// Run the C10 hardcoded-text detector over a source tree (here: the pre-C10 baseline) and summarise per file.
//   node scan_baseline.mjs <checkerPath> <srcDir> <outJson>
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";

const [checker, srcDir, outJson] = process.argv.slice(2).map((p) => path.resolve(p));
const { findHardcoded, ALLOWLIST } = await import(pathToFileURL(checker).href);
const ts = createRequire(checker)("typescript");
const files = [];
const walk = (d) => { for (const e of fs.readdirSync(d, { withFileTypes: true })) {
  const p = path.join(d, e.name);
  if (e.isDirectory()) { if (e.name !== "i18n") walk(p); } else if (/\.(tsx?|mts)$/.test(e.name)) files.push(p);
} };
walk(srcDir);
const perFile = {};
let total = 0, allow = 0;
for (const f of files.sort()) {
  const sf = ts.createSourceFile(f, fs.readFileSync(f, "utf8"), ts.ScriptTarget.ES2021, true, f.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  const relf = "src/" + path.relative(srcDir, f).split(path.sep).join("/");
  const hits = findHardcoded(sf).filter((h) => {
    const a = ALLOWLIST.some((x) => x.file === relf && x.text === h.text);
    if (a) allow++;
    return !a;
  });
  total += hits.length;
  perFile[relf] = hits.length;
  if (hits.length) perFile[relf + " (examples)"] = hits.slice(0, 3).map((h) => `${h.line}: ${h.why}: ${h.text.slice(0, 60)}`);
}
const out = { srcDir, files: files.length, hardcodedFindings: total, allowListed: allow, perFile };
fs.writeFileSync(outJson, JSON.stringify(out, null, 2) + "\n");
console.log(JSON.stringify({ files: out.files, hardcodedFindings: total, allowListed: allow,
  perFile: Object.fromEntries(Object.entries(perFile).filter(([k]) => !k.includes("examples"))) }, null, 1));
