# V-10 final scientific resolution (2026-11-14)

**Answer: V-10 cannot legitimately pass on this holdout under the frozen criteria.**

The investigation found **no defect in LUNA-OPS**:
- an independent horizon calculation on the same terrain reproduces the engine within about 1 pp at 17 of 17 locations;
- coordinates, the visibility definition, observer height, weighting, smooth classification and averaging period are all verified.

The failure is a terrain-model and reference-map difference at one location. There the Earth never rises more than 8.4° and the horizon is 2–7°, so a few metres of terrain decide the answer.

NASA's own newer terrain (PDS 2017, 40 m) does **not** reproduce NASA's 0 % patch: it gives 24 % at the point and 33 % across the patch. NASA's original source model (LDEM_85S_060M) is no longer distributed, so the patch cannot be reproduced or disproved exactly.

Turning V-10 into a Pass would need one of three things:
- removing the point;
- replacing NASA's reference value with our own reconstruction (circular, so not a validation);
- changing criteria after seeing the results.

All three are excluded. V-10 remains **Failed**. This supersedes the "likely artifact" wording of `V10_ROOT_CAUSE.md` with the numbers below.

## Part 2: NASA terrain

| Item | Finding |
|---|---|
| LDEM_85S_060M (NASA's stated source) | **Not available.** It is not in the current PDS LOLA GDR polar directory, which lists only the 2017 V2 products: 10, 20 and 40 m at 85° S, and 60 m only at 60° S and 75° S. The illumination `release_2011`/`release_2014`/`release_2016` folders contain readmes only. Checked 2026-11-14. |
| Independent NASA terrain used instead | `ldem_85s_40m.img` (V2.0, created 2017-06-15, LOLA data 2009-07-13 to 2017-02-02; 40 m; DN × 0.5 m above the 1737.4 km sphere; south polar stereographic) and `ldec_85s_40m.img` (LOLA shots per pixel). Kept unmodified with `SHA256SUMS` in `data/reference_validation/pds_lola_gdr_2017/`. |
| Registration | Ground height at the point: PDS 40 m −628.6 m, PGDA 20 m −628.5 m, engine −628 m. |
| Terrain in the patch | PDS minus PGDA: +1.2 m mean (3.0 m rms) in the patch, +2.4 m (4.9 m) in the ring 2–4 px out, +2.9 m (6.6 m) at 5–12 px. Neither model shows a crater, ridge or pit at the patch. The patch is a shallow hollow about 9 m below the ring 120–240 m away, in both models. |
| Data density (LOLA shots) | Patch: 1.97 shots per 40 m pixel, 29 % of pixels with no shot (interpolated). Ring 2–4 px: 2.44 and 22 %. Ring 5–12 px: 2.55 and 19 %. The patch is somewhat less densely measured, which supports, but does not prove, an interpolation effect in the older, sparser 2013-era model. |

**Earth visibility with the independent horizon method** (18.6-year track, mean over the listed pixels, %):

| | NASA map | Engine | Independent on PGDA 20 m | Independent on PDS 40 m (2017) |
|---|---|---|---|---|
| Failing point | **0.0** | 39.8 | 39.9 | 24.4 |
| Zero patch (8 px) | **0.0** | 42.0 | 41.0 | 33.4 (1 of 8 at 0) |
| Beside the patch (8 px) | 31.8 | 37.9 | 36.8 | 31.6 |

The independent method:
- uses its own ray-march (720 azimuths, out to 150 km, with curvature and projection scale);
- uses the engine's Earth ephemeris, which is validated by V-04/V-05;
- applies the any-part-of-the-disc rule.

Files: `pds_terrain_check.json/.txt`. A first run had the local-north sign reversed; it is kept as `SUPERSEDED_*` and not used.

**Critical question: can the older terrain model explain the 0 %?**

It cannot be tested directly, because that model is unavailable. The evidence:
1. The answer here is extremely sensitive to terrain. The Earth peaks at 8.4° and the horizon toward it is 2.4–5.3° (PGDA) or 6.1–7.4° (PDS 40 m) at the point, so roughly 1–3° more horizon, a few metres of terrain within 100–200 m, removes the Earth entirely.
2. NASA's 2017 terrain already lowers the point from 40 % to 24 % and puts one patch pixel at 0 %. A sparser, interpolated older model is therefore a plausible cause.
3. Neither current NASA nor PGDA terrain reproduces a 41-pixel zero patch, so the reference value is not supported by present-day terrain.

## Part 3: comparison methodology

| Item | Result |
|---|---|
| Coordinates and pixel registration | 0.3 m from the pixel centre (60 m pixels). The label's projection offsets were used, and the round trip is exact. |
| Earth-visibility definition | Same: any part of the Earth disc (NASA label; `visible_any`). |
| Apparent Earth disc | Angular radius asin(R_Earth/d). The independent and engine results agree within about 1 pp. |
| Observer height | 0 m, the approved project assumption. At 2 m the result is 42.8 %, so height cannot produce 0 %. |
| Terrain horizon | Engine 2.5–5.3° toward the Earth; independent method on the same terrain 2.4–5.3°. Verified. |
| Averaging period | NASA's 2014 readme for the same product family: Earth maps are averaged "over one lunar precession cycle (~18.6 years)". The label's 2009–2013 dates match the LOLA data-collection period (the 2017 terrain models carry the same start date). The engine's 18.6 years matches NASA's method. |
| Period sensitivity (2009-07-13 to 2013-07-18, same method) | Point 40.8 % vs 39.9 %; patch mean 41.9 % vs 41.0 %; beside 37.3 % vs 36.8 %. Immaterial (about 1 pp). File: `pds_terrain_check_period_2009_2013.json`. |
| Missing and uncertain data | 0 inconclusive; horizon complete. |
| Area weighting | Horvitz–Thompson weights over eligible pixels per stratum. Correct; stratum 0 has the most pixels. |
| R1 smooth classification | Correct as written: reference 3×3 range ≤ 5 pp. The point's 3×3 neighbourhood is 0.0–3.3 % because the zero patch (41 px) is larger than 3×3. So the point counts as "smooth" by the frozen rule. |

## What would and would not be legitimate

- **Not legitimate for this run:**
  - removing or replacing the point;
  - substituting our recomputed reference value;
  - switching V-10 to a different terrain model after seeing results;
  - widening the smooth window now.
- **Diagnostic only, not a result:** without this one point, R1 RMSE would be 0.37 pp and R2 3.48 pp (bias −0.73), both within limits. The failure therefore rests on this single location.
- **Legitimate future routes (each needs owner approval before any new data are seen):**
  1. Pre-register a reference-anomaly screen, for example excluding reference pixels inside isolated zero patches larger than 3×3 whose 9×9 surroundings average above X %. Then draw a **new** independent holdout.
  2. Pre-register a terrain-model-difference allowance.
  3. Ask NASA/GSFC (LOLA team) for LDEM_85S_060M and test the patch directly.

No engine file, criteria value, holdout point, weight or NASA dataset was changed. Engine `9cd7b08b…`, suite `70606628…`.
