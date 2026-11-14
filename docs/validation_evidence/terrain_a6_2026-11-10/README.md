# Phase 4 A6: Cross-Product Terrain Validation Evidence

**Date:** 2026-11-10
**Algorithm Version:** 1.5.0 (`lunaops.ALGORITHM_VERSION`)
**Feature Branch:** `phase4-a6-cross-product-terrain-validation`

## 1. Overview
Phase 4 A6 completes the cross-resolution terrain validation across all three tiers of the LUNA-OPS science engine:
- **5 m/pixel** (PGDA 78 Site01 site DEM, priority 40, 8 km half-width)
- **20 m/pixel** (PGDA 90 regional DEM, priority 50, 40 km half-width, coverage 80°S–90°S)
- **80 m/pixel** (PGDA 90 regional DEM, priority 50, 250 km half-width, coverage 80°S–90°S)

## 2. Cross-Product Discrepancy Allowances (`CROSS_PRODUCT_SAMPLING`)
Evaluated via bilinear interpolation over window intersections with $n \ge 100$:

| Pair | Samples ($n$) | Mean Offset | Standard Deviation | RMS Discrepancy ($s_x$) | Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **5 m vs 20 m** (Site01) | 40000 | -0.0629 m | 0.5230 m | **0.5267 m** | Measured |
| **5 m vs 80 m** (Site01) | 40000 | -0.0532 m | 1.2227 m | **1.2239 m** | Measured |
| **20 m vs 80 m** (Site01 Reg.) | 27889 | -0.0251 m | 1.1052 m | **1.1054 m** | Measured |

> [!NOTE]
> The intermediate 20 m tier reduces the cross-product allowance against 5 m Site01 from **1.224 m** down to **0.527 m** (>57% reduction in transition uncertainty).

## 3. Site01 Footprint Overlap Statistics (4–8 km Annulus)
Comparison of bilinear interpolation against nearest-pixel sampling:

| Method | Resolution Pair | Points ($n$) | Mean Offset | Std Dev | RMS Difference |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Bilinear (Approved)** | 5 m vs 20 m | 376,986 | -0.0642 m | 0.3952 m | **0.4004 m** |
| **Nearest Pixel** | 5 m vs 20 m | 37,699 | -0.0184 m | 1.5576 m | **1.5577 m** |
| **Bilinear (Approved)** | 5 m vs 80 m | 23,572 | -0.0727 m | 1.1949 m | **1.1971 m** |
| **Nearest Pixel (Audit)** | 5 m vs 80 m | 23,572 | +1.0726 m | 6.2428 m | **6.3343 m** |

## 4. Polar-Wide (80°S–90°S) 20 m vs 80 m Grid & Elevation Alignment
Evaluated across 144,400 distributed points across the entire 608 km × 608 km polar domain:
- **Bounds Match:** True (exact match: `[-304000.0, -304000.0, 304000.0, 304000.0]`)
- **Pixel Grid Ratio:** 4.0× (each 80 m pixel perfectly subdivides into 4 × 4 = 16 20 m pixels)
- **CRS:** IAU:30135 South Polar Stereographic (Sphere 1737.4 km)
- **Mean Difference (20 m − 80 m):** -0.0472 m
- **Standard Deviation:** 2.1405 m
- **RMS Difference:** 2.1410 m
- **5th–95th Percentile:** [-3.550 m, +3.399 m]

## 5. Error Maps & Non-Negativity
All three products feature verified, linked uncertainty error maps:
- **5 m Error Map (`Site01_final_adj_5mpp_toterr.tif`):** min = 0.0616 m, max = 5.5828 m (Non-negative: True)
- **20 m Error Map (`LDEM_80S_20MPP_ADJ_ERR.TIF`):** min = 0.1550 m, max = 6.7283 m, mean = 0.6515 m (Non-negative: True)
- **80 m Error Map (`LDEM_80S_80MPP_ADJ_ERR.tiff`):** min = 0.0258 m, max = 6.9381 m, mean = 0.4733 m (Non-negative: True)

## 6. Multi-Resolution Hierarchy Priority & Horizon Propagation
- **Site01 Priority:** Sourced from `5m` ($h = 1944.83$ m). Available levels: `['5m', '20m', '80m']`.
- **Regional Priority (outside Site01):** Sourced from `20m` ($h = 628.02$ m). Available levels: `['20m', '80m']`.
- **Horizon Incomplete Bins:** 0 (100% complete 360° coverage).
- **Horizon Uncertainty $\sigma$:** min = 0.0010°, max = 0.0897°, mean = 0.0828°.

## 7. Formal Acceptance & Corrigendum Documentation
- Full 6-tier formal acceptance record: [`ACCEPTANCE.md`](ACCEPTANCE.md)
- Narrative description corrigendum reconciling JSON descriptions with empirical reports: [`MEASUREMENT_CORRIGENDUM.md`](MEASUREMENT_CORRIGENDUM.md)

