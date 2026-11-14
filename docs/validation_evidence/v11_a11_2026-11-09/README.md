# V-11 permanent-shadow validation: script hardening (Phase 4, A11), 2026-11-09/10

**Status: V-11 has NOT been run on real terrain.** This folder documents the hardened validator and its checks
against the real reference map. The final V-11 run is deferred until A5 (PGDA 90 20 m registration) and A6 (overlap
statistics) are complete and the registered PGDA terrain is available. No V-11 result has been merged into the
validation report; V-11 stays "not run" and every dependent label stays Pending validation.

**On the registered terrain alone, a V-11 run could not pass.** The coverage diagnostic below shows 7 of the 200
formal points have incomplete horizons, so at most 96.5% could be shown dark. Wider terrain is required; see
"Terrain required".

**Unchanged:**
- **Acceptance criterion:** at least 99% of the formal sample with zero sunlight over an 18.6-year hourly Sun track.
- **Per-hour test:** El + rho_max ≥ the minimum horizon over the hour's azimuth sweep.
- **Tolerances, algorithm version (1.5.0), datasets, registry and A5/A6 files.**

## Formal sample and scoring (refined 2026-11-10)
**Formal sample: 200 points inside the documented coverage, 80–90°S.**
- PGDA states the `80S` products cover "80 - 90 deg South" (`coverage_review/pgda90_page_excerpt.txt`).
- A 160 m cell is used only if all four of its corners lie at or south of 80°S. In polar stereographic a cell's northernmost point is a corner.
- That limit is applied before the existing 2-cell margin. So every sampled point's whole 5 × 5-cell neighbourhood lies inside the coverage, and the point is at least 400 m inside the 80°S circle.
- Sampling is deterministic, as before: seeded choice (seed 1), points at cell centres.

**Real map** (`sampling_80S_formal.txt`, `formal_points_seed1_80S.json`):

| | Cells |
| --- | --- |
| Shadow | 711,098 |
| Shadow inside the coverage | 667,521 (43,577 excluded) |
| Interior | 470,581 (493,105 without the limit) |

- **Formal sample:** 200 points from 89.652°S to 80.081°S. Two draws are identical.
- **Closest to the limit:** 2.469 km inside the 80°S circle.
- **By band:** 30 at 88–90°S, 63 at 85–88°S, 72 at 82–85°S, 35 at 80–82°S.
- **Earlier unlimited sample** (89.745–77.796°S, `sampled_points_seed1.json`): kept only as the record of the review that led here.

**Point outcomes.**
- **Scored:** a point is scored only if its horizon is complete. Every one of its 3600 azimuth bins must be closed by the engine's exact stopping bound before the ray meets nodata, leaves all registered terrain, or reaches the end of its last window. A scored point is **dark** (zero sunlight) or **lit**.
- **Inconclusive:** a point with any incomplete bin, a non-finite horizon value, or no terrain horizon at all.
  - It is never scored, and never counted as dark.
  - It records the incomplete azimuth ranges.
  - It records the verdict of the lower-bound horizon under `unscored_` names, for review only.

**Overall status** (n = 200; the 99% rule unchanged):

| Status | Condition | Meaning |
| --- | --- | --- |
| passed | dark/n ≥ 0.99 | holds even if every inconclusive point were lit |
| failed | (dark + inconclusive)/n < 0.99 | fails even if every inconclusive point were dark |
| inconclusive | otherwise | |

- `inconclusive` is a new accepted status in `validation/common.py`.
- A merge never turns it into a pass: failed > inconclusive > passed.
- Labels gated by V-11 stay Pending with the reason "V-11: inconclusive".
- If fewer than 200 interior cells lie in the coverage, the run writes no result.

**Assumption, stated rather than changed.** Completeness follows the engine's stopping bound, which takes terrain beyond the loaded windows to be no higher than their highest sample (`h_max`, recorded per point). Unseen higher terrain could only raise the true horizon. That can turn a lit verdict dark, never the reverse, so a dark verdict on a complete horizon stands either way.

## Terrain coverage at the formal points (`coverage_review/horizon_coverage_registered.*`)
**Method.**
- The engine's own `compute_horizon` was run at all 200 formal points with the registered terrain only: `LDEM_80S_80MPP_ADJ`, re-downloaded with SHA-256 equal to the registry.
- The file was found through the engine's documented `LUNAOPS_DEM_FALLBACK_DIRS` lookup; `data/` and the registry were not touched.
- No point is within reach of the (missing) 5 m Site01 tile.
- **No sunlight was computed.**

**Results.**
- **193 of 200** formal points have complete horizons.
- **7 are incomplete,** all at 80.3–81.0°S:

| Point | Incomplete bins | Cause | Reach needed (upper bound) | Needs terrain to |
| --- | --- | --- | --- | --- |
| 80.979°S 88.411°E | 14 | left the 80 m data from 31.7 km | ≤ 32.0 km | 79.999°S, beyond the ±304 km square |
| 80.942°S 86.784°E | 620 | left the data from 29.0 km | ≤ 43.5 km | 79.748°S, beyond the square |
| 80.815°S 349.914°E | 34 | end of the 250 km window | ≤ 254.1 km | 86.788°S, inside the square |
| 80.771°S 349.863°E | 78 | end of the 250 km window | ≤ 260.5 km | 86.512°S, inside the square |
| 80.676°S 85.904°E | 391 | left the data from 21.2 km | ≤ 23.1 km | 79.915°S, beyond the square |
| 80.624°S 86.958°E | 408 | left the data from 19.4 km | ≤ 28.0 km | 79.866°S, beyond the square |
| 80.339°S 195.274°E | 920 | left the data from 20.6 km | ≤ 50.5 km | 79.331°S, beyond the square |

- **Reach needed:** an upper bound from the engine's own stopping bound, with each bin's current lower-bound horizon.
- **Consequence:** at most 193/200 = 96.5% can be shown dark, below 99%. On the registered terrain V-11 is at best **inconclusive**, and at least 5 of the 7 must be resolved before a pass is possible.

## Terrain required (`coverage_review/whatif_240m*`)
**What is missing.**
- **Data beyond the ±304 km square:** five points need it, as far as **79.33°S** (map radius 324.5 km).
- **Rays beyond the 80 m level's 250 km window:** two points need them, to **260.5 km**.
- The 80 m data there exist, but the engine's nominal window (a fixed physics setting) ends at 250 km. The next coarser level, 240 m, has a 600 km window.

**Data that would close it: PGDA 90 `LDEM_60S_240MPP_ADJ.TIF`.**
- The engine's existing **240 m** level, same projection and sphere.
- 7760 × 7760 pixels, ±931.2 km, reaching 60°S at the edge midpoints.
- 218,961,039 bytes, SHA-256 `3f966325…4d8cec8b34`, Last-Modified 2023-07-07.
- Its error map `LDEM_60S_240MPP_ADJ_ERR.TIF` (267,005,175 bytes) would be registered with it, for the horizon uncertainty.

**What-if check.** The product was downloaded to scratch only and added as the 240 m window to each point's registered pyramid, in memory, with the engine's reference loader (`LUNAOPS_WINDOW_MODE=full`; nothing registered).
- **Result** (`coverage_review/whatif_240m_all.txt`): with it, **all 200 formal points have complete horizons** (0 incomplete bins). With the registered terrain alone, 7 are incomplete.
- With it, `h_max` is 7024.8–7026.3 m.
- Reference mode reproduced the registered-terrain baseline exactly.

**Next step: a registry change, A5 scope, not done here.** Register the 60S 240 m product (and its error map) through `python -m lunaops.acquire register-dem`.

## Reference map: PGDA 90 `LPSR_80S_20MPP_ADJ.TIF`
**File** (`lpsr_reference.txt`):
- 154,221,202 bytes, SHA-256 `ad95311b…f470834e`, Last-Modified 2023-06-03.
- Downloaded to a scratch folder; not stored in the repository.

**Encoding** (`lpsr_encoding_probe.txt`, `lpsr_full_scan.txt`):
- Cloud-optimized GeoTIFF, 30,400 × 30,400 pixels of 20 m, float32, nodata NaN.
- South polar stereographic on the 1737.4 km sphere, extent ±304 km.
- A full-resolution scan found **only 0 and 1**: 55,856,975 pixels of 1 (22,342.8 km²) and 868,303,025 of 0.
- **The overview layers (2× to 64×) are resampled, not binary:** the coarsest has 223,017 distinct values, including negatives.

## Defect found and fixed: overview-based sampling
The previous `interior_points` read the map at 1/8 size, through the resampled overviews, and selected `a > 0`. On the real map (`sampling_real_map.txt`), with seed 1 and 200 points:

| Sampler | Points not in a fully shadowed cell | Points failing the full-resolution 2-cell interior test |
| --- | --- | --- |
| Previous | 3 | 32 (16%) |
| New | 0 | 0 |

**Its other defect:** its `np.roll` erosion wrapped across the raster edges.

**The new sampler:**
- Cells are 8 × 8 full-resolution pixels (160 m).
- A cell is shadow only if all 64 pixels equal 1; NaN counts as not shadow.
- An interior cell needs an all-shadow 5 × 5 neighbourhood: the original margin, now exact.
- The border is padded, not wrapped.

## Earlier coverage review (2026-11-09; context for the refinement)
`coverage_review/coverage_review.*` and `unseen_terrain.*` were run on the earlier unlimited sample.

**Findings:**
- The map's corners hold valid 0/1 values to 75.9°S with no edge artefact, but lie outside the documented coverage. 8 of 200 points (4%) came from them.
- A geometric screen bounded what unseen terrain could hide, using the LOLA `LDEM_4` global maximum, 10.504 km.

**Superseded by:**
- the 80–90°S formal sample;
- the engine diagnostic above. It is exact for the engine's own stopping, so it is far less pessimistic than the screen (7 incomplete points, not 24).

