# Landing hazard map and footprint findings: investigation and repair (2026-11-14)

This is a frontend-only repair, made at the owner's request. Five frontend files changed; the originals are in `originals/` and the diff is `changes.diff`. No backend, landing algorithm, engine, data manifest, NASA dataset, cache, validation label or report was changed (`backend_integrity.txt`). The removed NASA slope option was not restored.

## 1. Why the hazard map was not visible

**Root cause.** The landing server keeps only its latest 3 screenings (`backend/lunaops_landing/assess.py`, `CACHE_MAX = 3`). Any further screening pushes the oldest one out: another site, the mission dashboard, another tab, or test runs against the same server, including mine earlier today. The screening on screen then no longer exists on the server:
- Its layer images return 404.
- Its footprint updates return 404.

**What the frontend did with that 404 (reproduced in the browser before the fix; `diagnosis/before_fix/`, `logs/02_before_fix_evict.log`):**
- Switching to Elevation requested `elevation.png`, which returned 404. The overlay was not drawn, and no message appeared. The map kept showing the earlier slope image while the legend said Elevation (screenshot `evict-after-layer-switch-1440.png`).
- Changing the footprint radius returned 404 and showed "The screening could not be run: This assessment is no longer held by the server…".
- Layer images already in the browser cache still appeared, which made the failure intermittent.

**Category:** a frontend error-handling defect, triggered by the backend's deliberate small cache. It was not a tile, projection or missing-data fault:
- Backdrop tiles returned 200 at every site (9 tiles at 85.33° S, 9 at 88.5° S, 6 at Site01; slowest 516 ms; none pending; `diagnosis/diagnosis.json`).
- The tile grid `/api/tiles/meta` and the tile URLs `/api/display/tiles/z/x/y.png` match the South Polar Map's.
- The overlay sits on the window's own pixel-edge bounds.

**Fixes:**
- **`LandingMap.tsx`:**
  - A failed overlay image is removed, so no image of another layer stays under the legend. The base map, outlines and footprint stay.
  - A message is shown over the map.
  - LandingView is told about the failure.
- **`LandingView.tsx`:**
  - When the server answers 404 for a layer or footprint, the screening is re-run with the configuration the server reported for it: site, window, resolved product, roughness window and depression limits, plus the current footprint.
  - The assessment id is a hash of those inputs, the product checksum and the landing code. The server therefore recomputes the same result from the same data, and the browser check confirmed the id was unchanged.
  - The overlay is then reloaded (new `rev` query parameter, which the server ignores).
  - Re-runs are limited to two per screening, so there is no loop.
- **`LandingView.tsx` (no-data case):** when the selected value layer has no values in the window, a "No data … (coverage unavailable)" message is shown over the base map.
- **`client.ts`:** API errors now carry the HTTP status, and the layer URL accepts `rev`.
- **`landing.css`:** style for the on-map message.

## 2. Why the four terrain findings were unavailable

The reported text ("Requires higher-resolution data. No DEM pixel centre lies inside the footprint" for all four findings) is reproduced exactly when the **240 m product** (`LDEM_60S_240MPP_ADJ`) is used with the default 50 m radius (`api/`, `diagnosis/`):

| Site | Product | Pixel (m) | Footprint across (pixels) | Pixel centres in footprint | Findings |
|---|---|---|---|---|---|
| Site01 | auto, which selects 5 m | 5 | 20.0 | 316 | values calculated |
| Site01 | 20 m | 20 | 5.0 | 16 | values calculated |
| Site01 | 80 m | 80 | 1.3 | 2 | higher-resolution data needed (1.3 px) |
| Site01 / 85.33° S / 88.5° S | 240 m | 240 | 0.4 | 0 | **"No DEM pixel centre lies inside the footprint"** |
| 85.33° S, 285.21° E | auto, which selects 20 m | 19.97 | 5.0 | 21 | values calculated |
| 88.5° S, 60° E | auto, which selects 20 m | 20.0 | 5.0 | 20 | values calculated |

- The automatic choice ("Finest product covering the window") never picks 240 m at these sites. The 240 m result arises when 240 m is selected in "Terrain product".
- **Contributing defect, fixed:** a product chosen for one site stayed selected after moving to another site. When that product does not cover the new site (for example 5 m from Site01 at 88.5° S), the screening failed with 422. The selection now returns to "Finest product covering the window" whenever the chosen product does not cover the site (check D).

