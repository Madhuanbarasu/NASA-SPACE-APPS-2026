# D1: V-05 acceptance criterion, decision report (2026-11-11)

> **See `RECONCILIATION.md` (later the same day).** The reconciliation against the blueprint-stated limits supersedes this report's recommendation wherever they differ.

> **Update 2026-11-11: D1 is CLOSED.** The Phase 1.1 criteria were approved and the existing evidence accepted; see `ACCEPTANCE.md` and `DECISION_LOG.md`. The status line below records this report's state when it was written.

**Status: AWAITING HUMAN DECISION.**
- **Nothing approved:** this report approves nothing and does not mark V-05 as passed.
- **Nothing changed:** no criterion, script, evidence or `report.json` was changed. The official report still has V-05 "not run".
- **Analysis only:** this used the existing refreshed evidence. No new measurement and no network access.
- **Fingerprints:** code `5bf9753f…`, suite `1632af16…`, terrain acceptance `e48eb8ed…`, algorithm 1.5.0, `report.json` `5e6c76d7…`, all unchanged.

## Recommendation
**Approve the proposed 1.0 s V-05 threshold (Option A)**, and record the approval in a documentation-only acceptance record outside `backend/`.

**Why it is technically sound:**
- **It sits above the measurement resolution:** the detector's resolution limit is ±0.5 s, its geometric and reference error is ≤ 0.035 s, and 1.0 s leaves a margin of about 0.47 s for any single event.
- **It matches an approved tolerance:** it is identical to `EVENT_TOL_S`, the tolerance already approved for the same detector in V-14.
- **It reuses the evidence:** the refreshed evidence already applies 1.0 s and can be merged unchanged, so no new measurement and no code change are needed.

**The approver should first check the blueprint:** the V-05 criterion text is not in the repository. If it states a different criterion, that text governs (Option B or C).

## Measured evidence (verified against the files)
Source: `../refresh_v04_v05_v13_v14_2026-11-11/v04_horizons/horizons.json` (SHA-256 `401e446d…`) and `../refresh_v04_v05_v13_v14_2026-11-11/v05_riseset/`.

**Run:** 2026-11-11, production kernels, current code and suite fingerprints. 6 sites, 30 days (2026-11-14 to 12-14 TT), Sun and Earth centre crossings of a flat 0° horizon.

| Quantity | Value |
| --- | --- |
| Horizons crossings | 18 |
| Matched | **18/18** |
| Missed / spurious | **0 / 0** (no confirmation table needed) |
| max abs(dt), dt = t_LUNA − t_Horizons | **0.49995 s** (south-polar B, Sun set) |
| Sun events (10) | dt +0.219 to +0.500 s; mean +0.438 s; all positive |
| Earth events (8) | dt −0.109 to +0.330 s; mean +0.106 s |
| Within 0.5 s / within the proposed 1.0 s | 18/18 / 18/18 |

## Error budget (`d1_analysis.py` → `d1_analysis.log`)

| Source | Bound on the timing error | Basis |
| --- | --- | --- |
| **Detector quantization** | **≤ 0.5 s** by construction | `events._refine` bisects until the bracket is ≤ `EVENT_TOL_S` = 1.0 s and reports the bracket **midpoint** (`events.py` lines 308–320) |
| Geometry (LUNA-OPS vs Horizons direction) | ≤ 0.034 s (Earth at the limb site); ≤ 0.005 s for every other site and body | worst V-04 elevation residual for that site and body over the month ÷ its elevation rate at the crossing (6.3e-6 to 1.4e-4 °/s) |
| Horizons reference | ≤ 0.0002 s | elevations printed to 1e-9°, linear interpolation over 1 s; the reference moved by only 8.4e-5 s between 2026-11-09 and 2026-11-11 |

**Interpretation:**
- **Quantization dominates:** V-05 effectively measures the detector's quantization, and the worst case (0.49995 s) sits at the theoretical ±0.5 s limit.
- **Timing differences are not geometry:** V-04 shows the apparent directions agree to ≤ 5.2e-7°, so the timing differences are not geometric.
- **The Sun's positive bias is not a timing defect:** all 10 Sun differences are positive (probability 1/1024 if the error were symmetric). This is consistent with the step control in the code:
  - `_tau` is a conservative bound, so steps approach each crossing from before;
  - the final bracket therefore tends to start just before the crossing, and its reported midpoint lands up to +0.5 s late.
  - It is not a timing offset: V-04 compares the two at identical epochs and agrees to 3e-8° for the Sun, whereas a 0.4 s offset would appear as up to 5.6e-5°.
  - It stays inside the ±0.5 s bound, but it means results cluster near +0.5 s rather than spreading around 0.
- **Caveat:** this bias explanation is inferred from the code and the measurements; it has not been isolated by a dedicated test.

