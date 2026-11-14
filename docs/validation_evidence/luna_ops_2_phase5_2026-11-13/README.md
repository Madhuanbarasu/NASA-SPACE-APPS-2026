# LUNA-OPS 2.0, Phase 5: Landing Safety Assessment (2026-11-13)

**Status: implemented; awaiting the owner's review.** Phase 6 and Phase 7 have not been started.

This is **preliminary DEM-based landing-site hazard screening**. It does not certify any site as safe. There are no combined scores, landing-success probabilities, rankings or safe/unsafe verdicts. Every finding is reported separately with its source, resolution, basis and limits.

## Approved decisions (owner, 2026-11-13)
1. **Site01 extras.** The PGDA 78 Site01 LOLA count map, NASA slope map and slope-uncertainty map (about 123 MB) were downloaded and recorded in a separate landing manifest. `data/dem/registry.json` was not modified.
2. **PGDA 104.** The 2.2 GB Connecting Ridge shape-from-shading model was not downloaded. It is documented as investigated but not integrated: frame, vertical datum and missing-data conventions are unverified.
3. **Obstacles.** Boulder and obstacle detection shows "Not available - manual review required". No detections are generated from DEM height jumps.
4. **Placement.** The new backend is the separate package `backend/lunaops_landing/` (landing 0.1.0). Its routes are attached in `start.py`, and the validated engine is unchanged.

## Validated engine and fingerprint scope
- **What the fingerprints cover.** `lunaops.fingerprint.code_fingerprint()` hashes every `.py` file under `backend/lunaops` plus `backend/lunaops/manifests/*.json`. `suite_fingerprint()` hashes every `.py` file under `backend/tests` and `backend/validation`. The exact file lists are in `baseline/code_fingerprint_scope.txt` (27 files) and `baseline/suite_fingerprint_scope.txt` (44 files).
- **What Phase 5 added, all outside both fingerprints:**
  - `backend/lunaops_landing/`;
  - `data/landing/`;
  - a four-line change to `start.py`;
  - the frontend.
- **Unchanged after Phase 5:**
  - algorithm 1.5.0;
  - code fingerprint `84cbd4ea…`;
  - suite fingerprint `1632af16…`;
  - terrain acceptance digest `e48eb8ed…`;
  - `backend/validation/report.json` SHA-256 `8c03ebaf…`.
  
  See `logs/backend_fingerprints_after.txt`, which is identical to `baseline/backend_fingerprints.txt`. All 25 engine source files are byte-identical (`logs/backend_lunaops_sha256_after.txt`). The running app's `/api/status` reports the same code fingerprint as the report, with no validation blockers.
- **Not validated.** The landing package is **not covered** by the official validation report, and the app never labels it "Validated". Every response carries:
  - `validation_status`: "Preliminary screening - not part of the validated engine";
  - its own `landing_version` (0.1.0) and `landing_code_sha256` (final: `e20d9b0b…`, test files excluded);
  - the engine fingerprint, marked as not covering the screening.
- **Development runs.** `uvicorn lunaops.api.main:app` alone does not include the landing routes. `start.py` attaches them with `lunaops_landing.api.install(app)`, which inserts them ahead of the single-page-app catch-all route.

## Features implemented
**Backend (`backend/lunaops_landing/`, 7 modules).** The data, algorithms and parameters are in `DATA_SOURCES.md` and `ALGORITHMS.md`.
- **`POST /api/landing/assess`:** screens a square window up to 1201 × 1201 pixels on the finest covering product, or the product the user chooses. It returns:
  - region statistics: slope, detrended roughness, TRI, multi-scale roughness, elevation, height uncertainty, NASA slope and slope uncertainty (Site01), valid share and measured share;
  - unconfirmed depression candidates;
  - layer index and legends;
  - full provenance;
  - the footprint findings.
- **`POST /api/landing/{id}/footprint`:** footprint findings for a new centre, radius or thresholds, computed on the cached window in about 1–5 ms.
- **`GET /api/landing/{id}/layer/{name}.png`:** the elevation, slope, roughness, coverage, uncertainty, NASA slope and slope-above-threshold layers.
- **`GET /api/landing/{id}/point`:** pointer readout.
- **`GET /api/landing/meta`.**
- **Caching:** the latest 3 assessments are kept in memory; a repeat takes about 2 ms.
- **`python -m lunaops_landing.acquire register`:** registers an auxiliary product only if its CRS, grid and DEM SHA-256 match.

