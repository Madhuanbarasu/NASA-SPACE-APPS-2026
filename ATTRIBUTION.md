# Attribution and source manifest (blueprint Section 12.2)

## Data

| Source | Terms found | Attribution |
| --- | --- | --- |
| PGDA LOLA large-area DEMs and error maps, "A New View of the Lunar South Pole from LOLA" (product 90); also its LPSR_80S_20MPP_ADJ permanent-shadow map (V-11 validation) | Product page asks users to cite the paper (wording kept verbatim in `docs/validation_evidence/v11_a11_2026-11-09/coverage_review/pgda90_page_excerpt.txt`, 2026-11-09). No licence or redistribution terms recorded (IB-5: unresolved) | Barker et al. 2023, PSJ 4, 183, doi:10.3847/PSJ/acf3e1; data doi:10.60903/gsfcpgda-lola-spole |
| PGDA South Pole LOLA DEM Mosaic, 87-90 S 5 m (product 81) | Product page asks users to cite the paper | Barker et al. 2021, PSS 203, 105119, doi:10.1016/j.pss.2020.105119 |
| PGDA High-Resolution LOLA Topography for Lunar South Pole Sites: site DEMs, total-Z-uncertainty maps, ROI shapefiles (product 78) | Product page asks users to cite the paper | Barker et al. 2021, PSS 203, 105119, doi:10.1016/j.pss.2020.105119; site numbering follows Mazarico et al. 2011 |
| LOLA illumination maps, Lunar Polar Illumination (product 69, validation only); AVGVISIB_85S_060M_201608[_EARTH] from PDS data set LRO-L-LOLA-4-GDR-V1.0 (V-09/V-10) | Product page asks users to cite the paper. The PDS3 labels name the producer (LRO_LOLA_TEAM, David E. Smith, Goddard Space Flight Center) and state no terms (IB-5: unresolved) | Mazarico et al. 2011, Icarus 211, 1066-1081, doi:10.1016/j.icarus.2010.10.030 |
| NAIF SPICE toolkit and kernels | No fees or licensing required; acknowledgement encouraged. The `pck00011.tpc` header asks that a user-modified file have its by-line, date, version description and file name updated; LUNA-OPS uses the kernels unmodified (pinned by SHA-256) | NASA's SPICE system, Navigation and Ancillary Information Facility, JPL |
| DE440 ephemeris | Cited by NAIF's PCK readme | Park et al. 2021, AJ 161, 105 |
| USGS "Down Selected Artemis III Candidate Landing Site Navigational Grids" (if registered) | Not yet recorded from this release's metadata (not registered in this installation; IB-5: unresolved) | McClernan, M.T., 2024, U.S. Geological Survey data release, doi:10.5066/P1MEQ6UK (ScienceBase item 671a6fa8d34efed5620f89f8); LGRS ACC navigation grids; regions sourced from LROC QuickMap; not an official NASA boundary |
| LROC products (if registered) | PDS products public domain; LROC website images copyrighted | NASA/GSFC/Arizona State University; PDS copies only |
| LROC WAC south-pole illumination maps WAC_POLE_ILL_TWI_SOUTH_100M and WAC_POLE_ILL_PCT_SOUTH_100M (V-12 validation) | The product README asks: "When citing this product, use the following reference: Speyerer, E. J., & Robinson, M. S. (2013)…" (`backend/validation/reference/lroc/WAC_POLE_ILL_TWI_SOUTH_README.TXT`). Terms: as for LROC products above | Speyerer, E. J. and Robinson, M. S. (2013), Persistently illuminated regions at the lunar poles: Ideal sites for future exploration, Icarus 222(1), 122-136, doi:10.1016/j.icarus.2012.10.010. Instrument: Robinson et al. 2010, Space Science Reviews 150, 81-124, doi:10.1007/s11214-010-9634-2 |
| NASA GSFC lunar eclipse catalogue (V-13 validation; figure and page copies kept in `docs/validation_evidence/v13_gsfc_2026-11-09/gsfc/`) | "Permission is freely granted to reproduce this data when accompanied by an acknowledgment" (`LEdecade2021.html`) | Eclipse Predictions by Fred Espenak, NASA's GSFC |
| NASA Scientific Visualization Studio "CGI Moon Kit" (SVS ID 4720): `lroc_color_2k.jpg` (2048×1024 colour map, the 2025 version: built from the LROC WAC Hapke-normalised mosaic, 643/566/415 nm, which covers 70°N–70°S; higher latitudes are filled with the lower-resolution LOLA albedo map LDAM) and `ldem_3_8bit.jpg` (1024×512 8-bit LOLA displacement image); used only as the 3D globe's imagery and visual relief shading, not as elevation data (`frontend/public/moon/`) | SVS help page (retrieved 2026-11-11): "All of our content is in the public domain (unless otherwise noted), meaning that it is free to download, use, and redistribute for whatever purposes you see fit." NASA Images and Media Usage Guidelines: texture maps "generally are not subject to copyright in the United States"; NASA should be acknowledged as the source; no implied endorsement; the NASA insignia and logotype are not in the public domain and are not used. The page notes the map "is optimized for aesthetics, not science". Copies: `docs/validation_evidence/phase5_prompt1_2026-11-12/provenance/` | "NASA's Scientific Visualization Studio" (credit line requested on the item page; visualizer Ernie Wright, scientist Noah Petro); data from the LRO LROC and LOLA instrument teams |
| JPL Horizons API outputs (V-04/V-05 validation; raw outputs kept in `docs/validation_evidence/horizons_v04_v05_2026-11-09/horizons_raw/`) | Not recorded: the outputs state no terms (IB-5: unresolved) | NASA/JPL Horizons on-line solar system data and ephemeris computation service |
| ShadowCam | Not used by LUNA-OPS; terms not recorded (IB-5: unresolved, applies only if ShadowCam data is added) | - |

