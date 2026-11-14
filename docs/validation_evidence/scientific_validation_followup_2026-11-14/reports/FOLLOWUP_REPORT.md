# LUNA-OPS 2.0: event-detection correction and scientific-validation follow-up (2026-11-14)

**Scope:**
- the approved event-detection correction (`backend/lunaops/engine/events.py` only);
- the new fingerprints and validation baseline;
- focused regression tests;
- V-09/V-10 criteria work;
- disk-visibility and power-indicator verification;
- targeted E2E tests.

**Not changed:** no other engine algorithm, dataset, threshold or validation label rule. **Not run:** the Phase 7 suite.

## 1. Event-detection defect and correction
- **Defect:** interval states were taken at segment midpoints, and entering or leaving incomplete (missing-terrain, lower-bound) horizon bins was not an interval boundary. Time when a disk's verdict rested on such bins could therefore be reported as **visible** instead of **unknown**.
- **Correction** (`event_fix/events.py.diff`, 38 changed lines, all in `events.py`):
  - **New functions:** `incomplete_cuts(det, et0, et1)` and `_unknown_flags`. They scan the engine's own per-target unknown flag (`Sample.geo[target]["state"]["unknown"]`, the flag the disk calculations already set) every 60 s, and refine each change by bisection to the event tolerance (1 s).
  - **`build_intervals`:** adds those times as cuts. A cut within 1 s of an existing cut is skipped, so no sub-second slivers appear.
  - **Not touched:** geometry, disk calculations, event functions and event timing. The extra scan runs **only when the horizon has incomplete bins**. Complete horizons take exactly the previous code path, and the intervals are proved identical (tests, E2E-03).
  - **Events list unchanged:** missing-terrain boundaries are interval boundaries, not entries in the events list.
  - **Cost:** about 0.7 ms per scan point, so about 30 s more for a 30-day analysis of a site with incomplete bins. The −60.48° E2E analysis took 42 s in total.

**Before and after:**

| Case | Before | After |
|---|---|---|
| Synthetic investigation case: Sun over incomplete bins, low horizon | 6,782 s expected unknown → **0 s unknown, 6,782 s visible** | **6,782 s unknown, 0 s visible** (`event_fix/after/events_independent_after.json`) |
| Real case, −60.482591°, 266.96912° E, 12 Nov–12 Dec 2026 (19.3 % incomplete bins) | `a667129a`: 8,404 min should be unknown; reported 6,166 unknown, **2,238 min (37.3 h) visible**, and 7,567 min unknown in total (about 1,400 min more than required) | `5998e029` (same request, new engine): **8,404 unknown, 0 visible, 8,404 unknown in total**. Summary unknown 126.11 h → 140.06 h (`event_fix/after/incomplete_bins_real_results_after.json`) |
| Other 12 synthetic event cases (short windows 8.8–420.6 s, several windows, analysis start and end, no visibility, always visible, uncertain terrain, Sun-centre rule) | All matched; worst edge error 0.50 s | Identical: the same windows and the same timing errors (≤ 0.50 s); uncertain terrain still flagged |

**The pre-fix result `a667129a` is kept** in the cache, unchanged, as history.

## 2. New engine fingerprint and validation baseline
| | Previous (preserved) | New |
|---|---|---|
| Code fingerprint | `84cbd4ea34f6606abcd32e02df295f204cb97ca9bef3d9a4d455b4557c831109` | **`9cd7b08b36ba6be4fe0e623ff0a8b04da4dae15b1f9867e496927ff945dd73c8`** |
| Suite fingerprint | `1632af16763dda4e27909a9af3d2fdd903b0d58951faacded72c4cf06d75eabc` | **`519a8e4ca3053cbc4c151fccf68397f17c416f3ce677ef4ec66052a7eb116cb6`** (new test file `backend/tests/test_events_incomplete_cuts.py`) |
| Validation report | `backend/validation/report.json` `8c03ebaf…` (unchanged; copy in `fingerprints/report.json.historical_84cbd4ea`) | Not regenerated: that is the full validation run, deferred to Phase 7 |

