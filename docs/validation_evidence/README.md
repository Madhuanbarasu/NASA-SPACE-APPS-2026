# Validation evidence for this build (sandbox, 2026-11-07, regenerated after the kernel-setup changes)

Produced with the sandbox **test** kernels (`python -m lunaops.acquire sandbox-kernels`, kept in `data/kernels_demo`) and synthetic terrain, Python 3.12.3 and the pinned packages. None of it is a production validation; every quantity stays "Pending validation" until the production kernels and the external references are used.

| File | What it is |
| --- | --- |
| `pytest_sandbox.log` | Full verbose pytest run: 58 passed, 1 skipped (V-02e), 139.2 s, with the values printed by the V-08 and V-14 tests |
| `report_sandbox.json` | `python -m validation.run_validation --merge v14.json` output (copy; the live report path `backend/validation/report.json` is not shipped, as before) |
| `v14_month_sandbox.json` | Full-form V-14: 29.530589 days x 3 sites, per-function counts, offsets, false-event checks (superseded by the production run in `v14_month_a14_2026-11-10/`) |
| `disk_accuracy_original_tangent_plane.txt` | `measure_disk.py` run against the original (pre-audit) code |
| `disk_accuracy_fixed_exact_sphere.txt` | `measure_disk.py` run against this build |
| `disk_exact.py`, `measure_disk.py`, `kink_check.py` | Independent exact spherical reference used for the two measurements |

To reproduce a disk measurement, run from `backend/` with a data directory that holds a kernel lock:

```bash
LUNAOPS_DATA_DIR=<data dir> python ../docs/validation_evidence/measure_disk.py
LUNAOPS_DATA_DIR=<data dir> python ../docs/validation_evidence/kink_check.py
```

`measure_disk.py` samples the reference on a fixed azimuth grid, so on the "rough" horizon its edge-clearance residual (up to about 1.7e-5 deg) is the reference grid missing horizon kinks; `kink_check.py` adds the horizon nodes to the reference and gives 1.4e-12 deg. Timings in the two files depend on the machine (this build: 6.1 to 7.8 us per Sun disk and 18.3 to 22.8 us per Earth disk across runs; original: 4.1 to 4.4 and 11.7 us).

The report and the V-14 file are bound to the code and test-suite fingerprints of this build; `run_validation --merge` will refuse `v14_month_sandbox.json` after any change to `backend/lunaops`, `backend/tests` or `backend/validation`.

The production kernels could not be installed in the build sandbox (naif.jpl.nasa.gov unreachable), so V-02e is skipped in these files. The disk-accuracy measurements were not re-run: the kernel-setup changes did not touch the engine.

## Phase 4 evidence index (production kernels; reconciled at the closure review, 2026-11-11)

**Phase 4: COMPLETE WITH APPROVED DEFERRALS (2026-11-12).** The closure report is `phase4_final_merge_2026-11-12/README.md`.
- **Official report at the Phase 4 closure:** `2279606c…`; pytest 438 passed, 0 failed; report entries 420 passed, 2 not run (V-09, V-10). Superseded on 2026-11-12 by `5135efe8…` (Phase 5 U-04/U-06 re-registration; see Phase 5 evidence).
- **Decisions:** D1 to D7 are in `phase4_closure_2026-11-11/README.md` and `phase4_remaining_decisions_2026-11-11/DECISIONS_RECORDED.md`.
- **Deferred:** D2 (V-09/V-10) and D5 (IB-5).

