# UI simplification and site comparison (2026-11-14)

This change touches the frontend and documentation only. It was approved by the owner after a written plan, including the four decisions below.

**Unchanged:**
- no backend file, engine, API, dataset, validation result or criterion;
- engine fingerprint `9cd7b08b…`;
- test-suite fingerprint `70606628…`.

## What changed

| Increment | Change |
|---|---|
| A. Layout and navigation | <ul><li>Clearer tab names: Mission, Explore & analyse, Landing terrain, Communication, Compare sites, Guide.</li><li>Guide opens with "Getting started in five steps" and a visible link to Data and validation (`#data`).</li><li>Left panel:<ul><li>sourced mission-site search;</li><li>date presets (1 day, 7 days, lunar day of 29.53 d) and a UTC note;</li><li>observer, visibility rules and panel under "Advanced settings", with a one-line summary.</li></ul></li></ul> |
| B. Mission dashboard | <ul><li>A four-step journey: choose a site → inspect the terrain → analyse → compare. The next step is highlighted, and the former shortcuts are inside the steps.</li><li>Status strip and System status card fold into one "System status" line with details.</li></ul> |
| C. Site selection | <ul><li>**Reference catalogue** `frontend/src/data/reference_sites.json`: 30 sourced sites from NASA NSSDCA and LROC (NASA/GSFC/ASU), with positions copied unchanged.</li><li>4 sites inside 60–90° S can be analysed (coverage checked).</li><li>26 are "Reference only — outside LUNA-OPS terrain coverage".</li><li>Mission sites appear on the south polar map (with names) and on the 3D globe (reference-only ones dimmed).</li></ul> |
| D. Compare | <ul><li>Results open on a **Summary**:<ul><li>trade-offs at a glance;</li><li>Sunlight, Earth & communication and Preliminary terrain assessment panels, each stating leaders with both values;</li><li>optional user criteria with Favourable / Needs review / Insufficient data / Not assessed and the exact reasons.</li></ul></li><li>Terrain screening per site uses `POST /api/landing/assess` (the Landing method).</li><li>RF appears only with the user's Communication link budget (`POST /api/comms/simulate`); otherwise "Not assessed".</li><li>Builder quick-adds the selected site or a mission site.</li><li>Matrix (CSV) and Charts are kept one click away.</li></ul> |
| E. Analysis pages | <ul><li>The result's section bar stays in view while scrolling.</li><li>Validation and provenance (Result, Landing, Communication) open on request ("Show details").</li><li>Nothing removed.</li></ul> |

## Decisions applied

1. **Catalogue location:** a separate sourced data file, documented in the README.
2. **Sites outside coverage:** shown for reference only and never analysed. The coverage API refuses them too.
3. **Criteria:** none pre-filled. Factual comparison values are always shown, and there is no overall score.
4. **Commits:** incremental commits, pushed after all increments passed.

The increments were verified together, so they were committed together; see the final report.

## Tests (actual results)

| Check | Result |
|---|---|
| TypeScript (`tsc --noEmit`) | 0 errors |
| `npm test` (check-strings, check-a11y, moon-geo, window) | exit 0. 0 problems: 1,529 keys, 41 components, 52 colour pairs. |
| Production build | exit 0 |
| Functional browser check (`functional/func.json`, `logs/05_func_all.log`) | **33/33 passed**, 0 console errors, 0 failed API requests |
| Screenshot tour after (`after/tour.json`, `logs/07_after_tour.log`) | 7 views × 1920/1440/1024/390/320 px; 0 console errors; 0 horizontal-scroll or overflow problems |
| Backend Communication tests (run alone) | 61/61 passed |
| Backend Landing tests (run alone) | 35/35 passed |
| Engine / suite fingerprints | `9cd7b08b…` / `70606628…`, unchanged |

The functional check covered:
- tab names;
- catalogue search, source link, coordinates and coverage, reference-only refusal;
- the three date presets;
- the advanced-settings fold;
- the Mission journey;
- Guide steps and the Data link;
- map and globe mission legends;
- the result section bar and folded validation;
- a 2-site × 2-window comparison:
  - Summary with leads;
  - Not assessed without criteria, then criteria giving Favourable / Needs review with reasons;
  - terrain screening at both sites (the 240 m Chandrayaan-3 site reported as Insufficient data / too coarse);
  - RF "Not assessed" without a link budget, then evaluated with one;
  - Matrix with CSV and cards;
  - Charts;
- the Landing screening and the Communication tab still working.

**Notes:**
- Running the Communication and Landing backend packages *together* shows 1 failure (`test_gm_read_from_verified_naif_file`). It happens because the Landing tests' `conftest.py` redirects the data folder at import. This is the known test-isolation issue recorded in Phase 7, not a regression: no backend file changed.
- The browser checks used one headless Chrome against a temporary server running this repository's code (port 8001). Data was read only, from the project's data folder.

## Screenshots

- `before/` and `after/`: every view at 1440 px, the comparison scrolled to its results (`compare-1440-mid`), and phone views at 390 px (Mission, Site, Compare).
- `functional/`: catalogue, Mission journey, Guide, Compare summary, Earth & RF, terrain, map and globe mission sites, analysis result.

All files are covered by `SHA256SUMS`.
