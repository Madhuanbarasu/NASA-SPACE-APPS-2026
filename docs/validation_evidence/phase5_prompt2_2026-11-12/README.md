# Phase 5, Prompt 2: South Pole Explorer (2026-11-12)

**Status:** implemented and tested; frontend only.
- **Live checks** (all on the final build):
  - **explorer:** 27/27;
  - **globe regression:** 31/31;
  - **no-WebGL:** 2/2.
- **Geometry and coordinate checks:** 238,972.
- **Regression:** existing analysis, comparison, map, local 3D terrain and accessibility are unchanged.
- **Unchanged:** the backend, algorithm 1.5.0, the fingerprints and the official report (§6).
- **Not started:** Prompt 3.

## 1. What was built

| Area | Implementation |
| --- | --- |
| **One site selection** | The store's site coordinates (the sidebar fields) are the only coordinate state. The globe's `selected` is derived from them (`parseSite`); globe picks and map picks both write them through one conversion, `lib/moonGeo.siteCoords` (rounded to 1e-6°, east longitude 0–360 after rounding, latitude clamped). `MapView` now uses the same function. The Prompt 1 local `globePick` state was removed. |
| **One coverage lookup** | Coverage moved from the sidebar into the store: `GET /api/coverage`, debounced 350 ms, with stale answers rejected (`coverageFor`). The sidebar, the explorer card and the globe marker all use it; the sidebar's texts and behaviour are unchanged. |
| **Globe → South Pole** | The South Pole viewpoint and a new "Centre the view on the selected site" button. Viewpoint changes and centring fly smoothly (650 ms, great-circle; instant under `prefers-reduced-motion`). A green ring marks 60°S, the backend's own coverage limit (`dem.coverage_check`). The marker is green where terrain is registered, orange where it is not, and gold while unknown. |
| **Selected site card** (`SiteExplorer`) | Shows coordinates (same formatter everywhere: `lib/format.fmtLatLon`), the signed form, the site name, coverage levels from the API, the finest product, and the backend's reason for unsupported points. Actions: **Inspect local terrain** and **Analyse this site** (the existing `runAnalysis`, with the sidebar's dates and rules); both are disabled without coverage. Also Show on the globe / map, job progress and errors. |
| **Local terrain before analysis** (`TerrainPreview`, lazy) | `GET /api/terrain` for the selected site. The 3D mesh draws **only cells whose four corners have data**: no fill, no interpolation. It reports product, display grid and cell size, height range and mean (relative to the 1737.4 km sphere), height near the site, data share and a colour legend. Window 2, 4, 8 or 16 km; vertical exaggeration; buttons and keyboard. When the window's product is coarser than the point's finest coverage, it explains why. |
| **Transitions** | The welcome pane switches between **South polar map**, **3D Moon globe** and **Local terrain** (Local terrain is disabled without coverage); the selected site card sits beside it. The result view gains **Back to the Moon explorer**, which keeps the site and settings. |
| **States** | No site; checking coverage; covered; not covered (with the backend's reason); coverage error; terrain loading; terrain error (backend reason, e.g. no single product covers the window); no data; analysis running or failed; no WebGL; chunk load failure (`LazyBoundary`). |
| **Accessibility** | Every new control is a named button or select. Globe picks are announced politely by the globe itself, only for picks made on it (not on every keystroke in the sidebar). Disabled secondary buttons now look disabled. |
| **Lazy loading** | `TerrainPreview` (6.2 KB) and `MoonGlobe` (13.4 KB) load on demand and share the three.js chunk. Initial JS is 306.6 KB raw / 97.3 KB gzip (+7.6 KB / +2.4 KB over Prompt 1, for the explorer card, shared coverage and strings). |

## 2. Data coverage and accuracy
- **Coverage:** always the backend's answer (`/api/coverage`); the frontend never guesses it. The 60°S ring is the backend's hard rule (points north of it are refused), and finer coverage is checked point by point.
- **Registered products** (from the backend registry; shown through coverage results):
  - 5 m PGDA 78 Site01;
  - 20 m and 80 m PGDA 90 (±304 km stereographic square);
  - 240 m PGDA 90 (to 60°S).
- **Elevation shown:** only values served from the registered DEMs (`/api/terrain`). They are display-averaged, labelled as such, and leave no-data cells empty. The globe imagery remains imagery only.
- **The 3D window can use a coarser product than the point.** The backend serves a window from the finest product covering the **whole** window. At Site01 the point is covered at 5 m, but the 8 km window extends past the 5 m tile, so it shows 20 m; the interface says so, and a 4 km window shows the 5 m product. This is the backend's existing rule, not changed here.
- **Consistency:** at Site01 the display-averaged height near the site in the 8 km preview is 1943.6 m (20 m product). The analysis reports a ground height of 1944.8 m (5 m product) for the same coordinates.
- **Provenance and labels:** nothing in provenance or validation labels changed. The analysis opened from the explorer shows the same label chips as before.

## 3. Results

| Check | Result | Evidence |
| --- | --- | --- |
| TypeScript | exit 0 | `logs/00_typecheck.log` |
| `npm test`: strings (519 keys, 0 problems), static a11y (18 components, 0 problems), geometry and coordinates (238,972 checks) | exit 0 | `logs/01_npm_test.log` |
| Production build; bundle split | exit 0; three.js not in the initial chunk | `logs/02_npm_run_build.log`, `logs/03_check_bundle.log` |
| **Explorer live check** (`scripts/explorer-live-check.mjs`) | **27/27** | `logs/04_explorer_live_check.log`, `explorer_check/` |
| Globe live check, adapted to the explorer layout | **31/31** | `logs/05_globe_live_check.log`, `globe_check/` |
| Globe check without WebGL | **2/2** | `logs/06_globe_live_check_no_webgl.log` |
| Full live U-04 audit (real Site01 analysis, local 3D terrain, map, 2 × 2 comparison, Data, Guide) compared with the U-04 release run | **unchanged** | `logs/07_audit_a11y.log`, `a11y_regression/`, `logs/08_a11y_regression_compare.log` |

**The 27 explorer checks:**
- **Globe → site transfer:**
  - the South Pole pick gives (−89.9, 0) in the sidebar and "89.900° S, 0.000° E" in the explorer;
  - a canvas click west of the prime meridian gives an east longitude in (300, 360), identical in the sidebar and explorer;
  - typed Site01 → "Centre on selection" centres the globe at 89.463° S, 222.510° E.
- **Edges:**
  - a North Pole pick (89.9° N) is refused with the backend's reason;
  - −137.489553 → 222.510° E;
  - 360 → 0.000° E;
  - 359.9999996 → 0.000° E (never 360.000);
  - −90 is accepted and covered;
  - −91 → no site.
- **Coverage:**
  - the polar point is covered at 20 m, 80 m and 240 m;
  - Site01 is covered at 5 m, 20 m, 80 m and 240 m (finest PGDA 78);
  - 70°S 100°E is covered at 240 m only;
  - nearside points are refused with "The registered LOLA products cover 60-90 S only…", with local terrain and analysis disabled.
- **Local terrain:**
  - Site01 at 8 km uses 20 m with the coarser-window note; at 4 km it uses the 5 m PGDA 78 product;
  - 70°S 100°E switches to the 240 m product;
  - no error or no-data overlay.
- **Analysis:**
  - "Analyse this site" opens the result at "−89.46316°, 222.51045° E", with the map, the local 3D terrain and five label chips;
  - "Back to the Moon explorer" returns with the site kept.
- **Responsive:** at 390 px the explorer stacks under the pane, with no sideways scroll.
- **Errors:** no page exceptions or console errors. The 422 replies for refused terrain windows are expected API answers.

**Existing features** (`logs/08_a11y_regression_compare.log`):
- **All six views:** 0 problems.
- **Tab stops:** identical except the expected +2 on the welcome view (map/globe switch) and +1 on the result view (Back to the Moon explorer).
- **Functional tests:** all 16 are identical to the release run.
- **One CSS-only change after the audit:** the disabled state of `.quiet-button` and `nowrap` on the terrain controls. The static a11y check and both live checks were rerun after it.

## 4. Defects found and fixed during testing
1. **WebGL render after teardown:** a render frame queued just before unmounting could run after `forceContextLoss()` and throw inside three.js. `TerrainPreview` and `MoonGlobe` now cancel the pending frame and ignore renders after teardown.
2. **Stale readout after a flight:** OrbitControls emits "change" only for moves above its EPS, so a flight's final correction could leave the centre readout and frame stale (89.887° instead of 89.900°). View changes now refresh explicitly (`sync`).
3. **Longitude display:** `fmtLatLon` showed 359.9999996 as "360.000" and −0.0001 as "0.000° S". It now rounds before normalising.
4. **Disabled styling:** disabled `quiet-button`s looked enabled; they now look disabled.

## 5. Limitations
- **Coverage for rendering:** the globe draws the 60°S coverage limit only. Finer product footprints (the 20/80 m square, the 5 m tile) are not drawn, because their extents are not exposed by the API and the backend was not changed; coverage is reported per point instead.
- **Terrain preview:** display-averaged (160 × 160) with illustrative light. Horizons, Sun and Earth visibility and validation labels come only from the analysis.
- **Ground height before analysis:** the explorer does not show the exact site ground height, which the backend computes only in the analysis.
- **Browser coverage:** tested in headless Chrome 157 (SwiftShader) only, with no physical touch device.
- **Official report:** U-04 and U-06 in the official report (`2279606c…`) still describe the pre-Phase 5 build. The live audit shows the existing views unchanged, but U-04 and U-06 should be re-registered for this build before the next official report (as noted in Prompt 1).
- **IB-5 (D5) restrictions** still apply to distributing `frontend/dist`.

## 6. Files changed
| File | Change |
| --- | --- |
| `frontend/src/components/SiteExplorer.tsx` | **new**: selected-site card and `useSiteCoverage` |
| `frontend/src/components/TerrainPreview.tsx` | **new**: pre-analysis local terrain (no-data cells left empty) |
| `frontend/scripts/explorer-live-check.mjs` | **new**: live end-to-end check |
| `frontend/src/components/SiteView.tsx` | three-way welcome view, globe bound to the store, explorer card, Back to the Moon explorer |
| `frontend/src/components/MoonGlobe.tsx` | `selectedCovered` and `selectionPanel` props, 60°S ring, coloured marker, centre-on-selection, flights, announcement of own picks, render guard, `sync` |
| `frontend/src/components/Sidebar.tsx` | uses the store's coverage (no local lookup) |
| `frontend/src/components/MapView.tsx` | picks through `siteCoords` |
| `frontend/src/state/store.tsx` | shared coverage state and lookup |
| `frontend/src/api/types.ts`, `api/client.ts` | `Coverage` type |
| `frontend/src/lib/moonGeo.ts` | `siteCoords`, `parseSite` |
| `frontend/src/lib/format.ts` | `fmtLatLon` |
| `frontend/src/i18n/en.ts` | `explorer` and `terrainPreview` sections, globe additions (483 → 519 keys) |
| `frontend/src/styles/app.css` | explorer, terrain preview, disabled quiet buttons |
| `frontend/scripts/check-moon-geo.mjs` | transfer and edge-case tests |
| `frontend/scripts/globe-live-check.mjs` | reads the selection from the explorer card; waits for flights |
| `frontend/dist/` | rebuilt. Hashes before and after: `logs/dist_before_sha256.txt`, `logs/dist_after_sha256.txt` |

**Not changed:**
- backend code;
- algorithm 1.5.0, code `5bf9753f…`, suite `1632af16…` and terrain acceptance `e48eb8ed…` (`logs/backend_fingerprints_after.txt`);
- `report.json` (`2279606c…`);
- `Terrain3D.tsx`;
- the Phase 4 and Prompt 1 evidence;
- `package.json` and the lock file.

No dependency was installed and no Git operation was run.
