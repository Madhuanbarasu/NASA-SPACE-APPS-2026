# Updated findings (addendum to the pre-Phase 7 audit, 2026-11-14)

Original report: `../pre_phase7_audit_2026-11-14/README.md`. That report is not changed. Where this file differs from it, this file is newer.

## AUD-01: out-of-range latitude is not flagged (confirmed defect, Low)
**Evidence** (`logs/layout_metrics_landing_site.json`, copied from `browser_run2/audit-results.json`). Typing latitude −95 gave:
- `"invalid": null`: the field was not marked invalid;
- the hint showed the server's message, "Latitude -95.0 is outside -90 to 90 degrees.";
- `runDisabled: true`;
- one network failure, `422 /api/coverage?lat=-95&lon=222.510447`;
- one console error: "Failed to load resource … 422".

**Cause:** two places check only that the value is a finite number, not that it is in range.
1. `frontend/src/components/Sidebar.tsx:38–39`, function `Sidebar`: `coordsGiven`, `latBad` and `lonBad` use `isFinite` only. The invalid flag (`aria-invalid`, lines 85 and 91) and the hint (line 99) therefore never trigger for −95.
2. `frontend/src/state/store.tsx:252–264`, function `StoreProvider`: the terrain-coverage `useEffect` checks only `isFinite` at line 256, so it sends `/api/coverage` for out-of-range values. That is the request that returns 422.

**Correction to the original report:** it named only `Sidebar.tsx:39` plus "the store's coverage effect". Both locations need the change.

**Recommended correction (not applied):**
- Use the existing `parseSite(lat, lon)` (`frontend/src/lib/moonGeo.ts:82`; latitude −90 to 90, longitude −360 to 360, the same rules as the backend) in both places:
  - `latBad`/`lonBad` should be true when the value is non-empty and out of range;
  - the coverage effect should return early when `parseSite` returns `null`.
- `SiteExplorer.tsx:22` already uses `parseSite`, so this also makes the sidebar and the explorer consistent.
- Update `invalidCoordinates` (`frontend/src/i18n/en.ts:170`), which currently says only "must be numbers in degrees", to state the ranges.

## AUD-04: 76 px blank below "Landing footprint" at 1920 px (confirmed, Low, cosmetic)
**Evidence** (`logs/layout_metrics_landing_site.json`):
- `1920-landing.blanks = [{ card: "landing-footprint", gap: 76, h: 1252 }]`, as recorded by the audit script: `gap` is the empty vertical space below the card and `h` is the card's height.
- At 1440, 1024, 390 and 320 px the Landing tab has no blanks.

**Limit of the evidence:** `browser_run2/screenshots/layout-1920-landing.png` shows only the first 1080 px of a 3487 px page, so the gap itself is below the screenshot. The finding rests on the DOM measurement and the CSS below, not on the image.

**Cause:**
- `frontend/src/components/LandingView.tsx:435–438`: wide screens use two columns, `[siteCard, footprintCard]` and `[mapCard, terrainCard]`.
- `frontend/src/styles/landing.css`:
  - `:20` `.landing-band { align-items: stretch }` makes both columns the same height;
  - `:21` the columns are flex columns;
  - `:22–23` only the map card grows (`flex: 1 0 auto`), with a map minimum height of `clamp(360px, 58vh, 620px)`.
- So the right column can absorb extra height, but the left column cannot:
  - at 1440 px the left column is taller and the map card grows, so there is no gap;
  - at 1920 px the right column (map at its 620 px cap plus the terrain card) is 76 px taller, so the extra space appears under the last left card.

**Recommended correction (not applied):** in `landing.css`, let the last card of each `.landing-col` grow (`flex: 1 0 auto`), so the card ends flush and the space falls inside it. Accepting the gap is also reasonable.

## AUD-05: lighter rectangle on the Landing hazard map (possible issue, cause not confirmed)
**Evidence:** `browser_run2/screenshots/layout-1920-landing.png` shows a lighter rectangle inside the slope raster, at about x 1295–1648, from y ≈ 580 to the bottom of the image.

**Relevant code:** the map draws a hillshade backdrop from the same server tiles at opacity 0.9, under the semi-transparent hazard raster (`frontend/src/components/LandingMap.tsx:151–159`, `maxResolution: 300`).

**Possible explanations, none tested:**
- a backdrop tile that differs from its neighbours, for example still loading or drawn from different products;
- the tile-drawing problem in AUD-06.

**Not confirmed.** This needs an inspection of the individual backdrop tiles at that view, which requires the server. It stays a possible issue, not a defect.

## AUD-06: faint square grid on the South Polar Map (confirmed defect, Low, display only)
**Evidence in the app:** `../pre_phase7_audit_2026-11-14/browser/screenshots/fail-SITE-05-globe-controls.png` (about 10 km scale near Site01). Fine horizontal and vertical lines appear in patches; they are not visible at the zoomed-out scale in `browser_run2/screenshots/site-map-1440.png`.

**The grid is in the server's tile images, not added by the browser:**
- `scripts/tile_probe.py` called the app's own `render_tile` offline (no server) for the tiles around Site01. The zoom-7 tile 63/64 (56.8 m/px) shows the grid (`images/tile_7_63_64_x3.png`).
- Those tiles are fully opaque, so neither CSS background (the 48 px shell grid at 2.8% alpha, or the diagonal "no tile" hatch) can show through.
- The map uses the server tiles directly at this zoom (`MapView.tsx` composes tiles only at ≥ 400 m/px).

