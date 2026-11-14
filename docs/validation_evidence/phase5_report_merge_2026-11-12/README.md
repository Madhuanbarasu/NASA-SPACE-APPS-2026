# Phase 5: approved re-registration of U-04 and U-06 in the official report (2026-11-12)

**Approval:** the project owner explicitly approved merging the refreshed Phase 5 U-04 and U-06 results into `backend/validation/report.json`. The approval covers only this merge and its evidence and documentation.

**Result:** merged with zero rejections. The new official report is **`5135efe88e5feb0fd36e0230ecba9f2d2b99322a70e1e69e822e13def69df53f`** (`run_utc` 2026-11-12T06:27:21Z) and supersedes `2279606c…`.
- **What changed:** U-04 and U-06 stay **passed** and now describe the final Phase 5 frontend.
- **What did not change:** everything else in the report is identical (37/37 checks).

## 1. Pre-merge recheck (`dry_run.py` → `dry_run.log`, `dry_run.json`)
- **Inputs:** the eight files of the Phase 4 final merge, with the two Phase 4 frontend files replaced by the Phase 5 ones:
  - `v09_v10.json`, `v11.json`, `v12.json`, `horizons.json` (V-04/V-05), `v13.json` and `v14.json`;
  - `phase5_final_2026-11-12/frontend_u04_phase5.json` and `frontend_u06_phase5.json`.
- **Hashes:** each input's SHA-256 equals its recorded value. The six science files are checked against `phase4_final_merge_2026-11-12/dry_run.json`, the two Phase 5 files against `phase5_final_2026-11-12/SHA256SUMS`.
- **Merge guard (`validation.common.merge_external`, in memory):**
  - all eight files carry the current code and suite fingerprints, the production kernel profile and the loaded kernel set;
  - each reports only the test IDs its owner script may report;
  - **zero rejections**.
- **Projection against the live report:** the only differences are the `detail` and `run_utc` of U-04 and U-06. Both stay "passed", with the Phase 5 detail. This agrees with the earlier dry run in `phase5_final_2026-11-12/merge_dry_run_phase5.json`.

## 2. Backup and merge
- **Backup:** `report_before.json` is a byte copy of the previous report, verified as `2279606ceab9354b8616ba9216e12e89e399f34cfc3cbfcbd7502d12d077d376` before the run.
- **Command:** the existing project procedure (as in `phase4_final_merge_2026-11-12/`), run once from `backend/` with `TEMP`/`TMP` = `E:\Temp\LUNA-OPS` and `PYTHONUTF8=1`. Full output is in `run_validation.log`.
  ```
  .venv/Scripts/python.exe -m validation.run_validation \
    --merge ../docs/validation_evidence/v09_v10_final_2026-11-10/v09_v10.json \
    --merge ../docs/validation_evidence/v11_final_2026-11-10/v11.json \
    --merge ../docs/validation_evidence/v12_final_2026-11-10/v12.json \
    --merge ../docs/validation_evidence/refresh_v04_v05_v13_v14_2026-11-11/v04_horizons/horizons.json \
    --merge ../docs/validation_evidence/refresh_v04_v05_v13_v14_2026-11-11/v13_eclipse/v13.json \
    --merge ../docs/validation_evidence/refresh_v04_v05_v13_v14_2026-11-11/v14_month/v14.json \
    --merge ../docs/validation_evidence/phase5_final_2026-11-12/frontend_u04_phase5.json \
    --merge ../docs/validation_evidence/phase5_final_2026-11-12/frontend_u06_phase5.json
  ```
- **Run:** ended 2026-11-12T06:27:21Z after 860 s, **exit code 0**.
- **pytest:** **438 passed, 2 skipped, 0 failed**, the same as the previous merge. The skips are the two sandbox-only kernel-setup tests; the only warning is the known Starlette deprecation.
- **Report entries:** 420 passed, 2 not run, 2 skipped.
- **Copy:** `report_after.json` is a byte copy of the new report. **No restore was needed.**

## 3. Verification (`verify_merge.py` → `verify_merge.log`, `verification.json`): 37/37 checks passed
- **Run integrity:**
  - `run_validation` exited 0;
  - pytest had 0 failed and 0 errors, with the same counts as before;
  - `pytest_exit_code` is 0;
  - there is no "NOT merged" line, and `rejected_merges` is `{}`.
- **Build:**
  - algorithm 1.5.0;
  - code `5bf9753f…` and suite `1632af16…`, both equal to the current build and to the previous report;
  - production kernels, SHA-256 equal to the loaded set;
  - terrain acceptance `e48eb8ed…`;
  - label-rules digest current;
  - no label blockers.
- **Nothing else changed:**
  - every report-level field except `run_utc` is identical to the previous report;
  - the same test entries are present, and every status is unchanged;
  - every other external entry (V-04, V-05, V-09 to V-14) is byte-identical;
  - all automated (pytest) entries are identical;
  - status counts are unchanged.
- **U-04 and U-06:**
  - both are "passed", external, from scripts `frontend_u04` and `frontend_u06`;
  - their detail and `run_utc` (2026-11-12T06:06:55Z) are those of the Phase 5 result files;
  - the previous entries (2026-11-11T18:19:06Z) described the Phase 4 build.
- **Labels:** identical to the previous report.
  - Status page: `sun_earth_azel` and `horizon` are Validated; `disk_visibility`, `events` and `power_indicator` are Pending validation.
  - In results with horizon σ, `horizon` stays Pending (L_corr limitation).

**Fingerprints after the merge:** `backend_fingerprints_after.txt` (unchanged; report hash `5135efe8…`).

## 4. Not changed
- **Backend:** backend source code, the test suite and its fingerprint, and algorithm 1.5.0 are unchanged.
- **Scope of the approval:** the IB-5 deferral (D5) is not changed, nor is the deferral of V-09/V-10 (D2).
- **Earlier evidence:** no earlier evidence file was modified. The Phase 5 final folder still records the pre-merge state ("not merged"); this folder records the merge.

No Git command was run.
