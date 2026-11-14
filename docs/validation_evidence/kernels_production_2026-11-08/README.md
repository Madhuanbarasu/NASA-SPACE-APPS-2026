# Production SPICE kernel installation (Phase 4, A1), 2026-11-08

The pinned production set in `backend/lunaops/manifests/kernels.production.json` (manifest SHA-256
`c54f8025a01e5f4258236a192756b2adc88fb998aecb2d84800165e01c766db6`) was installed with the existing tool,
`python -m lunaops.acquire kernels`, from `naif.jpl.nasa.gov` in a cloud session at git `b4ad283`
(Python 3.13.18, SpiceyPy 8.3.0, CSPICE N0067). `data/kernels/` was empty beforehand (only `.gitkeep`), so
nothing was overwritten and no `superseded_*` folder was created. No engine code, manifest, tolerance or
reference data was changed. The kernel files themselves are not committed (`data/kernels/*` is git-ignored);
`lock.json` here is a copy of the installed lock.

| Role | File | Bytes | SHA-256 | Check against a NAIF-published value |
| --- | --- | ---: | --- | --- |
| lsk | naif0012.tls | 5,257 | `678e32bdb5a744117a467cd9601cd6b373f0e9bc9bbde1371d5eee39600a039b` | size and MD5 `25a2fff30b0dedb4d76c06727b1895b1` match the PDS4 label |
| text_pck | pck00011.tpc | 131,226 | `3dff7b1dbeceaa01f25467767d3fa25816051c85d162d1edf04acb310ee28bb1` | none published; trusted on first download |
| spk | de440s.bsp | 32,726,016 | `c1c7feeab882263fc493a9d5a5b2ddd71b54826cdf65d8d17a76126b260a49f2` | MD5 `3917ee56769db332790c751e2168843d` matches `spk/planets/aa_checksums.txt` |
| lunar_pck | moon_pa_de440_200625.bpc | 12,863,488 | `60cd55aa401ea2ea97360636f567554bfe4e37bb829f901b4460a455dfaf783f` | none published; trusted on first download |
| lunar_fk | moon_de440_250416.tf | 19,478 | `a47c71e9c9f33796bdafb2c9d69a7ee447b6016ecad80f71cd6f3e479f9cf768` | size and MD5 `3556dde4bb7ca54a89917c301e650bbf` match the CLPS PDS4 label |
| de421_pck | moon_pa_de421_1900-2050.bpc | 1,770,496 | `656f90616403d75a75f0cd6c8830fc5b44f8cb4facb5ccb8915e752b397520cf` | none published; trusted on first download |
| de421_fk | moon_080317.tf | 21,437 | `78732477b96f9863e7b0d65bcee3c22b8707ca5ed0db56d1173319cb2e8c7993` | none published; trusted on first download |

Total 47,537,398 bytes (46 MB on disk with `lock.json`).

**Notes:**
- `moon_de440_250416.tf` was served from its first manifest URL, `generic_kernels/fk/satellites/`, with the
  size and MD5 of the CLPS PDS4 label. The fallback `moon_de440_220930.tf` was not needed. IB-2 (which FK is
  authoritative) is still open.
- NAIF publishes no `aa_checksums.txt` in `generic_kernels/pck/`, `fk/satellites/` or `lsk/` (HTTP 404 on
  2026-11-08), so the four files marked "trusted on first download" have no published checksum to check
  against. Their SHA-256 is now pinned in the lock.

## Files
- `acquire_kernels.log`: installer output. Staged download, published-value checks, SPICE test-load, then commit.
- `verify_kernels.log`: `python -m lunaops.acquire verify-kernels` (online). Every file `ok`, load ok, frame
  `MOON_ME_DE440_ME421` defined, coverage 1849-12-25 to 2150-01-21, V-02e prerequisites met.
- `independent_hashes.txt`: SHA-256 and MD5 recomputed with coreutils, independently of the tool.
- `naif_listings/spk_planets_aa_checksums.txt`: the NAIF checksum listing used for `de440s.bsp`.
- `pytest_kernel_setup.log`: `tests/test_kernel_setup.py` run twice. With the production set as the session
  source: 6 passed, 2 skipped (both need the sandbox set). With `LUNAOPS_KERNEL_SOURCE=data/kernels_demo`:
  8 passed. The installed files' SHA-256 values were identical before and after both runs.

**Not run here:** V-02e and the other tests that need production kernels (Phase 4 A2), and the validation report.
