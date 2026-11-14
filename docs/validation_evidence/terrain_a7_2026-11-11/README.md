# Phase 4 A7: Real-Terrain Performance Profiling & Window Identity Evidence

**Date:** 2026-11-11  
**Algorithm Version:** 1.5.0 (`lunaops.ALGORITHM_VERSION`)  
**Code Fingerprint:** `5bf9753fa5c5493eadeb9839c07b837f2e3e69e3986e76146a2ed1717e37d2f8`  
**Terrain Acceptance Digest:** `e48eb8ed0ca2003c2769c60932323dbce34385e4eac2a675f076e13bbd943dce`  
**Status:** Completed & Closed  

> [!NOTE]
> **Provenance Clarification:** The canonical `Terrain Acceptance Digest` is `e48eb8ed0ca2003c2769c60932323dbce34385e4eac2a675f076e13bbd943dce` (evaluating from `validation.terrain_gate.acceptance_digest()`), matching the production V09–V12 acceptance records. The previously drafted value (`b17a126b...`) was an erroneous documentation literal created during report drafting; the underlying empirical A7 test results, window-identity calculations, and profiling benchmarks were entirely unaffected. (The distinct `Terrain Products Digest` is `830c4e28f9bed7f0c64e7f2a9b87148b094b088fd50df53586a8351f20c36cc0`.)  

---

## 1. Executive Summary

Phase 4 A7 closes the empirical performance, memory optimization, and correctness verification of the LUNA-OPS science engine running on actual registered lunar terrain.

This evidence package establishes three core empirical pillars:
1. **Durable Integration Suite Verification:** Full execution of `backend/tests/test_pgda90_integration.py` passing 19 of 19 tests against the complete multi-resolution hierarchy (5m, 20m, 80m, and 240m).
2. **Adaptive DEM Window Identity:** Proof of bitwise-identical horizon calculations between the reference full loader (`LUNAOPS_WINDOW_MODE=full`) and the production adaptive window loader (`LUNAOPS_WINDOW_MODE=adaptive`), demonstrating 32% to 85% peak memory reduction without numerical divergence across all 16 output arrays and uncertainty bounds.
3. **Real-Terrain Performance Profiling:** Comprehensive cProfile analysis and wall-clock timings on registered NASA DEMs covering cold starts (horizon computation + numba kernel compilation) and cached-horizon event analysis.
4. **Historical Cross-Reference Reconciliation:** Formal documentation linking Phase 4 A4 acquisition records with Phase 4 A5 evidence, and updating requirement C07 (V-02e) and external validations V09–V12 in `docs/TRACEABILITY.md` and `README.md`.

---

## 2. Integration Test Evidence (19/19 Passed)

