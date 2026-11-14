# Phase 4 closure review, 2026-11-11

> **Final status (2026-11-12): Phase 4 COMPLETE WITH APPROVED DEFERRALS** (`../phase4_final_merge_2026-11-12/README.md`).
> - **Official report:** regenerated with all eight approved files: `2279606c…d077d376`; pytest 438 passed, 2 skipped, 0 failed; 420 entries passed, 2 not run.
> - **Passed:** V-04, V-05, V-11 to V-14, U-04 and U-06.
> - **Not run:** V-09 and V-10 (deferred, D2).
> - **IB-5:** deferred (D5).
> - **Labels:** only `sun_earth_azel` (and `horizon` on the status page) are Validated.
> - **This record:** it reflects the closure review and is kept as it was written.


**Official Phase 4 status: NOT COMPLETE (not closable).**
- **What is finished:** every Phase 4 task that can be executed has been executed and has evidence.
- **Decisions (2026-11-11):** every decision D1–D7 now has a recorded outcome (`../phase4_remaining_decisions_2026-11-11/DECISIONS_RECORDED.md`; D1 in `../d1_v05_decision_2026-11-11/ACCEPTANCE.md`): D1 accepted; D2 deferred; D3 and D4 accepted (scoped; the U-04 current-build re-audit passed); D5 deferred; D6 completed; D7 undefined.
- **Why it is not declared complete:**
  - V-05, U-04 and U-06 are accepted, but their merge-ready results are not yet merged into the official report;
  - the D2 and D5 deferrals leave items open;
  - the completion declaration is the owner's.
- **D1, the V-05 criteria, is closed (2026-11-11).** The Phase 1.1 criteria were approved and the existing evidence accepted (`../d1_v05_decision_2026-11-11/ACCEPTANCE.md`); V-05 remains "not run" in the official report until a separately approved merge.
- **D6, regenerating the official validation report, is completed** (2026-11-11 17:24:21Z; `../phase4_merge_2026-11-11/`).
  - **pytest:** 438 passed, 2 skipped, 0 failed.
  - **Report entries:** 417 passed, 5 not run, 2 skipped.
  - **Passed:** V-04, V-11, V-12, V-13 and V-14.
  - **Not run:** V-05, V-09, V-10, U-04 and U-06.
  - **`report.json` SHA-256:** `5e6c76d75eff6c3454f68edc76ab5e08f48733e3ad2cfff72eac3e55db812e7b`.
- **Consequence:** every LUNA-OPS quantity stays **"Pending validation"**.

**What this review did:**
- It consolidates the existing evidence and reconciles the documentation.
- **No test or measurement was repeated.**
- No approval was invented.
- **Unchanged by the review:** the backend code, the thresholds, the acceptance records and `backend/validation/report.json`. The report was regenerated afterwards by the approved merge.
- **Updated 2026-11-11 after the merge:** documentation sync only. It changed this README and `SHA256SUMS`; the other files in this folder are as produced by the review.

## Build fingerprints (unchanged by this review and by the merge)
| Item | Value |
| --- | --- |
| Algorithm version | 1.5.0 |
| Code fingerprint | `5bf9753fa5c5493eadeb9839c07b837f2e3e69e3986e76146a2ed1717e37d2f8` |
| Suite fingerprint | `1632af16763dda4e27909a9af3d2fdd903b0d58951faacded72c4cf06d75eabc` |
| Terrain acceptance digest | `e48eb8ed0ca2003c2769c60932323dbce34385e4eac2a675f076e13bbd943dce` (`terrain_acceptance.json` SHA-256 `c0465069…892356ae`) |
| Kernel profile | production (7 files, verified 2026-11-11: `../refresh_v04_v05_v13_v14_2026-11-11/00_preflight/verify_kernels.log`) |
| `backend/validation/report.json` | **Current:** SHA-256 `5e6c76d7…db812e7b`, regenerated 2026-11-11T17:24:21Z by the approved merge (`../phase4_merge_2026-11-11/report_after.json`). **At the review:** `00d2cda1…6b15c239` (2026-11-10, = `../report_production_merged.json` = `../phase4_merge_2026-11-11/report_before.json`) |

