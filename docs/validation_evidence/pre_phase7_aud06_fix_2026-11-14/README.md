# AUD-06 fix: grid pattern in the hillshade map (2026-11-14)

**Approved:** Option 2 of `../pre_phase7_aud06_architecture_review_2026-11-14/`, a separate tile-rendering package.

**Not changed:**
- the validated engine: `backend/lunaops/` and `backend/lunaops/api/tiles.py`;
- the engine tests, validation scripts, reports, datasets, labels and existing evidence.

Phase 7 was not started.

**Status of the new package:** `lunaops_tiles` 0.1.0 renders display images only. Its tests check images, not science. It is **not scientifically validated** and not covered by the engine's validation report; `/api/display/tiles/info` says so.

## Root cause addressed
- **The defect:** the engine's `render_tile` reads each LOLA product with `src.read(..., out_shape=…, boundless=True, resampling=bilinear)`.
- **Why it draws a grid:** in rasterio 1.5.2 a boundless read builds an in-memory VRT and reduces it to `out_shape` with no resampling argument (`rasterio/_io.pyx:605–615`). The reduction is therefore nearest-neighbour whatever is requested. Reducing the 20 m product by 2.84 at zoom 7 alternately skips 2 and 3 source pixels, which the hillshade draws as lines about 6 px apart.
- **A second, smaller grid:** enlarging the coarse 240 m product makes blocky steps on the boundless path. A plain bilinear enlargement would still leave creases at every 240 m pixel edge.

## Architecture implemented
**New package `backend/lunaops_tiles/`** (outside both fingerprinted trees, like `lunaops_landing` and `lunaops_comms`):

| File | Content |
|---|---|
| `__init__.py` | Version `0.1.0`; `STATUS` ("Display rendering only - not part of the validated engine and not scientifically validated"); `tiles_code_hash()` |
| `render.py` | `read_level`, `hillshade_rgba`, `render_heights` and `render_tile` |
| `api.py` | `GET /api/display/tiles/{z}/{x}/{y}.png` and `GET /api/display/tiles/info`; `install(app)` inserts the routes ahead of the SPA catch-all |
| `tests/` | `helpers.py`, `test_read.py`, `test_real_tiles.py`, `test_api.py`: 33 tests |

**What `render.py` does:**
- **Reused by import, read only (no copies):** the engine's tile grid `lunaops.api.tiles.tile_meta`, `TILE`, `_empty`, and the terrain registry and file lookup `lunaops.engine.dem.usable_levels` and `resolve_dem_path`.
- **No terrain data and no scientific calculation** is duplicated.
- **`read_level` (corrected):** a normal windowed read (fractional window, `boundless=False`), only for tile pixels lying wholly inside the product.
  - **Reducing:** bilinear; GDAL also uses the product's overviews.
  - **Enlarging:** cubic (interpolating). A cubic B-spline was not used because it smooths the heights; Lanczos was not used because it rings (measured).
  - **Missing data:** pixels the product covers only partly or not at all stay NaN, so the coarser level drawn first shows there. Nodata becomes NaN, so it is never blended into heights (tested with NaN and a numeric nodata value).
  - **Rotated rasters** are refused.
- **`hillshade_rgba`:** the engine's cartographic hillshade, unchanged (light 315°/40°, grey 40 + 190·shade, blue ×1.02, alpha from data).
- **`render_tile`:** the engine's level loop (coarse first, finer over it, the same skip rule) and PNG encoding.

**Wiring:**
- **`start.py`:** `install_tiles(app)` after Landing and Communication.
- **Frontend** (only the three tile URLs, `/api/tiles/…` → `/api/display/tiles/…`):
  - `frontend/src/components/MapView.tsx`: the OpenLayers `tileUrlFunction` and the composition `fetch`;
  - `frontend/src/components/LandingMap.tsx`: `tileUrlFunction`.
- **Still the engine's:** the grid metadata `/api/tiles/meta`. The engine's `/api/tiles/{z}/{x}/{y}.png` is still served, unchanged.

