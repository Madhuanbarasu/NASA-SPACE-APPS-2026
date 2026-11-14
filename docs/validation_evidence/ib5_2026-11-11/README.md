# IB-5: licence and attribution inventory (Phase 4, 2026-11-11)

**Blueprint item IB-5:** inventory third-party licences, including those bundled inside Python wheels (GDAL/PROJ in rasterio/pyproj), and record the data-source terms (ShadowCam, USGS).

**Status: inventory complete for everything verifiable locally, with unresolved items listed below.** Every dependency, vendored binary, data source and asset in this installation is inventoried.

What was verified from local files:
- the licence, copyright holder, licence-file location and source of every Python distribution and every npm package;
- the licence text shipped with every package that ships one;
- the attribution clauses found in those texts.

What remains unresolved:
- 44 of the 49 vendored native binaries ship **no** licence text, so their licences are not verified;
- the licence and redistribution terms of most data sources are not available locally.

These items are marked unresolved, not guessed.

## Method and constraints

- **Local files only.** No network access, no downloads, no package installs, no git operations. Licences were never inferred from a project's name or reputation. A licence counts as verified only when a text or declaration that ships with the component states it.
- **Python:** the project venv `backend/.venv`, Python 3.13.7 on Windows, read with its own interpreter in isolated mode (`-I`).
  - Sources: installed metadata (`importlib.metadata`: License-Expression, License, classifiers, License-File, Requires-Dist), every licence-like file in each wheel's RECORD, and the `*.libs` folders of vendored DLLs.
  - The DLLs' embedded Windows version resources (product, version, LegalCopyright) were read with the Win32 API.
  - Library versions were confirmed at runtime: `rasterio.__gdal_version__`, `spiceypy.tkvrsn`, `llvmlite.binding.llvm_version_info`, `numpy.show_config`, `PIL.features`.