**Frontend.**
- **New lazily loaded `Landing` tab** (`LandingView.tsx`, 24 KB chunk) with:
  - **A. Selected landing site:** coordinates, coverage, products at the point, analysis resolution, window, valid and measured shares, configuration.
  - **B. Terrain analysis:** a statistics table with units and the basis of each quantity, the slope distribution, multi-scale roughness.
  - **C. Landing footprint:**
    - centre inputs, plus dragging on the map;
    - radius and its pixels-across note;
    - user-defined thresholds, labelled as assumptions, with no defaults except the 95% minimum terrain data;
    - coverage and uncertainty metrics;
    - five separate findings with the API's status words.
  - **D. Hazard map** (`LandingMap.tsx`, separate 20 KB chunk):
    - OpenLayers canvas renderer, so no WebGL context; the same projection definition as the South Polar Map;
    - the server's hillshade as backdrop, fine tiles only;
    - one raster layer at a time (elevation, slope, roughness, data coverage, height uncertainty, NASA slope product, slope above threshold) with opacity;
    - toggles for depression candidates (moment ellipses styled by quality), footprint and analysis window;
    - legends with units, a pointer readout, zoom, fit and centre-on-footprint, and candidate selection;
    - the obstacle layer stated as not available.
  - **Depression candidate table:** each candidate is selectable and centres the map.
  - **E. Scientific provenance:**
    - status and validation note;
    - dataset, product id, file and SHA-256, resolution, frame and CRS, vertical datum, citation;
    - error map and auxiliary products (with source URLs);
    - window bounds, methods, versions, configuration, notes and limitations;
    - JSON export.
- **Mission dashboard.**
  - Each candidate card has a "Landing safety" button: it selects the site, opens the tab and runs the screening.
  - The selected-site card has "Open in Landing safety".
  - Each candidate card shows a "Landing screening in this session" block listing every finding with its own status word, or "not run" or "needs registered terrain".
  - Existing selection, analyse, comparison metrics, the 6 h2 headings, the section ids and the `li` structure are unchanged (`mission.nestedLi = 0`, `h2 = 6`). The integrity pattern `/score|probabilit|recommend|rank|best site/` does not match the dashboard text.
- **Top bar (`shell.css`).**
  - With six views the inline tabs no longer fit below 1440 px. The bar already overflowed with five views: by 109 px at 1200 px and 51 px at 1280 px (`logs/11_topbar_before_css_change.txt`).
  - The existing compact navigation menu now applies below 1440 px instead of below 1200 px. The docked Mission Parameters panel is unchanged.
  - The bar now has no overflow from 320 to 1920 px (`previews/topbar.json`, `previews/screenshots/topbar-menu-1280.png`).

## Files changed
See `logs/changed_files.txt`.

**Frontend, modified:**
- `src/App.tsx`
- `src/api/client.ts`
- `src/api/types.ts`
- `src/components/MissionView.tsx`
- `src/components/TopBar.tsx`
- `src/i18n/en.ts`
- `src/state/store.tsx`
- `src/styles/app.css`
- `src/styles/shell.css`

**Frontend, new:**
- `src/components/LandingView.tsx`
- `src/components/LandingMap.tsx`
- `src/styles/landing.css`

**Backend:**
- `start.py`, modified;
- `backend/lunaops_landing/`, new: `__init__`, `kernels`, `sources`, `assess`, `render`, `api`, `acquire`, and `tests/` with 4 files.

**Data:** `data/landing/`, new: `manifest.json` and 3 files (118 MB).

**Unchanged:** no new dependency (`package.json` and `requirements.txt` unchanged).

## Focused test results (no 440-test suite, no U-04/U-06 audits)
- **Backend:** `pytest lunaops_landing/tests`: **35 passed** (`logs/05_landing_pytest.log`).
  - Fixtures are isolated synthetic terrain: a 10 m DEM with a 10° plane, an 8 m deep, 400 m wide paraboloid bowl, a ±0.5 m checkerboard patch, a 100 m no-data hole, a constant 0.5 m error map and a count map with returns on every 5th column. They live in a temporary data folder; the production registry is never touched.
  - **Slope:** exact on planes from 0 to 60° and on oblique planes with unequal spacing; never uses missing samples.
  - **Roughness:** equals a NumPy least-squares reference; zero on a plane; needs a complete window. TRI equals its definition.
  - **Depressions:** a closed bowl is exactly 5 m deep; a gap or the window edge limits depth to the spill level; tilted rims; 8-connectivity. On the API, the bowl is found with D within 3%, depth within 0.05 m, the centre within 1 pixel, quality "defined", measured share 20%, and a footprint intersection.
  - **Projection:** forward transform within 1 mm of pyproj with the engine's projection at 6 latitudes; inverse round trip to 1e-10°; point scale equals the numerical derivative and 2/(1 − sin φ).
  - **Footprint:** pixel count equals πr²/pixel² within 2%; outside the window gives "insufficient"; a footprint under 3 pixels gives "higher resolution"; with no threshold there is no finding.
  - **Layers:** PNG size equals the window grid, and the extent lies on the DEM's pixel edges.
  - **API:** routes precede the catch-all; 404 and 422 handling; no score, probability, rank, certify, safe or validated keys.
