# Frozen acceptance criteria and holdout methodology (Phase 7)

**Frozen:** 2026-11-14T03:25Z. This was written before any holdout point was drawn or computed. It is not to be changed after holdout results are seen.

**Approved by the owner:** R1–R3 for V-09/V-10; the 0.0005 disk tolerance; the 1 s / 2 s event tolerances; the power-indicator acceptance basis (Phase 7 instruction).

## A. V-09 (Sun) and V-10 (Earth): LOLA AVGVISIB holdout
**Reference:**
- `AVGVISIB_85S_060M_201608.IMG` (V-09) and `…_EARTH.IMG` (V-10). Hashes are in `backend/validation/reference/avgvisib/provenance.json`.
- 60 m/pixel; value = DN × 0.00004; "any fraction of the disc"; hourly over 18.6 years.

**Observer height:**
- **NASA's observer height is unknown.** It is not stated in the PDS labels, PGDA 69 or the official PDS `readme_illumination_2016.txt` (copy in this folder, SHA-256 `f806f9c7…`). The full text of Mazarico et al. 2011 was not accessible.
- **The project models 0 m** (observer on the DEM surface). This is a project modelling assumption, **not a claim about NASA's method**. It is recorded as a limitation.
- The PDS readme also states that "some maps show linear artifacts that arise from the topographic DEMS" and that the products "are not supported by the PDS or the LOLA Science Team". Both are recorded as reference limitations.

**Model settings (unchanged from the inspected benchmark):**
- start 2026-01-01T00:00:00Z, 18.6 years, hourly;
- the "any" rule; Earth occultation of the Sun included;
- the engine at code fingerprint `9cd7b08b…`;
- registered terrain (5/20/80/240 m) with the terrain acceptance gate.

**Sampling region:** AVGVISIB pixels whose four corners all lie at or south of 85° S (the documented complete-coverage region), the same rule as before.

**Independence:**
- every pixel used by the previously inspected benchmark (seed 1, runs of 2026-11-10 and 2026-11-12, 200 per test) is excluded from both holdout samples;
- the old results are not consulted when selecting points.

**Sampling design:**
- **Strata:** the same 5 equal-width strata of the reference value ([0, 0.2), [0.2, 0.4), [0.4, 0.6), [0.6, 0.8), [0.8, 1.0]); nominal 40 points each, 200 per test.
- **Shortfall:** a stratum's shortfall goes one point at a time to the other strata in ascending order (the existing `allocate`).
- **Random generator:** `numpy.random.default_rng([20261114, stratum])`, sampling without replacement. **Seed 20261114.**
- **Known consequence:** V-09's [0.8, 1.0] stratum has 19 pixels, all used before, so it has 0 eligible pixels and its 40 points are reallocated. That stratum (19 of about 20 million pixels) is not represented; this is reported.

**Freezing the points:**
- the selected points are written to `V09_holdout/points_frozen.json` and `V10_holdout/points_frozen.json`;
- their SHA-256 values are recorded in `scientific_criteria/points_sha256.txt` **before** the model is run;
- the run loads these files and refuses to start if the hash differs;
- no point is removed or replaced after selection.

**Smooth-region mask (R1):**
- for each point, the range (max − min) of the reference over its 3 × 3 pixel neighbourhood (the pixel and its 8 neighbours: ±60 m);
- the point is "locally smooth" when that range is ≤ 0.05 (5 percentage points);
- computed from the reference map only, at selection time.

**Weights (R2):**
- Horvitz–Thompson inclusion-probability weights: for a point in stratum h, w = N_h / n_h. N_h is the number of eligible pixels in stratum h (inside the region, not previously used); n_h is the number of scored points in stratum h.
- All pixels have equal nominal area (60 m); the polar-stereographic scale factor varies by < 0.2 % within 85° S and is ignored.
- Area-weighted RMSE = sqrt(Σ w d² / Σ w); bias = Σ w d / Σ w; d = computed − reference, in percentage points.

**Gates:**

| Gate | Statistic | Limit |
|---|---|---|
| **R1** | Unweighted RMSE and bias over the scored points inside the smooth mask (the statistic presented when R1 was approved) | RMSE ≤ 2 pp **and** \|bias\| ≤ 1 pp |
| **R2** | Area-weighted RMSE and bias over all scored points | RMSE ≤ 5 pp **and** \|bias\| ≤ 2 pp |
| R3 (diagnostic, not a gate) | Equal-weight RMSE and bias; maximum \|d\|; outliers \|d\| > 10 pp with coordinates; per-stratum values; area-weighted R1 (also diagnostic); fraction of computed values inside the reference's 3 × 3 range | — |

**Status rules** (the existing script rules, plus R1 evaluability):
- **"not run":** the span is shorter than 18.6 years, the terrain gate is not met, or fewer than 20 scored smooth points (R1 not evaluable).
- **"inconclusive":** any point inconclusive (incomplete horizon or unknown engine verdict).
- **"passed":** R1 and R2 both met.
- **"failed":** otherwise.

**Run once.** A rerun is allowed only for a technical failure (crash), with the same frozen points, and recorded.

## B. Earth-disk visibility
- **Absolute visible-fraction difference** to the independent spheroid/cap ray-cast: ≤ 0.0005.
- **Classifications:** any-, centre- and fully-visible must match the independent reference in every comparable case.
- **Excluded cases:** where the reference itself cannot decide, namely missing terrain (an expected "unknown") and clearances within the reference grid resolution. These are reported, not hidden.

## C. Event detection
- **Timing:** edge error ≤ 1 s; duration error ≤ 2 s, against an independent brute-force scan.
- **Missing terrain:** must be Unknown, never Visible. Entering and leaving missing terrain must be interval boundaries (each within 1 s of the per-second unknown flag).

## D. Power indicator (Estimated; dimensionless)
- **Equation:** P_rel = f_sun × (1 au / r)² × k(panel).
- **Agreement:** with an independent calculation within storage precision (5 decimals: |Δ| ≤ 1.5e-5) for every stored series, all panel models.
- **Edge cases:** all 14 as defined.
- **Frontend/backend:** agreement within display rounding.
- **Units and terminology:** dimensionless; not watts.
- **Inputs:** missing and invalid inputs refused.
- **Scope:** mathematical and implementation validation only. **Not** validation against measured spacecraft electrical power.
