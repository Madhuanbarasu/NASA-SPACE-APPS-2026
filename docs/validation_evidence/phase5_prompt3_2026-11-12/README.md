# Phase 5, Prompt 3: scientific visualisation integration (2026-11-12)

**Status:** implemented and tested; frontend only.
- **Visualisation check:** 25/25 live checks compare the page with the API's own result objects.
- **Regression:** globe 31/31 and explorer 27/27; existing analysis, comparison, map, local 3D terrain and accessibility unchanged apart from documented additions.
- **Unchanged:** no backend, scientific calculation, label or validation result changed; the fingerprints and `report.json` (`2279606c…`) are unchanged (§6).

## 1. What was improved (existing components reused; every value read from the result object)

| Area | Change | Data used |
| --- | --- | --- |
| **Data classes** | New "How to read this result" key (`DataKey`) under the validation chips. It explains **Calculated** (engine outputs, carrying the Validated/Pending labels), **Measured input** (registered LOLA heights and error maps), **Illustrative** (3D lighting, globe imagery, colours, exaggeration) and **Unavailable** (hatched, gaps, n/a; never filled). Matching tags appear on the context cards. | none |
| **Site, observer and terrain** | New context cards (`SiteContext`). **Site:** coordinates (shared formatter), signed form, ground height above the 1737.4 km sphere and the terrain level at the site. **Observer and window:** observer label and height, UTC window, display step. **Horizon:** range over its bins, complete or % lower bounds, near-field share, whether a σ exists (with the L_corr caveat). **Terrain used:** every level the horizon used, with pixel size, reach and product name. | `site`, `window`, `series.step_s`, `horizon`, `provenance.parameters.observer`, `provenance.horizon.levels` |
| **Sunlight vs Earth visibility** | New `VisibilityChart`: the calculated visible share of the **Sun's disc** and of **Earth's disc** at every display step, in two separate panels on one UTC axis. Step rendering; null values shown as hatched gaps, never interpolated; axis labels and units; a live readout; click moves the shared time cursor (keyboard equivalent: the time slider). | `series.sun.f`, `series.earth.f`, `series.utc/et` |
| **Event timeline** | Every interval, **including dark/out-of-view and unknown periods**, has a tooltip: row, state, UTC start and end, duration, and the engine's flags (uncertain with reasons, near field, brief, sub-bin peak true/unknown). These Phase 2/3 fields had been marked "display planned for Phase 5" in the result type. A legend explains all nine encodings, and a new **Intervals** table gives keyboard and screen-reader users the same information. | `intervals[*]` incl. `uncertain_reasons`, `near_field`, `subbin_peak`, `brief`, `state` |
| **Horizon panorama** | The readout keeps its text and appends the bin's **±1σ** and a **near-field** flag where the result has them; near-field bins are marked along the azimuth axis. The legend adds "Horizon ±1σ (L_corr assumption)" and "Near-field bins", shown only when present. | `horizon.sigma_deg`, `horizon.near_field` |
| **Terrain ↔ analysis** | The context cards tie the analysis to the actual terrain products and their reach. The Prompt 2 local terrain preview and the result's `Terrain3D` are unchanged and remain connected through the shared site. | as above |
| **Site comparison** | Each result cell shows a magnitude bar (0–100 % for percentages, otherwise relative to the largest value in the table) and its **validation label counts** ("1 validated, 4 pending"). A colour-scale legend shows the actual range and direction ("higher/lower is better"), with a note on how bars and shading differ. | `cells[*].summary`, `cells[*].labels` |

**Consistency:**
- **Colours:** Sun gold, Earth blue, both cream, unknown hatched orange, cursor pale gold, near field violet. They are the same in the panorama, timeline, chart and legends.
- **No motion:** no animation was added, so reduced-motion behaviour is unchanged.
- **Reflow:** the context cards reflow 4 → 2 → 1 columns, and the chart and timeline scale to width.

## 2. Scientific accuracy
- **Nothing computed:** nothing is calculated in the browser beyond formatting, layout and bar lengths; all values are fields of the API result (blueprint C09).
- **Gaps stay gaps:** missing values (null fractions, unknown intervals, lower-bound horizon bins) are drawn as gaps or hatching and listed as "unknown". They are never filled or interpolated.
- **Labels unchanged:** labels are shown exactly as the API gives them. The comparison counts them from each cell's labels. Nothing is upgraded: in the tested results the four terrain-dependent quantities are Pending, and only Sun and Earth positions are Validated, exactly as the API reports.
- **Uncertainty is qualified:** σ is shown with its L_corr caveat, and near-field dependence is flagged.
- **Illustrative content is labelled:** imagery and lighting are labelled illustrative (key, globe, terrain views).

## 3. Results

| Check | Result | Evidence |
| --- | --- | --- |
| TypeScript | exit 0 | `logs/00_typecheck.log` |
| `npm test`: strings (593 keys, 0 problems; self-test 38/38), static a11y (20 components, 0 problems; self-test 15/15), geometry (238,972) | exit 0 | `logs/01_npm_test.log` |
| Production build; bundle split | exit 0; three.js still lazy; initial JS 322.1 KB / 101.6 KB gzip (+15.6 / +4.3 KB over Prompt 2, the new result-view components) | `logs/02_npm_run_build.log`, `logs/03_check_bundle.log` |
| **Visualisation live check** (`scripts/viz-live-check.mjs`) | **25/25** | `logs/04_viz_live_check.log`, `viz_check/viz-check.json`, `viz_check/screenshots/` |
| Explorer regression (Prompt 2 check) | 27/27 | `logs/05_explorer_live_check.log` |
| Globe regression (Prompt 1 check) | 31/31 | `logs/06_globe_live_check.log` |
| **Full live U-04 audit** (Site01 analysis, local 3D terrain, map, 2 × 2 comparison, Data, Guide) compared with the U-04 release run | **0 problems in all six views; functional tests unchanged** | `logs/07_audit_a11y.log`, `a11y_regression/`, `logs/08_a11y_regression_compare.log` |

