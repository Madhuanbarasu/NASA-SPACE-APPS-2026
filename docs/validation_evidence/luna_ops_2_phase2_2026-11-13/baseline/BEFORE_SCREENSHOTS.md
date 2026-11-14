# Phase 2 "before" state

The Phase 2 starting point is the final Phase 1 build. Its screenshots are reused, not re-captured, because of the memory limits:

- `../../luna_ops_2_phase1_2026-11-13/screenshots_after/screenshots/` contains 24 images: every view at 1440, 1024 and 390 px, plus the navigation states.
  - Explorer views: `after-{desktop,tablet,phone}-site-welcome-map.png` (South Polar Map) and `after-{desktop,tablet,phone}-site-globe.png` (3D Moon).
- `../../luna_ops_2_phase1_2026-11-13/screenshots_iter1/screenshots/` contains the result views of the first Phase 1 build.

**Identity of this baseline:**
- `dist_sha256.txt` equals the Phase 1 `logs/dist_after_sha256.txt` (the served bundle is `index-ZnayDHTI.js` and `index-DCMBg5-B.css`).
- `frontend_files_sha256.txt` equals the Phase 1 `logs/frontend_files_after_sha256.txt` (66 files).
- `backend_fingerprints.txt` equals the Phase 1 baseline: algorithm 1.5.0, code `84cbd4ea…`, suite `1632af16…`, terrain `e48eb8ed…`, report.json `8c03ebaf…`.

**Measured on the before state (1440×900, parameters docked):**
- The explorer stage starts at y ≈ 595, below the hero, the readiness board and the steps.
- The globe stage is `clamp(340px, 62vh, 640px)`, which is 558 px here. The lunar disc is about 545 px across, and only about 45% of the stage is above the fold.
