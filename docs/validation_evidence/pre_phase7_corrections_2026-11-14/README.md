# Pre-Phase 7 defect corrections (2026-11-14)

**Scope:** the approved corrections AUD-01 and AUD-04, and the investigation of AUD-05, from `../pre_phase7_audit_2026-11-14/` and `../pre_phase7_audit_2026-11-14_addendum/`. Frontend only.

**Not changed:**
- the backend, including `backend/lunaops/` and `tiles.py`;
- scientific algorithms, datasets and validation labels;
- existing evidence.

Phase 7 was not started.

## Files changed
The changes are in `logs/source_changes.diff`. The originals are in `baseline/originals/`.

| File | Change |
|---|---|
| `frontend/src/components/Sidebar.tsx` | AUD-01: `coordsGiven`, `latBad` and `lonBad` use `parseSite` |
| `frontend/src/state/store.tsx` | AUD-01: the coverage lookup is skipped unless `parseSite` accepts the coordinates |
| `frontend/src/i18n/en.ts` | AUD-01: the `invalidCoordinates` message now states the ranges. This is needed for a correct inline message. |
| `frontend/src/styles/landing.css` | AUD-04: map minimum in the two-column band, and the left column's last card |

No other frontend file changed (`logs/frontend_files_sha256_after.txt` against `baseline/frontend_files_sha256.txt`). The code fingerprint, suite fingerprint, `report.json` and `tiles.py` hashes are unchanged (`baseline/backend_fingerprints.txt` = `logs/backend_fingerprints_after.txt`).

## AUD-01: invalid latitude and longitude (fixed)
**Root cause:** `Sidebar.tsx` (`latBad`, `lonBad`, `coordsGiven`) and the coverage effect in `store.tsx` checked only that the values were finite numbers. Out-of-range values were therefore:
- not marked invalid;
- sent to `/api/coverage`, which answered 422, logging a console error.

**Fix:**
- Both places now use the existing `parseSite` from `frontend/src/lib/moonGeo.ts`: latitude −90 to 90, longitude −360 to 360. These are the backend's rules and the Site explorer's.
- Each field is checked on its own, so only the wrong field gets `aria-invalid`.
- Invalid coordinates are never sent.
- Valid input is unchanged: the request uses the typed values as before, and comparison entries keep the typed values.

**Browser results at 1440 px** (`before/corrections-before.json` against `after/corrections-after.json`, `aud01`):

| Input | Before | After |
|---|---|---|
| Latitude −95, 95, −90.0001 | Not marked invalid; `/api/coverage` → **422** each time; server message shown | Latitude field `aria-invalid="true"`; hint (red) "Latitude must be a number from −90 to 90 and longitude a number from −360 to 360 degrees…"; **no request**; Analyse and Add to comparison disabled |
| Longitude 400, −361 | Not marked invalid; **422** | Longitude field `aria-invalid="true"`; **no request**; same hint |
| Latitude "abc" | Marked invalid; no request | Unchanged |
| Empty latitude | Prompt hint; no request | Unchanged |
| Valid Site01; −90/0; −85/360; −85/−10 | Coverage 200; Analyse enabled | Unchanged: coverage 200 and Analyse enabled. The −85/360 and −85/−10 replies came after the main check's 2.5 s sample, so they were re-checked with a 15 s wait: replies in 0.6–1.5 s (`after/aud01-edge.json`) |
| Console errors and failed requests over the whole run | 6 × "Failed to load resource … 422"; 6 failed requests | **0 and 0** |

Additional checks:
- **Analysis:** an analysis of Site01 (default window) still runs. Its figures (Sunlight 55.5%, Direct-to-Earth 18.3%, Operational overlap 1.4%, Power indicator 0.539) and its validation labels are identical before and after.
- **Unit check:** `scripts/aud01_unit.mjs` runs the exact sidebar and store expressions against `parseSite` in 19 cases, including the ±90 and ±360 edges, NaN, Infinity, `1e3` and whitespace. 19/19 pass (`logs/06_aud01_unit.log`).
- **Screenshots:** `before/screenshots/aud01-latitude-minus95-1440.png` and `after/screenshots/aud01-latitude-minus95-1440.png`.

