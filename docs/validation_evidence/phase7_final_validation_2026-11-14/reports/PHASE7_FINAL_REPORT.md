# LUNA-OPS 2.0 — Phase 7 final validation report (2026-11-14)

**Overall status: Phase 7 is partly complete.** All the scientific validations ran under the current engine, and one of them failed (V-10). The full automated test suite was **skipped on the owner's instruction** before it finished. The official validation report could therefore not be regenerated; an **interim report** was produced instead. The application currently shows **no Validated labels**, which is correct given the evidence. Several checks that need the application server have not been run.

No NASA approval or certification is claimed. There is no operational DSN or LunaNet integration.

## 1. Versions under test

| Item | Value |
|---|---|
| Engine code fingerprint | `9cd7b08b36ba6be4fe0e623ff0a8b04da4dae15b1f9867e496927ff945dd73c8` (unchanged in Phase 7) |
| Test-suite fingerprint | `70606628abed3fdee2704e0b8e2891f648da27266b04791d7690531a517cd546` |
| Why the suite fingerprint changed (was `519a8e4c…`) | The approved V-09/V-10 criteria and the holdout support were written into `validation/v09_v10_avgvisib.py` and its test file. The scientific engine did not change. |
| Installed official report | `backend/validation/report.json`, sha `8c03ebaf…`. It is the historical report (code `84cbd4ea…`, suite `1632af16…`, run 2026-11-12). It was not overwritten. |

Every result below was checked against its result file. Each file carries the fingerprints above in its `meta` block, and the project's merge guard (`merge_external`) accepted all of them with 0 rejections.

## 2. Results

### Passed (13 checks)

| Test | What it checks | Result | Evidence |
|---|---|---|---|
| V-09 | Sunlight average visibility vs NASA PGDA, fresh frozen holdout | Passed. 200/200 points scored. Smooth points (R1): RMSE 1.84 pp, bias −0.66 pp (limits 2 / 1). Area-weighted (R2): RMSE 2.41 pp, bias −0.77 pp (limits 5 / 2). | `engine_regression/external/v09_v10_holdout.json`, `V09_holdout/` |
| V-13 | Lunar eclipse timing vs NASA GSFC | Passed: 20/20 | `external/v13.json` |
| V-14 | One month, 1 s brute-force check of window edges | Passed: 955 edges, 0 missed, worst 0.5 s | `external/v14.json` |
| V-04 | Sun/Earth direction vs JPL Horizons | Passed: max 5.2e-7° (tolerance 0.01°), 7,931 epochs | `external/horizons.json` |
| V-05 | Rise/set times vs JPL Horizons | Passed: 18 crossings, worst 0.5 s (tolerance 1 s) | `external/horizons.json` |
| V-11 | Permanent shadow vs NASA LPSR map | Passed: 200/200 dark, 0 lit, 0 inconclusive | `external/v11.json` |
| V-12 | Illumination vs LROC WAC | Passed: 200/200 scored. C1: 26 shadow samples, 0 above 1 %. | `external/v12.json` |
| U-04 | Accessibility (approved scoped WCAG 2.2 A/AA, D4) | Passed: 0 problems in 12 views; 13/13 keyboard and announcement checks | `accessibility/frontend_u04.json`, `accessibility/u04_audit/audit-phase7.json` |
| Earth disk | Partial-disk visibility vs an independent calculation | Passed: \|Δf\| max 1.36e-4 (limit 5e-4); 23/23 any/centre/full classifications agree. Reused from the same engine. | `scientific_validation_followup_2026-11-14/disk_visibility/disk_independent_after.json` |
| Events | Window edges and durations; missing terrain | Passed: 17 windows, edge error max 0.5 s (limit 1 s), duration error max 0.92 s (limit 2 s). Missing terrain: 6,781.5 of 6,782 s reported Unknown, never Visible (0.5 s at a sample boundary). | `event_detection/` |
| Power indicator | Independent recalculation (dimensionless, labelled Estimated) | Passed: 297 series match within 1.01e-5; 14/14 edge cases | `power_indicator/power_independent_phase7.json` |
| Relay geometry | Independent orbit propagation | Passed: positions agree to 1.3e-11 km; vis-viva about 1e-15; leg-2 line of sight 500/500 | `power_indicator/relay_independent.json` |
| Landing reference | Site01, 1.5 km half-width | Reproduced exactly: slope median 10.85°, 42 depressions (28 defined, 14 weak) | `engine_regression/landing_site01_1500.json` |

The power indicator is not validated against measured power and keeps its Estimated label.

### Application checks (passed, run before the server stopped)

| Check | Result |
|---|---|
| E2E | 16/16 |
| App checks | 13/13 |
| Explorer | 27/27 |
| Globe | 31/31 |
| Globe target | 9/9 |
| Responsive (7 tabs × 1920/1440/1024/390/320) | 35/35, 0 console errors |
| Map | 19/21 (see Investigated) |
| RF link budget | Hand-worked case matched exactly (reused) |

Evidence: `application_e2e/`, `responsive_design/`.

### Failed (1)

| Test | Result |
|---|---|
| **V-10** (Earth average visibility vs NASA PGDA, fresh frozen holdout) | **Failed.** 200/200 points scored, 0 inconclusive. R1 smooth: RMSE 3.26 pp (limit 2), bias 0.25 pp. R2 area-weighted: RMSE 5.41 pp (limit 5), bias −0.29 pp. |

