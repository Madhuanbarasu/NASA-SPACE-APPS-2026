# Earth pole of date (Phase 4, algorithm 1.5.0), 2026-11-08/09

Evidence for replacing the frozen J2000 Earth pole with the Celestial Intermediate Pole of date: IAU 2006
precession + IAU 2000B nutation, the SOFA/ERFA `pn06` + `nut00b` combination.
- Implementation commit: `c6413a0` on `claude/brave-fermat-jdx922`.
- Model, derivation and limitations: `docs/AUDIT_2026-11.md`, section *Phase 4: Earth pole of date*.
- Run conditions: cloud session, Python 3.13.18 (`backend/.venv`; CI uses 3.12), SpiceyPy 8.3.0 (CSPICE N0067).
- Production kernels: the set installed in A1 (`../kernels_production_2026-11-08/lock.json`).
- No tolerance, golden file or reference fixture was changed to make a test pass.

## Results

| Check | Criterion | Result |
| --- | --- | --- |
| ERFA published test values (`t_erfa_c.c`: nut00b, pfw06, obl06, fw2m, pn06 CIP row) | ERFA's own tolerances (1e-12 to 1e-16) | largest difference 7e-17 |
| ERFA at 602 TT epochs, 2000–2049 (`backend/tests/reference/erfa_cip_2000_2049.json`) | nutation ≤ 1e-15 rad; mean pole and CIP ≤ 1e-14 rad | met; largest CIP difference 2.9e-11″ |
| Frame bias of the IAU 2006 mean pole at J2000.0 | (−16.617, −6.819) mas, IERS 2010, ± 0.01 mas | met |
| Nutation amplitude (CIP − mean pole, 2000–2050) | < 11″, and > 6″ somewhere | met |
| Mean-pole precession over half a century | 0.5 × 2004.19″ ± 1″ | met |
| IAU 2006 mean pole vs IAU_EARTH (`pck00011`), 200 epochs 2000–2049 | ≤ 1.5″ (WGCCRE coefficient rounding, omitted T² terms, frame bias) | 0.632″ |
| CIP vs IAU_EARTH | ≤ 11″ + 1.5″ | 9.631″ (the nutation IAU_EARTH omits) |
| Frozen J2000 Z vs IAU_EARTH (for comparison) | none | up to 1000.9″ |
| **A2 frozen-pole check (`test_frozen_pole_against_iau_earth`, limit 1e-5° unchanged), engine pole vs IAU_EARTH** | P1, P2 < 1e-5° | **passed**: P1 1.25e-7°, P2 1.68e-7°, P3 3.5e-8, ε max 9.63″ (A2 with the frozen pole: P2 1.82e-5°, failed) |

## Event timing: new pole against the old frozen pole (`impact/`)
**Setup.**
- The real `EventDetector`, site −89°, 45°.
- 30-day windows from 2026-11-01, 2036-11-01 and 2046-11-01.
- Four horizons (flat, sloped 0.6, sloped 0.8, notched) through Earth's median position: 12 cases, 85 events.

**Results.**
- Event sequences are identical in every case, with zero step-estimate failures for either pole.

| Event | Largest shift |
| --- | --- |
| Earth centre (default DTE rule `centre`) | ≤ 0.004 s (bisection noise) |
| Earth upper/lower limb (DTE rules `any`, `full`), 2026 | 0.42 s |
| Earth upper/lower limb, 2036 | 2.23 s |
| Earth upper/lower limb, 2046 | 0.23 s |

- This run used the first, pure-NumPy version of the pole code. The numba version that was committed computes
  the same model, within 1e-16 rad (the ERFA comparison above).

**Cost** (`impact/timing_result.txt`): a 30-day detection takes 1.8% longer (median 11.64 s against 11.43 s,
three alternating runs in one process).

## Investigation before the change (`investigation/`)
- `pole_study.py` compares the frozen pole, IAU_EARTH, and an approximate reference pole of date. The reference
  is IAU 2006 ζ_A/θ_A precession with the dominant nutation terms (Meeus), good to about 0.5″; it is not the
  final model.
- **Findings:**
  - frozen vs reference: P2 up to 1.83e-5° on the slope-0.8 horizon;
  - IAU_EARTH vs reference: P2 ≤ 1.7e-7°;
  - same-horizon event shifts as in the table above.

## Full backend suites at `c6413a0`'s content (`suites/`)
- **Production kernels:** 315 passed, 12 skipped. The skips are 10 tests that need the PGDA files and 2
  kernel-setup tests that need the sandbox set as source.
- **Sandbox kernels:** 314 passed, 13 skipped. The skips are 10 PGDA, V-02e, and the two IAU_EARTH checks, which
  need the production PCK.
- Both exit 0. The Phase 2 golden tests pass with both kernel sets.

## Validation report (`report_production_1.5.0.json`)
`python -m validation.run_validation` at `c6413a0` (`code_version 0.1.0+c6413a0`), run 2026-11-09T06:03Z with the production kernels. It is a copy of the live, git-ignored `backend/validation/report.json`; the log is `run_validation.log`.

**Contents:**
- `pytest_exit_code` 0: 315 passed, 12 skipped.
- Report entries: 293 passed, 12 skipped, 0 failed, 9 not run.
- Not run: V-04, V-05, V-09, V-10, V-11, V-12, V-13, U-04, U-06.
- V-14 is the in-suite short form; the month-long form was not run or merged.
- `terrain_products` is empty (no PGDA terrain here).

**Report-level blockers:** none for the first time. That means production kernels, matching code and suite fingerprints, and a passing suite.

**Labels:** every quantity is still **Pending validation**:
- `sun_earth_azel`, `horizon`, `disk_visibility`, `events` and `power_indicator` each list U-04 and U-06 (global) and their own unexecuted V-tests (V-04, V-05, V-09 to V-13) as reasons. This was checked with `provenance.compute_labels` on this report.
- Any result on real terrain would also be blocked by "terrain product not covered by validation report".

## ERFA provenance
See `erfa_provenance.txt`. ERFA was used only to read its source and test values and to generate the reference
file, from a separate virtualenv. It is not a LUNA-OPS dependency.