- **Labels:** the engine's guard (`provenance.label_blockers`) now reports "the validation report was produced by different code" and "… a different version of the tests". So **no quantity is labelled Validated** (`fingerprints/api_status_after.json`).
  - Sun/Earth azimuth and elevation, and the terrain horizon, were Validated before; they are now **Pending validation**.
  - All five labels display as Pending validation (E2E-01).
- **New baseline** (`fingerprints/new_validation_baseline.json`):
  - all 424 entries of the historical report are listed with their old status;
  - the **420 that passed are marked "revalidation required"**;
  - V-09/V-10 stay "not run", and 2 are skipped.
- **Unchanged identifiers:** algorithm version 1.5.0 was not bumped (it lives outside `events.py`). The change is identified by the code fingerprint, which every new result records. Bumping it at the next revalidation is recommended.

## 3. Regression tests
| Test | Result | Log |
|---|---|---|
| New `test_events_incomplete_cuts.py` (5): the 6,782 s case (boundaries within 1 s of the per-second unknown flag, no visible time over missing terrain); two missing-terrain runs (two unknown intervals, edges within 1 s); a window opening on missing terrain at the analysis start; hidden over missing terrain stays hidden; complete horizon gives no extra cuts and intervals identical to the old construction | **5 passed** | `regression/pytest_events_incomplete_cuts.log` |
| Existing event tests: `test_events_api`, `test_phase4_v14`, `test_phase2_golden`, `test_phase3_earth_rates` | **48 passed** | `regression/pytest_existing_event_tests.log` |
| Synthetic event cases (13), short windows down to 8.8 s, start and end boundaries | All windows matched; worst edge error ≤ 0.50 s (as before) | `logs/01_events_synthetic_after.log` |
| Real complete-terrain case: Site01, 30 days, every interval of every rule against the pre-fix result `976a3d8f` | **Identical** (E2E-03) | `e2e/e2e-results.json` |
| Disk ray-cast (24 cases) under the new engine | Engine outputs identical to before; 23/23 verdicts agree | `logs/06_disk_after.log` |
| Power indicator: 261 series (87 results × 3 panels), 14 edge cases, RF hand case | Match within storage rounding; 14/14; RF exact | `logs/04_power_after.log` |

**Test-design corrections made during this work, recorded for transparency:**
- **Three of the new tests initially failed because of my setups:**
  - one test allowed no boundary second;
  - one used a missing-terrain run that extended past the window;
  - one used a random horizon that never crossed the Sun.

  They were corrected; the engine was not changed in response.
- **The power script** first read the panel azimuth from a non-existent key, assuming 0°. Once results with a 400° azimuth existed, that showed up as a false mismatch. It was corrected to `provenance.parameters.panel.azimuth_deg`.

## 4. V-09 (Investigated)
Details: `v09_v10/V09_V10_FINDINGS.md`.
- **Reported:** equal-weight RMSE 14.09 / bias −7.19 pp; area-weighted 3.77 / −0.97; smooth subset 1.15 / −0.34 (n = 90).
- **Cause:** at bright ridges and rims where the Sun grazes the horizon, the observer-point and near-field definition dominates (2 m: worst-10 RMSE 43.9 → 7.6). Equal-per-stratum sampling then gives these 0.007 % of the area 32 % of the points.
- **NASA observer height:** not found in the stored labels, PGDA 69 or the searched sources (Mazarico et al. 2011, Icarus 211, 1066–1081; full text not accessible). It remains a recorded assumption (0 m).
- **Criteria (not approved):**
  - R1: smooth subset, RMSE ≤ 2 / |bias| ≤ 1 pp;
  - R2: area-weighted, RMSE ≤ 5 / |bias| ≤ 2;
  - R3: report the equal-weight statistics and outliers without gating.
- **Circularity risk:** these were written after seeing the residuals. **A fresh holdout sample** (new seed, criteria and definition fixed in writing first; about 2 h of computation) is recommended before approval.
- **No algorithm change.** Status: **Investigated**, and **revalidation required** under the new fingerprint before any decision.

