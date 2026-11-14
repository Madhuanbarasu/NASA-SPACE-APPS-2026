# Phase 7 final validation evidence (2026-11-14)

The summary is in `reports/PHASE7_FINAL_REPORT.md`.

**Fingerprints:**
- engine `9cd7b08b36ba6be4fe0e623ff0a8b04da4dae15b1f9867e496927ff945dd73c8`
- suite `70606628abed3fdee2704e0b8e2891f648da27266b04791d7690531a517cd546`

| Folder | Contents |
|---|---|
| `scientific_criteria/` | Frozen V-09/V-10 criteria (`FROZEN_CRITERIA.md` with sha256 and UTC time), the NASA PGDA readme |
| `V09_holdout/`, `V10_holdout/` | Frozen holdout points (checksummed before the run), results, V-10 failure diagnosis |
| `engine_regression/external/` | V-09/V-10 holdout, V-13, V-14, V-04/V-05, V-11, V-12 results and logs (`chain_progress.txt`) |
| `engine_regression/pytest/` | Partial full-suite log (stopped by the owner), collection order, partial summary, failure list |
| `engine_regression/` (top level) | Landing reference reproduction |
| `report_regeneration/` | Preserved pre-Phase 7 report, interim report, historical-report and checksum verification |
| `accessibility/` | U-04 audit (before fixes, interim, final), `frontend_u04.json`, originals of changed frontend files |
| `performance/` | U-06 evaluator (not yet run: needs the server) |
| `application_e2e/`, `responsive_design/` | E2E, live checks, app checks, responsive results and screenshots |
| `event_detection/`, `power_indicator/`, `earth_disk/` | Event, power, relay checks (Earth disk reused from `scientific_validation_followup_2026-11-14/disk_visibility/`) |
| `cache_integrity/` | Cache integrity at the start of Phase 7 |
| `scripts/` | Every script used in Phase 7 |
| `logs/` | Numbered command logs, including `35_interruption_low_memory.txt` |

`SHA256SUMS` covers every file in this folder except itself.
