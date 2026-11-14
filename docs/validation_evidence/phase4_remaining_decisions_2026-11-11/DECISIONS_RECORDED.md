# Phase 4 decisions D2, D3, D4, D5 and D7: formal records (2026-11-11)

| Field | Value |
| --- | --- |
| Approver | Project owner, by working-session instruction "Phase 4, Prompt 3: record approvals & register audits", 2026-11-11 (no name stated) |
| Basis | The decision-ready report `README.md` in this folder |
| Build | Algorithm 1.5.0; code `5bf9753f…37d2f8`; suite `1632af16…6d75eabc`; terrain acceptance `e48eb8ed…943dce`; production kernels. All unchanged. |
| Official report | `backend/validation/report.json` SHA-256 `5e6c76d7…db812e7b`, **unchanged**. The merge that would record U-04, U-06 and V-05 has **not** been run. |
| D1 | Closed earlier the same day; record preserved unchanged at `../d1_v05_decision_2026-11-11/ACCEPTANCE.md` |

**Summary of the recorded decisions:**

| Decision | Recorded outcome |
| --- | --- |
| D2 V-09/V-10 | **DEFERRED.** No criteria approved; both remain "not run" |
| D3 U-06 | **ACCEPTED (scoped).** Criteria met; U-06 result file `passed`, merge-ready |
| D4 U-04 | **ACCEPTED (scoped, conditional, condition met).** The current-build re-audit passed; U-04 result file `passed`, merge-ready |
| D5 IB-5 | **DEFERRED** with interim distribution restrictions; no licensing clearance claimed |
| D7 A15 | **UNDEFINED**, and not a Phase 4 completion criterion |

---

## D2: V-09 / V-10, formal deferral
**Decision:** V-09 and V-10 are deferred. The provisional criteria (RMSE ≤ 5 pp, abs(bias) ≤ 2 pp) are **not approved**, and no other criteria are approved.

**Measured results recorded** (`../v09_v10_final_2026-11-10/v09_v10.json`; re-derived in `d2_strata.log`):
- **Run:** 200 stratified points per map, 85–90°S, 18.6 years hourly, observer at 0 m, registered 5/20/80/240 m terrain, 0 inconclusive.
- **V-09 (Sun vs LOLA AVGVISIB):** RMSE **14.09 pp**, bias **−7.19 pp**, max abs(d) 53.09 pp. The difference is concentrated where the reference is above 0.6 (bias −16.6 and −28.8 pp in the two brightest strata).
- **V-10 (Earth vs AVGVISIB_EARTH):** RMSE **3.13 pp**, bias **−0.74 pp**, max abs(d) 22.27 pp.

**Unresolved reference observer height:**
- **Not documented:** AVGVISIB's observer height is not given in its PDS3 labels or the PGDA 69 page. LUNA-OPS assumed 0 m.
- **Strong sensitivity:** the A10 diagnostics showed that at the 36 worst V-09 points the mean difference moves from −14.9 pp at 0 m to +1.5 pp at 2 m and +8.1 pp at 10 m.
- **What that means:** the bright-stratum V-09 differences cannot be attributed to LUNA-OPS until the reference's height is established, for example from Mazarico et al. (2011) or the LOLA team.

**Official report:** V-09 and V-10 stay **"not run"**, as already merged. Nothing changes and no rerun or code change takes place.

**Consequence:** `disk_visibility`, `events` and `power_indicator` stay "Pending validation".

**Conditions to close later:**
1. Establish the observer height.
2. Approve criteria before a new run.
3. Rerun.

Any script change for steps 2 or 3 changes the suite fingerprint and requires every external validation to be regenerated.

---

## D3: U-06 performance, scoped acceptance
**Approved project criteria** (scoped; this is not a claim of formal field Core Web Vitals compliance):

| Criterion | Limit |
| --- | --- |
| Largest Contentful Paint (lab, every run) | ≤ 2.5 s |
| Cumulative Layout Shift (every run) | ≤ 0.1 |
| Browser-measured interaction response, p95 | ≤ 200 ms |
| Memory | no progressive leak over repeated remount cycles |
| Total Blocking Time | recorded for information only, **not a gate** |

**Scope:**
- **Machine:** HP Laptop 15-fd0xxx (Intel Core 5 120U, 15.7 GB RAM), Windows 11.
- **Browser:** Chrome 157 headless, 1440 × 900.
- **Profiles:** native; 4× CPU throttle; 4× CPU + 10 Mbit/s with 40 ms latency.
- **Evidence:** `../u06_2026-11-11/` (final build `index-kvDT7UBF.js`), reused without new measurement.

