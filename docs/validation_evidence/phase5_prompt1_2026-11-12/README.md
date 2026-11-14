# Phase 5, Prompt 1: interactive 3D Moon globe (2026-11-12)

**Status:** implemented and tested.
- **Checks:** 31/31 live browser checks, 2/2 no-WebGL checks and 236,953 geometry checks pass.
- **Regression:** the existing map, analysis, local 3D terrain, comparison and accessibility behaviour are unchanged; the full live U-04 audit was re-run on the new build.
- **Unchanged:** no backend, scientific code, validation result, label or Phase 4 evidence was changed (§6).
- **Not started:** Prompt 2.

## 1. What was built
**A lazily loaded globe** in the Site welcome pane, behind a new **"South polar map | 3D Moon globe"** switch. The map stays the default, so the first screen and its load cost are unchanged.

**Code:**
- `MoonGlobe` (`frontend/src/components/MoonGlobe.tsx`) renders the globe.
- `lib/moonGeo.ts` holds the geometry.

| Feature | Implementation |
| --- | --- |
| Spherical Moon with authentic imagery | Unit sphere (256 × 128 segments); colour map `lroc_color_2k.jpg` (NASA SVS CGI Moon Kit, LROC WAC mosaic); relief **shading** (bump map) from `ldem_3_8bit.jpg` |
| Correct latitude/longitude mapping | +y = north pole; (0°, 0°) on +x; east longitude increasing to the screen right. Proven against three.js's own SphereGeometry UVs and against known lunar features (§4) |
| Pole orientation | North-up default; N/S axis stubs and labels (hidden when looking straight down on that pole, so they never cover the polar surface); North Pole and South Pole viewpoints |
| Space background and lighting | Dark radial sky with a deterministic decorative star field (not a catalogue); an illustrative oblique light carried with the viewpoint; an "Even light" toggle |
| Rotation, zoom and drag | OrbitControls: drag rotates (slower when zoomed in), wheel or pinch zooms within limits, no panning |
| Touch | Pointer events: one finger rotates, pinch zooms, a tap selects |
| Keyboard | Focusable globe region: arrows turn the view 10° (Shift: 2°), + and − zoom, Enter or Space select the location under the centre crosshair, Home returns to the nearside |
| Buttons (no dragging needed) | Turn west/east/north/south, zoom in/out, select centre; viewpoints Nearside, Farside, North Pole, South Pole; Grid (30° graticule, equator and prime meridian highlighted) |
| Location selection | Click or tap without dragging (≤ 6 px, ≤ 0.7 s) → **exact ray–sphere intersection** (not mesh-dependent) → latitude and east longitude; a marker ring and pin that are hidden behind the globe when on the far side |
| Coordinate display | Selected location (3 decimals, N/S and °E), the signed form used by site coordinates (east-positive 0–360°), a live centre and pointer readout, and a polite screen-reader announcement |
| Callback for Prompt 2 | `MoonGlobe({ selected?, onSelect? })`. `onSelect(location: { lat, lon })` gives degrees +north and degrees east in [0, 360), the site-coordinate convention. SiteView currently keeps the pick locally (`globePick`); wiring it into site selection is Prompt 2. |
| Loading, error and fallback states | Chunk loading text; a `LazyBoundary` message if the chunk fails; an imagery-loading message; imagery failure → untextured rotatable sphere plus a note; no WebGL → a message and no canvas; WebGL context loss → a message |
| Responsive | Stage height clamp(340 px, 62 vh, 640 px). Below 600 px the toolbar becomes a bar above the stage instead of covering the globe |
| Lazy loading | The globe chunk (12.1 KB) and the shared three.js chunk load only when the globe is opened; the textures load with it |
| Cleanup | Disposes geometries, materials, textures, controls and renderer; `forceContextLoss()`; listeners and ResizeObserver removed |
| Local 3D terrain view | `Terrain3D` is unchanged; it now shares the three.js chunk with the globe |