- **npm:**
  - Sources: `frontend/package-lock.json` (lockfile v3) and the installed `node_modules/*/package.json` and licence files.
  - Which packages ship in the browser bundle was taken from **the production Vite/Rollup build itself**: `vite.build` with `write: false`, outDir in a scratch folder, and the per-module `renderedLength` of each output chunk. `frontend/dist` was not touched (hashes checked before and after).
  - The built `dist` was inspected for preserved licence comments and for the licence metadata inside each WOFF2 font (name table, decoded with Node's built-in brotli).
- **Data and assets:**
  - Sources: `backend/lunaops/manifests/datasets.json`, `data/dem/registry.json`, `data/kernels/lock.json`, and the product READMEs, PDS3/PDS4 labels and provenance files under `backend/validation/reference/`.
  - Also used: the product-page copies saved in earlier evidence folders, the SPICE kernel headers, and the GeoTIFF metadata tags of every registered raster.
  - The repository was searched for ShadowCam and USGS.
- **Obligations and restrictions are quoted, not interpreted.** In the CSV tables they are clauses detected verbatim in the shipped licence text (for example "Redistributions in binary form must reproduce…", "Neither the name…", OFL condition 2). A component without a licence text gets "unresolved".

## Results

### Python (backend)

| Count | Value |
| --- | --- |
| Distributions installed | 35 |
| Direct (pinned in `requirements.txt`; all 12 pins match the installed versions) | 12 |
| Transitive (dependency closure) | 22 |
| Environment tooling only (`pip`) | 1 |
| Distributions without a licence file | 0 |

**Licences declared** (from installed metadata, each with its licence file present):
- MIT (17, including `pip`)
- BSD-3-Clause (8)
- BSD-2-Clause (1)
- BSD / "BSD License" (2: numba, colorama)
- MIT-CMU (pillow)
- MPL-2.0 (certifi)
- PSF-2.0 (typing_extensions)
- Apache-2.0 (opentelemetry-api)
- Apache-2.0 OR BSD-2-Clause (packaging)
- BSD-2-Clause AND Apache-2.0 WITH LLVM-exception (llvmlite)
- BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 (numpy)

The full table is in `inventory_python.csv`.

**Bundled components that are documented inside the wheels (verified):**
- **NumPy 2.5.4:** `LICENSE.txt` lists the bundled OpenBLAS 0.3.34 (BSD-3-Clause, The OpenBLAS Project), LAPACK (BSD-3-Clause-Open-MPI, University of Tennessee et al.) and the **GCC runtime library (GPL-3.0-or-later WITH GCC-exception-3.1)** statically linked into `libscipy_openblas64_*.dll`. It also lists 16 further licence files for vendored source (libdivide, Highway, x86-simd-sort, SVML, pocketfft, lapack_lite, random generators, etc.).
- **Numba 0.68.0:** `LICENSE` has Copyright (c) 2012 Anaconda, Inc., with the two conditions of the BSD 2-clause form. `LICENSES.third-party` covers appdirs, NetworkX, jquery.graphviz.svg, CPython (including its unicode code), cloudpickle, NumPy, the CUDA Half Precision Headers, pythoncapi_compat and numba-cuda.
- **llvmlite 0.50.0:** `LICENSE` (Copyright (c) 2014 Anaconda Inc., BSD) and `LICENSE.thirdparty` (the LLVM licence: Apache License v2.0 with LLVM Exceptions). `llvmlite.dll` contains LLVM 22.1.0 (runtime-confirmed).
- **rasterio 1.5.2:**
  - `rasterio/gdal_data/LICENSE.TXT` is GDAL's own licensing file. Its sections are: GDAL/OGR General (MIT-style); port/cpl_float; hdf-eos; libcsf; degrib (NWS); minizip (Info-ZIP); intronurbs; thinplatespline; libqhull; PDF; MRF; CMake modules; FlatGeobuf (ISC) and flatbuffers (Apache-2.0).
  - It covers code **inside the GDAL source tree**. The GDAL 3.12.2 DLL's version resource says "See LICENSE.TXT".
  - `rasterio/proj_data/copyright` gives the PROJ terms (MIT-style), for PROJ 9.7.1.
- **pyproj 3.8.0:** `LICENSE` (MIT) and `LICENSE_proj` / `proj_dir/share/proj/copyright` (PROJ terms) for the bundled PROJ 9.8.1.
- **Pillow 13.0.0:** `LICENSE` (MIT-CMU) includes the licences of its 12 statically linked libraries, with versions: brotli 1.2.0, FreeType 2.14.3, HarfBuzz 14.5.0, lcms2 2.19.1, libavif 1.4.2, libjpeg-turbo 3.2.0, libpng 1.6.58, libwebp 1.6.0, OpenJPEG 2.5.4, LibTIFF 4.7.2, XZ 5.8.4, zlib-ng 2.3.3.
- **SpiceyPy 8.3.0:** `LICENSE` (MIT, Andrew Annex) covers SpiceyPy only. It doesn't mention the bundled CSPICE (runtime: `CSPICE_N0067`).

### Vendored native binaries (`inventory_native_binaries.csv`)

49 binaries were found. **5 have their licence text in the wheel:**
- GDAL and PROJ (rasterio);
- PROJ (pyproj);
- OpenBLAS (numpy);
- `llvmlite.dll` (llvmlite).

**44 are unresolved:** the wheel ships no licence text for them. Their size, SHA-256 and embedded version resource are recorded. Where a version resource exists, it gives:

| Library (wheel) | Version | Embedded copyright notice |
| --- | --- | --- |
| OpenSSL libcrypto/libssl (rasterio) | 3.6.1 | Copyright 1998-2026 The OpenSSL Authors |
| curl (rasterio / pyproj) | 8.18.0 / 8.19.0 | Copyright (C) Daniel Stenberg |
| PostgreSQL libpq (rasterio) | 16.9 | Portions Copyright (c) 1996-2023, PostgreSQL Global Development Group… |
| libxml2 (rasterio) | 2.15.1 | Copyright (C) Daniel Veillard |
| libiconv (rasterio) | 1.18 | Copyright (C) 1999-2024 |
| libjpeg-turbo (rasterio / pyproj) | 3.1.3 / 3.1.4.1 | The libjpeg-turbo Project and many others |
| LibTIFF (rasterio / pyproj) | 4.7.1 | "See LICENCE.md" (that file is **not** in either wheel) |
| SQLite (rasterio / pyproj) | 3.51.2 / 3.53.0 | points to http://sqlite.org/copyright.html |
| zlib (rasterio / pyproj) | 1.3.1 | (C) 1995-2022 Jean-loup Gailly & Mark Adler |
| Zstandard (rasterio) | 1.5.7 | Copyright (c) Meta Platforms, Inc. and affiliates |
| XZ liblzma (rasterio / pyproj) | 5.8.2 / 5.8.3 | (none) |
| libexpat (rasterio) | 2.8.5.0 | (none) |
| Microsoft C++ runtime `msvcp140.dll` (4 copies) | 14.40-14.51 | © Microsoft Corporation. All rights reserved. |

The following have no version resource at all:
- GEOS / geos_c (runtime: GEOS 3.14.1)
- libgeotiff, giflib, HDF5 / HDF5_hl, netCDF, json-c, LERC, libpng16, libsharpyuv, libwebp, minizip, OpenJPEG, PCRE2
- qhull_r, SpatiaLite, FreeXL, szip, tinyxml2
- `cspice.dll`

### npm (frontend; `inventory_npm.csv`)

| Count | Value |
| --- | --- |
| Lockfile entries | 219 (47 optional platform binaries for other OSes not installed) |
| Installed | 172 |
| **Shipped in `frontend/dist`** (per Rollup) | **26**: 25 packages with code in the JS bundle, plus the Archivo font package |
| Runtime dependencies, not in the bundle | 45 |
| Build/dev tooling only | 101 |
| Lockfile licence ≠ installed `package.json` licence | 0 |
| Version mismatches | 0 |
| Without a licence file | 4: `lerc@3.0.0` (Apache-2.0 declared; runtime dependency of `geotiff` via OpenLayers, not in the bundle), and the native build-tool binaries `@esbuild/win32-x64`, `@rollup/rollup-win32-x64-gnu`, `@rollup/rollup-win32-x64-msvc` |

**The 26 shipped packages:**
- `@fontsource-variable/archivo` (OFL-1.1);
- 15 `d3-*` modules: ISC, except `d3-ease`, which is BSD-3-Clause with Copyright 2001 Robert Penner;
- `ol` (BSD-2-Clause);
- `proj4`, `mgrs`, `wkt-parser`, `rbush`, `react`, `react-dom`, `scheduler`, `three` (MIT);
- `quickselect` (ISC).

The licence clauses found in their texts: notice retention (MIT/ISC/BSD), the no-endorsement clause (`d3-ease`), and OFL condition 2 and Reserved Font Name rules (Archivo).

An esbuild metafile probe over-counted 42 shipped packages because it keeps unused d3 modules. The Rollup figures are authoritative.

### Data sources and assets (`inventory_data_sources.csv`)

| Source | Citation or acknowledgement | Terms |
| --- | --- | --- |
| PGDA 90 DEMs, error maps, LPSR | **Verified** verbatim from the saved page excerpt: "Please cite this paper when using these products: Barker et al., 2023…" | No licence or redistribution text found locally: **unresolved** |
| PGDA 78 / 81 / 69 | Recorded 2026-11-07 (manifest, ATTRIBUTION); no local page copy | **Unresolved** |
| AVGVISIB (PDS LRO-L-LOLA-4-GDR-V1.0) | Producer **verified** from the PDS3 label: LRO LOLA Team, David E. Smith, GSFC | No terms in the label: **unresolved** |
| LROC WAC south-pole illumination maps | **Verified** from the product README: cite Speyerer & Robinson 2013, Icarus 222(1), 122-136 (**was missing from ATTRIBUTION.md**) | ATTRIBUTION's earlier "PDS products public domain…" recorded 2026-11-07, not re-verifiable offline |
| NASA GSFC eclipse catalogue (Espenak) | **Verified**: "Permission is freely granted to reproduce this data when accompanied by an acknowledgment: 'Eclipse Predictions by Fred Espenak, NASA's GSFC'" (**was missing from ATTRIBUTION.md**; the repository commits copies of the pages and figures) | Verified for the pages; the PDFs carry no extractable text, so whether the statement explicitly covers them is unresolved |
| NAIF SPICE kernels | Earlier recorded acknowledgement; `pck00011.tpc` asks that modified files carry an updated by-line, and LUNA-OPS does not modify them (SHA-256 pinned) | NAIF general statement not re-verifiable offline |
| CSPICE (in SpiceyPy) | - | No terms in the wheel: **unresolved** |
| JPL Horizons outputs (47 files committed as evidence) | - | No terms in the outputs: **unresolved** |
| USGS Artemis III grids | Recorded citation | Not registered here; release metadata not available locally: **unresolved** |
| ShadowCam | - | **Not used anywhere** (only named in README line 274); terms **unresolved**, relevant only if ShadowCam data is ever added |
| Archivo font | OFL-1.1 **verified** | - |
| `docs/screenshots` | Project renders of synthetic terrain; the OFL text exempts "any document created using the fonts" | - |

## Findings for distribution

None of these were changed: each needs an application, configuration or build change, which this task excludes.

1. **The browser bundle drops most licence notices.**
   - `frontend/dist/assets/index-*.js` keeps licence comments only for React (react, jsx-runtime, scheduler, react-dom) and three.js. The other 21 shipped JS packages' notices are absent, and `dist` contains no licence file.
   - Their licence texts require the notice in copies: "shall be included in all copies…", "must reproduce the above copyright notice…" and "appear in all copies".
   - Serving or distributing `dist` therefore needs a third-party notices file, for example generated at build time.
2. **The fonts carry a copyright notice and a URL, but not the OFL text.** OFL condition 2 requires "the above copyright notice and this license" in each copy, as a file, a header or "machine-readable metadata fields". Shipping `OFL.txt` with `dist` would settle it.
3. **`data/reference_validation/` (256 MB) is not git-ignored.**
   - It holds the PGDA LPSR and the PDS AVGVISIB and LROC rasters, whose redistribution terms are unresolved.
   - A routine `git add` would commit them, and `LPSR_80S_20MPP_ADJ.TIF` (154 MB) would also exceed GitHub's 100 MB file limit.
   - Recommendation: add `data/reference_validation/*` to `.gitignore`, matching `data/dem/*`.
4. **Python wheels are not redistributed by this repository** (it ships `requirements.txt`). The 44 unresolved native-library licences matter only to anyone redistributing the environment, for example as a container image or installer.
5. **The interface's own attribution table (`frontend/src/i18n/en.ts`, `data.attribution`) predates IB-5.** It lacks the LROC citation and the GSFC acknowledgment. The interface doesn't reproduce eclipse data, so this is not required, but the table could be aligned in a later frontend change.

## Changes made

| File | Change |
| --- | --- |
| `ATTRIBUTION.md` | All 8 original data rows and 15 software rows kept. Added: <br>• verified citation, producer and terms details to the PGDA 90, PGDA 69/AVGVISIB, NAIF and USGS rows;<br>• new rows for the LROC WAC illumination maps, the GSFC eclipse catalogue (with the required acknowledgment), JPL Horizons (unresolved) and ShadowCam (unused, unresolved);<br>• software rows refined with the verified bundled components: NumPy's GCC runtime exception, llvmlite/LLVM, the GDAL/PROJ versions with their licence-file paths, Pillow's bundled libraries, SpiceyPy's CSPICE note and d3-ease;<br>• the full Python closure table (35);<br>• the shipped-in-browser table (26);<br>• an IB-5 status section listing the unresolved items.<br>The original is preserved in `raw/ATTRIBUTION.before_ib5.md` (identical to the committed version). |
| `docs/validation_evidence/ib5_2026-11-11/` | New: this report and its evidence (see "Contents" below). |

Nothing else was modified. Checks after the work:
- backend code fingerprint `5bf9753f…`, suite fingerprint `1632af16…` and terrain acceptance `e48eb8ed…` are unchanged, algorithm 1.5.0 (`raw/backend_fingerprints_after.txt`);
- `frontend/dist` hashes are unchanged;
- the C10 frontend files' hashes are unchanged;
- the pre-existing uncommitted diff (14 files, +276/−70) is unchanged.

## Checks performed

| Check | Result |
| --- | --- |
| Direct requirements vs installed versions | 12/12 pinned versions installed; none missing |
| Dependency closure from Requires-Dist (platform markers evaluated) | 34 packages; `pip` is the only extra |
| Licence file present for every Python distribution | 35/35 |
| Vendored binaries enumerated, hashed, version resources read | 49 binaries (`raw/dll_version_resources.json`) |
| Runtime version confirmation | GDAL 3.12.2, PROJ 9.7.1 (rasterio) and 9.8.1 (pyproj), GEOS 3.14.1, CSPICE N0067, LLVM 22.1.0, OpenBLAS 0.3.34, Pillow library versions (`raw/runtime_versions.json`) |
| Lockfile vs installed `package.json` (licence and version) | 0 mismatches over 172 installed packages |
| Shipped set from the real Vite/Rollup build | 25 packages with code + the Archivo font package; `dist` untouched |
| Licence notices preserved in `dist` | 5 legal comments (React ×4, three.js); fonts: copyright + OFL URL in the name table; no licence file in `dist` |
| GeoTIFF metadata tags of all registered rasters and LPSR | no copyright, licence or source tags |
| Repository search for ShadowCam / USGS / terms | ShadowCam only in README line 274; USGS in the manifest, acquire, catalogue code and docs, with no registered data |
| `ATTRIBUTION.md` referenced by tests or CI | no (only a comment in `en.ts`) |

## Unresolved items (need online sources or a decision)

1. **Licences of the 44 vendored binaries** without shipped licence texts: rasterio ×34, pyproj ×7, numpy and llvmlite `msvcp140` ×2, and CSPICE. Upstream licence files for the exact versions listed are needed, or a statement from the wheel builders.
2. **Data terms:** PGDA (78, 81, 90) and PGDA 69, PDS/LROC (re-confirm the 2026-11-07 statement), JPL Horizons, the NAIF general statement (re-confirm), the USGS release `Use_Constraints` (when registered), and ShadowCam (only if used).
3. **`lerc@3.0.0`** has no licence file in the installed package (declared Apache-2.0; not shipped).
4. **The GSFC acknowledgment's coverage of the per-eclipse PDF figures** is not stated on the figures themselves.
5. **Decisions for the maintainers:**
   - generate a third-party notices file and ship the OFL text with `frontend/dist` (findings 1 and 2);
   - git-ignore `data/reference_validation/` (finding 3);
   - update the README's IB-5 limitation (README line 274 still says the inventory hasn't been done) in the final traceability task.