**Measured against the criteria** (`frontend_u06.json`):

| | native | 4× CPU | 4× CPU + 10 Mbit/s | Result |
| --- | --- | --- | --- | --- |
| LCP, worst run | 192 ms | 632 ms | 1,044 ms | met |
| CLS, worst run | 0 | 0 | 0 | met |
| Interaction p95 (Event Timing, 20 keyboard time-cursor interactions) | 32 ms | 40 ms | not measured (loads only) | met where measured |
| Memory, 5 remount cycles with forced GC | +0.3 MB heap, +5 nodes, +5 listeners, no WebGL warnings | – | – | met (the audit found no leak) |
| TBT, cold / warm (information only) | 0 / 0 ms | 410 / 249 ms | 214 / 282 ms | not gated |

**Disclosures recorded with the acceptance:**
- **Two backend map tiles were excluded:** `/api/tiles/0/0/0.png` and `/api/tiles/1/0/1.png` were **blocked** in every measured run. Without blocking, a page load starts one backend tile render that takes minutes and up to about 2 GB. The recommended backend fix (`api/tiles.py`) has not been made.
- **What "interaction response" was measured on:** browser Event Timing on keyboard time-cursor steps only.
  - Other single-frame interactions (tab switches up to 117 ms, 3D rotate ≤ 36 ms, mode and metric switches ≤ 32 ms, comparison cell → result ≤ 194 ms at 4× CPU) are reported, not gated.
  - Data-loading operations are reported, not gated: cached analysis → result 632 ms and → 3D data 955 ms at 4× CPU; comparison → matrix about 650 ms.
- **Profile coverage:** the third profile (network throttle) had no interaction workflow, and the memory check ran in the native profile only.
- **Sample size and limits:** few samples (3 cold and 2 warm loads per profile; one workflow per CPU profile), one laptop, one engine, desktop applications running.
- **Per-cycle memory:** a per-cycle memory series was not recorded, so "no progressive leak" rests on the before/after values and the audit's finding.

