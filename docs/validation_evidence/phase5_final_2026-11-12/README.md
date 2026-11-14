# Phase 5 final: integration and release verification (2026-11-12)

**Verdict: COMPLETE WITH APPROVED DEFERRALS.** The justification is in `COMPLETION_REPORT.md`. Frontend only.
- **Unchanged:** backend code, algorithm 1.5.0, every fingerprint and `backend/validation/report.json` (`2279606c…`).
- **Not merged:** the refreshed U-04 and U-06 result files are prepared but not merged, because merging needs explicit approval.

## 1. Final integration

| Item | Result |
| --- | --- |
| **Phase 5 review** | The 3D Moon, South Pole Explorer, local terrain preview, scientific visualisations and mission dashboard were re-checked together. All earlier browser checks pass on the final build (§3), and a new end-to-end check runs the whole workflow (`frontend/scripts/e2e-live-check.mjs`). |
| **Navigation, selected site, coordinates** | The globe pick at the South Pole gives (−89.9, 0) in the sidebar, explorer and dashboard. The analysis is for exactly those coordinates. The globe check (31/31) and explorer check (27/27) cover the conversion edge cases. |
| **Result preservation (new)** | Leaving a result for the explorer (Back button, dashboard navigation) now *parks* it, with its time cursor, instead of discarding it. The explorer offers "Return to the result for …"; the dashboard shows it as kept, and Analysis or a deep link returns to it. The end-to-end check confirms the same result id and the same time step (57), and that no second `/api/results` request is made. |
| **Session list (improved, safely)** | The list of analyses is kept in this browser tab's `sessionStorage` and is cleared when the tab closes. It is restored only when the backend's code fingerprint and the validation report time equal those saved with it; otherwise it is discarded, so restored figures and labels can never be stale. Results are reopened from the server's on-disk cache; one that no longer exists is reported in place ("could not be opened … Run the analysis again"). All of this is checked live: reload restores, another build discards, a real 404 is reported. Comparisons are held in server memory and are not persisted. |
| **UI defects fixed** | (1) **Coordinate names:** the sidebar's "Add to comparison" named coordinate-only sites in a signed format (`-89.463°, 222.510°`), different from every other view (`89.463° S, 222.510° E`), so mixed formats appeared in the comparison, result titles, candidate cards and session table. It now uses the shared formatter, and the dashboard also tolerates names in the old format. (2) **Curated names:** after a curated site was chosen, typing new coordinates kept the curated site's name, so an analysis of other coordinates would carry that name; the name is now cleared (a name the user typed is kept). (3) **Open errors:** opening a result that fails is now caught and shown instead of becoming an unhandled promise rejection (store `openResult` returns false and sets the error). |
| **Desktop and mobile** | No sideways scrolling on any of the five tabs at 1440, 390 and 320 px (end-to-end check), and 320 px reflow in all ten audited views (U-04, §2). |

## 2. Accessibility (U-04) and performance (U-06)

### U-04: re-evaluated on the final frontend (criteria and scope of D4)
**Audit:** `npm run audit:a11y` (`frontend/scripts/a11y-live-audit.mjs`), extended this time with four Phase 5 views after the unchanged release scenario. Chrome 157.0.8103.51 headless; real Site01 analysis and 2 × 2 comparison. Comparator: `u04_compare.py` → `logs/11_u04_compare.log`.

| View | Tab stops (release → now) | Automated problems |
| --- | --- | --- |
| site-welcome | 34 → 36 (+2, prompt 1 view switch) | 0 |
| site-result-technical | 52 → 55 (+3, prompts 2–3) | 0 |
| site-result-public | – | 0 |
| compare-matrix | 76 → 76 | 0 |
| data | 34 → 34 | 0 |
| guide | 33 → 33 | 0 |
| **site-explorer-globe** (new) | 55, walk cycled | 0 |
| **site-explorer-terrain** (new) | 48, walk cycled | 0 |
| **mission** (populated, new) | 55, walk cycled | 0 |
| **mission-empty** (fresh page, new) | 35, walk cycled | 0 |

**Automated columns per view:**
- unnamed controls and images;
- focusable elements without a widget role;
- text contrast (every visible text node);
- target size (24 px with the spacing exception);
- missing, clipped or obscured focus indicator;
- 320 px horizontal scroll and overflowing elements;
- text-spacing clipping;
- unlabelled form controls, duplicate ids, `role=application`.

