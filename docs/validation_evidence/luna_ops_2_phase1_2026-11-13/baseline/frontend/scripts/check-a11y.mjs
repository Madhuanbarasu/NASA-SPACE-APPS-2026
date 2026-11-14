#!/usr/bin/env node
// U-04 regression check (WCAG 2.2 AA): static rules over src/ and the colour tokens in src/styles/app.css.
//
//   node scripts/check-a11y.mjs               check (exit 1 on any problem)
//   node scripts/check-a11y.mjs --self-test   prove every rule fires on known-bad input
//   node scripts/check-a11y.mjs --json f      also write a report
//
// Uses only the TypeScript compiler already installed. The live browser audit (scripts/a11y-live-audit.mjs) covers
// what static rules cannot (rendered contrast, focus visibility, reflow, target size, the accessibility tree).
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import ts from "typescript";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SRC = path.join(ROOT, "src");
const CSS = path.join(SRC, "styles", "app.css");
const rel = (p) => path.relative(ROOT, p).split(path.sep).join("/");

// ---------------------------------------------------------------- colour tokens
// Text tokens must reach 4.5:1 on every surface they are used on (1.4.3, small text assumed); boundaries and state
// indicators of controls must reach 3:1 against the colours next to them (1.4.11).
export const TEXT_PAIRS = [
  ...["text", "muted", "faint", "sun", "earth", "both", "valid", "alert"].flatMap((fg) =>
    ["night", "panel", "panel-raised"].map((bg) => ({ fg, bg, min: 4.5, why: `--${fg} text on --${bg}` }))),
  { fg: "#1b1406", bg: "sun", min: 4.5, why: "run button label on --sun" },
];
export const NONTEXT_PAIRS = [
  { fg: "control-edge", bg: "night", min: 3, why: "text-input/select border against the page (1.4.11)" },
  { fg: "control-edge", bg: "panel", min: 3, why: "text-input/select border against its own fill (1.4.11)" },
  { fg: "focus", bg: "night", min: 3, why: "focus ring on the page" },
  { fg: "focus", bg: "panel", min: 3, why: "focus ring on panels" },
  { fg: "focus", bg: "panel-raised", min: 3, why: "focus ring on raised surfaces" },
  { fg: "sun", bg: "panel-raised", min: 3, why: "selected-state indicator (segmented, mode switch) on raised fill" },
  { fg: "sun", bg: "panel", min: 3, why: "selected-site indicator on panel fill" },
  { fg: "sun", bg: "night", min: 3, why: "selected-tab underline on the page" },
];
const lum = (h) => { const c = [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255)
  .map((v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)); return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]; };
