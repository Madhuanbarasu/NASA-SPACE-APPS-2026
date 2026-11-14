# LUNA-OPS 2.0 pre-Phase 7 health audit (2026-11-14), read only

**Scope.** No application source, CSS, configuration, data or existing evidence was changed. The audit scripts live in `E:\Temp\LUNA-OPS\audit\`.

**Evidence:**
- `browser/`: the first browser run. Three of its failures came from wrong selectors in my script, so its results are kept only as a record.
- `browser_run2/`: the corrected run (selectors taken from the live DOM). It holds `audit-results.json` and 40 screenshots, and is the basis of this report.

**Tested:** the live app in one headless Chrome (CDP) against the existing server, and the live API with direct requests.
**Code-reviewed only:** where stated below.
**Not tested:** see section 11.

## 1. Startup and connectivity (tested)
- **Server:** one instance on 127.0.0.1:8000 (PID 10244; PID 12140 is its venv launcher). No duplicate server was started. RAM was 5.3 GB free; E: had 133 GB free.
- **Endpoints:** `/`, `/api/status`, `/api/catalog`, `/api/coverage`, `/api/tiles/meta`, a tile PNG, `/api/terrain`, `/api/validation`, `/api/landing/meta`, `/api/comms/meta`, `/api/results/<id>` and `/docs` all return 200 in 3–155 ms. Unknown results, jobs and assets return 404. Unknown page routes return the app's index page (single-page app).
- **Engine status:** algorithm 1.5.0. Code fingerprint `84cbd4ea…` equals the validation report's fingerprint. The report has 424 tests (420 passed, 2 not run, 2 skipped) and no blockers.
- **Labels in `/api/status`:** Sun/Earth azimuth and elevation and terrain horizon Validated; disk visibility, events and power indicator Pending validation.
- **Network during the browser run:** one request failed, a 422 from `/api/coverage?lat=-95` (AUD-01). There were no other 4xx/5xx responses and no failed loads.

## 2. Navigation and page loading (tested, 1440 px)
- **Tabs:** all seven (Mission, Site, Landing, Communication, Compare, Data and validation, Guide) load with content. In each, the active tab id is correct and no fallback or blank panel appears.
- **Mode switch:** Technical/Public switching works. The Public result view shows the public summary.
- **Mission Parameters panel:** docks and collapses (≥ 1200 px). Below 1200 px it opens as a drawer, and Escape closes it.
- **Compact navigation (1280 px):** the menu opens, choosing Guide closes it and activates the tab, and the toggle shows "Guide".

## 3. UI and alignment (tested at 1920, 1440, 1024, 390 and 320 px on all seven tabs; 35 combinations)
- **Horizontal scroll:** none in any combination. No element extends past the right edge.
- **Labels and cards:** no clipped button, tab or heading labels, and no overlapping cards.
- **Site result (all widths):** "blank space" was flagged below the summary figure cards. This is a **measurement artefact**: the timeline, charts and tables follow those cards and are not counted as cards by the detector. The screenshots show no empty space.
- **Landing at 1920 px:** 76 px below "Landing footprint" (AUD-04). The other Landing and Communication combinations have the normal 16 px gaps, confirming the recent fixes.
- **Hazard map at 1920 px:** a lighter rectangle inside the raster (AUD-05).

## 4. Functional interactions (tested; 37 steps, 36 passed)
- **Site:** coverage lookup; South Polar Map (zoom in, reset, pointer readout, clicking the map picks a new site).
- **Globe** (genuinely clicked; button text "3D Moon globe"):
  - switching to globe mode is verified (pressed state, panel heading, map removed);
  - the Farside and South Pole viewpoints move the view centre (0°N 180°E, then 89.9°S 0°E);
  - the Grid toggle changes state, and zooming changes the image;
  - there is one WebGL context.
- **Local terrain:** rotate, zoom, exaggeration (2, 4, 8, 16) and reset all change the view; one WebGL context.
- **Analysis (cached Site01 window):**
  - figures match the API exactly (Sun 100.0%, Earth 22.4%, overlap 22.4%);
  - next and previous event, event-list click, play and pause, the table toggles, and clicking a chart all move the time cursor;
  - Back to explorer and Return to the result both work.
- **Mission:** adding a candidate; candidate actions (Select is correctly disabled for the selected site, plus Analyse, Open result, Landing safety, Communication, Remove); the quick actions; the locator; the session history.
- **Landing:**
  - a run gives 5 findings;
  - a 10° slope threshold changes the slope finding to "Potential hazard detected";
  - all 6 raster layers render distinct images;
  - changing the footprint radius updates it (20 → 60 px across);
  - selecting a depression candidate sets its pressed state.
- **Communication:**
  - simulation runs, with the engine labels shown verbatim;
  - "Lander to relay" switches even with no relay, and shows the relay-needed note;
  - a direct link budget completes (margin 13.98–14.71 dB);
  - a hypothetical relay gives the three-leg table.
- **Compare** (genuinely run, 2 sites × 1 window, 6 s):
  - the matrix fills in, and switching the metric changes the caption ("Sunlit time" → "Longest darkness");
  - both site cards render.
- **Data:** 5 tables (7, 4, 424, 5 and 6 rows).
- **Guide:** renders with 6 sections.
- **Session:** after a reload the analysis history is restored from sessionStorage, keyed to the code fingerprint. By design, comparison sites and the landing and communication results are not restored.
- **Failed:** SITE-02 (AUD-01).

## 5. Backend and API (tested)
- **Engine reference:** result `c9b10862…` (84.31° S 359.05° E, 30 d) gives Earth in view 545.02 h (75.70%) and overlap 356.15 h. This equals the Phase 6 reference.
- **Landing reference:** Site01, 1.5 km window: slope median 10.85°, 42 depression candidates (28 defined, 14 weak), 9.18% measured pixels. This equals the Phase 5 example. Its status is "Preliminary screening".
- **Comms reference:** direct 545.02 h in 2 windows; illustrative margin 13.96–15.03 dB; free-space path loss at 384,400 km and 2.2 GHz is 210.99 dB. A data rate of 0 is reported as invalid and the margin is not evaluated.
- **Coverage outside the terrain:** 40° S returns `covered: false` with the scope reason.

## 6. Scientific calculations (tested against reference cases; no thresholds or labels changed)
- **Reference cases:** all reproduce exactly (section 5).
- **Zero visibility:** zero Earth-in-view results are physical; see `../earth_zero_investigation_2026-11-14/`.
- **Labels:** passed through verbatim. A result can carry "Pending validation" for the horizon while `/api/status` says Validated, because of the per-result L_corr assumption reason. No label was upgraded.

## 7. Browser console and network (tested)
- **Console and network:** the only console error was the browser's "Failed to load resource" for the 422 from AUD-01, which was also the only failed request. There were no JavaScript exceptions and no other errors or warnings in the run.

## 8. Responsive design (tested)
- **Layout:** see section 3. Compact navigation below 1600 px and the drawer below 1200 px both work, and there is no horizontal scroll at 320 px.
- **Phones (390 and 320 px):** single-column layouts with no clipping (`browser_run2/screenshots/layout-390-*`, `layout-320-*`).

## 9. Data integrity and regression (tested)
- **Engine and packages:** the code fingerprint, suite fingerprint, terrain digest and `report.json` hash are unchanged. All `backend/lunaops` files are byte-identical to the Phase 6 baseline, and `lunaops_landing` and `lunaops_comms` are unchanged since Phase 6.
- **Data manifests:** `registry.json`, the landing manifest and the kernel `lock.json` are unchanged.
- **Evidence:** 22 of 23 evidence folders verify against their `SHA256SUMS`. The 23rd verifies once its Windows line endings are stripped; all 275 of its files are intact (AUD-03).
- **Result cache:** 74 indexed results, all readable with matching ids. All 27 horizon files are present.
- **Package tests:** landing 35/35 and comms 57/57 pass when run separately. A combined run fails (AUD-02).
- **Frontend checks:** `tsc` 0 errors. `npm test`: strings 1369 keys, 0 problems; accessibility 40 components and 52 colour pairs, 0 problems; check-moon-geo 238,972 checks.

## 10. Issues

| ID | Severity | Location | Reproduce | Expected | Actual | Evidence | Recommended correction |
|---|---|---|---|---|---|---|---|
| AUD-01 | Low | `frontend/src/components/Sidebar.tsx:39` (`latBad`/`lonBad`); `state/store.tsx` coverage effect | Enter latitude −95 | Field marked invalid locally, no request | Not marked invalid (only finiteness is checked); `/api/coverage` returns 422; console "Failed to load resource". The server's message is shown and Analyse stays disabled. | `browser_run2/audit-results.json` SITE-02 | Use the range check already in `lib/moonGeo.ts` `parseSite` (±90°, ±360°) for `latBad`/`lonBad`, and skip the coverage request for out-of-range values |
| AUD-02 | Low (test tooling) | `backend/lunaops_landing/tests/conftest.py` (sets `LUNAOPS_DATA_DIR` at import) | `pytest lunaops_landing/tests lunaops_comms/tests` in one run | Both suites pass | 1 failure (GM manifest missing), 11 skipped (no kernels); separately 35/35 and 57/57 | `E:\Temp\LUNA-OPS\audit\pytest_packages.log` | Run the suites separately in Phase 7, or isolate the environment per package |
| AUD-03 | Low (evidence format) | `docs/validation_evidence/post_phase5_backend_and_ui_fixes_2026-11-12/SHA256SUMS` | `sha256sum -c SHA256SUMS` | OK | "FAILED open or read" for every file (CRLF line endings) | 275/275 OK with CR stripped | Leave as is and document, or regenerate with LF, only with the owner's approval |
| AUD-04 | Low | Landing tab, two-column band at about 1920 px | Run a screening at 1920 px | Cards end flush | 76 px below Landing footprint (right column taller) | `layout-1920-landing` metrics | Accept, or rebalance the stacks for very wide screens |
| AUD-05 | Low (unconfirmed cause) | Landing hazard map | Run a screening at 1920 px | Uniform raster | Lighter rectangle inside the raster, probably the partly loaded hillshade backdrop seen through the semi-transparent layer | `browser_run2/screenshots/layout-1920-landing.png` | Investigate the backdrop tile loading under the overlay |
| AUD-06 | Low (unconfirmed) | South Polar Map, zoomed in near Site01 | Zoom to about 10 km scale at Site01 | Smooth hillshade | Faint square grid lines across the map (not visible fully zoomed out) | `browser/screenshots/fail-SITE-05-globe-controls.png` | Check tile seams and the hatch pattern showing through composed tiles |
| AUD-07 | Info (data) | `/api/catalog` | Open the site list | Curated sites | Empty: no USGS or PGDA region files are registered | API response | Register the catalogue data if wanted (README step 4) |

**Before Phase 7:** none of these is Critical, High or Medium. AUD-01 is the only user-facing behaviour defect.

## 11. Not performed or not verified
- **Deferred to Phase 7:**
  - the 440-test engine suite;
  - the live-check scripts;
  - U-04/U-06 audits;
  - rendered colour contrast;
  - keyboard and screen-reader operation;
  - long-window performance.
- **Not exercised:**
  - dragging the South Polar Map, globe or terrain views (only buttons and clicks were tested);
  - map interactions at phone widths;
  - CSV and JSON downloads (links present, files not opened);
  - every candidate action across several candidates (one candidate was tested);
  - a comparison with more than 2 sites or 1 window.
- **Causes not confirmed:** AUD-05 and AUD-06 are observations from screenshots only.
- **Not done:** fresh, uncached long analyses (cached windows were used for speed and memory).
- **In-app session state** for comparison, landing and comms after a reload was confirmed only as not restored, which is the documented behaviour.
