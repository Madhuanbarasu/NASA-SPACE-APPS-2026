#!/usr/bin/env node
// C10 string check: the interface text lives in src/i18n/en.ts and components only reference it.
//
//   node scripts/check-strings.mjs                 check src/ (exit 1 on any problem)
//   node scripts/check-strings.mjs --json out.json also write a machine-readable report
//   node scripts/check-strings.mjs --self-test     prove that every detector fires on known-bad input
//
// Uses only the TypeScript compiler already installed as a devDependency (no new packages). It reports:
//   unknown-key   an S.* reference (directly or through an alias such as `const T = S.site`) to a key that
//                 does not exist in the dictionary (TypeScript also rejects these at compile time);
//   unused-key    a dictionary entry that no source file references;
//   hardcoded     user-facing English left in a component or library file (JSX text, accessible names,
//                 titles, placeholders, rendered string literals, UI-named object properties, error
//                 messages, state setters, returned text), unless allow-listed below with a reason;
//   dictionary    malformed dictionary entries (empty strings, unbalanced {placeholders});
//   html          index.html <title>/lang out of step with the dictionary;
//   allowlist     an allow-list entry that no longer matches anything (stale exceptions are errors).
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import ts from "typescript";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SRC = path.join(ROOT, "src");
const I18N = path.join(SRC, "i18n");
const DICT_FILE = path.join(I18N, "en.ts");
const INDEX_FILE = path.join(I18N, "index.ts");
const norm = (p) => path.resolve(p).split(path.sep).join("/");
const rel = (p) => path.relative(ROOT, p).split(path.sep).join("/");

// Literals that look like text but are not interface strings. Each needs a reason and must still match.
export const ALLOWLIST = [
  { file: "src/components/ResultLabels.tsx", text: "Validated",
    reason: "prefix of the API's validation status word, compared (not displayed) to pick the chip style" },
  { file: "src/components/ResultLabels.tsx", text: "Synthetic",
    reason: "prefix of the API's validation status word, compared (not displayed) to pick the chip style" },
  { file: "src/components/CompareView.tsx", text: "Validated",
    reason: "prefix of the API's validation status word, compared (not displayed) to count a cell's validated labels" },
  { file: "src/components/MissionView.tsx", text: "Validated",
    reason: "prefix of the API's validation status word, compared (not displayed) to count validated labels on the dashboard" },
  { file: "src/components/MapView.tsx", text: "12px 'Archivo Variable', sans-serif",
    reason: "CSS font shorthand for OpenLayers labels (font family name, not text)" },
  { file: "src/components/CompareView.tsx", text: "transparent",
    reason: "CSS colour keyword returned by the matrix shading function" },
  { file: "src/state/store.tsx", text: "useStore outside provider",
    reason: "developer invariant (programming error), never shown in the interface" },
];

// attributes whose value is read or shown to the user
const UI_ATTRS = new Set(["aria-label", "aria-description", "aria-roledescription", "aria-valuetext", "aria-placeholder",
  "title", "placeholder", "alt", "label"]);
// object-literal properties whose value is interface text in this code base
const UI_KEYS = new Set(["label", "text", "title", "t", "name", "message", "note", "reason", "error", "placeholder",
  "caption", "heading", "description", "tooltip"]);
const COMPARISON = new Set([ts.SyntaxKind.EqualsEqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsEqualsToken,
  ts.SyntaxKind.EqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsToken]);
const ARRAY_METHODS = new Set(["map", "forEach", "filter", "find", "some", "every", "reduce", "slice", "join",
  "includes", "indexOf", "length", "entries", "keys", "values", "flatMap", "at"]);
const LETTERS = /[A-Za-z]/;
const WORD = /[A-Za-z]{2,}/;
// CSS functions, URLs and API paths are technical values, not text
const TECHNICAL = /^(rgba?|hsla?|url|var|calc|repeating-linear-gradient|linear-gradient|radial-gradient)\(|^\/|^https?:\/\/|^data:/;
const PROSE = /[A-Za-z]{2,}\s+[A-Za-z]|^[A-Z][a-z]+/;

// ---------------------------------------------------------------- dictionary

export async function loadDictionary(file = DICT_FILE) {
  const src = fs.readFileSync(file, "utf8");
  const js = ts.transpileModule(src, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2021 } }).outputText;
  const mod = await import("data:text/javascript;base64," + Buffer.from(js).toString("base64"));
  if (!mod.en || typeof mod.en !== "object") throw new Error(`${rel(file)} must export the dictionary as \`en\``);
  return mod.en;
}