**Frame:** DE421 MOON_ME (map and DEM) against the engine's `MOON_ME_DE440_ME421`: at most 0.863 m at the surface (IB-2), negligible.

## Illumination test optimisation
`first_lit_hour` vectorises the original per-hour loop with an exact range-minimum table over the circular horizon:
- **Same cells and result as the loop:** checked on 500 random cases, including NaN horizons and arcs across the 0/360° seam.
- **Speed:** 20 ms against 0.4 s for a full 18.6-year track (163,047 hours).

## Output (per run)
- **Map:** encoding counts and SHA-256.
- **Sampling:** the statistics, including the coverage limit and its source.
- **Sun track:** hours and maximum solar radius.
- **Terrain:** the registered products digest.
- **Scoring:** the rule and counts: n, dark, lit, inconclusive, worst- and best-case shares.
- **Per point:** latitude, longitude, x/y, outcome, zero_sunlight (None when inconclusive), first lit hour and smallest clearance (scored points), incomplete bins and azimuth ranges, the reason, `h_max_m` and terrain levels.

## Tests (`tests/test_phase4_v11.py`, 22 tests; `tests/`)
**Map and sampling:**
- encoding check;
- full-resolution margin, border and determinism;
- overviews not used;
- erosion does not wrap;
- the vectorised test equals the loop;
- flat-horizon edge cases.

**Geographic boundary:**
- On a fully shadowed map straddling the 80°S circle, every point is south of 80°S and at least 400 m inside it. The margin is not exceeded needlessly. The same map without the limit gives points north of 80°S. Sampling is deterministic.
- A map wholly north of 80°S gives no point, and the run writes no result.

**Incomplete coverage:**
- An otherwise-dark horizon with incomplete bins, one incomplete bin, or a NaN bin is inconclusive (zero_sunlight None, unscored lower-bound verdict only). Azimuth runs merge across 0/360°.
- No terrain is inconclusive.
- The scoring table, 8 cases: inconclusive is never counted as dark, and a sample with nothing scored is never a pass.
- `inconclusive` merges, never combines into a pass, and keeps every V-11-gated label Pending.
- End-to-end over the real 18.6-year Sun track on a synthetic map: +20° horizon passes, −10° fails, +20° with two incomplete bins is inconclusive. Each result merges.

**Suite results** (`tests/`):
- Refinement (base `a697397` plus this change):
  - `test_phase4_v11`: **22 passed** (`test_phase4_v11_refined.log`).
  - Full backend suite with production kernels: **355 passed, 12 skipped** (`suite_production_refined.log`).
  - Full backend suite with sandbox kernels (`LUNAOPS_KERNEL_SOURCE=data/kernels_demo`): **352 passed, 15 skipped** (`suite_sandbox_refined.log`).
  - No failures. The single warning is the existing Starlette TestClient deprecation.
- First hardening commit (`7b70972`): 9 passed; production 342/12, sandbox 339/15 (`test_phase4_v11.log`, `suite_production.log`, `suite_sandbox.log`).

## Before a final V-11
1. Complete A5 and A6. The map is derived at 20 m; the registered terrain is 5 m Site01 plus 80 m.
2. Register the wider terrain identified above (`LDEM_60S_240MPP_ADJ` and its error map) and re-run `coverage_review/horizon_coverage.py`: every formal point should then be complete.
3. Make the registered terrain available here (SHA-256-verified against the registry).
4. Run `python -m validation.v11_psr --lpsr LPSR_80S_20MPP_ADJ.TIF --points 200 --out v11.json` with the production kernels.
5. Review lit points (clearance, first lit hour) and any inconclusive ones.
6. Merge into the report.

## Open uncertainties about the shadow map's derivation
The map is cited to Barker et al. 2023 (PSJ 4, 183, doi:10.3847/PSJ/acf3e1). PGDA's page states none of the following, and the paper was not consulted:
1. **Period** used to define "permanent". V-11 uses 18.6 years from 2026-01-01.
2. **Observer height.** V-11 uses 0 m. A positive height in the product would make its PSRs smaller, never larger.
3. **Sun model.** V-11 counts a point lit when any part of the disk clears the horizon, the strictest reading.
4. **Terrain extent behind the product's horizons.** If it extended beyond what LUNA-OPS has registered, the product's horizons include terrain LUNA-OPS cannot see.
   - Where that terrain matters, the ray usually runs out of data, so the point is inconclusive rather than lit.
   - A bin closed by the stopping bound can still miss unseen terrain higher than `h_max` (the stated assumption).
   - Such misses could only make a point look lit, never dark.
5. **Validity outside 80°S.** It no longer matters: the formal sample stays inside 80–90°S.
6. **Resolution.** The product is derived at 20 m; sub-cell rims seen at 20 m may not be resolved at 80 m. A5 addresses this.
7. **Frame.** DE421 MOON_ME against the engine's DE440 frame: ≤ 0.863 m, negligible.