## AUD-04: 76 px gap below Landing footprint at 1920 px (fixed)
**Root cause** (`landing.css`, two-column band above 1100 px):
- The two columns are stretched to the same height, and only the hazard-map display could grow. Its minimum was `clamp(360px, 58vh, 620px)`, which is 620 px at 1920 × 1080.
- That made the map column 60 px taller than the site/footprint column. The space showed as 76 px of blank below the footprint card (60 px plus the 16 px gap).

**Fix:**
- In this layout the map display's minimum is 360 px, the same floor as before. The display still grows to fill the band, so the map column no longer forces extra height.
- As a fallback, the left column's last card extends to the band's end if the map column is ever the taller one.
- No negative margins and no hidden content.

**Measured** (`before/` and `after/corrections-*.json`, `landing`; Site01 default screening):

| Width | Map display | Blank below Landing footprint | Other cards |
|---|---|---|---|
| 1920 × 1080 | 620 → **560 px** | **76 → 16 px** (the standard gap) | Terrain, candidates and provenance heights unchanged; they move up 60 px |
| 1600 × 900 | 627 → 627 | 16 → 16 | Identical |
| 1440 × 900 | 704 → 704 | 16 → 16 | Identical |
| 1280 × 800 | 981 → 981 | 16 → 16 | Identical |
| 1024 × 768 | 445 → 445 | 16 → 16 | Identical (one column) |
| 390 × 844 and 320 × 640 | 359 / 300, unchanged | 16 → 16 | Identical |

- At every width: no horizontal page scroll, no overlapping cards, and the same count of elements extending past the edge as before. The non-zero counts at 1440, 1280, 390 and 320 px are inside scroll containers and are identical before and after.
- At 1920 px both columns now end on the same line (`spaceBelowLastCard` 60 → 0).
- **Screenshots:** `before/` and `after/screenshots/landing-{1920,1440,1024,390}-footprint-bottom.png`.

## AUD-05: lighter rectangle on the hazard map (cause found, not a defect, no change made)
**Cause:** a transient loading state of the hillshade backdrop, captured by the audit's screenshot.
- The hazard raster is drawn at 85% opacity (the default) over the backdrop. The backdrop is the server's hillshade tiles at 90% opacity (`LandingMap.tsx:159`).
- Where a tile has not arrived yet, the map pane's dark hatch shows through instead. This is the legend's "Hatched: no hillshade image here yet" state.
- The raster therefore looks lighter over tiles that have loaded and darker over those that have not. Once all tiles arrive, the effect disappears.

**Evidence:**
1. **Tile alignment** (`scripts/aud05_tile_alignment.py`, `logs/13_aud05_tile_alignment.log`). The rectangle's edges in the audit screenshot are at x = 1293 and 1648 and y = 579. These match the predicted zoom-11 backdrop tile edges: column 1011 at x 1292.7, column 1013 at x 1648.6, and row 1036 at y 580.7. The rectangle is exactly 2 tiles wide. It does not match the zoom-10 column edges (x 1114.8, 1470.6).
2. **Tile content:** the tiles inside the rectangle are not brighter than their neighbours. The mean grey is 187 and 172 for tiles 1011/1036 and 1012/1036, against 200 for 1010/1036 and 150 for 1013/1036 (`before/tiles/`). All are fully opaque, so the tiles' own brightness does not explain it.
3. **Reproduced:** the screening was run at 1920 px and the new map captured as tiles arrived (`scripts/aud05_repro2_body.mjs`, `before/aud05_repro2/`).
   - At 120 ms there is hatch only.
   - At 600 ms the raster shows lighter tile-shaped rectangles over the loaded tiles and darker areas over the hatch, the same appearance as the audit screenshot.
   - At 4 s it is uniform.
   - A resize from 1440 to 1920 px shows the same hatch at the newly exposed edges for under about 1 s (`before/aud05_repro/`).
