# AUD-08: out-of-range coordinates shown as a selected site on the South Polar Map (2026-11-14)

**Scope:** `frontend/src/components/MapView.tsx` only (`logs/source_changes.diff`; original in `baseline/originals/`).

**Not changed:**
- backend, `tiles.py`, algorithms, datasets, labels and existing evidence;
- AUD-05, as instructed.

Phase 7 was not started.

## Root cause
`MapView` drew the selected-site marker and the "Selected …" readout for any finite typed coordinates south of 60° S:
- the marker effect checked `isFinite` and `lat > -60`;
- `siteOnMap` checked `isFinite` and `lat <= LIMIT_LAT`.

So:
- −95 was projected beyond the pole and labelled "Selected 95.000° S";
- −90.0001 was rounded to "Selected 90.000° S";
- longitude 400 was shown as "40.000° E" and −361 as "359.000° E".

The Site tab passes the typed values unchanged (`SiteView.tsx:33–34, 81`).

## Fix
- `MapView` now derives the selected site with `parseSite` from `frontend/src/lib/moonGeo.ts`, the same rule as the sidebar (AUD-01), the backend and the Site explorer: latitude −90 to 90, longitude −360 to 360.
- The marker, the view animation, the "centre on site" button and the readout use only that validated site. Its longitude is normalised to 0–360°, which `fmtLatLon` already did for display.
- Invalid input: no marker and no readout. The sidebar keeps the typed text, `aria-invalid` and the inline message (AUD-01, unchanged).
- Not changed:
  - the existing "south of 60° S" map limit;
  - the comparison-candidate drawing;
  - the result view's map (`ResultWorkspace.tsx`, which passes the engine's validated result coordinates; code-reviewed, unaffected).

## Results (Site tab, South Polar Map, 1440 px)
`before/aud08-before.json` against `after/aud08-after.json`; screenshots in `before/` and `after/screenshots/`.

"Marker" means gold selected-ring pixels in a 120 px box at the map centre. The map pans to a selected site.

| Input | Before: readout / marker / centre button | After: readout / marker / centre button | Sidebar after (value kept, invalid flag) |
|---|---|---|---|
| Latitude −95 | "Selected 95.000° S, 222.510° E" / 96 px / enabled | **none / 0 / disabled** | −95 kept; latitude `aria-invalid` |
| Latitude 95 | none / 0 / disabled (north of the map) | none / 0 / disabled | 95 kept; latitude invalid |
| Latitude −90.0001 | "Selected 90.000° S, 0.000° E" / 96 / enabled | **none / 0 / disabled** | Kept; latitude invalid |
| Longitude 400 | "Selected 89.463° S, 40.000° E" / 96 / enabled | **none / 0 / disabled** | 400 kept; longitude invalid |
| Longitude −361 | "Selected 89.463° S, 359.000° E" / 96 / enabled | **none / 0 / disabled** | −361 kept; longitude invalid |
| Latitude −90 (valid) | "Selected 90.000° S, 0.000° E" / 96 / enabled | Same | No invalid flag |
| Latitude 90 (valid, north pole) | none / 0 / disabled | Same: valid but outside the south polar map; no misleading label | No invalid flag |
| Longitude −360 (valid), latitude −85 | "Selected 85.000° S, 0.000° E" / 96 / enabled | Same | No invalid flag |
| Longitude 360 (valid), latitude −85 | "Selected 85.000° S, 0.000° E" / 96 / enabled | Same | No invalid flag |
| Site01 (valid) | "Selected 89.463° S, 222.510° E" / 96 / enabled | Same | No invalid flag |

- **Console and requests:** no console errors or warnings in either run. Coverage requests were sent only for valid coordinates (the AUD-01 behaviour).

**Observation, not part of AUD-08 and not changed:**
- **What happens:** in one row ("valid Site01 (reset)" right after −90.0001) the readout and the marker were correct, but the marker was not at the map centre, in both runs. The script changes both fields within milliseconds, so the map briefly received a valid intermediate point (−89.463°, 0° E). Two 300 ms pan animations then overlapped, and the view stopped near the first point (`after/screenshots/aud08-07-…png`).
- **Status:** pre-existing behaviour of `MapView`'s pan animation, identical before and after. The "centre on site" button recentres the view.
- **Possible remedy, if wanted:** cancel the running animation before starting a new one.

## Checks
| Check | Result | Log |
|---|---|---|
| Type check | 0 errors | `logs/02_typecheck.log` |
| `npm test` | check-strings 1369 keys, 0 problems; check-a11y 40 components, 52 colour pairs, 0 problems; check-moon-geo 238,972 checks | `logs/03_npm_test.log` |
| Build | OK | `logs/04_build.log`, `after/dist_sha256.txt` |
| Browser before/after | As above | `logs/01_before.log`, `logs/05_after.log` |
| Frontend files changed | `src/components/MapView.tsx` only | `logs/frontend_files_sha256_after.txt` against `baseline/` |
| Backend fingerprints, `report.json`, `tiles.py` | Unchanged | `baseline/backend_fingerprints.txt` = `logs/backend_fingerprints_after.txt` |
| Existing evidence | All 26 folders with a `SHA256SUMS` verify (one with CR stripped, AUD-03) | Run at the end of this task |

The existing server (started for the previous corrections) was used; no second server was started.

## Not verified
- The result view's map with an invalid typed site was not exercised in the browser. It receives the engine's result coordinates, not typed text.
- Pointer-driven readout (hover) was not exercised.