/** Leaf paths ("a.b.0.c") of the dictionary: strings and functions. */
export function leafPaths(node, prefix = []) {
  if (typeof node === "string" || typeof node === "function") return [prefix.join(".")];
  return Object.keys(node).flatMap((k) => leafPaths(node[k], [...prefix, k]));
}

function dictionaryProblems(dict) {
  const out = [];
  const walk = (node, p) => {
    if (typeof node === "string") {
      if (node.length === 0) out.push({ kind: "dictionary", key: p.join("."), message: "empty string" });
      const opens = (node.match(/\{/g) || []).length, closes = (node.match(/\}/g) || []).length;
      const ph = (node.match(/\{\w+\}/g) || []).length;
      if (opens !== closes || opens !== ph) out.push({ kind: "dictionary", key: p.join("."), message: "unbalanced or malformed {placeholder}" });
    } else if (typeof node === "function") {
      // nothing to check without arguments; TypeScript checks the call sites
    } else if (node && typeof node === "object") {
      if (Object.keys(node).length === 0) out.push({ kind: "dictionary", key: p.join("."), message: "empty section" });
      for (const k of Object.keys(node)) walk(node[k], [...p, k]);
    } else {
      out.push({ kind: "dictionary", key: p.join("."), message: `unsupported value type ${typeof node}` });
    }
  };
  walk(dict, []);
  return out;
}

/** Follow `segments` from `path0` into the dictionary. Returns { node, path, stop } or { error }. */
export function resolveSegments(dict, path0, segments) {
  let node = dict;
  for (const k of path0) node = node?.[k];
  const pathOut = [...path0];
  for (const seg of segments) {
    if (seg === null) return { node, path: pathOut, stop: "dynamic" };            // S.x[expr]: whole subtree used
    if (typeof node === "string") return { node, path: pathOut, stop: "string-method" };
    if (typeof node === "function") return { node, path: pathOut, stop: "call" };
    if (Array.isArray(node) && ARRAY_METHODS.has(seg)) return { node, path: pathOut, stop: "array-method" };
    if (node == null || !Object.prototype.hasOwnProperty.call(node, seg)) {
      return { error: `unknown key '${[...pathOut, seg].join(".")}'` };
    }
    node = node[seg];
    pathOut.push(seg);
  }
  return { node, path: pathOut, stop: "end" };
}

// ---------------------------------------------------------------- program and key usage