**Functional tests:**
- **Release tests (16):** all the same as the U-04 release run. The panorama readout keeps the release text with σ and near field appended (documented in Prompt 3).
- **Phase 5 tests:**
  - the globe is keyboard-operable (rotate, zoom);
  - the local terrain is keyboard-operable (pan, rotate, zoom);
  - the explorer offers the kept result;
  - a dashboard deep link moves focus to its section.

**Audit-tool note:** in a trial run the terrain view counted 196 Tab stops. The walk started at the last clicked control inside the scrolling main area, so its identity (element plus position) changed between laps and the walk never closed. For the four Phase 5 views the walk now starts at the top of the page. The six release views keep their original walk for comparability.

**Scope and limits (unchanged from D4):**
- Chrome/Chromium only;
- no real screen-reader user session (the accessibility tree was inspected);
- zoom emulated through the viewport;
- speech input not tested.

This is **not a claim of unrestricted WCAG 2.2 AA conformance.**

### U-06: re-measured on the final production build (criteria of D3)
**Setup:**
- **Script:** `frontend/scripts/perf-audit.mjs`, with the same laptop (HP 15-fd0xxx, Core 5 120U, Windows 11), Chrome 157 headless on the real GPU (ANGLE D3D11), 1440 × 900.
- **Profiles:** the same three as D3.
- **Runs per profile:** 3 cold + 2 warm loads; the interaction workflow on native and 4× CPU; 5 remount cycles with forced GC (native).
- **Blocked tiles:** the same two slow tiles as in D3.
- **Server:** freshly started.
- **Phase 5 supplement:** a new `--phase5 1` option adds Mission tab, globe and local-terrain timings, Event Timing on globe and terrain keyboard steps, and globe and terrain remount cycles.

**Evaluation:** `u06_evaluate.py` → `u06_perf/summary-final.json` and `summary-repeat.json`.

| D3 criterion | native | 4× CPU | 4× CPU + 10 Mbit/s | Met |
| --- | --- | --- | --- | --- |
| LCP ≤ 2.5 s (worst run; first set / repeat) | 540 / 520 ms | 1,728 / 988 ms | 1,332 ms | yes |
| CLS ≤ 0.1 (worst run) | 0 | 0 | 0 | yes |
| Interaction p95 ≤ 200 ms (Event Timing, 20 keyboard steps; first / repeat) | 56 / 32 ms | 88 / 64 ms | not measured (as in D3) | yes |
| No progressive leak (5 remounts, forced GC) | +0.3 MB, +5 nodes, +5 listeners, no warnings (both sets) | – | – | yes (rule below) |
| TBT (information only), cold / warm median | 0 / 0 ms | 510 / 602 ms; repeat 350 / 534 ms | 417 / 544 ms | not gated |

**Phase 5 supplement** (outside the D3 scope, reported only):

| | native (first / repeat) | 4× CPU (first / repeat) |
| --- | --- | --- |
| Mission tab switch | 38 / 62 ms | 155 / 146 ms |
| Open the globe: canvas / imagery | 251 / 250 ms; 400 / 398 ms | 874 / 302 ms; 919 / 356 ms |
| Open local terrain: canvas / data | 100 / 329 ms; 127 / 280 ms | 186 / 255 ms; 143 / 192 ms |
| Key-step p95: globe / terrain (upper bounds) | 40 / 24 ms; 56 / 32 ms | 64 / 40 ms; 48 / 24 ms |
| Remount heap growth: globe / terrain | +0.8 / +0.2 MB; +0.6 / +0.3 MB | +0.7 / +0.2 MB; +0.6 / +0.2 MB |

The key-step p95 values are upper bounds because only events of 16 ms or longer are recorded.

**Honest observations:**
- **Slower than the U-06 build:** the final build is slower than the accepted 2026-11-11 U-06 build, although every criterion is still met.
  - Native loads are similar except the first cold load of each run (about 520–540 ms, reproduced in both sets; the baseline worst was 192 ms).
  - At 4× CPU the repeat set's cold median FCP is 748 ms against 480 ms, and the Data tab switch takes 434 ms against 117 ms.
  - JavaScript transferred on a cold welcome load grew from 735 to 768 KB.
  - **The cause was not isolated.**
