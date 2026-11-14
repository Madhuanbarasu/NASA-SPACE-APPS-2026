# LUNA-OPS 2.0, Phase 2: Immersive 3D Moon and South Polar Explorer (2026-11-13)

**Status: implemented.** Gates and short visual previews are recorded here. Lengthy browser checks and audits are deferred to Phase 5, as instructed; see "Outstanding verification".

## Approved decisions
- **Moon framing:** the complete disc at 90 % of the explorer stage height on the opening view (no cinematic crop). Manual zoom is kept.
- **Layout:** the readiness board and introductory steps move below the stage. The heading is compact and does not cover the Moon.
- **Baseline:** saved first, before any source change.
- **Constraints:**
  - frontend only: no backend, API, dataset or algorithm change, and the official validation report is untouched;
  - one WebGL view at a time, lazy loading kept, no new dependency;
  - temporary files on `E:\Temp\LUNA-OPS`, one browser at a time;
  - no Git operations, and nothing outside `E:\LUNA-OPS`.

## Baseline (saved before any change)
`baseline/` contains the following:
- **`frontend/`:** a copy of `src`, `scripts`, `public`, `index.html`, `vite.config.ts`, `package.json`, `package-lock.json` and `tsconfig.json`, with its own `frontend_snapshot_SHA256SUMS`.
- **`frontend_files_sha256.txt`:** 66 files. It equals the Phase 1 final `logs/frontend_files_after_sha256.txt`.
- **`dist_sha256.txt`:** equals the Phase 1 final build (`index-ZnayDHTI.js`, `index-DCMBg5-B.css`).
- **`backend_fingerprints.txt`:**
  - algorithm 1.5.0;
  - code `84cbd4ea…`, suite `1632af16…`, terrain acceptance `e48eb8ed…`;
  - `report.json` `8c03ebaf…`.
- **`BEFORE_SCREENSHOTS.md`:** links to the Phase 1 "after" screenshots, which serve as the Phase 2 "before" state, and the measured before-state layout.

## What changed

