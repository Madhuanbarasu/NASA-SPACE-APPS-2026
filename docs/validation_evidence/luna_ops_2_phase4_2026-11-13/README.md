# LUNA-OPS 2.0, Phase 4: Mission Dashboard (2026-11-13)

**Status: implemented.** Type checks, frontend tests, the production build, the bundle check and short visual previews are recorded here. Lengthy browser checks and audits are deferred to Phase 5. The approved plan is in `PLAN.md`.

## Approved decisions
1. **South polar locator:** a clearly labelled schematic SVG of the selected site, the candidate sites and the analysed locations. Candidate marks can be selected.
2. **Candidate cards:** each shows the latest analysis from this session (sunlit %, Earth-in-view %, its window and label status) alongside coverage. Unavailable values are never shown as measurements.
3. **Comparison panel:** sunlit % and Earth-in-view % side by side for every available comparison cell. The existing status is kept, and there is no combined score, ranking or probability.

**Constraints:**
- frontend only: no backend, dataset or algorithm change, and the official validation report and the LUNA-OPS 1.0 backup are untouched;
- temporary files in `E:\Temp\LUNA-OPS`, one browser at a time;
- no Git commands.

## Baseline
`baseline/` was saved before any Phase 4 change:
- **Frontend:** a snapshot and hashes. `frontend_files_sha256.txt` (81 files) equals the final Phase 3 state, including the mobile time-bar correction.
- **Build:** the dist hashes.
- **Backend:** the backend fingerprints with the `report.json` hash.
- **Before screenshots:** `BEFORE_SCREENSHOTS.md` links them.

## What changed (`components/MissionView.tsx`, `components/MissionLocator.tsx`, `styles/mission.css`)
**Unchanged logic:** the selection, analyse, open-result, deep-link (`focusWhenReady`) and coverage logic is the same code.

- **Status strip:** facts the app already holds.
  - kernels: profile, with the frame as a note;
  - LOLA terrain: product count, with the synthetic flag when set;
  - validation labels: validated and pending counts from `/api/status`;
  - candidate sites, and analyses this session;
  - comparison: size, running or none yet.
- **Quick actions:** the same five navigation buttons with icons, and the same targets and disabled rules.
- **Selected site:**
  - large monospace coordinates;
  - the coverage sentence (unchanged), plus coverage level chips from `/api/coverage` with the finest level marked;
  - the existing actions, job progress and errors.
- **South polar locator (`MissionLocator`):**
  - **What it plots:** the selected site (gold), the candidates (accent rings, as buttons with 24 px targets that select the site exactly like their Select button) and the other sites analysed in this session (grey).
  - **Projection:** radius proportional to the angular distance from the pole (azimuthal equidistant), with 0° E at the top and 90° E to the right, as on the south polar map.
  - **Extent:** adapts to the plotted sites (0.5°, 1°, 2°, 5°, 10°, 20° or 30° from the pole) and is stated in the note. Sites north of 60° S are counted as outside the plot.
  - **Labelling:** described as schematic, for orientation only. It computes no value for any site.
  - **Empty state:** it says that nothing is plotted yet.
- **Current analysis:**
  - the same label chips;
  - the same five figures (same fields and formatter, same dt/dd structure and labels), now as Sun, Earth and both tiles;
  - the same uncertainty items, highlighted;
  - **links to all eight Phase 3 sections:** Window summary, Horizon panorama, Timeline, Sunlight, Earth visibility, 3D terrain and map, Validation and provenance, and Events and data tables (Technical mode only).