- **CPU contention in the first 4× CPU set:**
  - **Measurements:** script time about 2,000 ms per load against 830 ms in the baseline, with app-ready varying 1.8–3.7 s between identical loads. Native script time rose only about 15 % in the same set.
  - **Re-run:** both workflow profiles were therefore repeated on the warm server. The repeat's worst 4× CPU LCP is 988 ms.
  - **Both sets are kept.** The worst values above come from either.
  - **Machine load:** the desktop Chrome with many processes and other applications was running, as in the original U-06 audit.
- **Evaluator correction:**
  - **First version:** required all 20 keystrokes to appear in Event Timing, and reported the native first set as "not met" (`logs/13_u06_evaluate_first_rule.log`).
  - **Why that was wrong:** the browser records only events of 16 ms or longer. The 4 missing keystrokes were faster than 16 ms, so the p95 over the 16 recorded (56 ms) is an upper bound.
  - **Fix:** the rule was corrected and documented in the script; the original log is kept.
- **Memory rule:** D3 gives no number for "no progressive leak". Used here, as a stated and unapproved rule: growth no larger than the accepted baseline's (+0.3 MB, +5 nodes, +5 listeners) plus 1 MB, 50 nodes and 10 listeners, with no new console warnings.

**Scope and limits:**
- lab measurement on one laptop, in one engine;
- few samples;
- the slow-tile backend fix recommended in U-06 has still not been made (backend changes are out of scope);
- **not a field Core Web Vitals claim.**

### Result files (refreshed, NOT merged)
- **Files:** `frontend_u04_phase5.json` (U-04 passed) and `frontend_u06_phase5.json` (U-06 passed). They were written by `make_phase5_frontend_results.py` with the same schema and owners as the Phase 4 files.
- **Dry run:** both pass `merge_external` in an in-memory dry run against the live report with no rejection (`merge_dry_run_phase5.json`).
- **Not merged:** `report.json` was hashed before and after and is unchanged. Merging needs the project owner's explicit approval.
- **Build relationship:** both files bind the measured build and the release build. The release build differs only by the two added notice files (below).

## 3. Regression results (final build)

| Check | Result | Log |
| --- | --- | --- |
| TypeScript | exit 0 | `logs/00_typecheck.log` |
| `npm test`: strings 658 keys (0 problems; self-test 38/38); static a11y 21 components, 33 colour pairs (0; 15/15); geometry 238,972 | exit 0 | `logs/01_npm_test.log` |
| Production build; bundle | exit 0; initial JS 321.3 KB / 101.0 KB gzip; three.js still lazy | `logs/02`, `logs/03` |
| Mission dashboard check | 42/42 | `logs/04_mission_live_check.log`, `mission_check/` |
| Visualisation check | 25/25 | `logs/05_viz_live_check.log`, `viz_check/` |
| Explorer check | 27/27 (attempt 1: headless Chrome did not open its DevTools port within 20 s, so no test ran; log kept) | `logs/06_*` |
| Globe check; without WebGL | 31/31; 2/2 | `logs/07`, `logs/08` |
| **End-to-end check** (new) | **16/16** | `logs/09_e2e_live_check.log`, `e2e_check/` |
| U-04 audit; comparison | exit 0; no problem in 10 views | `logs/10`, `logs/11`, `u04_audit/` |
| U-06 runs (3 profiles + repeat of 2); evaluation | all complete; D3 met in both sets | `logs/12_*`, `logs/14_*`, `logs/13_u06_evaluate_final.log`, `logs/15_u06_evaluate_repeat.log`, `u06_perf/` |
| IB-5 shipped-set re-derivation; notices; rebuild | 26 packages, unchanged from IB-5; 26 licence files; exit 0 | `logs/16`, `logs/17`, `logs/18` |
| Result files and dry run | 0 rejections; `report.json` unchanged | `logs/19_make_phase5_frontend_results.log` |
| Previous evidence checksums | 10/10 folders verify | `logs/20_previous_evidence_checksums.log` |

**What the end-to-end check covers** (`e2e_check/e2e-check.json`):
- the dashboard's loading text on a slow connection;
- a globe pick reaching the same site in every view;
- local terrain;
- an analysis for exactly the picked coordinates;
- result preservation, through the dashboard and through the explorer;
- candidates → 2 × 2 comparison → cell result → dashboard;
- persistence across a reload; discard for another build;
- a real missing result (404);
- the status API unreachable;
- no sideways scrolling on any tab at three widths;
- no console errors.

