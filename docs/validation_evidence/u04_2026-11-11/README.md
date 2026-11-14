# U-04: accessibility audit against WCAG 2.2 Level AA (2026-11-11)

## Final status: **PASS (scoped)**

All 55 WCAG 2.2 Level A and AA success criteria were assessed against the LUNA-OPS interface.
- **24 defects were found**, all fixed, and each fix was re-verified in the running application.
- **No A/AA failure remains in the audited scope.**

The scope and its limits are stated in "Remaining limitations" below. Most importantly:
- the audit used the browser's accessibility tree, scripted keyboard tests and measurements, **not a session with a real screen reader user**;
- it ran in **one browser engine** (Chromium 157).

The criterion applied is requirement C02 (WCAG 2.2 AA). The blueprint's own U-04 procedure text is not in the repository.

**The validation report has not been updated.** `backend/validation/report.json` still lists U-04 as `not run`. Recording it needs a `frontend_u04` result file merged with `run_validation`, which reruns the pytest suite and changes label gating. That step is left for approval (see "Not done here").

## Method and environment

- **Application under test:** the production build `frontend/dist`, served by `start.py --no-browser --port 8765`.
  - Production NAIF kernels, the registered PGDA terrain (5/20/80/240 m), algorithm 1.5.0, code fingerprint `5bf9753f…`.
  - A real analysis of Site01 (−89.463163°, 222.510447°, 14–21 Nov 2026).
  - A real 2-site × 2-window comparison.
  - No backend code, validation logic or threshold was touched.
- **Browser:** Chrome 157.0.8103.39 in headless mode, driven through the Chrome DevTools Protocol by `frontend/scripts/a11y-live-audit.mjs`. It uses Node's built-in WebSocket; **no packages were installed or downloaded**.
- **Static regression check:** `frontend/scripts/check-a11y.mjs`, using the TypeScript compiler already installed.
- **Content preservation:** the C10 server-side render harness (`../c10_2026-11-11/ssr_equivalence/`).

**Per view, the live audit records:**
- the browser's full accessibility tree: controls and images without a name, focusable elements without a widget role;
- structure: `lang`, title, landmarks, headings, duplicate ids, positive `tabindex`, `aria-hidden` focusables, table headers, live regions;
- contrast of **every visible text node**, against backgrounds composited up the ancestor chain;
- a **real Tab-key walk**: order, focus indicator, clipping of the indicator by overflow containers, obscured focus, traps;
- target size: 24 px, with the spacing exception;
- reflow at 320 CSS px (= 1280 px at 400 %);
- a text-spacing override (1.4.12);
- screenshots.

**Functional tests** drive real key and pointer events and check the outcome:
- skip link;
- tab arrow keys;
- coordinate error;
- slider value text;
- live-region behaviour while playing;
- Escape on the hover readout;
- Space and Enter on comparison cells;
- keyboard pan, rotate and zoom of the map and the 3D view;
- the panorama azimuth slider;
- the single-pointer view buttons;
- status announcements;
- reduced motion.

**Runs** (all kept):

| Label | Build | Purpose |
| --- | --- | --- |
| `before` | build before U-04 | baseline |
| `after` | pass 1 | intermediate |
| `final` | pass 2 | intermediate |
| `release` | final code | the result reported here |

## Application coverage

| View / state | Covered by |
| --- | --- |
| Site, no result (welcome, readiness list, map) | live audit `site-welcome`, Tab walk, 320 px, text spacing |
| Site, analysed result, Technical mode (label chips, panorama, readout, time slider, countdowns, timeline, map, 3D, figures, notes, Events and Chart-data tables expanded) | live audit `site-result-technical`, Tab walk (52 stops), keyboard and pointer tests |
| Site, analysed result, Public mode (plain-language summary) | live audit `site-result-public` |
| Sidebar: catalogue empty state, coordinates (valid, invalid), coverage, dates, display step, observer profile, rules, margin, panel, Analyse, progress, errors | every view's Tab walk; invalid-coordinate test; C10 SSR scenarios for progress/error/API-unreachable states |
| Compare: site and window lists, add/remove, metric selector, matrix with result cells, CSV link | live audit `compare-matrix` (76 stops), cell activation by Space and Enter |
| Data and validation: kernels, terrain, validation report, labels, attribution | live audit `data` |
| Guide | live audit `guide` |
| Top bar: brand, tabs, data status, Technical/Public switch | every view |
| Narrow screens: 320 px (each view) and 390 px (mobile site view) | reflow screenshots |
| Dialogs | none exist in the application |