**Sampling logic: no defect.**
- The footprint test uses the window's own pixel-centre coordinates.
- The window, bounds and centres are consistent: `Window.bounds` and `Window.centres` use the same transform, and the inside-window test uses the same projection and point scale.
- A 100 m wide footprint inside one 240 m pixel cannot be resolved. Area-weighted sampling would return the value of the 240 m pixel(s) it touches, and the Horn slope there spans a 720 m baseline. That describes a 720 m area, not the footprint.
- The server already marks any footprint under 3 pixels across as "Requires higher-resolution data", even when pixel centres fall inside (the 80 m row). Area weighting would change the reason text, not the status. It was therefore not introduced, and the algorithm is unchanged.

**What changed instead:** the footprint card now explains the cause. It names the current product and its pixel size, and lists the finer registered products that cover the site (or says none does). It asks the user to choose the finest product and re-run. Nothing is resampled.

## 3. Obstacles

No imagery or obstacle dataset is registered (`obstacle_dataset_check.txt`). The only LROC files are 100 m WAC illumination statistics used for V-12, not surface images. The finding stays "Not available - manual review required".

## 4. Checks

| Check | Result | Log |
|---|---|---|
| `tsc --noEmit` | 0 errors | `logs/03_typecheck.log` |
| `npm test` | exit 0: check-strings, check-a11y, check-moon-geo, check-window 20/20 | `logs/04_npm_test.log` |
| Production build | exit 0 | `logs/05_build.log` |
| Browser verification (one headless Chrome, existing server) | see below | `logs/06_verify.log`, `verify/` |

Browser verification results:
- **A. Eviction (85.33° S):**
  - The screening was pushed out three times, by layer switch, footprint change and leaving then re-entering the tab.
  - After the fix: elevation 404, then a re-run (200, same id `ac4933775c25ea281be5`), then `elevation.png?rev=1` 200.
  - The footprint 404 was followed by a re-run with no error shown. After re-entering the tab the layer loaded with 200.
  - **Pass.**
- **B. Three sites × 1920/1440/1024/390/320:**
  - Checked: map present (larger than 200 px), the 5 layers (elevation, roughness, coverage, uncertainty, slope) each showing its legend, every layer response 200, four terrain findings with values, obstacles "manual review", no error, no horizontal overflow.
  - The first evaluation gave **9/15**. All 6 failing rows failed only the "at least 5 layer-image network responses per width" criterion. Chrome serves images it already holds from memory without network events, so that count depends on caching.
  - Re-evaluated without it, with the original verdicts kept: **15/15** (`verify/verify_evaluated.json`). The screenshots of the failing rows show the overlay drawn.
- **C. 240 m product at 85.33° S:** the map is shown, the four findings are "Requires higher-resolution data", and the hint names 20 m and 80 m as finer covering products. **Pass.**
- **D. 5 m product chosen at Site01, then site changed to 88.5° S:** the selection returned to "Finest product…" and the screening ran (200). **Pass.**
- **Console:** 3 messages, all from the deliberate eviction in A: two 404s and the browser failing to decode the 404 body as an image. None came from B, C or D.

**Not tested in the browser:**
- the "No data" map message, because no selectable layer at these sites lacks values;
- the two-re-run limit, because there was no persistent failure to provoke it.

Both rely on the code and the type check only.

## 5. Remaining scientific limitations

- The 5 m Site01 product has a LOLA return in about 9.5% of its pixels; the rest are interpolated. Findings at 5 m describe the DEM surface, not measured metre-scale terrain.
- 20 m products resolve a 50 m radius footprint with 5 pixels across. Coarser footprints or products give "Requires higher-resolution data".
- The 80 m and 240 m products cannot resolve footprints of a few tens of metres.
- No obstacle detection is possible with the registered data.
- The server still keeps only 3 screenings. The frontend now recovers by re-running, which takes about 0.3 to 2 s at these sites.

Note: in `logs/01_diagnose.log` and `diagnosis/diagnosis.json` the findings text is missing every letter "s". The diagnosis script escaped a regular expression wrongly. The findings statuses and map measurements are unaffected, and the verification script reads the text correctly.
