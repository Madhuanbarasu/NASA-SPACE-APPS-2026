> **Historical document (status as of 2026-11-12).** This was the project README before Phase 7. Its setup steps, commands, algorithm notes and limitations remain the detailed technical reference, but its **validation status is out of date**: it predates the Phase 7 final validation of 2026-11-14, in which V-09 passed, **V-10 failed**, the full pytest suite was skipped and no Validated label is shown. For the current status see the top-level README.md and docs/validation_evidence/phase7_final_validation_2026-11-14/reports/PHASE7_FINAL_REPORT.md. Text unchanged below this note.

# LUNA-OPS: Lunar Landing Site Navigator

LUNA-OPS compares lunar south polar landing sites and dates by placing the Sun and Earth against the real terrain horizon. It reports when a site is sunlit, when Earth is in view for direct-to-Earth (DTE) contact, when both happen at once, and a labelled relative power-generation indicator. The Phase 1.1 Engineering Blueprint is the source of truth for every requirement, algorithm and test referenced below.

All scientific quantities are computed by the Python science engine. The API serves them unchanged, and the browser only visualizes them (blueprint C09).

## What is real, what you must download, what is synthetic

| Item | Status |
| --- | --- |
| Sun and Earth geometry | NASA/JPL SPICE via SpiceyPy (CSPICE N0067), DE440 ephemeris, `CN+S` aberration, pinned body-fixed frame `MOON_ME_DE440_ME421`. Earth is the IERS 2010 oblate spheroid (a = 6378.1366 km, 1/f = 298.25642) whose spin axis is the pole of date (CIP: IAU 2006 precession + IAU 2000B nutation, as SOFA/ERFA, about 1 mas; no atmosphere) |
| Terrain | NASA PGDA LOLA DEMs that **you download and register**. Nothing is substituted when terrain is missing |
| Site catalogue | Built only from files you register (USGS Artemis III region grids, PGDA 78 ROI shapefiles). No coordinates are built into the code |
| Synthetic terrain | Analytic test rasters for automated tests and demos. Refused unless enabled (`--demo` or `LUNAOPS_ALLOW_SYNTHETIC=1`) and labelled "not a lunar result" everywhere |
| Sandbox test kernels | A labelled kernel set for machines without NAIF access (tests and demos only), kept in `data/kernels_demo`, apart from the production kernels in `data/kernels`. Results are never marked Validated with it |

## Requirements

- Python **3.11, 3.12 or 3.13** (3.14 may lack wheels for the pinned scientific packages)
- About 11 GB free disk for the core LOLA terrain set (not needed for the demo)
- Node 20 or later (with npm) to build the interface once. `frontend/dist` is not kept in git; `start.py` builds it automatically the first time when npm is on your PATH (or run `cd frontend && npm ci && npm run build` yourself)

## Fastest way to see it running (any OS)

```bash
cd luna-ops
python -m pip install -r backend/requirements.txt
python start.py --demo
```

