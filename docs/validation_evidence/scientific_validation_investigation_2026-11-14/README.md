# Scientific validation investigation (2026-11-14)

**Main report:** [`reports/SCIENTIFIC_VALIDATION_REPORT.md`](reports/SCIENTIFIC_VALIDATION_REPORT.md).

**Scope:** focused investigation of V-09, V-10, Earth-disk visibility, event detection and the power indicator. Not the Phase 7 suite.

**No changes were made to:**
- the engine, tests, validation scripts or reports;
- datasets, the cache or earlier evidence;
- thresholds or labels.

**Proposed for approval:** one engine correction (`events.py`, unknown time over incomplete horizon bins). It is not implemented.

| Folder | Content |
|---|---|
| `V09_illumination/`, `V10_earth_visibility/` | `per_point_residuals.csv`: all 200 points, with reference, computed, residual and the reference's own 3 × 3 range |
| `independent_checks/` | `avgvisib_experiment.json`: 25 points × 3 horizon variants (0 m, 2 m, 60 m near field) |
| `disk_visibility/` | `disk_independent.json`: engine against the spheroid ray-cast, 24 cases |
| `event_detection/` | `events_independent.json` (13 synthetic cases against a 0.5 s brute force); `incomplete_bins_real_results.json` (5 real cached results) |
| `power_indicator/` | `power_independent.json`: 240 series and metrics, 14 edge cases, RF hand-worked case |
| `scripts/` | Every script used (all read only); run with `backend/.venv/Scripts/python.exe` |
| `logs/` | `01` residuals; `02` experiment; `03` disk; `04` events; `05` incomplete bins on real results; `06` smooth subsets; `07` power and RF; `08` area-weighted statistics; `09` integrity after |
| `reports/` | The report |
| `SHA256SUMS` | Every file in this folder (LF line endings) |

**Source of the V-09/V-10 per-point data:** `../backend_tiles_and_ui_fixes_2026-11-12/validation/v09_v10.json`, run 2026-11-12 under engine `84cbd4ea…`. It was reused, not rerun.
