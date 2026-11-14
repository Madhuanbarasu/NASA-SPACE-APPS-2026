# C10: interface string externalisation (Phase 4, 2026-11-11)

**Requirement C10 (blueprint Section 3):** English, text separate from code.
**Status:** implemented and checked. The full checklist is in "Completion checklist" below.

Before this change every interface string was written inline in components and in `lib/format.ts`. Now every user-facing string lives in one type-safe English dictionary, `frontend/src/i18n/en.ts`. A checker (`npm run check:strings`) gates `npm run build`, CI and `start.py`, and it rejects:
- unknown keys;
- unused keys;
- hardcoded interface text.

The rendered interface is byte-identical to the build before C10 in all 54 rendered scenarios.

Backend, science and API are untouched:
- no file under `backend/` was modified;
- the code fingerprint, suite fingerprint and terrain-acceptance digest are unchanged;
- the algorithm version is still 1.5.0.

## Results

| Check | Command | Result | Evidence |
| --- | --- | --- | --- |
| TypeScript | `npm run typecheck` (`tsc --noEmit -p .`, strict) | exit 0, no diagnostics | `logs/01_typecheck.log` |
| String-check self-test | `node scripts/check-strings.mjs --self-test` | 37/37 passed | `logs/02_npm_test.log`, `logs/check_strings_selftest.json` |
| String check on `src/` | `node scripts/check-strings.mjs` | 420 keys, 420 referenced, 21 files scanned, 0 problems, 5 allow-listed literals | `logs/check_strings_report.json` |
| Frontend tests | `npm test` (self-test, then check) | exit 0 | `logs/02_npm_test.log` |
| Production build | `npm run build` (tsc, string check, vite build) | exit 0; 376 modules; built in 9.19 s | `logs/03_npm_run_build.log` |
| Rendered-output equivalence | SSR harness, baseline vs C10 (see below) | 54/54 scenarios byte-identical (375,855 characters), 0 render errors | `ssr_equivalence/` |
| Negative control (equivalence) | the same harness with a one-space change to one dictionary entry | 5/54 scenarios differ (every scenario that renders it) | `ssr_equivalence/negative_control_mutant_summary.json` |
| Negative control (detector) | the hardcoded-text detector run on the pre-C10 baseline `src` | 398 findings in 14 files; 0 on the C10 `src` | `hardcoded_scan_baseline.json`, `hardcoded_scan_c10.json` |
| Backend unchanged | fingerprints recomputed after the work | code `5bf9753f…`, suite `1632af16…`, acceptance `e48eb8ed…`, algorithm 1.5.0: identical to before | `logs/backend_fingerprints_after.txt` |

**Environment:** Windows 11, Node v24.19.0, npm 11.17.0, TypeScript 5.6.3, Vite 5.4.21. No dependency was added or installed and no network access was used.

The frontend has no unit-test framework, and adding one would mean installing a dependency. The applicable frontend tests are therefore the type check, the string checker with its self-test, the production build, and the rendered-output equivalence harness.

## What changed

### New files

| File | Purpose |
| --- | --- |
| `frontend/src/i18n/en.ts` | The English dictionary: 420 strings in 26 top-level sections, typed `as const`. It has no imports, so the checker can load it. |
| `frontend/src/i18n/index.ts` | Exports `S` (the strings), `rich`, `Strings`, and a d3 time locale built from the dictionary's month and day names (used for the timeline axis). |
| `frontend/src/i18n/rich.ts` | `rich(template, values)` renders a whole sentence containing markup (bold numbers, code) from a `{placeholder}` template. The placeholder names are checked at compile time: a missing or extra value is a TypeScript error. |
| `frontend/scripts/check-strings.mjs` | The C10 checker, built on the TypeScript compiler API that is already installed. |

### Modified files

All modified files are in `frontend/`, and every change only swaps inline text for dictionary references. `frontend_c10_tracked.diff` has the full diff, and `logs/c10_files_sha256.txt` has the file hashes.