| Folder | Task | Status |
| --- | --- | --- |
| `kernels_production_2026-11-08/` | A1 production SPICE kernels | Completed |
| `kernel_validation_2026-11-08/` | A2 production-kernel validation (V-01 to V-03, V-02e) | Completed (frozen-pole failure resolved by `earth_pole_2026-11-09/`) |
| `ib2_2026-11-09/` | A3 IB-2 lunar frame kernel | Completed (decision approved) |
| `earth_pole_2026-11-09/` | Earth pole of date, algorithm 1.5.0 | Completed |
| `pgda90_20m_2026-11-10/` | A4/A5 PGDA 90 20 m acquisition and registration | Completed |
| `terrain_a6_2026-11-10/`, `terrain_a6_240m_2026-11-10/`, `terrain_a6_polar_wide_240m_2026-11-10/`, `terrain_a6_polar_wide_corrected_2026-11-10/`, `terrain_a6_acceptance_review_2026-11-10/` | A6 cross-product terrain validation; formal acceptance in `terrain_a6_2026-11-10/ACCEPTANCE.md` | Completed; accepted (digest `e48eb8ed…`) |
| `terrain_a7_2026-11-11/` | A7 real-terrain profiling and window identity | Completed |
| `horizons_v04_v05_2026-11-09/` | A8/A9 V-04/V-05, first run | Superseded (stale fingerprints) |
| `v09_v10_a10_2026-11-10/`, `v09_v10_final_2026-11-10/` | A10 V-09/V-10 | Measured; formally deferred, no criteria approved (D2) |
| `v11_a11_2026-11-09/`, `v11_final_2026-11-10/` | A11 V-11 | PASS (merged) |
| `v12_lroc_a12_2026-11-10/`, `v12_final_2026-11-10/` | A12 V-12 | PASS (merged) |
| `v13_gsfc_2026-11-09/` | A13 V-13, first run (holds the preserved GSFC sources) | Superseded (stale fingerprints) |
| `v14_month_a14_2026-11-10/` | A14 V-14, first run | Superseded (stale fingerprints) |
| `refresh_v04_v05_v13_v14_2026-11-11/` | V-04, V-05, V-13 and V-14 refreshed with the current build | V-04 PASS, V-05 ACCEPTED (D1; not run in the official report), V-13 PASS, V-14 PASS |
| `u04_2026-11-11/` | U-04 accessibility (WCAG 2.2 AA), standalone audit | Accepted, scoped (D4); the current-build re-audit passed (`phase4_remaining_decisions_2026-11-11/u04_current_build/`); `frontend_u04.json` passed in the official report (2026-11-12) |
| `u06_2026-11-11/` | U-06 frontend performance, standalone audit | Accepted against scoped criteria (D3); `frontend_u06.json` passed in the official report (2026-11-12) |
| `c10_2026-11-11/` | C10 interface string externalisation | Completed |
| `hackathon_cleanup_2026-11-11/` | Hackathon readiness cleanup | Completed |
| `ib5_2026-11-11/` | IB-5 licence and attribution inventory | Inventory complete; issues unresolved; formally deferred with distribution restrictions (D5) |
| `report_production_merged.json` | Copy of the official report of 2026-11-10 (SHA-256 `00d2cda1…`) | **Superseded** on 2026-11-11 by `phase4_merge_2026-11-11/report_after.json`; kept as history |
| `phase4_closure_2026-11-11/` | Phase 4 closure review: task register and decisions D1–D7 | Review record; superseded by the final closure (`phase4_final_merge_2026-11-12/`) |
| `phase4_remaining_decisions_2026-11-11/` | D2–D7 decision report and records; U-04 current-build re-audit; `frontend_u04.json` and `frontend_u06.json` result files; merge dry run | D2 and D5 deferred; D3 and D4 accepted (scoped); D7 undefined; result files merged 2026-11-12 |
| `d1_v05_decision_2026-11-11/` | D1: V-05 criteria decision report, reconciliation, acceptance record and decision log | **Closed:** Phase 1.1 criteria approved, evidence accepted (`ACCEPTANCE.md`) |
| `phase4_merge_2026-11-11/` | Official validation report regenerated (closure D6) | **Completed.** pytest 438 passed, 2 skipped, 0 failed. Report entries: 417 passed, 5 not run, 2 skipped. V-04, V-11, V-12, V-13 and V-14 passed; V-05, V-09, V-10, U-04 and U-06 not run. `report.json` SHA-256 `5e6c76d7…`; 32/32 checks passed. **Superseded** by `phase4_final_merge_2026-11-12/` |
| `phase4_final_merge_2026-11-12/` | **Final validation merge and Phase 4 closure report** | Official report at the Phase 4 closure `2279606c…` (**superseded** by `phase5_report_merge_2026-11-12/`): 438 passed, 2 skipped, 0 failed; 420 entries passed, 2 not run; V-04, V-05, V-11 to V-14, U-04 and U-06 passed; V-09 and V-10 not run; 32/32 checks; **Phase 4 COMPLETE WITH APPROVED DEFERRALS** |