## 2. Data sources, licence and integrity
- **Local check:** no global lunar imagery existed in the installation. The only registered lunar data are the south-polar LOLA DEMs (to 60°S), which cannot honestly cover a globe.
- **Source used:** NASA's **Scientific Visualization Studio "CGI Moon Kit"** (SVS ID 4720), verified before use and retrieved 2026-11-11 19:25 UTC:

| File | Size | SHA-256 | Content (from the SVS page) |
| --- | --- | --- | --- |
| `frontend/public/moon/lroc_color_2k.jpg` | 2048 × 1024 RGB, 457,942 B | `f7130a18…a2170` | 2025 colour map from the LROC WAC Hapke-normalised mosaic (643/566/415 nm), which covers 70°N–70°S. Higher latitudes are filled with the lower-resolution LOLA albedo map (LDAM). "optimized for aesthetics, not science" |
| `frontend/public/moon/ldem_3_8bit.jpg` | 1024 × 512 greyscale, 111,552 B | `6d93f887…8bb98` | 8-bit LOLA displacement image. Its scaling is not documented on the page, so **no elevation value is derived from it**: it is used only as bump shading |

**Licence and attribution** (primary sources saved verbatim in `provenance/`):
- **SVS help** (`provenance/svs_help.html`): "All of our content is in the public domain (unless otherwise noted), meaning that it is free to download, use, and redistribute for whatever purposes you see fit."
- **NASA Images and Media Usage Guidelines** (`provenance/nasa_media_usage_guidelines.html`): texture maps "generally are not subject to copyright in the United States"; NASA should be acknowledged as the source; no implied endorsement. The NASA insignia and logotype are not public domain and are not used.
- **Item page** (`provenance/svs_4720_cgi_moon_kit.html`): "Please give credit for this item to: NASA's Scientific Visualization Studio".
- **Recorded in:** `ATTRIBUTION.md` (new row); `frontend/public/moon/ATTRIBUTION.txt` (shipped with the build, with hashes and terms); and the globe's on-screen credit line.

**Integrity:**
- **Imagery vs elevation:** the interface states that the globe shows imagery, not elevation data, that the lighting is illustrative and not the computed Sun direction, and that analyses use the registered south-polar LOLA terrain.
- **Resolution:** the imagery resolution is stated (2048 × 1024, about 5.3 km per pixel at the equator, lower-resolution albedo towards the poles). Coordinates are exact for the picked point, but the image resolves only kilometres, so typed coordinates are recommended for precise sites.
- **Nothing fabricated:** no elevation, illumination or other scientific value is computed or shown by the globe.

## 3. Results

| Check | Result | Evidence |
| --- | --- | --- |
| TypeScript (`npm run typecheck`) | exit 0 | `logs/00_typecheck.log` |
| `npm test`: string checker (self-test 38/38; 483 keys, 0 problems), static a11y (self-test 15/15; 16 components, 0 problems), **globe geometry** (new; 236,953 checks) | exit 0 | `logs/01_npm_test.log` |
| Production build (`npm run build`) | exit 0, 388 modules | `logs/02_npm_run_build.log` |
| Bundle split (`check-bundle`) | three.js not in the initial chunk; initial JS 299.0 KB raw / 95.0 KB gzip (+3.7 KB / +1.5 KB, strings and switch only) | `logs/03_check_bundle.log` |
| **Live globe check** (`scripts/globe-live-check.mjs`, Chrome 157 headless) | **31/31** | `logs/04_globe_live_check.log`, `globe_check/globe-check.json`, `globe_check/screenshots/` |
| Live globe check, **WebGL disabled** (`--no-webgl`) | **2/2** | `logs/05_globe_live_check_no_webgl.log`, `globe_check/globe-check-no-webgl.json` |
| **Existing features**: full live U-04 audit on the new build (`npm run audit:a11y`), compared with the U-04 release run | **unchanged** | `logs/06_audit_a11y.log`, `a11y_regression/`, `logs/07_a11y_regression_compare.log` |
| Texture orientation against known features (source images) | OK | `texture_orientation_check.py`, `.log` |

