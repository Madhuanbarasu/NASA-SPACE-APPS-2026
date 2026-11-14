# Phase 4 A6: Corrected Polar-Wide Cross-Product Terrain Validation Evidence

**Execution Date:** 2026-11-10T16:40:51.665514Z  
**Algorithm Version:** 1.5.0 (`lunaops.ALGORITHM_VERSION`)  
**Evidence Status:** **MEASURED RESULTS ONLY (PENDING SCIENTIFIC ACCEPTANCE)**  
**Lattice Geometry:** $380 \times 380 = 144,400$ candidate points on uniform $\Delta = 1,600\text{ m}$ grid  
**Radial Mask Equation:** $r^2 = x^2 + y^2 \le 304\,000^2\text{ m}^2$  

---

## 1. Domain Definition & Candidate Verification

This corrected measurement establishes two strictly distinguished evaluation domains:

1. **Primary Circular Polar Disk ($r \le 304,000\text{ m}$):**
   - **Coverage:** True Lunar South Pole cap ($80^\circ\text{S} - 90^\circ\text{S}$).
   - **Candidate Count:** Exactly **113,373** points ($78.51\%$ of lattice).
   - **Radial Exclusions:** Exactly **31,027** points ($21.49\%$) lying in the square corners beyond $r = 304\text{ km}$.
   - **Unexpected Exclusions:** **0** (all 113,373 candidate disk points contain 100% valid finite elevation).

2. **Secondary Full Square Bounding Box ($608\text{ km} \times 608\text{ km}$):**
   - **Coverage:** Full circumscribed bounding box $[-304000, 304000]\text{ m}$ including corner terrain spanning $80^\circ\text{S}$ down to $\approx 75.8^\circ\text{S}$ along diagonals.
   - **Candidate Count:** Exactly **144,400** points.
   - **Radial Exclusions:** **0**.
   - **Unexpected Exclusions:** **0** (all 144,400 candidate box points contain 100% valid finite elevation).

---

## 2. Statistical Results: Primary Circular Polar Disk ($n = 113,373$)

Evaluated over the primary $80^\circ\text{S} - 90^\circ\text{S}$ disk using production sampling:
- **80 m:** Exact pixel centres ($i \times 20, j \times 20$) from `LDEM_80S_80MPP_ADJ.tiff`.
- **20 m:** Production `bilinear_many` interpolation from `LDEM_80S_20MPP_ADJ.TIF` (chunked).
- **240 m:** Production `bilinear_many` interpolation from `LDEM_60S_240MPP_ADJ.TIF`.

### A. Pairwise Evaluations ($n = 113,373$, Radial Exclusions = $31,027$)
| Comparison | Valid Sample ($n$) | Mean Bias (m) | Population Std ($\sigma$) | RMS Discrepancy | Median (m) | 5th–95th Percentile | Min / Max Diff | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **80 m vs 240 m** | **113,373** | **+0.0092 m** | **2.9341 m** | **2.9341 m** | +0.1313 m | [-4.48 m, +4.17 m] | -61.1 m / +24.9 m | Measured |
| **20 m vs 240 m** | **113,373** | **+0.0112 m** | **3.1323 m** | **3.1323 m** | +0.1591 m | [-4.78 m, +4.39 m] | -64.5 m / +41.1 m | Measured |
| **20 m vs 80 m** *(Ref)* | **113,373** | +0.0020 m | 0.5785 m | 0.5785 m | +0.0249 m | [-0.59 m, +0.54 m] | -33.1 m / +40.4 m | Measured |

### B. Common Tri-Product Subset ($n = 113,373$)
| Comparison on Common Subset | Valid Sample ($n$) | Mean Bias (m) | Population Std ($\sigma$) | RMS Discrepancy | Median (m) | 5th–95th Percentile | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **80 m vs 240 m** | 113,373 | +0.0092 m | 2.9341 m | **2.9341 m** | +0.1313 m | [-4.48 m, +4.17 m] | Measured |
| **20 m vs 240 m** | 113,373 | +0.0112 m | 3.1323 m | **3.1323 m** | +0.1591 m | [-4.78 m, +4.39 m] | Measured |
| **20 m vs 80 m** | 113,373 | +0.0020 m | 0.5785 m | 0.5785 m | +0.0249 m | [-0.59 m, +0.54 m] | Measured |