export const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
export function tokens(css) {
  const root = /:root\s*\{([\s\S]*?)\}/.exec(css)?.[1] ?? "";
  return Object.fromEntries([...root.matchAll(/--([\w-]+)\s*:\s*(#[0-9a-fA-F]{6})\b/g)].map((m) => [m[1], m[2].toLowerCase()]));
}
export function colourProblems(css) {
  const t = tokens(css), out = [];
  const col = (k) => (k.startsWith("#") ? k : t[k]);
  for (const p of [...TEXT_PAIRS, ...NONTEXT_PAIRS]) {
    const a = col(p.fg), b = col(p.bg);
    if (!a || !b) { out.push({ kind: "contrast", message: `token missing for ${p.why}` }); continue; }
    const r = ratio(a, b);
    if (r < p.min) out.push({ kind: "contrast", message: `${p.why}: ${a} on ${b} = ${r.toFixed(2)}:1 < ${p.min}:1` });
  }
  // text inputs and selects must use the compliant boundary token
  const rule = /input\[type="text"\][^{]*\{([^}]*)\}/.exec(css)?.[1] ?? "";
  if (!/border:[^;]*var\(--control-edge\)/.test(rule)) out.push({ kind: "contrast", message: "text inputs/selects must use border colour var(--control-edge) (1.4.11)" });
  return out;
}

// ---------------------------------------------------------------- JSX rules
const INTERACTIVE = new Set(["button", "a", "input", "select", "textarea", "summary", "option", "label"]);
const HANDLERS = /^on(Click|KeyDown|KeyUp|KeyPress|MouseDown|MouseUp|DoubleClick)$/;
// pointer-only conveniences that have a documented keyboard equivalent elsewhere in the interface
export const POINTER_ALLOWLIST = [
  { file: "src/components/Timeline.tsx", tag: "svg", reason: "click-to-seek; keyboard equivalent: the Time cursor slider" },
  { file: "src/components/VisibilityChart.tsx", tag: "svg", reason: "click-to-seek; keyboard equivalent: the Time cursor slider" },
];
const attr = (el, name) => el.attributes.properties.find((p) => ts.isJsxAttribute(p) && p.name.getText() === name);
const attrText = (a) => { if (!a || !a.initializer) return a ? "" : null;
  if (ts.isStringLiteral(a.initializer)) return a.initializer.text; return a.initializer.getText(); };

export function jsxProblems(sf, file) {
  const out = [];
  const labelFor = new Set();
  const visitLabels = (n) => { if ((ts.isJsxOpeningElement(n) || ts.isJsxSelfClosingElement(n)) && n.tagName.getText() === "label") {
    const f = attrText(attr(n, "htmlFor")); if (f) labelFor.add(f); } n.forEachChild(visitLabels); };
  visitLabels(sf);
  const insideLabel = (n) => { for (let p = n.parent; p; p = p.parent) if (ts.isJsxElement(p) && p.openingElement.tagName.getText() === "label") return true; return false; };
  const line = (n) => sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1;
  const add = (n, rule, message) => out.push({ kind: rule, file, line: line(n), message });
  const visit = (n) => {
    if (ts.isJsxOpeningElement(n) || ts.isJsxSelfClosingElement(n)) {
      const tag = n.tagName.getText();
      if (/^[a-z]/.test(tag)) {
        const handlers = n.attributes.properties.filter((p) => ts.isJsxAttribute(p) && HANDLERS.test(p.name.getText())).map((p) => p.name.getText());
        const keyboardWidget = handlers.includes("onKeyDown") && attr(n, "tabIndex") && attr(n, "role");
        if (handlers.length && !INTERACTIVE.has(tag) && !keyboardWidget && !POINTER_ALLOWLIST.some((a) => a.file === file && a.tag === tag)) {
          add(n, "non-interactive-handler", `<${tag}> has ${handlers.join(", ")}: use a <button> (keyboard, role and Space/Enter for free)`);
        }
        const ti = attr(n, "tabIndex");
        if (ti) { const v = attrText(ti).replace(/[{}]/g, "");
          if (/^\d+$/.test(v) && Number(v) > 0) add(n, "positive-tabindex", `tabIndex=${v} breaks the focus order (2.4.3)`);
          if (v === "0" && !INTERACTIVE.has(tag) && !attr(n, "role")) add(n, "focusable-without-role", `<${tag} tabIndex=0> has no role (4.1.2)`); }
        const role = attrText(attr(n, "role"));
        if (role === "application") add(n, "role-application", `role="application" removes the screen reader's own keys; use role="img" or a widget pattern`);
        if (role === "img" && !attr(n, "aria-label") && !attr(n, "aria-labelledby")) add(n, "img-without-name", `role="img" needs aria-label (1.1.1)`);
        const hiddenSvg = attrText(attr(n, "aria-hidden")) === "true" || attrText(attr(n, "aria-hidden")) === "{true}";
        if (tag === "svg" && !hiddenSvg && (!role || !(attr(n, "aria-label") || attr(n, "aria-labelledby"))))
          add(n, "svg-without-role", `<svg> needs a role (img, or a widget role when operable) and aria-label, or aria-hidden (1.1.1)`);
        if (role === "slider" && !(attr(n, "aria-valuetext") || attr(n, "aria-valuenow")))
          add(n, "slider-without-value", "role=slider needs aria-valuenow/aria-valuetext (4.1.2)");
        if (tag === "img" && !attr(n, "alt")) add(n, "img-without-alt", "<img> needs alt (1.1.1)");
        if (tag === "input" || tag === "select" || tag === "textarea") {
          const id = attrText(attr(n, "id"));
          const named = attr(n, "aria-label") || attr(n, "aria-labelledby") || (id && labelFor.has(id)) || insideLabel(n);
          if (!named) add(n, "unlabelled-control", `<${tag}> has no label, aria-label or aria-labelledby (1.3.1, 4.1.2)`);
          if (attrText(attr(n, "type")) === "range" && !attr(n, "aria-valuetext")) add(n, "range-without-valuetext", "range input needs aria-valuetext (4.1.2)");
        }
        if (tag === "button" && ts.isJsxSelfClosingElement(n) && !attr(n, "aria-label")) add(n, "button-without-name", "self-closing <button> needs aria-label (4.1.2)");
      }
    }
    n.forEachChild(visit);
  };
  visit(sf);
  return out;
}

function sourceFiles() {
  const out = [];
  const walk = (d) => { for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, e.name); if (e.isDirectory()) walk(p); else if (/\.tsx$/.test(e.name)) out.push(p); } };
  walk(SRC);
  return out.sort();
}
const parse = (file, text) => ts.createSourceFile(file, text, ts.ScriptTarget.ES2021, true, ts.ScriptKind.TSX);

export function check() {
  const files = sourceFiles();
  const problems = [...colourProblems(fs.readFileSync(CSS, "utf8"))];
  for (const f of files) problems.push(...jsxProblems(parse(f, fs.readFileSync(f, "utf8")), rel(f)));
  const used = new Set(problems.filter((p) => p.kind === "allowlist-used").map((p) => p.file));
  void used;
  return { files: files.map(rel), problems };
}

function selfTest() {
  const results = []; const ok = (name, cond, detail = "") => results.push({ name, passed: !!cond, detail });
  const bad = parse("bad.tsx", `export const A = () => <div>
    <td tabIndex={0} onClick={() => 1} onKeyDown={() => 1}>cell</td>
    <span tabIndex={3}>x</span>
    <div role="application" aria-label="map" />
    <div role="img" />
    <svg viewBox="0 0 1 1"><rect /></svg>
    <img src="x.png" />
    <input id="nolabel" type="text" />
    <input type="range" aria-label="t" />
    <button />
  </div>;`);
  const kinds = jsxProblems(bad, "src/components/Bad.tsx").map((p) => p.kind);
  for (const k of ["non-interactive-handler", "positive-tabindex", "focusable-without-role", "role-application", "img-without-name",
    "svg-without-role", "img-without-alt", "unlabelled-control", "range-without-valuetext", "button-without-name"]) ok(`detects ${k}`, kinds.includes(k), kinds.join(","));
  const good = parse("good.tsx", `export const B = () => <div>
    <label htmlFor="a">A</label><input id="a" type="text" />
    <label>Exag <select aria-label="x"><option>1</option></select></label>
    <input type="range" aria-label="t" aria-valuetext="1 Jan" />
    <svg role="img" aria-label="chart" />
    <button onClick={() => 1}>Go</button>
  </div>;`);
  ok("accepts compliant markup", jsxProblems(good, "src/components/Good.tsx").length === 0, JSON.stringify(jsxProblems(good, "src/components/Good.tsx")));
  ok("allow-listed pointer convenience is accepted", jsxProblems(parse("t.tsx", `const T = () => <svg role="img" aria-label="x" onClick={() => 1} />;`), "src/components/Timeline.tsx").length === 0);
  const css = ":root { --night: #17212c; --panel: #1e2a37; --panel-raised: #243345; --text: #e7ecf1; --muted: #a3b1bf; --faint: #7d8d9d; --sun: #f2b544; --earth: #5fa8e8; --both: #e9dfb8; --valid: #7fc8a9; --alert: #ee9a6b; --focus: #ffd98a; --control-edge: #33475a; }\ninput[type=\"text\"], select { border: 1px solid var(--line); }";
  const cp = colourProblems(css).map((p) => p.message);
  ok("detects small text below 4.5:1 (old --faint on panel)", cp.some((m) => /--faint text on --panel:/.test(m)), cp.join(" | "));
  ok("detects control boundary below 3:1 (old --line)", cp.some((m) => /control-edge|border colour/.test(m)), cp.join(" | "));
  ok("ratio() matches WCAG reference (#777777 on white = 4.48)", Math.abs(ratio("#777777", "#ffffff") - 4.48) < 0.01, ratio("#777777", "#ffffff"));
  return results;
}

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  const jsonAt = process.argv.indexOf("--json"); const jsonOut = jsonAt > 0 ? process.argv[jsonAt + 1] : null;
  if (process.argv.includes("--self-test")) {
    const r = selfTest();
    for (const x of r) console.log(`${x.passed ? "PASS" : "FAIL"}  ${x.name}${x.passed ? "" : "  -> " + x.detail}`);
    const failed = r.filter((x) => !x.passed).length;
    console.log(`check-a11y self-test: ${r.length - failed}/${r.length} passed`);
    if (jsonOut) fs.writeFileSync(jsonOut, JSON.stringify({ selfTest: r }, null, 2) + "\n");
    process.exit(failed ? 1 : 0);
  }
  const { files, problems } = check();
  for (const p of problems) console.log(`${p.kind.padEnd(24)} ${p.file ? p.file + ":" + p.line + "  " : ""}${p.message}`);
  const css = fs.readFileSync(CSS, "utf8"), t = tokens(css);
  const pairs = [...TEXT_PAIRS, ...NONTEXT_PAIRS].map((p) => { const a = p.fg.startsWith("#") ? p.fg : t[p.fg], b = t[p.bg];
    return { ...p, fgHex: a, bgHex: b, ratio: a && b ? Math.round(ratio(a, b) * 100) / 100 : null }; });
  console.log(`check-a11y: ${files.length} components, ${pairs.length} colour pairs, ${problems.length} problem(s)`);
  if (jsonOut) fs.writeFileSync(jsonOut, JSON.stringify({ files, pairs, problems }, null, 2) + "\n");
  process.exit(problems.length ? 1 : 0);
}