`fingerprints_after.txt` records these values as recomputed at the end of this review.

## A1–A15 task register

| Task | Scope | Status | Evidence |
| --- | --- | --- | --- |
| **A1** | Production SPICE kernels installed and checksum-verified | **Completed** | `../kernels_production_2026-11-08/`; re-verified 2026-11-11 (`../refresh_v04_v05_v13_v14_2026-11-11/00_preflight/verify_kernels.log`) |
| **A2** | Production-kernel validation: V-01 to V-03, V-02e (d_max 0.506 m ≤ 1 m) | **Completed.** The frozen-pole IAU_EARTH check that failed in A2 was resolved by the Earth pole of date (algorithm 1.5.0). | `../kernel_validation_2026-11-08/`, `../earth_pole_2026-11-09/` |
| **A3** | IB-2: DE440 lunar frame kernel | **Completed** (decision approved: `moon_de440_250416.tf`) | `../ib2_2026-11-09/` |
| **A4** | PGDA 90 20 m acquisition and verification | **Completed**; its evidence is recorded under A5 (cross-reference in `../terrain_a7_2026-11-11/README.md` §5) | `../pgda90_20m_2026-11-10/` |
| **A5** | PGDA 90 20 m DEM and error-map registration (3-tier hierarchy) | **Completed** | `../pgda90_20m_2026-11-10/` |
| **A6** | Cross-product terrain validation and formal terrain acceptance (6 pairs, 5/20/80/240 m) | **Completed; ACCEPTED.** The accepted measurements are preserved unchanged, and the digest `e48eb8ed…` is enforced by `validation/terrain_gate.py`. | `../terrain_a6_2026-11-10/` (`ACCEPTANCE.md`, `MEASUREMENT_CORRIGENDUM.md`), `../terrain_a6_240m_2026-11-10/`, `../terrain_a6_polar_wide_240m_2026-11-10/`, `../terrain_a6_polar_wide_corrected_2026-11-10/`, `../terrain_a6_acceptance_review_2026-11-10/`, `backend/validation/reference/terrain_acceptance.json` |
| **A7** | Real-terrain performance profiling and window-identity check | **Completed**; accepted measurements preserved | `../terrain_a7_2026-11-11/` |
| **A8** | V-04: Sun and Earth direction vs JPL Horizons | **Completed. V-04 PASS** (max 5.235e-7° vs 0.01°, 7,931 epochs). The current evidence is the 2026-11-11 refresh; the 2026-11-09 run is stale (older fingerprints). | `../refresh_v04_v05_v13_v14_2026-11-11/v04_horizons/`; history `../horizons_v04_v05_2026-11-09/` |
| **A9** | V-05: rise/set timing vs JPL Horizons | **Completed. V-05 ACCEPTED (D1, 2026-11-11)** against the approved Phase 1.1 criteria: ≤ 120 s vs Horizons rise/set, via the 1-s centre-crossing substitute (max 0.49995 s); ≤ 10 s vs the interpolated one-minute table (max 0.49956 s); 18/18 matched. Official report: not run until merged. | `../refresh_v04_v05_v13_v14_2026-11-11/v05_riseset/` (separate report); history `../horizons_v04_v05_2026-11-09/` |
| **A10** | V-09/V-10 vs LOLA AVGVISIB | **Measured; formally deferred (D2, 2026-11-11):** no criteria approved; recorded as "not run" with metrics. | `../v09_v10_a10_2026-11-10/`, `../v09_v10_final_2026-11-10/` |
| **A11** | V-11: no sunlight in PGDA permanently shadowed regions | **Completed. V-11 PASS** (200/200 dark, complete horizons) and merged in the live report | `../v11_a11_2026-11-09/`, `../v11_final_2026-11-10/` |
| **A12** | V-12 vs LROC WAC illumination maps | **Completed. V-12 PASS** (C1: 26/26 predicted-shadow samples at TWI ≤ 0.022 % vs 1 %) and merged in the live report | `../v12_lroc_a12_2026-11-10/`, `../v12_final_2026-11-10/` |
| **A13** | V-13: eclipse contacts vs NASA GSFC catalogue | **Completed. V-13 PASS** (20/20; smallest margin 482.6 s). The current evidence is the 2026-11-11 refresh; the GSFC sources were re-fetched and are byte-identical. | `../refresh_v04_v05_v13_v14_2026-11-11/v13_eclipse/`; history `../v13_gsfc_2026-11-09/` |
| **A14** | V-14: full synodic-month detection vs 1 s brute force | **Completed. V-14 PASS** (955 edges, 0 missed, 0 over 1.0 s, 0 spurious). The current evidence is the 2026-11-11 refresh. | `../refresh_v04_v05_v13_v14_2026-11-11/v14_month/`; history `../v14_month_a14_2026-11-10/` |
| **A15** | **Not defined in any repository record.** | **Recorded as undefined (D7, 2026-11-11):** no task, deliverable or acceptance; not a Phase 4 completion criterion. | The only mention is `../c10_2026-11-11/README.md` ("the final A1–A15 traceability update"). If A15 is that update, this folder is its deliverable and it is **in progress, not complete**. |

