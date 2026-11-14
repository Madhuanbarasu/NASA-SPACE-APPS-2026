# Scientific validation follow-up (2026-11-14)

**Main report:** [`reports/FOLLOWUP_REPORT.md`](reports/FOLLOWUP_REPORT.md).

**Approved and implemented:** the missing-terrain boundaries in `backend/lunaops/engine/events.py` (`build_intervals`). No other engine change.

**New fingerprints:**
- code `9cd7b08b…` (previous `84cbd4ea…`);
- suite `519a8e4c…` (previous `1632af16…`).

**Revalidation required:** the validation report is preserved unchanged, so every engine label now shows Pending validation until it is revalidated.

| Folder | Content |
|---|---|
| `event_fix/` | `before/` (original `events.py`, pre-fix synthetic and real-result checks, pre-fix result JSON); `after/` (corrected `events.py`, post-fix checks); `events.py.diff` |
| `fingerprints/` | `fingerprints.json` (previous and new, label blockers); `new_validation_baseline.json` (424 entries: revalidation required); `report.json.historical_84cbd4ea`; `api_status_after.json` |
| `regression/` | New test file (copy) and its log (5 passed); existing event tests log (48 passed) |
| `e2e/` | `e2e-results.json` (7 tests: 6 Pass, 1 Fail); `e2e07b.json`; `screenshots/` |
| `v09_v10/` | `V09_V10_FINDINGS.md` |
| `disk_visibility/` | `disk_independent_after.json` (24 cases under the new engine) |
| `power_indicator/` | `POWER_INDICATOR.md`; `power_independent_after.json` |
| `cache/` | `integrity_before.txt`, `integrity_after.txt`, `recomputed.json` |
| `scripts/` | Every script (E2E bodies are appended to `../luna_ops_2_phase1_2026-11-13/cdp_harness.txt`) |
| `logs/` | Run logs; `server.log` is the restarted server's output |
| `SHA256SUMS` | Every file in this folder (LF line endings) |