- **Candidate sites:** cards with:
  - the coverage sentence (still the first hint), plus level chips;
  - **"Latest analysis in this session":** its window in UTC, sunlit % and Earth in view %, read from the stored session history like the history table, plus label counts. Without one, it says "Not analysed in this session." (or the running job's message);
  - the same actions.
- **System status:** the same readiness rows, plus one `StatusBadge` per label from `/api/status` in the API's words, and the same notes.
- **Analyses in this session:** the same table, restyled.
- **Comparison:**
  - the same status line;
  - **per-cell table:** site, window, sunlit % and Earth in view % under the comparison's own rules (named in the headers), and label counts. A cell with an error reads "Unavailable: <reason>"; a missing value reads "Unavailable".
  - a note that the two percentages are never combined, and the same link to the Compare tab.

**Kept test hooks:**
- section ids and `aria-labelledby`: exactly 6 h2 sections; the locator uses an `aria-label` and an h3;
- the classes `.mission-card`, `.mission-nav`, `.mission-figures div > dt/dd`, `.mission-flags li`, `.mission-links`, `.label-row .chip`, `.explorer-coords`, `.hint[aria-live]`, and `.mission-candidates li` (no nested list items, coverage first `p.hint`);
- the history `tbody tr`;
- the integrity line and the intro.

**Shared pieces:**
- `ui/Icon.tsx`: five icons (globe, map, terrain, chart, compare);
- `ui/ChartLegend.tsx`: a `dot` swatch;
- `i18n/en.ts`: new `mission` keys. `linkVisibility` now reads "Sunlight", because it opens the Sunlight section.
- The mission rules moved from `views.css` to `mission.css` (`app.css` imports it).

## Files
See `logs/changed_files.txt`.
- **Modified (6):** `src/components/MissionView.tsx`, `src/i18n/en.ts`, `src/styles/app.css`, `src/styles/views.css`, `src/ui/ChartLegend.tsx`, `src/ui/Icon.tsx`.
- **Added (2):** `src/components/MissionLocator.tsx`, `src/styles/mission.css`.

## Results

| Check | Result | Log |
| --- | --- | --- |
| Locator orientation against the map projection (proj4, 8 sites) | bearings identical (worst 2.3e-13°) | `logs/01_locator_orientation.log`, `scripts/locator_orientation_check.mjs` |
| TypeScript | exit 0 | `logs/05_typecheck.log` |
| `npm test` | exit 0. Strings: 899 keys, all referenced, 0 problems. Static a11y: 36 components, 52 colour pairs, 0 problems. Globe geometry: 238,972 passed. | `logs/06_npm_test.log` |
| Production build | exit 0. Dashboard chunk 20.8 KB / 6.4 KB gzip (was 12.9 KB); still loaded on demand | `logs/07_npm_run_build.log` |
| Bundle | initial JS 289.6 KB / 93.6 KB gzip (Phase 3: 287.3 / 92.9) | `logs/08_check_bundle.log` |
| Short preview, one browser: empty dashboard, then 2 candidates analysed (cached) and a 2 × 1 comparison (cached), at 1440, 1024 and 390 px | 15 screenshots; 0 console errors; no sideways scroll or overflow at any width; one column at 390 px | `logs/11_preview_final.log`, `previews_final/` |
| Spot checks in the preview | **Wording:** the restricted-words scan (score, probability, rank, recommend) found none. **Headings:** exactly 6 h2. **Links:** 8 analysis links (Technical). **Values:** candidate cards' values equal the session history (100.0 % / 0.0 % and 66.5 % / 0.0 %, window 14–21 Nov), and the comparison cells equal the comparison (100.0 % / 0.0 %, 66.5 % / 0.0 %). **Locator:** choosing the other candidate's mark made it the selected site (dashboard and sidebar `-89.463163`, `222.510447`). | `previews_final/preview-phase4.json` |
| Backend and official report | unchanged (`logs/backend_fingerprints_after.txt` = `baseline/backend_fingerprints.txt`) | |

`previews_iter1/` holds the first build, before two fixes: the locator's longitude labels were clipped and overlapping, and there was no empty-locator note.

## Outstanding verification (deferred to Phase 5, not passed here)
1. **Live browser checks:** `mission-live-check` and the other seven live checks on the Phase 4 build. These expected changes need the check updated:
   - **Public mode:** 7 section links instead of 4 (all eight Phase 3 sections minus the data tables).
   - **Link labels:** "Visibility chart" is now "Sunlight".

   The other assertions use kept hooks.
2. **U-04 audit:** new focusable controls change the expected Tab counts: locator marks (one per candidate that is not selected) and three more section links. The automated audit of the dashboard needs re-running.
3. **Rendered contrast:** level chips, status badges and the locator over the dark panel.
4. **Locator at scale:** behaviour with many candidates or sites far apart (extent 10–30°), and with sites north of 60° S. Only the near-pole case was previewed.

## UI corrections after review (2026-11-13)
These are three issues found in the owner's review, fixed with frontend and CSS changes only. Measured before and after with `scripts/ui_fixes.mjs` (one browser, cached Site01 result):
- **Before:** `ui_fixes_before/`, `logs/30_ui_fixes_before.log`.
- **After:** `ui_fixes_after/`, `logs/33_ui_fixes_after.log`.
- **Build:** `logs/31_ui_fixes_build.log`, exit 0 (strings 899 keys and a11y 36 components / 52 pairs, both 0 problems).
- **Bundle:** `logs/32_ui_fixes_bundle.log`, initial JS 290.4 KB / 93.8 KB gzip.

**Files changed:** see `logs/frontend_files_after_ui_fixes_sha256.txt` compared with `logs/frontend_files_after_sha256.txt`.
- `src/components/DataView.tsx`
- `src/components/GuideView.tsx`
- `src/styles/views.css`
- `src/styles/analysis.css`

The backend and the official report are unchanged (`logs/backend_fingerprints_after_ui_fixes.txt` = baseline).

### 1. Data and validation: the validation report table
**Root cause:** a Phase 1 rule, `.prose table.data td, th { overflow-wrap: anywhere }`, lets every cell break between any two characters, so tables fit at 320 px. With automatic table layout, the browser then shrank the short Status column to its minimum, one character, and gave the width to the long text columns.

**Measured before (1440 px):**
- column widths: Test 154, What it checks 69, Status 36, Detail 792 px;
- **all 424 statuses wrapped** ("passed", "not run", "skipped");
- at 390 px the columns were squeezed into 356 px.

**Correction:**
- **Table:** class `validation-tests`, fixed table layout with `min-width: 760px`.
- **Column widths:** Test 7.5rem (no wrap), What it checks 30 %, Status 7.5rem (no wrap), Detail the rest.
- **Wrapping:** normal word wrapping, except Detail, which keeps break-anywhere for long values.
- **Statuses:** single-line `StatusBadge`s (`white-space: nowrap`) with the backend's own words (`passed`, `not run`, `skipped`). The badge only picks a style; the old inline colour (green, orange or muted) is replaced by the badge style.
- **Labels table:** the same treatment (class `validation-labels`, `min-width: 520px`, normal wrapping, status badges), because it had the same mid-word breaks on phones ("Geometri c").
- **Narrow screens:** both tables keep their minimum width and scroll sideways inside their own box.

**Measured after:**
- **1440 px:** 120 / 315 / 120 / 495 px, with **0 of 424 statuses wrapping**.
- **390 px:** the same column widths, the table scrolls sideways inside its box (760 px in a 356 px box), and 0 wrap.
- No sideways scroll of the page.

### 2. Analysis result (custom site): blank space under the South Polar Map
**Root cause:** in the terrain section, the map pane and the 3D terrain pane share a grid row (`.grid-2`), which stretches both cells to the taller pane. Phase 3 added a statistics card under the 3D view, so that pane became taller. The map pane stretched with it, but its map stage had a fixed height (`.terrain-grid .pane-body { flex: none; height: clamp(360px, 52vh, 520px) }`), which left empty space under the map caption.

**Measured before:**
- **1440 px:** map pane 782 px, map stage 468 px, **223 px blank** under the caption.
- **1024 px:** **239 px blank**.
- **390 px:** one column, no blank space.

**Correction:**
- **Stage sizing:** `.terrain-grid > .pane > .pane-body.map-stage { flex: 1 1 auto; height: auto; min-height: clamp(360px, 52vh, 520px) }`. The map stage now fills its pane and never drops below its former height.
- **Map rendering:** OpenLayers (`ResizeObserver`) follows the new size and shows more of the same map at the same scale, so nothing is cropped or distorted.
- **Unchanged:** the controls, coordinates, scale, legend and tiles.

**Measured after:**
- **1440 px:** stage 690 px, **1 px** below the caption (the border).
- **1024 px:** stage 637 px, **1 px** below the caption.
- **390 px:** unchanged (stage 439 px).
- All map instruments are present at every width.

### 3. Guide: page alignment and content width
**Root cause:** the Guide used `<article className="prose">` (`max-width: 900px`), while Data and validation uses `prose prose-wide` (`max-width: 1140px`).

**Measured before:**
- **1440 px:** Guide 900 px wide against Data 1100 px; headings and text 852 px against 1052 px.
- **1024 px:** 900 px against 1024 px.
- **390 px:** the same width.

**Correction:**
- **Container:** the Guide now uses the same container as Data and validation, `prose prose-wide`.
- **Typography and layout:** the same `.prose` rules (header, h2 markers and dividers, paragraphs, definition lists), the same left edge and the same maximum width.
- **Unchanged:** text, section order and behaviour. No text was stretched beyond the shared 1140 px container.

**Measured after:** Guide and Data are identical at every width.

| Width | Container left | Container width | Heading left | Text width |
| --- | --- | --- | --- | --- |
| 1440 px | 340 | 1100 | 364 | 1052 |
| 1024 px | 0 | 1024 | 24 | 976 |
| 390 px | 0 | 390 | 16 | 358 |

No sideways scroll and 0 console errors.

### Remaining limitations
- **Line length:** Guide paragraphs now have the same line length as Data and validation (up to about 1090 px of text at the widest). If a shorter reading measure is wanted, it should be set once for both pages.
- **Phone validation table:** the table scrolls sideways (by design), so the Status and Detail columns are reached by scrolling the table. Long Detail text makes some rows tall.
- **Not changed (outside these three issues):**
  - on phones, the analysis map's closed "Legend" button sits over the end of the scale text in the map readout (390 px; Phase 2/3 instrument layout);
  - the server's hillshade texture is unchanged.

## UI corrections after the second review (2026-11-13)
These are four issues from the owner's second review, fixed with frontend and CSS changes only. Measured before and after with `scripts/ui_fixes2.mjs` (one browser, cached results), at 1440, 1024 and 390 px, plus 360 and 320 px for the map:
- **Before:** `ui_fixes2_before/`, `logs/40_ui_fixes2_before.log`.
- **After:** `ui_fixes2_after/`, `logs/44_ui_fixes2_after.log`.

**Gates:**
- `logs/41_ui_fixes2_typecheck.log`: exit 0.
- `logs/45_ui_fixes2_npm_test.log`: exit 0 (strings 899 keys, 0 problems; a11y 36 components, 52 pairs, 0 problems; geometry 238,972 passed).
- `logs/42_ui_fixes2_build.log`: exit 0.
- `logs/43_ui_fixes2_bundle.log`: initial JS 290.4 KB / 93.8 KB gzip.

**Files changed:** see `logs/frontend_files_after_ui_fixes2_sha256.txt` compared with `logs/frontend_files_after_ui_fixes_sha256.txt`.
- `src/components/MissionView.tsx`
- `src/components/MissionLocator.tsx`
- `src/styles/mission.css`
- `src/styles/views.css`
- `src/styles/explorer.css`

The backend and the official report are unchanged (`logs/backend_fingerprints_after_ui_fixes2.txt` = baseline). "Blank below" means the distance from a card's bottom edge to the next card in its column; the grid gap is 16 px.

### 1 and 2. Mission Overview: blank space below Selected site and Candidate sites
**Root cause:** the dashboard used a 12-column grid with paired rows: Selected site (7 columns) beside the locator (5), and Candidate sites (7) beside System status (5). A grid row is as tall as its tallest cell, so the short card in each pair sat at the top of a much taller row. That held whether the cards stretched or, as here, were aligned to the start.

**Measured before:**

| State, width | Selected site: blank below (card height) | Candidate sites: blank below (card height) |
| --- | --- | --- |
| no candidates, 1440 | **446 px** (100) | **332 px** (143) |
| no candidates, 1024 | **463 px** | **395 px** |
| with a site, 2 candidates and a result, 1440 | **271 px** (254) | 16 px |
| with a site, 2 candidates and a result, 1024 | 271 px | **70 px** |

**Correction:**
- **One column of full-width sections,** each at its natural height: Current analysis, Candidate sites, Analyses in this session, Comparison.
- **The first band only** pairs content: a left stack (Selected site, then System status) beside the locator.
- **Locator:** its plot area fills the height of the left stack. The square inside is the largest that fits (`min(100cqw, 100cqh, 460px)`, container query units), so the marks, placed in percent of the square, stay exactly over the SVG positions.
- **Candidate cards:** each card in the grid takes its own height (`align-items: start`).
- **Nothing removed:** no content was removed and no filler was added. The section ids, the six h2, the `.mission-figures`, `.mission-links` and `.mission-candidates li` hooks, and every button are unchanged.
- **Reading order** is now: Selected site, System status, locator, Current analysis, Candidate sites, Analyses, Comparison.
- **Phones (≤ 900 px):** one column, with the locator plot as a fixed square (up to 360 px).

**Measured after:**
- **Every card:** 16 px below it (the grid gap) in all six cases (no candidates or populated, at 1440, 1024 and 390 px).
- **Locator height:**
  - 495 px with no candidates and 650 px populated, at 1440 px;
  - 520 and 692 px at 1024 px.
- **Layout:** one column at 390 px, and no sideways scroll.

### 3. Data and validation, and Guide: alignment when the Mission Parameters panel opens or closes
**Root cause:** both pages share `.prose.prose-wide` (`max-width: 1140px`, no horizontal centring). With the panel docked at 1440 px, the workspace is 1100 px and the container fills it. With the panel collapsed, the workspace becomes 1440 px, but the container stayed 1140 px wide and pinned to the left, leaving **300 px unused on the right**. The 1024 px drawer overlays the page (no reflow) and was already correct.

**Correction:** `margin-inline: auto` on the shared container.
- **Up to 1140 px of workspace:** it fills the workspace as before.
- **Wider workspace** (panel collapsed or a wide screen): it is centred.
- **Unchanged:** both pages keep identical alignment, and headings, paragraphs, tables and dividers stay on the same grid. No content is clipped.

**Measured after:**

| State | Workspace | Container left | Container width | Gaps (left / right) | Heading left |
| --- | --- | --- | --- | --- | --- |
| 1440 px, panel docked | 1100 | 340 | 1100 | 0 / 0 | 364 |
| 1440 px, panel collapsed | 1440 | 150 | 1140 | **150 / 150** (was 0 / 300) | 174 |
| 1024 px, drawer closed and open | 1024 | 0 | 1024 | 0 / 0 | 24 |
| 390 px | 390 | 0 | 390 | 0 / 0 | 16 |

The results are identical for Data and validation and for the Guide. There is no horizontal overflow, in the page or inside the workspace, in any state.

### 4. South Polar Map: Legend button over the scale on phones
**Root cause:**
- **Overlap:** on phones the map's readout (pointer or selected site, plus the scale bar) sat in the bottom-left corner and the Legend button in the bottom-right, with the readout set never to wrap. On a narrow map they met: on the analysis map at 390 px the Legend button covered 1,806 px² of the readout, 853 px² of it over the scale bar.
- **Overflow at 320 px:** the readout was wider than the map, which caused sideways page scrolling on the analysis map, and the readout also ran past the edge of the explorer map.

**Correction (≤ 600 px, explorer and analysis maps):**
- **Readout:** spans the bottom of the map (8 px from each edge) and wraps.
- **Legend button:** moves to the top-right corner, with a 32 px summary target.
- **Tile-status chips:** move below the Legend button.
- **Unchanged:** zoom, show-whole-map, centre-on-site, the coordinate readout, the scale and the legend's contents.

**Measured after:**
- **Overlap:** Legend against readout and against scale is 0 at 390, 360 and 320 px on the explorer map, and at 390 and 320 px on the analysis map.
- **Readout:** inside the map at every width.
- **Page:** no sideways scroll, and 0 console errors.

### Remaining limitations
- **Centred documents:** with the panel collapsed, Data and validation and the Guide are centred (150 px on each side at 1440 px), while the other tabs use the full width. This keeps the shared 1140 px reading width; widening it further would lengthen lines past what the first review asked to avoid.
- **Locator inner space:** where the left stack is taller than the locator's width allows, the locator's square is centred in its plot area, with some space above and below it inside the card. At 1440 px with a result: the plot area is about 530 px tall and the square about 400 px.
- **Open legend on phones:** when opened, the map legend now unfolds downward from the top-right corner and covers part of the map until it is closed again (it is a disclosure).

## Known issues and notes
- **Status vs result labels:** the status strip's label counts (from `/api/status`: 2 validated, 3 pending) differ from a result's labels (here 1 validated, 4 pending). The result labels depend on the site, such as horizon uncertainty under the L_corr assumption. Both are shown as the API gives them.
- **"Custom site" title:** the current-analysis title shows "Custom site" with the coordinates when a site has no name (unchanged behaviour).
