# Pre-Phase 7 preparation (2026-11-14)

**Main reports:**
- [`reports/PHASE7_READINESS_REPORT.md`](reports/PHASE7_READINESS_REPORT.md)
- [`reports/V09_V10_DECISION_REPORT.md`](reports/V09_V10_DECISION_REPORT.md)

**Modified files** (`source_changes.diff`; originals in `baseline/`):
- `frontend/src/components/Sidebar.tsx`: the panel-azimuth input loses its 0–360 browser limits and gains the hint (`aria-describedby="paz-hint"`).
- `frontend/src/i18n/en.ts`: `panelAzimuthHint`, "Azimuth in degrees; values are normalized modulo 360° (400° → 40°)."

**Not changed:**
- the backend, calculations, RF logic, thresholds and labels;
- the fingerprints (`logs/05_fingerprints.txt`: `9cd7b08b…` / `519a8e4c…`).

**Server:** the existing one; no new server was started. Phase 7 was not started.

**Checks:**
- **TypeScript:** 0 errors (`logs/01`).
- **`npm test`:** strings 1372 keys, 0 problems; a11y 0 problems; moon-geo 238,972; check-window 20/20 (`logs/02`).
- **Build:** OK (`logs/03`).

**E2E-07 rerun** (one browser cycle; `logs/04_e2e07_rerun.log`, `browser-results.json`, `screenshots/`):
- **Date cases, 5/5 Pass:**
  - valid 30-day and 1-minute windows: Analyse enabled, no message;
  - equal, reversed, and reversed by 1 minute: inline message, end field `aria-invalid`, sidebar and explorer Analyse disabled, **0 analysis requests**.
- **Azimuth:** the exact new hint is shown, no `min`/`max`, the browser marks 400 valid, the request carries 40, and the stored result has 40.
- **Script assertion error:** the run reported "Fail" for the azimuth case because its assertion picked the new static hint instead of the dynamic "used as 40°" note. That note was **not re-verified** here; its code is unchanged and was verified in `../date_validation_fix_2026-11-14/`.
- **Console:** 0 errors.
- **Results file:** `browser-results.json` was rebuilt from the UTF-8 log, after a first post-processing step mis-decoded its non-ASCII text.

**Scripts:** `scripts/e2e07_rerun_body.mjs`, appended to `../luna_ops_2_phase1_2026-11-13/cdp_harness.txt` to make `e2e07_rerun.mjs`.