**The 31 live checks** (each with its measured detail in `globe-check.json`):
- **Lazy loading:**
  - nothing three.js-related or any imagery is requested before the globe is opened;
  - on opening, the globe chunk, the shared three.js chunk and both images are requested.
- **Rendering:** the disc is drawn and the stage fits the viewport.
- **Coordinates:**
  - the centre readout is (0, 0) at start; "select centre" equals it; a click at the canvas centre selects (0, 0);
  - a click 120 px right of centre gives **19.464°E**, against **19.4643°** from exact ray–sphere geometry;
  - a click 120 px above gives 19.464°N (east is right, north is up).
- **Rendered orientation (even light):** Mare Moscoviense (28°N 148°E) is darker than its east–west mirror (28°N 212°E), and Mare Imbrium (32°N 344°E) is darker than its north–south mirror (32°S 344°E).
- **Keyboard:** Home; arrows turn exactly 10°; + zooms; Enter selects the centre.
- **Mouse:**
  - the wheel zooms;
  - a drag rotates (centre 0° → 44.6°E);
  - a drag does not select.
- **Viewpoints:** South Pole 89.900°S; North Pole 89.900°N; Farside 180°E.
- **Grid toggle:** changes `aria-pressed` and the image.
- **Accessibility:**
  - all 13 globe buttons are named and at least 24 px;
  - the globe region is focusable and named;
  - the selection is announced politely.
- **Responsive (390 × 844):**
  - no sideways scroll;
  - the toolbar sits above the globe, not over it;
  - the canvas fills the stage.
- **Cleanup:** 5 map↔globe cycles leave 0 canvases and no WebGL context warnings; heap 24.9 → 26.6 MB (+1.65 MB over 6 forced-GC samples, below the 2 MB check limit).
- **Errors:** no page exceptions or console errors.
- **Fallbacks:**
  - blocked imagery gives a note and an untextured sphere;
  - a blocked globe chunk gives the load-failed message, with the page intact;
  - the map still works afterwards;
  - with WebGL disabled, the no-WebGL message appears, no canvas is created, and the map works.

**Existing features** (`logs/07_a11y_regression_compare.log`). The audit performs a real Site01 analysis, the local 3D terrain view, the map, a 2 × 2 comparison and the Data and Guide pages:
- **All six views:** 0 problems in every automated column.
- **Tab stops:** identical, except the welcome view (34 → 36, the two new switch buttons, as expected).
- **Functional tests:** 15 of 16 are byte-identical.
- **Panorama keyboard test:** equivalent rather than identical. Its starting azimuth comes from the audit's earlier mouse-hover position (263° vs 264°). The step sizes are the same (+1, +10), and the horizon values are identical wherever both runs read the same azimuth (264° → −1.55°).

## 4. Coordinate mapping proof
- **`scripts/check-moon-geo.mjs`** (runs in `npm test`):
  - **round trip:** latitude/longitude → vector → latitude/longitude, worst 3e-13°;
  - **three.js agreement:** every one of the 64,619 vertices of a three.js `SphereGeometry(1, 360, 180)` has the texture coordinate `textureUV(unitToLatLon(vertex))`, to float32 precision (3.8e-8);
  - **picking:** exact ray–sphere picking hits the aimed-at location to 2e-11°, including Site01 (89.463163°S, 222.510447°E).
- **Source image** (`texture_orientation_check.log`): five dark features (Moscoviense, the Tsiolkovskiy floor, Crisium, Imbrium, Orientale) are darker than their mirror points, and the South Pole–Aitken basin is lower than the farside highlands in the relief image. The map is neither mirrored nor flipped.
- **Rendered output:** the live orientation and pixel-geometry checks in §3.

