# V-13 refresh: eclipse contacts compared with the NASA GSFC lunar eclipse catalogue, 2026-11-11

**Result: PASS (20 of 20)** under the existing V-13 criterion; no criterion was changed.

| | Value |
| --- | --- |
| Criterion (`validation/v13_eclipse.py`, blueprint Section 10.1) | at each site, LUNA-OPS's partial occultation of the Sun by Earth lies inside GSFC [P1, P4], and any total occultation inside [U1, U4], with 1 s slack (`SLACK_S`) |
| Approval status | the existing V-13 criterion, in force since A13; not changed or re-decided here |
| Coverage | 4 GSFC eclipses (3 total, 1 partial) × 5 nearside sites |
| Smallest margins | 502.6 s (partial start after P1), 482.6 s (partial end before P4), 600.8 s (total start after U1), 516.7 s (total end before U4) |
| Detector step-estimate failures (`ecl_*`) | 0 |
| Status written by the script | `passed` |

## Run
- **Command:** run from `backend/`:
  `python -m validation.v13_eclipse --reference validation/reference/gsfc_lunar_eclipses_2025_2026.json --out <this folder>/v13.json`
- **Time:** 2026-11-11 16:27:03 to 16:27:15 UTC (12 s), exit 0. The log is in `v13_eclipse.log`.
- **Software and kernels:** same as V-04 (code `5bf9753f…`, suite `1632af16…`, algorithm 1.5.0, production kernels verified before the run; `../00_preflight/`). The kernel SHA-256s are in `v13.json` → `meta`.
- **Detector setup:**
  - the engine's adaptive `EventDetector` with functions `ecl_contact` (Earth's limb touches the Sun's limb) and `ecl_total` (Sun fully hidden);
  - terrain is set to −30° so only Earth occults;
  - each search runs from P1 − 2 h to P4 + 2 h.

## Official reference: NASA GSFC Eclipse Web Site (F. Espenak)
- **Transcribed reference:** `backend/validation/reference/gsfc_lunar_eclipses_2025_2026.json`, SHA-256 `721e7115…a674b`.
  - It is unchanged since A13 and was not edited by this refresh.
  - The script re-checks it before running: the contact differences must equal the durations GSFC states, the contacts must round to the minutes on GSFC's text pages, and they must be in order.

**Sources re-fetched on 2026-11-11 16:24:47 UTC** (`gsfc_refetch/`, with `fetch.log` and `SHA256SUMS`):
- **Figures:** `https://eclipse.gsfc.nasa.gov/LEplot/LEplot2001/LE2025Mar14T.pdf`, `LE2025Sep07T.pdf`, `LE2026Mar03T.pdf` and `LE2026Aug28P.pdf`.
- **Decade table:** `https://eclipse.gsfc.nasa.gov/LEdecade/LEdecade2021.html`.
- **Yearly text pages:** `https://eclipse.gsfc.nasa.gov/OH/OH2025.html` and `OH2026.html`.
- **Result:** all seven are **byte-identical** to the copies preserved in A13 (`../../v13_gsfc_2026-11-09/gsfc/`). The four figure hashes also equal the `figure_sha256` values in the reference JSON. The reference is therefore current.

**GSFC's method, as stated in the figures:**
- the shadow is enlarged by Danjon's rule;
- the ephemeris is VSOP87/ELP2000-85;
- UT comes from TD with a predicted ΔT of about 75 s.

**Time scale:** each contact is converted to TD with that eclipse's own ΔT (74.5, 74.8, 75.1 and 75.4 s).

| Eclipse | Type | P1 | U1 | U2 | U3 | U4 | P4 (UT, GSFC) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2025 Mar 14 | total | 03:57:24 | 05:09:33 | 06:25:59 | 07:31:23 | 08:47:48 | 10:00:01 |
| 2025 Sep 07 | total | 15:28:21 | 16:27:02 | 17:30:41 | 18:52:47 | 19:56:26 | 20:55:00 |
| 2026 Mar 03 | total | 08:44:22 | 09:50:00 | 11:04:26 | 12:02:45 | 13:17:10 | 14:22:59 |
| 2026 Aug 28 | partial | 01:23:55 | 02:33:48 | – | – | 05:51:55 | 07:01:41 |

