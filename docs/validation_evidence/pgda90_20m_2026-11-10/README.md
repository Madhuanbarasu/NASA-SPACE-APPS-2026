# Phase 4 A5: NASA PGDA90 20 m DEM Acquisition & Registration Evidence

**Date:** 2026-11-10
**Algorithm Version:** 1.5.0 (`lunaops.ALGORITHM_VERSION`)
**Feature Branch:** `phase4-a5-pgda90-20m-integration`

## 1. Overview
Phase 4 A5 incorporates the NASA Planetary Geodynamics Laboratory (PGDA) 90 LOLA 20 m/pixel south polar regional Digital Elevation Model (DEM) and its corresponding height uncertainty error map into the LUNA-OPS science engine.

This establishes the 3-tier terrain resolution hierarchy:
1. **5 m/pixel** (PGDA 78 Site01 local site DEM, priority 40, half-width 8 km)
2. **20 m/pixel** (PGDA 90 regional DEM, priority 50, half-width 40 km, coverage 80°S–90°S)
3. **80 m/pixel** (PGDA 90 regional DEM, priority 50, half-width 250 km, coverage 80°S–90°S)

## 2. Acquired Datasets
- **Surface DEM (`LDEM_80S_20MPP_ADJ.TIF`):**
  - Source: `https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_20MPP_ADJ.TIF`
  - Destination: `data/dem/pgda90_20m/LDEM_80S_20MPP_ADJ.TIF`
  - Bytes: 2,696,082,051 bytes (exact match)
  - SHA-256: `09b7ca80f9e6a146f970225d18af72fc02787669b3ef51b888e347d2b6845649`
  - Dimensions: 30400 × 30400 pixels (608 km × 608 km)
  - Coordinate System: IAU:30135 (Moon 2015 South Polar Stereographic)
- **Error Map (`LDEM_80S_20MPP_ADJ_ERR.TIF`):**
  - Source: `https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_20MPP_ADJ_ERR.TIF`
  - Destination: `data/dem/pgda90_20m/LDEM_80S_20MPP_ADJ_ERR.TIF`
  - Bytes: 3,954,709,201 bytes (exact match)
  - SHA-256: `d64045b8aa58a24010f009ab5667ae02cc06cffa7796784dd5e2d48b3059d8cf`
  - Dimensions: 30400 × 30400 pixels (identical grid alignment)

## 3. Registration
Registered using the verified acquisition CLI:
```bash
python -m lunaops.acquire register-dem \
  --product pgda90_20m \
  --file data/dem/pgda90_20m/LDEM_80S_20MPP_ADJ.TIF \
  --error-map data/dem/pgda90_20m/LDEM_80S_20MPP_ADJ_ERR.TIF
```
Registered outputs recorded in `data/dem/registry.json`.

## 4. Verification Evidence
- `independent_hashes.txt`: Independent SHA-256 calculation and raster geometry verification.
- `registration_meta.json`: Complete registration metadata.
- `acquire_status.log`: `python -m lunaops.acquire status` output showing 3 registered products and 3 linked error maps.
- `acquire_verify.log`: `python -m lunaops.acquire verify` output re-hashing all registered DEM and error map files.
- `pytest_pgda90_integration.log`: 15 passed tests in `backend/tests/test_pgda90_integration.py`.
- `pytest_audit_fixes.log`: 12 passed tests in `backend/tests/test_audit_fixes.py`.