4. **Fully loaded:** with all tiles loaded, the raster is uniform under every setting tried: slope at 85%, 100% and 20%, data coverage, elevation, and no raster (`before/screenshots/aud05-*.png`).

**Decision:** no code change. This is the documented "tile still loading" state, it clears within about 1–4 s, and it involves no data or rendering error.

**Optional presentation change, for the owner:** hide the raster until the backdrop tiles under the window have loaded, or use a neutral loading backdrop instead of the dark hatch beneath the raster. This is not implemented.

## New observation, not fixed (outside the approved files)
**AUD-08 (Low):**
- **What happens:** the South Polar Map still plots an out-of-range typed latitude and shows "Selected 95.000° S, 222.510° E" for −95. This happens both before and after the fix; see the two `aud01-latitude-minus95-1440.png` screenshots. The Site explorer beside it correctly shows "No site selected".
- **Cause:** `frontend/src/components/MapView.tsx:313` and `:320` check only `isFinite` and `lat <= LIMIT_LAT` (−60°).
- **Recommended:** use `parseSite` there as well. This needs approval, since `MapView.tsx` was not in the approved file list.

## Tests and checks
| Check | Result | Log |
|---|---|---|
| Type check (`tsc --noEmit`) | 0 errors | `logs/04_typecheck.log`, `logs/11_typecheck_final.log` |
| `npm test` (strings, accessibility, moon geometry) | Pass: string and a11y self-tests; a11y 40 components, 52 colour pairs, 0 problems; check-moon-geo 238,972 checks | `logs/05_npm_test.log`, `logs/12_npm_test_final.log` |
| Production build (`npm run build`, which also runs tsc, check-strings and check-a11y) | Built. The final build after a CSS comment-only edit is byte-identical to the build that was measured. | `logs/07_build.log`, `logs/10_build_final.log`, `after/dist_sha256.txt` |
| AUD-01 unit check | 19/19 | `logs/06_aud01_unit.log` |
| Browser before/after (one headless Chrome, CDP) | As in the tables above | `logs/01_before.log`, `logs/08_after.log`, `logs/09_aud01_edge.log` |
| Backend fingerprints | Unchanged | `logs/backend_fingerprints_after.txt` |
| Existing evidence | All 25 folders with a `SHA256SUMS` verify (`post_phase5_backend_and_ui_fixes_2026-11-12` with CR stripped, as already recorded under AUD-03) | Run at the end of this task |

**Server:** for the visual checks one server was started (its output file `logs/server.log` stayed empty during the run), because none was running; about 3.4 GB of RAM was free at start. No duplicate server was started.

## Not verified
- Screen-reader announcement of the new invalid state: `aria-invalid` and the `aria-live` hint were checked as attributes only.
- The two-column Landing layout at viewport heights other than those listed.
- AUD-05 under slow networks.
- AUD-06 (map grid) is unchanged; it needs the owner's decision recorded in the addendum.

## Contents
- `baseline/`:
  - `originals/`: the 4 files before the change;
  - frontend file and `dist` hashes;
  - backend fingerprints.
- `before/` and `after/`:
  - `corrections-*.json`;
  - screenshots;
  - `before/tiles/`: the backdrop tiles and layer PNGs used, for the AUD-05 analysis;
  - `before/aud05_repro*/`;
  - `after/aud01-edge.json`;
  - `after/dist_sha256.txt`.
- `scripts/`:
  - `corrections_body.mjs`, `aud05_repro_body.mjs`, `aud05_repro2_body.mjs` and `aud01_edge_body.mjs`. Each is appended to `../luna_ops_2_phase1_2026-11-13/cdp_harness.txt` to make the runnable `.mjs` beside it.
  - `aud01_unit.mjs`;
  - `aud05_tile_alignment.py`.
- `logs/`: as listed above, plus `source_changes.diff`.
- `SHA256SUMS`: every file in this folder (LF line endings).
