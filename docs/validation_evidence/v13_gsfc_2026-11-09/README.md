# V-13 against the NASA GSFC lunar eclipse catalogue (Phase 4, A13), 2026-11-09

**Code:** `validation/v13_eclipse.py` at the content committed with this folder (base `60365f3`, algorithm 1.5.0).

**Run conditions:**
- Production kernels (A1; IB-2 resolved in A3).
- Python 3.13.18, SpiceyPy 8.3.0.
- Network access to `eclipse.gsfc.nasa.gov` approved for this run.

## What V-13 tests and its criterion (unchanged)
- **What it tests:** Earth occulting the Sun as seen from the lunar nearside during a catalogued lunar eclipse.
- **How:** the engine's adaptive event detector finds, at each site, when Earth's limb first and last touches the Sun's (`ecl_contact`, partial occultation) and when the Sun disappears and reappears behind Earth (`ecl_total`). Terrain is set at −30°, so only Earth matters.
- **Criterion** (blueprint Section 10.1, as written in the script since before Phase 4): **partial occultation lies inside [P1, P4] and any total occultation inside [U1, U4]**, with the existing 1 s slack. No threshold was added or changed.
- **Why containment:** P1/P4 and U1/U4 are when the *Moon's limb* touches the penumbra and umbra, so any single site's time in the penumbra or umbra lies within them.

## Reference: NASA GSFC (F. Espenak)
**Sources** (`gsfc/`, with `SHA256SUMS`):
- the 2021–2030 decade table (`LEdecade2021.html`);
- the per-eclipse figures `LE2025Mar14T.pdf`, `LE2025Sep07T.pdf`, `LE2026Mar03T.pdf` and `LE2026Aug28P.pdf` (`https://eclipse.gsfc.nasa.gov/LEplot/LEplot2001/`, dated 2009 Apr 29);
- the yearly text pages `OH2025.html` and `OH2026.html`.

**Transcription:**
- The figures give the contacts to the second but contain no extractable text (the times are drawn as graphics). The contacts were transcribed from the rendered figures into `backend/validation/reference/gsfc_lunar_eclipses_2025_2026.json`.
- **Checked twice:** every contact difference equals the duration printed in the same figure (one 1-second rounding difference, the 2025 Sep penumbral duration), and every contact rounds to the minute value on GSFC's independent text page.
- The script refuses to run on an inconsistent reference, and a test checks that it catches 3 s, 1 min and ordering errors.

**GSFC's method, as stated in each figure:**
- Earth's shadow is enlarged for the atmosphere (Danjon's rule, "CdT (Danjon)"); LUNA-OPS uses the solid Earth.
- The ephemeris is VSOP87/ELP2000-85 (LUNA-OPS: DE440).
- UT is derived from TD with a predicted ΔT (about 75 s; real ΔT is about 69 s).

**Time scale:**
- Each contact is converted to TD with that eclipse's own ΔT, taken from its greatest-eclipse TD and UT: 74.5, 74.8, 75.1 and 75.4 s.
- Converting GSFC's UT with today's leap-second UTC instead would misplace the contacts by about 6 s.
- The contacts carry ±0.5 s rounding.

| Eclipse | Type | P1 | U1 | U2 | U3 | U4 | P4 (UT, GSFC) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2025 Mar 14 | total | 03:57:24 | 05:09:33 | 06:25:59 | 07:31:23 | 08:47:48 | 10:00:01 |
| 2025 Sep 07 | total | 15:28:21 | 16:27:02 | 17:30:41 | 18:52:47 | 19:56:26 | 20:55:00 |
| 2026 Mar 03 | total | 08:44:22 | 09:50:00 | 11:04:26 | 12:02:45 | 13:17:10 | 14:22:59 |
| 2026 Aug 28 | partial | 01:23:55 | 02:33:48 | – | – | 05:51:55 | 07:01:41 |

## Result: V-13 passed (20 of 20)
- **Coverage:** 4 eclipses × 5 nearside sites: the centre (0°, 0°) used since the first version of the script, and (±45°, 0°), (0°, ±45°). The criterion must hold at every nearside point.
- **Robustness:** zero detector step-estimate failures.
- **Smallest margins:** 502.6 s (partial start after P1), 482.6 s (partial end before P4), 600.8 s (total start after U1), 516.7 s (total end before U4). All are far beyond the 1 s slack and the ±0.5 s reference rounding.

