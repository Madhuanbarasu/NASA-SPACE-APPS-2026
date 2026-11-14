# Phase 4 A6: Benchmark-Location Terrain Discrepancy Evidence (Command A)

**Execution Date:** 2026-11-10T16:23:38.806339Z  
**Algorithm Version:** 1.5.0 (`lunaops.ALGORITHM_VERSION`)  
**Engine Function:** `lunaops.engine.horizon.cross_product_discrepancy`  
**Terrain Coverage Tiers:** 5 m (Site01), 20 m (80°S–90°S), 80 m (80°S–90°S), 240 m (60°S–90°S)  

## 1. Overview
This test executes **Command A** from the Phase 4 A6 validation plan, evaluating all pairwise DEM cross-product discrepancy allowances across 8 standardized benchmark locations:
- **Site01 (Connecting Ridge):** $(-89.463163^\circ, 222.510447^\circ)$
- **South Pole:** $(-90.0^\circ, 0.0^\circ)$
- **Malapert Mountain:** $(-85.99^\circ, 2.93^\circ)$
- **Nobile Rim:** $(-85.2^\circ, 53.5^\circ)$
- **Boundary 80.5°S (0°):** $(-80.5^\circ, 0.0^\circ)$
- **Boundary 80.5°S (90°):** $(-80.5^\circ, 90.0^\circ)$
- **Boundary 80.5°S (180°):** $(-80.5^\circ, 180.0^\circ)$
- **Boundary 80.5°S (270°):** $(-80.5^\circ, 270.0^\circ)$

## 2. 240 m Cross-Product Discrepancy Summary

| Location | Pair | Overlap Samples ($n$) | Mean Offset | Standard Deviation | RMS Allowance ($s_x$) | Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Site01 (Connecting Ridge)** | 5m vs 240m | 4,489 | +0.1504 m | 4.3110 m | **4.3136 m** | Measured |
| **Site01 (Connecting Ridge)** | 20m vs 240m | 27,889 | -0.0307 m | 2.7352 m | **2.7354 m** | Measured |
| **Site01 (Connecting Ridge)** | 80m vs 240m | 36,100 | -0.0000 m | 2.6199 m | **2.6199 m** | Measured |
| **South Pole** | 5m vs 240m | 357 | -0.6303 m | 2.5240 m | **2.6015 m** | Measured |
| **South Pole** | 20m vs 240m | 27,889 | -0.0327 m | 2.7313 m | **2.7315 m** | Measured |
| **South Pole** | 80m vs 240m | 36,100 | -0.0090 m | 1.3968 m | **1.3968 m** | Measured |
| **Malapert Mountain** | 5m vs 240m | — | — | — | — | Unavailable (Outside Coverage) |
| **Malapert Mountain** | 20m vs 240m | 27,889 | -0.0702 m | 3.7367 m | **3.7373 m** | Measured |
| **Malapert Mountain** | 80m vs 240m | 37,829 | +0.0111 m | 2.6894 m | **2.6894 m** | Measured |
| **Nobile Rim** | 5m vs 240m | — | — | — | — | Unavailable (Outside Coverage) |
| **Nobile Rim** | 20m vs 240m | 27,889 | +0.0116 m | 3.0580 m | **3.0580 m** | Measured |
| **Nobile Rim** | 80m vs 240m | 35,685 | +0.0180 m | 2.6491 m | **2.6492 m** | Measured |
| **Boundary 80.5S (0 deg)** | 5m vs 240m | — | — | — | — | Unavailable (Outside Coverage) |
| **Boundary 80.5S (0 deg)** | 20m vs 240m | 19,372 | -0.0122 m | 2.9784 m | **2.9784 m** | Measured |
| **Boundary 80.5S (0 deg)** | 80m vs 240m | 36,279 | +0.0082 m | 1.4295 m | **1.4295 m** | Measured |
| **Boundary 80.5S (90 deg)** | 5m vs 240m | — | — | — | — | Unavailable (Outside Coverage) |
| **Boundary 80.5S (90 deg)** | 20m vs 240m | 19,372 | +0.0059 m | 2.4686 m | **2.4687 m** | Measured |
| **Boundary 80.5S (90 deg)** | 80m vs 240m | 36,279 | -0.0004 m | 1.4536 m | **1.4536 m** | Measured |
| **Boundary 80.5S (180 deg)** | 5m vs 240m | — | — | — | — | Unavailable (Outside Coverage) |
| **Boundary 80.5S (180 deg)** | 20m vs 240m | 19,372 | +0.0188 m | 2.4767 m | **2.4768 m** | Measured |
| **Boundary 80.5S (180 deg)** | 80m vs 240m | 36,279 | -0.0036 m | 1.3489 m | **1.3489 m** | Measured |
| **Boundary 80.5S (270 deg)** | 5m vs 240m | — | — | — | — | Unavailable (Outside Coverage) |
| **Boundary 80.5S (270 deg)** | 20m vs 240m | 19,372 | -0.0313 m | 2.7961 m | **2.7963 m** | Measured |
| **Boundary 80.5S (270 deg)** | 80m vs 240m | 36,279 | -0.0020 m | 1.3028 m | **1.3028 m** | Measured |

## 3. Findings & Observations
1. **Zero-Bias Alignment:** Across all regional sites, the mean bias between 80 m and 240 m is tightly bounded within $\pm 0.018\text{ m}$, and between 20 m and 240 m within $\pm 0.070\text{ m}$.
2. **Boundary Truncation:** At $80.5^\circ\text{S}$, the 20 m DEM window naturally truncates at the $80^\circ\text{S}$ product edge, yielding $n = 19,372$ valid pairs (down from 27,889), with no edge artifacts.
3. **Site01 5 m vs 240 m:** Over the $16\text{ km} \times 16\text{ km}$ Site01 window, $n = 4,489$ pairs yield an RMS discrepancy allowance of $4.3136\text{ m}$.

Evidence files:
- Raw terminal log: `benchmark_locations_output.txt`
- Structured JSON: `benchmark_locations_report.json`