Missing-data (−60.02°, 0°) and unsupported-location (−30°, 10°) states are covered by the mission and visualisation checks.

## 4. Licensing (IB-5) and distribution
- **Shipped set re-derived:** with IB-5's own script (`vite_modules.mjs`, in-memory build, `dist` untouched). The same 25 JS packages plus the Archivo font ship as in the inventory (`ib5_review/vite_modules_final.json`).
- **Notices added only from verified texts:**
  - `frontend/scripts/gen-notices.mjs` writes `frontend/public/THIRD_PARTY_NOTICES.txt`: the full licence file of each of the 26 shipped packages, with name, version and declared licence. Declared licences match the IB-5 inventory. The script refuses to write if any package lacks a licence file.
  - `OFL.txt` is the Archivo package's own licence file, which contains the OFL 1.1 text.
  - Both are copied into `dist` by the build.
- **Release build vs measured build:** the release `dist` is byte-identical to the measured build except for the two added text files (`logs/dist_after_sha256.txt` vs `logs/dist_release_sha256.txt`).
- **Reference rasters:** `data/reference_validation/` is now in `.gitignore`. The files stay on disk.
- **Still unresolved, D5 deferral stands:**
  - 44 native-library licences in the Python wheels;
  - data terms for PGDA, PDS/LROC, JPL Horizons, NAIF, USGS and ShadowCam;
  - `lerc` (not shipped);
  - the GSFC figure acknowledgment.

  **No licensing clearance is claimed.**
- **Distribution restrictions** (README, Remaining limitations):
  - do not redistribute a packaged Python environment;
  - do not commit or redistribute `data/reference_validation/`;
  - publish `frontend/dist` only with `THIRD_PARTY_NOTICES.txt`, `OFL.txt` and `moon/ATTRIBUTION.txt`;
  - keep the Horizons and GSFC copies as evidence only;
  - do not distribute terrain, kernels or other data products.

## 5. Files changed in this step
| File | Change |
| --- | --- |
| `frontend/src/state/store.tsx` | parked result (`closeResult`, `restoreResult`); session list in `sessionStorage` tied to the build and report; `openResult` reports failures |
| `frontend/src/components/SiteView.tsx` | Back button parks the result |
| `frontend/src/components/SiteExplorer.tsx` | "Return to the result for …" |
| `frontend/src/components/MissionView.tsx` | shows a kept result; Analysis restores it; open errors shown in place; coordinate names; session-list note |
| `frontend/src/components/Sidebar.tsx` | coordinate names in the shared format; typed coordinates drop a curated site's name |
| `frontend/src/i18n/en.ts` | 4 new strings and one reworded (654 → 658 keys) |
| `frontend/scripts/a11y-live-audit.mjs` | Phase 5 views and tests (default; `--release-views-only` for the old scope); top-of-page walk for them |
| `frontend/scripts/perf-audit.mjs` | opt-in `--phase5 1` supplement (default method unchanged) |
| `frontend/scripts/e2e-live-check.mjs` | **new**: end-to-end check |
| `frontend/scripts/gen-notices.mjs` | **new**: third-party notices from the shipped packages' licence files |
| `frontend/public/THIRD_PARTY_NOTICES.txt`, `frontend/public/OFL.txt` | **new** (generated) |
| `.gitignore` | `data/reference_validation/` |
| `README.md` | Phase 5 section; IB-5 bullets updated (line 99 unchanged) |
| `docs/TRACEABILITY.md` | U-04, U-06, IB-5 rows; Phase 5 rows |
| `ATTRIBUTION.md` | redistribution findings updated |
| `docs/validation_evidence/README.md` | index row |
| `frontend/dist/` | rebuilt (hashes in `logs/`) |

**Not changed:**
- backend code;
- algorithm 1.5.0, code `5bf9753f…`, suite `1632af16…`, terrain acceptance `e48eb8ed…` (`logs/backend_fingerprints_after.txt`, identical to Prompts 3 and 4);
- `backend/validation/report.json` (`2279606c…`);
- all earlier evidence (checksums verified);
- `package.json` and the lock file.

No dependency was installed and no Git command was run.