Times below are UTC (LUNA-OPS's leap-second UTC); margins are computed in TD.

| Eclipse | Site (lat, lon) | Partial occultation (UTC) | Total occultation (UTC) | start - P1 | P4 - end | total start - U1 | U4 - total end | Pass |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 2025-03-14 (total) | (+0, +0) | 04:29:56.9 – 09:24:44.0 | 05:44:36.1 – 08:10:08.6 | 1947.6 s | 2122.3 s | 2097.8 s | 2264.7 s | yes |
| 2025-03-14 (total) | (+45, +0) | 04:41:47.4 – 09:19:41.3 | 06:07:00.5 – 07:54:37.4 | 2658.1 s | 2425.0 s | 3442.2 s | 3195.9 s | yes |
| 2025-03-14 (total) | (-45, +0) | 04:23:02.0 – 09:26:38.8 | 05:33:20.6 – 08:16:20.2 | 1532.7 s | 2007.5 s | 1422.2 s | 1893.1 s | yes |
| 2025-03-14 (total) | (+0, +45) | 04:52:14.5 – 09:48:23.3 | 06:06:05.6 – 08:34:36.6 | 3285.1 s | 703.0 s | 3387.3 s | 796.7 s | yes |
| 2025-03-14 (total) | (+0, -45) | 04:08:52.7 – 09:01:39.7 | 05:24:23.7 – 07:46:13.5 | 683.4 s | 3506.7 s | 885.3 s | 3699.8 s | yes |
| 2025-09-07 (total) | (+0, +0) | 16:00:59.6 – 20:26:51.3 | 17:00:44.4 – 19:27:18.3 | 1953.0 s | 1694.4 s | 2016.8 s | 1753.3 s | yes |
| 2025-09-07 (total) | (+45, +0) | 15:54:57.0 – 20:26:23.4 | 16:52:24.4 – 19:29:03.2 | 1590.4 s | 1722.2 s | 1516.8 s | 1648.4 s | yes |
| 2025-09-07 (total) | (-45, +0) | 16:09:26.2 – 20:22:27.9 | 17:15:07.1 – 19:17:01.7 | 2459.5 s | 1957.7 s | 2879.5 s | 2369.9 s | yes |
| 2025-09-07 (total) | (+0, +45) | 16:20:26.0 – 20:47:03.0 | 17:19:43.8 – 19:47:54.9 | 3119.4 s | 482.6 s | 3156.2 s | 516.7 s | yes |
| 2025-09-07 (total) | (+0, -45) | 15:40:39.6 – 20:05:05.6 | 16:40:55.9 – 19:05:00.7 | 733.0 s | 3000.0 s | 828.3 s | 3090.9 s | yes |
| 2026-03-03 (total) | (+0, +0) | 09:13:57.0 – 13:48:11.9 | 10:21:59.4 – 12:39:53.8 | 1769.1 s | 2093.0 s | 1913.5 s | 2242.1 s | yes |
| 2026-03-03 (total) | (+45, +0) | 09:12:50.5 – 13:56:21.6 | 10:16:36.3 – 12:52:24.7 | 1702.6 s | 1603.4 s | 1590.4 s | 1491.2 s | yes |
| 2026-03-03 (total) | (-45, +0) | 09:20:33.7 – 13:37:33.0 | 10:39:08.7 – 12:18:38.2 | 2165.7 s | 2731.9 s | 2942.8 s | 3517.7 s | yes |
| 2026-03-03 (total) | (+0, +45) | 09:36:57.0 – 14:09:14.0 | 10:45:53.5 – 13:00:01.4 | 3149.1 s | 831.0 s | 3347.6 s | 1034.6 s | yes |
| 2026-03-03 (total) | (+0, -45) | 08:52:50.6 – 13:28:18.5 | 10:00:06.7 – 12:20:47.5 | 502.6 s | 3286.4 s | 600.8 s | 3388.4 s | yes |
| 2026-08-28 (partial) | (+0, +0) | 02:00:21.5 – 06:29:57.4 | 03:15:51.9 – 05:14:22.5 | 2180.3 s | 1909.8 s | 2517.6 s | 2258.7 s | yes |
| 2026-08-28 (partial) | (+45, +0) | 02:08:24.9 – 06:14:53.1 | 03:48:20.0 – 04:34:48.1 | 2663.7 s | 2814.1 s | 4465.8 s | 4633.1 s | yes |
| 2026-08-28 (partial) | (-45, +0) | 01:55:17.9 – 06:39:14.0 | 03:02:57.3 – 05:31:33.3 | 1876.7 s | 1353.3 s | 1743.1 s | 1227.9 s | yes |
| 2026-08-28 (partial) | (+0, +45) | 02:22:40.7 – 06:49:38.9 | 03:39:42.4 – 05:32:32.2 | 3519.5 s | 728.3 s | 3948.2 s | 1169.0 s | yes |
| 2026-08-28 (partial) | (+0, -45) | 01:36:51.9 – 06:08:36.2 | 02:50:55.5 – 04:54:29.0 | 770.6 s | 3191.0 s | 1021.3 s | 3452.2 s | yes |

**Informative only, not part of the criterion:** at every site of the three total eclipses, LUNA-OPS's total occultation begins before U2 and ends after U3 (all `info_*` values in `v13.json` are negative). That is as expected: every site is in the umbra while the whole Moon is.

## Validation report (`report/`)
- **Inputs:** `run_validation --merge v13.json --merge report/horizons_rerun.json` with the production kernels.
- **Why V-04/V-05 were re-run:** the new tests changed the suite fingerprint, so the A8/A9 result could no longer merge. The re-run gave the same V-04 and V-05 results; its raw responses were kept outside the repository and repeat the queries preserved in `../horizons_v04_v05_2026-11-09/`, differing only in Horizons' header timestamp. Their SHA-256s are in `horizons_rerun.json`.
- **Result:** pytest exit 0; 314 passed, 12 skipped, 6 not run (V-09, V-10, V-11, V-12, U-04, U-06); no merge rejected.
- **V-04, V-05 and V-13** are each recorded as passed.
- **Every label stays Pending validation** (U-04 and U-06 are required everywhere). `power_indicator` now lacks only V-09, V-11, U-04 and U-06.

## Tests (`tests/`)
- **Full backend suite, production kernels:** 333 passed, 12 skipped, exit 0.
- **Full backend suite, sandbox kernels:** 330 passed, 15 skipped, exit 0.
- **New:** `tests/test_phase4_v13.py`, 6 tests, passing with both kernel sets:
  - reference provenance and consistency;
  - the check catching transcription errors;
  - the GSFC-ΔT conversion;
  - the criterion holding at the nearside centre and failing once P1 moves 1.5 s past the detected start (passing at 0.5 s, inside the slack) or U4 moves before the end of totality, or when U1/U4 are missing;
  - the end-to-end run and merge;
  - refusal of an inconsistent reference.

## Unresolved methodology and data dependencies
1. **The criterion is containment, not timing agreement.** By design it cannot detect a small timing error: with margins of 8–60 minutes, an error of minutes would still pass. LUNA-OPS's eclipse event timing is tested more tightly by V-14 and the Phase 3 joint-visibility tests; V-13 checks consistency with the catalogue.
2. **Shadow model:** GSFC enlarges the shadow (Danjon), LUNA-OPS uses the solid Earth. Enlargement only widens GSFC's windows, so the containment criterion stays valid, but a site-level timing comparison against GSFC is not meaningful without modelling that enlargement.
3. **Ephemeris and ΔT:** GSFC's contacts use VSOP87/ELP2000-85 and a 2009 prediction of ΔT, which is why they are converted to TD with GSFC's own ΔT.
4. **Manual transcription:** the reference was read from rendered figures, not machine-extracted; the two consistency checks guard it. A machine-readable GSFC source with contacts to the second was not found (the text pages give minutes only).
5. **Coverage:** four 2025–2026 eclipses (three total, one partial) and five nearside sites; penumbral eclipses are not included.