**Other Phase 4 items (no A-number in the records):**

| Item | Status | Evidence |
| --- | --- | --- |
| Earth pole of date (algorithm 1.5.0) | Completed | `../earth_pole_2026-11-09/`, `docs/AUDIT_2026-11.md` |
| U-04: WCAG 2.2 AA accessibility | **Accepted, scoped (D4, 2026-11-11).** 55 A/AA criteria assessed, 24 defects fixed; the current-build re-audit passed (0 problems, 16/16 functional tests). Chrome/Chromium only; no real screen-reader user session. **Official report: not run** until `frontend_u04.json` (passed) is merged. | `../u04_2026-11-11/` |
| U-06: frontend performance | **Accepted against scoped criteria (D3, 2026-11-11):** LCP ≤ 2.5 s, CLS ≤ 0.1, interaction p95 ≤ 200 ms, no progressive leak; tested laptop and profiles; two slow tiles excluded; TBT for information only. **Official report: not run** until `frontend_u06.json` (passed) is merged. | `../u06_2026-11-11/` |
| C10: interface strings externalised | **Completed** (420-key English dictionary, 0 hardcoded strings, 54/54 rendered scenarios byte-identical) | `../c10_2026-11-11/` |
| Hackathon readiness cleanup | **Completed** | `../hackathon_cleanup_2026-11-11/` |
| IB-5: licence and attribution inventory | **Inventory complete; issues unresolved; formally deferred with interim distribution restrictions (D5, 2026-11-11)** | `../ib5_2026-11-11/` |
| V-04/V-05/V-13/V-14 refresh | Completed 2026-11-11 | `../refresh_v04_v05_v13_v14_2026-11-11/` |

## Validation report: merge assessment
**How the merge workflow works** (`backend/validation/run_validation.py`):
- `python -m validation.run_validation --merge <file> …` **always runs the full pytest suite first** and then **overwrites** `backend/validation/report.json`.
- It rebuilds the report from scratch. Existing external entries (V-09 to V-12) are kept only if their files are merged again.
- Each `--merge` file passes `validation.common.merge_external`, which checks code, suite and kernel fingerprints, the script's test-ID ownership, and the terrain gate for V-09 to V-12.

**Eligible results** (`merge_preview.json`, computed **in memory**, nothing written to the report):

