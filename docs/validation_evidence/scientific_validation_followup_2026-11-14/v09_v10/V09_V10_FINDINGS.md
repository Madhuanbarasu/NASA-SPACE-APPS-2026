# V-09 / V-10: criteria investigation (follow-up, 2026-11-14)

**Status of both: Investigated.**
- **Criteria:** the acceptance criteria remain provisional and unapproved.
- **Reference method:** the reference methodology is unconfirmed.
- **No algorithm changes:** the illumination and Earth-visibility algorithms were not changed.
- **Revalidation required:** the event correction does not affect V-09/V-10 (the benchmark scores only complete horizons, and its per-hour verdicts do not use interval construction). The benchmark nevertheless needs a run under the new engine fingerprint before any decision.

**Earlier evidence used** (not repeated): `../../scientific_validation_investigation_2026-11-14/`. It contains the per-point residuals of all 200 points per test, the 25-point experiment, smooth-subset statistics and area-weighted statistics.

## 1. NASA reference observer height
- **Sources checked:**
  - the stored PDS labels (`backend/validation/reference/avgvisib/*.lbl`);
  - `provenance.json` (PGDA 69 wording);
  - two web searches for the Mazarico et al. (2011) method and the PDS illumination readme.
- **Not found in any accessible source:** the observer height for AVGVISIB_85S_060M.
  - Mazarico et al. 2011 (*Icarus* 211, 1066–1081, doi:10.1016/j.icarus.2010.10.030) describes LOLA-based illumination over 18.6-year cycles at 240 m/pixel. Its full text, which would give the height convention, was not accessible here.
  - PGDA 69 refers to "height above the surface" as needing further analysis, which suggests surface-level maps. This is an inference, not a statement of the value.
- **Status:** unresolved. The 0 m assumption remains a recorded assumption, not a fact.
- **Next:** obtain the paper's methods section, or ask the LOLA team (PGDA contact).

## 2. Reference terrain resolution and averaging
- **Terrain:** AVGVISIB is produced on LDEM_85S_060M (LOLA, 60 m/pixel, product 2016-09-15), as stated in the label.
- **Averaging:** hourly timesteps over 18.6 years, with "any fraction of the disc".
- **Not documented:** how the observer point is placed within a 60 m pixel (centre, mean or maximum height), and how the near field is treated. A 60 m DEM cannot represent the sub-pixel relief that a 5 m or 20 m DEM has.
- **Measured effect** (25-point experiment): replacing the engine's near field with the 20 m product averaged to 60 m halves the worst-point error, but worsens points that already agree. Resolution alone does not explain the discrepancy.

## 3. Equal-weighted and area-weighted statistics (all 200 points, reported separately)
| | V-09 RMSE / bias (pp) | V-10 RMSE / bias (pp) |
|---|---|---|
| Equal weight per sampled point (as reported by the script) | **14.09 / −7.19** | **3.13 / −0.74** |
| Area-weighted (each point × its stratum's pixel count / points drawn) | **3.77 / −0.97** | **3.28 / −0.90** |
| Reference spatially smooth (3 × 3 range ≤ 5 pp) | 1.15 / −0.34 (n = 90) | 1.04 / −0.19 (n = 160) |
| Without the 10 points with the largest error | 10.37 / −5.28 | 0.87 / −0.13 |

**Why the weightings differ:**
- **V-09:** the stratified design draws 64 of 200 points from the two brightest strata, which hold 1,479 of about 20 million pixels (0.007 %). The equal-weight RMSE therefore describes the rare bright extremes, and the area-weighted one the map.
- **V-10:** the strata are more even in area, so the two weightings agree (3.13 against 3.28).

**Neither weighting is "the" right one; they answer different questions:**
- equal weight per stratum: accuracy across the range of values;
- area weight: typical accuracy over the region.

Both should be reported.

## 4. The 25 alternative-assumption comparisons (already run; not repeated)
| | Worst points: RMSE / bias | Control points: RMSE / bias |
|---|---|---|
| V-09, 0 m (as benchmarked) | 43.91 / −43.56 (n = 10) | 1.12 / −0.69 (n = 5) |
| V-09, 2 m | 7.55 / −0.37 | 3.10 / +1.72 |
| V-09, 60 m near field, 0 m | 22.56 / −21.42 | 11.67 / −6.55 |
| V-10, 0 m | 16.07 / −15.50 (n = 6) | 0.01 / −0.01 (n = 4) |
| V-10, 2 m | 4.60 / +3.85 | 0.04 / +0.02 |
| V-10, 60 m near field, 0 m | 8.60 / −7.43 | 0.01 / 0.00 |

**Reading:**
- **No single change reconciles all points:** 2 m fixes V-09's worst points but makes the controls overshoot (+1.7), and over-corrects V-10's worst (+3.9).
- **The discrepancy at bright and grazing points is a definitional difference** (observer point and near field), mixed with a terrain difference. It is not a calculation error.
- **These 25 points are the worst ones and therefore not representative.** They diagnose the mechanism; they do not estimate accuracy.

## 5. Is a fresh holdout sample required?
**Yes, before any criterion derived from these results is approved.**
- **Why:** the recommended criteria R1–R3 (below) were written after the residuals were seen, so evaluating them on the same 200 points is circular. A favourable result would be partly built in.
- **Proposed design (not run here):**
  - a second stratified sample of 200 points per test, with a different seed fixed before the run and recorded in advance;
  - the same definition (observer height as approved, or 0 m with the limitation documented);
  - criteria fixed in writing before the run;
  - about 2 hours of computation per run on this machine (the existing run took 7,386 s for both tests).

## 6. Criteria recommendations (not approved)
- **R1, well-posed subset** (reference 3 × 3 range ≤ 5 pp): RMSE ≤ 2 pp and |bias| ≤ 1 pp.
  - **Rationale:** where the reference is locally smooth, the residual budget is set by hourly sampling and start epoch (≤ 0.35 pp), geometry (negligible) and DEM version (unknown, small where the terrain is smooth).
- **R2, map level:** area-weighted RMSE ≤ 5 pp and |bias| ≤ 2 pp. These are the provisional numbers, applied to the statistic that measures typical accuracy over the region.
- **R3, reported, not gated:**
  - equal-weight statistics;
  - the fraction of computed values within the reference's own 3 × 3 range (V-09 84 %, V-10 78.5 %);
  - a list of bright and grazing outliers with the near-field caveat.
- **Prerequisite for all of them:** confirm the reference's observer height; then run on a fresh holdout under the approved definition.

**Circularity:** these were formulated after viewing the results. They are argued from the reference's resolution, sampling design and documented behaviour, but approving them on the same data risks designing a pass. The holdout run in section 5 removes that risk.

**The provisional limits** (RMSE ≤ 5 pp, |bias| ≤ 2 pp on equal weights) remain the only limits on record, labelled provisional. Nothing has been approved or changed.