## Contents

| Path | What |
| --- | --- |
| `inventory_python.csv` | 35 Python distributions: version, scope, declared licence and its source, first copyright notice, licence files, source URL, obligations and restrictions found in the text, unresolved notes |
| `inventory_native_binaries.csv` | 49 vendored binaries: size, SHA-256, version resource, licence text shipped (or NONE), status |
| `inventory_npm.csv` | 172 installed npm packages: role (shipped / runtime not shipped / tooling), licences (`package.json` and lockfile), copyright, licence files, source, obligations, restrictions |
| `inventory_data_sources.csv` | 15 data sources and assets: presence, identifiers, provider, citation (verbatim where verified) and its evidence file, terms, status, redistribution in this repository, open questions |
| `licence_texts/python/`, `licence_texts/npm/` | Copies of every licence, notice, copyright and authors file found (Python: all 35 distributions; npm: the 168 installed packages that ship a licence file) |
| `raw/*.json` | Machine-readable inventories: Python metadata, npm metadata, Vite module list, DLL version resources, runtime versions, dist notices, summary; `ATTRIBUTION.before_ib5.md`; backend fingerprints after the work |
| `scripts/` | The inventory scripts (`py_inventory.py`, `dll_versions.py`, `npm_inventory.mjs`, `vite_modules.mjs`, `dist_notices.mjs`, `gen_tables.py`), to re-run the inventory |
