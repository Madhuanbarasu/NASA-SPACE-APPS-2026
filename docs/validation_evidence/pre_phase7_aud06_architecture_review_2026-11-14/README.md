# AUD-06 architecture review: map hillshade grid (2026-11-14)

**Review only. Nothing was implemented:**
- `backend/lunaops/api/tiles.py` is unchanged (SHA-256 `05b1df86…`);
- no new package was created;
- fingerprints are unchanged (code `84cbd4ea…`, suite `1632af16…`).

Defect evidence: `../pre_phase7_audit_2026-11-14_addendum/`.

## 1. The defect and its exact mechanism
- **Where:** `render_tile` (`backend/lunaops/api/tiles.py:50–106`) reads each LOLA level with:

  ```python
  src.read(1, window=win, out_shape=(r1 - r0, c1 - c0), boundless=True, fill_value=…, resampling=Resampling.bilinear)
  ```

- **What rasterio does:** in rasterio 1.5.2 (GDAL 3.12.2) a `boundless=True` read builds an in-memory VRT whose source carries the requested resampling (`rasterio/vrt.py:188`). It then reads that VRT into `out_shape` with `vrt._read(indexes, out, Window(...), None)`, with no resampling argument (`rasterio/_io.pyx:605–615`).
- **Result:** the reduction to the tile size is effectively nearest-neighbour, whatever `resampling` says. This matches the addendum's measurement: bilinear and average gave identical output (line score 3.23 / 2.50).
- **Why a grid:** nearest-neighbour reduction of the 20 m product by 2.84 (zoom 7, 56.8 m/px) alternately skips 2 and 3 source pixels. That beats with a period of about 1 / (3 − 2.84) ≈ 6.3 tile pixels, matching the measured line spacing of 6.1–6.6 px. The hillshade gradient turns each skip into a visible line.
- **Upsampling too:** the 240 m product shows the same effect when upsampled (blocky steps every 4.2 px).
- **Clean paths:** a normal (`boundless=False`) read applies bilinear and is clean (0.89 / 0.69).

**Scope:** display only.
- `render_tile` is used only by `GET /api/tiles/{z}/{x}/{y}.png` (`backend/lunaops/api/main.py:371–377`), and `tile_meta` by `/api/tiles/meta`.
- Neither feeds any analysis, horizon, landing finding or comms result. The engine reads DEMs for science through `lunaops.engine.dem` and the horizon code, not through tiles.
- The tile metadata already labels the images "Cartographic hillshade … not the lunar Sun".

## 2. What a change to `tiles.py` sets off (verified in the code)
- `lunaops/fingerprint.py`: `code_fingerprint()` hashes every `.py` under `backend/lunaops`, so any edit to `tiles.py` changes it.
- `lunaops/engine/provenance.py:82`: if the report's `code_fingerprint` differs, `label_blockers()` returns "the validation report was produced by different code". **No quantity can then be labelled Validated** until the validation report is regenerated: `backend/validation/report.json`, by the full suite.
- `lunaops/engine/analysis.py:84–88`: result IDs include `code_fingerprint()`. **All 74 cached results** become unreachable and would be recomputed on request.
- `lunaops/engine/horizon.py:277`: horizon cache keys include `code_fingerprint()`. **All 27 cached horizons** are invalidated.
- `frontend/src/components/MapView.tsx`: the slow-tile memory is keyed by the code fingerprint and resets. This is harmless.

