# V-04 refresh: apparent Sun and Earth direction compared with JPL Horizons, 2026-11-11

**Result: PASS.** The criterion is unchanged and was not set by this refresh.

| | Value |
| --- | --- |
| Criterion (`validation/horizons_compare.py`, `V04_TOL_DEG`) | max abs(dAz cos El) <= 0.01° **and** max abs(dEl) <= 0.01° |
| Measured max abs(dAz cos El) | **5.235e-07°** (1.9 mas) |
| Measured max abs(dEl) | **5.226e-07°** (1.9 mas) |
| Epochs compared | 7,931 (11 site/body series × 721 hourly epochs) |
| Status written by the script | `passed` |
| Approval status of the criterion | Existing V-04 criterion, in force since A8; not changed or re-decided here |

## Run
- **Command:** run from `backend/`:
  `python -m validation.horizons_compare --out <this folder>/horizons.json --raw-dir <this folder>/horizons_raw`
  - The script ran unmodified with its default window and sites; no option changed a criterion.
- **Time:** 2026-11-11 16:24:20 to 16:26:37 UTC (137 s), exit 0. The log is in `horizons_compare.log`.
- **Software:**
  - code fingerprint `5bf9753f…37d2f8` and suite fingerprint `1632af16…6d75eabc`;
  - algorithm 1.5.0;
  - Python 3.13.7 (Windows 11, x64), SpiceyPy 8.3.0 (CSPICE N0067), NumPy 2.5.4;
  - the full environment is in `../00_preflight/`.
- **Kernels:** production profile (DE440s, `moon_pa_de440_200625.bpc`, `moon_de440_250416.tf`, `naif0012.tls`, `pck00011.tpc`, plus the DE421 PCK/FK).
  - They were checked against the lock file and NAIF checksums immediately before the run (`../00_preflight/verify_kernels.log`).
  - Their SHA-256s are listed in `horizons.json` → `meta.kernels`.
- **Terrain acceptance digest** at run time: `e48eb8ed…943dce`. V-04 does not use terrain; the digest is recorded only so the metadata is complete.

## Reference: JPL Horizons API (official)
- **Endpoint:** `https://ssd.jpl.nasa.gov/api/horizons.api`, signature `{"source": "NASA/JPL Horizons API", "version": "1.2"}`.
- **Query:** observer table, `CENTER='coord@301'`, `COORD_TYPE='GEODETIC'`, altitude 0 km, `QUANTITIES='4'` (apparent azimuth/elevation), `APPARENT='AIRLESS'`, `TIME_TYPE='TT'`, `ANG_FORMAT='DEG'`, `EXTRA_PREC='YES'`, `STEP_SIZE='1h'`.
- **Responses:** all 47 (11 hourly V-04 tables and 36 V-05 refinement tables) are saved verbatim in `horizons_raw/`. `horizons.json` → `horizons_responses` lists each one's SHA-256, size and full query. `../SHA256SUMS` covers every file in this refresh.

**Header facts**, read from every response (`horizons.json` → `horizons_header_facts`):

| Fact | Horizons | LUNA-OPS |
| --- | --- | --- |
| Ephemeris (DE version) | **DE441** | **DE440** (`de440s.bsp`) |
| Lunar body-fixed frame | `MEAN_ME (high precision)` | `MOON_ME_DE440_ME421` |
| Lunar radii | 1737.4 km sphere (checked by the script: VT-2 needs no height conversion) | 1737.4 km sphere |
| Refraction | `NO (AIRLESS)` | none |
| Time tags | TT | ET/TDB internally (converted with SPICE) |
| Light bending | applied (Sun, Earth; DE441) | not applied (`CN+S` only) |

## Sites, coordinates and dates
- **Window:** 2026-11-14 00:00 TT to 2026-12-14 00:00 TT, hourly.
- **Sites:** blueprint Section 10.3, all at height 0 km on the 1737.4 km sphere, with planetodetic latitude and east longitude.

| Site | Lat (°) | Lon E (°) | Bodies |
| --- | ---: | ---: | --- |
| south-polar A | −89.5 | 0 | Sun, Earth |
| south-polar B | −86.0 | 210 | Sun, Earth |
| north-polar | 87.0 | 30 | Sun, Earth |
| nearside equatorial | 0.0 | 0 | Sun, Earth |
| limb | 0.0 | 90 | Sun, Earth |
| farside | 0.0 | 180 | Sun only (Earth never visible) |

## Measured differences (LUNA-OPS − Horizons)

| Site | Body | Epochs | max abs(dAz cos El) (°) | max abs(dEl) (°) |
| --- | --- | ---: | ---: | ---: |
| south-polar A | Sun | 721 | 2.094e-08 | 3.431e-08 |
| south-polar A | Earth | 721 | 5.226e-07 | 4.927e-08 |
| south-polar B | Sun | 721 | 1.993e-08 | 3.482e-08 |
| south-polar B | Earth | 721 | 5.235e-07 | 5.984e-08 |
| north-polar | Sun | 721 | 1.869e-08 | 3.100e-08 |
| north-polar | Earth | 721 | 5.228e-07 | 5.479e-08 |
| nearside equatorial | Sun | 721 | 2.947e-08 | 3.196e-08 |
| nearside equatorial | Earth | 721 | 3.978e-07 | 4.156e-07 |
| limb | Sun | 721 | 3.268e-08 | 2.002e-08 |
| limb | Earth | 721 | 5.062e-08 | 5.226e-07 |
| farside | Sun | 721 | 2.960e-08 | 3.212e-08 |

**Raw measurements:**
- Every epoch is in `horizons_v04_residuals.csv`, with the site, target, TT tag, ET, Horizons az/el, LUNA-OPS az/el, dAz·cos El and dEl.
- Per-series maxima are in `horizons.json` → `v04.runs`.

## Comparison with the stale A8/A9 evidence (`../../horizons_v04_v05_2026-11-09/`)
**Why the old evidence is stale:** it was produced with code fingerprint `230071e0…` and suite fingerprint `dd2304cd…`. Both differ from the current build, so the live `report.json` lists V-04 as "not run".

**What the refresh shows:**
- **Same comparison:** both runs cover the same 7,931 (site, body, epoch) keys, and the 47 queries are identical.
- **LUNA-OPS side:** az/el changed by at most 1.4e-13° from the A8/A9 values, which is floating-point noise between Linux and Windows builds.
- **Horizons side:** the hourly V-04 values are identical.
- **Every raw response differs in its header timestamp.** In 41 of the 47 there is more:
  - **Earth tables (21):** JPL's EOP file is now `eop.261110.p270205`; it was `eop.261106.p270202` on 2026-11-09.
  - **V-05 refinement tables (36):** the `RTS-only print` header line is gone, and some 1-minute and 1-second values differ in the 9th decimal (1e-9°).
- The V-04 maxima are the same to the printed precision.

## Interpretation and limitations (unchanged from A8)
- **Sun:** it agrees to about 3e-8°.
- **Earth:** the 5.2e-7° residual is the same at every site, so it is systematic.
  - Likely sources are DE440 vs DE441 and Horizons' gravitational light bending (not applied by `CN+S`).
  - It is not decomposed further.
- **Coverage:** one 30-day window and six sites, with no terrain and centre directions only.
