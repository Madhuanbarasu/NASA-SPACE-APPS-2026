# V-09 / V-10: methodology decision report (for the owner; nothing approved)

**Evidence reused** (no new benchmark run):
- `../../scientific_validation_investigation_2026-11-14/` (per-point residuals of all 200 points per test; 25-point experiment);
- `../../scientific_validation_followup_2026-11-14/v09_v10/`;
- source run: `../../backend_tiles_and_ui_fixes_2026-11-12/validation/v09_v10.json`.

**Status of both: Investigated.**
- The criteria are provisional and unapproved.
- The run must be repeated under the current engine fingerprint (`9cd7b08b…`) before any decision. The event correction does not change these values: complete horizons, per-hour verdicts.

## 1. The facts the decision rests on
| | V-09 Sun | V-10 Earth |
|---|---|---|
| Equal weight per sampled point: RMSE / bias | **14.09 / −7.19 pp** | **3.13 / −0.74 pp** |
| Area-weighted (stratum pixels / points drawn) | **3.77 / −0.97 pp** | **3.28 / −0.90 pp** |
| Reference locally smooth (3 × 3 range ≤ 5 pp) | 1.15 / −0.34 (n = 90) | 1.04 / −0.19 (n = 160) |
| Points whose computed value lies within the reference's own ±60 m range | 168/200 (84 %) | 157/200 (78.5 %) |
| Share of squared error in the 10 worst points | 48.5 % | 92.6 % |

1. **Weighting.** Sampling is five equal-width brightness strata, 40 points each.
   - For V-09 the two brightest strata hold 1,479 of about 20 million pixels (0.007 % of the area), yet contribute 64 of the 200 points (32 %). Equal-weight statistics therefore measure the rare extremes; area-weighted statistics measure the map.
   - For V-10 the strata are balanced in area, and both weightings agree.
2. **Observer height** (largest uncertainty):
   - Not documented for AVGVISIB in the labels, PGDA 69 or the sources searched. Mazarico et al. 2011 (*Icarus* 211) was not accessible in full.
   - The benchmark assumes 0 m.
   - At bright ridges and rims the Sun stays below about 1.5°, so a 2 m height changes the 10 worst V-09 points by about +40 pp: RMSE 43.9 → 7.6. The controls then overshoot by +1.7 pp, and V-10's worst over-correct by +3.9 pp, so no single height reconciles every point.
3. **Reference terrain:**
   - AVGVISIB uses LDEM_85S_060M: 60 m pixels, from 2016.
   - LUNA-OPS uses PGDA 90 at 20/80/240 m and PGDA 78 at 5 m (Site01).
   - Averaging the near field to 60 m explains about half of the worst-point error, and worsens points that already agree.
   - Within ±60 m the reference itself varies by up to 85 pp at bright points (median 5.6 pp, 90th percentile 42.7 pp, V-09).
4. **Not limiting:** time sampling and start epoch (≤ 0.35 pp) and geometry (≤ 2e-5°).
5. **No implementation defect** was found: values reproduce exactly, geometry agrees with the engine, and disk verdicts agree with an independent ray-cast.

## 2. Circularity risk
- R1–R3 below were formulated **after** the residuals were seen.
- The reasoning comes from the reference's resolution, sampling design and documented behaviour, not from tuning to pass. Even so, approving them and judging them on the same 200 points would partly build the outcome in.
- Example: the smooth-subset threshold (≤ 5 pp) could be chosen, consciously or not, where the current numbers look good.
- **Only a fresh, pre-registered holdout sample removes this.**

## 3. Recommended methodology (for approval)
1. **Fix the definition first, in writing:**
   - Ask the LOLA/PGDA team, or obtain Mazarico et al. 2011, for the AVGVISIB observer height and near-field method. Do not wait on this indefinitely.
   - If unavailable by the Phase 7 start, adopt **0 m with a documented limitation** ("reference height unknown; bright-point residuals are definitional").
2. **Pre-register before running:**
   - the criteria (below);
   - the statistics: area-weighted primary; smooth-subset and equal-weight reported;
   - the definition;
   - a **new sampling seed**.
3. **Independent holdout:**
   - 200 new stratified points per test with the new seed;
   - run once under the current fingerprint;
   - judged only against the pre-registered criteria;
   - about 2 h of computation;
   - **not run now**, as instructed: it needs the methodology approved first.
4. **Optional, to separate data from method:** one run using LDEM_85S_060M itself for the horizon (one PDS download).
5. **Report always:** equal-weight statistics, bright-point outliers with the near-field caveat, and the fraction within the reference's ±60 m range. Informative, not gating.

## 4. Recommended acceptance criteria (proposals; not approved)
| ID | Statistic (on the holdout) | Proposed limit | Basis |
|---|---|---|---|
| **R2 (primary)** | Area-weighted RMSE / \|bias\| | ≤ 5 pp / ≤ 2 pp | The provisional numbers on file, applied to the statistic that measures map accuracy |
| **R1** | Smooth subset (reference ±60 m range ≤ 5 pp): RMSE / \|bias\| | ≤ 2 pp / ≤ 1 pp | Where the comparison is well posed, the residual budget is sampling, epoch and DEM version (≤ about 1 pp) |
| **R3** | Equal-weight RMSE/bias, the within-range fraction, the outlier list | Reported, not gating | They describe extremes dominated by the undefined reference height |

**Decision needed:**
1. Approve, amend or reject R1–R3.
2. Choose the observer-height policy (wait for the source, or accept 0 m as a documented limitation).
3. Authorise the holdout run.

Until then V-09 and V-10 stay **Investigated**; no Pass or Fail is assigned.
