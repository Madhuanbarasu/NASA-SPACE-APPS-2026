# Attribution and source manifest (blueprint Section 12.2)

## Data

| Source | Terms found | Attribution |
| --- | --- | --- |
| PGDA LOLA large-area DEMs and error maps, "A New View of the Lunar South Pole from LOLA" (product 90) | Product page asks users to cite the paper | Barker et al. 2023, PSJ 4, 183, doi:10.3847/PSJ/acf3e1; data doi:10.60903/gsfcpgda-lola-spole |
| PGDA South Pole LOLA DEM Mosaic, 87-90 S 5 m (product 81) | Product page asks users to cite the paper | Barker et al. 2021, PSS 203, 105119, doi:10.1016/j.pss.2020.105119 |
| PGDA High-Resolution LOLA Topography for Lunar South Pole Sites: site DEMs, total-Z-uncertainty maps, ROI shapefiles (product 78) | Product page asks users to cite the paper | Barker et al. 2021, PSS 203, 105119, doi:10.1016/j.pss.2020.105119; site numbering follows Mazarico et al. 2011 |
| LOLA illumination maps, Lunar Polar Illumination (product 69, validation only) | Product page asks users to cite the paper | Mazarico et al. 2011, Icarus 211, 1066-1081, doi:10.1016/j.icarus.2010.10.030 |
| NAIF SPICE toolkit and kernels | No fees or licensing required; acknowledgement encouraged | NASA's SPICE system, Navigation and Ancillary Information Facility, JPL |
| DE440 ephemeris | Cited by NAIF's PCK readme | Park et al. 2021, AJ 161, 105 |
| USGS "Down Selected Artemis III Candidate Landing Site Navigational Grids" (if registered) | Not yet recorded from this release's metadata | McClernan, M.T., 2024, U.S. Geological Survey data release, doi:10.5066/P1MEQ6UK (ScienceBase item 671a6fa8d34efed5620f89f8); LGRS ACC navigation grids; regions sourced from LROC QuickMap; not an official NASA boundary |
| LROC products (if registered) | PDS products public domain; LROC website images copyrighted | NASA/GSFC/Arizona State University; PDS copies only |

Sandbox test kernels (tests only, never production results): `de440s.bsp` from a GitHub mirror verified against the mirror's SHA256SUMS; NAIF's DE421 lunar PCK/FK as redistributed in the `lunarsky` 1.0.1.post2 PyPI wheel; generated test LSK and radii kernels.

## Software (licences as reported by PyPI and npm)

| Package | Version | Licence |
| --- | --- | --- |
| SpiceyPy (bundles CSPICE under NAIF rules) | 8.3.0 | MIT |
| NumPy | 2.5.4 | BSD-3-Clause and bundled permissive licences |
| Numba | 0.68.0 | BSD |
| rasterio (bundles GDAL and other libraries in wheels) | 1.5.2 | BSD-3-Clause |
| pyproj | 3.8.0 | MIT |
| FastAPI / Uvicorn | 0.161.1 / 0.54.0 | MIT / BSD-3-Clause |
| Pydantic | 2.14.1 | MIT |
| Pillow | 13.0.0 | MIT-CMU (HPND) |
| pyshp | 3.1.6 | MIT |
| React / React DOM | 18.3.1 | MIT |
| OpenLayers (`ol`) | 10.11.0 | BSD-2-Clause |
| proj4js | 2.22.0 | MIT |
| D3 | 7.9.0 | ISC |
| three.js | 0.170.0 | MIT |
| Archivo typeface (@fontsource-variable/archivo) | 5.3.0 | SIL Open Font License 1.1 |

Licences bundled inside Python wheels (for example GDAL and PROJ inside rasterio and pyproj) are still to be inventoried (blueprint IB-5).

Product names, file names, citations and DOIs above were checked against the PGDA product pages (69, 78, 81, 90) and the ScienceBase item page on 2026-11-07.
