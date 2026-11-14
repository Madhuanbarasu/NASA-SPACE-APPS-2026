# Phase 4 validation merge, 2026-11-11

**Result: MERGE SUCCEEDED and all 32 verification checks passed. No restore was needed.**
- The official report `backend/validation/report.json` was regenerated with the six approved result files.
- V-04 and V-13 now record **passed**. V-05, V-09, V-10, U-04 and U-06 remain **not run**.
- **Every quantity label is still "Pending validation"**, because V-05, V-09, V-10, U-04 and U-06 have not passed.
- **Phase 4 is not complete:** decisions D1–D5 and D7 in `../phase4_closure_2026-11-11/README.md` are still open; D6, regenerating the report, is done by this merge.

## Run
- **Approval:** the user approved the merge on 2026-11-11 after a read-only preflight.
- **Environment:**
  - `TEMP` and `TMP` were `E:\Temp\LUNA-OPS` and `PYTHONUTF8=1`, set for the session; Python resolved its temporary directory to E:.
  - Windows 11, Python 3.13.7, `backend/.venv`.
- **Backup:** `report_before.json`, a byte copy of the previous `report.json` with SHA-256 `00d2cda1bf3fe38fe98cc8a76e92acabdf9cb771ab900119750203586b15c239`. It was verified before the run and again afterwards. It is also identical to `../report_production_merged.json`.
- **Command:** run once from `backend/`; full output in `run_validation.log`.
  ```
  .venv/Scripts/python.exe -m validation.run_validation \
    --merge ../docs/validation_evidence/v09_v10_final_2026-11-10/v09_v10.json \
    --merge ../docs/validation_evidence/v11_final_2026-11-10/v11.json \
    --merge ../docs/validation_evidence/v12_final_2026-11-10/v12.json \
    --merge ../docs/validation_evidence/phase4_closure_2026-11-11/merge_inputs/horizons_v04_only.json \
    --merge ../docs/validation_evidence/refresh_v04_v05_v13_v14_2026-11-11/v13_eclipse/v13.json \
    --merge ../docs/validation_evidence/refresh_v04_v05_v13_v14_2026-11-11/v14_month/v14.json
  ```
- **Timing:** 2026-11-11 17:00:42 to 17:24:21 UTC (1,419 s), **exit code 0**.
- **pytest:** **438 passed, 2 skipped, 0 failed** (1,417 s).
  - The 2 skips are the sandbox-only kernel-setup tests: `test_demo_lock_in_production_folder_is_refused_then_migrated` and `test_verify_kernels_passes_then_catches_tampering`. Both need the sandbox kernel set as the session's source, and the same 2 were skipped in the previous report.
  - The only warning is the known Starlette TestClient deprecation.
- **Merges:** none rejected; there was no `NOT merged` output and `rejected_merges` is `{}`.
- **New report:** `report_after.json` is a byte copy of the new `report.json`, SHA-256 `5e6c76d75eff6c3454f68edc76ab5e08f48733e3ad2cfff72eac3e55db812e7b`, `run_utc` 2026-11-11T17:24:21Z.
  - Report entries: 417 passed, 5 not run, 2 skipped.

## Verification (`verify_merge.py` → `verification.json`, `verify_merge.log`): 32/32 passed
**Report integrity:**
- **pytest:** exit code 0.
- **Merges:** zero rejected.
- **Fingerprints:**
  - code `5bf9753f…37d2f8` and suite `1632af16…6d75eabc`, both equal to the current build;
  - kernel profile production, with the 7 kernel SHA-256s equal to the loaded kernels;
  - label-rules digest `8d8e229fd52cbe79` (current).
- **Terrain:** 4 terrain products recorded, unchanged from the previous report. The terrain acceptance digest `e48eb8ed…` is unchanged.
- **Algorithm:** version 1.5.0.
- **Label blockers:** none at report level (`provenance.label_blockers` is empty).

**Statuses:**

| Test | Before | After | Source |
| --- | --- | --- | --- |
| V-04 | not run | **passed** | external, `horizons_compare` (V-04-only file) |
| V-05 | not run | **not run** | not merged: the 1.0 s threshold is not approved |
| V-09 | not run | not run | external, `v09_v10_avgvisib` (criteria unapproved) |
| V-10 | not run | not run | external, `v09_v10_avgvisib` (criteria unapproved) |
| V-11 | passed | passed | external, `v11_psr` |
| V-12 | passed | passed | external, `v12_lroc` |
| V-13 | not run | **passed** | external, `v13_eclipse` |
| V-14 | passed (pytest form) | passed | external month run `v14_month` and the automated form |
| U-04 | not run | not run | no `frontend_u04` result (D4) |
| U-06 | not run | not run | no approved criterion (D3) |

**Further checks:**
- **Not passed:** V-05, V-09, V-10, U-04 and U-06 are **not** marked passed.
- **No failures:** no entry anywhere in the report, blueprint or other, is `failed`.
- **Automated statuses:** every automated blueprint status (V-01 to V-03, V-06 to V-08b, U-01 to U-03, U-05, U-07, etc.) is unchanged from the previous report.

**Labels**, computed with the engine's own rule (`provenance.compute_labels`): every quantity is **Pending validation**:
- **`sun_earth_azel`:** blocked only by U-04 and U-06;
- **`horizon`:** also blocked only by U-04 and U-06;
- **the other quantities:** additionally blocked by V-05, V-09 and/or V-10, as listed in `verification.json`.

## Not changed
- **Code and criteria:** scientific code, thresholds, acceptance records (`terrain_acceptance.json` and the A6 `ACCEPTANCE.md`) and the merge inputs.
- **Evidence:** every existing evidence folder, including `../report_production_merged.json`, which still holds the previous report as history.
- **Other:** no dependency was installed and no Git operation was run.

## Documentation now out of date (not edited here)
These statements were true before this merge and now need updating in a documentation step:
- `README.md`, `docs/TRACEABILITY.md`, `docs/AUDIT_2026-11.md` and `docs/validation_evidence/README.md` say the official report "has not been regenerated" and that the live report lists V-04 and V-13 as not run;
- `../phase4_closure_2026-11-11/README.md`, decision D6, is that same open item. It is now done, but the closure folder is checksummed evidence and was left unchanged.

## Files
| File | Contents |
| --- | --- |
| `report_before.json` | Previous `report.json` (backup, `00d2cda1…`) |
| `report_after.json` | New `report.json` (`5e6c76d7…`) |
| `run_validation.log` | Full output of the merge run, with the command, environment and exit code |
| `verify_merge.py` | Read-only verification script, kept outside `backend/` so the suite fingerprint is unaffected |
| `verify_merge.log`, `verification.json` | Verification output: every check, the before/after statuses and the labels with their reasons |
| `SHA256SUMS` | Checksums of every file in this folder |