Sandbox test kernels (tests only, never production results): `de440s.bsp` from a GitHub mirror verified against the mirror's SHA256SUMS; NAIF's DE421 lunar PCK/FK as redistributed in the `lunarsky` 1.0.1.post2 PyPI wheel; generated test LSK and radii kernels.

## Software (licences as reported by PyPI and npm)

| Package | Version | Licence |
| --- | --- | --- |
| SpiceyPy (bundles CSPICE N0067 as `cspice.dll`; the wheel ships no CSPICE licence text, see NAIF above) | 8.3.0 | MIT |
| NumPy (the wheel also bundles OpenBLAS 0.3.34: BSD-3-Clause; LAPACK: BSD-3-Clause-Open-MPI; GCC runtime: GPL-3.0-or-later WITH GCC-exception-3.1, per its `LICENSE.txt`) | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| Numba (third-party notices in `LICENSES.third-party`) | 0.68.0 | BSD |
| llvmlite (Numba dependency; `llvmlite.dll` contains LLVM 22.1.0) | 0.50.0 | BSD-2-Clause AND Apache-2.0 WITH LLVM-exception |
| rasterio (bundles GDAL 3.12.2, licence in `rasterio/gdal_data/LICENSE.TXT`, and PROJ 9.7.1, licence in `rasterio/proj_data/copyright`, plus 34 other DLLs whose licence texts the wheel does not ship: IB-5 unresolved) | 1.5.2 | BSD-3-Clause |
| pyproj (bundles PROJ 9.8.1, licence in `LICENSE_proj`, plus 7 other DLLs whose licence texts the wheel does not ship: IB-5 unresolved) | 3.8.0 | MIT |
| FastAPI / Uvicorn | 0.161.1 / 0.54.0 | MIT / BSD-3-Clause |
| Pydantic | 2.14.1 | MIT |
| Pillow (bundles brotli, FreeType, HarfBuzz, Little CMS, libavif, libjpeg-turbo, libpng, libwebp, OpenJPEG, LibTIFF, XZ and zlib-ng, with their licences in the wheel's `LICENSE`) | 13.0.0 | MIT-CMU (HPND) |
| pyshp | 3.1.6 | MIT |
| React / React DOM | 18.3.1 | MIT |
| OpenLayers (`ol`) | 10.11.0 | BSD-2-Clause |
| proj4js | 2.22.0 | MIT |
| D3 (shipped modules are ISC except `d3-ease`, BSD-3-Clause, Copyright 2001 Robert Penner and 2010-2026 Mike Bostock) | 7.9.0 | ISC |
| three.js | 0.170.0 | MIT |
| Archivo typeface (@fontsource-variable/archivo) | 5.3.0 | SIL Open Font License 1.1 |

### Python dependency closure (IB-5)

Every package installed in `backend/.venv`. The direct ones are pinned in `backend/requirements.txt`. Licences are as declared in each package's installed metadata, and each package's licence file was read (copies in the IB-5 evidence).

| Package | Version | Licence (as declared in the installed metadata) | Scope |
| --- | --- | --- | --- |
| fastapi | 0.161.1 | MIT | direct |
| httpx | 0.28.1 | BSD-3-Clause | direct (tests) |
| numba | 0.68.0 | BSD | direct |
| numpy | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | direct |
| pillow | 13.0.0 | MIT-CMU | direct |
| pydantic | 2.14.1 | MIT | direct |
| pyproj | 3.8.0 | MIT | direct |
| pyshp | 3.1.6 | MIT | direct |
| pytest | 9.1.1 | MIT | direct (tests) |
| rasterio | 1.5.2 | BSD-3-Clause | direct |
| spiceypy | 8.3.0 | MIT | direct |
| uvicorn | 0.54.0 | BSD-3-Clause | direct |
| affine | 3.0.1 | BSD-3-Clause | transitive (via rasterio) |
| annotated-doc | 0.0.5 | MIT | transitive (via fastapi) |
| annotated-types | 0.8.0 | MIT | transitive (via pydantic) |
| anyio | 4.16.0 | MIT | transitive (via httpx, starlette) |
| attrs | 26.1.0 | MIT | transitive (via affine, rasterio) |
| certifi | 2026.10.23 | MPL-2.0 | transitive (via httpcore, httpx, pyproj, rasterio) |
| click | 8.5.1 | BSD-3-Clause | transitive (via rasterio, uvicorn) |
| colorama | 0.4.6 | BSD License | transitive (via pytest) |
| h11 | 0.16.0 | MIT | transitive (via httpcore, uvicorn) |
| httpcore | 1.0.9 | BSD-3-Clause | transitive (via httpx) |
| idna | 3.20 | BSD-3-Clause | transitive (via anyio, httpx) |
| iniconfig | 2.3.1 | MIT | transitive (via pytest) |
| llvmlite | 0.50.0 | BSD-2-Clause AND Apache-2.0 WITH LLVM-exception | transitive (via numba) |
| opentelemetry-api | 1.45.2 | Apache-2.0 | transitive (via fastapi) |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | transitive (via pytest) |
| pluggy | 1.7.0 | MIT | transitive (via pytest) |
| pydantic_core | 2.50.1 | MIT | transitive (via pydantic) |
| Pygments | 2.21.0 | BSD-2-Clause | transitive (via pytest) |
| pyparsing | 3.3.3 | MIT | transitive (via rasterio) |
| starlette | 1.10.0 | BSD-3-Clause | transitive (via fastapi) |
| typing-inspection | 0.4.5 | MIT | transitive (via fastapi, pydantic) |
| typing_extensions | 4.16.0 | PSF-2.0 | transitive (via anyio, fastapi, opentelemetry-api, pydantic, pydantic-core, typing-inspection) |

`pip` 25.2 (MIT) is also installed in the environment but is not required by LUNA-OPS.

### Shipped in the browser bundle (IB-5)

These packages put code or assets into `frontend/dist`, as determined from the production Vite/Rollup build. Copyright notices are from each package's licence file.

| Package | Version | Licence | Copyright (from the package licence file) |
| --- | --- | --- | --- |
| @fontsource-variable/archivo (font files and CSS) | 5.3.0 | OFL-1.1 | Copyright 2020 The Archivo Project Authors (https://github.com/Omnibus-Type/Archivo) |
| d3-array | 3.2.5 | ISC | Copyright 2010-2026 Mike Bostock |
| d3-color | 3.1.1 | ISC | Copyright 2010-2026 Mike Bostock |
| d3-dispatch | 3.0.2 | ISC | Copyright 2010-2026 Mike Bostock |
| d3-ease | 3.0.2 | BSD-3-Clause | Copyright 2010-2026 Mike Bostock; Copyright 2001 Robert Penner |
| d3-format | 3.1.3 | ISC | Copyright 2010-2026 Mike Bostock |
| d3-interpolate | 3.0.2 | ISC | Copyright 2010-2026 Mike Bostock |
| d3-path | 3.1.1 | ISC | Copyright 2015-2026 Mike Bostock |
| d3-scale | 4.0.3 | ISC | Copyright 2010-2026 Mike Bostock |
| d3-selection | 3.0.1 | ISC | Copyright 2010-2026 Mike Bostock |
| d3-shape | 3.2.1 | ISC | Copyright 2010-2026 Mike Bostock |
| d3-time | 3.1.1 | ISC | Copyright 2010-2026 Mike Bostock |
| d3-time-format | 4.1.1 | ISC | Copyright 2010-2026 Mike Bostock |
| d3-timer | 3.0.2 | ISC | Copyright 2010-2026 Mike Bostock |
| d3-transition | 3.0.2 | ISC | Copyright 2010-2026 Mike Bostock |
| d3-zoom | 3.0.1 | ISC | Copyright 2010-2026 Mike Bostock |
| mgrs | 1.0.0 | MIT | Copyright (c) 2012, Mike Adair, Richard Greenwood, Didier Richard, Stephen Irons, Olivier Terral, Calvin Metcalf |
| ol | 10.11.0 | BSD-2-Clause | Copyright 2005-present, OpenLayers Contributors |
| proj4 | 2.22.0 | MIT | Copyright (c) 2014, Mike Adair, Richard Greenwood, Didier Richard, Stephen Irons, Olivier Terral and Calvin Metcalf |
| quickselect | 3.0.0 | ISC | Copyright (c) 2024, Vladimir Agafonkin |
| rbush | 4.0.1 | MIT | Copyright (c) 2024 Volodymyr Agafonkin |
| react | 18.3.1 | MIT | Copyright (c) Facebook, Inc. and its affiliates. |
| react-dom | 18.3.1 | MIT | Copyright (c) Facebook, Inc. and its affiliates. |
| scheduler | 0.23.2 | MIT | Copyright (c) Facebook, Inc. and its affiliates. |
| three | 0.170.0 | MIT | Copyright © 2010-2024 three.js authors |
| wkt-parser | 1.6.0 | MIT | Copyright (c) 2014, Mike Adair, Richard Greenwood, Didier Richard, Stephen Irons, Olivier Terral and Calvin Metcalf |

The other 146 installed npm packages are build or development tools, or runtime dependencies that the build tree-shakes out of the bundle. None of them ships in `frontend/dist`. They are listed with their licences in the IB-5 evidence.

## Licence inventory status (blueprint IB-5)

The inventory was taken on 2026-11-11 from local files only: installed metadata, the licence files shipped in each package, version resources embedded in the DLLs, product READMEs and labels, and saved product pages. No information was downloaded. Evidence, CSV tables and copies of every licence text are in `docs/validation_evidence/ib5_2026-11-11/`.

**Unresolved:**

- **Native libraries vendored in wheels:**
  - 44 of the 49 vendored Windows binaries ship without a licence text: 34 in `rasterio.libs`, 7 in `pyproj.libs`, the Microsoft C++ runtime copies in `numpy.libs` and `llvmlite.libs`, and CSPICE in SpiceyPy.
  - Examples are GEOS, OpenSSL, curl, PostgreSQL libpq, libxml2, libiconv, HDF5, netCDF, SpatiaLite, FreeXL, LibTIFF, SQLite and the Microsoft C++ runtime.
  - Their version resources and copyright notices are recorded, but their licences are not verified.
- **Data terms:** the licence and redistribution terms of the PGDA products, the PDS/LROC products, JPL Horizons outputs, the USGS release and ShadowCam are not recorded locally.
- **npm:** `lerc` 3.0.0 has no licence file. It is a runtime dependency but is not in the bundle.

**Findings for anyone redistributing LUNA-OPS:**

- **JavaScript bundle notices (addressed 2026-11-12, Phase 5 final):** the inventory found that `frontend/dist` kept licence comments only for React (with React DOM and Scheduler) and three.js. The build now ships `THIRD_PARTY_NOTICES.txt` (from `frontend/public/`): the full text of the licence file of each of the 26 shipped packages, generated by `frontend/scripts/gen-notices.mjs` from the installed packages' own files. The shipped set was re-derived from the production build and is unchanged from the inventory. Evidence: `docs/validation_evidence/phase5_final_2026-11-12/ib5_review/`.
- **Fonts (addressed 2026-11-12):** the Archivo WOFF2 files carry the copyright notice and the OFL URL. The build now also ships `OFL.txt`, the font package's own licence file, which contains the OFL 1.1 text.
- **Moon globe imagery (Phase 5):** `frontend/public/moon/` holds two NASA SVS CGI Moon Kit images. Their terms (public domain unless noted; NASA acknowledged as the source; no endorsement) are verified and recorded in the table above and in `moon/ATTRIBUTION.txt`, which ships with the build.
- **Reference data in git (addressed 2026-11-12):** `data/reference_validation/` (256 MB of PGDA and PDS reference rasters, redistribution terms unresolved) is now listed in `.gitignore`. The files stay on disk, and they must still not be committed or redistributed.
- **Still unresolved (D5 deferral stands):** the native-library licences, the data terms, `lerc` and the GSFC figure acknowledgment listed above. No licensing clearance is claimed.

Product names, file names, citations and DOIs above were checked against the PGDA product pages (69, 78, 81, 90) and the ScienceBase item page on 2026-11-07.
