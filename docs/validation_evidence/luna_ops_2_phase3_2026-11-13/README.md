# LUNA-OPS 2.0, Phase 3: Scientific Intelligence and Analysis Workspace (2026-11-13)

**Status: implemented.** Type checks, frontend tests, the production build, the bundle check and short visual previews are recorded here. Comprehensive browser checks and audits are deferred to Phase 5 (see "Outstanding verification").

## Approved decisions
1. **Sunlight and Earth visibility:** separate sections, each using one reusable chart.
2. **Analysis 3D terrain:** cells without data are left as gaps; they are no longer filled with the window's lowest height.
3. **Comparison matrix:** the existing better/worse shading is kept.
4. **Comparison charts:** a sunlight-versus-Earth-visibility scatter, a grouped bar chart and side-by-side site cards are added. No combined score is formed anywhere.

**Constraints:**
- frontend only: no backend, API, dataset or algorithm change, and the official validation report is unchanged;
- temporary files in `E:\Temp\LUNA-OPS`, one browser at a time;
- no Git, and the LUNA-OPS 1.0 backup was not touched.

## Baseline (saved before any source change)
`baseline/` contains:
- **`frontend/`:** a snapshot of the source and config, with `frontend_snapshot_SHA256SUMS`.
- **`frontend_files_sha256.txt`:** 69 files. It equals the Phase 2 final state.
- **`dist_sha256.txt`:** equals the Phase 2 final build.
- **`backend_fingerprints.txt`:**
  - algorithm 1.5.0;
  - code `84cbd4ea…`, suite `1632af16…`, terrain acceptance `e48eb8ed…`;
  - `report.json` `8c03ebaf…`.
- **`BEFORE_SCREENSHOTS.md`:** links to the latest "before" images of the result and comparison views (Phase 1).

**Earlier evidence:** the Phase 1 and Phase 2 evidence folders verified against their own `SHA256SUMS` before and after this phase.

## What changed

### Analysis workspace (`ResultWorkspace.tsx`, loaded when a result is first opened)
The sections, in order:
- **Header and labels:** the header, validation chips and data key, plus the site / observer / terrain context cards (unchanged).
- **Section navigation:** a strip of links to each section.
- **Window summary:** four figures (sunlight, direct-to-Earth, overlap, power indicator). They now show every summary field the API sends:
  - hours, windows and brief windows, longest window and gap;
  - unknown time and uncertain windows;
  - for power: the share of time with a known value, and the lower-bound note when the API sets `lower_bound`.

  Each figure also shows the validation status of the labels it rests on, in the API's words.
- **Sticky time bar:**
  - play;
  - previous and next event, which jump the cursor to the nearest display step;
  - the time-cursor slider;
  - the cursor time and the display step.

  Below it are the cursor readout (unchanged) and the countdowns, which now show the time of each next change.
- **Horizon panorama:**
  - **Size:** taller, with titled azimuth and elevation axes.
  - **Readout panel:** azimuth, horizon, ±1σ and near-field on hover or keyboard. At rest it shows the Sun and Earth position at the cursor, the horizon at the Sun's azimuth and the horizon range.
  - **Paths:** each path is drawn dashed where the API's clearance (`series.*.c < 0`) puts the body's centre below the terrain horizon, with a start marker on each path.
  - **Legend:** a shared legend.
  - **Unchanged:** keyboard operation and value text.
- **Event timeline:**
  - **Intervals and flags:** the same as before.
  - **Event markers:** a new row of rise/set markers with hover details.
  - **Event list:** all of the API's events, in time order, each with its time from the cursor (a difference of served times). Choosing one moves the cursor; it is a single Tab stop operated with the arrow keys.
- **Sunlight and illumination, and Earth visibility:** two instances of the reusable `VisibilityChart`. Each has:
  - an interval band (on / off / unknown hatched / uncertain dashed);
  - rise and set markers, plus Earth–Sun contact lines on the Sun chart;
  - the visible share of the disc, with gaps hatched and never interpolated;
  - a hover panel: time, visible share, elevation, azimuth, clearance, and the interval's state, span and flags;
  - a legend and a statistics panel. The panel shows every summary field: windows, longest window and gap, transitions, unknown time, uncertain windows and gaps, near-field windows, sub-bin windows and the mean visible Sun.
- **Terrain:**
  - **Map:** the analysis map gets the Phase 2 instruments, with its legend starting closed.
  - **3D terrain (`Terrain3D`):**
    - **gaps stay empty**, using the shared `lib/terrainStats.gridMesh` that the explorer also uses;
    - the same height colours;
    - controls with reset, an exaggeration selector and a legend (Sun and Earth directions, site, gaps, height bar);
    - a statistics card: product, heights, near the site, ground at the site, grid, and cells with data / gaps;
    - the WebGL context is now released on unmount (`forceContextLoss`, frame cancelled, geometry and materials disposed).