## Is 1.0 s consistent with the measurement resolution?
**Yes.**
- **A threshold must exceed the method's own error,** which here is ≤ 0.5 s quantization plus ≤ 0.035 s from geometry and the reference, or the test would fail on resolution alone.
- **1.0 s leaves about 0.47 s of headroom per event**, so a real defect of about 0.5 s or more on top of worst-case quantization would be caught.
- **It is the same value as `EVENT_TOL_S`** and as the approved V-14 tolerance (`v14_month.TOL_S`, pinned in `test_phase4_v14`). V-14 shows the same worst offset, 0.500 s, against a 1 s brute force.
- **A threshold at or below 0.5 s is not consistent.** The current detector would pass or fail on quantization noise: the worst case is 0.49995 s, only 5e-5 s below 0.5 s.

## Options and consequences

| Option | Code or script change | Fingerprint impact | New measurement | Expected V-05 result | Effort |
| --- | --- | --- | --- | --- | --- |
| **A. Approve 1.0 s** (recommended) | None. `V05_TOL_S` is already 1.0 | None | **None**; the refreshed `horizons.json` already applies 1.0 s and records V-05 `passed` | PASS (18/18, max 0.49995 s, 0.5 s margin) | Write an acceptance record; then one approved `run_validation` (~24 min) |
| **B. Approve a value in (0.5, 1.0) s**, e.g. 0.75 s | `V05_TOL_S` in `validation/horizons_compare.py` | **Suite fingerprint changes**, which invalidates *every* external result file (V-04/V-05, V-09/V-10, V-11, V-12, V-13, V-14) | **Yes**: horizons_compare and every other external validation, including the long terrain runs (V-09 to V-12) and the month-long V-14, plus the full suite | Likely PASS (worst 0.49995 s) but with a thin margin above quantization | Large |
| **C. Approve ≤ 0.5 s** | A finer `EVENT_TOL_S` in the engine (an algorithm change, with a probable version bump) and the script | Code **and** suite fingerprints change, plus probably the algorithm version | **Yes**: everything, including V-14 and the golden tests | Unknown until rerun | Very large |
| **D. Defer** | None | None | None | V-05 stays "not run"; the `events` label stays Pending | None |

**Notes:**
- **Option A, what the record must hold:**
  - The record should state the approver, the date, the criterion (no missed or spurious centre crossing, every abs(dt) ≤ 1.0 s, 600 s matching window) and the evidence file SHA-256 (`401e446d…`).
  - **Do not edit `horizons_compare.py`'s docstring** ("…should be confirmed"). Any byte change under `backend/validation` changes the suite fingerprint, with the consequences listed for Option B. The acceptance record supersedes that note in documentation.
- **Option A, how the merge would run:** replace `phase4_closure_2026-11-11/merge_inputs/horizons_v04_only.json` with `refresh_v04_v05_v13_v14_2026-11-11/v04_horizons/horizons.json` among the six files.
  - This is valid only while the code and suite fingerprints are unchanged.
- **Option A, effect on labels:**
  - V-05 is required only by `events`, which also needs V-09, V-10, U-04 and U-06. Approving D1 therefore **changes no label**: `events` stays Pending validation until D2, D3 and D4 are resolved.
  - **The case for A is cost:** it closes D1 cheaply now, rather than having V-05 hold up `events` later.
- **Options B and C:** a stricter threshold improves nothing physically measurable, because the observed differences are detector quantization. Unless the blueprint requires it, the cost of re-running every external validation is not justified.

## Can the existing evidence be reused?
**For Option A, yes, unchanged:**
- **Fingerprints:** `horizons.json` was produced 2026-11-11 with the current code and suite fingerprints and the production kernels, and passes the merge guard (dry run and real merge of its V-04 part).
- **Criterion:** its V-05 entry was computed with exactly the 1.0 s criterion.
- **Limit:** reuse is valid only while no file under `backend/lunaops`, `backend/tests` or `backend/validation` changes.

**For Options B and C:** the measurements would still be informative, because the dt values are known for any threshold. But a formal result requires a rerun under the changed fingerprints.

## Decision requested
**The approver chooses:**
- **A:** approve 1.0 s;
- **B:** approve another value in (0.5, 1.0) s;
- **C:** require ≤ 0.5 s;
- **D:** defer.

**If A is chosen, the follow-up steps** (each needing its own approval):
1. Write a V-05 acceptance record in `docs/`, without touching `backend/`.
2. Run one `run_validation` with the full `horizons.json` in place of the V-04-only file.
3. Synchronise the documentation.

**Files in this folder:**
- **`README.md`:** this report.
- **`d1_analysis.py`:** read-only; it reads only the existing refresh evidence.
- **`d1_analysis.log`:** its output.