function createProgram(extraFiles = {}) {
  const cfgPath = path.join(ROOT, "tsconfig.json");
  const host = ts.createCompilerHost({});
  const parsed = ts.getParsedCommandLineOfConfigFile(cfgPath, {}, { ...ts.sys, onUnRecoverableConfigFileDiagnostic: (d) => {
    throw new Error(ts.flattenDiagnosticMessageText(d.messageText, "\n"));
  } });
  const options = parsed.options;
  const h = ts.createCompilerHost(options);
  const virtual = new Map(Object.entries(extraFiles).map(([k, v]) => [norm(k), v]));
  const getSourceFile = h.getSourceFile.bind(h);
  h.getSourceFile = (f, lang, ...rest) => virtual.has(norm(f))
    ? ts.createSourceFile(f, virtual.get(norm(f)), lang, true, f.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
    : getSourceFile(f, lang, ...rest);
  const fileExists = h.fileExists.bind(h);
  h.fileExists = (f) => virtual.has(norm(f)) || fileExists(f);
  const readFile = h.readFile.bind(h);
  h.readFile = (f) => (virtual.has(norm(f)) ? virtual.get(norm(f)) : readFile(f));
  void host;
  return ts.createProgram([...parsed.fileNames, ...virtual.keys()], options, h);
}

const isInType = (n) => { for (let p = n.parent; p; p = p.parent) { if (ts.isTypeNode(p)) return true; if (ts.isStatement(p)) return false; } return false; };

function symbolOf(checker, id) {
  let s = checker.getSymbolAtLocation(id);
  if (s && s.flags & ts.SymbolFlags.Alias) s = checker.getAliasedSymbol(s);
  return s;
}

/** Collect key usage from the program. Returns { used:Set, problems:[] }. */
function keyUsage(program, dict) {
  const checker = program.getTypeChecker();
  const declPath = new Map();   // VariableDeclaration node (root or alias) -> dictionary path
  const pathOf = (s) => { for (const d of s?.declarations ?? []) if (declPath.has(d)) return declPath.get(d); return undefined; };
  const problems = [];
  const used = new Set();
  const files = program.getSourceFiles().filter((sf) => norm(sf.fileName).startsWith(norm(SRC) + "/")
    && norm(sf.fileName) !== norm(DICT_FILE));

  // the dictionary roots: `en` (en.ts) and `S` (index.ts)
  for (const sf of program.getSourceFiles()) {
    const f = norm(sf.fileName);
    if (f !== norm(DICT_FILE) && f !== norm(INDEX_FILE)) continue;
    const want = f === norm(DICT_FILE) ? "en" : "S";
    sf.forEachChild(function visit(n) {
      if (ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.name.text === want) {
        declPath.set(n, []);
      }
      n.forEachChild(visit);
    });
  }

  // chain of property/element accesses above an identifier
  const chainFrom = (id) => {
    const segs = [];
    let node = id;
    for (;;) {
      const p = node.parent;
      if (p && ts.isPropertyAccessExpression(p) && p.expression === node) { segs.push(p.name.text); node = p; continue; }
      if (p && ts.isElementAccessExpression(p) && p.expression === node) {
        const a = p.argumentExpression;
        segs.push(ts.isStringLiteralLike(a) || ts.isNumericLiteral(a) ? a.text : null);
        node = p;
        if (segs[segs.length - 1] === null) break;
        continue;
      }
      break;
    }
    return { segs, top: node };
  };

  // aliases: const X = <root>.a.b  (iterate until stable so aliases of aliases resolve)
  const aliasDecls = new Set();   // declaration name identifiers of object aliases (and roots)
  for (const d of declPath.keys()) aliasDecls.add(d.name);
  for (let changed = true; changed;) {
    changed = false;
    for (const sf of files) {
      sf.forEachChild(function visit(n) {
        if (ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.initializer && !aliasDecls.has(n.name)) {
          let e = n.initializer;
          while (ts.isAsExpression(e) || ts.isParenthesizedExpression(e) || ts.isSatisfiesExpression?.(e)) e = e.expression;
          let base = e;
          while (ts.isPropertyAccessExpression(base) || ts.isElementAccessExpression(base)) base = base.expression;
          if (ts.isIdentifier(base)) {
            const bp = pathOf(symbolOf(checker, base));
            if (bp) {
              const { segs, top } = chainFrom(base);
              if (top === e && !segs.includes(null)) {
                const r = resolveSegments(dict, bp, segs);
                if (r.error) problems.push({ kind: "unknown-key", file: rel(sf.fileName), line: line(sf, n), message: r.error });
                else if (r.stop === "end" && r.node && typeof r.node === "object") {
                  // an object alias (const T = S.site); a typed copy such as Record<string,string> = S.rules is a use
                  if (n.type) markSubtree(dict, r.path, used);
                  else { declPath.set(n, r.path); aliasDecls.add(n.name); changed = true; }
                }
              }
            }
          }
        }
        n.forEachChild(visit);
      });
    }
  }

  // usages
  for (const sf of files) {
    sf.forEachChild(function visit(n) {
      if (ts.isIdentifier(n) && !aliasDecls.has(n) && !isInType(n)) {
        const p = n.parent;
        const isDeclName = (ts.isVariableDeclaration(p) || ts.isParameter(p) || ts.isBindingElement(p)
          || ts.isPropertyAssignment(p) || ts.isFunctionDeclaration(p) || ts.isPropertySignature(p)) && p.name === n;
        const isPropName = ts.isPropertyAccessExpression(p) && p.name === n;
        const isImport = ts.isImportSpecifier(p) || ts.isImportClause(p) || ts.isNamespaceImport(p) || ts.isExportSpecifier(p);
        if (!isDeclName && !isPropName && !isImport) {
          const sp = pathOf(symbolOf(checker, n));
          if (sp) {
            const { segs, top } = chainFrom(n);
            // skip the initializer of an object alias or of the root itself (S = en): their uses are counted instead
            const decl = top.parent;
            const isAliasInit = decl && ts.isVariableDeclaration(decl) && decl.initializer === top && aliasDecls.has(decl.name);
            const r = resolveSegments(dict, sp, segs);
            if (r.error) problems.push({ kind: "unknown-key", file: rel(sf.fileName), line: line(sf, n), message: r.error });
            else if (!isAliasInit) markSubtree(dict, r.path, used);
          }
        }
      }
      n.forEachChild(visit);
    });
  }
  return { used, problems, files: files.map((f) => rel(f.fileName)) };
}

function markSubtree(dict, p, used) {
  let node = dict;
  for (const k of p) node = node[k];
  for (const leaf of leafPaths(node, p)) used.add(leaf);
}

const line = (sf, n) => sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1;

// ---------------------------------------------------------------- hardcoded text

function literalText(n) {
  if (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n)) return n.text;
  if (ts.isTemplateExpression(n)) return [n.head.text, ...n.templateSpans.map((s) => s.literal.text)].join("\u0000");
  return null;
}

