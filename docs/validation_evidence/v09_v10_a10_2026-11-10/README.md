# V-09 / V-10 against LOLA AVGVISIB (Phase 4, A10), 2026-11-10

**Status: implemented and tested; V-09 and V-10 are NOT decided.**
- **Criteria not approved:** the acceptance criteria (RMSE ≤ 5 percentage points, |bias| ≤ 2 pp) are **provisional and not approved**, so every result is reported as "not run" with its metrics. The script cannot report a pass until `CRITERIA["approved"]` is set after explicit approval.
- **Preliminary only:** the real-terrain run below uses the currently registered terrain. It is not merged into the validation report.
- **Repeat after A5/A6:** the final run must be repeated after A5 (20 m registration) and A6, because terrain resolution affects the horizons. It also needs the wider 240 m terrain identified in A11.

## Reference: data, encoding and documented rules (`backend/validation/reference/avgvisib/`)

| | V-09 (Sun) | V-10 (Earth) |
| --- | --- | --- |
| PDS IMG (primary) | `AVGVISIB_85S_060M_201608.IMG`, 51,166,728 B, SHA-256 `82dadf32…21c1efe1` | `…_EARTH.IMG`, 51,166,728 B, SHA-256 `09583130…b7948c11f` |
| PDS label (stored) | `avgvisib_85s_060m_201608.lbl` | `avgvisib_85s_060m_201608_earth.lbl` |
| PGDA GeoTIFF (cross-check) | identical DN at every pixel; same geotransform | identical DN at every pixel; same geotransform |

Source: PDS Geosciences node, `lrolol_1xxx/extras/illumination/img/`. Hashes and URLs are in `provenance.json`.

**Documented facts used:**
- **Value:** the fraction of timesteps in which any part of the disc is visible. The label reads "the percentage of timesteps where each pixel was sunlit (by any fraction of the solar disc)"; the EARTH product reads "Earth disc".
- **Earth rule:** PGDA 69 says Earth is "considered visible if any part of its disc is not obscured", so both tests use the **"any"** rule.
- **Scaling:** `AVERAGE_VISIBILITY = DN × 0.00004 + 0`, DN 25000 = 1, 16-bit LSB integer, 5058 × 5058.
  - Read checks: Sun DN 0–22,111 (maximum 0.88444); Earth DN 0–25,000. No value outside [0, 25000].
- **Time sampling:** PGDA 69 says "averaged over hourly timesteps spanning 18.6 years".
- **Source terrain and grid:** LDEM_85S_060M (LOLA data 2009-07-13 to 2013-07-18, product 2016-09-15). Polar stereographic, 60 m/pixel true at the pole, 1737.4 km sphere, DE421 mean-Earth frame.
  - The label grid (projection offset 2528.5 pixels) gives the geotransform `[60, 0, −151740, 0, −60, 151740]`, equal to PGDA's GeoTIFF.
- **Coverage:** complete to 85°S, partial to about 82.9°S (PDS `readme_illumination_2016.txt`).
- **Label defects** (recorded, not relied on): the IMAGE description calls the values "binary", and the EARTH label gives `MINIMUM_LATITUDE = 90`.

**Not documented, recorded as assumptions** (`provenance.json`):
- **Observer height:** 0 m. PGDA 69 implies surface-level maps: it says "height above the surface" needs further analysis. Mazarico et al. (2011) was not reachable here. *The diagnostics below show this matters.*
- **Start of the 18.6-year span:** 2026-01-01 (as V-11). Its effect was measured as ≤ 0.35 pp (below).
- **Earth occulting the Sun:** included, as in the engine's "any" rule. It changed 1,430 Sun-hours over all V-09 points.

## Method (`backend/validation/v09_v10_avgvisib.py`)
**Sampling** (defined here):
- **Domain:** the 60 m pixels wholly inside 85–90°S (all four corners).
- **Strata:** five equal-width strata of the reference value, 40 points each, drawn with `default_rng([seed, stratum])`.
- **Shortfall:** a stratum's shortfall goes one point at a time to the other strata in ascending order.
  - V-09 has only 19 pixels in [0.8, 1.0], so it gets 46/45/45/45/19.
  - V-10 gets 40 per stratum.
- **Determinism:** two draws are identical.

**Hourly visibility, vectorised:**
- **Track:** the Sun and Earth apparent positions are computed once per hour from the Moon's centre (spkcpo, `CN+S`, the engine's frame). Each site subtracts its own vector.
  - Agreement with the engine's per-site `sample_target` over 3,000 epochs across the 18.6 years at 4 sites: Sun 1.7e-6°, Earth 2.7e-5°.
- **Sun:** the sign of the exact spherical-cap top-edge clearance (`disk_edges_many`). Hours in which Earth's outer circle touches the Sun go to the engine (`full_state`).
- **Earth:** the oblate silhouette lies between circles of radius β = asin(b/d) and α = asin(a/d), because nested spheres give nested silhouettes. Hours in which those two circles disagree go to the engine.
- **Guard band:** any verdict within 1e-3° of zero also goes to the engine (37 × the geometry difference above). An approximation can therefore never change a verdict.
- **Scoring:** only points with a complete horizon are scored. Incomplete ones are inconclusive, as in V-11.

**Cross-check against the event detector** (`crosscheck_detector.txt`): **7,156 epochs, 0 mismatches.**

