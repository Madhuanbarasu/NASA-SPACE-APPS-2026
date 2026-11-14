# Phase 3 "before" state

The Phase 3 starting point is the final Phase 2 build. These identities were checked when the baseline was saved:
- **Frontend source and config:** `frontend_files_sha256.txt` (69 files) equals the Phase 2 `logs/frontend_files_after_sha256.txt`.
- **Build:** `dist_sha256.txt` equals the Phase 2 `logs/dist_after_sha256.txt`.
- **Backend and official report:** `backend_fingerprints.txt` equals the Phase 2 baseline:
  - algorithm 1.5.0;
  - code `84cbd4ea…`, suite `1632af16…`, terrain acceptance `e48eb8ed…`;
  - `validation/report.json` `8c03ebaf…`.
- **Earlier evidence:** the Phase 1 and Phase 2 evidence folders still verify against their own `SHA256SUMS`.

Phase 2 did not change the analysis result view or the comparison view, so the latest screenshots of them are from Phase 1:
- `../../luna_ops_2_phase1_2026-11-13/screenshots_iter1/screenshots/`: `iter1-desktop-site-result-top.png`, `-charts.png`, `-terrain.png` and `iter1-desktop-mission-with-result.png`.
- `../../luna_ops_2_phase1_2026-11-13/screenshots_after/screenshots/`: `after-*-compare.png` (the empty comparison builder).