## Phase 5 evidence

| Folder | Task | Status |
| --- | --- | --- |
| `phase5_prompt1_2026-11-12/` | Prompt 1: interactive 3D Moon globe (frontend only; NASA SVS CGI Moon Kit imagery, licence verified) | Implemented; 31/31 live checks, 2/2 no-WebGL checks, 236,953 geometry checks; existing features and accessibility unchanged; backend fingerprints and the official report unchanged |
| `phase5_prompt2_2026-11-12/` | Prompt 2: South Pole Explorer (globe → site → local terrain → analysis; frontend only) | Implemented; 27/27 explorer, 31/31 globe, 2/2 no-WebGL live checks; 238,972 geometry checks; existing features and accessibility unchanged; backend fingerprints and the official report unchanged |
| `phase5_prompt3_2026-11-12/` | Prompt 3: scientific visualisation integration (data-class key, site/terrain context, Sun/Earth visibility chart, timeline flags and intervals table, panorama sigma, comparison bars and labels; frontend only) | Implemented; 25/25 visualisation checks against the API results, globe 31/31 and explorer 27/27 regressions; accessibility unchanged apart from documented additions; backend fingerprints and the official report unchanged |
| `phase5_prompt4_2026-11-12/` | Prompt 4: advanced mission dashboard (Mission tab: selected site and coverage, system status, current analysis with labels and uncertainty, deep links, candidate sites, session analyses, comparison status; 3D terrain marker/message overlap fixed; frontend only) | Implemented; 42/42 mission checks against the API responses, visualisation 25/25, explorer 27/27 and globe 31/31 regressions; accessibility unchanged apart from documented additions; backend fingerprints and the official report unchanged |
| `phase5_final_2026-11-12/` | Phase 5 final integration and release verification (result kept while exploring, session list tied to build and report, UI fixes; U-04 re-evaluated in 10 views; U-06 re-measured; end-to-end check; IB-5 browser notices; refreshed U-04/U-06 result files prepared here; merged afterwards with approval, see next row) | **Phase 5 COMPLETE WITH APPROVED DEFERRALS**; all browser checks pass (42, 25, 27, 31, 2, 16); U-04 0 problems in 10 views; U-06 D3 criteria met (slower than the 2026-11-11 build, reported); backend fingerprints and the official report unchanged |
| `phase5_report_merge_2026-11-12/` | Approved re-registration of U-04 and U-06 for the final Phase 5 frontend: dry run (8 files, hashes verified, 0 rejections), backup, `run_validation` merge, verification | **Current official report** `5135efe8…` (run 2026-11-12T06:27:21Z): pytest 438 passed, 2 skipped, 0 failed; 420 entries passed, 2 not run, 2 skipped; identical to `2279606c…` except U-04/U-06 (passed, now the Phase 5 results); 37/37 checks |
| `south_polar_map_fixes_2026-11-12/` | South polar map fixes (frontend only): missing L-shaped region drawn again from the server's own finer hillshade tiles (slow backend tiles at zooms 1-4 cancelled and composed, remembered), view bounded to the map's data square, loading/failed/outside-60° S notes; backend tile-renderer root cause documented, not changed | Map check 20/20; explorer 27/27, globe 31/31, mission 42/42, end-to-end 16/16; accessibility unchanged (0 problems in 10 views); backend fingerprints and the official report unchanged |