- **Validation and provenance:**
  - **Labels:** every label as a table with its kind, status and each test's status badge. The words are the API's own, so `passed` and `not run` stay distinct, and "Validated" appears only where the API says so. The reasons are listed too.
  - **Run provenance**, from `result.provenance`:
    - algorithm, code version and fingerprint, validation report hash, label rules digest;
    - kernels (profile, frame, coverage), horizon cache key, terrain interpolation;
    - aberration, refraction and Earth shape;
    - the result id and hash, and the terrain products used for the site.
- **Notes and tables:** unchanged.

### Comparison workspace (`CompareView.tsx`, `CompareCharts.tsx` lazy)
- **Builder and run:** restyled, with the same functions.
- **Provenance line:** the rules, panel model, observer and step from `comparison.base`.
- **Sites side by side:** one card per site for the chosen window. Each shows sunlit %, Earth in view %, both %, longest darkness, longest Earth gap, power indicator and unknown time, plus label counts and "Open full result". A cell without values reads "Unavailable".
- **Matrix:** unchanged in content (bars, better/worse shading, label counts, CSV), with window tags in the headers.
- **Bar chart:** the chosen metric for each site and window, with exact values. Percentages are drawn on 0–100 %; other metrics are scaled to the largest value. A cell without a value shows "Unavailable" and no bar.
- **Scatter:** sunlit % against Earth-in-view %, one point per site and window, with no combined score. Cells without both values are counted and not plotted.

### Shared pieces
- **`lib/timeAxis.ts`:** shared time axis and spaced ticks.
- **`lib/terrainStats.ts`:** `gridStats` and `gridMesh`, moved out of `TerrainPreview`.
- **UI components:** `ui/SectionHeader`, `ui/Metric`, `ui/StatusBadge`, `ui/ChartLegend`, `ui/ChartTooltip`.
- **Labels module:** `components/ResultLabels.tsx` (label chips and section ids, kept small for the mission dashboard).
- **Styles:** `styles/analysis.css`; the replaced result and comparison rules were removed from `views.css`.

### Other changes
- **`lib/format.ts` `fmtDuration`:** an exact zero now reads "0 min" instead of "<1 min". This affects every view, and is more accurate.
- **`MissionView.tsx`:** its jump to a result section waits up to about 5 s, up from about 1 s, because the workspace now loads on demand. No other change.
- **`MapView.tsx`:** new `legendOpen` prop.
- **`scripts/check-strings.mjs`:** the two allow-list entries (the API status-word prefixes) moved with `LabelChips` to `ResultLabels.tsx`.
- **Strings:**
  - **New:** the `analysis` section and the new comparison keys.
  - **Removed (no longer used):** `site.panoramaRegion`, `viz.visHeading`, `viz.visLabel`, `viz.visHover`, `viz.visNote` and the terrain glyph icons. They are replaced by the per-body chart texts and SVG icons.
  - **Unchanged:** scientific, validation and uncertainty texts.

## Files
See `logs/changed_files.txt`.

**Modified (15):**
- `src/components/`: `CompareView`, `HorizonPanorama`, `MapView`, `MissionView`, `ResultContext`, `SiteView`, `Terrain3D`, `TerrainPreview`, `Timeline`, `VisibilityChart`
- `src/i18n/en.ts`, `src/lib/format.ts`
- `src/styles/app.css`, `src/styles/views.css`
- `scripts/check-strings.mjs`

**Added (12):**
- `src/components/`: `CompareCharts`, `EventList`, `ResultLabels`, `ResultWorkspace`
- `src/lib/`: `terrainStats`, `timeAxis`
- `src/styles/analysis.css`
- `src/ui/`: `ChartLegend`, `ChartTooltip`, `Metric`, `SectionHeader`, `StatusBadge`

## Results

| Check | Result | Log |
| --- | --- | --- |
| TypeScript | exit 0 | `logs/05_typecheck.log` |
| `npm test` | exit 0. Strings: 862 keys, all referenced, 0 problems. Static a11y: 35 components, 52 colour pairs, 0 problems. Globe geometry: 238,972 checks passed. | `logs/06_npm_test.log` |
| Production build | exit 0 | `logs/07_npm_run_build.log` |
| Bundle | **initial JS 287.3 KB / 92.9 KB gzip**, below Phase 2 (329.2 / 103.7) because the workspace now loads on demand. Lazy JS is 1067.4 KB in 12 chunks. | `logs/08_check_bundle.log` |
| Short preview, one browser (one-week Site01 analysis, 2-site comparison; results served from the backend cache) | 36 screenshots; no sideways scroll at 1440, 1024 or 390 px; 0 console errors | `logs/11_preview_final.log`, `previews_final/` |
| Integrity spot checks in the preview | next-event moved the cursor to the next event (Earthrise, 20 Nov 10:30 step); the validation table keeps `passed` and `not run` distinct and shows "Validated" only for Sun and Earth positions, as the result's labels say; terrain card 100.0 % cells with data, no gaps; comparison 2 cards, 2 matrix cells, 2 scatter points | `previews_final/preview-phase3.json` |
| Backend and official report | unchanged (`logs/backend_fingerprints_after.txt` = `baseline/backend_fingerprints.txt`) | |