## 3. Options compared
| Aspect | Option 1: minimal fix inside `tiles.py` | Option 2: separate tile-rendering package (engine unchanged) |
|---|---|---|
| **Files and modules** | `backend/lunaops/api/tiles.py` (`render_tile` read step, about 10 lines); a regression test in `backend/tests/` (changes the suite fingerprint); a regenerated `backend/validation/report.json` | **New:** `backend/lunaops_tiles/` (`__init__.py`, `render.py`, `api.py` with `install(app)`, `tests/`). **Changed:** `start.py` (one install call, as for landing and comms). **Frontend, recommended variant:** the tile URL in `MapView.tsx` (2 places: the OpenLayers URL and the compose `fetch`) and `LandingMap.tsx` (1 place). **Unchanged:** `backend/lunaops/**`, `backend/tests/**`, `backend/validation/**` |
| **Architectural complexity** | Lowest code change, but the highest process cost: re-validation, report regeneration, cache rebuild | Moderate: a small package (about 80 lines plus tests) on the established Phase 5/6 pattern. Two tile renderers exist until the engine is next re-validated; the engine's stays reachable for comparison. |
| **API compatibility** | Identical URLs and responses (PNG, 256 px, same tile grid) | **2a:** override the same path `/api/tiles/{z}/{x}/{y}.png`. The URL is unchanged, but the engine's route is silently shadowed. **2b (recommended):** a new path, for example `/api/display/tiles/{z}/{x}/{y}.png`, with the frontend switched to it. In both, `/api/tiles/meta` stays the engine's own, so the grid, extent and levels are guaranteed identical. |
| **Browser cache** | Tiles are sent with `Cache-Control: public, max-age=86400`. Same URL, so browsers may show cached grid tiles for up to 24 h. | **2a:** same 24 h problem. **2b:** new URLs, so corrected tiles appear immediately. |
| **Terrain data handling** | Same registered DEMs and levels (`usable_levels`, `resolve_dem_path`); only the read call changes: clip the window to the dataset and use `boundless=False` | The same: the package **imports** `usable_levels` and `resolve_dem_path` from `lunaops.engine.dem`, and `tile_meta`, `TILE` and `_empty` from `lunaops.api.tiles` (read-only reuse, no copies). Only the read call is corrected. No dataset is touched. |
| **Duplication** | None | The level loop and the 8-line cartographic hillshade of `render_tile` are re-implemented. They are inline in `render_tile`, so they cannot be imported without editing `tiles.py`. This is display code, not a scientific calculation; no engine computation is duplicated. |
| **Scientific calculations** | Numerically unchanged, but formally re-labelled: every Validated label is withdrawn until re-validation, and every cached result and horizon must be recomputed | Unchanged, byte for byte: same engine, same fingerprints, same labels, same caches |
| **Required tests** | Line-score regression on a 20 m tile (score below about 1.0); the existing `test_tiles_render_from_relative_registry_paths`; the full automated test suite and validation run to regenerate `report.json`; a check of the label state after regeneration | **Package tests:** (1) line score of zoom-7 tile 63/64 below about 1.0 for the 20 m level and the composed tile, against 3.23 now; (2) alpha mask identical to the engine's `render_tile` on sample tiles at zooms 1, 4, 7 and 11; (3) mean grey within a small tolerance of the engine tile where no artefact exists; (4) route test: the new path serves the package's renderer and `/api/tiles/meta` is unchanged; (5) render time for zooms 1–4, where the 5 m product makes tiles slow; (6) fingerprints unchanged. **Engine:** the existing engine tests unchanged, plus the landing and comms suites. **Browser:** a South Polar Map check at about 10 km scale, the composed zoomed-out tiles, and the Landing hazard-map backdrop. |
| **Fingerprints** | Code fingerprint changes (and the suite fingerprint, if a test is added). The report must be regenerated, which requires owner approval because `report.json` is protected. | **None.** Code fingerprint `84cbd4ea…` and suite fingerprint `1632af16…` unchanged. |
| **Regression risk** | Low in the renderer itself; **high for the rest of the system**: Validated labels withdrawn until re-validation; 74 results and 27 horizons recomputed (time and memory on this machine); any re-validation failure blocks labels | **Low to moderate:** (a) small sub-pixel differences at product edges, where a clipped window replaces the boundless one, mitigated by test 2; (b) a different read path could change render times for zoomed-out tiles, mitigated by test 5 and the frontend's existing composition and timeouts; (c) two code paths to maintain, mitigated by a provenance note in the package and a plan to fold the fix into the engine at its next planned re-validation |

## 4. Recommendation
**Option 2, variant 2b:** a separate `backend/lunaops_tiles` package on a new route, with the frontend tile URL switched.

Reasons:
1. **The validated engine stays intact.** It is byte-identical, so labels, the validation report, the 74 cached results and the 27 horizons are untouched, and the display defect never causes a re-validation. This follows the project rule used for Phases 5 and 6: new backend code lives outside `backend/lunaops`.
2. **Reuse without duplicating science.** The package reuses the engine's tile grid (`tile_meta`), DEM registry and path resolution by import. It re-implements only the read step and the cartographic hillshade, which are not scientific quantities.
3. **Explicit and cache-safe.** A new path makes the renderer's provenance explicit: no silently shadowed engine route. It also avoids up to 24 h of stale cached tiles in browsers.

**Later:** at the next planned engine re-validation, the same read fix can go into `tiles.py`, and the package and route can be retired.

## 5. Implementation outline (for approval; not started)
1. **Baseline:** fingerprints, `tiles.py` hash, sample engine tiles and their line scores.
2. **`lunaops_tiles/render.py`:** `render_tile(z, x, y)`, which:
   - uses `tile_meta()` for the grid;
   - for each level, intersects the read window with the dataset's full window;
   - reads with `boundless=False`, `out_shape` set to the covered tile pixels, and bilinear resampling;
   - leaves uncovered pixels as NaN (coarser levels fill them, as now);
   - applies the same hillshade and RGBA encoding as the engine.
3. **`api.py`:** `GET /api/display/tiles/{z}/{x}/{y}.png`, with the same error handling and cache header, installed ahead of the SPA catch-all.
4. **Wiring:**
   - `start.py`: `install_tiles(app)`.
   - **Frontend:** the tile URLs in `MapView.tsx` (2) and `LandingMap.tsx` (1).
5. **Tests and checks:** the tests in section 3, `tsc`, `npm test` and build, and browser checks. Evidence goes to a new folder.