| Case | Result |
| --- | --- |
| Synthetic V-14 horizon, one synodic month hourly at 2 sites | Sun and Earth equal |
| Synthetic V-14 horizon, 10 days every 10 min at a third site | Sun and Earth equal |
| 3 March 2026 total eclipse, every minute at 3 sites (flat −10° horizon) | 69–71 min hidden by Earth, all equal |

Speed: 0.01–0.04 s per site-month against 10–41 s for the detector.

## Preliminary real-terrain run (`preliminary_run/`)
**Setup:**
- 200 points per test, 18.6 years hourly (163,048 epochs), observer at 0 m, production kernels, 2,260 s.
- **Terrain:** the registered 80 m PGDA 90 and 5 m PGDA 78 Site01 DEMs, re-downloaded and SHA-verified against the registry. They were served through `LUNAOPS_DEM_FALLBACK_DIRS`; `data/` and the registry were not touched.
- **Not merged** into the report.

| | Scored | Inconclusive | RMSE | Bias | Max abs. difference | Within provisional criteria? |
| --- | --- | --- | --- | --- | --- | --- |
| V-09 (Sun) | 130 / 200 | 70 | 10.22 pp | −4.29 pp | 42.9 pp | no |
| V-10 (Earth) | 123 / 200 | 77 | 1.98 pp | −0.28 pp | 13.5 pp | yes (not approved) |

**By stratum** (RMSE / bias in pp, scored points):

| Stratum | V-09 | V-10 |
| --- | --- | --- |
| [0, 0.2] | 1.47 / −0.16 (45) | 1.24 / −0.30 (32) |
| [0.2, 0.4] | 3.68 / −0.26 (35) | 2.56 / −0.74 (30) |
| [0.4, 0.6] | 2.52 / −1.25 (16) | 1.08 / +0.23 (35) |
| [0.6, 0.8] | 11.95 / −9.32 (19) | 0.75 / +0.14 (23) |
| [0.8, 1.0] | 26.07 / −22.97 (15) | 7.77 / −4.45 (3) |

## Diagnostics (`preliminary_run/diagnostics.json`, `epoch_sensitivity.json`)
**Observer height drives the V-09 high-illumination differences.** For the 36 V-09 points with |d| > 5 pp, the mean difference changes with observer height:

| Observer height | Mean difference |
| --- | --- |
| 0 m | −14.85 pp |
| 2 m | +1.46 pp |
| 10 m | +8.05 pp |

- **V-10 (6 such points):** −6.0 / +5.5 / +10.0 pp at the same heights.
- **What this means:**
  - The comparison is very sensitive to the undocumented observer height, and to how each DEM represents the near-field slope at 0 m.
  - For these points the reference behaves more like a small height above the surface than 0 m. That is an observation, not a determination of AVGVISIB's height, and no parameter was changed.
- **The reference is spatially rough.** For these points the reference varies by a median 38.7 pp (V-09) and 30.3 pp (V-10) within its own 3 × 3 pixels (±60 m). The computed value at 0 m lies inside that local range at 33 of 36 (V-09) and 6 of 6 (V-10) points.

**Inconclusive points are a terrain-coverage gap**, the same one found in A11:
- **V-09:** 21 reach the end of the 80 m level's 250 km window; 49 run off the registered data first. They lie mostly in strata 2 and 3.
- **V-10:** 11 and 66; mostly the top stratum (37).
- **Remedy:** the 240 m PGDA 90 `LDEM_60S_240MPP_ADJ` (600 km window), whose registration is A5/registry scope.

**Start epoch:** moving the 18.6-year span to 2009-07-13 changes 20 points per test by at most 0.35 pp (V-09, RMS 0.19) and 0.27 pp (V-10, RMS 0.09). It is negligible.

## Tests (`backend/tests/test_phase4_v09_v10.py`, 16)
- **Label facts and provenance:** hashes; the "any fraction of the disc" wording; DN × 0.00004 with 25000 = 1; grid, frame and sphere; geotransform equal to the GeoTIFF; both label defects present; criteria unapproved.
- **Encoding checks:** out-of-range DN, wrong scaling and wrong file size are refused.
- **Allocation:** 5 cases.
- **Stratified sampling:** inside 85°S, allocation and shortfall, deterministic.
- **Engine agreement:**
  - hourly geometry equals the engine's;
  - vectorised Sun and Earth equal the event detector (10 days every 20 min);
  - Earth occultation of the Sun equals the detector (2026-03-03 eclipse);
  - routing every hour to the engine changes nothing.
- **Inconclusive:** incomplete or missing terrain gives inconclusive.
- **Provisional criteria never pass:** with approved criteria the same metrics would pass, fail or be inconclusive, and a partial span is never decided.
- **End-to-end:** a synthetic run merges through the guard.

**Suites** (`tests/`): `test_phase4_v09_v10` 16 passed; production kernels **385 passed, 12 skipped**; sandbox kernels **382 passed, 15 skipped**; exit 0.

## Decisions needed before a final V-09 / V-10
1. **Approve, or replace, the acceptance criteria:** RMSE ≤ 5 pp and |bias| ≤ 2 pp, currently provisional.
2. **Confirm AVGVISIB's observer height**, from Mazarico et al. 2011 or the LOLA team. If it is not 0 m, run V-09/V-10 at that height; the preliminary run shows a large effect at bright points.
3. **Complete A5/A6 and register the wider 240 m terrain**, then repeat the run. That removes the inconclusive points and replaces the 80 m near field.
4. **Optionally, decide how to handle the reference's own spatial roughness** (39 pp within ±60 m at bright points). For example, compare against a neighbourhood value. This is a methodology change, not made here.
