# Phase 4 final validation merge and closure report (2026-11-12)

**Verdict: Phase 4 COMPLETE WITH APPROVED DEFERRALS** (basis and conditions in §5).
- **The scope of this verdict:** it closes the Phase 4 work programme. It does **not** make every product label Validated.
  - `sun_earth_azel` is Validated.
  - `horizon` is Validated on the status page and stays Pending in results that carry horizon uncertainty.
  - `disk_visibility`, `events` and `power_indicator` stay **Pending validation**.

## 1. Pre-merge verification (`dry_run.py` → `dry_run.log`, `dry_run.json`)
- **Decision records verified:** `SHA256SUMS` passes for `../d1_v05_decision_2026-11-11/` (D1) and `../phase4_remaining_decisions_2026-11-11/` (D2–D5, D7, result files), as well as the closure, first-merge and refresh folders.
- **Environment:** `TEMP`/`TMP` = `E:\Temp\LUNA-OPS` and `PYTHONUTF8=1`. Python resolves its temporary directory to E: and runs in UTF-8 mode; 142 GB were free on E:.
- **Build:** algorithm 1.5.0; code `5bf9753f…37d2f8`; suite `1632af16…6d75eabc`; terrain acceptance `e48eb8ed…943dce`; production kernels.
- **Inputs:** all eight carry these fingerprints and the loaded kernel SHA-256s, and each reports only the test IDs its script owns.
  - Their SHA-256s are recorded in `dry_run.json`.
  - The refresh and decision-folder files also match their folders' `SHA256SUMS`.
  - D1 is approved, so the **full** refreshed `horizons.json` (V-04 and V-05) replaces the earlier V-04-only copy.
- **No-write dry run:** `validation.common.merge_external` in memory gave **zero rejected merges**, with exactly the statuses listed in §3.

## 2. Protected regeneration of the official report
- **Backup:** `report_before.json`, a byte copy of the previous `backend/validation/report.json`, verified as `5e6c76d75eff6c3454f68edc76ab5e08f48733e3ad2cfff72eac3e55db812e7b` before the run.
- **Command:** run once from `backend/`, with the full output in `run_validation.log`.
  ```
  .venv/Scripts/python.exe -m validation.run_validation \
    --merge ../docs/validation_evidence/v09_v10_final_2026-11-10/v09_v10.json \
    --merge ../docs/validation_evidence/v11_final_2026-11-10/v11.json \
    --merge ../docs/validation_evidence/v12_final_2026-11-10/v12.json \
    --merge ../docs/validation_evidence/refresh_v04_v05_v13_v14_2026-11-11/v04_horizons/horizons.json \
    --merge ../docs/validation_evidence/refresh_v04_v05_v13_v14_2026-11-11/v13_eclipse/v13.json \
    --merge ../docs/validation_evidence/refresh_v04_v05_v13_v14_2026-11-11/v14_month/v14.json \
    --merge ../docs/validation_evidence/phase4_remaining_decisions_2026-11-11/frontend_u04.json \
    --merge ../docs/validation_evidence/phase4_remaining_decisions_2026-11-11/frontend_u06.json
  ```
- **Run:** 2026-11-11 18:34:48 to 18:57:18 UTC (1,350 s; 2026-11-12 local time), **exit code 0**.
- **pytest:** **438 passed, 2 skipped, 0 failed** (1,345.9 s). The skips are the two sandbox-only kernel-setup tests, the same as in earlier reports. The only warning is the known Starlette TestClient deprecation.
- **New `backend/validation/report.json`:**
  - SHA-256 **`2279606ceab9354b8616ba9216e12e89e399f34cfc3cbfcbd7502d12d077d376`**, `run_utc` 2026-11-11T18:57:17Z;
  - copied byte for byte to `report_after.json`;
  - **report entries: 420 passed, 2 not run, 2 skipped.**
- **No restore was needed.**

## 3. Verification of the final report (`verify_final.py` → `verify_final.log`, `verification.json`): 32/32 checks passed
- **Run integrity:**
  - `run_validation` exited 0; pytest output has no failures or errors; `pytest_exit_code` is 0;
  - there is no `NOT merged` line and `rejected_merges` is `{}`.