## Files created and modified
| | Files |
|---|---|
| Created | `backend/lunaops_tiles/__init__.py`, `api.py`, `render.py`; `backend/lunaops_tiles/tests/__init__.py`, `helpers.py`, `test_read.py`, `test_real_tiles.py`, `test_api.py` (hashes in `logs/lunaops_tiles_files_sha256.txt`; copy in `package_snapshot/`) |
| Modified | `start.py` (+4 lines); `frontend/src/components/MapView.tsx` (2 URLs); `frontend/src/components/LandingMap.tsx` (1 URL). Diff in `logs/source_changes.diff`; originals in `baseline/originals/` |
| Rebuilt | `frontend/dist` (`baseline/dist_sha256.txt` → `after/dist_sha256.txt`) |
| Unchanged (verified) | Everything under `backend/lunaops` (tree digest); `tiles.py`, `main.py`, `report.json`, `data/dem/registry.json`; all other frontend files (`logs/frontend_files_sha256_after.txt` against `baseline/`) |

## Engine, suite and cache integrity
`baseline/integrity_before.txt` and `logs/integrity_after.txt` are **identical** (`scripts/integrity.py`, read only):

| Item | Before = after |
|---|---|
| Code fingerprint | `84cbd4ea34f6606abcd32e02df295f204cb97ca9bef3d9a4d455b4557c831109` |
| Suite fingerprint | `1632af16763dda4e27909a9af3d2fdd903b0d58951faacded72c4cf06d75eabc` |
| `report.json` | `8c03ebaf…`; `/api/status` still reports code fingerprint `84cbd4ea…` |
| `tiles.py` | `05b1df86…` |
| `backend/lunaops` tree digest | `b1c04177…` |
| Cached results | 78 rows, ID digest unchanged. **The audit's 74** (created before 2026-11-13 20:00 UTC) are all present with their files (digest `a7095be4…`). |
| Cached horizons | 27 indexed, 27 of 27 files present; the horizon file digest is unchanged |

**Why 78 and 31, not 74 and 27:** the cache had 78 results and 31 horizon files **before** this task started.
- **Results:** three were created by the audit's own browser run (2026-11-13 20:07–20:08 UTC), after its cache count. One was created by the corrections check on 2026-11-14 01:06 UTC, because the default date window had rolled over.
- **Horizon files:** 4 are unindexed files from 7–9 Nov.

Nothing in this task created, invalidated or recomputed a cached result or horizon.

## Before/after images
- **South Polar Map and Landing backdrop, side by side:** `images/compare-*.png`. Raw screenshots are in `before/screenshots/` and `after/screenshots/`.
  - Before: the engine route, before the change.
  - After: the final package, served by the restarted server.
- **Tile pairs, enlarged 2×:** `images/tiles/*_engine-left_new-right.png`. Groups:
  - A: zoomed-out 20 m;
  - B: full detail;
  - C: 240 m only;
  - D: product and map edges;
  - E: composed zoomed-out.
- **What they show:**
  - the square grid is gone at 10 km and 5 km scale near Site01 (`compare-map-2-site.png`, `compare-map-3-zoom-in-1.png`);
  - the grid on the 20 m side of the 20 m product edge is gone (`D_6_42_31`);
  - blocky enlarged 20 m and 240 m terrain is smooth (`B_11_1107_879`, `C_7_27_42`);
  - the whole-map view and the Landing backdrop are unchanged in appearance.

## Grid-line measurements
The line score is the addendum's measure: about 0.6–0.9 means no lines, about 3 means clear lines.

**1. The addendum's own script, run unchanged** (`scripts/level_probe.py`, a byte-identical copy), against the same measurement on the package's read (`scripts/level_probe_package.py`). Zoom-7 tile 63/64, each level alone; `logs/09_level_probe_engine_vs_package.log`:

| Level | Engine read (addendum, reproduced exactly) | `lunaops_tiles` read |
|---|---|---|
| 20 m (reduced ÷2.84) | **3.23 / 2.50** | **0.89 / 0.69** |
| 80 m | 0.95 / 0.87 | 0.79 / 0.69 |
| 240 m (enlarged ×4.2) | **3.64 / 2.27** | **1.58 / 1.05** (see limitations) |