- **Frontend:**
  - `tsc --noEmit`: 0 errors.
  - `npm test`: check-strings 1111 keys, 0 problems; check-a11y 38 components and 52 colour pairs, 0 problems; check-moon-geo 238,972 checks.
  - `npm run build`: OK.
  - `check-bundle`: initial JS 301.0 KB (97.2 KB gzip). This was 290.4 KB in Phase 4; the growth is the new strings and store code. Lazy chunks: `LandingView` 24 KB, `LandingMap` 20 KB. Logs 06–08.
- **Engine integrity:** fingerprints and report hash unchanged; engine files identical; `registry.json` unchanged; the Phase 1–4 `SHA256SUMS` all verify.

## NASA slope comparison (Site01, all 10,227,204 interior pixels; `logs/03_nasa_slope_comparison.json`)

| Our estimator against the NASA `_slp` product | Mean diff | RMS diff | 95th pct. abs diff | Correlation | Within NASA's 1σ slope error |
|---|---|---|---|---|---|
| Horn 3 × 3 (used by the app) | −0.033° | 0.380° | 0.773° | 0.9979 | 99.67% |
| 2-pixel central differences | −0.007° | 0.008° | 0.015° | 1.0000 | 100% |

- **Interpretation.**
  - NASA's slope product is, to 0.008° RMS, the 2-pixel central-difference slope of the same DEM. This confirms our grid, spacing and orientation handling.
  - The remaining −0.007° is consistent with our (R + h)/R height correction, which NASA's product does not apply.
  - The app keeps Horn's 3 × 3 operator, as in the approved plan. It smooths slightly; its RMS difference of 0.38° is a fifth of NASA's median slope uncertainty (1.90°).
- **By pixel type.** Results are similar for measured pixels (RMS 0.456°) and interpolated pixels (RMS 0.371°).

## Landing hazard and footprint examples (real registered data; `examples/*.json`, `logs/04_real_examples.log`)
The thresholds (slope 10°, roughness 0.5 m, relief 10 m) are demonstration assumptions only.

| Case | Product, window | Region slope median | Depression candidates (defined / weak) | Footprint findings |
|---|---|---|---|---|
| Site01 89.4632° S, 222.5104° E, 1.5 km half-width | 5 m, 601² | 10.85° | 42 (28 / 14) | r 50 m (20 px across; 11.4% measured pixels): slope *hazard* (1.9% of pixels > 10°, max 10.9°); roughness *clear*; relief 8.7 m *clear*; depressions *none detected*; obstacles *manual review* |
| same, 3 km half-width | 5 m, 1201² | 12.15° | 125 (96 / 29) | r 100 m: slope *hazard* (6.3% > 10°) |
| same site on the 20 m product | 20 m, 301² | 11.94° | 35 (33 / 2) | r 100 m: slope *hazard* (3.8%); measured share *unavailable* (no count map) |
| Shackleton rim area 89.9° S, 0° E | 20 m, 401² | 18.59° | 17 (15 / 2) | r 100 m: slope *hazard* (100% > 10°, max 25.0°), relief 76.4 m |
| 85° S, 30° E | 80 m, 501² | 8.27° | 189 (155 / 34) | r 100 m spans 2.5 pixels: slope, roughness, relief and depressions *Requires higher-resolution data* |

- **Roughness depends on the product:** the median 5 × 5 roughness at the same site is 0.13 m on 5 m pixels and 0.65 m on 20 m pixels. This is why the window and pixel size are always shown.
- **Screenshots:** in `previews/screenshots/`:
  - `02`–`04`: layers;
  - `05`/`06`: the footprint dragged and resized, with its findings;
  - `07`: terrain analysis;
  - `08`: candidates;
  - `09`: provenance;
  - `10`: the Mission card;
  - `11`: a 20 m site;
  - `12`–`14`: tablet and phone (390 and 320 px).

## Previews (one headless browser; `scripts/landing_preview_body.mjs`, `previews/landing-preview.json`)
- **Interaction:**
  - the Landing tab opens and runs;
  - the pointer readout shows height, slope, roughness, height uncertainty, LOLA returns and the depression under the pointer;
  - dragging the footprint moved it from 89.4632° S, 222.5104° E to 89.4813° S, 221.9160° E and re-evaluated it; resizing to 150 m re-evaluated it;
  - all 7 raster layers display;
  - a candidate selects and centres;
  - Mission shows the findings and opens the site in Landing;
  - returning to the tab keeps the settings of the result on screen (150 / 10 / 0.5 / 10);
  - a stale-site banner appears when the selected site changes.