- **Build:**
  - algorithm 1.5.0;
  - code and suite fingerprints equal to the current build;
  - production kernels with the 7 SHA-256s equal to the loaded set;
  - terrain acceptance digest unchanged;
  - terrain products unchanged;
  - label-rules digest current;
  - no report-level label blockers.

| Test | Before (`5e6c76d7…`) | After (`2279606c…`) | Source |
| --- | --- | --- | --- |
| V-04 | passed | **passed** | `horizons_compare` (full file) |
| V-05 | not run | **passed** | `horizons_compare`; D1 maps its 1.0 s internal check to the approved Phase 1.1 criteria |
| V-09 | not run | **not run** | `v09_v10_avgvisib`; deferred (D2) |
| V-10 | not run | **not run** | `v09_v10_avgvisib`; deferred (D2) |
| V-11 | passed | **passed** | `v11_psr` |
| V-12 | passed | **passed** | `v12_lroc` |
| V-13 | passed | **passed** | `v13_eclipse` |
| V-14 | passed | **passed** | `v14_month` and the automated form |
| U-04 | not run | **passed** | `frontend_u04` (scoped, D4) |
| U-06 | not run | **passed** | `frontend_u06` (scoped, D3) |

**Status checks:**
- **No unsupported PASS:** the only newly passed IDs are exactly V-05, U-04 and U-06.
- **No failures:** no entry anywhere is `failed`.
- **Automated statuses:** every automated (non-external) status is unchanged.

**Product labels**, computed with the engine's own rule (`provenance.compute_labels`):

| Quantity | Status page (no result) | Analysis result with horizon sigma | Reason still pending |
| --- | --- | --- | --- |
| `sun_earth_azel` | **Validated** | **Validated** | none |
| `horizon` | **Validated** | Pending validation | L_corr = 250 m is an uncalibrated assumption (horizon uncertainty depends on it) |
| `disk_visibility` | Pending validation | Pending validation | V-09, V-10 not run (D2) |
| `events` | Pending validation | Pending validation | V-09, V-10 not run (D2); L_corr in results |
| `power_indicator` | Pending validation | Pending validation | V-09 not run (D2); L_corr in results |

**Further label conditions in the engine** (unchanged):
- Results computed on synthetic terrain carry "Synthetic test terrain - not a lunar result" for the terrain quantities.
- A result's terrain products must be listed in the report's `terrain_products`.

## 4. Decisions and their effect

| Decision | Outcome | Record |
| --- | --- | --- |
| D1 V-05 criteria | Accepted (Phase 1.1: 120 s via the centre-crossing substitute; 10 s one-minute table). **Now passed in the report.** | `../d1_v05_decision_2026-11-11/ACCEPTANCE.md` |
| D2 V-09/V-10 | **Deferred.** No criteria approved; V-09 RMSE 14.09 pp, bias −7.19 pp; V-10 RMSE 3.13 pp, bias −0.74 pp; observer height unresolved. **Not run in the report.** | `../phase4_remaining_decisions_2026-11-11/DECISIONS_RECORDED.md` |
| D3 U-06 | Accepted, scoped (LCP ≤ 2.5 s, CLS ≤ 0.1, interaction p95 ≤ 200 ms, no progressive leak; tested laptop and profiles; two slow tiles excluded). **Now passed.** | same |
| D4 U-04 | Accepted, scoped (the current-build re-audit passed; Chromium only; no screen-reader user session). **Now passed.** | same |
| D5 IB-5 | **Deferred**, with interim distribution restrictions R1–R5; no licensing clearance | same |
| D6 Report regeneration | Completed 2026-11-11 (`5e6c76d7…`), and **again now** (`2279606c…`) | `../phase4_merge_2026-11-11/`, this folder |
| D7 A15 | Recorded as undefined; not a completion criterion | same |

## 5. Phase 4 exit-criteria evaluation and verdict
**No written Phase 4 exit criteria exist in the repository.**
- **Search:** the repository was searched for "exit criteria", "definition of done" and "phase 4 complete". The Phase 1.1 blueprint, the declared source of truth, is not in the repository.
- **What the criteria below are based on:** the project's own Phase 4 records (the AUDIT Phase 4 sections, the closure register and TRACEABILITY). **These are derived criteria, not quoted ones.**

