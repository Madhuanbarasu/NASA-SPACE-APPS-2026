# D1: V-05 formal acceptance record

**Decision: ACCEPTED.** The V-05 acceptance criteria of the Phase 1.1 Engineering Blueprint are approved for the hackathon deliverable, and the existing V-05 evidence is accepted as meeting them.

| Field | Value |
| --- | --- |
| Decision ID | D1, V-05 timing acceptance criterion (Phase 4 closure register) |
| Approver | Project owner; approval given in the working-session instruction "Phase 4 — D1: Approve V05 acceptance" (no name stated) |
| Date | 2026-11-11 |
| Scope | Hackathon deliverable |
| Approved criteria (Phase 1.1 blueprint) | **C1:** each LUNA-OPS rise/set time within **120 s** of the Horizons rise/set reference. **C2:** each within **10 s** of the time interpolated from the one-minute Horizons table. |
| Criteria source | As stated by the approver. The Phase 1.1 blueprint document itself is not in the repository (`RECONCILIATION.md` §1). |
| Accepted substitute (C1) | The 1-second Horizons **centre-crossing** comparison is accepted as a documented substitute for direct Horizons RTS (rise/transit/set) output |
| Algorithm / code / suite | 1.5.0 / `5bf9753f…37d2f8` / `1632af16…6d75eabc` (unchanged) |
| Terrain acceptance digest | `e48eb8ed…943dce` (unchanged) |

## Accepted evidence (reused as is; no measurement repeated)

| Item | Value |
| --- | --- |
| Run | `../refresh_v04_v05_v13_v14_2026-11-11/v04_horizons/` (2026-11-11, production kernels, current fingerprints). `horizons.json` SHA-256 `401e446dad093fae2a7dd5c01768231ff5886101da21be5c1e5c789a1e0ad49b`; 47 verbatim Horizons responses (`horizons_raw/`, listed in `../refresh_v04_v05_v13_v14_2026-11-11/SHA256SUMS`) |
| Separate V-05 report | `../refresh_v04_v05_v13_v14_2026-11-11/v05_riseset/` |
| Analyses | `d1_analysis.py`/`.log` (error budget) and `reconcile_analysis.py`/`.log` (1-minute interpolation, RTS markers). Both are read-only re-readings of the stored responses. |
| Coverage | 6 sites (Section 10.3, height 0 km), Sun and Earth, 2026-11-14 to 2026-12-14 TT, flat 0° horizon, centre crossings |

| Criterion | Compared against | Matched / missed / spurious | Max abs(t_LUNA − t_ref) | Limit | Result |
| --- | --- | --- | --- | --- | --- |
| C1 (120 s) | Horizons 1-s centre crossings, the accepted substitute for RTS output | **18/18** / 0 / 0 | **0.49995 s** | 120 s | **Met** |
| C2 (10 s) | Linear interpolation of the stored one-minute Horizons tables | **18/18** / 0 / 0 | **0.49956 s** | 10 s | **Met** |

**Error budget:**
- **Dominant term:** the differences are the detector's ±0.5 s bisection-midpoint quantization.
- **Smaller terms:** geometry contributes ≤ 0.034 s and the Horizons reference ≤ 0.0002 s.
- **Consistency check:** the 1-minute interpolation agrees with the 1-s crossings to ≤ 0.00068 s.

## Limitations accepted with this decision
1. **Horizons RTS mode was not queried directly.** No rise/transit/set-only request exists in the evidence. Criterion C1 is therefore met through the substitute, not through Horizons' own rise/set output.
2. **The limb-versus-centre difference remains.**
   - **Horizons' definition:** Horizons defines rise and set against the reference-ellipsoid true visual horizon, with an accuracy of ≤ 2 × the search step.
   - **What the evidence suggests:** the only two RTS markers in the evidence (farside Sun, 1-minute tables) fall where the Sun's centre is about one solar radius below the horizon, consistent with an upper-limb definition.
   - **What V-05 measured:** centre crossings. LUNA-OPS limb events were not compared with Horizons RTS times.
   - **Consequence:** the acceptance covers centre-crossing timing. It does not demonstrate agreement with Horizons' limb-based RTS times.
3. **The blueprint text was not available.** The criteria are taken from the approver's statement of the Phase 1.1 blueprint, and its exact wording is not reproduced here.
4. **Coverage:** one 30-day window, six sites, flat horizon, no terrain. Real-terrain event timing is covered by V-14 and the horizon validations.

## Relationship to the validation script and the official report
- **Nothing changed in code:** no script, threshold, backend code, fingerprint or evidence was changed.
- **The internal check is stricter:** `validation/horizons_compare.py` still applies its internal check `V05_TOL_S` = 1.0 s, and its docstring still says the criterion "should be confirmed". Both are left untouched on purpose: editing them would change the suite fingerprint and invalidate every external result.
  - **What the 1.0 s pass means:** the refreshed `horizons.json` records V-05 `passed` under that stricter 1.0 s check, which implies C1 (substitute) and C2 for the same 18 events.
  - **Which record governs:** this record, not the script's text, defines the approved V-05 criterion.
- **The official report still says V-05 is not run:** `backend/validation/report.json` (SHA-256 `5e6c76d7…db812e7b`) still lists V-05 as **not run**, because this decision does not run the merge.
- **What would record V-05 as passed:** a separately approved `run_validation` with the full `../refresh_v04_v05_v13_v14_2026-11-11/v04_horizons/horizons.json` in place of `../phase4_closure_2026-11-11/merge_inputs/horizons_v04_only.json`, together with the other five files of the 2026-11-11 merge.
  - **When it is valid:** only while the code and suite fingerprints are unchanged.
- **Labels:** no product label changes. `events`, the only quantity that needs V-05, still needs V-09, V-10, U-04 and U-06 (D2, D3, D4).
