# V-12 against the LROC WAC south-pole illumination maps (Phase 4, A12), 2026-11-10

**Status: implemented and tested; V-12 is NOT validated.**
- **Preliminary only:** the real-terrain run below uses the currently registered terrain and is reported as "not run". It is not merged into the validation report.
- **When a run can be final:** only with the A5 20 m terrain and the wider 240 m terrain registered and A6 complete (`FINAL_PREREQUISITES`). Until then the script reports "not run" whatever the metrics.

## Approved methodology (A12)
1. **Reference:** WAC **TWI** (time-weighted) is the primary reference; **PCT** (plain ratio) is a secondary sensitivity comparison.
2. **Rules:** LUNA-OPS Sun visibility under the **whole-disc (full)** and **any-part (any)** rules brackets the undocumented LROC threshold. The centre rule is reported for diagnosis.
3. **C1 (gating):** LROC TWI ≤ **1 %** wherever LUNA-OPS predicts permanent shadow over the period.
4. **C2 (not gating):** share of samples inside [full − s, any + s] for s = 0, **1.31 pp** (TWI−PCT RMS) and **3.0 pp** (TWI−PCT p95). No pass share is defined.
5. **C3:** reported benchmark only.
6. **Spatial:** the central LROC pixel is compared; its 3 × 3 neighbourhood is reported separately.
7. **Observer and period:** observer height **0 m**; period **2010-02-15 to 2011-02-05**, from the product README.

## Reference (`backend/validation/reference/lroc/`)

| | TWI (primary) | PCT (secondary) |
| --- | --- | --- |
| IMG (not stored) | `WAC_POLE_ILL_TWI_SOUTH_100M.IMG`, 5,904,896 B, MD5 `be37f6f4…3800c9db` (= PDS4 label) | `…PCT…`, 5,904,896 B, MD5 `86c5be41…fe34b31` (= PDS4 label) |
| Stored | PDS4 label, README, the attached 9,712-byte PDS3 header | same |

Source: `LROLRC_2001` (LRO-L-LROC-5-RDR-V1.0), BDR `WAC_POLE`, v1.3, on the PDS cloud archive. SHA-256 hashes, URLs and facts are in `provenance.json`; a local `.gitattributes` keeps the fixtures byte-exact.

**Format:**
- PC_REAL 32-bit, 1214 × 1214, 100 m/pixel.
- Polar stereographic on the 1737.4 km sphere, 88–90°S.
- `CORE_NULL` and saturation constants `0xFF7FFFFB`–`F` are treated as missing.
- Values are percent: TWI 0–71.67, PCT 0–71.58, with tiny negatives ≥ −1e-5 that are zeros.

**Image offset 9712 (verified):**
- The attached PDS3 header has `RECORD_BYTES = 4856`, `LABEL_RECORDS = 2` and `^IMAGE = 3`, and the file size equals header + image.
- The PDS4 label's Array offset of **4856 is wrong**: it points into the header and yields values up to about 1e19.
- The PDS4 `upperleft_corner_x/y` (+60650) is also inconsistent with the grid.

**Geotransform `[100, 0, −60700, 0, −100, 60700]`:** it equals LROC's own GeoTIFF browse product, whose 8-bit values correlate 0.99999 with the float map read at byte 9712.

**Speyerer & Robinson (2013) could not be obtained through an authorized route:**
- NASA ADS has no e-print, author or ADS PDF.
- The publisher returns 403 to automated access and reserves text-and-data mining (`tdm-reservation: 1`).
- NASA NTRS has only a related 2016 abstract.