| # | Exit criterion (derived) | Status | Evidence |
| --- | --- | --- | --- |
| E1 | Every defined Phase 4 task A1–A14 is executed with evidence | **Met.** A1–A9 and A11–A14 completed; A10 measured with evidence | closure register |
| E2 | Every Phase 4 external validation (V-04, V-05, V-09 to V-14) is decided: passed or owner-approved deferral | **Met.** V-04, V-05, V-11 to V-14 passed; V-09/V-10 deferred by approval (D2) | §3, D2 |
| E3 | U-04 and U-06 are decided against owner-approved criteria | **Met.** Both accepted, scoped, and passed in the report | D3, D4 |
| E4 | The official report is regenerated from the current build: pytest 0 failures, 0 rejected merges, current fingerprints, production kernels | **Met** | §2–3 |
| E5 | Every open decision has a recorded owner outcome | **Met.** D1–D7 recorded | §4 |
| E6 | IB-5 licence inventory complete; unresolved items formally handled | **Met by approved deferral** (D5); **no clearance** | D5 |
| E7 | Documentation and traceability synchronised with verified evidence | **Met by this closure step** (§6) | §6 |
| E8 | Labels honest: nothing Validated whose gates are unmet | **Met.** Only `sun_earth_azel` (and `horizon` on the status page) are Validated, by the engine rule | §3 |

**Verdict: COMPLETE WITH APPROVED DEFERRALS.**
- **Every derived criterion is met.** E2 and E6 are met only through owner-approved deferrals (D2, D5). A15 is excluded by D7.
- **Condition:** if the Phase 1.1 blueprint makes V-09/V-10 passes or licensing clearance a **non-deferrable** Phase 4 exit criterion, this verdict does not hold, and Phase 4 would be NOT COMPLETE until those items are resolved. The owner should confirm this against the blueprint.

## 6. Unresolved future work (not Phase 4 blockers under the approved deferrals; none started here)
1. **V-09/V-10 (D2):**
   - establish AVGVISIB's observer height;
   - approve criteria **before** a new run;
   - rerun. This changes the suite fingerprint, so every external result must be regenerated.
   - **Until then:** `disk_visibility`, `events` and `power_indicator` stay Pending.
2. **IB-5 (D5):**
   - resolve the 44 native-library licences, the data terms, `lerc` and GSFC figure coverage;
   - add a third-party notices file and the OFL text to `frontend/dist`;
   - git-ignore `data/reference_validation/`;
   - restrictions R1–R5 apply until then.
3. **L_corr calibration:** the horizon uncertainty's 250 m correlation length is an uncalibrated assumption, so `horizon`, `events` and `power_indicator` stay Pending in results with sigma.
4. **U-06 backend tile fix:** slow low-zoom basemap tiles (`api/tiles.py`). It is a backend code change: new code fingerprint, everything regenerated.
5. **U-04 extensions:** an assistive-technology (NVDA/Narrator) spot check, and Firefox/Safari, before any formal conformance claim.
6. **U-06 extensions:** more devices and samples, and field data, before any Core Web Vitals claim.
7. **V-05 extension:** a direct Horizons RTS comparison with LUNA-OPS limb events (the limb-versus-centre limitation).
8. **Housekeeping:**
   - `tests/test_phase3_labels.py` reads the docs with the platform default codec, so it fails on Windows without `PYTHONUTF8=1`. Fixing it changes the suite fingerprint.
   - C10 inline lower-casing and number formatting.
   - The README "Event rules" disclosure decision.
   - The V-11 LPSR provenance facts that PGDA does not state.
9. **A15:** to be added only if an authoritative definition is supplied (D7).

## 7. Files in this folder
| File | Contents |
| --- | --- |
| `README.md` | This closure report |
| `dry_run.py`, `dry_run.log`, `dry_run.json` | Pre-merge no-write dry run of the eight files |
| `report_before.json` | Previous official report (`5e6c76d7…`), backup |
| `run_validation.log` | Full merge output, command, environment and exit code |
| `report_after.json` | New official report (`2279606c…`), byte copy |
| `verify_final.py`, `verify_final.log`, `verification.json` | 32 verification checks, statuses, and labels with reasons |
| `doc_checks_final.py`, `doc_checks_final.log` | Documentation consistency checks after the closure updates |
| `SHA256SUMS` | Checksums of every file in this folder |