| File | Tests | Guard result | Status after merge |
| --- | --- | --- | --- |
| `../v09_v10_final_2026-11-10/v09_v10.json` | V-09, V-10 | accepted (terrain gate ok) | not run / not run (unchanged) |
| `../v11_final_2026-11-10/v11.json` | V-11 | accepted (terrain gate ok) | passed (unchanged) |
| `../v12_final_2026-11-10/v12.json` | V-12 | accepted (terrain gate ok) | passed (unchanged) |
| `merge_inputs/horizons_v04_only.json` | V-04 | accepted | **not run → passed** |
| `../refresh_v04_v05_v13_v14_2026-11-11/v13_eclipse/v13.json` | V-13 | accepted | **not run → passed** |
| `../refresh_v04_v05_v13_v14_2026-11-11/v14_month/v14.json` | V-14 | accepted | passed (now backed by the month run as well as the pytest form) |

**About `merge_inputs/horizons_v04_only.json`:**
- It is the refreshed `horizons.json` with only the `tests.V-05` entry removed. Everything else, including `meta`, is copied verbatim, and `derived_from` records the source SHA-256.
- It exists because the original file would record **V-05 as `passed`** under the unapproved threshold. With V-05 removed, V-05 stays "not run".
- Generator: `scripts/prepare_merge.py`, log `prepare_merge.log`.

**Not eligible:**
- **The original `horizons.json`:** see V-05 above.
- **U-04:** no result file exists, and writing one that turns "scoped PASS" into `passed` is an acceptance decision (D4).
- **U-06:** no criterion exists (D3).

> **Outcome (2026-11-11):** after a read-only preflight and the user's approval, the merge below was run once with `TEMP`/`TMP` on E: and `PYTHONUTF8=1`. It exited 0 with 438 passed, 2 skipped, 0 failed; no merge was rejected and all 32 verification checks passed. The status column above is now the recorded result (`../phase4_merge_2026-11-11/`). The blocker list below is kept as it stood at the review.

**At the review, the official merge was NOT run. It was blocked on this host:**
1. **Full-suite rerun not established as safe here:**
   - pytest's temporary folder is `C:\Users\…\AppData\Local\Temp` on drive C:, which is **97 % full (6.2 GB free)**.
   - The only recorded Windows suite run (`docs/AUDIT_2026-11.md`, "Cross-platform test findings") had 23 failures caused by a full system drive.
   - Every recorded passing full-suite run comes from a Linux cloud session. No passing full-suite run is recorded on this Windows host.
2. **A known failure on this host:** `tests/test_phase3_labels.py` fails 2 tests on Windows unless Python runs in UTF-8 mode (see "Checks after the edits"). A plain `run_validation` here would therefore end with a non-zero pytest exit code.
3. **A failing or interrupted run would overwrite `report.json`** with a non-zero pytest exit code, which the label rules reject. The instruction for this closure was not to risk existing evidence through an unsafe full-suite rerun.
4. **Report decisions pending:** V-05's handling (D1) and U-04's (D4) should be decided first, so the report is regenerated once.

**To unblock:**
- Free space on C: or point `TEMP`/`TMP` at E: for the run.
- Set `PYTHONUTF8=1`, or run on Linux/CI.
- Copy `report.json` aside.
- Then, from `backend/`:

```bash
python -m validation.run_validation \
  --merge ../docs/validation_evidence/v09_v10_final_2026-11-10/v09_v10.json \
  --merge ../docs/validation_evidence/v11_final_2026-11-10/v11.json \
  --merge ../docs/validation_evidence/v12_final_2026-11-10/v12.json \
  --merge ../docs/validation_evidence/phase4_closure_2026-11-11/merge_inputs/horizons_v04_only.json \
  --merge ../docs/validation_evidence/refresh_v04_v05_v13_v14_2026-11-11/v13_eclipse/v13.json \
  --merge ../docs/validation_evidence/refresh_v04_v05_v13_v14_2026-11-11/v14_month/v14.json
```

**When to run it:** only while the code and suite fingerprints are still those above. Any change to `backend/lunaops`, `backend/tests` or `backend/validation` invalidates every merge file listed.