## 5. V-10 (Investigated)
- **Reported:** equal-weight 3.13 / −0.74; area-weighted 3.28 / −0.90; smooth subset 1.04 / −0.19 (n = 160); without the 10 dominant points 0.87 / −0.13.
- **Cause:** the same mechanism at crater-floor points where Earth grazes the terrain. No single observer height reconciles them (2 m over-corrects: +3.85).
- **Criteria and holdout:** as for V-09.
- **Definition:** "any part of the Earth disc" in both the reference and the benchmark; the UI default (centre) is a different, documented quantity.
- Status: **Investigated**.

## 6. Earth-disk visibility (Pending validation)
- **The 24 independent ray-cast comparisons are preserved** (23 comparable, plus 1 unknown by design). Rerun under the new engine with identical outputs:
  - visible fraction within **1.36e-4**;
  - **identical any/centre/full verdicts in all 23**;
  - grazing slivers (±0.002°) resolved;
  - partial, crater-wall, peak-site (below 0° but above the terrain) and fully blocked cases correct;
  - missing terrain: visible becomes unknown, and a blocking lower bound stays hidden.
- **End-to-end:**
  - **E2E-04** (84.31° S, 359.05° E): UI 75.7 % = backend 75.70 %. It reproduces the Phase 6 reference of 545.02 h (centre) under the new engine, with 266 partial-disk samples (0 < f < 1); any-part hours 614.08 ≥ centre hours 545.02.
  - **E2E-05** (78.40° S, 21.87° E): UI 0.0 % = backend 0; all 1,442 Earth samples have f = 0 (fully terrain-blocked).
- **Not Validated:** acceptance tolerances are not approved, and the engine gates U-04/U-06 have not been run.

## 7. Power indicator (Pending validation)
Details: `power_indicator/POWER_INDICATOR.md`.
- **Definition:** P_rel = f_sun × (1 au / r)² × k(panel). Dimensionless; 1 = whole Sun at 1 au, face-on.
- **What it is not:** electrical power in watts, or an RF quantity. There are no hardware parameters, so none is invented.
- **Verified:**
  - 261 series and metrics recomputed exactly;
  - 14/14 boundary behaviours as defined;
  - E2E-06: UI 0.539 = backend 0.5386 (vertical tracking), and UI 0.014 = backend 0.0139 (horizontal; the request carried `panel_model: horizontal`). No watt or kW wording; labelled Estimated.
- **Terminology recommendation (not applied):**
  - rename "Power indicator" to "Solar availability indicator (relative, dimensionless)", or state "no unit; 1 = full Sun at 1 au, face-on" beside the value;
  - rename "Equivalent full-Sun" to "Equivalent full-Sun hours (face-on, 1 au)".
- **Not validated** against measured power: no measurement data exists.

## 8. Targeted E2E results (`e2e/e2e-results.json`, `e2e/screenshots/`)
Path tested: browser input → frontend validation → API → backend → API response → display. One headless browser, against the single restarted server. The reference cases were recomputed one after another.

| ID | Workstream | Steps (short) | Expected | Actual | Result |
|---|---|---|---|---|---|
| E2E-01 | V-09 / V-10 | Data and validation tab | V-09 / V-10 "not run" with 14.09 / −7.19 and 3.13 / −0.74 and "provisional"; blockers note; all labels Pending | As expected; blockers name both fingerprint mismatches; 5/5 labels Pending | **Pass** |
| E2E-02 | Events, missing terrain | −60.48° site, 30 days, Analyse | Unknown shown and equal to the backend; hatched (unknown) segments; no visible time over missing terrain | UI 140 h unknown = backend 140.06 h; hatched segment in the Sunlit row (screenshot); backend 0 min visible over missing terrain | **Pass** |
| E2E-03 | Events, complete terrain | Site01, 30 days | Intervals identical to the pre-fix result; Unknown 0; UI % = backend | All 7 interval sets identical; Unknown 0 min; 55.5 % = 55.54 % | **Pass** |
| E2E-04 | Earth disk, partial | 84.31° S, 359.05° E | UI = backend; partial-disk samples present | 75.7 % = 75.70 %; 266 partial samples; 545.02 h reproduced | **Pass** |
| E2E-05 | Earth disk, fully blocked | 78.40° S, 21.87° E | 0 % displayed and computed; f = 0 throughout | As expected | **Pass** |
| E2E-06 | Power | Site01; vertical, then horizontal panel | UI = backend; no watt claim; Estimated | 0.539 / 0.5386; 0.014 / 0.0139; no watt wording | **Pass** |
| E2E-07 | Power / inputs | lat −95; end before start; panel azimuth 400; unknown panel model (API) | Invalid latitude flagged with no request; **end-before-start refused before a request is sent** (UI or API 4xx); unknown panel → 4xx | Latitude flagged, no request (pass); unknown panel → 422 (pass). **End-before-start: Analyse stays enabled and the API returns 200 (job accepted). The job then stops with "The end time must be after the start time.", the UI shows that message and no result (E2E-07b, `e2e/e2e07b.json`).** Panel azimuth 400: the UI marks the field invalid but Analyse stays enabled; the API accepts it and computes with 400° ≡ 40° | **Fail** (against the stated expectation; no incorrect result is produced; low-severity validation gap) |

