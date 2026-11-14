# Phase 6 baseline (saved 2026-11-13, before any Phase 6 change)

| File | Contents |
|---|---|
| `backend_fingerprints.txt` | Algorithm 1.5.0, code fingerprint `84cbd4ea…`, suite fingerprint `1632af16…`, terrain acceptance digest `e48eb8ed…`, `report.json` SHA-256 `8c03ebaf…`. Identical to the Phase 5 final values. |
| `code_fingerprint_scope.txt`, `suite_fingerprint_scope.txt` | The exact files each fingerprint hashes (unchanged since Phase 5). |
| `backend_lunaops_sha256.txt` | Engine source files. |
| `backend_lunaops_landing_sha256.txt` | Phase 5 landing package. Identical to the Phase 5 final package. |
| `frontend_files_sha256.txt`, `frontend/`, `frontend_snapshot_SHA256SUMS` | Frontend sources and configuration. Identical to the Phase 5 final state. |
| `dist_sha256.txt` | Production build. Identical to the Phase 5 final build. |
| `data/` | Copies of `registry.json`, `landing_manifest.json`, `kernels_lock.json` (the NAIF kernel set the engine uses) and `datasets.json`. |
| `startup_and_data_sha256.txt` | SHA-256 of `start.py`, `requirements.txt` and the data manifests above. |
| `disk_space_E.txt` | Free space on E: before any download (134 GB). |
| `existing_evidence_folders.txt` | Evidence folders present. The Phase 1–5 `SHA256SUMS` manifests all verified before and after Phase 6. |

**Relevant Phase 5 references.**
- The Phase 5 projection, terrain and geometry evidence is in `../../luna_ops_2_phase5_2026-11-13/`: the README, `DATA_SOURCES.md` and `ALGORITHMS.md`.
- Phase 6 reuses the engine's horizon profiles and Earth geometry, not the landing package.

**Before screenshots.** The app before Phase 6 is the Phase 5 final build: the dist hashes above match it. Its screenshots are in `../../luna_ops_2_phase5_2026-11-13/previews/screenshots/`. No Communication view existed before Phase 6.
