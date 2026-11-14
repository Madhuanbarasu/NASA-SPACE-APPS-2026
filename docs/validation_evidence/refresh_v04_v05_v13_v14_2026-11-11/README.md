# Phase 4: V-04, V-05, V-13 and V-14 validation refresh, 2026-11-11

**Purpose:** refresh the stale V-04, V-05, V-13 and V-14 evidence with the current production configuration and algorithm 1.5.0.
- **Not Phase 4 closure:** this is not the Phase 4 closure documentation, and **Phase 4 is not complete**.
- **Live report not updated:** no `run_validation` was executed, so the live `backend/validation/report.json` was not updated.

## Results

| Test | Result | Criterion and approval | Key measurement | Evidence |
| --- | --- | --- | --- | --- |
| **V-04** JPL Horizons direction | **PASS** | abs(dAz cos El), abs(dEl) <= 0.01° (existing criterion) | max 5.235e-07° / 5.226e-07° over 7,931 epochs | `v04_horizons/` |
| **V-05** rise/set timing vs Horizons | **PROVISIONAL** | proposed 1.0 s threshold **not approved**, so not marked PASS | 18/18 crossings matched, 0 missed, 0 spurious; max abs(dt) 0.49995 s | `v05_riseset/` (separate report) |
| **V-13** eclipse contacts vs NASA GSFC | **PASS** | containment in [P1, P4] and [U1, U4], 1 s slack (existing criterion) | 20/20; smallest margin 482.6 s | `v13_eclipse/` |
| **V-14** month-long detection | **PASS** | full form, 1.0 s, 3 s match, 2 s window (existing criteria, pinned in tests) | 955 edges, 0 missed, 0 over 1.0 s, 0 spurious; worst 0.500 s | `v14_month/` |

**Blocked:** nothing. JPL Horizons and the GSFC site were reachable through the normal network path, and the production kernels and every required input were present.

## Fingerprints and status (`00_preflight/`)
| Item | Value | Before = after the runs |
| --- | --- | --- |
| Code fingerprint | `5bf9753fa5c5493eadeb9839c07b837f2e3e69e3986e76146a2ed1717e37d2f8` | yes |
| Suite fingerprint | `1632af16763dda4e27909a9af3d2fdd903b0d58951faacded72c4cf06d75eabc` | yes |
| Terrain acceptance digest | `e48eb8ed0ca2003c2769c60932323dbce34385e4eac2a675f076e13bbd943dce` | yes |
| `terrain_acceptance.json` SHA-256 | `c04650699f1cdade46b29614fc4f9b2dd20d27eb3b99fd32b9a8e72a892356ae` | yes (unchanged) |
| Algorithm version | 1.5.0 | yes |
| Kernel profile | production (7 files; SHA-256 in each `meta.kernels`) | yes |
| `backend/validation/report.json` SHA-256 | `00d2cda1bf3fe38fe98cc8a76e92acabdf9cb771ab900119750203586b15c239` | yes (byte-identical; checked against a pre-run copy) |
| Python, SpiceyPy, CSPICE, NumPy | 3.13.7 (Windows 11 x64), 8.3.0, N0067, 2.5.4 | (`pip_freeze.txt`) |

**Files in `00_preflight/`:**
- **`snapshot_before.json` / `snapshot_after.json`:** these also hold the SHA-256 of the validation scripts and reference files, which were identical before and after.
- **`verify_kernels.log`:** all 7 kernels match the lock file; NAIF checksums are OK where NAIF publishes them.
- **`merge_guard_dry_run.json`:** `validation.common.merge_external` was run **in memory only** against the live report's tests.
  - All three result files pass the code, suite and kernel guard; none was rejected.
  - They would turn V-04, V-05 and V-13 from "not run" into "passed".
  - **V-05 caution:** a merge of `v04_horizons/horizons.json` would record V-05 as `passed` under the unapproved 1.0 s threshold, so it must not be merged until a V-05 criterion is approved.

## Stale evidence identified (not modified)
Every earlier V-04/V-05/V-13/V-14 result file was produced with code fingerprint `230071e0…` and an older suite fingerprint. Both differ from the current build, so the live report lists V-04, V-05 and V-13 as "not run", and V-14 only in its pytest form.

| Earlier evidence | Run | Stale code / suite |
| --- | --- | --- |
| `../horizons_v04_v05_2026-11-09/horizons.json` (A8/A9) | 2026-11-09 | yes / yes |
| `../v13_gsfc_2026-11-09/v13.json` (A13) | 2026-11-09 | yes / yes |
| `../v14_month_a14_2026-11-10/v14.json` (A14), and its `report/horizons.json` and `report/v13.json` | 2026-11-10 | yes / yes |

**What the refresh reproduced:**
- **V-04/V-05:** the same values. LUNA-OPS az/el moved by ≤ 1.4e-13° and its event times are identical.
  - The Horizons reference changed slightly: a new EOP file, 1e-9° last-digit changes, and crossing times moved ≤ 8.4e-5 s.
- **V-13:** identical margins and event times.
- **V-14:** identical counts and offsets.

## Preservation
- **Not modified:**
  - backend algorithms, scientific calculations, thresholds and acceptance decisions;
  - `terrain_acceptance.json`;
  - the A6/A7, V-09 to V-12 and earlier V-04/V-05/V-13/V-14 evidence folders;
  - `report.json`.
- **New files:** nothing was added under `backend/`, so the suite fingerprint is unchanged. The two helper scripts live in `scripts/`:
  - **`snapshot.py`:** read-only fingerprint snapshot.
  - **`v05_report.py`:** post-processes `horizons.json` into the separate V-05 report.
- **No other actions:** no dependency was installed and no Git operation was run.
- **One run each:** the validations ran one after another (V-04/V-05, then V-13, then V-14).

## Outstanding (not done here)
1. **V-05:** a formal V-05 timing criterion has to be approved. If it is not the 1.0 s already in `horizons_compare.py`, the script has to change and the run has to be repeated.
2. **Merging:** the results have to be merged into the production report with `run_validation --merge`.
   - That overwrites `report.json`, which this refresh was told not to do.
   - It also re-runs the full pytest suite, which was not run here.
   - It needs a decision on how to handle V-05 (see 1).
3. **Phase 4 closure:** the closure documentation (`docs/TRACEABILITY.md`, the evidence index in `../README.md`) was not started.
   - V-09 and V-10 remain without approved criteria ("not run" in the live report).
   - U-04 and U-06 are also "not run" in the live report; they are outside this refresh.

`SHA256SUMS` covers every file in this folder.
