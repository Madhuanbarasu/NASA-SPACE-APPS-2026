# LUNA-OPS: project features

This document describes what LUNA-OPS does, view by view, and how its results are labelled. Status is as of 2026-11-14 (after the Phase 7 final validation and the Landing hazard map repair).

**Labels.** Every number is labelled by origin:
- **Calculated:** computed by the engine.
- **Estimated:** modelled, for example the power indicator.
- **Preliminary:** the landing and communication modules.
- **Unavailable:** no data.

No quantity currently carries a "Validated" label (see README, Validation status). LUNA-OPS has no NASA approval or certification, and no DSN or LunaNet integration.

## 1. Scientific engine (`backend/lunaops`)

| Capability | Details |
|---|---|
| Sun and Earth geometry | NASA/JPL SPICE (SpiceyPy, CSPICE N0067), DE440, light time and stellar aberration (`CN+S`), body-fixed frame `MOON_ME_DE440_ME421`. Earth is the IERS 2010 oblate spheroid with the pole of date (IAU 2006/2000B). |
| Terrain | Multi-resolution pyramid of registered NASA PGDA LOLA DEMs (5 m Site01, 20 m, 80 m, 240 m); finer products are sampled first. SHA-256 is checked at registration. Nothing is substituted when terrain is missing. |
| Horizon | Numba ray-marching, 0.1° azimuth bins with sub-bin rays, exact stopping bound. Per-bin uncertainty from the products' error maps. Near-field and sub-bin peak flags. |
| Disk visibility | Exact visible fraction of the Sun and Earth disks against the piecewise-linear horizon: spherical-cap solution, exact Earth limb ellipse, Earth in front of the Sun. |
| Events | Adaptive detection of rise and set of any part, centre or whole disk of Sun and Earth, including eclipse boundaries, to about 1 s. |
| Power indicator | Dimensionless relative indicator (uniform disk and limb-darkened, Neckel & Labs 1994), labelled Estimated. |
| Observer | Surface (0 m), astronaut or equipment height. |
| Provenance | Each result records kernels, terrain products, algorithm versions, code fingerprint, warnings and label reasons. |
| Exports | CSV and JSON for results and comparisons. |

## 2. Interface (`frontend`, React + TypeScript)

**Throughout the interface:**
- **Technical and public modes:** the same data, with explanations at different levels.
- **Layout:** responsive from 1920 px to 320 px; checked at 1920, 1440, 1024, 390 and 320 px.
- **Accessibility:** keyboard navigation and screen-reader announcements, with automated checks (`npm test`: check-strings, check-a11y). Scoped WCAG 2.2 A/AA audit U-04 passed in Chrome headless; no screen-reader session.
- **Text:** all interface text is in one dictionary (`frontend/src/i18n/en.ts`).

### Mission
- A four-step planning journey: choose a site → inspect its terrain → analyse sunlight and Earth → compare sites. The next step is highlighted, and each step has its main action.
- System status (kernels, terrain, validation report) folds into one line with details on request.
- Selected site, terrain coverage at that point (5/20/80/240 m), system status (kernels, terrain, validation report).
- Current analysis summary: sunlit time, longest darkness, Earth in view, longest Earth gap, sunlit with Earth in view.
- South polar locator, candidate sites, analyses of the session, comparison shortcut.
- Validation badges were removed from this view on 2026-11-14 at the owner's request. The validation record remains on the Data page.

