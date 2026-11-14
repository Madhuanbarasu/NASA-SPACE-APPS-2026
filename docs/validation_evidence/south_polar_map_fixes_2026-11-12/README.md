# South polar map fixes (2026-11-12)

**Status:** fixed in the frontend; backend unchanged.
- **Main fix:** the missing (L-shaped) map region is drawn again from the server's own hillshade, and the view no longer exposes empty space beyond the map's data square.
- **Feedback:** loading, failed-tile and outside-the-map states are now reported.
- **Coordinates:** they were already exact; verified, not changed.
- **Unchanged:** backend code, algorithm 1.5.0, the fingerprints and the official report (`5135efe8…`).
- **Remaining:** the root cause of the slow tiles is in the backend tile renderer. It is documented below and left untouched.

## 1. Diagnosis (before; `diagnosis_before/`)
The map was driven in headless Chrome against the running application. The diagnosis script is `diagnosis_before/map_diag.mjs`; screenshots are in `diagnosis_before/screenshots/`.

| Observation | Finding | Software bug or data limit? |
| --- | --- | --- |
| **Missing L-shaped region** (`01-fresh-1440.png`): the lower-left quarter of the default view is empty | Tile `1/0/1` was still pending after 26 s and never completed. On zooming in or out, tiles `2/1/2`, `3/3/4` and `4/7/8` behaved the same (`03-zoomout-pan-1440.png`). At each zoom 1–4 it is exactly the tile that contains the 5 m Site01 product. | **Software (backend renderer)**. Valid LOLA data exists there: the 240 m product covers everything to 60° S, and the 20 m and 80 m products cover the inner region. |
| **Cause** | `backend/lunaops/api/tiles.py` `render_tile` skips levels much *coarser* than the tile but never levels much *finer*. A zoomed-out tile that overlaps the 5 m product reads it over the whole tile: a boundless window thousands of times larger than the file, resampled to 256 × 256 with no overviews. It runs for minutes on about 7–11 CPU cores at up to about 1.6 GB (measured on the server process). The U-06 audit found the same for tiles `0/0/0` and `1/0/1`. | backend |
| Side effect | Each hanging request held one of the browser's few connections to the server, and every new map started another such render. | backend + frontend |
| **Empty bands beside the map** | On wide panes the view showed the whole square plus empty space left and right, and panning could move off the data. | frontend viewport |
| No loading or error state | The note switched from "Loading terrain tiles" to the hillshade caption as soon as the tile metadata arrived, even while tiles never finished. Tile errors were ignored silently. | frontend |
| **Clicks north of 60° S** (the square's corners) | Silently ignored: no site and no message. | frontend feedback (the 60–90° S limit itself is real) |
| Coordinates | Clicks match an independent proj4 inverse exactly (6 decimals), including the pole. | **no bug** |
| Fine grid-like texture at high zoom (`02-site01-1440.png`) | Present in the server's own tiles; the radial lines are the graticule converging at the pole. | server rendering of the data; unchanged |
| Console | No errors | – |

**Why the backend was not changed:**
- **Fingerprint:** every file in `backend/lunaops` is covered by the code fingerprint (`lunaops/fingerprint.py`). The official validation report and every cached result are bound to that fingerprint.
- **Consequence:** a one-line fix in `render_tile` (skip levels far finer than the tile, or read from overviews) would invalidate the report until the whole validation is re-run and re-approved. Changing backend code also needs separate approval.
- **Overviews rejected:** adding overview files next to the DEMs was also rejected. The engine's decimated reads could silently start using them, which would be a scientific change.

## 2. Fixes (frontend only, `frontend/src/components/MapView.tsx`)
1. **The missing region is drawn from finer tiles (no fabrication):**
   - **When it happens:** a coarse tile (400 m/pixel or coarser; zooms 1–4 with the registered products) that has not arrived after 10 s.
   - **What happens:** the request is cancelled, freeing the browser connection, and the tile is drawn from its four child tiles one zoom finer, recursively.
   - **Why it is not fabrication:** those children are the server's own hillshade of the same LOLA heights, downscaled 2:1 per level. Nothing is stretched, interpolated or invented. A child the server cannot provide would stay transparent.
   - **Memory:** the slow tile is remembered in `localStorage`, keyed by the backend code fingerprint, tile grid and terrain products. Later visits compose it at once without asking the server again.
   - **Fresh profile:** 3 slow tiles (`2/1/2`, `3/3/4`, `4/7/8`), each cancelled at about 10 s. The view was complete after about 15–25 s.
   - **Reload:** complete at once (all requests ≤ 0.1 s), and the slow tiles were not requested again.
2. **The view stays on the map's data square:** the OpenLayers view is bounded to the tile extent. You cannot pan or zoom out into empty space beyond the square, and the default view fills the pane.
   - **Before:** the whole square was letterboxed in a wide pane.
   - **Now:** the desktop default view spans the full width, roughly ±931 km east–west by about ±390 km north–south around the pole. You pan or zoom to see the rest.
   - **What stays dark:** only the square's corners beyond 60° S, where no registered terrain exists.
3. **States are reported in the map note:**
   - "Loading *n* terrain tiles.";
   - "*n* hillshade tiles are drawn from the next finer zoom because the server is slow to render them at this zoom … same LOLA hillshade, downscaled." (shown only while those tiles are in view);
   - "*n* terrain tiles could not be loaded." (HTTP errors);
   - "… not rendered by the server in time; zoom in … The terrain data there is not missing." (a fine tile past the 20 s limit; not observed);
   - "Terrain tiles unavailable." (metadata error, unchanged).
4. **Clicks north of 60° S** now set no site, as before, and the note says so: "That point is north of 60° S, outside the south polar map; no site was set."

**Unchanged:**
- **Look:** the map's appearance, controls, colours and graticule.
- **Projection and conversions:** the projection and the click → coordinate conversion (`lib/moonGeo` `siteCoords`).
- **Site behaviour:** the site marker and zoom-to-site.
- **U-06 mitigation:** the never-request-zoom-0 rule.
- **Layout fix:** the empty-space fix in `app.css` was not touched.

## 3. Tests (logs in `logs/`)

| Check | Result |
| --- | --- |
| TypeScript; `npm test` (strings 663 keys, 0 problems; static a11y 0 problems; geometry 238,972); production build; bundle | all exit 0 (`00`–`03`) |
| **Map check** (`frontend/scripts/map-live-check.mjs`, new) | **20/20** (`04_map_live_check.log`, `map_check/`) |
| Explorer / globe regression | 27/27 / 31/31 (`05`, `06`) |
| Mission dashboard regression | **42/42** (`07`; attempt 1: 41/42, see below) |
| End-to-end regression | **16/16** (`08`; attempt 1: 14/16, see below) |
| Accessibility audit vs the U-04 release run | 0 problems in all 10 views; map keyboard and zoom-button tests the same as release (`09`, `10`, `a11y_audit/`) |

**What the map check verifies** (canvas pixels sampled in the page, not just screenshots):
- **No empty region inside the 60° S circle:** 0 of 5,464 sampled points are transparent after the first load and after a reload. It also holds at the default view and at each of 4 zoom-in steps (0 of 5,782 each), and after resizing the window to 1,100 × 800, 1,920 × 1,080 and 1,440 × 900, including a live widening of each.
- **Bounded view:** after zooming out fully and panning far left, terrain is still drawn at 12 % and 88 % of the pane width.
- **Clicks:** the four test clicks inside 60–90° S equal the proj4 inverse of the click point within one display pixel, including the pole (−90, 0). Clicks in the corners north of 60° S set no site and show the note.
- **Site selection:** Site01 zoom-6 tiles all return 200. "Inspect local terrain" opens the preview for the map's site. "Analyse" runs it, and the result view's map renders.
- **Interaction:** the zoom buttons and keyboard arrows change the view.
- **Unsupported location:** a typed point at (−30°, 10°) shows the backend's coverage reason, and terrain and analysis are disabled.
- **Errors:** with the cache off and zooms 5–7 blocked, "6 terrain tiles could not be loaded." appears; blocking the tile metadata shows "Terrain tiles unavailable." and the graticule still works.
- **Mobile:** 390 px renders without sideways scrolling.
- **Console:** no errors.

**Regression attempts that needed attention:**
- **Mission, reduced motion (attempt 1):** the check required the deep-linked last section to end within 250 px of the top. That only happened because of the earlier page-scroll bug, removed by the empty-space fix: the whole page scrolled up 557 px. Now only `.main` scrolls and the section ends in view at 777 px of 900, focused and reached in one step. The expectation was corrected to "in view".
- **End-to-end, terrain stats and missing-result message (attempt 1):** fixed short waits. The server was busy with long tile renders started by the previous check's fresh browser profile (measured at about 7–11 cores for over 9 minutes). The checks now wait for the state they test.
- Both attempt-1 logs are kept.

## 4. Remaining limitations
- **Backend tile renderer (not changed):**
  - **First visit:** the first visit from a browser profile still makes the server start one long render for each slow tile at the zooms it views (here up to three). The render continues in the server even after the browser cancels its request; for example, 6.6 cores were still in use well after the test runs.
  - **What the frontend does about it:** it stops waiting, draws the area from finer tiles and never asks again.
  - **Real fix:** `render_tile` should skip levels far finer than the tile. That is a backend change, which changes the code fingerprint and so needs approval and re-validation.
- **Composite shading:** a composed coarse tile is a downscale of finer hillshade, so its shading texture can differ slightly from a natively rendered coarse tile. It is the same cartographic hillshade of the same heights, and it is labelled in the note.
- **Default view:** on wide desktop panes, the default view now shows a full-width band around the pole rather than the whole square letterboxed. Zoom or pan to see the rest.
- **Browser coverage:** tested in Chrome headless only.

## 5. Files
| File | Change |
| --- | --- |
| `frontend/src/components/MapView.tsx` | tile loading with patience, composition from finer tiles, timeouts and memory; bounded view; tile-state and outside-60° S notes |
| `frontend/src/i18n/en.ts` | 5 map strings (`tilesLoading`, `tilesComposed`, `tilesStalled`, `tilesFailed`, `outsideMap`) |
| `frontend/scripts/map-live-check.mjs` | **new**: live map check |
| `frontend/scripts/mission-live-check.mjs` | reduced-motion expectation corrected (see above) |
| `frontend/scripts/e2e-live-check.mjs` | waits for the terrain data and the error message instead of fixed delays |
| `frontend/dist/` | rebuilt (`logs/dist_before_sha256.txt`, `logs/dist_after_sha256.txt`) |

**Not changed:**
- backend code;
- algorithm 1.5.0, code `5bf9753f…`, suite `1632af16…` and terrain acceptance `e48eb8ed…` (`logs/backend_fingerprints_after.txt`);
- `backend/validation/report.json` (`5135efe8…`);
- the empty-space layout fix;
- all earlier evidence (12 folders verified);
- `package.json` and the lock file.

No dependency was installed and no Git command was run.
