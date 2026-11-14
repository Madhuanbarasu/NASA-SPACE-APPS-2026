# Phase 4 A6: Measurement Provenance Corrigendum

**Document Date:** 2026-11-11  
**Target Package:** `docs/validation_evidence/terrain_a6_2026-11-10/`  
**Reference Document:** `docs/validation_evidence/terrain_a6_2026-11-10/ACCEPTANCE.md`  
**Canonical Gate Record:** `backend/validation/reference/terrain_acceptance.json`  
**Canonical Acceptance Digest:** `e48eb8ed0ca2003c2769c60932323dbce34385e4eac2a675f076e13bbd943dce`  
**Algorithm Version:** 1.5.0 (`lunaops.ALGORITHM_VERSION`)

---

## 1. Executive Summary and Scope

This corrigendum provides formal provenance reconciliation for three human-readable narrative descriptions in [`backend/validation/reference/terrain_acceptance.json`](file:///E:/LUNA-OPS/backend/validation/reference/terrain_acceptance.json).

In accordance with strict configuration management and cryptographic merge-guard rules:
* The machine-readable file `terrain_acceptance.json` is **cryptographically bound** to external validation reports (V-09, V-10, V-11, V-12) via `terrain_gate.acceptance_digest()`.
* Modifying any string inside `terrain_acceptance.json` would alter the canonical digest (`e48eb8ed...`), invalidate existing production validation runs, and trigger rejection under `backend/validation/common.py:merge_external()`.
* Therefore, `terrain_acceptance.json` remains **strictly byte-for-byte unchanged** (raw SHA-256: `c04650699f1cdade46b29614fc4f9b2dd20d27eb3b99fd32b9a8e72a892356ae`).
* This document serves as the permanent, authoritative audit record explaining three editorial transcription discrepancies in the JSON narrative fields.

---

## 2. Mathematical Role of the Allowance in the Science Engine

In [`backend/lunaops/engine/horizon.py:cross_product_discrepancy()`](file:///E:/LUNA-OPS/backend/lunaops/engine/horizon.py#L368-L389), the cross-product allowance is evaluated by sampling finer elevations at pixel centers and comparing them against bilinear interpolated coarser elevations:

```python
diff = hf[ok] - hc[ok]
mean, std = float(np.mean(diff)), float(np.std(diff))
rms = float(np.sqrt(np.mean(diff ** 2)))
return {**base, "status": "measured", "mean_m": mean, "std_m": std, "rms_m": rms, "allowance_m": rms}
```

* **Governing Metric:** The approved allowance assigned in the engine (`allowance_m`) is **strictly determined by the Root Mean Square (RMS) discrepancy**:
  $$\text{RMS} = \sqrt{\frac{1}{n}\sum_{i=1}^n (h_{\text{fine}, i} - h_{\text{coarse}, i})^2} = \sqrt{\mu^2 + \sigma^2}$$
* **Engine Isolation:** The narrative `"measurement"` string in `terrain_acceptance.json` is human-readable documentation. The science engine never parses this string; it binds only to the numerical allowance and registered raster SHA-256 hashes.
* **Authoritative Approval:** User Request 6 (Step 3240, `2026-11-10T17:03:14Z`) formally approved all six overlapping pairs following the completed implementation-readiness review (Step 3115), adopting the exact cross-product RMS allowances:
  * 5m / 20m: **$0.527\text{ m}$**
  * 5m / 80m: **$1.224\text{ m}$**
  * 20m / 80m: **$1.105\text{ m}$**
  * 5m / 240m: **$4.314\text{ m}$**
  * 20m / 240m: **$2.735\text{ m}$**
  * 80m / 240m: **$2.620\text{ m}$**
* All numerical allowances remain **100% correct and unchanged**. The corrections below pertain solely to descriptive text.

---

## 3. Discrepancy Reconciliation

### 3.1 Pair 5m / 240m: Window Tile vs. Radial Annulus

#### Text in `terrain_acceptance.json`:
> `"cross-product allowance around Site01 (4-8 km annulus): n 4489, mean +0.1504 m, RMS 4.3136 m; allowance 4.314 m"`

#### Verified Physical Measurements:
1. **Site01 Cross-Product Allowance (Window Intersection)**:
   * **Region:** Site01 tile footprint ($16\text{ km} \times 16\text{ km}$, bounds `[-19000, -20000, -3000, -4000]` m).
   * **Method:** `cross_product_discrepancy()`, grid sampling at pixel centers of the 5m DEM at stride 48 px ($240\text{ m} / 5\text{ m} = 48$); coarser 240m DEM evaluated via `bilinear_many()`.
   * **Sign Convention:** $\Delta z = z_{5\text{m}} - z_{240\text{m}}$ (finer minus coarser).
   * **Sample Count:** $n = 4,489$ valid pairs.
   * **Mean Bias ($\mu$):** $+0.1504\text{ m}$ ($+0.1503686\text{ m}$).
   * **Population Std ($\sigma$):** $4.3110\text{ m}$.
   * **Cross-Product RMS:** **$4.3136\text{ m}$** ($4.3135831\text{ m}$).
   * **Approved Allowance ($s_x$):** **$4.314\text{ m}$** (RMS rounded up).
   * **Source Report:** [`docs/validation_evidence/terrain_a6_240m_2026-11-10/benchmark_locations_report.json`](file:///E:/LUNA-OPS/docs/validation_evidence/terrain_a6_240m_2026-11-10/benchmark_locations_report.json) (`Site01 (Connecting Ridge)`).
   * **Source Log:** [`docs/validation_evidence/terrain_a6_240m_2026-11-10/benchmark_locations_output.txt`](file:///E:/LUNA-OPS/docs/validation_evidence/terrain_a6_240m_2026-11-10/benchmark_locations_output.txt).

2. **Supplementary Site01 4–8 km Annulus Comparison**:
   * **Region:** Radial annulus $4\text{ km} \le r \le 8\text{ km}$ centered on Site01 Connecting Ridge.
   * **Method:** Bilinear interpolation vs. nearest-neighbour sampling across annulus points.
   * **Sign Convention:** $\Delta z = z_{5\text{m}} - z_{240\text{m}}$.
   * **Sample Count:** $n = 2,617$ valid pairs.
   * **Mean Bias ($\mu$):** $+0.0130\text{ m}$ ($1.3\text{ cm}$).
   * **Population Std ($\sigma$):** $4.3247\text{ m}$.
   * **Annulus Bilinear RMS:** **$4.3247\text{ m}$** (Nearest-Neighbour RMS $= 12.4264\text{ m}$).
   * **Source Report:** [`docs/validation_evidence/terrain_a6_acceptance_review_2026-11-10/README.md`](file:///E:/LUNA-OPS/docs/validation_evidence/terrain_a6_acceptance_review_2026-11-10/README.md#L141-L149) and [`docs/validation_evidence/terrain_a6_acceptance_review_2026-11-10/acceptance_review.json`](file:///E:/LUNA-OPS/docs/validation_evidence/terrain_a6_acceptance_review_2026-11-10/acceptance_review.json).

#### Editorial Cause:
When drafting the acceptance entry, the author copied the phrase `(4-8 km annulus)` from the Pair 1 (5m/20m) template and inadvertently attached it to the $n = 4,489$ tile window metrics. The allowance ($4.314\text{ m}$) was derived correctly from the $n = 4,489$ cross-product RMS ($4.3136\text{ m}$).

---

### 3.2 Pair 20m / 240m: Polar-Wide Mean Bias Transcription

#### Text in `terrain_acceptance.json`:
> `"cross-product allowance at Site01: n 27889, mean -0.0307 m, RMS 2.7354 m; allowance 2.735 m; polar-wide circular disk (80-90 S): n 113373, mean -0.0465 m, RMS 3.1322 m"`

#### Verified Physical Measurements:
1. **Site01 Cross-Product Allowance (Regional Window)**:
   * **Region:** Site01 regional window ($127\text{ km} \times 127\text{ km}$).
   * **Method:** `cross_product_discrepancy()`, stride 24 px; bilinear interpolation of 240m DEM.
   * **Sign Convention:** $\Delta z = z_{20\text{m}} - z_{240\text{m}}$.
   * **Sample Count:** $n = 27,889$ valid pairs.
   * **Mean Bias ($\mu$):** $-0.0307\text{ m}$ ($-0.0307349\text{ m}$).
   * **Population Std ($\sigma$):** $2.7352\text{ m}$.
   * **Cross-Product RMS:** **$2.7354\text{ m}$**.
   * **Approved Allowance ($s_x$):** **$2.735\text{ m}$**.
   * **Source Report:** [`docs/validation_evidence/terrain_a6_240m_2026-11-10/benchmark_locations_report.json`](file:///E:/LUNA-OPS/docs/validation_evidence/terrain_a6_240m_2026-11-10/benchmark_locations_report.json).

2. **Supplementary Polar-Wide Circular Disk Evaluation**:
   * **Region:** True circular polar cap $r \le 304,000\text{ m}$ ($80^\circ\text{S}\text{--}90^\circ\text{S}$) in IAU:30135 South Polar Stereographic projection.
   * **Method:** Regular grid lattice ($380 \times 380 = 144,400$ candidate points, $1,600.0\text{ m}$ spacing) filtered by radial mask $r^2 \le 304,000^2$. 20m sampled via memory-bounded chunked bilinear interpolation; 240m sampled via `bilinear_many()`.
   * **Sign Convention:** $\Delta z = z_{20\text{m}} - z_{240\text{m}}$.
   * **Sample Count:** $n = 113,373$ valid pairs (31,027 radial exclusions).
   * **Mean Bias ($\mu$):** $\mathbf{+0.0112\text{ m}}$ ($+0.0112039\text{ m}$, $1.1\text{ cm}$ geodetic alignment).
   * **Population Std ($\sigma$):** $3.1323\text{ m}$ ($3.1322973\text{ m}$).
   * **Polar-Wide RMS:** **$3.1323\text{ m}$** ($3.1323174\text{ m}$).
   * **Source Report:** [`docs/validation_evidence/terrain_a6_polar_wide_corrected_2026-11-10/polar_wide_report.json`](file:///E:/LUNA-OPS/docs/validation_evidence/terrain_a6_polar_wide_corrected_2026-11-10/polar_wide_report.json) (`primary_circular_polar_disk["pairwise_evaluations"]["20m_vs_240m"]`).
   * **Source Log:** [`docs/validation_evidence/terrain_a6_polar_wide_corrected_2026-11-10/polar_wide_output.txt`](file:///E:/LUNA-OPS/docs/validation_evidence/terrain_a6_polar_wide_corrected_2026-11-10/polar_wide_output.txt).

#### Editorial Cause:
In `terrain_acceptance.json` line 54 (for 20m/80m), the description reads:
`"polar-wide circular disk (80-90 S, 113373 points): mean -0.0465 m, RMS 0.5794 m"`.
The author copy-pasted `mean -0.0465 m` directly from the 20m/80m line into the 20m/240m line while correctly transcribing the RMS ($3.1322\text{ m}$). The true circular disk mean for 20m/240m is **$+0.0112\text{ m}$**.

---

### 3.3 Pair 80m / 240m: Boundary Diagnostic Transcription

#### Text in `terrain_acceptance.json`:
> `"cross-product allowance at Site01: n 36100, mean -0.000037 m, RMS 2.6199 m; allowance 2.620 m; polar-wide circular disk (80-90 S): n 113373, mean -0.0007 m, RMS 2.9344 m"`

#### Verified Physical Measurements:
1. **Site01 Cross-Product Allowance (Regional Window)**:
   * **Region:** Site01 regional window ($127\text{ km} \times 127\text{ km}$).
   * **Method:** `cross_product_discrepancy()`, stride 33 px; bilinear interpolation of 240m DEM.
   * **Sign Convention:** $\Delta z = z_{80\text{m}} - z_{240\text{m}}$.
   * **Sample Count:** $n = 36,100$ valid pairs.
   * **Mean Bias ($\mu$):** $-0.000037\text{ m}$ ($-0.037\text{ mm}$).
   * **Population Std ($\sigma$):** $2.6199\text{ m}$.
   * **Cross-Product RMS:** **$2.6199\text{ m}$**.
   * **Approved Allowance ($s_x$):** **$2.620\text{ m}$**.
   * **Source Report:** [`docs/validation_evidence/terrain_a6_240m_2026-11-10/benchmark_locations_report.json`](file:///E:/LUNA-OPS/docs/validation_evidence/terrain_a6_240m_2026-11-10/benchmark_locations_report.json).

2. **Supplementary Polar-Wide Circular Disk Evaluation**:
   * **Region:** True circular polar cap $r \le 304,000\text{ m}$ ($80^\circ\text{S}\text{--}90^\circ\text{S}$) in IAU:30135.
   * **Method:** Regular grid lattice ($380 \times 380 = 144,400$ candidate points, $1,600.0\text{ m}$ spacing) filtered by radial mask $r^2 \le 304,000^2$. 80m sampled at exact pixel centers; 240m sampled via `bilinear_many()`.
   * **Sign Convention:** $\Delta z = z_{80\text{m}} - z_{240\text{m}}$.
   * **Sample Count:** $n = 113,373$ valid pairs (31,027 radial exclusions).
   * **Mean Bias ($\mu$):** $\mathbf{+0.0092\text{ m}}$ ($+0.0091744\text{ m}$, $9.2\text{ mm}$ geodetic alignment).
   * **Population Std ($\sigma$):** $2.9341\text{ m}$ ($2.9340514\text{ m}$).
   * **Polar-Wide RMS:** **$2.9341\text{ m}$** ($2.9340658\text{ m}$).
   * **Source Report:** [`docs/validation_evidence/terrain_a6_polar_wide_corrected_2026-11-10/polar_wide_report.json`](file:///E:/LUNA-OPS/docs/validation_evidence/terrain_a6_polar_wide_corrected_2026-11-10/polar_wide_report.json) (`primary_circular_polar_disk["pairwise_evaluations"]["80m_vs_240m"]`).
   * **Source Log:** [`docs/validation_evidence/terrain_a6_polar_wide_corrected_2026-11-10/polar_wide_output.txt`](file:///E:/LUNA-OPS/docs/validation_evidence/terrain_a6_polar_wide_corrected_2026-11-10/polar_wide_output.txt).

#### Editorial Cause:
In the 80.5°S boundary diagnostic across four cardinal quadrants ([`acceptance_review.json`](file:///E:/LUNA-OPS/docs/validation_evidence/terrain_a6_acceptance_review_2026-11-10/acceptance_review.json)), the combined mean bias was $-0.0008\text{ m}$, rounded to `-0.0007 m`. When summarizing the circular disk in the acceptance JSON, the boundary diagnostic mean and an intermediate unrounded RMS ($2.9344\text{ m}$) were mistakenly typed into the circular disk clause. The actual polar-wide circular disk values are $\mu = \mathbf{+0.0092\text{ m}}$ and $\text{RMS} = \mathbf{2.9341\text{ m}}$.

---

## 4. Master Provenance Summary Table

| Overlapping Pair | Operational Metric / Scope | Text Literal in Acceptance JSON | True Verified Empirical Value | Governing Engine Statistic | Primary Source Artifact |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **5m / 240m** | **Allowance Basis (Site01 Tile)** | `"n 4489, mean +0.1504 m, RMS 4.3136 m; allowance 4.314 m"` *(erroneously labelled annulus)* | $n = 4,489$, $\mu = +0.1504\text{ m}$, $\text{RMS} = \mathbf{4.3136\text{ m}}$ | **Cross-Product RMS ($4.314\text{ m}$)** | [`benchmark_locations_report.json`](file:///E:/LUNA-OPS/docs/validation_evidence/terrain_a6_240m_2026-11-10/benchmark_locations_report.json) |
| **5m / 240m** | Supplementary Annulus (4–8 km) | Not explicitly distinguished | $n = 2,617$, $\mu = +0.0130\text{ m}$, $\text{RMS} = 4.3247\text{ m}$ | Diagnostic only | [`acceptance_review/README.md`](file:///E:/LUNA-OPS/docs/validation_evidence/terrain_a6_acceptance_review_2026-11-10/README.md) |
| **20m / 240m** | **Allowance Basis (Site01 Window)** | `"n 27889, mean -0.0307 m, RMS 2.7354 m; allowance 2.735 m"` | $n = 27,889$, $\mu = -0.0307\text{ m}$, $\text{RMS} = \mathbf{2.7354\text{ m}}$ | **Cross-Product RMS ($2.735\text{ m}$)** | [`benchmark_locations_report.json`](file:///E:/LUNA-OPS/docs/validation_evidence/terrain_a6_240m_2026-11-10/benchmark_locations_report.json) |
| **20m / 240m** | Supplementary Polar Disk (80°S–90°S) | `"n 113373, mean -0.0465 m, RMS 3.1322 m"` *(mean copied from 20m/80m)* | $n = 113,373$, $\mathbf{\mu = +0.0112\text{ m}}$, $\text{RMS} = 3.1323\text{ m}$ | Supplementary check | [`polar_wide_report.json`](file:///E:/LUNA-OPS/docs/validation_evidence/terrain_a6_polar_wide_corrected_2026-11-10/polar_wide_report.json) |
| **80m / 240m** | **Allowance Basis (Site01 Window)** | `"n 36100, mean -0.000037 m, RMS 2.6199 m; allowance 2.620 m"` | $n = 36,100$, $\mu = -0.000037\text{ m}$, $\text{RMS} = \mathbf{2.6199\text{ m}}$ | **Cross-Product RMS ($2.620\text{ m}$)** | [`benchmark_locations_report.json`](file:///E:/LUNA-OPS/docs/validation_evidence/terrain_a6_240m_2026-11-10/benchmark_locations_report.json) |
| **80m / 240m** | Supplementary Polar Disk (80°S–90°S) | `"n 113373, mean -0.0007 m, RMS 2.9344 m"` *(mean copied from 80.5°S boundary)* | $n = 113,373$, $\mathbf{\mu = +0.0092\text{ m}}$, $\text{RMS} = 2.9341\text{ m}$ | Supplementary check | [`polar_wide_report.json`](file:///E:/LUNA-OPS/docs/validation_evidence/terrain_a6_polar_wide_corrected_2026-11-10/polar_wide_report.json) |

---

## 5. Architectural & Cryptographic Invariance

1. **Acceptance File Invariance**:
   `backend/validation/reference/terrain_acceptance.json` raw SHA-256 remains:
   `c04650699f1cdade46b29614fc4f9b2dd20d27eb3b99fd32b9a8e72a892356ae`.
2. **Digest Verification**:
   Executing `validation.terrain_gate.acceptance_digest()` confirms:
   `e48eb8ed0ca2003c2769c60932323dbce34385e4eac2a675f076e13bbd943dce`.
3. **Merge Guard Stability**:
   All final validation reports (V-09, V-10, V-11, V-12) maintain 100% cryptographic compatibility with the repository gate. No validation runs are rendered stale.

