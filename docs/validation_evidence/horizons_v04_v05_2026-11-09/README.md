# V-04 and V-05 against JPL Horizons (Phase 4, A8 + A9), 2026-11-09

**Code:** `validation/horizons_compare.py` at the content committed with this folder (base `2a0f0b9`, algorithm 1.5.0).

**Run conditions:**
- Production kernels as installed in A1 (`../kernels_production_2026-11-08/`); IB-2 resolved (`../ib2_2026-11-09/`).
- Python 3.13.18, SpiceyPy 8.3.0 (CSPICE N0067).
- Network access to `ssd.jpl.nasa.gov` approved for this run.

## Reference: JPL Horizons API
- **Source:** `https://ssd.jpl.nasa.gov/api/horizons.api`, signature `{"version": "1.2", "source": "NASA/JPL Horizons API"}`.
- **Responses:** all 47 are saved verbatim in `horizons_raw/`. Their SHA-256, size and query parameters are listed under `horizons_responses` in `horizons.json` (SHA-256 of `horizons.json`: `b79afc51…d38b`).
- **Query:** observer table, `CENTER='coord@301'`, `COORD_TYPE='GEODETIC'`, altitude 0 km, quantity 4 (apparent azimuth and elevation), `APPARENT='AIRLESS'`, `TIME_TYPE='TT'`, `ANG_FORMAT='DEG'`, `EXTRA_PREC='YES'`.
- **Header facts** (identical in every response):

  | Fact | Horizons | LUNA-OPS |
  | --- | --- | --- |
  | Ephemeris | DE441 | DE440 |
  | Lunar frame | `MEAN_ME (high precision)` | `MOON_ME_DE440_ME421` |
  | Lunar radii | 1737.4 km sphere (so altitude 0 km is the same height in both; VT-2 needs no conversion, and the script checks this) | 1737.4 km sphere |
  | Refraction | none (airless) | none |
  | Time tags | TT | TDB internally |
  | Light bending | applied (Sun, Earth) | not applied (`CN+S` only; milliarcsecond-level) |

## Window and sites
- **Window:** 2026-11-14 00:00 to 2026-12-14 00:00 TT, hourly (721 epochs per site and body; 7,931 in all).
- **Sites, Section 10.3,** all at altitude 0: south-polar A (89.5 S, 0 E), south-polar B (86 S, 210 E), north-polar (87 N, 30 E), nearside equatorial (0, 0), limb (0, 90 E), farside (0, 180 E; Sun only).

## V-04: epoch-by-epoch direction
**Criterion:** max |dAz cos El| <= 0.01° and max |dEl| <= 0.01°. **Result: passed.**
- Overall max |dAz cos El| = 5.235e-07° and max |dEl| = 5.226e-07°, i.e. 1.9 milliarcseconds. That is about 19,000 times below the tolerance.
- Every epoch's residual is in `horizons_v04_residuals.csv`.

| Site | Body | Epochs | max abs(dAz cos El) | max abs(dEl) |
| --- | --- | ---: | ---: | ---: |
| south-polar A | sun | 721 | 2.09e-08° | 3.43e-08° |
| south-polar A | earth | 721 | 5.23e-07° | 4.93e-08° |
| south-polar B | sun | 721 | 1.99e-08° | 3.48e-08° |
| south-polar B | earth | 721 | 5.23e-07° | 5.98e-08° |
| north-polar | sun | 721 | 1.87e-08° | 3.10e-08° |
| north-polar | earth | 721 | 5.23e-07° | 5.48e-08° |
| nearside equatorial | sun | 721 | 2.95e-08° | 3.20e-08° |
| nearside equatorial | earth | 721 | 3.98e-07° | 4.16e-07° |
| limb | sun | 721 | 3.27e-08° | 2.00e-08° |
| limb | earth | 721 | 5.06e-08° | 5.23e-07° |
| farside | sun | 721 | 2.96e-08° | 3.21e-08° |

**Interpretation:**
- The Sun agrees to about 3e-8° (0.1 mas).
- The Earth residual reaches about 5.2e-7°, at the same size at every site, so it is a systematic difference in Earth's apparent direction, not a site effect.
- Its likely sources are the DE440/DE441 difference and Horizons' gravitational light bending, which `CN+S` omits. This was not decomposed further.

## V-05: event timing (its own measurement and status)
**Method:**
- **Reference (Horizons only):** times at which the Sun's and Earth's centres cross an ideal flat 0° horizon. Each sign change of the hourly Horizons elevation is refined with a 1-minute Horizons table over that hour, then a 1-second table over that minute, and interpolated linearly between the two bracketing 1-second samples.
- **LUNA-OPS:** the engine's adaptive event detector (`EventDetector`, functions `sun_c`/`earth_c`) on the same flat horizon and window.
- **Matching:** same body and direction within 600 s. Detector events with no reference crossing are re-checked against Horizons at 1-minute steps over ±30 minutes.