**Which data carries it** (`scripts/level_probe.py`, `logs/level_probe_output.txt`). This draws the same tile from each LOLA level alone, using the same read call as `tiles.py`:

| Level | Line score cols / rows |
|---|---|
| 20 m, read as in `tiles.py` | **3.23 / 2.50** (`images/lvl_20m.png`, grid visible) |
| 20 m, file at full detail (centre 512 px) | 0.66 / 0.59 |
| 80 m, read as in `tiles.py` | 0.95 / 0.87 |
| 240 m, read as in `tiles.py` | **3.64 / 2.27** (enlarged from 240 m; not checked visually) |
| 5 m Site01 | covers 58% of this tile |

`render_tile` writes the finer levels last. The 5 m product therefore replaces the 20 m data over 58% of the tile, which is why the grid appears only in patches: where the 20 m data is shown.

**Root cause** (`scripts/ovr_probe.py`, `logs/ovr_probe_output.txt`; rasterio 1.5.2, GDAL 3.12.2). The same 20 m tile area, read in different ways:

| Read of the 20 m product for zoom-7 tile 63/64 | Line score cols / rows |
|---|---|
| Built-in 40 m overview, at its own size | 0.68 / 0.65 |
| Full detail, overviews off, then bilinear to 56.8 m | 0.82 / 0.66 |
| Full detail, overviews off, then average | 0.73 / 0.61 |
| 40 m overview opened directly, bilinear to 256 px | 0.89 / 0.69 |
| 40 m overview, then `reproject` with bilinear | 0.85 / 0.70 |
| **Default open, `boundless=True` (as `tiles.py`), bilinear** | **3.23 / 2.50** |
| **Default open, `boundless=True`, average** | **3.23 / 2.50** |
| Default open, `boundless=False`, bilinear | 0.89 / 0.69 |
| Default open, `boundless=False`, average | 1.70 / 1.26 |

- The grid appears only with the `boundless=True` read used by `backend/lunaops/api/tiles.py`, function `render_tile`, lines 83–86 (`src.read(1, window=win, out_shape=…, boundless=True, fill_value=…, resampling=Resampling.bilinear)`).
- On that path the requested resampling has no effect: bilinear and average give identical results.
- The terrain file, its overviews and the non-boundless read are all clean.

**Line score:** the image is high-passed (each pixel minus the mean of its four neighbours). Each column and each row of that is averaged, and the average magnitude is divided by the expected noise level. About 0.6–0.9 means no straight lines; around 3 means clear 1-pixel lines along columns or rows.

**Impact:**
- Display only. `render_tile` is used only by `/api/tiles/{z}/{x}/{y}.png` (`backend/lunaops/api/main.py:371–374`), which serves the South Polar Map and the Landing hazard-map backdrop.
- No analysis, horizon, landing finding or comms result reads these tiles. The tile metadata labels them "Cartographic hillshade … not the lunar Sun".

**Recommended correction (not applied):**
- In `render_tile`, intersect `win` with the dataset's full window and read that part with `boundless=False` (keeping `out_shape` scaled to it). Leave the rest of the tile's pixels as NaN, so they are filled by coarser levels as now.
- Recheck with `scripts/ovr_probe.py` and `scripts/level_probe.py` that the scores drop to about 0.6–0.9 for the 20 m and 240 m levels.

**Constraint and owner decision:** `tiles.py` is inside `backend/lunaops/`, so editing it changes the code fingerprint (`84cbd4ea…`) that binds the validation report. The options are:
- accept the fingerprint change and re-establish validation; or
- move tile rendering into a separate package outside the fingerprinted directories, installed by `start.py` before the existing route, as `lunaops_landing` and `lunaops_comms` are.

**Note on `scripts/ovr_probe.py`:**
- It is copied unchanged.
- Line 10 is a leftover no-op: `exec(... if False else "")` evaluates only `exec("")`, so the path passed as its first argument is never read. Pass any existing path, for example `scripts/level_probe.py`, as in `logs/ovr_probe_output.txt`.
- All three scripts import `lunaops` from `E:\LUNA-OPS\backend`. Run them with `backend/.venv/Scripts/python.exe`.

## Site tab "blank space": false positive (confirmed)
**What the script reported** (`logs/layout_metrics_landing_site.json`): "blanks" below the summary figure cards at every width:
- 1920 px: gap 2835 px;
- 1440 px: 2769;
- 1024 px: 3045;
- 390 px: 4625;
- 320 px: 5030.

**Why it is wrong:**
- `browser_run2/screenshots/layout-1920-site.png` shows the time slider and play control directly under the four figure cards (y ≈ 1045). There is no empty space.
- The gap was measured to the next element the script counts as a card. The timeline, charts and tables in between are not counted, so the "gap" is their height.
- The pattern fits this: at phone widths the figures stack and only the last one is flagged.

No correction is needed in the application.

## Unchanged from the original report
- **AUD-02:** combined pytest run (test tooling).
- **AUD-03:** CRLF in one older checksum file.
- **AUD-07:** empty curated catalogue.
- **Not verified:** the list in section 11 of the original report still applies.