### 1. A much larger 3D Moon
**Explorer stage.** The Site tab (before an analysis) is now a stage that fills the workspace height under the command bar:
- **Height:** `100dvh − bar − 72 px` (with a `vh` fallback).
- **Title and site panel:** the compact title (the page's h1) and the selected-site panel sit beside the stage, so nothing covers the Moon.

**Whole-disc framing.** `MoonGlobe.fitDistance` sets the opening view, Reset, Home, Nearside and Farside:
- **Size:** the disc spans 90 % of the stage height, or 92 % of its width on portrait stages.
- **Formula:** `d = sqrt(1 + t²) / t`, with `t = f · tan(fov/2)`.
- **Proof:** checked against three.js's own projection (`scripts/globe_fit_check.mjs`, `logs/02_globe_fit_check.log`, worst error 1e-16).
- **Resizing:** a view still at the framing keeps it when the stage changes size; a view the user zoomed is left alone.

**On-screen disc, measured in the browser** (Even light, longest lit run through the stage centre):

| Screen | Before (Phase 1 final) | After |
| --- | --- | --- |
| 1440 × 900, parameters docked | about 545 px; stage starts at y ≈ 595, so about 45 % of it is above the fold | **688 px**, whole disc on screen (stage 752 × 768 at y = 119) |
| 1024 × 768 | about 545 px area, mostly below the fold | **568 px**, whole disc on screen (stage 696 × 636) |
| 390 × 844 | stage `clamp(300px, 70vw, 420px)` | **318 px** (92 % of the width) |

**Rendering:** quality, textures, lighting, geometry, the pole marks and the 60° S limit are unchanged.

### 2. Professional globe controls
- **Navigation cluster** (top right, floating, outside the disc): reset view (new as a button; Home already did it), turn north/south/east/west, zoom in/out, select the centre and centre on the selection. It uses SVG icons, with the same names and keyboard map as before.
- **Viewpoints** (top left): Nearside, Farside, North Pole, South Pole.
- **Display toggles** (Grid, Even light): bottom right.
- **Readout** (bottom left, monospace): the centre, then the pointer while hovering, or else the selected site in gold.
- **Legend:** a disclosure with the site-marker colours (covered / not covered / not checked), comparison candidates and the 60° S limit. It starts closed so it never covers the disc.
- **Smooth camera:**
  - drags have inertia (OrbitControls damping, rendered only while moving);
  - zoom buttons and Reset animate along the existing great-circle flight;
  - programmatic positions are applied exactly (`settle()` clears leftover inertia);
  - the keyboard + and − stay immediate, and reduced motion makes every move instant.
- **Comparison candidates:** shown as small accent rings on the globe.
- **Picking and targeting:** unchanged (`lib/moonGeo`, `siteCoords`).

### 3. South Polar Explorer (map)
The map fills the same stage: 752 × 768 at 1440 × 900, where it was 300–640 px tall below the fold. The explorer variant (`MapView instruments`) adds:
- **Pointer readout:** latitude and longitude, using the same inverse projection as a click, or "north of 60° S" outside the map.
- **Scale bar:** measured on the 1737.4 km reference sphere at the view centre. OpenLayers' scale line is not used because it assumes Earth's radius. Checked against the projection's exact point scale: worst relative difference 2.8e-4, from the ±50 px finite chord (`scripts/map_scale_check.mjs`, `logs/01_map_scale_check.log`).
- **New buttons** under the zoom: "Show the whole south polar map" and "Centre the map on the selected site".
- **Tile status chips:** loading, composed from finer tiles, not rendered in time, failed. The full sentences stay in the note under the map.
- **The 60° S edge:** drawn clearly.
- **Missing tiles:** areas with no hillshade tile yet (loading, stalled, failed) are hatched instead of dark, and the legend explains this. The server's tiles were checked to be fully opaque, so hatching never shows through real terrain.
- **Comparison candidates:** accent rings.
- **Unchanged:** tile requests, the composition from finer tiles, timeouts, the slow-tile memory and the fallback logic. The analysis-result map does not use the variant, so it stays as it was for Phase 3.

### 4. Local terrain
- **Stage:** the 3D view fills the same stage.
- **Controls:**
  - floating view controls with a new Reset view button;
  - window and vertical-exaggeration selects float at the top right.
- **Legend:** the product level and name, "Gaps: no registered data, not drawn", and a height colour bar. The bar uses the same height-to-grey ramp as the mesh and shows the window's min and max.
- **Loading:** a ring and "Loading the N km window of registered terrain".
- **Unchanged:** the full statistics list and notes stay under the stage. The API calls, resolution and no-data handling are also unchanged.

### 5. Integration and responsive layout
- **One selection everywhere:** the store's site coordinates drive all three views.
  - The globe opens centred on the selected site with the whole disc in view.
  - The map centres on it.
  - The terrain view is the site's window.
  - The selected-site panel, unchanged, offers Inspect, Analyse, Show on the globe and Show on the map.
- **Switching:** views fade in when switched (none with reduced motion). Only one WebGL view is mounted at a time, as before.

**Responsive layouts:**

| Width | Layout |
| --- | --- |
| ≥ 1200 | stage, plus a 300 px console column (title and site panel) |
| 901–1199 | 280 px console |
| ≤ 900 | title, then stage (`70dvh`), then site panel |
| ≤ 600 | the globe's viewpoints and navigation become a bar above the stage; the globe stage is limited to `100vw + 56 px` so the width-limited disc doesn't leave empty bands; legends start closed |

No view scrolls sideways at 1440, 1024 or 390 px (`previews_final/preview-phase2.json`).

## Files
See `logs/changed_files.txt` (baseline hashes compared with `logs/frontend_files_after_sha256.txt`).

**Modified (11):**
- `src/components/MoonGlobe.tsx`, `MapView.tsx`, `TerrainPreview.tsx`, `SiteView.tsx` (explorer branch only), `Welcome.tsx` (split into the compact title and `WelcomeDetails`)
- `src/i18n/en.ts`
- `src/styles/app.css`, `tokens.css` (HUD and candidate tokens, console width), `views.css` (old explorer, globe and terrain rules moved out)
- `src/ui/Icon.tsx`
- `scripts/globe-live-check.mjs` (its pixel-to-angle check now uses the framing distance instead of the old fixed 3.4; not run)

**Added (3):**
- `src/styles/explorer.css`
- `src/ui/StageLegend.tsx`
- `src/lib/mapScale.ts`

**Strings:**
- **Removed:** the eight globe glyph strings (◀ ▶ ▲ ▼ + − ⌖ ◎), now SVG icons.
- **Added:** keys for the new instruments.
- **Changed wording:** one step's text ("click the map or the 3D Moon above") follows the new layout.
- **Unchanged:** every scientific, validation and uncertainty text.

**Differences from the plan:**
- **No separate components:** the planned `ControlRail.tsx` and `HudPanel.tsx` were not needed; the controls stay inside each view, and the shared piece is `StageLegend`.
- **`SiteExplorer.tsx`:** needed no change.
- **Console column:** not made collapsible, because the disc is limited by the stage height on desktop, so a wider stage would not enlarge it.

## Results

| Check | Result | Log |
| --- | --- | --- |
| TypeScript | exit 0 | `logs/05_typecheck.log` |
| `npm test`: strings, static accessibility and globe geometry | exit 0. Strings: 699 keys, all referenced, 0 problems. Static a11y: 26 components, 52 colour pairs, 0 problems. Globe geometry: 238,972 checks passed. | `logs/06_npm_test.log` |
| Production build | exit 0 | `logs/07_npm_run_build.log` |
| Bundle | initial JS 329.2 KB / 103.7 KB gzip (Phase 1: 326.9 / 102.9); globe, map and terrain still lazy (separate chunks) | `logs/08_check_bundle.log` |
| Globe framing (three.js projection) | exact (1e-16) at 7 stage sizes | `logs/02_globe_fit_check.log` |
| Map scale bar (analytic point scale) | within 2.8e-4 at 6 positions and resolutions | `logs/01_map_scale_check.log` |
| Short visual preview, one browser | 13 screenshots; no sideways scroll; 0 console errors; the site centre on the globe is exactly the typed site (89.463° S 222.510° E; 89.200° S 200.000° E) | `logs/11_preview_final.log`, `previews_final/` |
| Backend and official report | unchanged (`logs/backend_fingerprints_after.txt` = `baseline/backend_fingerprints.txt`) | |

**Screenshots** (`previews_final/screenshots/`, final build):
- **Desktop:** globe, globe with the legend open, globe at a site, globe with a candidate, map, map at a site, map with a candidate, local terrain, and the content below the stage.
- **Tablet and phone:** globe and map.

`previews_iter1/` holds the first build, before the phone globe-height and legend-wording fixes.

## Outstanding verification (deferred to Phase 5, not passed here)
1. **Live browser checks:** all eight still need to run on the Phase 2 build: shell, mission, visualisation, explorer, globe, globe targeting, map and end-to-end. The map and end-to-end checks are also still deferred from Phase 1.
   - **Expected script updates:** the globe check's 390 px layout test and the explorer check's stacking test should still hold. Their selectors (`.globe-toolbar`, `.explore-grid > .pane`, `.pane-head h3`, `.pane-note`, `.globe-readout-mini span`, `.segmented-mini` button texts) are kept.
   - **Pixel-to-angle check:** now uses the framing distance and needs a live run.
2. **U-04 accessibility audit (Tab stops and automated problems):** the new focusable controls change the expected counts.
   - **Globe:** Reset, plus the legend summary.
   - **Map:** Show whole map and Centre on site (only when a site is set), plus the legend summary.
   - **Terrain:** Reset, plus the legend summary.
   - Phase 5 must re-measure and re-register these counts.
3. **Contrast over imagery:** the floating panels (`--hud`, 86–94 % opaque) need a rendered-contrast check over the brightest hillshade. The static estimate is about 11:1 for text and 6.5:1 for muted text.
4. **Performance:** the larger map view requests more tiles at once. Measure the first paint and tile timings in the Phase 5 performance audit.

## Known issues and notes
- **Map hillshade texture:** the server's hillshade shows fine grid and radial texture in some craters at large zoom. The tiles are fully opaque, so this comes from the server-rendered hillshade and not from the new hatched background. The backend is unchanged and out of scope.
- **Phone globe:** the S pole label can sit partly under the readout panel at the bottom of the stage.
- **Overlapping markers:** at close zoom on the globe, sites a few kilometres apart overlap (the imagery resolves only a few km, as its note says).
- **Analysis-result view:** its map and 3D terrain are unchanged; they belong to Phase 3.