## Event times and contact differences
**How to read the table:**
- **Event times:** LUNA-OPS UTC (leap-second UTC, rounded to 0.1 s).
- **Contact differences:** computed in TD, in seconds.
  - Positive margins mean the LUNA-OPS event lies inside the GSFC interval.
  - "U2 diff" is total start − U2 and "U3 diff" is U3 − total end. Both are informative only and not part of the criterion; the negative values mean every site is in the umbra while the whole Moon is.
- **Site:** latitude and longitude in degrees, height 0.
- **Est. fail.:** detector step-estimate failures.

| Eclipse | Site | ΔT (s) | Partial occultation (UTC) | Total occultation (UTC) | start − P1 | P4 − end | total start − U1 | U4 − total end | U2 diff | U3 diff | Result | Est. fail. |
| --- | --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| 2025-03-14 (total) | +0, +0 | 74.5 | 04:29:56.9 to 09:24:44.0 | 05:44:36.1 to 08:10:08.6 | 1947.6 | 2122.3 | 2097.8 | 2264.7 | −2488.2 | −2320.3 | PASS | 0 |
| 2025-03-14 (total) | +45, +0 | 74.5 | 04:41:47.4 to 09:19:41.3 | 06:07:00.5 to 07:54:37.4 | 2658.1 | 2425.0 | 3442.2 | 3195.9 | −1143.8 | −1389.1 | PASS | 0 |
| 2025-03-14 (total) | −45, +0 | 74.5 | 04:23:02.0 to 09:26:38.8 | 05:33:20.6 to 08:16:20.2 | 1532.7 | 2007.5 | 1422.2 | 1893.1 | −3163.8 | −2691.9 | PASS | 0 |
| 2025-03-14 (total) | +0, +45 | 74.5 | 04:52:14.5 to 09:48:23.3 | 06:06:05.6 to 08:34:36.6 | 3285.1 | 703.0 | 3387.3 | 796.7 | −1198.7 | −3788.3 | PASS | 0 |
| 2025-03-14 (total) | +0, −45 | 74.5 | 04:08:52.7 to 09:01:39.7 | 05:24:23.7 to 07:46:13.5 | 683.4 | 3506.7 | 885.3 | 3699.8 | −3700.7 | −885.2 | PASS | 0 |
| 2025-09-07 (total) | +0, +0 | 74.8 | 16:00:59.6 to 20:26:51.3 | 17:00:44.4 to 19:27:18.3 | 1953.0 | 1694.4 | 2016.8 | 1753.3 | −1802.2 | −2065.7 | PASS | 0 |
| 2025-09-07 (total) | +45, +0 | 74.8 | 15:54:57.0 to 20:26:23.4 | 16:52:24.4 to 19:29:03.2 | 1590.4 | 1722.2 | 1516.8 | 1648.4 | −2302.2 | −2170.6 | PASS | 0 |
| 2025-09-07 (total) | −45, +0 | 74.8 | 16:09:26.2 to 20:22:27.9 | 17:15:07.1 to 19:17:01.7 | 2459.5 | 1957.7 | 2879.5 | 2369.9 | −939.5 | −1449.1 | PASS | 0 |
| 2025-09-07 (total) | +0, +45 | 74.8 | 16:20:26.0 to 20:47:03.0 | 17:19:43.8 to 19:47:54.9 | 3119.4 | 482.6 | 3156.2 | 516.7 | −662.8 | −3302.3 | PASS | 0 |
| 2025-09-07 (total) | +0, −45 | 74.8 | 15:40:39.6 to 20:05:05.6 | 16:40:55.9 to 19:05:00.7 | 733.0 | 3000.0 | 828.3 | 3090.9 | −2990.7 | −728.1 | PASS | 0 |
| 2026-03-03 (total) | +0, +0 | 75.1 | 09:13:57.0 to 13:48:11.9 | 10:21:59.4 to 12:39:53.8 | 1769.1 | 2093.0 | 1913.5 | 2242.1 | −2552.5 | −2222.9 | PASS | 0 |
| 2026-03-03 (total) | +45, +0 | 75.1 | 09:12:50.5 to 13:56:21.6 | 10:16:36.3 to 12:52:24.7 | 1702.6 | 1603.4 | 1590.4 | 1491.2 | −2875.6 | −2973.8 | PASS | 0 |
| 2026-03-03 (total) | −45, +0 | 75.1 | 09:20:33.7 to 13:37:33.0 | 10:39:08.7 to 12:18:38.2 | 2165.7 | 2731.9 | 2942.8 | 3517.7 | −1523.2 | −947.3 | PASS | 0 |
| 2026-03-03 (total) | +0, +45 | 75.1 | 09:36:57.0 to 14:09:14.0 | 10:45:53.5 to 13:00:01.4 | 3149.1 | 831.0 | 3347.6 | 1034.6 | −1118.4 | −3430.4 | PASS | 0 |
| 2026-03-03 (total) | +0, −45 | 75.1 | 08:52:50.6 to 13:28:18.5 | 10:00:06.7 to 12:20:47.5 | 502.6 | 3286.4 | 600.8 | 3388.4 | −3865.2 | −1076.6 | PASS | 0 |
| 2026-08-28 (partial) | +0, +0 | 75.4 | 02:00:21.5 to 06:29:57.4 | 03:15:51.9 to 05:14:22.5 | 2180.3 | 1909.8 | 2517.6 | 2258.7 | n/a | n/a | PASS | 0 |
| 2026-08-28 (partial) | +45, +0 | 75.4 | 02:08:24.9 to 06:14:53.1 | 03:48:20.0 to 04:34:48.1 | 2663.7 | 2814.1 | 4465.8 | 4633.1 | n/a | n/a | PASS | 0 |
| 2026-08-28 (partial) | −45, +0 | 75.4 | 01:55:17.9 to 06:39:14.0 | 03:02:57.3 to 05:31:33.3 | 1876.7 | 1353.3 | 1743.1 | 1227.9 | n/a | n/a | PASS | 0 |
| 2026-08-28 (partial) | +0, +45 | 75.4 | 02:22:40.7 to 06:49:38.9 | 03:39:42.4 to 05:32:32.2 | 3519.5 | 728.3 | 3948.2 | 1169.0 | n/a | n/a | PASS | 0 |
| 2026-08-28 (partial) | +0, −45 | 75.4 | 01:36:51.9 to 06:08:36.2 | 02:50:55.5 to 04:54:29.0 | 770.6 | 3191.0 | 1021.3 | 3452.2 | n/a | n/a | PASS | 0 |