| File | Externalised |
| --- | --- |
| `package.json` | Scripts `typecheck`, `check:strings` and `test` added; `build` now runs the string check between `tsc` and `vite build`. Dependencies are unchanged. |
| `src/components/TopBar.tsx` | Brand, tabs, data-status pill, Technical/Public mode switch, ARIA labels |
| `src/components/Welcome.tsx` | Heading, introduction, data-readiness rows, the three steps |
| `src/components/Sidebar.tsx` | Section headings, field labels, placeholders, rule/profile/panel options, coverage hints and errors, buttons, API-unreachable message |
| `src/components/SiteView.tsx` | Site header, downloads, label chips and their tooltips, panorama legend and hint, readout, countdowns, figures, the Public-mode summary, events and series tables, play/pause, region labels, synthetic-terrain alert |
| `src/components/CompareView.tsx` | Title and intro, metrics, site and window lists, buttons, target hints, matrix caption, headers and cell labels, shading hint |
| `src/components/DataView.tsx` | All headings, prose, table headers, the blueprint test names, the attribution table, footer |
| `src/components/GuideView.tsx` | The whole guide (prose, rules, glossary) |
| `src/components/HorizonPanorama.tsx` | Chart ARIA label, compass letters, axis degree labels, hover readout |
| `src/components/Timeline.tsx` | Row labels, ARIA label, axis date format (through the dictionary's d3 locale) |
| `src/components/MapView.tsx` | Map ARIA label, tile-status notes, graticule labels, click hint |
| `src/components/Terrain3D.tsx` | ARIA labels, loading text, WebGL error, height note, vertical-exaggeration control |
| `src/lib/format.ts` | Month names, `n/a`, `unknown`, duration units, `passed`, the UTC/date/degree/percent patterns. `RULE_NAMES` and `PANEL_NAMES` are kept as typed views of the dictionary, so their exports are unchanged. |
| `src/state/store.tsx` | Catalogue-load, analysis-stopped and comparison-stopped messages |
| `src/api/client.ts` | `Cancelled` |
| `src/main.tsx` | Sets `document.title` from the dictionary. The static `<title>` in `index.html` stays as the pre-script fallback, and the checker requires the two to match. |

No CSS, layout, class name, element structure, state logic, API request, scientific value or algorithm was changed. `frontend/dist` was rebuilt: only the JS bundle changed (`index-DoHGrS9u.js`, 1,230,747 bytes → `index-SfzAm8-Q.js`, 1,240,141 bytes, +0.76%). The CSS and font files are byte-identical (`logs/dist_before_sha256.txt`, `logs/dist_after_sha256.txt`).

## Dictionary conventions

- Plain text is a string. Text that includes values is a typed function, for example `S.compare.run(sites, windows)`.
- Sentences with markup inside are `{name}` templates rendered by `rich()`, so translators always see the whole sentence.
- Keys of the visibility rules, panels, observer profiles, quantities and tabs are the API's or store's own values. That keeps lookups typed (`S.rules[rule]`).
- Components alias one section (`const T = S.sidebar`). The checker follows these aliases through TypeScript symbol resolution, including aliases of aliases.
- Text coming from the API is data and is shown as received. That covers job messages, warnings, kernel errors, event names, label kinds and validation words, test statuses and details, catalogue names, the radio note, and the tile note.

## The checker (`frontend/scripts/check-strings.mjs`)

| Problem kind | Meaning |
| --- | --- |
| `unknown-key` | An `S.*` reference, direct or through an alias, to a key that doesn't exist. TypeScript rejects these too. |
| `unused-key` | A dictionary entry that no file references. |
| `hardcoded` | English left in `src/` outside `src/i18n/`. Covers: JSX text; literal `aria-*`, `title`, `placeholder`, `alt` or `label` attributes; strings rendered as JSX children; values of UI-named properties (`label`, `text`, `title`, `t`, `name`, `message`, `note`, …); `Error` messages; state-setter arguments; returned text; any other prose-like literal. |
| `dictionary` | Empty strings, empty sections, or unbalanced or malformed `{placeholders}`. |
| `html` | The `index.html` `<title>` or `lang="en"` is out of step with the dictionary. |
| `allowlist` | An exception that no longer matches anything. Stale exceptions fail the check. |

The self-test (37 cases) proves that each detector fires on known-bad input. It also proves the checker ignores technical literals: class names, CSS values, comparisons, dispatch action types, projection codes, colours and URLs. It checks unknown keys end to end in a virtual component, both through `S` and through an alias.

**The five allow-listed literals**, each kept with its reason in the script:
- the API status-word prefixes `Validated` and `Synthetic`, which are compared, not displayed;
- an OpenLayers CSS font shorthand;
- the CSS keyword `transparent`;
- the developer invariant `useStore outside provider`.

## Rendered-output equivalence (`ssr_equivalence/`)

`harness.tsx` renders every view with React's `renderToStaticMarkup`:
- TopBar, Sidebar, SiteView, CompareView, DataView, GuideView, HorizonPanorama and Timeline;
- 54 scenarios in total: Technical and Public modes, connecting, loading, error and empty states, production, test and missing kernels, real and synthetic terrain, custom and curated sites, cursor positions, playing state, coverage edges, every compare metric including an unknown one, comparison cell errors, and blockers;
- every formatting function in `lib/format.ts` over a grid of edge-case inputs.

The store is mocked per scenario. `ssr_diff.mjs` bundles the harness twice with the frontend's own esbuild, once against the baseline `src` snapshot taken before any edit (`logs/baseline_src_sha256.txt`) and once against the C10 `src`, and compares the outputs. The two render files are byte-identical: SHA-256 `9e1ee42b0a2a7dab…` for both (`render_outputs_sha256.txt`; the C10 render is in `render-c10.json.gz`).

**Coverage limits:** server rendering doesn't run effects or user events. Text that appears only after an effect or interaction wasn't compared, namely:
- MapView tile notes after loading;
- Terrain3D's grid note and WebGL error;
- the panorama hover readout;
- the contents of the opened Events and Chart-data tables.

Those strings are covered by the type check, the key check (all referenced), the hardcoded scan (none left) and a line-by-line review. Each one was moved verbatim into a function that keeps the original interpolation.

## What is not externalised, and why

1. **Text from the API** (listed under "Dictionary conventions"). It comes from the backend, which this task must not modify. The Data page's quantity column also shows API label keys with `_` replaced by spaces, as before.
2. **`toLowerCase()` on dictionary text.** It's used inline for rule names (Compare intro, Timeline rows) and panel names (Readout, Figures). It was kept so the output stays identical, including the existing "vertical, tracking the sun". This doesn't matter for English, but would for a future translation. The fix is inline-case dictionary entries, which would change one visible word, so it's left for a decision.
3. **Number formatting** (`toFixed`, `.` as the decimal mark) and the English ordinal in "Every {n}th sample" are unchanged. C10 asks for English.
4. **The five allow-listed technical literals** (above), and the non-breaking-space placeholder in Terrain3D, which contains no text.

## Documentation not updated here

`README.md` (Remaining limitations: "Interface strings are not yet externalized for translation (C10 partial)") and the `docs/TRACEABILITY.md` C10 row still describe the earlier state. Both files carry other uncommitted Phase 4 edits, so they are left for the final A1–A15 traceability update, which should point C10 at this folder.

## Completion checklist

- [x] Every user-facing frontend string inventoried: 398 detector findings in 14 of the 19 `src` files before C10; 15 `src` files and `package.json` modified.
- [x] Central type-safe English dictionary (`src/i18n/en.ts`, 420 keys) with typed interpolation and compile-time-checked rich templates.
- [x] Inline strings replaced in every component and library file; 0 hardcoded findings remain.
- [x] Behaviour, styling and layout preserved: 54/54 rendered scenarios byte-identical, CSS bundle byte-identical, no API or science change.
- [x] Checks for missing, misspelt, unused and hardcoded keys, built on the installed tooling and wired into `npm run build` and `npm test`.
- [x] TypeScript check, frontend tests and production build pass; `frontend/dist` rebuilt.
- [x] Backend fingerprints and algorithm version 1.5.0 unchanged; no dependencies installed; no git operations.
- [ ] README and TRACEABILITY C10 status lines: deferred to the final traceability task (see above).
