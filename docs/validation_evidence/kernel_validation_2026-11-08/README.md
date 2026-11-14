# Production-kernel scientific validation (Phase 4, A2), 2026-11-08

**Run conditions:**
- Cloud session, Python 3.13.18 (project `backend/.venv`; CI uses 3.12), SpiceyPy 8.3.0, CSPICE N0067.
- Code: branch `claude/brave-fermat-jdx922` at `4eb5c3f`. Its `backend/` is identical to `main` `b4ad283`; the
  report shows `code_version 0.1.0+4eb5c3f` because the version string follows git HEAD.
- Kernels: the production set installed in A1 (`kernels_lock.json`, manifest SHA-256 `c54f8025…`). Their SHA-256
  values were identical before and after every run here (`kernels_sha256_before_after.txt`).
- Nothing was changed in engine code, tests, tolerances, reference data or manifests.

## Results

| Check | Acceptance criterion (as coded) | Result | Status |
| --- | --- | --- | --- |
| V-01 UTC/TDB round trip | < 1 ms | pass | **passed** |
| V-02a frame definition | `MOON_ME_DE440_ME421` defined, centred on 301 | id 31009, class 4, centre 301 | **passed** |
| V-02b PA→ME rotation | orthonormal (1e-12); \|angle − 0.02886°\| < 5e-5° | 0.028863°; errors 2.2e-16 | **passed** |
| V-02c transformation direction | round trip 1e-12 | pass | **passed** |
| V-02d site round trip | < 1 mm | pass | **passed** |
| V-02e DE421/DE440 residual | d_max ≤ 1.0 m at 1 June 2026…2036 (11 epochs) | **d_max = 0.506 m** (2033) | **passed** |
| V-03 az/el vs SPICE AZLCPO (6 sites, Sun and Earth) | 1e-6° | pass; VT-10 south-pole output recorded | **passed** |
| Frozen J2000 Earth pole vs IAU_EARTH (`test_frozen_pole_against_iau_earth`), per-epoch bounds P1, P2, P3 at 200 epochs 2000–2049 | P1, P2, P3 each ≤ its bound for that epoch's ε(t) | All 200 epochs within all three bounds | met |
| Same test, final absolute check | worst P1 < 1e-5° **and** worst P2 < 1e-5° | P1 = 3.11e-6°; **P2 = 1.82e-5°** | **FAILED** |

V-02e d_max at each test epoch (m), 2026 to 2036: 0.330, 0.328, 0.323, 0.274, 0.432, 0.315, 0.317, 0.506, 0.155,
0.389, 0.357.

**Wider sampling (diagnostics only, not an acceptance criterion):**
- monthly 2026–2036: max 0.513 m;
- daily 2026–2036 (4019 epochs): max 0.533 m;
- every 1 June 1901–2049: max 0.890 m.

So the 1 m rule also holds at denser sampling in the 2026–2036 window, but by a margin of under 0.11 m over 1901–2049.

## The frozen-pole failure

**Setup.** ε(t) = ∠(J2000 Z, IAU_EARTH Z) is computed per epoch from `pck00011.tpc`. It is 0 at J2000.0 and
reaches 1000.9″ by 2049-12. Site −89°, 45°. The horizon is the test's linear ramp, slope 0.8°/°, through Earth's
median position.

**What the failure is.** The rigorous per-epoch bounds hold everywhere. The only excess, at J2000.0 itself where
ε = 0, is 9e-15 rad of rounding, inside the test's 1e-12 rad allowance. What fails is the fixed expectation, from
the Phase 3 plan, that the frozen-pole edge-clearance difference stays below 1e-5°.

