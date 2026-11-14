# V-14 full form: one synodic month with the production kernels (Phase 4, A14), 2026-11-10

**Result: V-14 passed** in its full form with the production kernels and algorithm 1.5.0. It is merged into the production validation report through the code, test-suite and kernel guard.

**What V-14 validates:** the adaptive event detector, which places window edges of the Sun and Earth disks against a horizon, compared with a 1 s brute-force reference.
- Terrain is not under test: each site uses the synthetic V-14 horizon (`lunaops.testing.v14_horizon`), which the Sun and Earth cross often.
- So V-14 does **not** depend on A5/A6 or any terrain product. It needs only the production kernels, installed and verified in A1.

## Criteria (unchanged; `validation/v14_month.py`, README "V-14 (full form)")
- **Coverage:** at least one synodic month (29.530589 days) at the three standard sites: (−89.5°, 0°), (−88.0°, 120°), (−86.5°, 250°).
- **Functions:** the Sun and Earth centre, top-edge and bottom-edge clearances, sampled every 1 s as one continuous series across the daily chunks. Crossings are placed by linear interpolation.
- **Required edges:** every interior edge of every reference window lasting ≥ 2 s must have a detector event of the same function and direction within 3 s; otherwise it is *missed*.
- **Timing:** every matched event must lie within **1.0 s** of its reference crossing (`EVENT_TOL_S`, the project's event-timing tolerance).
- **No spurious events:** every unmatched detector event must be confirmed by evaluating its function every 0.02 s within 1.5 s; otherwise it is *spurious*.
- **Status:** a shorter or fewer-site run is never a pass ("not run"); any miss, offset beyond tolerance or spurious event fails the run.

## Run (`v14_month.log`, `v14.json`)
- **Command and inputs:** `python -m validation.v14_month --out v14.json`, 2026-11-10 06:00:57 to 06:07:43 UTC (406 s).
- **Code:** base `85ee5d8` with this change; algorithm 1.5.0.
- **Kernels:** production profile, verified with `python -m lunaops.acquire verify-kernels` before the run.
- **Window:** start 2026-11-14T00:00:00Z, 29.530589 days.

| Site | Required edges | Missed | Beyond 1.0 s | Spurious | Worst offset (s) | Adaptive samples | Detector (s) | Brute force (s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| −89.5°, 0° | 661 | 0 | 0 | 0 | 0.500 | 32,621 | 34.8 | 108.6 |
| −88.0°, 120° | 183 | 0 | 0 | 0 | 0.500 | 15,424 | 17.3 | 116.8 |
| −86.5°, 250° | 111 | 0 | 0 | 0 | 0.500 | 11,852 | 14.3 | 111.9 |
| **Total** | **955** | **0** | **0** | **0** | **0.500** | | | |

**Per function, summed over the three sites:**

| Function | Required edges | Worst offset (s) |
| --- | --- | --- |
| Sun centre | 392 | 0.500 |
| Sun top | 328 | 0.4998 |
| Sun bottom | 214 | 0.4999 |
| Earth centre | 6 | 0.3009 |
| Earth top | 9 | 0.4932 |
| Earth bottom | 6 | 0.4223 |

- **Detector events:** 955 in all, every one matched; none needed the 0.02 s confirmation.
- **Earth crossings are few:** 21 in total, because Earth's elevation at polar sites changes only with libration. The pytest form of V-14 and `test_phase3_earth_rates` add per-limb Earth event-timing tests.
- **Unchanged from the sandbox run:** the edge counts per site (661, 183, 111) equal those of the 2026-11-07 run (`../v14_month_sandbox.json`, sandbox kernels, a pre-Phase 3 build before algorithm 1.4.0). That run is superseded by this one.

## Runtime estimate failures (`estimate_failures.txt`; not a V-14 criterion)
The detector's step control logged **33 estimate failures, 11 per site, all on `ecl_contact`**. That function is the Sun–Earth limb contact, used for eclipses, and is not one of the six scored functions.
- **When:** between 2026-11-27 and 2026-11-29.
- **Size:** in each, the observed change over a step reached its predicted bound, with observed/predicted between 1.0000098 and 1.0067873 (at most 0.68% over).
- **Handling:** the step was halved, which is the designed safeguard.
- **Effect:** no eclipse falls in this month, and no `ecl_contact` event was expected or missed.
- **Earlier runs:** the sandbox build logged the same count (11 per site, `ecl_contact`) at one epoch. The Phase 3 joint-visibility and V-13 eclipse tests cover eclipse events directly.

## Production validation report (`report/`)
The report's merge guard binds each external result to the current code and test-suite fingerprints. So V-13 and V-04/V-05 were re-run with the same code, as in A13, and merged with V-14:
- `report/v13.json`: V-13 passed, 4 GSFC eclipses × 5 nearside sites, 20/20.
- `report/horizons.json`: V-04 passed (maximum |ΔAz cos El| 5.235e-7°, |ΔEl| 5.226e-7°, tolerance 0.01°, 7931 epochs). V-05 passed (18 centre crossings, 0 missed, 0 spurious, worst 0.500 s against 1.0 s). The raw Horizons responses are kept outside the repository.
- `report/run_validation.log`, `report/report_production.json`: pytest exit 0 (369 passed, 12 skipped, production kernels), no merge rejected. 20 of the 26 blueprint IDs passed, including V-02e, V-04, V-05, V-13 and V-14. V-14 is passed both as the merged month run and in the automated pytest form. V-09, V-10, V-11, V-12, U-04 and U-06 are not run, so every label stays "Pending validation".

## Regression tests (`backend/tests/test_phase4_v14.py`, 14 tests)
- **The approved parameters are pinned:** 29.530589 days, the three standard sites, the six edge functions, 1.0 s tolerance (equal to `settings.EVENT_TOL_S`), 3 s matching, 2 s minimum window.
- **The status rule** (`v14_month.summarize`, factored out of `main` without changing it), 8 cases:
  - full and clean passes;
  - 29.5305 days, 2 sites, or 1 day at 1 site is "not run";
  - any miss, offset beyond tolerance or spurious event fails, even in a partial run.
- **The worst offset** ignores functions without events.
- **Short real runs:**
  - 6 hours at one site is clean and reported as a partial run, and it merges through the guard.
  - The checker catches a dropped Sun-centre event (missed), one moved by 2 s (beyond tolerance) and an invented one (spurious). Each fails V-14.

**Suite results** (base `85ee5d8` plus this change):
- `test_phase4_v14`: **14 passed** (`tests/test_phase4_v14.log`).
- Full backend suite, production kernels: **369 passed, 12 skipped**, exit 0 (inside `report/run_validation.log`).
- Full backend suite, sandbox kernels (`LUNAOPS_KERNEL_SOURCE=data/kernels_demo`): **366 passed, 15 skipped**, exit 0 (`tests/suite_sandbox.log`).
- No failures. The single warning is the existing Starlette TestClient deprecation.

## Limitations
- **Detection, not the models.** The brute-force reference evaluates the same disk models as the engine:
  - Sun: the exact spherical cap at every second;
  - Earth: the exact oblate limb wherever a crossing is possible, interpolated only where the sign provably cannot change.
  - V-14 therefore validates *when* the detector places edges for a given model. Model accuracy is V-03, V-04, V-05, V-08 and V-13.
- **Synthetic horizon.** The real-terrain behaviour of the horizon is V-06, V-07 and V-09 to V-12, not V-14.
- **Offset resolution.** Offsets are bounded by the detector's 1 s bisection bracket (worst 0.500 s), within the 1.0 s tolerance.
- **Short windows.** Windows shorter than 2 s are not required; windows below the 1 s step floor are not guaranteed (README).
- **One month only.** It is the required synodic month from 2026-11-14; other months are not covered by this evidence.
- **Labels stay Pending.** Every label stays "Pending validation": V-09 to V-12, U-04 and U-06 have not passed.