One console error was recorded: the expected 422 from the deliberate unknown-panel request.

## 9. Cache and evidence integrity (`cache/`)
- **Nothing deleted:** no cache entry, horizon, dataset, backup or earlier evidence was deleted or modified.
- **Recomputed under the new fingerprint, sequentially, by the E2E tests only** (6 results, 4 horizons; `cache/recomputed.json`):
  - `5998e029` (−60.48° missing-terrain case);
  - `eda9338a` (Site01, vertical);
  - `3ac70f2c` (Site01, horizontal);
  - `0e0522db` (Site01, 1 day, fixed panel at 400°, from E2E-07);
  - `47c26f2a` (84.31° S);
  - `f9d5518f` (78.40° S).

  The last two inherited the 400° panel azimuth left by E2E-07. That affects only their fixed-vertical power series (power metrics verified with the recorded azimuth); visibility is unaffected.
- **Old-fingerprint results:** all 81 kept, including the audit's 74 (files present, digest unchanged).
  - One of the 81 (`55ec1b92`, −85.02°, 47.13° E, created 02:38 UTC) appeared between the baseline and the server restart, at a site no test used. Like the earlier additions, it is consistent with someone using the app.
- **Normal cache behaviour:** old results stay addressable but are not reused, because new requests get new IDs. Nothing was mass-recomputed.
- **Engine tree:** the digest changed only through `events.py` (`cache/integrity_before.txt` against `cache/integrity_after.txt`). The terrain registry, `report.json` and `tiles.py` are unchanged.
- **Evidence:** every evidence folder with a `SHA256SUMS` verifies (run at the end of this task).

## 10. Status summary
| Item | Status |
|---|---|
| V-09 | **Investigated**; revalidation required under the new fingerprint; criteria not approved |
| V-10 | **Investigated**; as V-09 |
| Earth-disk visibility | **Pending validation** (revalidation required; strong independent evidence) |
| Event detection | **Pending validation**, defect corrected; revalidation required |
| Power indicator | **Pending validation** (implementation verified; not validated against measurement) |
| Previously Validated engine quantities (Sun/Earth positions, horizon) | **Revalidation required** (labels now Pending by the engine's own guard) |

Nothing is marked Validated or Failed at the scientific level. The one **Fail** is the E2E-07 input-validation expectation.

## 11. Not verified, and minimum work before Phase 7
**Not verified:**
- AVGVISIB's observer height and near-field method;
- V-09/V-10 on the reference's own DEM;
- a fresh holdout sample;
- the power indicator against measured power;
- the full automated suite and validation report under the new fingerprint;
- U-04/U-06;
- screen-reader and keyboard paths for the new unknown intervals;
- E2E at phone widths.

**Minimum work before Phase 7:**
1. Approve or replace the V-09/V-10 criteria. Settle the observer height, or accept it as a documented limitation. Run the fresh holdout.
2. Regenerate the validation report under fingerprints `9cd7b08b…`/`519a8e4c…`. This means the full automated suite plus V-04–V-14 external runs, which re-establish Sun/Earth positions and the horizon.
3. Decide the disk-visibility tolerances, the event timing tolerance (1 s edges, 2 s durations recommended) and the acceptance basis for the power indicator.
4. Optionally:
   - check the window in the frontend before sending (end after start), and bound the panel azimuth (E2E-07);
   - adopt the power-indicator terminology change;
   - bump the algorithm version at revalidation.