**Registration:** `frontend_u06.json` (owner `frontend_u06`), status **passed**, with the current backend fingerprints and the frontend `dist` hashes (equal to U-06's final build). It passes the merge guard in the no-write dry run. **It is not yet merged.**

---

## D4: U-04 accessibility, conditional scoped acceptance (condition met)
**Condition:** re-run `npm run audit:a11y` against the current frontend build. No dependency was installed.

**Re-run** (`u04_current_build/`):
- **When:** 2026-11-11 18:14:33 to 18:17:19 UTC, exit 0.
- **Build:** `frontend/dist`, byte-identical to U-06's final build, which is the current build.
- **Server:** `start.py --no-browser --no-build --port 8765`, with production kernels and registered terrain; stopped afterwards.

**Result** (`u04_compare.py` → `u04_compare.log`):
- **0 automated problems in all 6 views:** no unnamed controls, roles, contrast, target-size, focus-indicator, clipping, obscured-focus, reflow, text-spacing, label, duplicate-id or `role=application` problems.
- **Tab walks:** the Tab-stop counts are identical to the release run.
- **Functional tests:** all **16** produced the same outcome as the release run.
- **The condition is met.**

**Accepted scope and limitations** (no claim of unrestricted WCAG 2.2 AA conformance):
- **Assessed:** WCAG 2.2 Level A/AA, 55 success criteria, 24 defects fixed (`../u04_2026-11-11/`).
- **Browser:** Chrome/Chromium 157 headless only; Firefox and Safari not tested.
- **No real screen-reader user session:** screen-reader behaviour was inferred from the accessibility tree.
- **Other limits:** zoom emulated through the viewport; speech input not tested; empty curated-site list.

**Registration:** `frontend_u04.json` (owner `frontend_u04`), status **passed**, with the current backend fingerprints, the frontend `dist` hashes and the audit evidence hashes. It passes the merge guard in the no-write dry run. **It is not yet merged.**

---

## D5: IB-5 licensing and distribution, formal deferral
**Decision:** the unresolved IB-5 items are formally deferred, based only on the existing inventory (`../ib5_2026-11-11/`). No further licensing research was done, and **full licensing clearance is not claimed**.

**Deferred items:**
1. **Native-library licences:** 44 of the 49 native libraries bundled in the Python wheels ship no licence text:
   - rasterio ×34 (including OpenSSL 3.6.1, curl, libpq, libxml2, LibTIFF, SQLite, HDF5, netCDF, GEOS);
   - pyproj ×7;
   - `msvcp140` ×2;
   - CSPICE (SpiceyPy).
2. **Data terms not confirmed:**
   - PGDA 78/81/90 and PGDA 69;
   - PDS/LROC (re-confirmation pending);
   - JPL Horizons outputs;
   - the NAIF general statement;
   - the USGS release `Use_Constraints`;
   - ShadowCam (unused).
3. **`lerc@3.0.0`:** licence file missing (Apache-2.0 declared; not shipped).
4. **GSFC figures:** the acknowledgment's coverage of the per-eclipse PDF figures is not stated.
5. **Missing frontend notices and font licence:** `frontend/dist` contains licence comments only for React and three.js. The notices of the other 21 shipped packages are missing, `dist` has no notices file, and the Archivo font's OFL-1.1 text is not shipped (re-checked 2026-11-11).
6. **Reference-validation folder:** `data/reference_validation/` (256 MB; PGDA LPSR, PDS AVGVISIB and LROC rasters with unresolved terms; one 154 MB file) is not git-ignored (re-checked 2026-11-11).

**Interim distribution restrictions** (in force until each item is resolved):
- **R1. No packaged environment:** do not redistribute a packaged Python environment (container, installer or zipped venv); item 1 applies.
- **R2. No reference rasters:** do not commit, upload or redistribute `data/reference_validation/` (items 2 and 6). Exclude it, for example with a `.gitignore` entry (a repository change, not made here).
- **R3. Hosting the frontend:** do not publish or host `frontend/dist` as a release artifact without a third-party notices file and the OFL text (item 5); adding them is a separate build or frontend change.
- **R4. Third-party evidence:** keep the committed Horizons responses and GSFC pages and figures as validation evidence only, with the attribution in `ATTRIBUTION.md`. Do not republish them as a data product until items 2 and 4 are resolved.
- **R5. Source repository:** the source may be shared under Apache-2.0 with `ATTRIBUTION.md`, subject to R1–R4.

**Conditions for resolution:** for each item, an upstream licence text for the exact version or a published terms statement, recorded in `ATTRIBUTION.md` and the IB-5 inventory, followed by owner sign-off.

**Consequence:** no effect on validation, labels, fingerprints or `report.json`. The distribution risks remain until resolution.

---

## D7: A15 recorded as undefined
**Decision:** A15 has no defined scope in any project record.
- **Search:** all repository text records; the only independent mention is the C10 README's "final A1–A15 traceability update", which names a range, not a task.
- **The Phase 1.1 blueprint is not available** in the repository.
- **Record:** A15 is **undefined**. No task, deliverable or acceptance is assigned, and **it is not a Phase 4 completion criterion**.
- **If an authoritative definition is supplied later:** A15 is added to the register with its own status and evidence. No scope is assumed here.

---

## Status after these decisions

> **Update 2026-11-12:** the merge below was run after approval.
> - **Official report:** `2279606c…d077d376`; V-04, V-05, V-11 to V-14, U-04 and U-06 passed; V-09 and V-10 not run; 0 rejected; 32/32 checks.
> - **Phase 4 verdict:** COMPLETE WITH APPROVED DEFERRALS (`../phase4_final_merge_2026-11-12/README.md`).
> - **The text below:** it records the state before that merge.

**All seven Phase 4 decisions now have a recorded outcome:**
- **Closed:** D1 (accepted) and D6 (completed).
- **Accepted:** D3 and D4, both scoped.
- **Deferred:** D2 and D5.
- **Recorded as undefined:** D7.

**Not yet done** (each needs its own go-ahead):
- **Report merge:** one `run_validation` with the eight files listed in `merge_dry_run.json`: V-09/V-10, V-11 and V-12 re-merged; the full `horizons.json` (V-04 and V-05); V-13; V-14; `frontend_u04.json`; `frontend_u06.json`.
  - **The dry run:** no rejections; it projects V-04, V-05, V-11, V-12, V-13, V-14, U-04 and U-06 passed, and V-09 and V-10 not run.
  - **Effect on labels:** `sun_earth_azel` would become **Validated**. `horizon` would become Validated on the status page and stay Pending in results that carry horizon sigma (L_corr assumption). `disk_visibility`, `events` and `power_indicator` stay Pending (D2).
- **Phase 4 is not declared complete here.** The deferrals D2 and D5 remain open items, and the declaration is the owner's.
