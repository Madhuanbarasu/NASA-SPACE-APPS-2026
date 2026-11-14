# Investigation: "Earth in view 0.0%" and "Operational overlap 0.0%" (2026-11-14)

**No code was changed.** The frontend files and engine fingerprints are identical to before (`logs/backend_fingerprints.txt`).

**Where the figures are shown.** The Site tab's analysis figure cards (`frontend/src/components/ResultWorkspace.tsx`, function rendering `.figures`) show `summary["earth_<dte rule>"]` and `summary.overlap` from the engine result, unchanged.
- The engine computes them in `backend/lunaops/engine/analysis.py`. `analyze()` calls `get_horizon()` and `events.build_intervals()`, then `intersect()` for the overlap and `summarize()` for the figures.
- The Communication tab reads the same engine intervals.

## Finding: the zeros are geometric results, not a software defect
At every 0% site examined, the terrain horizon in the Earth's direction is higher than the Earth's highest elevation over the window. These sites lie in craters or basins (ground 3.2–3.7 km below the reference sphere) or on the far side or limb.

| Site (30 d, 13 Nov–13 Dec 2026, step 30 min, centre rule) | Earth elevation range | Earth azimuth | Horizon toward Earth (engine) | Earth clearance range | Samples with clearance > 0 | Earth in view |
|---|---|---|---|---|---|---|
| **84.31° S 359.05° E** (Phase 6 reference) | −1.18 to 11.94° | 0–360° (around north) | −0.20 to 0.81° | −1.80 to 11.35° | 1092 / 1442 | **545.02 h (75.7%)**, unchanged from Phase 6 |
| **78.40° S 21.87° E** (documented terrain-blocked case), ground +839 m | 4.22 to 16.74° | 330.0–344.9° | 26.30 to 29.94° | −22.99 to −12.12° | 0 / 1442 | 0 (Earth above 0° all 720 h but behind terrain) |
| 72.09° S 329.74° E, ground −3688 m | 7.89 to 22.20° | 24.5–38.1° | 29.08 to 30.78° | −21.70 to −8.24° | 0 / 1442 | 0 |
| 81.22° S 34.52° E, ground −3247 m | 0.75 to 13.18° | 317.5–332.3° | 14.67 to 16.74° | −14.32 to −2.78° | 0 / 1442 | 0 |
| 81.15° S 282.44° E, ground −3738 m | −5.55 to 8.67° | 71.0–84.1° | 13.01 to 15.13° | −19.96 to −4.50° | 0 / 1442 | 0 |
| 87.67° S 117.37° E (limb) | −7.75 to 5.06° | 235.3–249.7° | 19.38 to 19.67° | −27.19 to −14.58° | 0 / 1442 | 0 |
| 74.23° S 113.81° E (beyond the limb) | −11.94 to −0.85° | 239.0–254.7° | 2.24 to 4.29° | −16.04 to −3.43° | 0 / 1442 | 0 (Earth always below 0°) |
| 69.28° S 188.74° E (far side) | −27.47 to −13.97° | 163.3–178.0° | 2.00 to 3.10° | −29.65 to −16.77° | 0 / 1442 | 0 |
| 70.82° S 267.50° E (control, nonzero) | −8.85 to 6.53° | 86.5–98.3° | 2.24 to 4.59° | −11.79 to 2.61° | 333 / 1442 | 23.1% |

**Horizon is correct (`logs/01_independent_horizon.jsonl`).** An independent ray-march through the raw LOLA DEM files (nearest pixel, no engine horizon code, near field of two pixels excluded) agrees with the engine's horizon:
- within 0.001–0.11° at the reference site toward Earth (0.789° vs 0.788°), at the opposite azimuth (18.93° vs 18.97°) and at 90° to it;
- at 81.2° S 34.5° E toward Earth (15.57° vs 15.56°);
- in every off-Earth direction tested.

The only differences (1.5–5°) are at 0.04–0.5 km on steep crater walls in 240 m pixels, where nearest-pixel sampling is crude. They still put the horizon toward Earth at 28–34°, above the Earth's maximum elevation. A mirrored or rotated azimuth convention would have shown up in the opposite-azimuth checks; it did not.

**Frames and units:** consistent.
- Earth azimuths point toward the sub-Earth region, as they should from the south polar near side: about 0° at longitude 359°, about 338° (west of north) at 21.9° E, and about 78° (east of north) at 282.4° E.
- Clearance is Earth-centre elevation minus the horizon at the same azimuth, both in degrees in the same local frame.

**Sampling and events.**
- In every zero case the highest clearance over the month is −2.78° or lower. A window cannot hide between samples: event detection is adaptive at about 1 s, and the series step is 30 min.
- In the zero cases the Earth-disk fraction `f` is 0 at all 1442 samples.

**Intervals and the frontend (`logs/02_ui_figures.log`, `logs/03_overlap_and_summary_check.txt`).**
- The engine intervals are a single closed interval of 720 h at the zero sites.
- The browser shows exactly the engine values:
  - reference: 75.7%, 22 d 17 h, overlap 49.5%, 14 d 20 h, 3 windows;
  - zero sites: 0.0%, 0 min, longest gap 30 d 0 h, unknown 0 min.
- A missing value would display "n/a", not 0. No field is defaulted to zero.

**Overlap.** An independent intersection of the Sunlit and Earth-visibility intervals matches the engine:
- reference: 356.15 h in 3 windows;
- zero sites: 0 h.

The overlap must be 0 when the Earth is never in view.

**Unknown and Uncertain are zero.** Every horizon here has full terrain coverage (incomplete share 0.0), so no time is unknown. With no windows, and clearance far from 0 relative to the horizon σ (about 0.001–0.03°), nothing is flagged uncertain.

**Coordinates and window.** The request recorded in each result (lat, lon, start, end, step) equals the values typed in the UI. The UI result ID matches the cached result for the same settings.

## Recommendation
No calculation correction is needed. The labels are unchanged: Earth-disk visibility and events are still "Pending validation".

**Optional presentation improvement** (not implemented; for the owner to decide): when "Earth in view" is 0%, show the reason the engine result already contains. For example: "Earth stays below the terrain horizon at its azimuth all window (horizon about 26–30° vs Earth up to 16.7°)", or "Earth is below the local horizontal (far side)". This would let users tell a geometric zero from a missing result. The Communication tab already shows the "Earth above 0° but blocked by terrain" row.
