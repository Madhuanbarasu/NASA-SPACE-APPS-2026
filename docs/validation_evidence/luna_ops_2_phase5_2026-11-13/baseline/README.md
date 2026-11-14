# Phase 5 baseline (saved 2026-11-13, before any Phase 5 change)

| File | Contents |
|---|---|
| `backend_fingerprints.txt` | Algorithm 1.5.0, code fingerprint `84cbd4ea…`, suite fingerprint `1632af16…`, terrain acceptance digest `e48eb8ed…`, SHA-256 of `backend/validation/report.json` (`8c03ebaf…`). Same values as the Phase 4 baseline. |
| `code_fingerprint_scope.txt` | Every file the code fingerprint hashes: all `.py` files under `backend/lunaops` (25) plus `backend/lunaops/manifests/*.json` (2). |
| `suite_fingerprint_scope.txt` | Every file the suite fingerprint hashes: all `.py` files under `backend/tests` and `backend/validation` (44). |
| `backend_lunaops_sha256.txt` | SHA-256 of each engine source file. |
| `frontend_files_sha256.txt` | 83 frontend source and configuration files. Identical to the Phase 4 final state (`luna_ops_2_phase4_2026-11-13/logs/frontend_files_after_ui_fixes2_sha256.txt`; order-independent comparison). |
| `frontend/` and `frontend_snapshot_SHA256SUMS` | A copy of the frontend sources and configuration, with their hashes. |
| `dist_sha256.txt` | The Phase 4 production build. Identical to `dist_after_ui_fixes2_sha256.txt` of Phase 4. |
| `data/registry.json` | Copy of the production terrain registry (5 m PGDA 78 Site01; 20, 80 and 240 m PGDA 90; with their error maps). |
| `data/datasets.json` | Copy of the dataset manifest (product pages, frames, citations). |
| `startup_and_registry_sha256.txt` | SHA-256 of `start.py`, `backend/requirements.txt`, `data/dem/registry.json` and `datasets.json`. |
| `existing_evidence_folders.txt` | The evidence folders present before Phase 5. All are preserved. The Phase 1–4 `SHA256SUMS` manifests still verify after Phase 5 (README, "Integrity"). |

**Before screenshots.** The app before Phase 5 is the Phase 4 final build: the dist hashes above equal those of the Phase 4 second UI review. Its screenshots are in `../../luna_ops_2_phase4_2026-11-13/ui_fixes2_after/screenshots/`, for the Mission dashboard at 1440, 1024 and 390 px, Data and Guide, and the South Polar Map on phones.
- There was no Landing view before Phase 5, so no before screenshot of it exists.
- The top-bar overflow found during Phase 5 was measured on the five-tab bar. Its numbers are in `../logs/11_topbar_before_css_change.txt`.