**Why it failed.** One point dominates: 85.3305° S, 285.2104° E. NASA's value there is 0 % and LUNA-OPS computes 39.8 %. That single point carries 98 % of the R1 squared error.
- NASA's 0 % is a pocket one to two pixels wide. Within ±1 km the NASA map averages 41 %.
- The pocket is consistent with the "linear artifacts" that NASA's own readme warns about, but the cause is not proven.
- The point was **not removed**, because the holdout was frozen before the run, and no criteria were changed.

Full diagnosis: `V10_holdout/outlier_diagnosis.json`, `failure_analysis.txt`.

Options for the owner:
1. Accept the Failed result.
2. Pre-register an artifact screen, for future runs only.
3. Inspect the 60 m NASA terrain model (LDEM_85S_060M).

### Skipped (1)

**Full pytest suite: skipped on the owner's instruction.** It was stopped at 325 of 572 tests (549 s), and no JUnit file was produced. This is **not** recorded as passed.

Before it was stopped:

| Part of the suite | Passed | Failed | Skipped |
|---|---|---|---|
| `tests/` (the folder the official report uses) | 198 | 0 | 2 |
| Comms, landing and tiles package tests | 98 | 12 | 15 |
| Not reached | — | — | 247 tests |

Why the 12 comms tests failed. All 12 depend on the Moon's GM file. When the whole tree runs together, `tests/conftest.py` redirects the data folder to a temporary directory at import, so that file isn't found.
- The same tests pass when run on their own: `test_relay.py` 17/17 just now, and the comms package 57/57 earlier in Phase 7.
- This is a test-isolation problem in the combined run, not a product fault. It was not fixed, because no development was authorised.

Evidence: `engine_regression/pytest/`.

### Not run (needs the application server, which is stopped)

- **U-06 performance audit** (3 browser profiles) and its D3 evaluation. U-06 is required for every Validated label.
- **Backend timings and server memory.** The script is ready: `scripts/backend_perf.py`.
- **App and `/api/status` label display** after a new official report is installed.
- **Official report regeneration** (`run_validation`). It needs a complete pytest run of `tests/`, which was skipped.
- **Cache integrity end comparison** against `cache_integrity/integrity_phase7_start.txt`. This one does not need the server; it was not in the requested task list.

### Investigated

| Item | Finding |
|---|---|
| Server and chain stop at about 04:47Z | The host stopped them for low memory. The chain script survived and finished normally ("chain done 05:07:53Z"), so the results are unaffected. See `logs/35_interruption_low_memory.txt`. |
| Map check 19/21 | The two failures are a loading-note timing check and a click-placement check (no click landed north of 60° S). Targeted checks T2 and T3 confirmed both behaviours work. |
| Four accessibility findings | Fixed before the final audit: text-spacing in the figure cards and badges, an invisible chart label, a clipped focus ring in the comparison matrix, and a label chip at 320 px. |

## 3. Validation labels

- **Interim report** (`report_regeneration/interim_report_phase7.json`): 8 passed, 1 failed (V-10), 17 not run. The label rules give **no Validated label**, because the pytest suite was not completed.
- **Installed official report**: also **no Validated label**, because it was produced by different code and suite versions (`84cbd4ea…` / `1632af16…`). The application therefore cannot show a stale Validated label.
- No label was forced or restored by hand.

Even with a complete pytest run, labels would stay withheld until U-06 passes. Labels that depend on V-10 would stay unvalidated while V-10 is Failed.

## 4. Historical evidence and checksums

**Historical reports are preserved, with identical hashes:**

| File | sha256 |
|---|---|
| `backend/validation/report.json` | `8c03ebaf…` |
| `report.json.historical_84cbd4ea` | `8c03ebaf…` |
| `report_regeneration/report.json.before_phase7` | `8c03ebaf…` |
| `backend/validation/report.json.bak_5135efe8` | `5135efe8…` |

**Checksum manifests:** all 33 earlier evidence manifests verified.

| Result | Folders |
|---|---|
| OK | 31 |
| `post_phase5_backend_and_ui_fixes_2026-11-12` | 275/275 OK. The manifest has Windows line endings, so a plain `sha256sum -c` fails; it was checked with the line endings removed. |
| `scientific_validation_followup_2026-11-14` | 50/50 OK. The only mismatch is `logs/server.log`, a live server log written after its manifest was created (last entry 03:29:53Z). |

No manifest was edited. Details: `report_regeneration/historical_and_checksum_verification.txt`.

**This folder** is covered by its own `SHA256SUMS`.

## 5. Remaining limitations

- V-10 is Failed. The cause of NASA's 0 % pocket is undetermined.
- V-09 and V-10 assume an observer height of 0 m. This is the project's assumption: NASA's readme gives no observer height, and no claim is made that NASA used 0 m.
- U-04 was tested in Chrome headless only. There was no real screen-reader session, and it is not a claim of full WCAG 2.2 AA conformance.
- U-06 has not been measured under this engine.
- The full pytest suite was not completed, and the combined-run isolation problem in the comms tests is open.
- The power indicator is dimensionless and Estimated.
- Communication results are geometric and RF-budget estimates using illustrative inputs, not real spacecraft or DSN schedules.
