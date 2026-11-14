# Presentation source guide

This guide is for building a presentation or demo of LUNA-OPS. Each fact below names the file it comes from, so every figure on a slide can be traced. Paths are relative to the repository root. `P7` stands for `docs/validation_evidence/phase7_final_validation_2026-11-14/`.

## Key messages

1. **Problem.** Near the lunar south pole the Sun and Earth stay low. Whether a site is sunlit, or can see Earth for direct-to-Earth contact, depends on the terrain horizon, metre by metre and minute by minute.
2. **Approach.** LUNA-OPS places the Sun and Earth, from NASA/JPL SPICE, against horizons built from NASA LOLA terrain models. It reports sunlight, Earth visibility, events and a power indicator for any site and dates.
3. **Honesty by design.**
   - Every value carries its origin label.
   - Validation outcomes are reported as measured, including a failure.
   - No score, recommendation, landing probability or safety verdict is produced.
4. **Extensions.** Preliminary landing hazard screening and communication simulation, kept outside the validated engine.

## Suggested slides and their sources

| # | Slide | Content | Source |
|---|---|---|---|
| 1 | Title | LUNA-OPS: Lunar Landing Site Navigator, NASA Space Apps Challenge 2026 | `README.md` |
| 2 | The problem | Low Sun and Earth at the south pole; the horizon decides illumination and contact | `README.md`, `docs/TECHNICAL_REFERENCE_2026-11-12.md` (introduction) |
| 3 | Data | NASA PGDA LOLA DEMs at 5 m (Site01), 20, 80 and 240 m; NAIF SPICE DE440; frame MOON_ME_DE440_ME421 | `data/dem/registry.json`, `data/kernels/lock.json`, `README.md` setup steps 2–3 |
| 4 | How it works | Horizon ray-marching, exact disk visibility, adaptive events to about 1 s | `PROJECT_FEATURES.md` §1 |
| 5 | Mission view | Overview of the site, coverage and analysis | `docs/screenshots_current/01-mission-1920.png` |
| 6 | Site analysis | Events timeline and sunlight/illumination | `docs/screenshots_current/02`, `03` and `04` PNG files |
| 7 | Landing screening | Hazard map with depression candidates; footprint findings | `docs/screenshots_current/05`, `06` and `07` PNG files |
| 8 | Communication | RF link budget with every term and formula; hypothetical relay | `docs/screenshots_current/08` and `09` PNG files |
| 9 | Compare and Guide | Multi-site × multi-window matrix | `docs/screenshots_current/10` and `12` PNG files |
| 10 | Validation results | Table below | `P7/reports/PHASE7_FINAL_REPORT.md` |
| 11 | V-10: an honest failure | The failure story below | `P7/V10_investigation/V10_FINAL_RESOLUTION.md` |
| 12 | Limitations | Obstacles unavailable; resolution limits; preliminary modules; licensing | `README.md` "Known limitations" |
| 13 | Mobile and accessibility | 320–1920 px layouts; U-04 scoped audit | `docs/screenshots_current/13` and `14` PNG files; `P7/accessibility/` |

## Numbers you can quote, with sources

| Figure | Value | Source |
|---|---|---|
| V-09 (Sun average visibility vs NASA PGDA) | **Passed.** 200/200 points; smooth RMSE 1.84 pp, bias −0.66 pp (limits 2 / 1); area-weighted RMSE 2.41 pp (limit 5) | `P7/reports/PHASE7_FINAL_REPORT.md` §2 |
| V-10 (Earth average visibility vs NASA PGDA) | **FAILED.** 200/200 scored; smooth RMSE 3.26 pp (limit 2); area-weighted RMSE 5.41 pp (limit 5) | same, "Failed" |
| V-04 (Sun/Earth direction vs JPL Horizons) | Passed: max 5.2×10⁻⁷° over 7,931 epochs (tolerance 0.01°) | same |
| V-05 (rise/set times vs JPL Horizons) | Passed: 18 crossings, worst 0.5 s (tolerance 1 s) | same |
| V-11 (permanent shadow vs NASA LPSR) | Passed: 200/200 dark | same |
| V-12 (illumination vs LROC WAC) | Passed: 200/200 scored | same |
| V-13 (eclipse timing vs NASA GSFC) | Passed: 20/20 | same |
| V-14 (one month, 1 s brute force) | Passed: 955 edges, 0 missed, worst 0.5 s | same |
| U-04 (accessibility, scoped) | Passed: 0 problems in 12 views; 13/13 keyboard and announcement checks | same |
| Responsive check | 7 tabs × 5 widths: 35/35, 0 console errors (Phase 7) | `P7/responsive_design/` |
| Landing reference (Site01, 3 km window) | Slope median 10.85°; 42 depression candidates (28 defined, 14 weak) | `P7/engine_regression/landing_site01_1500.json` |
| Site01 5 m measured share | About 9.5 % of pixels have a LOLA return; the rest are interpolated | `docs/validation_evidence/landing_hazard_map_repair_2026-11-14/README.md` |
| Footprint (50 m radius) | 316 pixels at 5 m, about 20 at 20 m, 0 at 240 m | same, section 2 |
| Pytest | **Skipped** at 325/572 on the owner's instruction; not a pass | `P7/reports/PHASE7_FINAL_REPORT.md` "Skipped" |

## The V-10 story (one slide)

- **The point.** At 85.3305° S, 285.2104° E, NASA's map says Earth is never visible (0 %), while LUNA-OPS computes 39.8 %.
- **No defect found.** An independent horizon calculation reproduces the engine within about 1 pp at 17 of 17 nearby locations.
- **NASA's own newer terrain disagrees with the reference.** NASA's 2017 40 m terrain gives 24 % at the point, not 0 %. NASA's original source model is no longer distributed.
- **Nothing was adjusted.** The point was not removed and the criteria were not changed after the results were seen. **V-10 stays Failed.**

Source: `P7/V10_investigation/V10_FINAL_RESOLUTION.md`.

## Do not claim

- NASA approval, endorsement or certification.
- Integration with the Deep Space Network or LunaNet, or real spacecraft schedules.
- That a landing site is safe, or any landing probability or ranking.
- Obstacle or boulder detection. It is "Not available - manual review required".
- That V-10 passed, or that the full test suite passed.
- That any quantity is "Validated". None is labelled so in the current build.
- That the power indicator is measured power (it is dimensionless and Estimated).
- Full WCAG 2.2 AA conformance or full licensing clearance.

## Demo script (about 3 minutes, demo data or NASA data)

1. Run `python start.py` (or `--demo`) and open the printed address.
2. **Mission:** show the selected site and coverage.
3. **Site:** run an analysis; show the horizon panorama, the timeline and the sunlight percentages.
4. **Landing:** run a screening.
   - Switch layers (slope, roughness, coverage).
   - Drag the footprint and show the separate findings.
   - Point out the obstacles entry "Not available - manual review required".
5. **Communication:** enter link-budget values and show every term with its formula.
6. **Compare:** add two sites and two windows.
7. Close on the validation slide, including V-10.

With demo data, say that results are synthetic: the interface labels them "not a lunar result".