## Results: automated checks, baseline vs release

Each cell is the number of problems, as baseline → release.

| View | Unnamed controls/images | Focusable without role | Contrast failures | Target-size failures | Stops without focus indicator | Indicator clipped | Obscured | Horizontal scroll at 320 px | Overflowing elements at 320 px | Clipped with text spacing | `role=application` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| site-welcome | 0 → 0 | 0 → 0 | **1 → 0** | 0 → 0 | **2 → 0** | 0 → 0 | 0 → 0 | **yes → no** | **87 → 0** | 0 → 0 | **1 → 0** |
| site-result-technical | 0 → 0 | 0 → 0 | **1 → 0** | 0 → 0 | **2 → 0** | **2 → 0** | 0 → 0 | **yes → no** | **128 → 0** | 0 → 0 | **1 → 0** |
| site-result-public | 0 → 0 | 0 → 0 | **1 → 0** | 0 → 0 | – | – | – | **yes → no** | **129 → 0** | 0 → 0 | **1 → 0** |
| compare-matrix | 0 → 0 | **4 → 0** | **3 → 0** | 0 → 0 | **6 → 0** | **4 → 0** | 0 → 0 | **yes → no** | **94 → 0** | 0 → 0 | 0 → 0 |
| data | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | **2 → 0** | **1 → 0** | 0 → 0 | **yes → no** | **75 → 0** | 0 → 0 | 0 → 0 |
| guide | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | **2 → 0** | **1 → 0** | 0 → 0 | **yes → no** | **101 → 0** | 0 → 0 | 0 → 0 |

No view had unlabelled form controls, duplicate ids, positive `tabindex` or `aria-hidden` focusables. Every view has `lang="en"`, a title, and banner, tablist, complementary and main landmarks. The Tab walk cycled through every view without a trap.

**Target size (2.5.8):** three controls are under 24 px in one dimension, all passing by the spacing exception:
- the time slider, 800 × 16 px;
- the "Hide" table toggle, 28 × 19 px;
- the "Hide table" table toggle, 61 × 19 px.

## Results: functional tests, baseline vs release

| Test | Baseline | Release |
| --- | --- | --- |
| Skip link is the first Tab stop; Enter moves focus to `main` | no skip link | `a.skip-link`; focus moves to `main` |
| Tabs: one Tab stop; Right/Left arrows move and select | each tab a separate stop; arrows did nothing | 1 stop; Right selects and focuses Compare; Left returns to Site |
| Non-numeric latitude "abc" | silently ignored (generic hint) | "Latitude and longitude must be numbers in degrees, for example -89.5 and 222.5."; `aria-invalid="true"`; `aria-describedby="coord-hint"` |
| Time slider value | index "0" | `aria-valuetext` "14 Nov 2026, 00:00 UTC" |
| Readout live region while the animation plays | `polite` (about 7 announcements per second) | `off` while playing; `polite` when paused |
| Comparison cell activation | Enter opened the result; **Space did nothing**; cells had no role | real buttons; Space and Enter both open the result |
| Panorama hover readout dismissed with Escape | not dismissible | shown, then gone after Escape |
| Map by keyboard (focus, arrows, +) | map not focusable | pans and zooms (pixels change) |
| 3D view by keyboard (arrows, Shift+arrows, +) | not focusable | pans, rotates, zooms |
| Panorama azimuth slider (focus, →, Page Up) | mouse hover only | `role=slider`; "Az 264.0° horizon −1.55°" → "Az 275.0° horizon −1.07°"; the same readout is drawn on screen |
| Single-pointer view controls (no dragging) | drag only | map +/− and 3D rotate left/right, zoom in/out: 28 × 28 px, named, each changes the view |
| Status after an analysis completes | nothing announced | `role=status`: "Results ready for Custom site." |
| Status after a comparison completes | nothing announced | `role=status`: "Comparison ready: 2 sites × 2 windows." |
| `prefers-reduced-motion: reduce` | transitions 0 s | transitions 0 s (unchanged) |

## Contrast measurements

**Design tokens** (`src/styles/app.css`, checked on every `npm test` and `npm run build` by `check-a11y.mjs`; full list in `logs/check_a11y_report.json`):