/** Why a literal is user-facing text, or null. Purely syntactic. */
function uiReason(n) {
  const text = literalText(n);
  if (text == null || !LETTERS.test(text)) return null;
  if (TECHNICAL.test(text)) return null;
  const p = n.parent;
  if (ts.isImportDeclaration(p) || ts.isExportDeclaration(p) || ts.isExternalModuleReference(p)) return null;
  if (ts.isLiteralTypeNode(p) || isInType(n)) return null;
  if (ts.isPropertyAssignment(p) && p.name === n) return null;                       // object key
  if (ts.isElementAccessExpression(p) && p.argumentExpression === n) return null;     // obj["key"]
  if (ts.isBinaryExpression(p) && COMPARISON.has(p.operatorToken.kind)) return null;  // x === "sun"
  if (ts.isCaseClause(p)) return null;
  const prose = () => (PROSE.test(text.replace(/\u0000/g, " ")) ? "prose-like string literal" : null);
  // Walk up through value-preserving expressions (a ? "x" : "y", a || "x", ("x"), "x" as T) to the place the
  // value lands: a JSX attribute or child, a call argument, an object property, a return, or a declaration.
  for (let c = n, q = p; q; c = q, q = q.parent) {
    if (ts.isConditionalExpression(q) && q.condition !== c || ts.isParenthesizedExpression(q) || ts.isAsExpression(q)
      || ts.isNonNullExpression(q) || ts.isBinaryExpression(q) && !COMPARISON.has(q.operatorToken.kind)) continue;
    if (ts.isJsxAttribute(q)) {
      const name = q.name.getText();
      return UI_ATTRS.has(name) ? `literal in JSX attribute ${name}` : null;
    }
    if (ts.isJsxExpression(q)) {
      if (ts.isJsxElement(q.parent) || ts.isJsxFragment(q.parent)) return "string rendered as JSX content";
      continue;   // attribute value: the JsxAttribute above decides
    }
    if (ts.isCallExpression(q) || ts.isNewExpression(q)) {
      if (c === q.expression) return prose();
      const callee = q.expression.getText();
      if (/^Error$/.test(callee)) return "error message";
      // React state setters (setNote, setErr); DOM APIs such as setAttribute/setProperty take names, not text
      if (ts.isCallExpression(q) && /(^|\.)set(?!Attribute|AttributeNS|Property|Item|Timeout|Interval)[A-Z]\w*$/.test(callee)) return `argument of state setter ${callee}`;
      return prose();   // any other argument (dispatch types, projection codes, method keys): text only if prose
    }
    if (ts.isPropertyAssignment(q)) {
      if (q.initializer === c && ts.isIdentifier(q.name) && UI_KEYS.has(q.name.text)) return `value of UI property '${q.name.text}'`;
      return prose();
    }
    if (ts.isReturnStatement(q) || ts.isArrowFunction(q) && q.body === c) return WORD.test(text) ? "returned text" : null;
    break;
  }
  return prose();
}

export function findHardcoded(sf) {
  const out = [];
  const visit = (n) => {
    if (ts.isJsxText(n)) {
      const t = n.text.trim();
      if (LETTERS.test(t)) out.push({ line: line(sf, n), text: t, why: "JSX text" });
    } else if (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n) || ts.isTemplateExpression(n)) {
      const why = uiReason(n);
      if (why) out.push({ line: line(sf, n), text: literalText(n).replace(/\u0000/g, "${…}"), why });
      if (ts.isTemplateExpression(n)) n.templateSpans.forEach((s) => visit(s.expression));
      return;
    }
    n.forEachChild(visit);
  };
  visit(sf);
  return out;
}