- **Layout:** no horizontal page scroll at 1440, 1024, 390 or 320 px; map boxes 942 × 445 (1024 px), 324 × 359 (390 px) and 254 × 300 (320 px).
- **Errors:** 0 console errors.

## Performance and memory (`examples/summary.json`; Windows peak working set of the Python process)
- **Process baseline:** 61 MB.
- **Timings:**
  - 601² window at 5 m: 0.94 s, peak 153 MB;
  - 1201² window: 1.41 s, peak 261 MB (the largest allowed);
  - 20 m and 80 m windows: 0.2–0.5 s;
  - cached repeat: 1.5 ms;
  - footprint re-evaluation: 1–5 ms;
  - first browser run including page work: 0.2–1.7 s.
- **First call:** numba compiles the kernels once (cached to disk after that).
- **Browser:** layer PNGs at most 1201² pixels; one canvas map; no continuous rendering. The 3D views are untouched, so there is still at most one WebGL context.

## Scientific limitations
- **Screening only:** no result certifies a landing site as safe; thresholds are user assumptions; findings are not combined.
- **Effective resolution:** LOLA 5 m pixels are about 90% interpolated between laser tracks (9.5% hold a return at Site01). Effective resolution is coarser than the pixel size; slope and roughness describe the DEM at its scale.
- **Measured versus interpolated:** only Site01 has a count map. On the PGDA 90 products this is "unavailable", never assumed.
- **Roughness:** this is DEM roughness, not rock or boulder detection. Obstacles are always "Not available - manual review required"; even orbital imagery cannot guarantee that every hazard is found.
- **Depressions:**
  - candidates are unconfirmed; no crater catalogue is integrated (the Robbins database was not accessible);
  - depth is below the spill level, not the rim crest;
  - hollows open to the window edge or to missing data, and breached ones on slopes, are missed or measured shallower;
  - craters larger than the window are not seen;
  - the quality rules are a landing 0.1.0 convention.
- **Uncertainty:**
  - height uncertainty comes from the product's declared RMS error map;
  - slope uncertainty exists only for Site01 (NASA `_slperr`);
  - uncertainty is not propagated into our own slope and roughness values.
- **Window size:** windows are limited to 1201 pixels across, so large features need a coarser product.
- **Not integrated:** PGDA 104 shape-from-shading (image-derived heights) and other PGDA 78 sites.

## Outstanding for Phase 7 (deferred; not passed)
- **Live browser checks:** all eight, including the map and e2e checks deferred since Phase 1.
- **`viz-live-check` and `mission-live-check`:**
  - public-mode link count;
  - "Visibility chart" now "Sunlight";
  - two `.vis-chart`;
  - 11 timeline legend items;
  - new for Phase 5: the extra "Landing safety" buttons and landing block on candidate cards;
  - the sixth tab in `shell-live-check`;
  - the compact menu now applying at 1200–1439 px.
- **Audits:** re-register the U-04 Tab counts (now six tabs, and the compact menu below 1440 px). Rendered contrast, including the new finding chips and legend text. Performance on long windows.
- **Landing-specific:**
  - keyboard-only operation of the hazard map (the footprint can be moved with the coordinate inputs, but there is no keyboard drag);
  - screen-reader review of the Landing view;
  - an independent review of the depression-quality rules;
  - whether to integrate PGDA 104 (after verifying its frame, datum and nodata), other PGDA 78 sites, and a crater catalogue;
  - uncertainty propagation into slope and roughness.

## Integrity and reproduction
- **Commands:**
  - Backend tests: run `python -m pytest lunaops_landing/tests -p no:cacheprovider` from `backend/`, with TEMP and TMP set to `E:\Temp\LUNA-OPS`.
  - NASA comparison: `python <evidence>/scripts/nasa_slope_compare.py`.
  - Examples: `python <evidence>/scripts/real_examples.py <out>`.
  - Previews: concatenate `../luna_ops_2_phase1_2026-11-13/cdp_harness.txt` with the body script, then run `node landing_preview.mjs --base http://127.0.0.1:8000 --out <dir>`.
- **Manifest:** `SHA256SUMS` covers every file in this folder (verify with `sha256sum -c SHA256SUMS`).
- **Constraints observed:**
  - no Git commands;
  - temporary files and downloads on `E:\Temp\LUNA-OPS`;
  - one browser at a time;
  - the LUNA-OPS 1.0 backup, `report.json` and the Phase 1–4 evidence untouched.