The binary threshold, the spatial filters and the registration accuracy therefore remain unquantified. This is why the rules are bracketed rather than one being chosen. (To try these routes I added `doi.org`, `linkinghub.elsevier.com`, `www.sciencedirect.com` and `ntrs.nasa.gov` to the session environment's allowed hosts, with approval.)

## Reference analyses (`reference_analysis.txt`, `reference_analysis.py`)
1. **TWI − PCT** over 1,155,716 pixels: mean 0.009, RMS **1.314**, p95 **3.024**, max 7.89 pp. These are the C2 slacks.
2. **Scattered light:** at 71,346 PGDA 90 permanent-shadow interior points (2-cell margin) in 88–90°S, 99.4 % of TWI values are exactly 0, the 99.9th percentile is 0.033 % and the maximum is 0.87 %, the basis of C1's 1 %. PCT has a maximum of 0.06 %.
3. **Co-registration** with the PGDA 90 frame: LROC zero pixels against fully shadowed LPSR pixels give the best IoU, 0.863, at **zero shift** (0.858–0.860 at ±1 pixel).
4. **LROC against LOLA AVGVISIB** (18.6-year modelled, "any" rule, 100 m block mean): TWI is 1.90 pp lower, RMSE 4.32 pp, r = 0.954. That is consistent with a stricter-than-"any" threshold.
5. **WAC cadence:** the `WAC_POLE_MOVIE_SOUTH` file names (`wac_movie_south_epochs.json`, no frames downloaded) list 3,559 frames in the year (README: 3,807 + 229).
   - Median interval 1.88 h; 31 gaps longer than 6 h, totalling 581 h.
   - This supports comparing TWI with a time-uniform average.

## Method (`backend/validation/v12_lroc.py`)
**Sampling:**
- Deterministic and stratified: 200 TWI pixels whose whole 3 × 3 neighbourhood is valid.
- Six strata: 0–1, 1–10, 10–20, 20–30, 30–45 and 45–100 %, drawn with `default_rng([seed, stratum])` and the V-09/V-10 allocation.

**Sun visibility, vectorised:**
- **Time sampling:** uniform, every 600 s over the period (51,120 samples).
- **Clearances:** for each rule, the deciding clearance comes from the exact spherical cap (`disk_edges_many`): top edge for "any", centre for "centre", bottom edge for "full".
- **Engine fallback:** samples within 1e-3° of zero, and samples in which Earth's outer circle reaches the Sun's disc, are decided by the engine's own `full_state`, so Earth occultation is exact.
- **Scoring:** a point is scored only with a complete horizon.

**Cross-check against the event detector** (`crosscheck_detector.txt`): **11,454 epoch-rule pairs, 0 mismatches.**

| Case | Result |
| --- | --- |
| Synthetic V-14 horizon, a synodic month hourly at 2 sites (2010-06, 2010-09) | equal |
| Synthetic V-14 horizon, 10 days every 10 min at a third site | equal |
| 21 December 2010 total lunar eclipse, every minute at 2 sites | equal; any / centre / full = 322 / 261 / 199 of 480 min |

Speed: 0.00–0.10 s per site-month against 11–58 s for the detector.

**Time-step sensitivity** (`preliminary_run/step_sensitivity.json`): 120 s against 600 s at 20 points changes any / centre / full by at most 0.003 / 0.001 / 0.002 pp.

## Preliminary real-terrain run (`preliminary_run/`)
**Setup:**
- 200 samples, observer at 0 m, production kernels, 971 s.
- **Terrain:** the registered 80 m PGDA 90 and 5 m PGDA 78 Site01 DEMs, SHA-verified against the registry and served through `LUNAOPS_DEM_FALLBACK_DIRS`; `data/` and the registry were not touched.
- **Status:** "not run" (preliminary: 20 m and 240 m terrain not registered; A6 not complete).
- **Scored:** 161 / 200. 39 are inconclusive because of incomplete horizons; 36 of them are in the two brightest strata, the same 250 km window / data-edge gap as in A10/A11.

| Criterion | Result |
| --- | --- |
| **C1** (gating) | 26 samples with predicted permanent shadow; all TWI ≤ 0.022 % (maximum), PCT likewise: **would pass** |
| C2 TWI in [full, any] | 110 / 161 (68 %); with 1.31 pp 131 / 161 (81 %); with 3.0 pp 144 / 161 (89 %) |
| C2 PCT in [full, any] | 104 (65 %); with 1.31 pp 135 (84 %); with 3.0 pp 146 (91 %) |
| C2 3 × 3 (separate) | [full, any] overlaps the TWI 3 × 3 range at 140 / 161 |
| C3 RMSE against TWI | any 5.33, centre 4.52, full 4.76 pp; LOLA AVGVISIB at the same samples 5.51 pp |
| C3 bias (TWI − model) | any −2.31, centre −0.48, full +1.33 pp; AVGVISIB −2.01 pp |

**By stratum** (mean TWI − rule, pp; samples inside [full, any] without slack):

| TWI stratum | Scored | − any | − centre | − full | Inside |
| --- | --- | --- | --- | --- | --- |
| 0–1 % | 34 | −0.18 | −0.05 | +0.02 | 30 |
| 1–10 % | 34 | −1.96 | −0.46 | +0.99 | 22 |
| 10–20 % | 33 | −4.41 | −1.78 | +0.86 | 22 |
| 20–30 % | 30 | −4.10 | −1.07 | +1.84 | 23 |
| 30–45 % | 15 (18 inconclusive) | −2.27 | +0.38 | +2.98 | 10 |
| 45–100 % | 15 (18 inconclusive) | +0.19 | +1.67 | +3.43 | 3 |

**Reading:**
- Up to 30 % the LROC value lies between the whole-disc and any-part predictions and is closest to the centre rule.
- In the brightest stratum LROC is near the any-part prediction. Only 15 of 33 samples there could be scored; the 80 m terrain and the incomplete horizons limit this stratum. A5 (20 m) and the 240 m terrain address both.

## Tests (`backend/tests/test_phase4_v12.py`, 11)
- **Fixtures and provenance:** hashes; the IMG MD5 equals the PDS4 label's; the PDS4 offset 4856 is recorded; README facts; approved constants.
- **Reader** (real attached header plus synthetic data): offset 9712; specials become NaN; values; a read that yields > 100 % is refused; a short file is refused.
- **Sampling:** stratified, deterministic, full 3 × 3 neighbourhood; tiny negatives count as zeros.
- **AVGVISIB block mean.**
- **Engine agreement:**
  - the three rules equal the event detector on the synthetic V-14 horizon;
  - the 2010-12-21 eclipse equals the detector, with full < centre < any;
  - the guard band only routes samples to the engine.
- **Inconclusive** for incomplete or missing terrain.
- **Criteria and status:** C1 pass/fail; C2 slack counts; the 3 × 3 count; C3; inconclusive; the preliminary run is never final.
- **Current terrain** does not meet the final prerequisites.
- **End-to-end and merge.**

**Suites** (`tests/`): `test_phase4_v12` 11 passed; production kernels **396 passed, 12 skipped**; sandbox kernels **393 passed, 15 skipped**; exit 0. The first full run failed one test, `test_phase3_labels::test_v12_stub_refuses_to_produce_a_result`, which encoded the old blocked stub (it expected the word "blocked"). It was updated to the new contract: without the reference maps `v12_lroc` exits with an error and writes no result. Both suites were then rerun.

## Before a final V-12
1. Complete A5 (register the 20 m PGDA 90 terrain) and A6, and register the 240 m `LDEM_60S_240MPP_ADJ` with its error map.
2. Set `FINAL_PREREQUISITES["a6_complete"]` once A6 is accepted.
3. Repeat the run. C1 decides V-12; C2 and C3 are reported.
4. Optionally, if the paper becomes available, record the threshold, filters and registration accuracy in provenance.