function hardcodedProblems(program) {
  const problems = [];
  const allowUsed = new Set();
  for (const sf of program.getSourceFiles()) {
    const f = norm(sf.fileName);
    if (!f.startsWith(norm(SRC) + "/") || f.startsWith(norm(I18N) + "/")) continue;
    // src/data/*.json are sourced datasets (e.g. the reference mission sites with their citations), not interface text
    if (f.startsWith(norm(path.join(SRC, "data")) + "/") && f.endsWith(".json")) continue;
    for (const h of findHardcoded(sf)) {
      const ai = ALLOWLIST.findIndex((a) => a.file === rel(sf.fileName) && a.text === h.text);
      if (ai >= 0) { allowUsed.add(ai); continue; }
      problems.push({ kind: "hardcoded", file: rel(sf.fileName), line: h.line, message: `${h.why}: ${JSON.stringify(h.text)}` });
    }
  }
  ALLOWLIST.forEach((a, i) => {
    if (!allowUsed.has(i)) problems.push({ kind: "allowlist", file: a.file, message: `stale allow-list entry ${JSON.stringify(a.text)}` });
  });
  return problems;
}

function htmlProblems(dict) {
  const html = fs.readFileSync(path.join(ROOT, "index.html"), "utf8");
  const out = [];
  const title = /<title>([^<]*)<\/title>/.exec(html)?.[1];
  if (title !== dict.app.documentTitle) out.push({ kind: "html", file: "index.html", message: `<title> ${JSON.stringify(title)} differs from S.app.documentTitle ${JSON.stringify(dict.app.documentTitle)}` });
  if (!/<html[^>]*\slang="en"/.test(html)) out.push({ kind: "html", file: "index.html", message: "<html lang=\"en\"> is missing" });
  return out;
}

// ---------------------------------------------------------------- main

export async function check() {
  const dict = await loadDictionary();
  const program = createProgram();
  const leaves = leafPaths(dict);
  const usage = keyUsage(program, dict);
  const unused = leaves.filter((k) => !usage.used.has(k));
  const problems = [
    ...dictionaryProblems(dict),
    ...usage.problems,
    ...unused.map((k) => ({ kind: "unused-key", key: k, message: `dictionary key '${k}' is never referenced` })),
    ...hardcodedProblems(program),
    ...htmlProblems(dict),
  ];
  return { dict, leaves, used: usage.used, files: usage.files, problems };
}

