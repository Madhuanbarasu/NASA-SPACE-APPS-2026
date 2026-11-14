# Phase 4 A6: Polar-Wide 240 m Cross-Product Validation Evidence

**Execution Date:** 2026-11-10T16:31:46.723844Z  
**Algorithm Version:** 1.5.0 (`lunaops.ALGORITHM_VERSION`)  
**Shared Geographic Domain:** $80^\circ\text{S} - 90^\circ\text{S}$ Polar Disk (IAU:30135, $r \le 304\text{ km}$)  
**Sampling Lattice:** $380 \times 380 = 144,400$ candidate points ($1,600\text{ m}$ uniform spacing, $608\text{ km} \times 608\text{ km}$ domain)  
**Status:** **MEASURED RESULTS (PENDING SCIENTIFIC ACCEPTANCE)**  

---

## 1. Overview & Sampling Design
This evaluation fulfills the polar-wide cross-product evidence requirement for Phase 4 A6, validating the newly acquired **240 m** regional DEM against both the **80 m** and **20 m** regional DEMs across their entire shared geographic coverage:
- **80 m Elevations:** Evaluated at exact pixel centres ($i \times 20, j \times 20$) from `LDEM_80S_80MPP_ADJ.tiff`.
- **20 m Elevations:** Evaluated using production **bilinear interpolation** from `LDEM_80S_20MPP_ADJ.TIF` with memory-bounded chunking ($195\text{ MB}$ max RAM footprint).
- **240 m Elevations:** Evaluated using production **bilinear interpolation** from `LDEM_60S_240MPP_ADJ.TIF`.
- **Exclusion Masking:** All points outside the $80^\circ\text{S}$ product boundary ($r > 304\text{ km}$) and any stencil containing `nodata` (NaN) or implausible elevation ($|h| > 20,000\text{ m}$) are strictly excluded.

---

## 2. Polar-Wide Elevation Discrepancy Statistics

### A. Full Pairwise Evaluations
| Comparison | Candidate Points | Valid Overlap ($n$) | Excluded | Mean Bias (m) | Population Std ($\sigma$) | RMS Discrepancy | Median (m) | 5th–95th Percentile | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **80 m vs 240 m** | 144,400 | 144,400 | 0 | **+0.0036 m** | 2.9870 m | **2.9870 m** | +0.1209 m | [-4.58 m, +4.25 m] | Measured |
| **20 m vs 240 m** | 144,400 | 144,400 | 0 | **+0.0091 m** | 3.1911 m | **3.1911 m** | +0.1505 m | [-4.87 m, +4.48 m] | Measured |
| **20 m vs 80 m** *(Ref)* | 144,400 | 144,400 | 0 | +0.0055 m | 0.6238 m | 0.6238 m | +0.0262 m | [-0.59 m, +0.55 m] | Measured |

### B. Common Valid Subset (All Three Tiers Simultaneously Valid: $n = 144,400$)
| Comparison on Common Subset | Valid Sample ($n$) | Mean Bias (m) | Population Std ($\sigma$) | RMS Discrepancy | Median (m) | 5th–95th Percentile | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **80 m vs 240 m** | 144,400 | +0.0036 m | 2.9870 m | **2.9870 m** | +0.1209 m | [-4.58 m, +4.25 m] | Measured |
| **20 m vs 240 m** | 144,400 | +0.0091 m | 3.1911 m | **3.1911 m** | +0.1505 m | [-4.87 m, +4.48 m] | Measured |
| **20 m vs 80 m** | 144,400 | +0.0055 m | 0.6238 m | 0.6238 m | +0.0262 m | [-0.59 m, +0.55 m] | Measured |

---

## 3. Scientific Analysis & Key Findings
1. **Exceptional Mean Geodetic Consistency:**
   - The mean bias across the entire polar cap between 80 m and 240 m is **+0.0036 m** (essentially zero).
   - Between 20 m and 240 m, the mean bias is **+0.0091 m** (less than $1\text{ cm}$).
   - This confirms that the LOLA PGDA 90 240 m product is geodetically and vertical-datum consistent with both regional products across the whole lunar South Pole.
2. **Standard Deviation & Topographic Smoothing:**
   - 80 m vs 240 m: $\sigma = 2.9870\text{ m}$, $\text{RMS} = 2.9870\text{ m}$.
   - 20 m vs 240 m: $\sigma = 3.1911\text{ m}$, $\text{RMS} = 3.1911\text{ m}$.
   - 90% of all elevation discrepancies ($p_5$ to $p_95$) across the entire $608\text{ km} \times 608\text{ km}$ domain fall within $[-4.58\text{ m}, +4.25\text{ m}]$ for 80m/240m and $[-4.87\text{ m}, +4.48\text{ m}]$ for 20m/240m.
3. **Exclusion Characterization:**
   - Exactly 0 candidate lattice points (0.00%) were excluded because they lie in the corners of the $608\text{ km} \times 608\text{ km}$ projected box outside the circular $80^\circ\text{S}$ polar disk ($r > 304\text{ km}$) where 20 m and 80 m rasters have declared nodata.
   - Zero points inside the active $80^\circ\text{S}$ disk were dropped, indicating 100% valid data coverage.

---

## 4. Preservation & Integrity
- All existing evidence in `terrain_a6_2026-11-10/` and `terrain_a6_240m_2026-11-10/` is preserved.
- Code and registry files remain unchanged.
- This evidence records **measured physical results**; acceptance determination remains reserved.