| Period | ε max (″) | P1 max (°) | P2 max, slope 0.8 (°) | P2 max, flat (°) | P3 max |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2000–2009 | 196.2 | 5.1e-7 | 3.6e-6 | 5.1e-7 | 8.7e-7 |
| 2010–2019 | 397.3 | 1.2e-6 | 6.4e-6 | 1.2e-6 | 1.2e-6 |
| 2020–2025 | 518.1 | 1.3e-6 | 8.7e-6 | 1.3e-6 | 6.8e-7 |
| 2026–2036 | 739.4 | 2.0e-6 | **1.22e-5** | 2.0e-6 | 1.8e-6 |
| 2037–2049 | 1000.9 | 3.1e-6 | **1.82e-5** | 3.1e-6 | 2.2e-6 |

**Where and how much.**
- P2 first reaches 1e-5° at 2029-11-06 (ε = 598.5″) and does so at 27 of the 200 epochs. All 27 are on the
  sloped horizon; on a flat horizon P2 stays ≤ 3.1e-6°.
- The worst epoch is 2046-11-27: P2 = 1.82e-5°, against its bound of 2.76e-5° (ratio 0.66).
- At this site the Earth's elevation rate has a median of 1.3e-5 °/s (`earth_el_rate.log`). So 1.82e-5° is about
  1.4 s of Earth top or bottom edge timing, and 1.22e-5° (2026–2036) about 0.9 s. Both are comparable to the
  detector's 1 s event tolerance.

**Interpretation, for decision rather than as a conclusion.** The frozen J2000 pole's error grows with
precession, about 20″/yr, as stated in AUDIT. On sloped terrain this makes Earth edge clearances differ from the
IAU_EARTH pole by more than the 1e-5° the Phase 3 plan expected, from about 2029 onward. Whether to:
- tighten the model (an epoch-dependent pole), or
- revise the expectation with a derivation,

is a scientific decision. It was **not** made here; the test and tolerance are unchanged.

## Regression suites (full backend suite, 319 tests)
- **Sandbox kernels (`LUNAOPS_KERNEL_SOURCE=data/kernels_demo`, the set the golden files were recorded with):**
  307 passed, 12 skipped, exit 0. The skips are V-02e and the frozen-pole test (both need production kernels) and
  10 PGDA tests (terrain files absent). This matches the Phase 3 merge result.
- **Production kernels:** 306 passed, **1 failed** (the frozen-pole check above), 12 skipped, exit 1.
  - The skips are 10 PGDA tests (terrain absent) and 2 kernel-setup tests that only run with the sandbox set as
    the session source. Both of those passed in the sandbox run and in A1.
  - The Phase 2 golden tests pass with the production kernels too.

## Validation report
`report_production.json` is a copy of the live report written by `python -m validation.run_validation`. The live
file, `backend/validation/report.json`, is git-ignored. The report is in the current format, written by the
current code with `kernel_profile: production`.

**Contents:**
- 284 tests passed, 1 failed, 12 skipped, 9 not run.
- Not run: V-04, V-05, V-09 to V-13, U-04, U-06.
- `terrain_products` is empty, since no PGDA terrain is present.

**Effect on labels.** `pytest_exit_code` is 1, so `provenance.label_blockers` keeps **every quantity "Pending
validation"**. That would remain true even without the failure: V-04, V-05, V-09 to V-13, U-04 and U-06 are not
run, and no terrain is covered.

**V-14 in this report** is the in-suite short form (8 cases), not the month-long full form. The month-long run was
not repeated or merged here.

## Files
- `pytest_targeted_production.log`: V-01 to V-03, V-02e and the frozen-pole test, with their printed values.
- `v02ab_values.log`: V-02a/V-02b values.
- `pytest_full_sandbox.log`, `pytest_full_production.log`: the two full-suite runs.
- `run_validation.log`, `report_production.json`: the report run.
- `diagnostics.py`, `diagnostics.json`, `diagnostics.log`: read-only per-epoch V-02e and frozen-pole detail. The
  script repeats the tests' computations; it is not part of the suite.
- `frozen_pole_by_period.txt`: the period table above.
- `earth_el_rate.log`: Earth elevation rates at the test site.
- `kernels_lock.json`, `kernels_sha256_before_after.txt`: kernel provenance and integrity.