async function selfTest() {
  const results = [];
  const ok = (name, cond, detail = "") => { results.push({ name, passed: !!cond, detail }); };
  const dict = await loadDictionary();

  // 1. hardcoded-text detectors fire on known-bad input and stay quiet on technical literals
  const bad = `
    import { x } from "./not-text-but-a-path";
    export function A({ open }: { open: boolean }) {
      const [n, setNote] = useState("");
      setNote("Loading tiles.");
      if (!open) throw new Error("Something failed");
      const opts = [{ v: "any", t: "Any part" }];
      return <div className="hint warn" style={{ background: "repeating-linear-gradient(45deg,#000 0 2px)" }}
                  aria-label="Hard coded label" title="Hard title" data-x="not checked">
        Hello world
        <input placeholder="e.g. 5" />
        {open ? "Hide" : "Show"}{n === "sun" ? 1 : 2}{opts.length}
      </div>;
    }
    function f(v: number) { if (v < 0) return "passed"; return "Plain prose here"; }
    const g = () => dispatch({ type: "cursorMove", cursor: 0 });
    const h = (x: number) => proj4("LUNAOPS:GEO", "LUNAOPS:SPS", [x, 0]);
    const st = new Style({ text: new Text({ text: f.get("featureName"), fill: new Fill({ color: "#e7ecf1" }) }) });
    const u = (c: number[]) => \`/api/tiles/\${c[0]}.png\`;
    el.setAttribute("aria-description", S.map.zoomIn);`;
  const sf = ts.createSourceFile("fixture.tsx", bad, ts.ScriptTarget.ES2021, true, ts.ScriptKind.TSX);
  const found = findHardcoded(sf).map((h) => `${h.why}|${h.text}`);
  const expect = ["argument of state setter setNote|Loading tiles.", "error message|Something failed", "value of UI property 't'|Any part",
    "literal in JSX attribute aria-label|Hard coded label", "literal in JSX attribute title|Hard title", "JSX text|Hello world",
    "literal in JSX attribute placeholder|e.g. 5", "string rendered as JSX content|Hide", "string rendered as JSX content|Show",
    "returned text|passed", "returned text|Plain prose here"];
  for (const e of expect) ok(`detects ${e}`, found.includes(e), found.join("; "));
  for (const quiet of ["./not-text-but-a-path", "hint warn", "repeating-linear-gradient(45deg,#000 0 2px)", "not checked", "sun", "any",
    "cursorMove", "LUNAOPS:GEO", "LUNAOPS:SPS", "featureName", "#e7ecf1", "/api/tiles/${…}.png", "aria-description"]) {
    ok(`ignores technical literal ${JSON.stringify(quiet)}`, !found.some((f) => f.endsWith("|" + quiet)), found.join("; "));
  }
  ok("finds exactly the expected set", found.length === expect.length, found.join("; "));

  // 2. key resolution against the real dictionary
  ok("resolves an existing key", resolveSegments(dict, [], ["site", "customSite"]).stop === "end");
  ok("stops at a function call", resolveSegments(dict, [], ["site", "coords"]).stop === "end");
  ok("rejects a missing key", /unknown key 'site.noSuchKey'/.test(resolveSegments(dict, [], ["site", "noSuchKey"]).error ?? ""));
  ok("rejects a misspelt section", /unknown key 'sitee'/.test(resolveSegments(dict, [], ["sitee", "customSite"]).error ?? ""));
  ok("array method marks the array used", resolveSegments(dict, [], ["guide", "glossary", "map"]).stop === "array-method");
  ok("string method is not a key", resolveSegments(dict, [], ["rules", "any", "toLowerCase"]).stop === "string-method");
  ok("dynamic index uses the subtree", resolveSegments(dict, [], ["quantities", null]).stop === "dynamic");

  // 3. end to end on a virtual component: unknown key through S and through an alias, and a hardcoded string
  const vfile = path.join(SRC, "components", "__C10SelfTest__.tsx");
  const prog = createProgram({ [vfile]: `import { S } from "../i18n";\nconst T = S.site;\n` +
    `export const a = S.site.noSuchKey;\nexport const b = T.alsoMissing;\nexport const c = <p>Left in English</p>;\n` });
  const usage = keyUsage(prog, dict);
  const vf = rel(vfile);
  ok("program check: unknown key via S", usage.problems.some((p) => p.file === vf && /site\.noSuchKey/.test(p.message)), JSON.stringify(usage.problems));
  ok("program check: unknown key via alias", usage.problems.some((p) => p.file === vf && /site\.alsoMissing/.test(p.message)), JSON.stringify(usage.problems));
  const hc = hardcodedProblems(prog).filter((p) => p.file === vf);
  ok("program check: hardcoded JSX text", hc.some((p) => /Left in English/.test(p.message)), JSON.stringify(hc));

  // 4. dictionary validation
  ok("dictionary check: malformed placeholder", dictionaryProblems({ a: "Run {cmd now" }).some((p) => p.kind === "dictionary"));
  ok("dictionary check: empty string", dictionaryProblems({ a: "" }).some((p) => p.kind === "dictionary"));
  ok("dictionary check: real dictionary is clean", dictionaryProblems(dict).length === 0, JSON.stringify(dictionaryProblems(dict)));
  return results;
}

const args = process.argv.slice(2);
const jsonAt = args.indexOf("--json");
const jsonOut = jsonAt >= 0 ? args[jsonAt + 1] : null;
if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  if (args.includes("--self-test")) {
    const results = await selfTest();
    for (const r of results) console.log(`${r.passed ? "PASS" : "FAIL"}  ${r.name}${r.passed ? "" : "  -> " + r.detail}`);
    const failed = results.filter((r) => !r.passed).length;
    console.log(`check-strings self-test: ${results.length - failed}/${results.length} passed`);
    if (jsonOut) fs.writeFileSync(jsonOut, JSON.stringify({ selfTest: results }, null, 2) + "\n");
    process.exit(failed ? 1 : 0);
  }
  const { leaves, used, files, problems } = await check();
  for (const p of problems) console.log(`${p.kind.padEnd(11)} ${p.file ? p.file + (p.line ? ":" + p.line : "") + "  " : ""}${p.message}`);
  const summary = { dictionary: rel(DICT_FILE), keys: leaves.length, keysReferenced: leaves.filter((k) => used.has(k)).length,
    filesScanned: files.length, allowlist: ALLOWLIST, problems: problems.length };
  console.log(`check-strings: ${summary.keys} keys, ${summary.keysReferenced} referenced, ${summary.filesScanned} files scanned, ` +
    `${ALLOWLIST.length} allow-listed literals, ${problems.length} problem(s)`);
  if (jsonOut) fs.writeFileSync(jsonOut, JSON.stringify({ ...summary, files, problemList: problems }, null, 2) + "\n");
  process.exit(problems.length ? 1 : 0);
}
