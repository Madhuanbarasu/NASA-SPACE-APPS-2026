# Landing hazard map: "NASA slope product" option removed (2026-11-14)

This is a presentation-only change, made at the owner's request. Two frontend files changed (13 lines; the originals are in `originals/` and the diff is `changes.diff`). No backend, data manifest, terrain product, NASA dataset, algorithm, API or validation status was changed (see `backend_integrity.txt`).

## Why the option did not work

The hazard map's raster radio group offered `nasa_slope`. The NASA PGDA slope raster belongs to the Site01 5 m product set (PGDA 78). The landing API reports the layer `available: true` only there; it returns false, for example, at 85.3305° S, 285.2104° E and at 88.5° S, 60° E, where the 20 m LDEM is used. Everywhere outside Site01 the option was therefore a permanently disabled control.

At Site01 the layer image itself loads (HTTP 200).

## Change

- **`frontend/src/components/LandingView.tsx`:**
  - `nasa_slope` is removed from the offered rasters (`RASTERS`).
  - The default is the named constant `DEFAULT_RASTER = "slope"`, unchanged in value.
  - A safety effect resets any raster that is no longer offered to the default. The layer choice is component state and is not stored in the browser, so no old session can bring the option back; the effect is a guard only.
- **`frontend/src/i18n/en.ts`:** the now-unused option label `landing.layers.nasa_slope` is removed.

**Kept:**
- the backend `nasa_slope` layer route and data;
- the "NASA PGDA 78 slope product (cross-check)" statistics row and the footprint "NASA slope" metric, which show "unavailable" when absent;
- the `RasterLayer` type in `LandingMap.tsx`;
- all other options, rendering and legends.

## Checks

| Check | Result | Log |
|---|---|---|
| `tsc --noEmit` | 0 errors | `logs/01_typecheck.log` |
| `npm test` | Exit 0: check-strings 0 problems (1,364 keys), check-a11y 0 problems, check-window 20/20 | `logs/02_npm_test.log` |
| Production build | Exit 0 | `logs/03_build.log` |
| Browser check (one headless Chrome, existing server) | **10/10 passed**, 0 console errors, every layer image response 200 | `verify/verify.json`, `logs/04_verify.log` |

The browser check covered Site01 and 85.3305° S, 285.2104° E at 1920, 1440, 1024, 390 and 320 px. In every case:
- **Options offered:** none, elevation, slope, roughness, coverage, uncertainty, slope above threshold. There was no NASA option and no "NASA slope product" text in the selector.
- **Default:** "slope".
- **Switching:** every option selects. Elevation, roughness, coverage and uncertainty each load their own layer image; slope was already loaded. "Slope above threshold" asks for a threshold first, as before.
- **Layer requests:** `nasa_slope` was never requested.
- **Statistics:** the NASA slope statistics row is still present.
- **Layout:** no horizontal scroll, nothing past the viewport, no clipped control.

Screenshots: `verify/screenshots/`.

**Not tested in the browser:** the fallback for an unlisted saved value, because there is no saved state to inject. It is covered by the code above and the type check.