| Pair | Colours | Ratio | Needed |
| --- | --- | --- | --- |
| `--text` on night / panel / raised | #e7ecf1 on #17212c / #1e2a37 / #243345 | 13.69 / 12.25 / 10.81 | 4.5 |
| `--muted` on night / panel / raised | #a3b1bf | 7.44 / 6.66 / 5.87 | 4.5 |
| **`--faint` on night / panel / raised (before)** | **#7d8d9d** | 4.78 / **4.28** / **3.77** | 4.5 |
| **`--faint` on night / panel / raised (after)** | **#8b9bab** | 5.72 / 5.12 / 4.51 | 4.5 |
| `--sun` / `--earth` / `--alert` / `--valid` text, worst surface | #f2b544 / #5fa8e8 / #ee9a6b / #7fc8a9 | 7.02 / 5.05 / 5.79 / 6.57 | 4.5 |
| Analyse button label on gold | #1b1406 on #f2b544 | 9.98 | 4.5 |
| **Input/select border (before: `--line`)** against page / fill | #33475a | **1.70 / 1.52** | 3 |
| **Input/select border (after: `--control-edge`)** against page / fill | #617588 | 3.42 / 3.06 | 3 |
| Focus ring on night / panel / raised | #ffd98a | 12.05 / 10.78 / 9.51 | 3 |
| Selected-state indicators (gold) on raised / panel / night | #f2b544 | 7.02 / 7.96 / 8.89 | 3 |