**What it would not change:** even after this merge, **every label stays "Pending validation"**. V-05, V-09, V-10, U-04 and U-06 would still not have passed, and U-04 and U-06 gate every quantity.

## Outstanding decisions (none taken here)

| # | Decision | Current state | What closes it |
| --- | --- | --- | --- |
| **D1** | **V-05 timing threshold.** **CLOSED 2026-11-11: Phase 1.1 criteria approved (120 s Horizons rise/set via the 1-s centre-crossing substitute; 10 s interpolated one-minute table), evidence accepted; `../d1_v05_decision_2026-11-11/ACCEPTANCE.md`** | At the review: proposed 1.0 s (`EVENT_TOL_S`, `V05_TOL_S` in `horizons_compare.py`); **not approved**. The blueprint's V-05 criterion text is not in the repository. Measured worst case 0.49995 s; it is bounded by the detector's ±0.5 s bisection midpoint. | Approval of a criterion. **If 1.0 s is approved:** the refreshed `horizons.json` already encodes it and can be merged unchanged while the fingerprints hold. **If another value is approved:** change `V05_TOL_S`, rerun `horizons_compare` and regenerate the report. A threshold below 0.5 s would need a finer detector tolerance, which is an algorithm change. |
| **D2** | **V-09/V-10 acceptance criteria.** **DEFERRED 2026-11-11 (`../phase4_remaining_decisions_2026-11-11/DECISIONS_RECORDED.md`)** | Provisional, unapproved: RMSE ≤ 5 pp, abs(bias) ≤ 2 pp. Final run: **V-09** RMSE 14.09 pp, bias −7.19 pp (outside the provisional criteria); **V-10** RMSE 3.13 pp, bias −0.74 pp (inside them). Both are recorded as "not run". The A10 evidence shows V-09 is sensitive to the undocumented AVGVISIB observer height. | Approve (or replace) the criteria and decide the observer-height assumption. Then the script's `CRITERIA` approval flag can be set and V-09/V-10 rerun; that is a validation-script change, which changes the suite fingerprint. |
| **D3** | **U-06 performance criteria.** **ACCEPTED (scoped) 2026-11-11: LCP ≤ 2.5 s, CLS ≤ 0.1, interaction p95 ≤ 200 ms, no progressive leak; `frontend_u06.json` passed, not yet merged** | **No approved U-06 criterion exists**; C05 says "measured performance" without a threshold. The U-06 audit measured bundle size, first paint, interaction latency and memory on stated CPU/network profiles. It also recommends a backend fix for pathological zoom-0/1 tile renders (`api/tiles.py`), not done. | Approve criteria (metric, limit, device and network profile). Then compare the existing measurements or repeat them with the audit scripts, and write a `frontend_u06` result for merging. |
| **D4** | **U-04 audit sign-off and result registration.** **ACCEPTED (scoped, condition met) 2026-11-11: current-build re-audit passed; `frontend_u04.json` passed, not yet merged** | Standalone audit: scoped PASS. **Official report: not run.** Limits: no assistive-technology user session (screen-reader behaviour inferred from Chrome's accessibility tree); one browser engine (Chromium 157); zoom emulated through the viewport; speech input not exercised; empty curated-site list and backend-failure states not rendered live. | Decide whether the scoped PASS satisfies U-04 (or require an NVDA/Narrator spot check, or Firefox/Safari coverage). If accepted, a `frontend_u04` result file must be written and merged. |
| **D5** | **IB-5 licensing and distribution.** **DEFERRED 2026-11-11 with interim distribution restrictions; no clearance claimed** | Inventory complete. **Unresolved:** licences of 44 of 49 vendored native binaries (rasterio ×34, pyproj ×7, msvcp140 ×2, CSPICE); data terms for PGDA 78/81/90, PGDA 69, PDS/LROC, JPL Horizons, NAIF, USGS and ShadowCam; `lerc@3.0.0` licence file missing; GSFC acknowledgment coverage of the per-eclipse PDFs. **Distribution findings, not fixed:** the browser bundle drops 21 packages' licence notices; the OFL text is not shipped with the fonts; `data/reference_validation/` (256 MB, terms unresolved, one file over 100 MB) is not git-ignored. | **A formal deferral is required and has NOT been recorded.** No distribution of `frontend/dist`, of a packaged environment or of the reference rasters should be treated as cleared until each item is resolved or deferred by a named maintainer. No further IB-5 research was done here. |
| **D6** | **Official report regeneration** | **COMPLETED 2026-11-11.** pytest 438 passed, 2 skipped, 0 failed; report entries 417 passed, 5 not run, 2 skipped; V-04, V-11, V-12, V-13 and V-14 passed; V-05, V-09, V-10, U-04 and U-06 not run; SHA-256 `5e6c76d7…db812e7b`; 32/32 checks passed (`../phase4_merge_2026-11-11/`) | Closed. **Regenerated again 2026-11-12** with V-05, U-04 and U-06: `2279606c…` (`../phase4_final_merge_2026-11-12/`). A further regeneration is needed only after a new result (e.g. D2) or any change to the code or suite fingerprint |
| **D7** | **Definition of A15.** **RECORDED AS UNDEFINED 2026-11-11** | No repository record defines A15; still undefined, no scope assumed | The maintainers state what A15 is; this register is then updated |

**Smaller decisions left by earlier tasks (recorded, not decided):**
- **C10:** inline `toLowerCase()` on dictionary text and the English-only number formatting (`../c10_2026-11-11/README.md`, "What is not externalised").
- **Hackathon cleanup:** whether to keep the README "Event rules" disclosure (`../hackathon_cleanup_2026-11-11/README.md`, "For the team to decide").
- **V-11:** PGDA LPSR provenance facts that PGDA does not state (`../v11_a11_2026-11-09/README.md`).

## Documentation reconciled in this review
- **`docs/TRACEABILITY.md`:**
  - rows updated for A03, A04, A05, A07, A10, B19, B23, C02, C05, C10 and the V-09 to V-13 table (their quantity-gate column is unchanged);
  - new "Phase 4 task status" section.
- **`docs/AUDIT_2026-11.md`:**
  - a "Phase 4 closure (2026-11-11)" section;
  - one-line status pointers under the earlier A10, A11 and A12 sections.
- **`README.md`:**
  - the Phase 4 results and Remaining-limitations entries for V-04, V-05, V-13, V-14, U-04, U-06, IB-5 and C10;
  - the protected sentence on line 99 and the validated-requirements block are untouched.
- **`docs/validation_evidence/README.md`:** index of every Phase 4 evidence folder.
- **Not modified:**
  - the A6 acceptance record (`terrain_a6_2026-11-10/ACCEPTANCE.md`) and `terrain_acceptance.json`;
  - every other evidence folder;
  - `ATTRIBUTION.md`, which IB-5 already updated.

## Checks after the edits
`checks.log` holds:
- **Fingerprints:** code, suite and acceptance digest unchanged; algorithm 1.5.0.
- **`report.json`:** SHA-256 unchanged.
- **README line 99:** unchanged.
- **Documentation tests:** `tests/test_phase3_labels.py`, which checks the README block and summary sentence and the TRACEABILITY V-09 to V-13 rows against the code, was run on its own. It is a targeted documentation check, not a repeat of any measurement.
  - **Default Windows run: 16 passed, 2 failed** with `UnicodeDecodeError`. The test reads the files with `Path.read_text()` and no encoding, so Windows decodes UTF-8 as cp1252.
  - **The failing characters were already in the files** before this review ("10⁻⁷" etc. in README, "10⁴-case" and "ρ_up" in TRACEABILITY), so this is a pre-existing Windows portability defect in the test.
  - **Not fixed:** editing a test changes the suite fingerprint and would invalidate every merge file.
  - **With `PYTHONUTF8=1`: 18 of 18 pass,** so the reconciled documents are consistent with the code.

No dependency was installed and no Git operation was run.