**What the 25 visualisation checks compare** (with `GET /api/results/{id}` fetched in the same page):
- **Site01, 14–21 Nov:**
  - every context value equals the API result: coordinates, ground 1944.8 m (5 m), observer, window and step, horizon −2.17° to 4.74°, 44.2 % near field, σ statement, all four terrain levels;
  - the label chips equal the API labels (1 Validated, 4 Pending);
  - the chart draws gaps only where the API has nulls (none here);
  - clicking the chart moves the shared cursor;
  - all timeline intervals have tooltips, and the intervals table lists them with the API's near-field flag;
  - the panorama readout gives the API's horizon and σ (e.g. "Az 200.0° horizon 0.02° ±0.08° (1σ)").
- **Date switching:** Site01 13–20 Dec gives a new window and chart.
- **Site switching:** (−89.9°, 0°) gives a new site card (ground 628.0 m, 20 m).
- **Missing data, a real case at (−60.02°, 0°):**
  - the 240 m terrain ends about 2 km to the north, so 49.6 % of horizon bins are lower bounds;
  - the context and legend say so;
  - the API's 50 null Earth fractions appear as a hatched gap;
  - the unknown interval is hatched in the timeline and listed as "unknown";
  - the labels stay Pending exactly as the API gives them.
- **Unsupported location:** (−30°, 10°) has analysis disabled, with the backend's reason.
- **Comparison (2 × 2):**
  - a bar and label counts in every cell;
  - the legend scale "1.3% to 100.0% (higher is better)";
  - for Longest darkness: "6 d 21 h to <1 min (lower is better)";
  - opening a cell shows its full result with context and chart.
- **Layout:** at 390 px there is no sideways scroll and the cards stack.
- **Errors:** no page exceptions or console errors.

**Accessibility regression** (`logs/08_a11y_regression_compare.log`), with intentional differences only:
- **Tab stops:** welcome +2 (Prompt 1 switch); result view +3 (Prompt 2 back button, the data-key disclosure, the intervals toggle).
- **Panorama readout:** the release text is kept, with σ and near field appended ("Az 264.0° horizon −1.55° ±0.09° (1σ) near field").
- **Functional tests:** all other functional tests are identical.

## 4. Notes from testing
- **Accessibility audit compatibility:** the audit expands the Events and Series tables by clicking the first `.toggle-table` button labelled "Show". The new intervals toggle therefore uses its own class (`toggle-intervals`, same look), so the audit's walk is unchanged.
- **Finding a real missing-data case:** the 60°S coverage boundary does not always produce missing data. At (−61°, 30°) the horizon was complete. A real missing-data case was found at (−60.02°, 0°), next to the edge of the registered 240 m terrain.
- **Existing `Terrain3D` quirk (not changed):** in the existing result-view `Terrain3D`, when no single product covers the 8 km window, the backend's message is shown but the Earth marker is still drawn over it (`screenshots/05-edge-site-60S-missing-data.png`). It is outside this prompt's scope and left as is.

## 5. Limitations
- **Bar meaning:** comparison bars show magnitude; for lower-is-better metrics, better cells have shorter bars. The legend and note say so.
- **Chart resolution:** the visibility chart shows display-step samples; event times between steps are in the timeline, events table and intervals table.
- **Browser coverage:** tested in Chrome 157 headless only.
- **Official report:** U-04 and U-06 there still describe the pre-Phase 5 build; re-registration is recommended, as noted in Prompts 1 and 2.

## 6. Files changed
| File | Change |
| --- | --- |
| `frontend/src/components/ResultContext.tsx` | **new**: `DataKey`, `SiteContext` |
| `frontend/src/components/VisibilityChart.tsx` | **new**: Sun and Earth visible-disc chart |
| `frontend/scripts/viz-live-check.mjs` | **new**: live check against the API result objects |
| `frontend/src/components/Timeline.tsx` | tooltips for every interval, flag texts (`intervalNotes`), legend, intervals table |
| `frontend/src/components/HorizonPanorama.tsx` | σ and near-field readout, near-field bin marks |
| `frontend/src/components/SiteView.tsx` | data key, context cards, visibility chart, panorama legend items |
| `frontend/src/components/CompareView.tsx` | cell bars, label counts, scale legend and note |
| `frontend/src/i18n/en.ts` | `viz` section and panorama additions (519 → 593 keys) |
| `frontend/src/styles/app.css` | tags, context cards, legend swatches, chart, comparison bars and legend |
| `frontend/scripts/check-a11y.mjs` | pointer allow-list entry for the chart (click-to-seek; keyboard equivalent: the time slider), as for the timeline |
| `frontend/scripts/check-strings.mjs` | allow-list entry for the API status word "Validated" compared in CompareView (as already for SiteView) |
| `frontend/dist/` | rebuilt; hashes in `logs/dist_before_sha256.txt` and `logs/dist_after_sha256.txt` |

**Not changed:**
- backend code;
- algorithm 1.5.0, code `5bf9753f…`, suite `1632af16…` and terrain acceptance `e48eb8ed…` (`logs/backend_fingerprints_after.txt`);
- `backend/validation/report.json` (`2279606c…`);
- Phase 4 and Prompt 1/2 evidence (checksums verified);
- `package.json` and the lock file.

No dependency was installed and no Git operation was run.
