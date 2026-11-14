# V-10 failure: root-cause investigation (2026-11-14)

> **Superseded in part (2026-11-14) by `V10_FINAL_RESOLUTION.md`:** NASA 2017 PDS terrain was retrieved and an independent horizon check was run; see that file for the numbers.

**Conclusion.** No defect was found in LUNA-OPS: not in the calculation, the coordinate conversion, the reference reading, the weighting or the time sampling.

The failure comes from one compact patch of NASA's Earth-visibility map (41 pixels, about 760 m × 280 m) that says the Earth is never visible. In the current, higher-resolution LOLA terrain that patch has no terrain able to hide the Earth, and NASA's own map just beside it agrees with LUNA-OPS.

The most likely cause is a local feature or artifact in NASA's older source terrain model LDEM_85S_060M. NASA's readme warns that "some maps show linear artifacts that arise from the topographic DEMs". This is **likely but not proven**: LDEM_85S_060M is not available locally.

**No engine correction is justified.** Changing the engine to match this point would be tuning to the benchmark. **V-10 stays Failed** under the frozen criteria, with the frozen 200 points and without removing the point.

## Evidence, item by item

| # | Question | Finding | File |
|---|---|---|---|
| 1 | NASA value and record | `AVGVISIB_85S_060M_201608_EARTH.IMG`, pixel (row 1909, col 250). Value 0.00 %; the label defines DN 0 as "permanent shadow" for the Earth, a real value, not a fill value. NASA Sun map at the same pixel: 26.3 %. | `band_investigation.json` (A) |
| 2 | LUNA-OPS value | 39.80 % (holdout). Reproduced at 39.79 %. | `../V10_holdout/outlier_diagnosis.json` |
| 3 | Coordinates | The point lies 0.3 m from the pixel centre (60 m pixels) using the label's projection offsets; the round trip is exact. Mapping is correct. | (A) |
| 4 | Observer height | 0 m (project assumption; NASA states none). 2 m gives 42.8 %, so height cannot produce 0 %. | `outlier_diagnosis.json` |
| 5 | Terrain and horizon | Engine horizon toward the Earth (azimuth 66–83°) is 2.5–5.3°, set by terrain 10–20 m away on the 20 m LOLA product, with complete coverage. To hide the Earth at all times the horizon would need to exceed about 8.4°. LOLA 20 m shows only a 2.5 m-deep trough across the patch. | `outlier_diagnosis.json`, (D) |
| 6 | Time period and sampling | Engine: hourly over 18.6 years (full nodal cycle). NASA's label period is 2009-07-13 to 2013-07-18. A period difference shifts averages by a few points; it cannot turn about 40 % into exactly 0 % on one patch while the pixels beside it agree. | label; (A) |
| 7 | Missing or uncertain periods | 0 inconclusive; horizon complete; nothing missing was counted as visible. | holdout result |
| 8 | Interpolation and coverage | Nearest-pixel reading, no interpolation; the point is well inside the reference extent. | (A) |
| 9 | Same definition? | Yes. NASA counts time steps when "any fraction of the Earth disc" is visible; V-10 uses the same any-fraction rule (`visible_any`). | label; `v09_v10_avgvisib.py` |
| 10 | Weighting | Horvitz–Thompson weights (eligible pixels per stratum / points scored). The point is in stratum 0, which has the largest pixel count, so its weight is large; that is correct for an area statistic, not an error. | `v09_v10_avgvisib.py` |

## Decisive test: the engine on the patch and beside it

The unchanged engine was run on 8 random pixels inside NASA's zero patch and 8 pixels 2–4 pixels beside it. Same track and same 0 m height as the holdout. File: `band_neighbours_corrected.json`.

| Group | NASA | Engine | Mean difference |
|---|---|---|---|
| Inside the zero patch (8) | 0.0 % (all) | 37.2–50.0 % (mean 42.0) | +42.0 pp |
| Beside the patch (8) | 13.2–48.7 % (mean 31.8) | 26.7–45.1 % (mean 37.9) | +6.0 pp |

Beside the patch, 5 of 8 pixels agree within 2–10 pp. The 3 that differ lie on the south-west margin, where NASA's values fall steeply toward the patch (13–22 %).

In short, the engine's field is smooth across this area, as the terrain is. NASA's field drops from about 40 % to 0 % within one or two 60 m pixels, with no terrain cause in the current LOLA data.

## Other observations

- NASA's Sun map is also about 9 pp lower on the patch (30.8 % vs 40.1 % beside it). This fits a local depression in NASA's source terrain model, which would lower both maps.
- The patch is compact, not a long line, and runs 57° from the local meridian, so it is not a single LOLA ground track. "Artifact" is therefore not proven; an interpolation pit or a real sub-pixel feature in the older terrain model remains possible.

## Options for the owner (criteria stay frozen)

1. **Accept V-10 as Failed**, with this documented cause: a local reference-map discrepancy, no LUNA-OPS defect found. Recommended now.
2. **Confirm the cause with NASA's source terrain.** Download LDEM_85S_060M (public PDS data, read only) and compute the horizon at this point with it.
   - If that terrain has a pit absent from the 20 m product, the cause is proven.
   - This would **not** change this run's result: the points are frozen and nothing is removed.
3. **For a future, new holdout only**, pre-register a screen for isolated reference anomalies before any results are seen. This is a criteria change that needs your approval; it cannot be applied to this run.

No engine file, criteria value, holdout point or NASA dataset was changed.
