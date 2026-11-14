# D1: V-05 criteria reconciliation (read-only review, 2026-11-11)

> **Update 2026-11-11: D1 is CLOSED.** The Phase 1.1 criteria were approved and the existing evidence accepted; see `ACCEPTANCE.md` and `DECISION_LOG.md`. The status line below records this report's state when it was written.

**Status: AWAITING HUMAN DECISION.**
- **Nothing approved or changed:** this review approves nothing, does not mark V-05 as passed, and changes no code, threshold, acceptance record, evidence or `report.json`.
- **No new measurement and no network access:** the only computation is an offline re-reading of the stored Horizons responses (`reconcile_analysis.py` → `reconcile_analysis.log`).

**Effect on the earlier report:** this supersedes the recommendation in `README.md` (the D1 report written earlier today) wherever they differ.

## 1. Blueprint comparison: cannot be done from the repository
- **Search:** neither the Phase 1 nor the Phase 1.1 Engineering Blueprint is present.
  - **Where:** the whole working tree, plus a name search of drive E: to depth 4.
  - **Patterns:** "blueprint", "phase 1", `.pdf`/`.docx`/`.md`, "120-second", "10-second" and "one-minute table".
- **The only reference is `README.md` line 3:** *"The Phase 1.1 Engineering Blueprint is the source of truth for every requirement, algorithm and test referenced below."* That indicates Phase 1.1 is the latest and governing document. Its V-05 text is not available.
- **Every V-05 record in the repository says the blueprint's V-05 criterion text was unavailable:**
  - `validation/horizons_compare.py` docstring;
  - A8/A9 README;
  - `docs/AUDIT_2026-11.md` lines 641 and 675;
  - the refresh and closure READMEs.
- **Formal team approval: none recorded for any V-05 threshold** (120 s, 10 s or the proposed 1.0 s).
- **The 120 s and 10 s limits come only from the request for this review.** Which blueprint version states which limit, and their exact wording, **could not be verified**. The approver must confirm them from the Phase 1.1 document.

## 2. Does the existing evidence cover both comparisons?
Evidence: `../refresh_v04_v05_v13_v14_2026-11-11/v04_horizons/` (`horizons.json` SHA-256 `401e446d…`, 47 verbatim Horizons responses).

| Comparison (as named in the request) | Proposed limit | Covered? | What the evidence holds |
| --- | --- | --- | --- |
| **Horizons rise/set comparison** | 120 s | **Not as Horizons rise/set output; covered by a stricter substitute.** Horizons' own rise/transit/set (RTS) mode was **never queried**: no RTS-only request, and only 2 of all table rows carry an RTS marker (below). | Centre crossings of a 0° horizon derived from Horizons' own elevations at **1-s** resolution, compared with LUNA-OPS: 18/18 matched, max abs(dt) **0.49995 s** |
| **Interpolated one-minute table comparison** | 10 s | **Yes, in the raw data.** A 1-minute Horizons table was stored around each of the 18 crossings. This comparison was **not** part of the recorded V-05 output; it was computed now from the stored responses. | max abs(t_LUNA − t_1min) **0.49956 s**, 18/18 ≤ 10 s; the 1-minute interpolation differs from the 1-s crossing by ≤ 0.00068 s |

**Why Horizons RTS is a different event, not just a coarser one:**
- **Different horizon:** the stored headers define RTS as rise and set "with respect to the reference ellipsoid true visual horizon … Accuracy is < or = to twice the requested search step-size". With a 1-minute search step that is ≤ 120 s, which is consistent with a 120 s limit.
- **Different point on the disk:** the only two RTS markers in the evidence are at the farside site (`v05_farside_sun_*_min.json`). They sit where the Sun's *centre* is at −0.277° (set) and −0.269° (rise), about one solar radius below the horizon. That is consistent with Horizons flagging the **upper limb**, not the centre (inferred, not confirmed by Horizons documentation).
- **What a strict RTS comparison would need:** LUNA-OPS's top-edge events (`sun_top`/`earth_top`), not the centre events that V-05 measured. No such LUNA-OPS events were recorded in the V-05 run.