---

## 3. Statistical Results: Secondary Full Square Domain ($n = 144,400$)

| Comparison | Candidate Points | Valid Sample ($n$) | Radial Excl | Mean Bias (m) | Population Std ($\sigma$) | RMS Discrepancy | Median (m) | 5th–95th Percentile | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **80 m vs 240 m** | 144,400 | **144,400** | 0 | **+0.0036 m** | 2.9870 m | **2.9870 m** | +0.1209 m | [-4.58 m, +4.25 m] | Measured |
| **20 m vs 240 m** | 144,400 | **144,400** | 0 | **+0.0091 m** | 3.1911 m | **3.1911 m** | +0.1505 m | [-4.87 m, +4.48 m] | Measured |
| **20 m vs 80 m** *(Ref)* | 144,400 | **144,400** | 0 | +0.0055 m | 0.6238 m | 0.6238 m | +0.0262 m | [-0.59 m, +0.55 m] | Measured |

---

## 4. Separately Labelled Diagnostic: Nearest-Neighbour vs Bilinear Comparison

> [!NOTE]
> **Diagnostic Caveat:** Bilinear interpolation substantially mitigates the subpixel slope-offset coupling artifact ($\nabla h \cdot \mathbf{o}$) that inflates variance when sampling non-coincident grids at pixel centres. However, bilinear interpolation does **not** reconstruct true high-frequency topography filtered by the 240 m sensor footprint, nor does it eliminate residual interpolation curvature errors on steep slopes.

| Domain | Sampling Mode | Comparison | Sample ($n$) | Mean Bias (m) | Population Std ($\sigma$) | RMS Discrepancy |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **Circular Disk** | **Nearest-Neighbour (Uncorrected)** | 80 m vs 240 m | 113,373 | $+0.0401\text{ m}$ | $12.9840\text{ m}$ | $12.9840\text{ m}$ |
| **Circular Disk** | **Bilinear Interpolation (Approved)** | 80 m vs 240 m | 113,373 | $+0.0092\text{ m}$ | $2.9341\text{ m}$ | $2.9341\text{ m}$ |
| **Full Square** | **Nearest-Neighbour (Uncorrected)** | 80 m vs 240 m | 144,400 | $+0.0218\text{ m}$ | $13.0566\text{ m}$ | $13.0566\text{ m}$ |
| **Full Square** | **Bilinear Interpolation (Approved)** | 80 m vs 240 m | 144,400 | $+0.0036\text{ m}$ | $2.9870\text{ m}$ | $2.9870\text{ m}$ |

*Observation:* Subpixel coordinate offset on the 240 m grid ($+80\text{ m}$ origin shift) introduces $\approx 13\text{ m}$ of artificial dispersion under nearest-neighbour sampling. Bilinear interpolation correctly follows the continuous bilinear manifold defined across 240 m nodes, reducing dispersion to $2.93\text{ m}$.

---

## 5. Summary of Evidence Files Recorded
- [`polar_wide_output.txt`](file:///E:/LUNA-OPS/docs/validation_evidence/terrain_a6_polar_wide_corrected_2026-11-10/polar_wide_output.txt): Complete console output of the execution run.
- [`polar_wide_report.json`](file:///E:/LUNA-OPS/docs/validation_evidence/terrain_a6_polar_wide_corrected_2026-11-10/polar_wide_report.json): Structured machine-readable results distinguishing circular and square domains with all distribution metrics.
- [`README.md`](file:///E:/LUNA-OPS/docs/validation_evidence/terrain_a6_polar_wide_corrected_2026-11-10/README.md): This documentation report.

---

## 6. Preservation & Non-Acceptance Declaration
- Original evidence directories `terrain_a6_2026-11-10/`, `terrain_a6_240m_2026-11-10/`, and `terrain_a6_polar_wide_240m_2026-11-10/` remain strictly preserved and unmodified.
- Uncommitted changes in `data/dem/registry.json` and `backend/tests/test_pgda90_integration.py` remain intact and uncommitted.
- Algorithm version remains `1.5.0`.
- All metrics are physical measurements; scientific acceptance remains pending review.