**2. Composed tiles, engine against package** (`scripts/tile_verification.py`, `logs/tile_verification.json`, `logs/08_tile_verification.log`). 31 tiles:

| Group | Tiles | Transparency identical | Highest engine score | Highest package score |
|---|---|---|---|---|
| A: zoomed-out 20 m (zoom 5–7) | 6 | 6/6 | 3.59 | 0.93 |
| B: full detail (zoom 9–12; 5 m Site01 and 20 m only) | 7 | 7/7 | 1.44 | 1.07 |
| C: 240 m only (60–80° S, zoom 5–9) | 7 | 7/7 | 3.00 | 1.08 |
| D: edges (5 m product, 20 m product, map edge, outside 60° S) | 6 | 6/6 | 3.36 | 1.00 |
| E: composed zoomed-out (zoom 1–4) | 5 | 5/5 | 1.77 | 0.85 |

- **Brightness:** mean grey of the package and the engine agree within 0.32 grey levels on 29 of 31 tiles.
- **Exceptions:** a 240 m-only tile at zoom 9 (0.9) and a 20 m tile enlarged ×5.6 (1.1), where the engine's blocky surface and the smooth one shade differently.

**3. Browser screenshots** (`logs/07_screenshot_line_scores.log`, map area clear of the controls):

| View | Before | After |
|---|---|---|
| Whole map (200 km scale) | 0.78 / 0.75 | 0.75 / 0.69 |
| Site01, 10 km scale | **3.53 / 2.21** | **0.80 / 0.90** |
| 5 km | **3.28 / 3.83** | **0.98 / 1.03** |
| 2 km, 1 km, 500 m | 0.90 / 1.16, 0.80 / 0.94, 1.19 / 1.18 | 0.91 / 0.73, 0.81 / 0.87, 1.01 / 1.03 |

The first verification run, before cubic enlargement was added, is kept for the record:
- `logs/08a_tile_verification_first_run_bilinear_only.*`: group C was 1.10–2.70;
- `after_first_run_bilinear_only/`, `logs/06a_maps_after_first_run_bilinear_only.log`.

## Performance
**Offline render time per tile** (median of 3; `logs/08_tile_verification.log`):

| Group | Engine median / max (s) | Package median / max (s) |
|---|---|---|
| A | 0.669 / 1.784 | 0.308 / 0.563 |
| B | 0.256 / 0.307 | 0.157 / 0.248 |
| C | 0.160 / 0.223 | 0.132 / 0.134 |
| D | 0.287 / 0.598 | 0.205 / 0.300 |
| E | 0.403 / 2.969 | 0.234 / 0.602 |

**In the browser** (load time as the page sees it, including queueing; `before/` and `after/maps-*.json`):
- before: 76 requests, median 1.93 s, maximum 6.36 s;
- after: 84 requests, median 1.34 s, maximum 2.19 s.

## Browser cache behaviour
`--cache-test`, `after/maps-after.json` → `cacheTest`:
- **Old tiles do get cached:** an engine tile URL loaded twice was served from the browser's disk cache the second time (`Cache-Control: public, max-age=86400`).
- **The app avoids them:** it requested only `/api/display/tiles/…` URLs, 84 requests, all `X-LunaOps-Renderer: lunaops_tiles 0.1.0`. **0 engine tile URLs** were requested and **0 first requests** were served from cache.
- **Repeats:** the 6 cache hits in each run are repeats of a tile already fetched earlier in the same run.
- **Result:** corrected tiles therefore appear at once for any page that loads the new build.