The PGDA-dependent test suite was executed against the active registered datasets:
- **Command:** `python -m pytest backend/tests/test_pgda90_integration.py -v --tb=short`
- **Environment:** Windows, Python 3.13.7, pytest 9.1.1, pluggy 1.7.0, anyio 4.16.0
- **Duration:** 128.11s (02:08)
- **Exit Status:** 0 (All 19 passed)
- **Log File:** [`pytest_pgda90_integration.log`](file:///E:/LUNA-OPS/docs/validation_evidence/terrain_a7_2026-11-11/pytest_pgda90_integration.log)

### Test Inventory
| Test Name | Status | Coverage Scope |
| --- | --- | --- |
| `test_manifest_and_settings_include_80m` | PASSED | Manifest spec and level registration |
| `test_manifest_and_settings_include_20m` | PASSED | Manifest spec and 20m registration |
| `test_pgda90_file_integrity_and_geometry` | PASSED | 80m DEM/ERR raster geometry & CRS IAU:30135 |
| `test_pgda90_20m_file_integrity_and_geometry` | PASSED | 20m DEM/ERR raster geometry & CRS IAU:30135 |
| `test_registry_contains_both_5m_and_80m` | PASSED | Multi-tier registry co-existence |
| `test_multi_resolution_sampling_and_5m_priority` | PASSED | 5m precedence over 20m/80m within Site01 |
| `test_three_tier_hierarchy_5m_20m_80m` | PASSED | Priority cascade (5m -> 20m -> 80m) |
| `test_horizon_coverage_completes_with_80m` | PASSED | Long-range ray completion via regional DEM |
| `test_3d_terrain_grid_multi_resolution` | PASSED | Grid extraction across resolutions |
| `test_horizon_uncertainty_uses_both_error_maps` | PASSED | Error map integration for site & blocking points |
| `test_nodata_is_never_treated_as_valid_terrain` | PASSED | Rigorous NaN and NoData filtering |
| `test_cli_verify_all_registered` | PASSED | CLI hash verification of all registered files |
| `test_near_field_uncertainty_correlation_eliminates_7_deg_artifact` | PASSED | Spatial error correlation at near field ($L_{\text{corr}} = 250\text{ m}$) |
| `test_5m_footprint_and_overlap_elevation_offsets` | PASSED | Overlap offset verification 5m vs 80m |
| `test_registry_paths_are_portable` | PASSED | Path portability and serialization |
| `test_cross_product_discrepancy_all_resolution_pairs` | PASSED | Cross-product discrepancy validation across tiers |
| `test_5m_and_20m_overlap_elevation_offsets` | PASSED | Overlap elevation offset bounds 5m vs 20m |
| `test_20m_and_80m_polar_wide_grid_and_elevation_alignment` | PASSED | Polar-wide grid alignment 20m vs 80m |
| `test_bilinear_many_invariant_to_window_block_offsets` | PASSED | Invariance of bilinear interpolation across chunk offsets |

---

## 3. Window Identity & Memory Optimization Evidence

The adaptive DEM window loader (`LUNAOPS_WINDOW_MODE=adaptive`) reads only the necessary radial reach into a shared buffer and expands dynamically when high-elevation blocking terrain demands it.

The verification tool `scripts/check_window_identity.py` was executed across all four registered terrain tiers (5m, 20m, 80m, and 240m). For each site and configuration, the horizon is computed with the full reference loader and compared array-by-array against the adaptive loader.

### Arrays Verified Bitwise
The following 16 per-bin arrays plus uncertainty statistics and stopping bounds were verified for exact bitwise identity (`np.array_equal(..., equal_nan=True)`):
- `h_deg`
- `block_dist_m`
- `incomplete`
- `sigma_deg`
- `near_field`
- `blocker_product`
- `cross_product`
- `discrepancy_unknown`
- `sigma_nonlinear`
- `sigma_lower_bound_deg`
- `sigma_block_m`
- `sigma_block_model_m`
- `block_h_m`
- `subbin_excess_deg`
- `subbin_unknown`
- `stop_step`
- `params["h_max_m"]`
- `params["sigma"]`

### Results Table
| Site / Coordinates | Tier Hierarchy | Reach Configuration | Reference Peak (MB) | Adaptive Peak (MB) | Memory Reduction | Expansions | Verification Result |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| **Site01** (`-89.463163, 222.510447`) | 5m $\rightarrow$ 20m $\rightarrow$ 80m $\rightarrow$ 240m | Default (`80m=100km, 240m=200km`) | 745 MB | 422 MB | **43% lower** | 1 | **IDENTICAL** |
| **Site01** (`-89.463163, 222.510447`) | 5m $\rightarrow$ 20m $\rightarrow$ 80m $\rightarrow$ 240m | Custom (`20m=20km, 80m=50km, 240m=100km`) | 745 MB | 387 MB | **48% lower** | 2 | **IDENTICAL** |
| **Regional 80m** (`-89.9, 0.0`) | 20m $\rightarrow$ 80m $\rightarrow$ 240m | Default (`80m=100km, 240m=200km`) | 643 MB | 437 MB | **32% lower** | 1 | **IDENTICAL** |
| **Regional 80m** (`-89.9, 0.0`) | 20m $\rightarrow$ 80m $\rightarrow$ 240m | Custom (`80m=50km, 240m=100km`) | 664 MB | 429 MB | **35% lower** | 1 | **IDENTICAL** |
| **Regional 240m** (`-75.0, 0.0`) | 240m only | Default (`80m=100km, 240m=200km`) | 302 MB | 45 MB | **85% lower** | 0 | **IDENTICAL** |
| **Regional 240m** (`-75.0, 0.0`) | 240m only | Custom (`240m=100km`) | 302 MB | 160 MB | **47% lower** | 1 | **IDENTICAL** |

**Log File:** [`window_identity.log`](file:///E:/LUNA-OPS/docs/validation_evidence/terrain_a7_2026-11-11/window_identity.log)

---

## 4. Performance Profiling on Real Registered Terrain

Performance profiling was conducted using `scripts/profile_analysis.py` directly against the registered multi-resolution terrain.

### Scenario A: Site01 (PGDA 78 Site01), 30-Day Analysis Span
- **Site:** Lat `-89.463163°`, Lon `222.510447°`
- **Time Window:** 2026-11-14 to 2026-12-14 (30 days, 720 hourly evaluation epochs + event refinement)
- **Cold Run (Horizon computed + Numba compilation):** 15.90 s
- **Cached Horizon Run (Analysis only):** 9.22 s (42.0% faster)
- **Top Computational Hotspots (cProfile):**
  1. `earth_disk_state` (`lunaops/engine/earth.py`): 1.475 s own time (12,126 calls)
  2. `sample_target` (`lunaops/engine/ephem.py`): 0.728 s own time (18,466 calls)
  3. `spkcpo` (`spiceypy`): 0.599 s own time (25,674 calls)
  4. `cross3` (`lunaops/engine/frames.py`): 0.555 s own time (83,130 calls)
  5. `_earth_sample` (`lunaops/engine/ephem.py`): 0.537 s own time (9,233 calls)

### Scenario B: Regional 80m Site, 7-Day Analysis Span
- **Site:** Lat `-89.9°`, Lon `0.0°`
- **Time Window:** 2026-11-14 to 2026-11-21 (7 days)
- **Cold Run (Horizon computed):** 9.61 s
- **Cached Horizon Run (Analysis only):** 1.97 s (79.5% faster)
- **Top Computational Hotspots (cProfile):**
  1. `earth_disk_state`: 0.326 s own time (2,526 calls)
  2. `spkcpo`: 0.150 s own time (5,382 calls)
  3. `sample_target`: 0.149 s own time (3,694 calls)

**Log File:** [`profile_analysis.log`](file:///E:/LUNA-OPS/docs/validation_evidence/terrain_a7_2026-11-11/profile_analysis.log)

---

## 5. Phase 4 A4 & A5 Historical Evidence Cross-Reference

Phase 4 A4 encompassed the initial acquisition, verification, and registration of the NASA Planetary Geodynamics Laboratory (PGDA) 90 LOLA 20m/pixel south polar regional DEM and corresponding height error map.

Due to sequential task execution, all A4 acquisition verification evidence, SHA-256 validation logs, and registration CLI executions were durably captured within the Phase 4 A5 evidence repository:
- **Evidence Directory:** [`docs/validation_evidence/pgda90_20m_2026-11-10/`](file:///E:/LUNA-OPS/docs/validation_evidence/pgda90_20m_2026-11-10/)
- **Dem File:** `LDEM_80S_20MPP_ADJ.TIF` (2,696,082,051 bytes; SHA-256: `09b7ca80f9e6a146f970225d18af72fc02787669b3ef51b888e347d2b6845649`)
- **Error Map:** `LDEM_80S_20MPP_ADJ_ERR.TIF` (3,954,709,201 bytes; SHA-256: `d64045b8aa58a24010f009ab5667ae02cc06cffa7796784dd5e2d48b3059d8cf`)
- **Key Verification Files:**
  - `acquire_status.log`: Registry status confirmation.
  - `acquire_verify.log`: Direct re-hashing of all registered rasters.
  - `independent_hashes.txt`: Independent hashlib validation.
  - `registration_meta.json`: Full product registration metadata.

This entry explicitly confirms that Phase 4 A4 requirements are satisfied and permanently documented under the Phase 4 A5 record.

---

## 6. Traceability and Validation Status Updates

1. **Requirement C07 (V-02e Frame Alignment):**
   - Reconciled against Phase 4 A2 evidence ([`docs/validation_evidence/kernel_validation_2026-11-08/`](file:///E:/LUNA-OPS/docs/validation_evidence/kernel_validation_2026-11-08/)).
   - `d_max = 0.506 m <= 1.0 m` evaluated across 11 epochs (2026–2036) with production NAIF kernels.
   - Status updated in [`docs/TRACEABILITY.md`](file:///E:/LUNA-OPS/docs/TRACEABILITY.md) from "Pending V-02e" to "Implemented; V-02a-e passed (2026-11-08)".

2. **External Validations V09–V12:**
   - **V-11 (PGDA 90 PSR):** Passed on registered terrain (200/200 points dark, 0 inconclusive); recorded in [`docs/validation_evidence/v11_final_2026-11-10/`](file:///E:/LUNA-OPS/docs/validation_evidence/v11_final_2026-11-10/).
   - **V-12 (LROC WAC Illumination):** Passed on registered terrain (200/200 scored, C1 shadow gate passed at $\le 0.022\%$ TWI); recorded in [`docs/validation_evidence/v12_final_2026-11-10/`](file:///E:/LUNA-OPS/docs/validation_evidence/v12_final_2026-11-10/).
   - **V-09 & V-10 (LOLA AVGVISIB Sun & Earth):** Measured on multi-resolution terrain across 200 stratified points over 18.6 years (0 inconclusive); provisional criteria preserved with `status: not run` per scientific rules; recorded in [`docs/validation_evidence/v09_v10_final_2026-11-10/`](file:///E:/LUNA-OPS/docs/validation_evidence/v09_v10_final_2026-11-10/).
   - Both [`docs/TRACEABILITY.md`](file:///E:/LUNA-OPS/docs/TRACEABILITY.md) and [`README.md`](file:///E:/LUNA-OPS/README.md) updated to reflect these final production runs.
   - Label consistency verified via `backend/tests/test_phase3_labels.py` (18/18 passed).