## 3. The 18 events against each candidate criterion

| Criterion | Evaluated against | Matched / missed / spurious | Max abs(dt) | Result vs limit |
| --- | --- | --- | --- | --- |
| 120 s (Horizons rise/set) | Horizons 1-s centre crossings (substitute) | 18 / 0 / 0 | 0.49995 s | within, about 240× margin; **not** Horizons RTS output |
| 10 s (interpolated 1-minute table) | Horizons 1-minute table, linear interpolation | 18 / 0 / 0 | 0.49956 s | within, 20× margin |
| 1.0 s (proposed in A9, encoded in `V05_TOL_S`) | Horizons 1-s centre crossings | 18 / 0 / 0 | 0.49995 s | within, 2× margin |

**About the per-event values:**
- **Where they are:** `reconcile_analysis.log`.
- **Re-derivation check:** the 1-s crossings re-derived here equal the recorded `et_horizons` exactly (difference 0).
- **What dominates dt:** the detector's ±0.5 s midpoint quantization. Geometry contributes ≤ 0.034 s and the reference ≤ 0.0002 s (`d1_analysis.log`).

## 4. Recommendation
1. **Take the criterion from the Phase 1.1 blueprint** (the declared source of truth), after the approver confirms its exact V-05 wording. The 1.0 s value in the script was a stand-in because that text was missing; it should not override the blueprint.
2. **If Phase 1.1 specifies the 10 s interpolated 1-minute-table comparison, alone or alongside 120 s:**
   - **Approve it.** The existing evidence can be **reused without a rerun or any code change**.
   - **The 10 s comparison is met** with 20× margin, from the stored responses.
   - **The script's recorded `passed` was computed with the stricter 1.0 s check.** Passing it implies passing 10 s and 120 s for the same events.
   - **The acceptance record must state this mapping explicitly**, because `horizons.json` describes its criterion as 1.0 s. It should cite `reconcile_analysis.log`, the evidence SHA-256s and the approver and date.
   - **Do not edit `V05_TOL_S` or the script docstring.** Any byte change under `backend/validation` changes the suite fingerprint and invalidates every external result (V-04/V-05 and V-09 to V-14), forcing all of them to be rerun.
3. **If Phase 1.1 explicitly requires a comparison with Horizons' own rise/set (RTS) output (120 s)**, the existing evidence is **not sufficient in form**. The approver must choose:
   - **(a) accept the 1-s centre-crossing comparison as an equivalent-or-stricter substitute.** Recommended, if the blueprint wording allows it: same reference system, 240× inside the limit; or
   - **(b) require a new measurement:** Horizons RTS queries for the six sites, with LUNA-OPS limb events matching Horizons' RTS definition.
     - It needs network access and a change to `horizons_compare.py` for a mergeable V-05 result, which changes the suite fingerprint and triggers re-runs of every external validation and the full suite.
     - A docs-side supplementary script would avoid that, but its result could not be merged as V-05.
4. **Formal V-05 status after approval:** V-05 becomes `passed` in the official report only through `run_validation` with the full `horizons.json` in place of `horizons_v04_only.json`. That needs separate approval: about 24 minutes, same procedure as the 2026-11-11 merge.
   - **Effect on labels:** none. `events` also needs V-09, V-10, U-04 and U-06.

## Decisions requested from the approver
1. **The blueprint text:** confirm the Phase 1.1 V-05 wording, including whether 120 s and 10 s are both in it, and which document version each limit comes from.
2. **The criterion:** approve the V-05 criterion as written there.
3. **If an RTS comparison is required:** choose 3(a), accept the substitute, or 3(b), a new measurement.

**Files added by this review:**
- **`RECONCILIATION.md`:** this report.
- **`reconcile_analysis.py`:** read-only; it reads only the stored refresh evidence and the kernels.
- **`reconcile_analysis.log`:** its output.
- **`SHA256SUMS`:** regenerated to cover them.
