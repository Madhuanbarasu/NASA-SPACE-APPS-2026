# LUNA-OPS 2.0: Phase 7 readiness (2026-11-14)

**Engine:**
- code fingerprint `9cd7b08b…`, suite `519a8e4c…`, algorithm 1.5.0;
- validation report `report.json` `8c03ebaf…` (historical, from the previous fingerprint);
- live labels: every engine quantity is **Pending validation** (revalidation required).

## 1. Completed corrections
| Item | What | Evidence |
|---|---|---|
| AUD-01 | Latitude/longitude range validation; no out-of-range coverage requests | `pre_phase7_corrections_2026-11-14/` |
| AUD-04 | Landing 76 px gap at 1920 px | same |
| AUD-05 | Investigated: transient tile loading; no change needed | same |
| AUD-06 | Map grid: separate `lunaops_tiles` package, `/api/display/tiles/`; engine untouched | `pre_phase7_aud06_fix_2026-11-14/` |
| AUD-08 | Out-of-range site not drawn on the South Polar Map | `pre_phase7_aud08_fix_2026-11-14/` |
| Event detection | Missing-terrain boundaries in `events.py` (approved engine change): 37.3 h wrongly visible → 0; new fingerprints | `scientific_validation_followup_2026-11-14/` |
| E2E-07 | Date range must have its end strictly after its start: inline message, Analyse disabled, no request; panel azimuth normalised modulo 360° | `date_validation_fix_2026-11-14/` |
| Azimuth hint | "Azimuth in degrees; values are normalized modulo 360° (400° → 40°)."; the 0–360 browser limits removed | this folder |

## 2. Remaining scientific decisions (owner)
1. **V-09/V-10:**
   - approve, amend or reject criteria R1–R3;
   - choose the observer-height policy;
   - authorise the pre-registered holdout run (`V09_V10_DECISION_REPORT.md`).
2. **Earth-disk visibility:** acceptance tolerance. Proposed: visible fraction ≤ 5e-4; edges ≤ grid × (1 + slope); verdicts identical away from ±1e-3° grazing.
3. **Event timing:** tolerance. Proposed: 1 s for edges, 2 s for durations. Windows shorter than about 2 s are not guaranteed.
4. **Power indicator:**
   - the acceptance basis for an Estimated quantity (definition verified; no measured-power data);
   - optionally the terminology change "Solar availability indicator (relative, dimensionless)".
5. **Algorithm version:** whether to bump it (1.5.0 → 1.5.1) at revalidation, to mark the event change.

## 3. Outstanding unverified checks
- **Validation report:** the full automated suite and the validation report under `9cd7b08b…`/`519a8e4c…`. Until they run, no label can be Validated.
- **V-04–V-14 external runs** under the new fingerprint.
- **V-09/V-10 holdout;** the AVGVISIB observer height; optionally LDEM_85S_060M.
- **U-04 and U-06 gates;** rendered colour contrast; keyboard and screen-reader operation, including the new unknown intervals and the date-range message.
- **E2E:** phone widths; map dragging; CSV/JSON downloads; comparisons larger than 2 × 1.
- **Azimuth note:** the dynamic "used as 40°" note was verified in the previous cycle only; the script assertion in this cycle targeted the wrong hint.
- **Power indicator** against measured power: no data exists.

## 4. Exact requirements for starting Phase 7
**Must-do inside Phase 7, in order:**
1. **Owner decisions from section 2**, at least: V-09/V-10 criteria and observer-height policy; the disk and event tolerances; the power-indicator acceptance basis.
2. **Run the full automated test suite** under the current fingerprints. It must exit 0, as the engine's label guard requires.
3. **Regenerate the validation report** (`python -m validation.run_validation` plus the external V-04–V-14 runs) under `9cd7b08b…`/`519a8e4c…`. This restores Validated labels only where tests pass. Keep `report.json` `8c03ebaf…` as history.
4. **Run the V-09/V-10 pre-registered holdout** and judge it against the approved criteria.
5. **Run U-04/U-06, contrast and assistive-technology checks,** then the application-wide E2E suite.

**Preconditions already met:**
- every known Critical, High or Medium defect is resolved or approved;
- the engine change is documented with before-and-after evidence;
- fingerprints, caches and all evidence are preserved and checksum-verified.

**No remaining blocker prevents starting Phase 7** once the owner decisions in step 1 are given. Steps 2 onwards are Phase 7 work and have not been started.