On Windows, use `py` instead of `python` if `python` is not found. The launcher checks Python and the packages, builds the interface once if `frontend/dist` is missing (about a minute; `--no-build` turns this off), prepares labelled test data, picks a free port, starts the server and opens your browser at the address it prints (usually http://localhost:8000). Keep that window open while you use the app; closing it stops the server.

Demo data never mix with NASA data: the test kernels go to `data/kernels_demo` and the synthetic terrain to `data/dem_demo` (its own registry), so the production kernels in `data/kernels` and the LOLA registry `data/dem/registry.json` are neither read nor changed by `--demo`.

Use `python start.py` (without `--demo`) once the NASA kernels and LOLA terrain are installed (steps below). If a terrain file named in `data/dem/registry.json` is not on disk, the launcher lists it and analyses that need it are refused with the file name until you restore it or unregister it.

## Full setup with NASA data

### 1. Python environment

macOS / Linux:
```bash
cd luna-ops/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows (PowerShell):
```powershell
cd luna-ops\backend
py -m venv .venv
.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope Process Bypass
pip install -r requirements.txt
```

All later commands run from `luna-ops/backend` with the environment active.

### 2. Pinned NAIF kernels (production)

```bash
python -m lunaops.acquire kernels
python -m lunaops.acquire verify-kernels
```

`kernels` installs the set pinned in `backend/lunaops/manifests/kernels.production.json` into `data/kernels`:

| Role | File | NAIF-published check |
| --- | --- | --- |
| Leap seconds | `naif0012.tls` | 5,257 bytes, MD5 `25a2fff30b0dedb4d76c06727b1895b1` (NAIF PDS4 label) |
| Text PCK | `pck00011.tpc` | none published; SHA-256 pinned on first download |
| Planetary ephemeris | `de440s.bsp` (DE440, 1849-2150, 31 MB) | MD5 from NAIF's `aa_checksums.txt`, fetched at download time |
| Lunar orientation (DE440) | `moon_pa_de440_200625.bpc` | none published; SHA-256 pinned on first download |
| Lunar frames (DE440) | `moon_de440_250416.tf` (authoritative; IB-2 resolved), fallback `moon_de440_220930.tf` from NAIF's `a_old_versions` | 250416: 19,478 bytes, MD5 `3556dde4bb7ca54a89917c301e650bbf` (NAIF CLPS PDS4 label) |
| DE421 validation PCK/FK (optional, for V-02e) | `moon_pa_de421_1900-2050.bpc`, `moon_080317.tf` | none published; SHA-256 pinned on first download |

Every file is downloaded into `data/kernels/.staging`, checked against the published values above (a mismatch rejects the file and tries the next source or the fallback), and the staged set is test-loaded with SPICE (frames, coverage, radii). Only then does it replace the installed set, with `lock.json` written last; the previous set is kept in `data/kernels/superseded_<UTC>/`. Any failure leaves the installed set untouched. `verify-kernels` re-checks sizes, SHA-256 against the lock and the NAIF-published values, test-loads the set, and says whether V-02e can run.

**Lunar frame kernel (IB-2, resolved 2026-11-09).** `moon_de440_250416.tf` is the authoritative DE440 lunar frame kernel: NAIF's frame-kernel readme (`generic_kernels/fk/satellites/aareadme.txt`, revised 2025-04-16) names it as the frame kernel for `moon_pa_de440_200625.bpc`, and `fk/satellites` holds it while the earlier `moon_de440_220930.tf` has moved to `a_old_versions`. NAIF's PCK readme (revised 2026-10-03) still names 220930 at its former location, which now returns 404. The two kernels define `MOON_PA_DE440` and `MOON_ME_DE440_ME421` identically (only the ID codes of the generic `MOON_PA`/`MOON_ME` aliases differ), and the J2000 → `MOON_ME_DE440_ME421` rotation is bitwise the same with either. 220930 stays a fallback, fetched from `a_old_versions`. `moon_080317.tf` (DE421 frames, for V-02e) is kept; it also defines the generic `MOON_ME`/`MOON_PA` aliases and, loaded last, points them at the DE421 frames (up to 0.86 m from `MOON_ME_DE440_ME421` at the surface). LUNA-OPS therefore names every lunar frame explicitly (`MOON_ME_DE440_ME421`, `MOON_PA_DE440`, and `MOON_ME_DE421` for V-02e), never by an alias, and `tests/test_phase4_frames.py` checks both the names and that DE440 results are bitwise unchanged with or without the DE421 kernels. `lock.json` records which kernel was installed and from where; the load check requires `MOON_ME_DE440_ME421` to be defined. Evidence: `docs/validation_evidence/ib2_2026-11-09/`.

**Production and demo kernels are separate.** `python start.py --demo` and `acquire sandbox-kernels` use `data/kernels_demo`; `python start.py`, `acquire kernels` and the validation report use `data/kernels`. An install from an earlier version that kept the demo set in `data/kernels` is moved to `data/kernels_demo` automatically (nothing is deleted). The engine refuses to load a demo set as production or the reverse. `acquire status` lists both sets.

**If Python cannot reach naif.jpl.nasa.gov** (for example behind a proxy), download the files yourself and install them through the same checks:

```powershell
# Windows PowerShell, from the luna-ops folder: downloads, checks published sizes and MD5s, then installs
powershell -ExecutionPolicy Bypass -File scripts\get_production_kernels.ps1 -Python backend\.venv\Scripts\python.exe
```

or download the eight files from the URLs in the manifest into any folder and run `python -m lunaops.acquire kernels --from-dir <folder>`.

Then run V-02e (DE421/DE440 frame residual, rule: at most 1 m) and the report:

```bash
python -m pytest -s -k V02e tests/test_engine.py
python -m validation.run_validation
```

Production kernels alone do not make results Validated: V-04, V-05, V-09 to V-13, U-04 and U-06 must also pass (see Validation).

### 3. Terrain (core set, about 10.9 GB of height files)

Download from the PGDA product pages, then register each file. All of these are GeoTIFFs in south polar stereographic X/Y metres, MOON_ME frame of DE421, heights in metres above the 1,737.4 km sphere. Registration reads the embedded CRS, size, units and nodata, checks the projection to better than 1 mm, refuses values that look like km or undeclared nodata, and computes SHA-256. Several files may share a resolution: the 5 m mosaic and any number of PGDA 78 site DEMs can be registered together, and finer products are always sampled first.

File names, sizes and links below were read from the product pages on 2026-11-07; PGDA may change them.

| Product id | Product page | Height file | Error map (optional, `--error-map`) |
| --- | --- | --- | --- |
| `pgda81_mosaic` | https://pgda.gsfc.nasa.gov/products/81 | `ldem_87s_5mpp.tif` (87-90 S, 3.3 GB) | none published |
| `pgda78_site` (repeat per site) | https://pgda.gsfc.nasa.gov/products/78 | `<Site>_final_adj_5mpp_surf.tif` | `<Site>_final_adj_5mpp_toterr.tif` (total Z uncertainty, m) |
| `pgda90_10m` | https://pgda.gsfc.nasa.gov/products/90 | `LDEM_83S_10MPP_ADJ.TIF` (4.8 GB) | `LDEM_83S_10MPP_ADJ_ERR.TIF` (7.5 GB) |
| `pgda90_20m` | https://pgda.gsfc.nasa.gov/products/90 | `LDEM_80S_20MPP_ADJ.TIF` (2.6 GB) | `LDEM_80S_20MPP_ADJ_ERR.TIF` (3.7 GB) |
| `pgda90_80m` | https://pgda.gsfc.nasa.gov/products/90 | `LDEM_80S_80MPP_ADJ.tiff` (80-90 S, 189 MB) | `LDEM_80S_80MPP_ADJ_ERR.tiff` (255 MB) |
| `pgda90_240m` | https://pgda.gsfc.nasa.gov/products/90 | `LDEM_60S_240MPP_ADJ.TIF` (210 MB) | `LDEM_60S_240MPP_ADJ_ERR.TIF` (255 MB) |

PGDA 78 lists 27 regions (Site01, Site04, Site06, Site07, Site11, Site20, Site20v2, Site23, Site42, Haworth, Shoemaker, DM1, DM2, SL2, SL3, NPA to NPD, LM1 to LM8); files are under `https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/<Site>/`. Product 90 files are under `https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/`. Do not register the `_EFFRES`, `_HILL`, `LDEC`, `LDSM` or clone files as heights or error maps.

```bash
python -m lunaops.acquire register-dem --product pgda90_80m --file /path/to/LDEM_80S_80MPP_ADJ.tiff --error-map /path/to/LDEM_80S_80MPP_ADJ_ERR.tiff
python -m lunaops.acquire register-dem --product pgda90_20m --file /path/to/LDEM_80S_20MPP_ADJ.TIF --error-map /path/to/LDEM_80S_20MPP_ADJ_ERR.TIF
python -m lunaops.acquire register-dem --product pgda78_site --file /path/to/Site01_final_adj_5mpp_surf.tif --error-map /path/to/Site01_final_adj_5mpp_toterr.tif
python -m lunaops.acquire register-dem --product pgda90_10m --file ... --replace     # swap a single-file product
python -m lunaops.acquire unregister-dem --file <file name>
python -m lunaops.acquire status
python -m lunaops.acquire verify          # re-hash every registered DEM and error map (slow on large files)
```

Error maps are optional; when registered they give per-bin horizon uncertainty (see "Horizon uncertainty" under Remaining limitations for the model and its assumptions). An error map belongs to exactly one DEM: it must share the DEM's projection, pixel size and pixel grid, and it is recorded with the DEM's SHA-256. Each horizon bin reads only the error map of the product that supplied its blocking terrain sample. Replacing or re-registering a DEM drops an error map that was registered for other bytes.

If a registered file is later moved, deleted or changed in size, analyses that would use it are refused with the reason; LUNA-OPS never falls back to another product silently. Restore the file or unregister it.

### 4. Curated sites (optional)

```bash
python -m lunaops.acquire register-catalog --usgs /path/to/usgs_artemis3_grids.zip      # sciencebase.gov item 671a6fa8d34efed5620f89f8
python -m lunaops.acquire register-catalog --pgda /path/to/Site01_ROIs.tgz              # repeat for each site's ROI archive
```

The USGS release (McClernan 2024, "Down Selected Artemis III Candidate Landing Site Navigational Grids", doi:10.5066/P1MEQ6UK) contains Lunar Grid Reference System navigation grids in Artemis Condensed Coordinate format at 1 km, 100 m and 10 m for nine down-selected Artemis III candidate regions, projected in the USGS LTM or LPS projections; the regions were sourced from LROC QuickMap. It is a set of grids, not a set of region outlines: every shapefile becomes its own catalogue entry, and its extent is that grid's bounding box (labelled "not an official NASA boundary"). PGDA 78 publishes ROI shapefiles as one `<Site>_ROIs.tgz` per site (not every site has one); `.tgz`, `.tar.gz`, `.tar`, `.zip` and folders are accepted. Every catalogue point is labelled as the derived centre of a bounding box, not a published landing point. Catalogue IDs include the archive name (for example `pgda_site:Site01_ROIs/<shapefile>`), so identical shapefile names in different archives do not collide.

### 5. Run

```bash
cd ..                      # back to luna-ops
python start.py            # or: cd backend && uvicorn lunaops.api.main:app --port 8000
```

Open the printed address. API documentation is at `/docs` (its page loads assets from a public CDN, so it needs internet). For interface development: `cd frontend && npm ci && npm run dev` (proxies `/api` to port 8000).

The API accepts browser requests only from local origins (`localhost`, `127.0.0.1`, `[::1]`, any port), so other websites cannot use a running LUNA-OPS server through your browser, and the interface route serves only files inside `frontend/dist`.

## Continuous integration

`.github/workflows/ci.yml` runs on every push and pull request:

- **backend**: installs `backend/requirements.txt` on Python 3.12, fetches the sandbox test kernels (cached; only this job saves the cache), runs `python -m pytest` and checks that `data/dem/registry.json` is unchanged. Tests that need the real PGDA files or the production NAIF kernels are skipped there, and every result stays Pending validation;
- **frontend**: `npm ci && npm run build` on Node 22 (TypeScript check and Vite build);
- **demo-smoke**: restores (never saves) the kernel cache, then `python scripts/smoke_demo.py` starts `start.py --demo` with the built interface and checks the interface, coverage, tiles, a one-day analysis (labelled synthetic), the CORS policy and the frontend-route containment over HTTP.

Run the same checks locally from `backend/` with `python -m pytest`, and from the repository root with `python scripts/smoke_demo.py`. The actions are on their Node 24 majors (checkout v5, setup-python v6, setup-node v5, cache v5, upload-artifact v6, download-artifact v7).

**Speed.** A 30-day analysis of the synthetic golden site takes about 9 s on the CI-class machine used for development (15 s before Phase 3 item 8), dominated by the adaptive event detector's exact Earth-limb geometry and SPICE calls. To find hotspots on your own terrain, run `python ../scripts/profile_analysis.py` from `backend/` (cProfile of one analysis; `--lat/--lon/--start/--days`).

## Validation

```bash
python -m validation.run_validation                                   # pytest suite -> validation/report.json
python -m validation.horizons_compare --out h.json                    # V-04 (direction) and V-05 (event timing), needs ssd.jpl.nasa.gov
python -m validation.v13_eclipse --reference validation/reference/gsfc_lunar_eclipses_2025_2026.json --out v13.json   # V-13, GSFC contacts
python -m validation.v13_eclipse --p1 ... --u1 ... --u4 ... --p4 ... --out v13.json   # one eclipse, UTC contacts from the NASA catalogue
python -m validation.v11_psr --lpsr LPSR_80S_20MPP_ADJ.TIF --out v11.json
python -m validation.v14_month --out v14.json                         # full V-14: one synodic month, 3 sites, 1 s brute force (slow; shorter runs report "not run")
python -m validation.run_validation --merge h.json --merge v13.json --merge v11.json --merge v14.json
```

### How labels are decided

A quantity is labelled **Validated** only when all of these hold; otherwise it is **Pending validation** and the reasons are shown in the interface:

- the report's code fingerprint (SHA-256 of every engine source file and manifest) equals the running code's;
- the report's test-suite fingerprint (SHA-256 of `backend/tests` and `backend/validation`) equals the suite on disk, so editing a test or a pass criterion invalidates the report until it is run again;
- the whole pytest suite passed (exit code 0), including the label-integrity, merge-guard and terrain-registry tests that have no blueprint ID;
- the report was produced with the production NAIF kernels, and its kernel checksums equal the loaded kernels';
- every test required for that quantity passed, including the frame-alignment tests V-02a to V-02e (C07), and the accessibility audit U-04 and performance benchmarks U-06 passed;
- for terrain-dependent quantities (horizon, disk visibility, events, power indicator), every non-synthetic terrain product the result used, with its error map, is listed in the report's `terrain_products` (recorded by `run_validation`), so a report never validates terrain it did not cover.

The tests each quantity needs (kept in step with `engine/provenance.py` by `tests/test_phase3_labels.py`):

<!-- validated-requirements:start -->
- `sun_earth_azel`: V-01, V-02a, V-02b, V-02c, V-02d, V-02e, V-03, V-04
- `horizon`: V-02a, V-02b, V-02c, V-02d, V-02e, V-06, V-07, V-11, V-12
- `disk_visibility`: V-02a, V-02b, V-02c, V-02d, V-02e, V-06, V-07, V-08, V-09, V-10, V-11, V-12, V-13
- `events`: V-02a, V-02b, V-02c, V-02d, V-02e, V-05, V-06, V-07, V-08, V-09, V-10, V-11, V-12, V-13, V-14
- `power_indicator`: V-02a, V-02b, V-02c, V-02d, V-02e, V-06, V-07, V-08, V-08b, V-09, V-11, V-13
- every quantity: U-04, U-06
<!-- validated-requirements:end -->

External result files carry the same metadata plus the name of the script that produced them. `run_validation --merge` refuses a file produced with different code, tests or kernels, refuses test IDs the producing script does not own (for example `v14_month` may report only V-14) and unknown status words, and combines statuses so that a failure on either side wins: an external pass can never overturn a failed automated test. Result IDs include the code fingerprint and the validation-report digest, so edited code or a new report can never be served a stale cached result.

Results computed on synthetic terrain are labelled "Synthetic test terrain - not a lunar result" from the terrain that result actually used.

### Phase 4 production results (production kernels)

- **Phase 4 status (2026-11-12): COMPLETE WITH APPROVED DEFERRALS.**
  - **Closure report:** `docs/validation_evidence/phase4_final_merge_2026-11-12/`.
  - **Basis:** exit criteria derived from the project's Phase 4 records, because no written exit criteria exist in the repository and the Phase 1.1 blueprint is not present. If the blueprint makes V-09/V-10 or licensing clearance non-deferrable, the verdict does not hold.
  - **Decisions** (`docs/validation_evidence/phase4_remaining_decisions_2026-11-11/DECISIONS_RECORDED.md`):
    - **D1:** V-05 criteria accepted.
    - **D2:** V-09/V-10 **deferred**; no criteria approved.
    - **D3:** U-06 accepted, scoped.
    - **D4:** U-04 accepted, scoped; the current-build re-audit passed.
    - **D5:** IB-5 **deferred** with distribution restrictions.
    - **D6:** report regenerated.
    - **D7:** A15 undefined.
  - **Labels:** the closure does not validate every product.
    - `sun_earth_azel` is **Validated**.
    - `horizon` is Validated on the status page, but Pending in results that carry horizon uncertainty (uncalibrated L_corr).
    - `disk_visibility`, `events` and `power_indicator` stay **Pending validation** (V-09/V-10 deferred).
  - **Register and evidence paths:** `docs/validation_evidence/phase4_closure_2026-11-11/`.
- **V-04 and V-05 against JPL Horizons:** V-04 **PASS**; V-05 **PASS** against the approved Phase 1.1 criteria (D1, 2026-11-11), passed in the official report regenerated 2026-11-12 (`2279606c…d077d376`). First run 2026-11-09 (`docs/validation_evidence/horizons_v04_v05_2026-11-09/`, now stale); refreshed 2026-11-11 with the current build (`docs/validation_evidence/refresh_v04_v05_v13_v14_2026-11-11/`) with the same results.
  - **Setup:** Sun and Earth seen from six sites (south-polar A and B, north-polar, nearside equatorial, limb, farside), hourly over 30 days from 2026-11-14. Horizons used DE441, its MEAN_ME frame, a 1737.4 km sphere and airless apparent positions with TT time tags.
  - **V-04** (direction, tolerance 0.01°): the largest difference over 7,931 epochs is 5.2×10⁻⁷° in both azimuth (×cos El) and elevation. The Sun agrees to about 3×10⁻⁸°.
  - **V-05** (event timing, its own measurement): 18 Sun and Earth centre crossings of a flat 0° horizon from the engine's event detector, against crossings found in Horizons' own elevations at 1-second resolution. 0 missed, 0 spurious, largest difference 0.49995 s, which is the detector's 0.5 s bisection limit.
  - **V-05 criteria (approved 2026-11-11, Phase 1.1 blueprint):** within 120 s of the Horizons rise/set reference, and within 10 s of the time interpolated from the one-minute Horizons table.
    - **Measured:** 18/18 events matched, maximum 0.49995 s and 0.49956 s respectively.
    - **Accepted substitute:** the 1-s Horizons centre-crossing comparison stands in for Horizons' own rise/set (RTS) output, which was not queried.
    - **Limitation:** Horizons RTS appears to use the solar limb while V-05 measured centre crossings; that difference remains.
    - **Records:** `docs/validation_evidence/d1_v05_decision_2026-11-11/ACCEPTANCE.md`; the separate V-05 report is in `refresh_v04_v05_v13_v14_2026-11-11/v05_riseset/`.
    - **Script check:** the script's internal 1.0 s check (`V05_TOL_S`) is unchanged and stricter than the approved criteria.
- **V-13 against the NASA GSFC lunar eclipse catalogue:** **PASS.** First run 2026-11-09 (`docs/validation_evidence/v13_gsfc_2026-11-09/`, now stale); refreshed 2026-11-11 with the current build (identical margins; GSFC sources re-fetched and byte-identical): `docs/validation_evidence/refresh_v04_v05_v13_v14_2026-11-11/v13_eclipse/`.
  - **Coverage:** 4 eclipses (2025 Mar 14, 2025 Sep 07 and 2026 Mar 03, all total; 2026 Aug 28, partial) × 5 nearside sites: 20 of 20 pass.
  - **Criterion (Section 10.1, unchanged):** the site's partial occultation of the Sun by Earth lies inside GSFC's [P1, P4] and its total occultation inside [U1, U4]. The smallest margin is 483 s.
  - **Reference:** GSFC's contacts were transcribed from its per-eclipse figures and checked against the figures' durations and GSFC's text pages. They are converted to TD with GSFC's own ΔT (74.5–75.4 s).
  - **Limits:** GSFC enlarges Earth's shadow for the atmosphere (Danjon) and LUNA-OPS does not, so the margins are not a timing comparison. V-13 checks containment, not timing accuracy.
- **V-14 (full month):** **PASS**, refreshed 2026-11-11 with the current build (identical counts and offsets): `docs/validation_evidence/refresh_v04_v05_v13_v14_2026-11-11/v14_month/`.
- **V-11 and V-12:** **PASS** on registered terrain (2026-11-10), re-merged in the official report of 2026-11-11 (see Remaining limitations).
- **U-04 (WCAG 2.2 AA):**
  - **Standalone audit:** completed 2026-11-11 with a **scoped PASS**. 55 A/AA criteria were assessed and 24 defects fixed, in one browser engine and without an assistive-technology user session (`docs/validation_evidence/u04_2026-11-11/`).
  - **Decision D4 (2026-11-11):** accepted, scoped. Re-run on the current build: 0 automated problems in 6 views; 16/16 functional tests unchanged. Limits: Chrome/Chromium only; no real screen-reader user session. Not a claim of unrestricted WCAG 2.2 AA conformance.
  - **Official report:** **passed** (scoped), merged 2026-11-12 (`2279606c…d077d376`). Re-registered for the final Phase 5 frontend on 2026-11-12 (approved; `5135efe8…`; see Phase 5 interface).
- **U-06 (performance):**
  - **Standalone audit:** the frontend audit was completed on 2026-11-11 (`docs/validation_evidence/u06_2026-11-11/`).
  - **Decision D3 (2026-11-11):** accepted against scoped project criteria. Every run met LCP ≤ 2.5 s (worst 1,044 ms), CLS ≤ 0.1 (0), browser-measured interaction p95 ≤ 200 ms (32/40 ms) and no progressive memory leak. TBT was recorded for information only.
    - **Scope:** the tested laptop and its three profiles.
    - **Exclusion:** two slow backend map tiles were blocked during measurement.
    - **Not claimed:** field Core Web Vitals compliance.
  - **Official report:** **passed** (scoped), merged 2026-11-12 (`2279606c…d077d376`). Re-registered for the final Phase 5 build on 2026-11-12 (approved; `5135efe8…`; see Phase 5 interface).
- **Official report (`backend/validation/report.json`, regenerated 2026-11-11T18:57:17Z UTC = 2026-11-12 local, SHA-256 `2279606ceab9354b8616ba9216e12e89e399f34cfc3cbfcbd7502d12d077d376`; superseded on 2026-11-12T06:27:21Z by `5135efe8…`, see Phase 5 interface):**
  - **Run:** `run_validation` merged eight result files:
    - V-09/V-10, V-11 and V-12;
    - the full Horizons file (V-04 and V-05);
    - V-13 and the V-14 month run;
    - U-04 and U-06.
  - **pytest:** **438 passed, 2 skipped** (sandbox-only kernel-setup tests), **0 failed**, exit code 0; no merge rejected.
  - **Report entries:** **420 passed, 2 not run, 2 skipped.**
  - **Passed:** 24 of the 26 blueprint test IDs, including V-04, V-05, V-11, V-12, V-13, V-14, U-04 and U-06.
  - **Not run:** V-09 and V-10 (deferred, D2).
  - **Build:** code fingerprint `5bf9753f…`, suite fingerprint `1632af16…`, production kernels, terrain acceptance digest `e48eb8ed…`, algorithm 1.5.0.
  - **Evidence:** `docs/validation_evidence/phase4_final_merge_2026-11-12/`; 32 of 32 verification checks passed. The earlier report `5e6c76d7…` (2026-11-11, `docs/validation_evidence/phase4_merge_2026-11-11/`) is superseded.
- **V-02e and the Earth-pole checks:** see `docs/AUDIT_2026-11.md`, Phase 4.

### Phase 5 interface (2026-11-12)

- **Phase 5 status (2026-11-12): COMPLETE WITH APPROVED DEFERRALS** (`docs/validation_evidence/phase5_final_2026-11-12/COMPLETION_REPORT.md`). Frontend only. No backend code, algorithm (1.5.0) or fingerprint changed. The only report change is the approved re-registration of U-04 and U-06 for the final frontend (below).
- **Features** (Mission, Site and Compare tabs):
  - **3D Moon globe:** NASA SVS CGI Moon Kit imagery, illustrative only, with no elevation taken from it. Pick a site on the globe or the south polar map, or type coordinates; every view shares the same site and coordinate conversion.
  - **South Pole Explorer:** the selected site, its registered-terrain coverage from the API and a **local terrain preview** from the registered LOLA DEMs. Cells without data are left empty.
  - **Scientific visualisations:** a key to the data classes, site and terrain context, a Sun and Earth visible-disc chart (gaps never filled), timeline flags with an intervals table, the panorama ±1σ readout (L_corr assumption) and comparison bars with validation-label counts.
  - **Mission dashboard:** selected site and coverage, system status, the current analysis with its labels and uncertainty, deep links into the result, candidate sites, the analyses of this session and the comparison status. It shows no score, probability or recommendation.
  - **Context is kept:** leaving a result for the explorer keeps it, at the same time step, until you return. The list of analyses is kept in this browser tab's session storage and restored only for the same backend build and validation report, so it never shows stale figures or labels.
- **U-04 re-evaluated on the final frontend:**
  - **Result:** 0 automated problems in 10 views: the 6 release views plus the globe, local terrain, mission dashboard and empty dashboard. Release functional tests are unchanged apart from documented additions; the Phase 5 keyboard and focus tests pass.
  - **Scope (as D4):** Chrome 157 headless only; no real screen-reader user session. Not a claim of unrestricted WCAG 2.2 AA conformance.
- **U-06 re-measured on the final build:**
  - **Result:** the D3 criteria are met in every profile, in two run sets: worst LCP 540 / 1,728 / 1,332 ms (≤ 2.5 s), CLS 0, interaction p95 ≤ 88 ms, no leak in result-view, globe or terrain remounts.
  - **Slower than the 2026-11-11 build:** about 20–60 % at 4× CPU (cold median FCP 748 vs 480 ms in the repeat set). The first 4× CPU set ran under CPU contention and is kept. The cause is not isolated.
  - **Scope:** lab measurement on the D3 laptop and profiles, with the two slow tiles excluded; not a field Core Web Vitals claim.
- **Official report re-merged (approved 2026-11-12):** the refreshed U-04 and U-06 result files (`frontend_u04_phase5.json`, `frontend_u06_phase5.json`) were merged with the six Phase 4 science files through `run_validation` (pytest 438 passed, 2 skipped, 0 failed; 0 rejected merges).
  - **New report:** `backend/validation/report.json` SHA-256 `5135efe88e5feb0fd36e0230ecba9f2d2b99322a70e1e69e822e13def69df53f`, `run_utc` 2026-11-12T06:27:21Z. It supersedes `2279606c…`.
  - **What changed:** U-04 and U-06 stay **passed** and now describe the final Phase 5 frontend. Every other entry, status, count (420 passed, 2 not run, 2 skipped), fingerprint and label is identical (37/37 checks).
  - **Evidence:** `docs/validation_evidence/phase5_report_merge_2026-11-12/`.
- **Tests on the final build:** type check; `npm test`; production build; mission 42/42, visualisation 25/25, explorer 27/27, globe 31/31, no-WebGL 2/2 and end-to-end 16/16 browser checks; previous evidence checksums verified.
- **Licensing (IB-5, still deferred under D5):** the browser build now ships `THIRD_PARTY_NOTICES.txt` (the licence files of the 26 shipped packages) and `OFL.txt`, and `data/reference_validation/` is git-ignored. Other items are unresolved; see Remaining limitations.

### Results in this build (sandbox: test kernels and synthetic terrain)

Measured on 2026-11-07 with Python 3.12.3 and the pinned packages, after the kernel-setup changes. The full evidence is in `docs/validation_evidence/`.

**Automated suite:** 58 passed, 1 skipped (V-02e needs the production DE440 and DE421 lunar kernels, which could not be downloaded in the build sandbox), pytest exit code 0, 139.2 s. The same suite on the folder layout of earlier versions (demo set still in `data/kernels`): 58 passed, 1 skipped, 131.7 s.

**Report:** `run_validation` with the month-long V-14 merged (no merge rejected): of the 26 blueprint test IDs, 16 passed, 1 skipped (V-02e) and 9 not run (V-04, V-05, V-09 to V-13, U-04, U-06: they need production kernels, network access, downloaded reference products or the frontend audits); the 20 tests without a blueprint ID (integrity, registry, merge guard, kernel setup) passed. Because the sandbox used test kernels, every result is correctly labelled Pending validation.

- **V-03:** az/el agree with SPICE AZLCPO, including at both exact poles. At the exact south pole AZLCPO returns the LUNA-OPS convention (VT-10, CSPICE N0067).
- **V-06 / V-07:** the synthetic-crater horizon agrees with an independent analytic reference within the 0.01° threshold; the exact stopping rule changes no bin compared with no stopping; doubling the azimuth bins changes the horizon less than 0.01° at the 95th percentile; incomplete bins are flagged at coverage edges.
- **V-08:** against an independent dense spherical integration (horizon nodes included), the closed-form disk solution agrees to 5.7×10⁻⁹ in visible fraction and 4.2×10⁻¹⁰° in edge clearance for the Sun and Earth disks at 1° to 59.9° elevation. (Phase 3 found that on rare steep or notched horizons the visible fraction of a partly hidden disk could be off by up to 1×10⁻⁴, an ill-conditioned asin at the disk's azimuth extremes; fixed in algorithm 1.4.0, it now agrees with an independent exact-limb kernel to better than 10⁻⁹ on 3000 random cases.) The clearance step at the 60° switch to the sampled cap is 7.1×10⁻⁴°. With terrain clear, the combined Sun-Earth clearance equals γ + ρ_sun - ρ_earth to 10⁻⁹°.
- **V-14 (pytest form):**
  - synthetic one-node-notch windows of 1.7, 4.5 and 58.9 s were found, every event within 0.5 s; a 0.5 s window was not found (windows below 2 s are not required);
  - three sites × 1 day of 1 s brute force (Sun and Earth; centre, top and bottom edges), direction-aware and including windows open at either end of the day: all 102 required window edges found (37, 38, 27), worst offset 0.500 s, no unconfirmed detector events, zero runtime estimate failures;
  - curvature estimates covered the 1-minute-grid second derivatives;
  - an eclipse located by scanning the ephemeris (3 March 2026) had all six Earth-occultation boundaries within 1.5 s of brute force.
- **V-14 (full form, `validation/v14_month.py`), production kernels, algorithm 1.5.0 (Phase 4 A14, 2026-11-10; `docs/validation_evidence/v14_month_a14_2026-11-10/`):** passed. One synodic month (29.530589 days from 2026-11-14) at three sites, 1 s brute force continuous across the daily chunks: 955 required window edges (661, 183 and 111 per site), 0 missed, 0 beyond 1.0 s, 0 spurious; worst offset 0.500 s; 406 s. Refreshed 2026-11-11 with the current build with identical counts and offsets (`docs/validation_evidence/refresh_v04_v05_v13_v14_2026-11-11/v14_month/`). The 2026-11-10 run was merged into the production report with V-13 and V-04/V-05 re-run on the same code. The detector logged 33 runtime estimate failures (11 per site), all on the Sun-Earth contact function `ecl_contact` between 27 and 29 November, at most 0.68% over the predicted change; the step was halved each time and no event was affected.
- **V-14 (full form, earlier sandbox run, 2026-11-07, superseded):** one synodic month (29.530589 days from 2026-11-14) at three sites, 1 s brute force continuous across the daily chunks: 955 required window edges (661, 183 and 111 per site), 0 missed, 0 beyond 1.0 s, 0 spurious events; worst offset 0.5 s; 641 s run time. Merged into the report through the code, test-suite and kernel guard. The detector logged 11 runtime estimate failures per site, all for the Earth-Sun contact function at one epoch (2026-11-26 22:53:45 UTC), where the observed change equals the predicted bound to four digits and the step was halved; the original code logs the same 11.
- **U-01, U-02, U-03 (4 sites × 3 windows, identical summaries, labels and result IDs), U-05, U-07** pass.
- **Kernel setup** (`tests/test_kernel_setup.py`): separate production/demo folders, refusal and migration of a demo lock in the production folder, the staged install pipeline (published-checksum checks, fallback, SPICE test load, commit, previous set kept), unchanged installed set after a failed install, `verify-kernels` catching a modified file, the pinned manifest, and checksum-list parsing: all pass.
- **Audit regression tests** (`tests/test_audit_fixes.py`): refusal of missing or changed terrain files, terrain digest following the synthetic switch, rejection of undeclared nodata, error-map acceptance and grid checks, sigma taken from the sampled product's own error map, `.tgz` ROI import with unique IDs and unsafe-archive refusal, merge-guard ownership and failure dominance, and the V-14 crossing helpers: all pass.

Figures published with earlier builds (for example "423 reference windows" for the month-long V-14) came from a checker that dropped every window crossing a daily boundary and ignored event direction; they are superseded by the figures above.

## Remaining limitations

- **Production validation status.** With the production kernels and registered multi-resolution terrain (Phase 4), V-02e, V-04, V-11, V-12, V-13 and the month-long V-14 have passed. V-04, V-13 and V-14 were refreshed on 2026-11-11. V-05 meets the Phase 1.1 criteria approved on 2026-11-11 (D1, existing evidence accepted). All of these are passed in the official report regenerated 2026-11-12 (`2279606c…d077d376`). V-09 and V-10 were evaluated on registered multi-resolution terrain across 200 stratified points over 18.6 years (0 inconclusive), with criteria maintained as provisional and unapproved (`status: not run`) per scientific rules. U-04 and U-06 were accepted on 2026-11-11 (D4, D3; scoped) and are passed in the official report. V-09 and V-10 are formally deferred (D2) and remain "not run". So `disk_visibility`, `events` and `power_indicator` stay "Pending validation", and `horizon` stays Pending in results that carry horizon uncertainty (L_corr).
- **Lunar frame kernel (IB-2) resolved** (2026-11-09; see section 2, Pinned NAIF kernels). Four of the eight pinned kernels have no NAIF-published checksum and are trusted on first download (their SHA-256 is then pinned).
- **Real NASA PGDA terrain and reference datasets ingested and verified.** NASA PGDA 78 (Site01 5m), PGDA 90 (20m, 80m, 240m) DEMs and matching error maps have been ingested and verified via SHA-256 in `data/dem/`. External validation reference datasets for V-09/V-10 (LOLA AVGVISIB Sun & Earth), V-11 (PGDA 90 PSR), and V-12 (LROC WAC TWI & PCT) have been ingested and verified via SHA-256 in `data/reference_validation/`.
- **V-12 (A12, 2026-11-10): passed on registered terrain.**
  - **Reference:** the LROC WAC south-pole illumination maps, one observed lunar year (2010-02-15 to 2011-02-05), 100 m, 88–90°S. TWI is primary and PCT is a sensitivity comparison.
  - **Method:** LUNA-OPS Sun visibility at 0 m under the whole-disc and any-part rules brackets the undocumented WAC threshold.
  - **Criteria:** C1 gates (TWI ≤ 1 % wherever LUNA-OPS predicts permanent shadow). C2 (bracket containment, with 1.31 / 3.0 pp slack) and C3 (benchmark against LOLA AVGVISIB) are reported.
  - **Image offset:** the image starts at byte 9712 (attached PDS3 header).
  - **Final production run:** 200 of 200 samples scored (0 inconclusive). C1 gating passed: all 26 predicted permanent-shadow samples exhibit WAC TWI ≤ 0.022% (far below the 1.0% limit). Merged into production validation report.
  - **Evidence:** `docs/validation_evidence/v12_final_2026-11-10/`.
- **V-09 and V-10 (A10, 2026-11-10): measured, provisional criteria.**
  - **VT-11 is resolved from the PDS3 labels.** AVGVISIB is the fraction of hourly timesteps over 18.6 years in which any part of the disc is visible, DN × 0.00004. The `_EARTH` product is the same for Earth's disc, matching PGDA 69's "any" rule.
  - **Method.** `validation/v09_v10_avgvisib.py` compares deterministic stratified points (200 per map, 85–90°S) with a vectorised hourly method.
  - **Provisional criteria preserved.** The RMSE ≤ 5 pp / |bias| ≤ 2 pp criteria are provisional and unapproved, so the result is preserved with status `not run` along with its full measurement metrics per scientific guidelines.
  - **Formally deferred (D2, 2026-11-11).** No criteria were approved. Results: V-09 RMSE 14.09 pp, bias −7.19 pp; V-10 RMSE 3.13 pp, bias −0.74 pp. The AVGVISIB observer height is undocumented (0 m assumed) and strongly affects the bright V-09 points (`docs/validation_evidence/phase4_remaining_decisions_2026-11-11/DECISIONS_RECORDED.md`).
  - **Production run on registered terrain:** 200 of 200 points scored over 18.6 years (0 inconclusive). Merged into production validation report.
  - **Evidence:** `docs/validation_evidence/v09_v10_final_2026-11-10/`.
- **V-11 (A11, 2026-11-10): passed on registered terrain.**
  - **Reference:** PGDA 90 permanently-shadowed regions (`LPSR_80S_20MPP_ADJ.TIF`).
  - **Production run on registered terrain:** 200 of 200 formal points scored dark with complete horizons (100.0%, 0 inconclusive, 0 light). Merged into production validation report.
  - **Evidence:** `docs/validation_evidence/v11_final_2026-11-10/`.
- **U-04 (WCAG 2.2 AA audit): accepted, scoped (D4, 2026-11-11; current-build re-audit passed); passed in the official report (2026-11-12).**
  - **Limits:** no session with an assistive-technology user (screen-reader behaviour was inferred from Chrome's accessibility tree); Chromium only; zoom emulated through the viewport; speech input not exercised.
  - **Result file:** `docs/validation_evidence/phase4_remaining_decisions_2026-11-11/frontend_u04.json`, merged 2026-11-12. Not a claim of unrestricted WCAG 2.2 AA conformance.
  - **Evidence:** `docs/validation_evidence/u04_2026-11-11/`.
- **U-06 (performance): accepted against scoped criteria (D3, 2026-11-11); passed in the official report (2026-11-12).**
  - **Scope:** criteria LCP ≤ 2.5 s, CLS ≤ 0.1, interaction p95 ≤ 200 ms and no progressive leak, on the tested laptop and profiles only.
  - **Exclusion:** two slow map tiles were excluded.
  - **Not claimed:** formal field Core Web Vitals compliance.
  - **Result file:** `frontend_u06.json`, merged 2026-11-12.
  - **Open recommendation:** the audit recommends a backend fix for slow low-zoom hillshade tiles, which has not been made.
  - **Evidence:** `docs/validation_evidence/u06_2026-11-11/`.
- **Event detection is validated empirically, not proven.** The step rule depends on curvature estimates from an hourly grid (inflated by 1.5). Runtime checks catch estimate failures that show at step ends; V-14 is the acceptance evidence. Windows shorter than the 1 s step floor are not guaranteed to be found (in this build a 0.5 s synthetic window was missed; the requirement is 2 s).
- **Horizon uncertainty (algorithm 1.3.0) rests on an uncalibrated assumption.** Sigma per horizon bin is the exact first-order propagation of the error-map values at the blocking sample (from that sample's own product) and at the site. Errors within one product are taken as correlated with a Gaussian of length L_corr = 250 m, and the error-map variance of the site product is smoothed at that same length so the modelled error field is continuous at that scale (pixel-scale texture in a total-error map would otherwise appear as metre-scale near-field errors): **L_corr = 250 m is an uncalibrated assumption (no published source); horizon uncertainty and uncertain flags depend on it.** Every result that uses sigma says so in its warnings, labels (horizon, events, power indicator stay "Pending validation"), provenance and CSV headers. Where a blocker comes from a different product than the site, a *cross-product discrepancy allowance* is added: the RMS of finer-minus-coarser heights where the two products overlap around the site. It is measured with bilinear interpolation of the coarser product between its pixel centres, over the intersection of the two products' windows (`CROSS_PRODUCT_SAMPLING`); for PGDA 78 Site01 vs PGDA 90 80 m this gives mean -0.053 m, std 1.223 m, RMS 1.224 m over 40,000 points. It is a conservative allowance (it includes the measured bias), not a calibrated random 1-sigma. (The +1.07 m / 6.33 m figures in the 2026-11 audit are a different measurement: nearest-pixel sampling on a 4-8 km annulus; see `docs/AUDIT_2026-11.md`.) With fewer than 100 overlapping samples the discrepancy is reported unknown (never zero): those bins carry no sigma and every window or gap that crosses them is flagged uncertain. Bins with sigma above 5° are beyond first-order validity (`sigma_nonlinear`) and also force "uncertain". Windows and gaps are uncertain when their clearance stays within 1 sigma (k = 1) of the horizon at the disk's limiting edge; intervals list `uncertain_reasons`.
- **Near-field horizon at 0 m observer height.** At the default surface height the horizon in many directions is the DEM's own local slope a few metres away. Bins whose blocking terrain lies within 2 site-product pixels are flagged `near_field` (horizon output, intervals, summary counts and a result warning); their values are real DEM geometry but depend on the DEM at its resolution limit. Raising the observer height (astronaut or equipment profile) removes this.
- **Horizon sampling between ray steps** (half a pixel) can miss peaks narrower than a step. Between the 0.1° azimuth nodes the horizon is interpolated linearly; since algorithm 1.4.0, `SUBBIN_RAYS` = M extra rays per bin (default 4, i.e. every 0.025°; 1 to 16, environment `LUNAOPS_SUBBIN_RAYS`) measure how far terrain between the nodes rises above that interpolation (`subbin_excess_deg` per bin; unknown where a ray ran out of terrain). It is informational: the horizon values, sigma and the uncertain flags are unchanged, and windows whose clearance never exceeds the excess under the disk are flagged `subbin_peak` (gaps never are; a missed peak can only raise the horizon). Peaks narrower than the sub-ray spacing can still be missed. An M = 4 horizon costs about 2.5x the node-only time.
- **Disk model.** Up to 60° elevation each disk is solved exactly as a spherical cap against the piecewise-linear horizon (agreement with an independent dense spherical integration: 5.7×10⁻⁹ in visible fraction, 4.2×10⁻¹⁰° in edge clearance). Above 60°, and for a disk containing the zenith, the cap is integrated on 60×96 area-weighted points plus a 96-point boundary ring; edge clearances there are sampled, and the measured step across the 60° switch is up to 7.1×10⁻⁴° (it never occurs at south polar sites inside the terrain coverage, where the Sun stays below about 32° and Earth below about 38°). Earlier builds used a tangent-plane flattening whose error, ρ²·tan(el)/2, reached 1.3×10⁻²° for the Earth disk near 60° and about 10⁻³° at polar Earth elevations.
- **Earth disk (algorithm 1.4.0; pole of date since 1.5.0).** Earth is the IERS 2010 spheroid seen as its exact projected limb ellipse; its upper and lower limbs agree with SPICE `edlimb` to 5×10⁻¹⁶ rad and its clearances and visible fraction are computed on the exact ellipse (10⁻¹² rad and 10⁻⁶ against independent dense references). Its spin axis is, since algorithm 1.5.0, the Celestial Intermediate Pole of date: IAU 2006 precession with IAU 2000B nutation, the SOFA/ERFA `pn06` + `nut00b` combination (about 1 mas, 1900-2100), computed in the engine (`engine/earth_orientation`) so the demo and production kernel sets use the same pole. It matches ERFA 2.0.1 to 3×10⁻¹¹″ over 2000-2049 and lies within 9.6″ of the IAU_EARTH model in `pck00011` (which omits nutation). Polar motion and free-core nutation (about 0.3″ and 0.2 mas) are neglected. Until 1.4.0 the axis was frozen at J2000 Z, which drifts from the real pole by about 20″ per year (539″ in 2026, 1001″ in 2049): on sloped terrain that moved Earth's upper and lower limb by up to 1.8×10⁻⁵° and limb events by up to about 2 s. Earth-centre events and the default DTE rule (`centre`) never depended on the pole. The circular-cap shortcut is taken only where its proven error bounds are below 10⁻⁶° and 5×10⁻⁶ in fraction, which at Earth's oblateness is practically never. Compared with the earlier equatorial-radius circle, polar Earth limb events move by about 2.5 to 3 minutes. Earth's atmosphere is not modelled. The detector bounds Earth limb rates with the complete edge-clearance derivative (`docs/AUDIT_2026-11.md`, Phase 3 item 1).
- **Earth in front of the Sun (algorithm 1.4.0).** The share of the Sun behind Earth is computed against Earth's exact limb ellipse (agreement with an independent reference: 1.5×10⁻¹⁰), and the spherical lens formula with numerically stable branches is used when Earth is circular. The visible solar fraction is exact (closed form) when terrain clears the Sun or Earth's overlap lies wholly above or below the terrain; only when terrain and Earth both cut the Sun is it integrated, adaptively to 10⁻⁵ with the error estimate recorded (measured agreement with an independent reference: about 10⁻¹⁰). Treating Earth as a circle of its radius toward the Sun, as first planned, would have been off by up to 2×10⁻⁴. Eclipse contact events use Earth's limb radius toward the Sun's centre, which moves them by up to about 15 s compared with the mean radius.
- **The combined terrain-and-Earth clearance** (used for the any-part sunrise/sunset events during eclipses) is computed from a sampled spherical cap while Earth overlaps the Sun. It is exact whenever terrain clears the solar limb point farthest from Earth (pure occultation); when terrain and Earth both cut the Sun it rests on the sample points, and its value can step slightly when an overlap begins.
- **Terrain file integrity is checked cheaply at run time** (existence and byte size). Full SHA-256 re-verification is `python -m lunaops.acquire verify`.
- **Terrain window loading (algorithm 1.4.0, performance only).** Each level keeps its nominal window (`DEM_WINDOW_HALF_M`, which defines coverage, distance bands and steps). By default (`LUNAOPS_WINDOW_MODE=adaptive`) windows are read straight into one shared buffer (no second copy for the horizon kernel), and the 80 m and 240 m products are first loaded only up to an initial reach (`DEM_INITIAL_REACH_M`: 100 km and 200 km; per level or product, between 0 and the nominal half-width), with the stopping bound's maximum height still taken over the whole nominal window. A ray that reaches beyond the loaded part makes that product load in full and only those rays are recomputed, so the horizon is bitwise the same as with the reference loader (`LUNAOPS_WINDOW_MODE=full`). Peak memory on the synthetic scenes is 42-57% lower. `python ../scripts/check_window_identity.py` (from `backend/`) checks the identity on your own terrain and prints time and memory for both loaders.
- **Frame alignment:** the DE421-based DEMs are used in the DE440 ME421 frame as if identical until V-02e measures the residual (decision rule in blueprint Section 7.4).
- **Licences (IB-5): inventory complete (2026-11-11), issues unresolved, formally deferred (D5, 2026-11-11, `docs/validation_evidence/phase4_remaining_decisions_2026-11-11/DECISIONS_RECORDED.md`)** (`docs/validation_evidence/ib5_2026-11-11/`).
  - **Unverified licences:** 44 of the 49 native libraries bundled in the Python wheels ship no licence text.
  - **Data terms:** the redistribution terms of most data sources (PGDA, PDS/LROC, JPL Horizons, NAIF, USGS, ShadowCam) are not confirmed.
  - **Browser build (addressed 2026-11-12):** it lacked the licence notices of 21 packages and the fonts' OFL text. It now ships `THIRD_PARTY_NOTICES.txt` and `OFL.txt` (generated by `frontend/scripts/gen-notices.mjs` from the packages' own licence files), plus `moon/ATTRIBUTION.txt` for the globe imagery.
  - **Reference rasters (addressed 2026-11-12):** `data/reference_validation/` is now git-ignored.
  - **Deferral (D5):** recorded, with interim restrictions until each item is resolved. Full licensing clearance is **not** claimed.
    - Do not redistribute a packaged Python environment.
    - Do not commit or redistribute `data/reference_validation/`.
    - Publish `frontend/dist` only with `THIRD_PARTY_NOTICES.txt`, `OFL.txt` and `moon/ATTRIBUTION.txt` (all now in the build). Regenerate the notices if the frontend dependencies change.
    - Keep the committed Horizons and GSFC copies as evidence only.
    - Do not distribute terrain, kernels or other data products with LUNA-OPS; users download them from their sources (see Full setup).
- **Limb-darkened power indicator (D01, algorithm 1.4.0).** Beside the uniform-disk indicator `P_rel` (unchanged), results carry `P_rel_LD`: the visible share of the Sun's *flux* rather than of its area, using the centre-to-limb law of Neckel & Labs (1994, Solar Physics 153, 91, Table I, p. 98) at 541.760 nm, the tabulated wavelength nearest the V band, taken exactly as printed (A0..A5 = 0.26073, 1.27428, -1.30352, 1.47085, -0.96618, 0.26384; the limb is 26% as bright as the centre). It is normalised by the full-disk flux, so `P_rel_LD` = `P_rel` whenever the Sun is fully visible or hidden; the two differ only while terrain or Earth hides part of the Sun (a sliver at the limb carries about a third of its area share). Labelled "Estimated (D01 ...)"; one wavelength stands for the panel's spectral response (an assumption). Exported as `power_rel_ld_*` and `sun_visible_flux_fraction_ld`.
- **Category D extensions** other than D01 (D02 to D10) are not implemented. D09 groundwork exists: per-bin sigma is computed when error maps are registered.
- **First analysis after install is slow:** Numba compiles its kernels once (about 2 to 3 minutes on a single-core machine; usually less). The compiled code is cached, and later analyses take seconds.
- **Test-only warning:** the test client prints a Starlette deprecation warning about `httpx`; it does not affect the application.
- **Interface strings (C10)** are externalised in one English dictionary, `frontend/src/i18n/en.ts` (2026-11-11, `docs/validation_evidence/c10_2026-11-11/`). Text supplied by the API, inline lower-casing of some dictionary text and English number formatting would still need work for a translation.

## Architecture (blueprint Section 9)

```
backend/lunaops/engine   time, frames, ephemeris, multi-product DEM pyramid, numba horizon with exact stopping,
                         exact disk visibility, adaptive events (including eclipse boundaries), power indicator,
                         provenance and labels, caches, catalogue
backend/lunaops/api      FastAPI: status, catalogue, coverage, analysis/compare jobs, results, CSV/JSON exports,
                         3D terrain grids, hillshade tiles
backend/validation       validation runner, run metadata and merge guard, external-reference scripts
frontend/src             React + TypeScript: OpenLayers polar map, D3 horizon panorama and timeline,
                         Three.js terrain, comparison matrix, technical and public modes
start.py                 one-command launcher (Windows, macOS, Linux)
```

## Event rules

The Space Apps 2026 Team Formation Guide says project work should not begin before November 14, 2026, 9:00 a.m. local time. This code was written before that date at the team's request, so treat it as a non-competition build unless your Local Lead confirms otherwise.

## Screenshots

`docs/screenshots/` shows the interface running in the build sandbox with **synthetic test terrain and test kernels**; the labels in the images say so. They are not lunar results.

## Licence and attribution

Apache-2.0 (see LICENSE). Data and software attributions are in ATTRIBUTION.md.
