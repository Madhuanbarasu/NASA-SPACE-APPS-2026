# V-05 refresh: rise/set (horizon-crossing) timing compared with JPL Horizons, 2026-11-11 (separate report)

**Formal result: PROVISIONAL. V-05 is not marked PASS.**

| | Value |
| --- | --- |
| Proposed threshold | every abs(t_LUNA − t_Horizons) <= **1.0 s**, with no missed or spurious crossing |
| Approval status of the threshold | **Not approved.** It was proposed in A9 because the blueprint's V-05 criterion text was unavailable; this refresh was told explicitly not to treat it as approved. |
| Event-set agreement (does not depend on the threshold) | 18 Horizons crossings, 18 matched, **0 missed, 0 spurious** |
| Measured max abs(dt) | **0.49995 s** |
| Measured mean dt / median abs(dt) | +0.291 s / 0.339 s |
| Range of dt | −0.109 s to +0.500 s |
| Within the proposed 1.0 s | 18 of 18 (reported, not judged) |
| Status written by `horizons_compare.py` | `passed`. This is the script's mechanical comparison against the unapproved 1.0 s threshold, kept verbatim in `../v04_horizons/horizons.json`. It is **not** the formal result. |

> **Do not merge V-05 from `../v04_horizons/horizons.json`.**
>
> - **Why:** the script would record V-05 as `passed` in a validation report.
> - **What it would take:** a merge first needs a formally approved V-05 criterion, and then a run of the script that encodes it.
> - **What this refresh did:** it ran no `run_validation`, so `backend/validation/report.json` is unchanged.

## What is compared
- **Event:** the centre of the Sun or Earth crosses an ideal flat 0° horizon.
  - There is no terrain or refraction, and the site height is 0 km on the 1737.4 km sphere.
  - Rise is direction +1 and set is −1.
- **Run:**
  - the measurement comes from the same run as V-04 (same script, same software, same kernels, same Horizons responses);
  - see `../v04_horizons/README.md` for the run, the sites, the DE441/DE440 versions and the kernel and fingerprint record.
- **Window:** 2026-11-14 00:00 TT to 2026-12-14 00:00 TT.
- **Sites:** the six Section 10.3 sites (Earth is not checked at the farside site).

## Search-step details
**Reference (Horizons only):**
1. **Bracket:** a sign change in the hourly Horizons elevation (`STEP_SIZE=1h`, 11 tables) brackets a crossing.
2. **Minute table:** Horizons tabulates that hour in 60 intervals, i.e. 1-minute steps (18 tables).
3. **Second table:** Horizons tabulates the bracketing minute at 1-second steps with `TIME_DIGITS=FRACSEC` (18 tables).
4. **Interpolation:** the crossing time is linear between the two 1-s samples that bracket 0°. Every reference bracket was 1.0 s (`ref_bracket_s`).
5. **Confirmation:** an unmatched detector event would trigger a ±30 min, 1-minute Horizons table and the same refinement. None was needed (0 confirm tables).

**LUNA-OPS:**
- **Detector:** `lunaops.engine.events.EventDetector` with functions `sun_c` and `earth_c`, on the same flat horizon.
- **Step control:** adaptive steps capped at 600 s (`EVENT_STEP_CAP_S`), with a 1 s floor (`EVENT_STEP_FLOOR_S`).
- **Bisection:** to a 1.0 s bracket (`EVENT_TOL_S`).
- **Reported time:** the bracket midpoint. The detector's resolution is therefore ±0.5 s, and the worst measured difference, 0.49995 s, is exactly that limit.

**Matching:** same body and direction, nearest event within 600 s.

**Which file is which:** `v05_report.json` → `horizons_responses_by_stage` maps every Horizons file used to its stage, step, start, stop and SHA-256.

## Measured differences (dt = t_LUNA − t_Horizons)

| Site | Body | Event | Horizons crossing (UTC) | dt (s) |
| --- | --- | --- | --- | ---: |
| south-polar A | Earth | rise | 2026-11-17T08:05:50.798 | −0.1000 |
| south-polar A | Earth | set | 2026-11-30T06:58:22.895 | −0.0534 |
| south-polar B | Sun | set | 2026-11-16T10:01:31.984 | +0.5000 |
| south-polar B | Sun | rise | 2026-11-27T13:17:29.463 | +0.4483 |
| south-polar B | Earth | rise | 2026-11-20T00:17:07.595 | +0.1065 |
| south-polar B | Earth | set | 2026-11-27T15:54:06.267 | +0.3295 |
| north-polar | Sun | rise | 2026-11-17T02:29:16.343 | +0.4466 |
| north-polar | Sun | set | 2026-11-26T21:14:36.289 | +0.4514 |
| north-polar | Earth | set | 2026-11-19T00:54:25.097 | −0.1093 |
| north-polar | Earth | rise | 2026-11-28T14:53:56.409 | +0.3047 |
| nearside equatorial | Sun | rise | 2026-11-17T00:09:13.006 | +0.4987 |
| nearside equatorial | Sun | set | 2026-12-01T19:51:31.290 | +0.4925 |
| limb | Sun | set | 2026-11-24T09:58:20.425 | +0.3484 |
| limb | Sun | rise | 2026-12-09T05:09:42.389 | +0.4950 |
| limb | Earth | rise | 2026-11-26T00:30:52.948 | +0.1424 |
| limb | Earth | set | 2026-12-10T14:35:10.206 | +0.2281 |
| farside | Sun | set | 2026-11-17T00:09:03.446 | +0.2195 |
| farside | Sun | rise | 2026-12-01T19:51:40.882 | +0.4832 |

**Where the raw values are:**
- **ET of both times:** `v05_events.csv` and `v05_report.json` → `events`.
- **Full precision:** `../v04_horizons/horizons.json` → `v05`.

## Comparison with the stale A9 evidence
- **Same crossings:** the same 18 were found.
- **LUNA-OPS times:** identical to A9.
- **Horizons crossing times:** they moved by at most 8.4e-5 s. This follows from Horizons' own output changing in the 9th decimal of the elevation and its EOP file being updated (`../v04_horizons/README.md`).
- **dt values:** the same to 1e-4 s.

## Files
| File | Contents |
| --- | --- |
| `v05_report.json` | The separate V-05 report: formal status and approval record, summary statistics, sites, search-step details, events, missed and spurious events, Horizons files by stage, source-file SHA-256 (`401e446d…0ad49b` = `../v04_horizons/horizons.json`), and run metadata. |
| `v05_events.csv` | One row per matched crossing. |
| `v05_report.log` | Output of the generator. |
| `../scripts/v05_report.py` | The generator. It only post-processes `horizons.json`, adds no scientific computation, and sets the formal status by the rule in its docstring. |

## What would close V-05
- **Approve a criterion:** a V-05 timing criterion has to be formally approved (the proposed 1.0 s, or another value).
- **Then:**
  - if it differs from `V05_TOL_S` in the script, the script has to change;
  - the run has to be repeated under the resulting fingerprints.
- **Against the proposed 1.0 s:** the measured worst case, 0.49995 s, would meet it. The worst case is set by the detector's ±0.5 s midpoint resolution, so a threshold below 0.5 s would need a finer detector tolerance (an algorithm change outside this refresh).