## Tests
| Test | Result | Log |
|---|---|---|
| `lunaops_tiles` package tests | **33 passed**. Synthetic: placement on a plane within 0.1 source pixel; no grid on a plane when reduced or enlarged; no creases when a smooth bowl is enlarged; partial, outside and aligned edges; NaN and numeric nodata holes, reduced and enlarged; rotation refused; the engine's colours. Real LOLA: the same transparency and brightness as the engine on 7 tiles; line score < 1.3 on 6 tiles where the engine has grids; the 20 m level alone; out-of-range zoom. API: info, route order ahead of the catch-all, headers, other paths. | `logs/01_pytest_tiles.log` |
| Landing package tests (run separately, AUD-02) | 35 passed | `logs/10_pytest_landing.log` |
| Comms package tests | 57 passed | `logs/11_pytest_comms.log` |
| Engine tile test `tests/test_phase1.py::test_tiles_render_from_relative_registry_paths` (engine route still works) | 1 passed | `logs/12_pytest_engine_tile_test.log` |
| Frontend `tsc`, `npm test`, build | 0 errors; strings 1369 keys, 0 problems; a11y 40 components, 52 colour pairs, 0 problems; moon-geo 238,972 checks; build OK | `logs/03_typecheck.log`, `logs/04_npm_test.log`, `logs/05_build.log` |
| Browser: South Polar Map at 6 zoom levels; Landing map with and without raster | All tiles 200 from `/api/display/tiles`; no console errors; images as above | `logs/02_maps_before.log`, `logs/06_maps_after.log` |
| Live route checks | `/api/display/tiles/info` (the served `code_hash` equals the local package hash `81fccac8…`); headers; the engine route still 200 | `logs/display_tiles_info.json` |

**Server:** to load the new routes, the one server started earlier in this session was stopped and started again, twice: once for the first build and once for the final renderer. No duplicate server was run. Logs: `logs/server_first_run.log`, `logs/server.log`.

## Unresolved limitations
1. **240 m-only terrain enlarged ×4 or more** (60–80° S, zoom 7+):
   - cubic enlargement leaves faint residual pixel structure, with line scores of 1.0–1.6 against up to 3.6 for the engine;
   - this reflects the 240 m data's own resolution;
   - in the zoom-7 test tile near the pole, the 20 m product covers it.
2. **Radial lines converging on the south pole** are still visible inside craters near Site01, before and after. They converge on the pole's position in the view, consistent with LOLA polar-orbit ground tracks in the terrain products. They are not drawn by the renderer, and no change was attempted.
3. **Product edges:**
   - pixels only partly covered by a finer product show the coarser product, so a finer product's footprint can be up to one tile pixel smaller than the engine drew (Site01 5 m: 57% against 58% of tile 7/63/64);
   - a visible change in sharpness at product edges is the change in data resolution.
4. **The app page's own caching:** `index.html` is served with `Last-Modified` and an ETag but no `Cache-Control`, by the engine's `main.py`, which was not changed. A browser that heuristically reuses a cached copy of the old page could keep requesting the old tile URLs, and so the old cached tiles, until the page is reloaded. Each new build gives the page a new `Last-Modified`, so revalidating browsers get the new page.
5. **Not validated:** the package is display-only and not scientifically validated. The engine's own `/api/tiles/{z}/{x}/{y}.png` still produces the old images, until the fix is folded into `tiles.py` at a future engine re-validation.
6. **Not run:** the full engine test suite (440 tests) remains deferred to Phase 7. Only the engine's tile test was run.

## Contents
| Path | What it is |
|---|---|
| `baseline/` | `integrity_before.txt`; originals of `start.py`, `MapView.tsx` and `LandingMap.tsx`; frontend and `dist` hashes |
| `before/`, `after/` | Browser JSON and screenshots: before is the engine route, after is the final package |
| `after_first_run_bilinear_only/` | The intermediate browser run |
| `images/` | Side-by-side comparisons; `images/tiles/` has the tile pairs |
| `scripts/` | `integrity.py`, `tile_verification.py`, `compare_shots.py`, `level_probe_package.py`, `maps_body.mjs` (with the runnable `maps.mjs`), and copies of the addendum's `level_probe.py` and `ovr_probe.py` |
| `logs/` | As referenced above |
| `package_snapshot/` | The package source as tested |
| `SHA256SUMS` | Every file in this folder (LF line endings) |
