# Post-Phase 5 Official Validation Report Merge

**Merge Directory:** `docs/validation_evidence/post_phase5_backend_and_ui_fixes_2026-11-12/report_merge/`  
**Date:** 2026-11-12  
**Platform:** Windows 11 (HP Laptop 15-fd0xxx, Intel Core 5 120U, 15.7 GB RAM)  
**Approval:** Explicit user authorization granted for the eight-file official report merge into `backend/validation/report.json`.

---

## 1. Executive Summary

The official validation report [`backend/validation/report.json`](file:///e:/LUNA-OPS/backend/validation/report.json) has been successfully regenerated and merged via the project's standard procedure (`validation.run_validation`).
- **Before SHA-256:** `5135efe88e5feb0fd36e0230ecba9f2d2b99322a70e1e69e822e13def69df53f` (archived byte-for-byte in `report_before.json`)
- **After SHA-256:** `8c03ebafc72c5c41a238565f51464413bd63f3132302491cc518587d93ebe10d` (archived in `report_after.json`)
- **Pytest Exit Code:** `0` (438 passed, 0 failed, 2 skipped in 2,436.54 s)
- **Rejected Merges:** `{}` (zero rejections across all eight candidate files)
- **Preserved Unrelated Tests:** All 414 unrelated test cases in the report are identical between `report_before.json` and `report_after.json` (0 modified, 0 dropped).
- **Preserved Approved Deferrals:**
  - `V-09` and `V-10` remain explicitly deferred with status `not run` (provisional acceptance criteria preserved).
  - `IB-5` licensing and notices deferral remains preserved.
- **Active Mission View at 320 px:** The previous 3 px text overflow in the active Mission dashboard is completely resolved (`docScrollW: 320`, `horizontalScroll: false`, `offenders: []`). All 10 views in the application now record **0 automated problems**.

---

## 2. Pre-Merge Safety Checks & Dry Run

Pre-merge safety checks were performed using `dry_run.py` $\to$ recorded in `dry_run.json`:
- **Current Environment Fingerprints:**
  - `code_fingerprint`: `84cbd4ea34f6606abcd32e02df295f204cb97ca9bef3d9a4d455b4557c831109`
  - `suite_fingerprint`: `1632af16763dda4e27909a9af3d2fdd903b0d58951faacded72c4cf06d75eabc`
  - `terrain_acceptance_digest`: `e48eb8ed0ca2003c2769c60932323dbce34385e4eac2a675f076e13bbd943dce`
  - `kernel_profile`: `production`

### Merged Candidate Files & Hashes

| Candidate File | Producing Script | Target Tests | Candidate SHA-256 | Merge Guard Status |
| :--- | :--- | :--- | :--- | :--- |
| `horizons.json` | `horizons_compare` | `V-04`, `V-05` | `cdd023498603951f2f01f30141f234bf992bf9b8f2d8479e0996843ae8cb8fd3` | Accepted (0 rejections) |
| `v09_v10.json` | `v09_v10_avgvisib` | `V-09`, `V-10` | `6a0cd6f4618ef45e032ae38b25867f1367ea70711aa492167448e8a6042db0b7` | Accepted (0 rejections) |
| `v11.json` | `v11_psr` | `V-11` | `b113fe154a3d50a80dc2463e8a7ea3fa1e974e648cb94998797fbc6494e77dd6` | Accepted (0 rejections) |
| `v12.json` | `v12_lroc` | `V-12` | `fd4ee5b7c6cd6c79a929654d6fa7c5eaee110594dbf06821d3f9e9a4f66a9a7a` | Accepted (0 rejections) |
| `v13.json` | `v13_eclipse` | `V-13` | `697e8037c8441b67f10b7f6aa5ef897d26ba427181c015b6d58548ceef0fe550` | Accepted (0 rejections) |
| `v14.json` | `v14_month` | `V-14` | `bfaf3f0b72afacf3ce8c48a80d4620f5be870da4142f10b91d2f7881c9ba339d` | Accepted (0 rejections) |
| `frontend_u04.json` | `frontend_u04` | `U-04` | `400314ac85fc3d63bbba2eb7d8c6fec91e2b4f69f20e4e612cb3e46ca7981bdf` | Accepted (0 rejections) |
| `frontend_u06.json` | `frontend_u06` | `U-06` | `c13b480eefcef37f84813ea596f244199127bcfb95d2cb77ef7d87bc41a3a609` | Accepted (0 rejections) |

---

## 3. Merge Execution Details

**Execution Command:**
```powershell
cd backend
.\.venv\Scripts\python.exe -u -m validation.run_validation `
  --merge ../docs/validation_evidence/post_phase5_backend_and_ui_fixes_2026-11-12/validation/v09_v10.json `
  --merge ../docs/validation_evidence/post_phase5_backend_and_ui_fixes_2026-11-12/validation/v11.json `
  --merge ../docs/validation_evidence/post_phase5_backend_and_ui_fixes_2026-11-12/validation/v12.json `
  --merge ../docs/validation_evidence/post_phase5_backend_and_ui_fixes_2026-11-12/validation/v04_horizons/horizons.json `
  --merge ../docs/validation_evidence/post_phase5_backend_and_ui_fixes_2026-11-12/validation/v13.json `
  --merge ../docs/validation_evidence/post_phase5_backend_and_ui_fixes_2026-11-12/validation/v14.json `
  --merge ../docs/validation_evidence/post_phase5_backend_and_ui_fixes_2026-11-12/frontend_u04.json `
  --merge ../docs/validation_evidence/post_phase5_backend_and_ui_fixes_2026-11-12/frontend_u06.json
```

**Execution Log:** [`run_validation.log`](file:///e:/LUNA-OPS/docs/validation_evidence/post_phase5_backend_and_ui_fixes_2026-11-12/report_merge/run_validation.log)  
**Execution Time:** 2,436.54 s (~40 minutes)  
**Exit Code:** `0`  
**Test Summary:** 438 passed, 0 failed, 2 skipped  
**Report Summary:** `{'passed': 420, 'not run': 2, 'skipped': 2}`

---

## 4. Post-Merge Verification

Post-merge verification script [`verify_merge.py`](file:///e:/LUNA-OPS/docs/validation_evidence/post_phase5_backend_and_ui_fixes_2026-11-12/report_merge/verify_merge.py) validated:
1. **Report Status Counts:**
   - Total Tests in Report: 424
   - Passed: 420
   - Not Run: 2 (`V-09`, `V-10` provisional deferrals)
   - Skipped: 2 (kernel setup sandbox migration tests)
2. **Preservation of Unrelated Tests:**
   - 414 unrelated test cases checked between `report_before.json` and `report_after.json`.
   - **0 differences detected.**
3. **Owned External Tests Verified:**
   - `V-04`: `passed` (`horizons_compare`)
   - `V-05`: `passed` (`horizons_compare`)
   - `V-09`: `not run` (`v09_v10_avgvisib`)
   - `V-10`: `not run` (`v09_v10_avgvisib`)
   - `V-11`: `passed` (`v11_psr`)
   - `V-12`: `passed` (`v12_lroc`)
   - `V-13`: `passed` (`v13_eclipse`)
   - `V-14`: `passed` (`v14_month`)
   - `U-04`: `passed` (`frontend_u04`)
   - `U-06`: `passed` (`frontend_u06`)

---

## 5. Active Mission View at 320 px (Post-Merge Audit)

With the official report updated to code fingerprint `84cbd4ea...`, the live server was audited on port `8765` using `check_mission_reflow.py`:
* **Audit Record:** [`u04_postmerge/audit-postmerge.json`](file:///e:/LUNA-OPS/docs/validation_evidence/post_phase5_backend_and_ui_fixes_2026-11-12/report_merge/u04_postmerge/audit-postmerge.json)

```json
"reflow320": {
  "viewport": 320,
  "docScrollW": 320,
  "horizontalScroll": false,
  "offenders": [],
  "offenderCount": 0
}
```

* **Outcome:** The previous 3 px text overflow disappeared completely. The label chip now renders `"Sun: geometric, validated"` instead of the long discrepancy warning, fitting neatly within the 320 px container with zero horizontal scrolling.
* **Application-Wide Reflow:** All 10 views in the application record **0 automated problems** across all checks.

---

## 6. Verification Manifests

- Pre-merge backup: [`report_before.json`](file:///e:/LUNA-OPS/docs/validation_evidence/post_phase5_backend_and_ui_fixes_2026-11-12/report_merge/report_before.json) (SHA-256: `5135efe88e5feb0fd36e0230ecba9f2d2b99322a70e1e69e822e13def69df53f`)
- Post-merge report: [`report_after.json`](file:///e:/LUNA-OPS/docs/validation_evidence/post_phase5_backend_and_ui_fixes_2026-11-12/report_merge/report_after.json) (SHA-256: `8c03ebafc72c5c41a238565f51464413bd63f3132302491cc518587d93ebe10d`)
- Full Verification Record: [`verification.json`](file:///e:/LUNA-OPS/docs/validation_evidence/post_phase5_backend_and_ui_fixes_2026-11-12/report_merge/verification.json)