**Criterion:** at least one crossing, no missed or spurious event, and every |t_LUNA - t_Horizons| <= 1.0 s. The 1.0 s threshold is the project's existing event-timing tolerance (`EVENT_TOL_S`, used by V-14 and the Phase 2 golden test). **The blueprint's own V-05 criterion text was not available, so this threshold needs the reviewer's confirmation.**

**Result: passed.** 18 crossings matched, 0 missed, 0 spurious; max |dt| = 0.49995 s.

| Site | Body | Event | Horizons crossing (UTC) | t_LUNA - t_Horizons |
| --- | --- | --- | --- | ---: |
| south-polar A | earth | rise | 2026-11-17T08:05:50.798 | -0.100 s |
| south-polar A | earth | set | 2026-11-30T06:58:22.895 | -0.053 s |
| south-polar B | sun | set | 2026-11-16T10:01:31.984 | +0.500 s |
| south-polar B | sun | rise | 2026-11-27T13:17:29.463 | +0.448 s |
| south-polar B | earth | rise | 2026-11-20T00:17:07.595 | +0.106 s |
| south-polar B | earth | set | 2026-11-27T15:54:06.267 | +0.330 s |
| north-polar | sun | rise | 2026-11-17T02:29:16.343 | +0.447 s |
| north-polar | sun | set | 2026-11-26T21:14:36.289 | +0.451 s |
| north-polar | earth | set | 2026-11-19T00:54:25.097 | -0.109 s |
| north-polar | earth | rise | 2026-11-28T14:53:56.409 | +0.305 s |
| nearside equatorial | sun | rise | 2026-11-17T00:09:13.006 | +0.499 s |
| nearside equatorial | sun | set | 2026-12-01T19:51:31.290 | +0.493 s |
| limb | sun | set | 2026-11-24T09:58:20.425 | +0.348 s |
| limb | sun | rise | 2026-12-09T05:09:42.389 | +0.495 s |
| limb | earth | rise | 2026-11-26T00:30:52.948 | +0.142 s |
| limb | earth | set | 2026-12-10T14:35:10.206 | +0.228 s |
| farside | sun | set | 2026-11-17T00:09:03.446 | +0.220 s |
| farside | sun | rise | 2026-12-01T19:51:40.882 | +0.483 s |

**Interpretation:**
- The geometric residuals above correspond to sub-millisecond timing.
- The differences are set by the detector's own resolution. It bisects each event to a bracket of at most `EVENT_TOL_S` = 1.0 s and reports the bracket's midpoint, so its error is at most 0.5 s. The largest difference, 0.49995 s, is exactly that limit.
- V-05 does not reuse V-04's verdict: `tests/test_phase4_horizons.py` shows an elevation bias that passes V-04 making V-05 fail.

## Validation report (`report_production.json`, merged with `horizons.json`)
- `python -m validation.run_validation --merge horizons.json` with the production kernels.
- **Result:** pytest exit 0; 307 passed, 12 skipped, 7 not run; no merge rejected.
- **V-04 and V-05** are separate external entries (`script: horizons_compare`), both passed.
- **Still not run:** V-09, V-10, V-11, V-12, V-13, U-04, U-06.
- **Labels:** every quantity stays **Pending validation**. `sun_earth_azel` is now blocked only by U-04 and U-06; `events` also needs V-09 to V-12.

## Test results (`tests/`)
- **Full backend suite, production kernels:** 327 passed, 12 skipped, exit 0. The skips are 10 tests that need the PGDA terrain and 2 sandbox-only tests.
- **Full backend suite, sandbox kernels:** 324 passed, 15 skipped, exit 0. The skips are 10 PGDA, V-02e, 2 IAU_EARTH checks and 2 production-only frame tests.
- **New:** `tests/test_phase4_horizons.py`, 8 tests, which pass with both kernel sets.

## Limitations
- **Single window:** one 30-day window (November–December 2026) and six sites.
- **Centre only:** V-05 tests centre crossings of a flat 0° horizon. Limb events and real terrain are covered by V-14 and the horizon validations, not by Horizons.
- **Ephemeris and light bending:** Horizons uses DE441 and applies light bending; LUNA-OPS uses DE440 and `CN+S`.
- **Crossing detection:** a crossing pair inside one hour that the hourly scan misses could only be found through a detector event; none was seen.
