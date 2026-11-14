# Phase 5 source data catalogue and provenance

Each entry was read from the product's own page, README or file metadata on 2026-11-13. "Not stated" means the source does not give the value; nothing is filled in by assumption.

## A. Integrated: products the Landing screening reads

### A1. Registered LOLA DEMs (existing production terrain, read only)

| Level | Product (registry) | Grid | Coverage | Error map | Count map |
|---|---|---|---|---|---|
| 5 m | PGDA 78 `Site01_final_adj_5mpp_surf.tif` (SHA-256 `3ba7b97c…`) | 3200 × 3200, x −19 to −3 km, y −20 to −4 km | 16 × 16 km "Connecting ridge" site | `_toterr` (total Z uncertainty, m) | yes, `_ldec` (A2) |
| 20 m | PGDA 90 `LDEM_80S_20MPP_ADJ.TIF` (`09b7ca80…`) | 30400 × 30400 | 80–90° S | `_ERR` (m) | none published with this product here |
| 80 m | PGDA 90 `LDEM_80S_80MPP_ADJ.tiff` (`82030dcb…`) | 7600 × 7600 | 80–90° S | `_ERR` (m) | none |
| 240 m | PGDA 90 `LDEM_60S_240MPP_ADJ.TIF` (`3f966325…`) | 7760 × 7760 | 60–90° S | `_ERR` (m) | none |

- **Frame and projection.** The dataset manifest and the PGDA README give every product as "south polar stereographic X/Y coords in meters, MOON_ME reference frame of ephemeris DE421".
  - The CRS is the spherical south polar stereographic projection on the 1737.4 km sphere, true scale at the pole.
  - The engine checks its analytic transform against each file's CRS to better than 1 mm at registration.
  - All Phase 5 products share this one frame and projection; no DE421/DE440 mixing occurs.
- **Vertical:** height in metres above the 1737.4 km reference sphere.
- **Missing data:** NaN, plus the engine's ±20 km plausibility bound; Phase 5 reads heights through the engine's own reader.
- **Pixel registration:** Area (pixel-registered; GMT `node_offset = 1`).
- **Interpolation.** PGDA 78 says the 5 m `surf` heights are "surface height Z (meters) with interpolation filling empty pix". The product page gives about 90% of 5 m pixels as interpolated, and the count map confirms this (A2).
- **Accuracy (PGDA 78 product page):** median RMS Z error about 0.30–0.50 m and median RMS slope error about 1.5–2.5°. Horizontal track geolocation uncertainty is about 10–20 cm, vertical about 2–4 cm.
- **Citations.** PGDA 78: Barker et al. 2021, PSS 203, 105119, doi:10.1016/j.pss.2020.105119. PGDA 90: Barker et al. 2023, PSJ 4, 183, doi:10.3847/PSJ/acf3e1.

### A2. New: PGDA 78 Site01 auxiliary files (approved decision 1)

**Source:** `https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site01/`.
- Downloaded to `E:\Temp\LUNA-OPS\downloads\pgda78_site01\` after checking free space on E: (135 GB free).
- Copied into `data/landing/pgda78_site01/` and recorded in `data/landing/manifest.json` by `python -m lunaops_landing.acquire register`.
- The production `data/dem/registry.json` was not written; its SHA-256 `e664976c…` is unchanged.

| File | Kind | Bytes (= server Content-Length) | Server Last-Modified | SHA-256 | Values (whole file) |
|---|---|---|---|---|---|
| `Site01_final_adj_5mpp_ldec.tif` | LDEC count map: LOLA returns per pixel | 40,980,744 | 05 Jun 2020 | `16d6ed21…` | 0 to 5; 9.49% of pixels ≥ 1 |
| `Site01_final_adj_5mpp_slp.tif` | NASA slope (degrees) | 40,980,776 | 08 Jun 2020 | `3a90035a…` | 0 to 64.59°, mean 12.6° |
| `Site01_final_adj_5mpp_slperr.tif` | slope uncertainty (degrees, RMS) | 40,980,810 | 05 Jun 2020 | `52bc3b23…` | 0.61 to 21.51°, mean 2.00° |

- **Verified for each file** (`logs/01_site01_extras_metadata.txt`; the registration tool refuses any mismatch):
  - float32, nodata NaN, no NaN present;
  - CRS equal to the Site01 DEM's CRS (pyproj `CRS.equals`);
  - transform and size equal to the DEM's;
  - AREA_OR_POINT = Area.
- **Measured versus interpolated.** 9.49% of pixels hold at least one LOLA return. This independently confirms PGDA's "~90% interpolated" for Site01.
- **Slope method.** The README does not state the baseline or method of the NASA slope product. The comparison in README "NASA slope comparison" shows it matches 2-pixel central differences of the same DEM to 0.008° RMS.

## B. Investigated but not integrated

| Product | What it is (from its page) | Why not integrated |
|---|---|---|
| **PGDA 104**, Enhanced Topography Models for Selected Lunar South Pole Regions with Shape-from-Shading (Bertone et al., PSJ, doi:10.3847/PSJ/ae5b70; data Zenodo doi:10.5281/zenodo.17954508, CC-BY-4.0) | 5 m SfS DEMs from LROC NAC images on an a priori LOLA DEM (Ames Stereo Pipeline). 13 Artemis III candidate regions. One zip each, 1.1–4.4 GB, 26.6 GB in all; "Connecting Ridge" (covers Site01) is 2.2 GB. Includes slope and VRM roughness. | **Approved decision 2: not downloaded.** The record page states "Moon (2015) South Polar Stereographic" and 5 m pixels, but not the reference frame (DE421 or DE440), vertical datum or missing-data value. Detail is added only in illuminated areas. These are image-derived heights, not LOLA heights, and would need their own labelling and verification before use. |
| **PGDA 81**, South Pole LOLA DEM Mosaic, 87–90° S, 5 m (`ldem_87s_5mpp.tif`, 3.3 GB) | Listed in the existing dataset manifest; "97 individual 20 × 20 km fields … rigidly aligned". | Several-gigabyte regional product. Not needed for the approved scope; the registered Site01 and PGDA 90 products are used. |
| **Other PGDA 78 sites** (Site04, 06, 07, 11, 20, 23, …) | The same 5 m product family as Site01, each with its own `ldec`, `slp`, `toterr`, `slperr`. | Not registered as DEMs in this installation; registering new production terrain is outside Phase 5. |
| **LROC PDS** (EDR, CDR, RDR volumes) | Raw, calibrated and derived archives. The RDR page now redirects to the NASA PDS portal (`pds.mcp.nasa.gov`). | No obstacle or boulder product is offered. NAC images are hundreds of MB each, and automated boulder detection from them is not supported by verified tools or metadata here. **Approved decision 3:** the obstacle finding is "Not available - manual review required". |
| **Robbins (2018) lunar crater database** (USGS Astrogeology) | Global crater catalogue. | The USGS page refused automated access (HTTP 403), so its contents, format and size were not verified. No crater catalogue is integrated, and every depression stays an *unconfirmed candidate*. |

## C. Synthetic test terrain (isolated)

`backend/lunaops_landing/tests/conftest.py` writes a 10 m synthetic DEM, error map and count map into a fresh temporary data folder.
- `LUNAOPS_DATA_DIR` is set before `lunaops` is imported; the folder lives under `E:\Temp\LUNA-OPS` when TEMP points there and is deleted after the session.
- The terrain is flagged `synthetic` and labelled "SYNTHETIC TEST TERRAIN - NOT LUNAR DATA".
- It is never written to `data/dem/registry.json` or `data/landing/`.