**On the 2026 Aug 28 partial eclipse:** the Moon is only partly in the umbra, but sites on the umbral part of the disk still see a total solar occultation. That is why those sites show `ecl_total` events contained in [U1, U4].

**Raw measurements:** `v13.json` → `results` has the full precision and every event time.

## Comparison with the stale A13 evidence
**Why the old evidence is stale:** A13 (`../../v13_gsfc_2026-11-09/v13.json`) and the A14 re-run (`../../v14_month_a14_2026-11-10/report/v13.json`) were produced with code fingerprint `230071e0…`, which differs from the current `5bf9753f…`. The live `report.json` therefore lists V-13 as "not run".

**What the refresh shows:**
- every margin is **identical** to both earlier runs (max change 0 s);
- every event-time string is identical;
- the algorithm 1.5.0 Earth-pole change does not move these eclipse events at 0.1 s resolution.

## Limitations (unchanged from A13)
- **Containment, not timing agreement:** the 8–60 min margins cannot detect a timing error of minutes.
- **Different shadow models:** GSFC enlarges the shadow (Danjon); LUNA-OPS uses the solid Earth.
- **Different ephemerides and ΔT:** GSFC uses VSOP87/ELP2000-85 and a 2009 ΔT prediction; LUNA-OPS uses DE440.
- **Manual transcription:** the contacts were read from rendered PDF figures, which have no extractable text. They are guarded by the two consistency checks above.
- **Coverage:** four 2025–2026 eclipses, no penumbral-only eclipse, and five nearside sites.
