# D1 decision log: V-05 acceptance criterion

**Final status: D1 CLOSED, criteria APPROVED, evidence ACCEPTED (2026-11-11).**
- **Official report:** V-05 remains **not run** in `backend/validation/report.json` until a separately approved merge.

| # | Date (2026-11-11) | Step | Outcome | Record |
| --- | --- | --- | --- | --- |
| 1 | V-04/V-05 refresh | V-05 measured with the current build; the proposed 1.0 s threshold was not approved | V-05 PROVISIONAL (18/18, max 0.49995 s) | `../refresh_v04_v05_v13_v14_2026-11-11/v05_riseset/` |
| 2 | Phase 4 closure review | D1 opened: V-05 timing threshold approval | Open | `../phase4_closure_2026-11-11/README.md` |
| 3 | Validation merge | V-05 excluded (V-04-only file) | V-05 not run in the official report | `../phase4_merge_2026-11-11/` |
| 4 | D1 decision report | Error budget; 1.0 s judged consistent with ±0.5 s resolution | Recommended 1.0 s, pending the blueprint text | `README.md`, `d1_analysis.log` |
| 5 | D1 reconciliation | Blueprints not in the repository; Phase 1.1 governs (README line 3). Evidence checked against the 120 s RTS and 10 s one-minute limits. | Both met (0.49995 s / 0.49956 s); RTS mode not queried; recommended the Phase 1.1 criteria | `RECONCILIATION.md`, `reconcile_analysis.log` |
| 6 | **Approval** | Phase 1.1 criteria approved (120 s Horizons rise/set; 10 s interpolated one-minute table). The 1-s centre-crossing comparison is accepted as the RTS substitute. The existing evidence is accepted without new measurement or code change. | **D1 CLOSED: ACCEPTED** | `ACCEPTANCE.md` |
| 7 | 2026-11-12 | **Final merge**: full `horizons.json` merged with the seven other approved files | **V-05 passed in the official report** (`2279606c…`) | `../phase4_final_merge_2026-11-12/` |

**Open follow-up (not part of D1, needs its own approval):**
- **Official report:** ~~merge the full `horizons.json` so that the official report records V-05~~. **Done 2026-11-12** (row 7).
- **Optional:** a direct Horizons RTS comparison with LUNA-OPS limb events, if the limb-versus-centre limitation is to be closed.