### Explore & analyse (Site)
- Site choice:
  - search 30 sourced mission sites (Apollo, Surveyor, Luna, Chang'e, SLIM, Blue Ghost, Chandrayaan-3, IM-1, IM-2 and impact sites; NASA NSSDCA and LROC positions);
  - click the south polar map or the 3D globe, or type coordinates.
  - Only sites inside 60–90° S can be analysed; the others are marked "Reference only — outside LUNA-OPS terrain coverage".
- Mission sites appear on the map (inside 60–90° S, with names) and on the globe (all; reference-only ones dimmed). Comparison sites are cyan rings and the selected site is gold.
- Dates: presets (1 day, 7 days, one lunar day of 29.5 d) and custom start and end, all in UTC. Observer, visibility rules and panel settings sit under "Advanced settings".
- The analysis result has a section bar that stays in view (Summary, Horizon, Timeline, Sunlight, Earth, Terrain, Validation). Validation details open on request.
- Horizon panorama (D3) with the Sun and Earth paths.
- Sunlight and illumination, Earth visibility, events and intervals timeline (with an expandable interval list).
- Power indicator.
- 3D Moon globe, south polar map (OpenLayers, hillshade tiles), local 3D terrain (Three.js).
- Visibility rules (any part, centre or whole disk) and observer profiles in the sidebar.

### Landing (preliminary screening, `backend/lunaops_landing`)
- **Analysis setup:**
  - Window from 1 to 12 km square; terrain product "Finest product covering the window", or a chosen product.
  - Roughness window 3 to 25 pixels.
  - Depression depth and diameter limits.
- **Hazard map:**
  - Layers: elevation, slope, roughness, data coverage (measured vs interpolated where a count map exists), height uncertainty, slope above a user threshold.
  - Overlays: depression candidates, landing footprint, analysis window.
  - Pointer readout and draggable footprint.
- **Landing footprint:** radius (default 50 m) and user-set thresholds (no default thresholds). Separate findings for:
  - slope (Horn 1981);
  - roughness (RMS about a fitted plane);
  - elevation range;
  - depression candidates (priority-flood, unconfirmed);
  - obstacles.
- **Obstacles: "Not available - manual review required".** No imagery or boulder product is registered, and terrain models cannot resolve boulders.
- **Terrain statistics:** slope histogram, multi-scale roughness, provenance (products, SHA-256, algorithms, limitations), JSON export.
- **Repairs on 2026-11-14:**
  - A layer that cannot be loaded is no longer shown blank or under another layer's legend. If the server has dropped the screening, it is re-run with identical inputs.
  - Layers without values show "No data … (coverage unavailable)" over the base map.
  - A product selection is reset when it does not cover the new site.
  - Coarse products get a hint naming finer covering products.
  - The non-working "NASA slope product" raster option was removed. The NASA slope statistics remain in the tables.
  - Evidence: `docs/validation_evidence/landing_hazard_map_repair_2026-11-14/`, `docs/validation_evidence/landing_nasa_slope_option_removal_2026-11-14/`.

### Communication (preliminary simulation, `backend/lunaops_comms`)
- Direct-to-Earth windows read from a completed engine analysis; nothing is recomputed, and the engine's labels are passed through.
- RF link budgets (direct to Earth, lander to relay, relay to Earth), with every term and formula shown. All hardware values are entered by the user; there are no defaults.
- A hypothetical relay orbit (never an actual NASA spacecraft), window algebra and a store-and-forward planner.
- Geometric visibility is not called a radio link: a link is "RF-feasible" only when the user's budget meets the user's required Eb/N0.

### Compare sites
- **Builder:**
  - several sites × several date windows;
  - quick-add the selected site or a sourced mission site inside 60–90° S;
  - add the panel's dates or one synodic month later.
- **Summary (opens first):** answers "which site is better for what".
  - **Trade-offs at a glance:** the leader per objective, or "no clear leader".
  - **Sunlight:** % sunlit, sunlit time, longest darkness, windows, power indicator (Estimated), highest Sun elevation, first sunrise and sunset.
  - **Earth and communication:** % Earth in view, longest gap, windows, sunlit with Earth in view, Earth elevation and azimuth, clearance above the horizon. RF-feasible time appears only after "Evaluate RF with my Communication link budget"; otherwise "Not assessed".
  - **Preliminary terrain assessment:** "Screen the terrain at all sites" runs the Landing method per site and reports slope, roughness, relief, depression candidates, product, footprint size and data coverage. A product that is too coarse is reported as Insufficient data.
- **Assessments:**
  - optional user criteria, none pre-filled;
  - each site gets Favourable / Needs review / Insufficient data / Not assessed, with the exact values and reasons;
  - leads are stated with both values, and ties or uncertain time are flagged;
  - no overall score.
- **Matrix and Charts:** as before; links to each cell's result and CSV export.

### Guide
- How to read the results, labels and limitations.

### Data and validation (`/#data`)
- Data products, provenance and the validation record.
- Reachable by URL; removed from the navigation bar on 2026-11-14.

## 3. Validation framework (`backend/validation`)

- **Gating:** the code fingerprint (engine) and the suite fingerprint (tests and validation) gate every label. A report produced by other code is never trusted.
- **Merge guard:** external results (JPL Horizons, NASA GSFC eclipses, NASA PGDA AVGVISIB and LPSR, LROC WAC) are merged only when their fingerprints, kernels and owner match.
- **Criteria:** frozen before holdout runs, and never changed after viewing results.
- **Current outcomes:** see README.md. V-10 **Failed**; V-09, V-04, V-05, V-11, V-12, V-13, V-14 and U-04 passed; the pytest suite was skipped in Phase 7.

## 4. Tools and checks

- `start.py`: a one-command launcher with demo mode (labelled synthetic data).
- `frontend/scripts/`: string, accessibility, globe and time-window checks (`npm test`), plus live browser audit scripts.
- `scripts/`: kernel download (PowerShell), smoke test, profiling and diagnostics.
- CI (`.github/workflows/ci.yml`): backend tests on sandbox kernels, frontend build, demo smoke test.

## 5. Not provided

- No landing safety certification, score, ranking, probability or recommendation.
- No obstacle or boulder detection.
- No real spacecraft, DSN or LunaNet scheduling.
- No measured solar power.
- No redistributed NASA data: terrain, kernels and reference rasters must be downloaded.