**Screenshots** (`previews_final/screenshots/`):
- **Each width (desktop, tablet, phone):** the top of the result, then summary, horizon, timeline, sunlight, Earth, terrain and validation; and the comparison cards, matrix and charts.
- **Desktop only:** the sunlight chart and horizon hover panels, and the comparison builder.

`previews_iter1/` holds the first build, before these fixes:
- the opaque time bar;
- "0 min" for exact zeros;
- the σ label shown uppercase as "Σ";
- the result-map legend overlapping the readout;
- phone tick spacing and timeline labels;
- the comparison bar labels on phones.

## Outstanding verification (deferred to Phase 5, not passed here)
1. **Live browser checks:** all eight still need to run on the Phase 3 build, including the map and end-to-end checks deferred since Phase 1. These assertions depend on the changed structure and need updating:
   - `viz-live-check`: one `.vis-chart` now holds one body (there are two charts); the hatch pattern ids are now `vis-hatch-sun` and `vis-hatch-earth`; the timeline legend has 11 items instead of 9; the panorama legend moved from `.panorama-head .legend` to `.panorama-legend`; the visibility readout text changed (`visReadout`).
   - **Hooks kept:** `.figure`, `.readout`, `.scrubber input[type=range]`, `#result-panorama`, `#result-timeline`, `#result-visibility`, `#result-terrain`, `#result-tables`, `.label-row .chip`, `.context-card` ×4, `.timeline-wrap svg title` (still one per interval: event markers use an HTML panel, not `<title>`), `.intervals tbody tr`, `table.matrix td button`, `.cell-bar`, `.cell-sub`, `.compare-legend`.
2. **U-04 audit:** new focusable controls change the expected Tab-stop counts:
   - section navigation links;
   - previous/next event buttons;
   - the event list (one stop);
   - legend summaries, terrain reset and exaggeration;
   - site-card buttons and the window selector.

   The analysis view's automated audit also needs re-running.
3. **Rendered contrast:** the status badges, the dashed "pending" and dotted "not run" styles, and the sticky time bar over content.
4. **Performance:**
   - long windows (for example a one-year run of about 17,500 samples), checking hover and playback smoothness;
   - first-open time of the lazy workspace chunk (64 KB, 17.5 KB gzip).
5. **Deep links:** mission dashboard deep links into the lazily loaded workspace (the longer wait is untested live).
6. **Terrain gaps:** the gap rendering in the analysis 3D terrain should be shown live on a window with missing data. The preview site had 100 % data, so it showed no gaps.

## Correction after acceptance: mobile sticky time bar (2026-11-13)
**Issue:** on phones (≤ 600 px) the sticky time bar wrapped into two tall rows (about 110 px). It covered section headings, and it was taller than the sections' 76 px scroll margin.

**Change:** styling only, in `src/styles/analysis.css` (the ≤ 600 px block). No other file changed: compare `logs/frontend_files_after_sha256.txt` with `logs/frontend_files_after_correction_sha256.txt`.
- **One compact control row** (play, previous event, slider, next event), with the cursor time and display step on a small line underneath. The controls and their order are the same as before.
- **Scroll margin:** sections scroll to 80 px from the top, so a heading reached by the section links or the dashboard lands below the bar.
- **Unchanged:** behaviour, timeline, values, and the tablet and desktop layouts.

**Results:**

| Check | Result | Log |
| --- | --- | --- |
| Production build (includes TypeScript and the string and a11y gates) | exit 0; strings 862 keys, 0 problems; a11y 35 components, 52 pairs, 0 problems | `logs/20_timebar_fix_build.log` |
| Bundle | initial JS 287.3 KB / 92.9 KB gzip (unchanged) | `logs/21_timebar_fix_bundle.log` |
| Short preview at 390 px (cached Site01 result; 1024 and 1440 px measured as controls) | **Phone:** bar 62 px (was about 110), stuck at the top; all 8 section links leave the heading below the bar; controls visible (play 32, previous/next 30 × 30 px, slider); next event still moves the cursor (14 Nov 00:00 → 20 Nov 10:30). **Tablet and desktop:** bar 54 px, single row, unchanged. No sideways scroll and 0 console errors. | `logs/22_timebar_preview.log`, `timebar_fix/timebar-check.json`, `timebar_fix/screenshots/` |
| Backend and official report | unchanged (`logs/backend_fingerprints_after_correction.txt` = baseline) | |

**Not changed:** the slider keeps the browser's default height (about 16 px), as before the correction. Its target size is part of the Phase 5 rendered audit.

## Known issues and notes
- **Sticky time bar on phones:** fixed by the correction above (62 px, headings clear).
- **Map hillshade texture:** the fine grid and radial texture in the server's hillshade at large zoom is unchanged (see the Phase 2 note).
- **Countdowns:** they remain lookups in the served intervals ("not in window" when no change occurs before the window ends).
- **Mission dashboard (Phase 4):** not redesigned; only the deep-link wait changed.