**Rendered text in the release build** (`audit-release.json`, every visible text node in all six views):
- 22 distinct colour pairs, **0 below the required ratio**.
- The lowest are:
  - 4.78:1, for 11 px SVG axis labels (#7d8d9d on #17212c);
  - 5.12:1, for the pane notes;
  - 5.98:1, for comparison-cell text on the strongest gold shading (#e7ecf1 on #665635).

**Baseline failures:**
- "open full result" on comparison shading: 2.09, 4.21 and 4.27:1;
- pane notes: 4.28:1.

**Non-text graphics (1.4.11):**
- The chart lines and bars (Sun, Earth, overlap and the uncertainty hatch) are ≥ 5:1 against their backgrounds.
- The terrain silhouette has a #8a9aab outline, about 5:1.
- The selected-site marker on the bright hillshade now has a dark halo.

## Defects found and fixes

All fixes are verified in the release run. "Live" means measured in the running application.

| # | WCAG | Defect (evidence) | Fix |
| --- | --- | --- | --- |
| 1 | 1.4.3 | `--faint` text 4.28:1 on panels, 3.77:1 on raised (live; token check) | `--faint` #7d8d9d → #8b9bab (≥ 4.51:1 everywhere) |
| 2 | 1.4.3 | "open full result" 2.09:1 on gold shading (live; `before-compare-matrix.png`) | cell sub-label uses `--text` (≥ 5.98:1) |
| 3 | 1.4.11 | Text inputs and selects identified only by a 1.70/1.52:1 border | new `--control-edge` #617588 (3.42/3.06:1) |
| 4 | 1.4.11 | Selected Technical/Public mode shown only by a 1.27:1 fill change | gold inset ring (7.02:1) |
| 5 | 1.4.11 | Selected curated site shown only by a 1.12:1 fill change | gold inset bar (7.96:1). The catalogue is empty in this installation, so this was checked by the token check, not rendered. |
| 6 | 1.4.11 | Gold site marker on bright hillshade (about 1.3:1) | dark halo under the marker; dark outline on catalogue points |
| 7 | 1.4.10 | At 320 px every view was 406 px wide and scrolled sideways: inputs' intrinsic width, top-bar status and mode switch, tab strip, metric selector, two-column figures (live) | single shrinkable grid column; `min-width: 0` on inputs; the top bar, tabs and metric selector wrap; figures stack below 600 px; below 900 px the page scrolls as one document, not two cramped panes |
| 8 | 2.4.7 | Date-time fields showed no outline at some focus stops (Chrome focuses the inner date fields) | outline on `:focus` and `:focus-within` of the field |
| 9 | 2.4.7 / 2.4.11 | Focus rings partly clipped at scroll-container edges (Analyse button, table scroller, comparison cells) | `scroll-margin: 12px` on focusable elements |
| 10 | 2.1.1 / 4.1.2 | Comparison cells were clickable `<td tabIndex=0>` with no role; Space did nothing (live) | each result cell contains a `<button>` |
| 11 | 2.5.3 | The cell `aria-label` replaced the visible "open full result" text | the button's name is its visible text; row and column headers give the context |
| 12 | 4.1.2 | Map had `role="application"` with no keyboard support and no focus | `role="region"` with a name that describes the keys |
| 13 | 2.1.1 | Map pan and zoom were mouse-only | the map is focusable; OpenLayers' default keyboard pan/zoom now works (arrows, + and −) |
| 14 | 2.1.1 | 3D orbit was mouse-only | the view is focusable; arrows pan, Shift/Ctrl + arrows rotate, + and − zoom |
| 15 | 2.1.1 | Horizon readout per azimuth was pointer hover only | the panorama is an azimuth slider (arrows ±1°, Page Up/Down ±10°, Home/End), with the readout as `aria-valuetext` and drawn on screen |
| 16 | 2.5.7 | Map panning and 3D rotation needed dragging | map zoom buttons (with double-click to zoom on a point), and 3D rotate/zoom buttons, all 28 × 28 px |
| 17 | 4.1.2 | Time slider exposed only an index | `aria-valuetext` gives the UTC time |
| 18 | 3.3.1 / 3.3.3 | Non-numeric coordinates were silently ignored | error message with an example; `aria-invalid`; `aria-describedby` |
| 19 | 4.1.3 | Completion of an analysis or comparison was not announced | persistent `role="status"` messages |
| 20 | 4.1.3 (and usability) | Readout live region announced about 7 times a second during playback | `aria-live="off"` while playing |
| 21 | 1.4.13 | Panorama hover readout could not be dismissed without moving the pointer | Escape dismisses it |
| 22 | 1.3.1 | Attribution table had no header cells | first column is `<th scope="row">` |
| 23 | 4.1.2 (ARIA tabs pattern) | `tablist` without `tabpanel`/`aria-controls`; every tab a Tab stop; no arrow keys | full tabs pattern: ids, `aria-controls`, a `tabpanel` inside `main`, a single Tab stop, arrows/Home/End |
| 24 | 2.4.1 (enhancement) | Landmarks were present, but about 30 sidebar controls came before the results | "Skip to main content" link, visible on focus |

All new interface text goes through the C10 dictionary (`src/i18n/en.ts`, now 433 keys).

## WCAG 2.2 Level A and AA: criterion by criterion

"Fixed" means it failed in the baseline and passes after the fix (defect numbers refer to the table above).

| SC | Level | Result | Basis |
| --- | --- | --- | --- |
| 1.1.1 Non-text Content | A | Pass | Accessibility tree: 0 unnamed images or graphics. Panorama, timeline, map and 3D have names. Decorative dots are `aria-hidden`. Chart data is in the Chart-data and Events tables plus CSV/JSON downloads. |
| 1.2.1–1.2.5 Time-based media | A/AA | N/A | No audio or video |
| 1.3.1 Info and Relationships | A | Pass (fixed #22) | Landmarks, headings, labels, `role=group` names, table headers and captions |
| 1.3.2 Meaningful Sequence | A | Pass | DOM order: skip link, top bar, sidebar, main |
| 1.3.3 Sensory Characteristics | A | Pass | Instructions do not rely on colour or shape alone; colour words in the Guide are backed by labelled legends and text readouts |
| 1.3.4 Orientation | AA | Pass | No orientation lock; works at 320 and 390 px |
| 1.3.5 Identify Input Purpose | AA | N/A | No personal-data fields |
| 1.4.1 Use of Color | A | Pass (fixed #4, #5) | Sun/Earth have text labels; validation chips carry words; uncertain intervals are dashed; selected states have shape indicators |
| 1.4.2 Audio Control | A | N/A | No audio |
| 1.4.3 Contrast (Minimum) | AA | Pass (fixed #1, #2) | Every visible text node measured; minimum 4.78:1 |
| 1.4.4 Resize Text | AA | Pass | Reflow at 320 px (400 %) and text spacing pass; no text in images |
| 1.4.5 Images of Text | AA | Pass | None; map labels are vector text |
| 1.4.10 Reflow | AA | Pass (fixed #7) | No horizontal scrolling at 320 px; only data tables and the comparison matrix scroll inside their own containers (2-D content exception) |
| 1.4.11 Non-text Contrast | AA | Pass (fixed #3–#6) | Token and graphics measurements above |
| 1.4.12 Text Spacing | AA | Pass | Override applied in all views; 0 clipped elements; screenshots `*-textspacing.png` |
| 1.4.13 Content on Hover or Focus | AA | Pass (fixed #21) | Panorama readout dismissible, hoverable and persistent; native `title` tooltips are browser-controlled |
| 2.1.1 Keyboard | A | Pass (fixed #10, #13–#15) | Tab walk reaches every control. Map, 3D and panorama are keyboard-operable. Map click-to-pick has typed coordinates as an alternative; timeline click-to-seek has the time slider. |
| 2.1.2 No Keyboard Trap | A | Pass | The Tab walk cycles in every view; focus leaves the map, 3D view and panorama with Tab |
| 2.1.4 Character Key Shortcuts | A | Pass | Single keys (+, −, arrows) act only while the map, 3D view or panorama has focus |
| 2.2.1 Timing Adjustable | A | Pass | No time limits |
| 2.2.2 Pause, Stop, Hide | A | Pass | Animation starts only on request and has a Pause button; nothing auto-updates for more than 5 s |
| 2.3.1 Three Flashes | A | Pass | No flashing content |
| 2.4.1 Bypass Blocks | A | Pass (enhanced #24) | Landmarks plus skip link |
| 2.4.2 Page Titled | A | Pass | "LUNA-OPS: Lunar Landing Site Navigator" (single-page application) |
| 2.4.3 Focus Order | A | Pass (fixed #23) | Logical order; tabs are a single stop; no positive `tabindex` |
| 2.4.4 Link Purpose (In Context) | A | Pass | Links: skip link, Series/Events/Intervals CSV, Full result JSON, Comparison CSV |
| 2.4.5 Multiple Ways | AA | Pass | Single-page application; every view is reachable from the tab list (and the Guide) |
| 2.4.6 Headings and Labels | AA | Pass | Descriptive headings and labels |
| 2.4.7 Focus Visible | AA | Pass (fixed #8, #9) | Every Tab stop in every view has a visible 2 px #ffd98a ring, none clipped |
| 2.4.11 Focus Not Obscured (Minimum) | AA | Pass | 0 obscured stops; on narrow screens the bar no longer sticks over content |
| 2.5.1 Pointer Gestures | A | Pass | No multipoint or path-based gestures are required |
| 2.5.2 Pointer Cancellation | A | Pass | Native buttons; map pick fires on click (up event) |
| 2.5.3 Label in Name | A | Pass (fixed #11) | Accessible names contain the visible text |
| 2.5.4 Motion Actuation | A | N/A | No motion input |
| 2.5.7 Dragging Movements | AA | Pass (fixed #16) | View buttons; double-click zoom on the map; slider tracks accept single clicks |
| 2.5.8 Target Size (Minimum) | AA | Pass | 0 failures; 3 undersized controls pass by spacing |
| 3.1.1 Language of Page | A | Pass | `lang="en"` |
| 3.1.2 Language of Parts | AA | Pass | All text is English |
| 3.2.1 On Focus | A | Pass | Focus never changes context (the panorama only shows a readout) |
| 3.2.2 On Input | A | Pass | Inputs change settings only; tabs follow the WAI-ARIA tabs pattern |
| 3.2.3 Consistent Navigation | AA | Pass | Same top bar and sidebar in every view |
| 3.2.4 Consistent Identification | AA | Pass | Same labels for the same functions |
| 3.2.6 Consistent Help | A | Pass | The Guide tab is always in the same place |
| 3.3.1 Error Identification | A | Pass (fixed #18) | Coordinate error text; API errors are shown in `role=alert` |
| 3.3.2 Labels or Instructions | A | Pass | Every control labelled; hints for the formats |
| 3.3.3 Error Suggestion | AA | Pass (fixed #18) | Example values; coverage reasons from the API |
| 3.3.4 Error Prevention (Legal, Financial, Data) | AA | N/A | No such submissions |
| 3.3.7 Redundant Entry | A | Pass | "Add to comparison" and "Add the panel's dates" reuse earlier entries |
| 3.3.8 Accessible Authentication (Minimum) | AA | N/A | No authentication |
| 4.1.2 Name, Role, Value | A | Pass (fixed #10, #12, #17, #23) | Accessibility tree: 0 unnamed controls; widget roles and states correct |
| 4.1.3 Status Messages | AA | Pass (fixed #19, #20) | Coverage, progress, completion and error messages are live regions |

4.1.1 Parsing is obsolete in WCAG 2.2 and is not listed.

## Regression checks added

| Check | Runs in | What it guards |
| --- | --- | --- |
| `frontend/scripts/check-a11y.mjs` (15-case self-test) | `npm test`, `npm run build` (CI and `start.py` build too) | Colour tokens: all text pairs ≥ 4.5:1; control borders, focus ring and selected-state indicators ≥ 3:1; inputs use `--control-edge`. JSX: no click or key handlers on non-interactive elements unless they are a keyboard widget (role + `tabIndex` + key handler); no positive `tabindex`; no focusable element without a role; no `role="application"`; `role=img` and SVGs need a name and role; sliders need a value; every input/select is labelled; range inputs need `aria-valuetext`; self-closing buttons need `aria-label` |
| `frontend/scripts/a11y-live-audit.mjs` (`npm run audit:a11y`) | on demand, against a running app | The full live audit and functional tests in this report |
| `frontend/scripts/check-strings.mjs` (C10) | `npm test`, build | Now 38 self-test cases. The "state setter" rule no longer mistakes DOM `setAttribute`/`setProperty` attribute names for interface text; a negative self-test covers it. |

## Content and safeguards preserved

- **Visible text unchanged.** The C10 render harness (54 scenarios) shows 41 with identical text. The other 13 differ only by the "team target (C01)" hint removed in the earlier hackathon cleanup. 0 render errors; markup changed in 45 scenarios by ARIA attributes, ids and the cell buttons (`content_preservation/`).
- **Scientific functionality unchanged:**
  - no backend file was modified;
  - backend fingerprints are code `5bf9753f…`, suite `1632af16…`, terrain acceptance `e48eb8ed…`, algorithm 1.5.0, all unchanged (`logs/backend_fingerprints_after.txt`);
  - V-09…V-12 evidence and the validation report are untouched;
  - no A6/A7 measurement was repeated.
- **C10 and the hackathon cleanup are intact.** String check: 433 keys, all referenced, 0 problems; the C01 hint is still removed.

## Remaining limitations and observations

1. **No assistive-technology user session** with NVDA, JAWS, VoiceOver, Narrator or TalkBack. Screen-reader behaviour is inferred from Chrome's accessibility tree, roles, names, values and live regions. A short NVDA or Narrator spot check is recommended before any formal conformance claim.
2. **One browser engine:** Chromium 157 (Chrome; Edge uses the same engine). Firefox and Safari were not tested. The date-field focus fix targets Chrome's date-field internals and uses standard `:focus`/`:focus-within`.
3. **Zoom was emulated through the viewport** (320 CSS px = 400 % of 1280 px), not the browser's zoom UI. Text-only 200 % zoom was not run separately; it is covered by the stricter reflow and text-spacing checks.
4. **Speech input** was not exercised. Label-in-name was verified by inspecting accessible names.
5. **Not rendered live:**
   - The curated-site list is empty in this installation, so its selected-state indicator (#5) is verified by the token check.
   - Backend failure states (API unreachable, job error) are covered by the C10 render scenarios and code review.
6. **Observations that are not WCAG failures:**
   - the last timeline tick label is cut at the right edge (the same time is in the cursor readout and tables);
   - the sidebar's H2 headings come before each view's H1 in DOM order;
   - the disabled "Analyse site" button is dimmed (inactive controls are exempt from 1.4.3);
   - a few SVG axis labels still use #7d8d9d (4.78:1, passes).

## Not done here

- **Validation report:** writing a `frontend_u04` result and merging it with `run_validation` reruns pytest and updates `backend/validation/report.json`, so it awaits approval.
- **U-06 (performance)** was not started.

## Contents

| Path | What |
| --- | --- |
| `audit-before.json`, `audit-after.json`, `audit-final.json`, `audit-release.json` (+ `.log`) | Full machine-readable audit of each run; `release` is the reported one |
| `screenshots/` | 95 PNGs: per view and run, the full page, the 320 px reflow, the text-spacing override, the 390 px mobile view, the invalid-coordinate state, 14 crops of date-field focus stops from the `final` run (`final-noindicator-*`, showing Chrome's own ring on the calendar button before fix #8 was completed), and `release-detail-map-3d-panes.png` (view buttons and marker halo) |
| `logs/` | typecheck, `npm test` and build logs (`01–03` first fix pass, `04–06` second pass, `07–09` release); `check_a11y_report.json` (all colour pairs with ratios); `check_a11y_selftest.json`; `check_strings_report.json`; `dist_*_sha256.txt`; `backend_fingerprints_after.txt`; `u04_files_sha256.txt` |
| `content_preservation/` | visible-text and markup comparison against the source before the cleanup and U-04 |
| `u04_frontend_src.diff` | source diff against `frontend/src` as it was before the hackathon cleanup and U-04 (it therefore also contains that cleanup's 2-line hint removal) |
