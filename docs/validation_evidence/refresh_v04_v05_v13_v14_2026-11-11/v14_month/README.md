# V-14 refresh: full month-long adaptive event detection against 1 s brute force, 2026-11-11

**Result: PASS.** This is the full form: one synodic month at the three standard sites, run with the production kernels and the production detector configuration.

| | Value |
| --- | --- |
| Criteria (`validation/v14_month.py`; parameters pinned by `tests/test_phase4_v14.py`) | ≥ 29.530589 days at the 3 standard sites. Every interior edge of every reference window ≥ 2 s must be matched by a detector event of the same function and direction within 3 s. Every match must lie within **1.0 s**. Every unmatched event must be confirmed at 0.02 s sampling (otherwise it is spurious). |
| Approval status | The existing V-14 criteria approved in A14; not changed or re-decided here |
| Required window edges | **955** |
| Missed / beyond 1.0 s / spurious | **0 / 0 / 0** |
| Worst offset | **0.500 s** (the detector's ±0.5 s bisection-midpoint limit) |
| Detector events | 955; all matched; none needed 0.02 s confirmation |
| Status written by the script | `passed` (full V-14) |

## Run (production configuration; no short or substitute run)
- **Command:** run from `backend/` with all defaults:
  `python -m validation.v14_month --out <this folder>/v14.json`
  - start 2026-11-14T00:00:00Z;
  - **29.530589 days**;
  - sites (−89.5°, 0°), (−88.0°, 120°) and (−86.5°, 250°).
- **Time:** 2026-11-11 16:27:30 to 16:34:12 UTC (**402 s**), exit 0.
  - It ran on its own, after V-04/V-05 and V-13 had finished.
  - The log is in `v14_month.log`, which holds the per-site JSON lines and the final verdict.
- **Software:**
  - code `5bf9753f…37d2f8`, suite `1632af16…6d75eabc`, algorithm **1.5.0** (recorded in `v14.json` → `algorithm_version`);
  - Python 3.13.7 (Windows 11 x64), SpiceyPy 8.3.0 (CSPICE N0067), NumPy 2.5.4.
- **Kernels:**
  - **profile:** production;
  - **verification:** checked against the lock file and NAIF checksums before the run (`../00_preflight/verify_kernels.log`);
  - **record:** their SHA-256s are in `v14.json` → `meta.kernels`.
- **Detector configuration:** the production `EventConfig()` defaults: 600 s step cap, 1 s floor, 1.0 s bisection tolerance and the production curvature inflation.

**On "real production data":**
- **Real production inputs:** the kernels and the detector.
- **Synthetic horizon, by design:** each site uses the **synthetic** V-14 horizon from `lunaops.testing.v14_horizon` (an oscillating horizon the Sun and Earth cross often).
  - This is the V-14 method as defined and approved in A14, not a substitute. V-14 tests *when the detector places window edges*, not terrain.
  - Terrain is validated by V-06/V-07 and V-09 to V-12.
- **No short or reduced run:** none was used in place of the month run.

## Measurements

| Site | Required edges | Missed | Beyond 1.0 s | Spurious | Worst offset (s) | Adaptive samples | Estimate failures | Detector (s) | Brute force (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| −89.5°, 0° | 661 | 0 | 0 | 0 | 0.500 | 32,621 | 11 | 28.3 | 84.6 |
| −88.0°, 120° | 183 | 0 | 0 | 0 | 0.500 | 15,424 | 11 | 13.7 | 86.1 |
| −86.5°, 250° | 111 | 0 | 0 | 0 | 0.500 | 11,852 | 11 | 11.0 | 175.0 |
| **Total** | **955** | **0** | **0** | **0** | **0.500** | 59,897 | 33 | | |

**Per function, summed over the three sites:**

| Function | Required edges | Worst offset (s) |
| --- | ---: | ---: |
| Sun centre | 392 | 0.500 |
| Sun top | 328 | 0.4998 |
| Sun bottom | 214 | 0.4999 |
| Earth centre | 6 | 0.3009 |
| Earth top | 9 | 0.4932 |
| Earth bottom | 6 | 0.4223 |

**Where the raw values are:** `v14.json` → `sites[*].functions` has the reference crossings, required edges, detector events, missed, worst offset, over-tolerance, confirmed and spurious counts per function.

**Estimate failures (not a V-14 criterion):**
- The detector logged 33 step-estimate failures, 11 per site, the same count as A14.
- A14 attributed them all to `ecl_contact` (no eclipse in this month), and the designed step-halving safeguard handled them.
- This refresh did not re-extract the per-failure list. `v14_month.py` records only the count.

## Comparison with the stale A14 evidence (`../../v14_month_a14_2026-11-10/`)
**Why the old evidence is stale:** A14's `v14.json` was produced with code `230071e0…` and suite `060a1916…`, which differ from the current build.
- The live report's V-14 "passed" comes only from the automated pytest form ("8 case(s)"); the month run no longer merges.

**What the refresh shows:**
- **Counts and offsets:** every per-function count and every worst offset is **identical** to A14.
- **Adaptive samples and estimate-failure counts:** also identical.
- **Wall-clock timings:** they differ, because of a different machine and OS.

## Limitations (unchanged from A14)
- **Detection, not models:** the brute-force reference evaluates the same disk models as the engine.
- **Synthetic horizon:** see above.
- **Offset resolution:** bounded by the 1 s bisection bracket.
- **Short windows:** windows shorter than 2 s are not required.
- **One month:** only the month starting 2026-11-14 is covered.
