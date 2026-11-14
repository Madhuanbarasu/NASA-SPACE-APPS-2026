# Phase 4 A6 Formal Acceptance Record (Full 6-Tier Hierarchy)

**Decision:** ACCEPT, full acceptance across all six overlapping DEM pairs (5 m / 20 m / 80 m / 240 m).
- **Approver:** Thilakhaesh K
- **Date:** 2026-11-10
- **Algorithm Version:** 1.5.0
- **Evidence Sources:**
  - `docs/validation_evidence/terrain_a6_2026-11-10/` (Scoped 5m/20m/80m report & benchmarks)
  - `docs/validation_evidence/terrain_a6_240m_2026-11-10/` (8-location benchmark & Site01 240m evaluation)
  - `docs/validation_evidence/terrain_a6_polar_wide_corrected_2026-11-10/` (Polar-wide circular disk evaluation, $r \le 304\text{ km}$, $n=113,373$)
  - `docs/validation_evidence/terrain_a6_acceptance_review_2026-11-10/` (Final comprehensive review report)
  - [`docs/validation_evidence/terrain_a6_2026-11-10/MEASUREMENT_CORRIGENDUM.md`](MEASUREMENT_CORRIGENDUM.md) (Measurement provenance corrigendum reconciling narrative descriptions)
- **Machine-Readable Record:** `backend/validation/reference/terrain_acceptance.json`
- **Gate Enforcement:** `backend/validation/terrain_gate.py`

---

## Accepted Overlapping Pairs (Bound to Registered Bytes)

| Pair | Resolution | Registered DEM SHA-256 (finer / coarser) | Registered Error-Map SHA-256 (finer / coarser) | Measured Allowance ($s_x$) | Status |
| :--- | :--- | :--- | :--- | :---: | :---: |
| **5m / 20m** | 5 m / 20 m | `3ba7b97c…f7e747e` / `09b7ca80…b6845649` | `cf2cf52f…51054ab1c` / `d64045b8…b3059d8cf` | **0.527 m** | **ACCEPTED** |
| **5m / 80m** | 5 m / 80 m | `3ba7b97c…f7e747e` / `82030dcb…b4beee5a` | `cf2cf52f…51054ab1c` / `e8930691…3c370ffc6` | **1.224 m** | **ACCEPTED** |
| **20m / 80m** | 20 m / 80 m | `09b7ca80…b6845649` / `82030dcb…b4beee5a` | `d64045b8…b3059d8cf` / `e8930691…3c370ffc6` | **1.105 m** | **ACCEPTED** |
| **5m / 240m** | 5 m / 240 m | `3ba7b97c…f7e747e` / `3f966325…cec8b34` | `cf2cf52f…51054ab1c` / `6b987570…38fab` | **4.314 m** | **ACCEPTED** |
| **20m / 240m** | 20 m / 240 m | `09b7ca80…b6845649` / `3f966325…cec8b34` | `d64045b8…b3059d8cf` / `6b987570…38fab` | **2.735 m** | **ACCEPTED** |
| **80m / 240m** | 80 m / 240 m | `82030dcb…b4beee5a` / `3f966325…cec8b34` | `e8930691…3c370ffc6` / `6b987570…38fab` | **2.620 m** | **ACCEPTED** |

*Note: All hashes match full 64-character hexadecimal SHA-256 strings recorded in `backend/validation/reference/terrain_acceptance.json`.*

---

## Pending Pairs

None. All six overlapping DEM resolution pairs across the 4 registered tiers are accepted.

---

## Gate Status and Downstream Effect

- `backend/validation/terrain_gate.py` dynamically evaluates all 6 overlapping pairs against registered terrain.
- All 6 pairs are present in `accepted_pairs` with matching hashes.
- `missing_pairs` is empty (`[]`), and `terrain_gate.evaluate()["ok"]` evaluates to `True`.
- External validation tests (V-09, V-10, V-11, V-12) meet the terrain prerequisites and their final execution results can now be merged under the canonical `terrain_acceptance_digest`.

---

## Measurement Provenance Corrigendum

For detailed reconciliation of human-readable narrative descriptions in `terrain_acceptance.json` against the underlying empirical reports, see [`MEASUREMENT_CORRIGENDUM.md`](MEASUREMENT_CORRIGENDUM.md).