## 5. Limitations
1. **Imagery resolution:** about 5.3 km per pixel at the equator, coarser towards the poles (LDAM fill beyond 70°). The polar regions look softer, and the globe is not a substitute for the south-polar map or the registered LOLA DEMs.
2. **Relief:** visual bump shading from a 1024 × 512 image. There is no geometric displacement and no elevation data; the globe is a smooth sphere of radius 1737.4 km in scale.
3. **Lighting:** illustrative, not the Sun direction of any date; no shadows are cast.
4. **Coordinates:** planetocentric latitude and east longitude on a sphere (the same convention as LUNA-OPS site inputs). Picking precision is limited by the screen pixel, which is about 0.1–0.4° depending on zoom.
5. **Polar viewpoints:** they stop at ±89.9° (OrbitControls singularity); the pole itself is reached by picking or by the readout.
6. **Selections are not yet sites:** a globe selection is kept in the welcome view only and does not set the site coordinates; that is Prompt 2's integration.
7. **Browser coverage:** tested in Chrome 157 headless (SwiftShader WebGL) only, with no real touch device or other browsers; touch is via pointer events, as implemented by OrbitControls.
8. **Official report bound to the earlier build:** U-04 and U-06 in the official report (`2279606c…`) were registered for the **previous** `frontend/dist`, whose hashes are in `frontend_u04.json`/`frontend_u06.json` and in `logs/dist_before_sha256.txt`.
   - **What changed:** the build now differs (new globe, +1.5 KB gzip initial JS).
   - **Accessibility:** the re-run audit shows the existing views unchanged. The globe itself is covered by `globe-live-check`, not by the U-04 audit script.
   - **Performance:** U-06 was not re-measured.
   - **Recommendation:** re-register U-04 and U-06 for the new build before the next official report. The merge guard checks only backend fingerprints, so the report does not detect this itself.
9. **IB-5 (D5):** the new assets are public domain with shipped attribution. The general missing third-party notices and OFL text in `dist` (D5 restriction R3) remain unresolved.

## 6. Files changed
| File | Change |
| --- | --- |
| `frontend/src/components/MoonGlobe.tsx` | **new**: the globe component |
| `frontend/src/lib/moonGeo.ts` | **new**: globe frame, latitude/longitude ↔ vector, texture UV, exact ray–sphere picking, angular distance |
| `frontend/src/components/LazyBoundary.tsx` | **new**: error boundary for lazily loaded panes |
| `frontend/src/components/SiteView.tsx` | the map/globe switch in the welcome pane; lazy `MoonGlobe`; `globePick` state |
| `frontend/src/i18n/en.ts` | new `globe` section (dictionary 433 → 483 keys) |
| `frontend/src/styles/app.css` | globe styles (stage, toolbar, readouts, responsive rules) |
| `frontend/scripts/check-moon-geo.mjs` | **new**: geometry check (in `npm test`) |
| `frontend/scripts/globe-live-check.mjs` | **new**: live browser check (`--no-webgl` mode) |
| `frontend/package.json` | scripts only: `test` runs `check-moon-geo`; new `check:globe` (no dependency change) |
| `frontend/public/moon/lroc_color_2k.jpg`, `ldem_3_8bit.jpg`, `ATTRIBUTION.txt` | **new**: imagery and its shipped attribution |
| `ATTRIBUTION.md` | new row for the CGI Moon Kit |
| `frontend/dist/` | rebuilt. Previous hashes: `logs/dist_before_sha256.txt` (a full copy was kept in the session scratchpad); new: `logs/dist_after_sha256.txt` |

**Not changed:**
- backend code and algorithm 1.5.0;
- code `5bf9753f…`, suite `1632af16…` and terrain acceptance `e48eb8ed…` (`logs/backend_fingerprints_after.txt`);
- `backend/validation/report.json` (`2279606c…`);
- `Terrain3D.tsx`, `MapView.tsx`;
- all Phase 4 evidence folders (checksums verified);
- `package-lock.json` and `node_modules`.

No dependency was installed and no Git operation was run.
