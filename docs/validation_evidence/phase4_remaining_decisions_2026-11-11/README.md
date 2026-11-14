# Phase 4 remaining decisions: D2, D3, D4, D5, D7 (decision-ready report, 2026-11-11)

> **Update 2026-11-11: decisions recorded.** D2 and D5 deferred; D3 and D4 accepted, scoped (the U-04 current-build re-audit passed); D7 undefined. See `DECISIONS_RECORDED.md`, the result files `frontend_u04.json` and `frontend_u06.json`, and `merge_dry_run.json`. The status line below records this report's state when it was written.

**Status: AWAITING PROJECT-OWNER DECISIONS.** This is a read-only investigation.
- **Nothing approved:** no decision is approved here.
- **Nothing changed:** no code, threshold, acceptance record, evidence or `report.json` was changed.
- **Nothing rerun:** no measurement, test or validation was repeated.
- **Analysis only:** the three scripts in this folder re-read existing files only.
- **Build:** algorithm 1.5.0; code `5bf9753f…`, suite `1632af16…`, terrain acceptance `e48eb8ed…`; `report.json` `5e6c76d7…db812e7b`. All unchanged.
- **Already closed:** D1 (V-05 criteria, `../d1_v05_decision_2026-11-11/ACCEPTANCE.md`) and D6 (report regeneration, `../phase4_merge_2026-11-11/`).

## Summary

| Decision | Recommendation | Changes the official report? | Code / suite fingerprint change? | New measurement? |
| --- | --- | --- | --- | --- |
| **D2** V-09/V-10 | **Formally defer** V-09/V-10 for the hackathon (measured, not decided). Do not adopt post-hoc criteria. | No | No | No |
| **D3** U-06 | **Adopt the published Core Web Vitals "good" limits (LCP, CLS, INP) plus a no-leak rule**, scoped to the tested laptop and profiles, and register U-06 | Yes, U-06 → passed (after a merge) | No (docs-side result file) | No |
| **D4** U-04 | **Accept the scoped PASS on condition that the existing live audit is re-run on the current build** (`npm run audit:a11y`), then register U-04 | Yes, U-04 → passed (after a merge) | No (docs-side result file) | One audit re-run (existing script) |
| **D5** IB-5 | **Approve a formal, conditional deferral** that restricts distribution until the listed items are resolved | No | No | No |
| **D7** A15 | **Record A15 formally as "undefined, no scope, not a Phase 4 deliverable"** unless the owner supplies its definition | No | No | No |

**Label consequences** (`label_projection.py`/`.log`, using the engine's own `compute_labels` on the live report):
- **D3 + D4 together are the only decisions that move labels.** With U-04 and U-06 passed:
  - `sun_earth_azel` becomes **Validated** everywhere (V-01 to V-04 and V-02a–e already pass);
  - `horizon` becomes Validated on the status page. In analysis results that carry horizon sigma it stays Pending, because of the uncalibrated L_corr assumption.
- **D2 is needed for the rest:** `disk_visibility`, `events` and `power_indicator` stay Pending until D2 passes V-09 and V-10.
- **Approving D3 and D4 is therefore a decision to show "Validated" labels in the product.**

---

## D2: V-09 / V-10 acceptance criteria

### Existing evidence
- **Final run:** `../v09_v10_final_2026-11-10/v09_v10.json` (2026-11-10).
  - Current fingerprints; terrain gate met; already merged as "not run".
  - 200 stratified points per map over 85–90°S, 18.6 years hourly; observer at 0 m; registered 5/20/80/240 m terrain; 0 inconclusive.
- **Method and diagnostics:** `../v09_v10_a10_2026-11-10/README.md`.
- **Reference (documented from the PDS3 labels):**
  - LOLA AVGVISIB is the fraction of hourly timesteps over 18.6 years in which **any part** of the disc is visible (DN × 0.00004);
  - 60 m grid, from LDEM_85S_060M;
  - the Earth product uses the same rule as PGDA 69.
- **Undocumented:** the **observer height** (assumed 0 m) and the start epoch (effect ≤ 0.35 pp, negligible).
- **Provisional criteria:** RMSE ≤ 5 pp and abs(bias) ≤ 2 pp (`CRITERIA["approved"] = False` in `validation/v09_v10_avgvisib.py`). They are marked "provisional thresholds (README/blueprint)"; no approval is recorded.

**Results** (re-derived from the stored points, `d2_strata.py`/`.log`; identical to the recorded metrics):

| | RMSE | Bias | Max abs(d) | abs(d) ≤ 5 pp | Provisional criteria |
| --- | --- | --- | --- | --- | --- |
| **V-09 (Sun)** | **14.09 pp** | **−7.19 pp** | 53.09 pp | 136/200 | **Not met** (both RMSE and bias) |
| **V-10 (Earth)** | **3.13 pp** | **−0.74 pp** | 22.27 pp | 189/200 | **Met** |

**By reference stratum** (RMSE / bias, pp):

| Stratum | V-09 | V-10 |
| --- | --- | --- |
| [0, 0.2] | 1.05 / −0.29 (46) | 2.81 / −0.74 (40) |
| [0.2, 0.4] | 5.42 / −1.65 (45) | 4.89 / −1.89 (40) |
| [0.4, 0.6] | 3.43 / −1.26 (45) | 0.64 / −0.04 (40) |
| [0.6, 0.8] | **20.87 / −16.59** (45) | 2.17 / −0.46 (40) |
| [0.8, 1.0] | **30.97 / −28.78** (19) | 3.47 / −0.59 (40) |
| reference < 0.6 | 3.74 / −1.06 (136) | 3.28 / −0.89 (120) |

### Why V-09 does not meet the provisional limits
- **Where it fails:** entirely in the two brightest strata (reference > 0.6), where LUNA-OPS predicts **less** sunlight than AVGVISIB (bias −17 to −29 pp). Below 0.6, V-09 is within both provisional limits.
- **Observer height drives it.**
  - **What A10 measured:** the A10 diagnostics, on the preliminary run, showed the mean difference at the 36 worst V-09 points moving from −14.9 pp at 0 m to +1.5 pp at 2 m and +8.1 pp at 10 m.
  - **What that suggests:** the reference behaves like a small height above the surface. That is an observation, not a determination, and it was not re-measured on the final terrain.
- **The reference is spatially rough:** a median 39 pp variation within ±60 m (3 × 3 pixels) at those points. The 0 m value lay inside that local range at 33 of 36 points.
- **Why V-10 is better behaved:** Earth sits near the horizon at nearly fixed azimuths, and its bright strata do not show the same height sensitivity at scale.

### Options

| Option | What it means | Consequences |
| --- | --- | --- |
| **A. Approve the provisional criteria as they are** | RMSE ≤ 5 pp, abs(bias) ≤ 2 pp over all strata | **V-09 FAILS and V-10 PASSES.** Recording either requires setting `CRITERIA["approved"]` in `backend/validation`, which changes the suite fingerprint: every external validation (V-04/05, V-09 to V-14) and the full suite must be rerun, including the long terrain runs. A recorded scientific FAIL for V-09. Labels unchanged (`disk_visibility`, `events` and `power` still Pending). |
| **B. Approve stratified criteria** | e.g. the limits apply to reference < 0.6; the bright strata are reported but not gated | V-09 3.74 / −1.06 and V-10 3.28 / −0.89 pp would pass. **The criterion is chosen after seeing the results (post hoc)** and needs an explicit scientific justification. Same code and fingerprint cascade as A. |
| **C. Establish AVGVISIB's observer height first** | From Mazarico et al. (2011) or the LOLA team; rerun at that height; then decide criteria set in advance | **A new measurement and external research** (outside the current restrictions). The most defensible scientific outcome. Same cascade once the script changes. |
| **D. Change the comparison method** | e.g. compare against the reference's 3 × 3 neighbourhood range | A methodology change in the script; new run; same cascade |
| **E. Formal deferral (recommended for the hackathon)** | V-09/V-10 recorded as "measured, criteria not decided". Metrics published with the observer-height caveat. | No code or fingerprint change; no rerun. The official report keeps both "not run" (already merged). `disk_visibility`, `events` and `power_indicator` stay Pending. Honest and cheap; C stays the path to closure. |

**Recommendation: E now, with C as the route to closure after the hackathon.**
- **Against A and B:** neither is recommended now. A records a FAIL that is probably caused by an undocumented reference assumption. B tailors the criterion after seeing the data. Both also force a full rerun of every external validation.

**Exact approval required:** *"D2: I approve deferring V-09 and V-10. They remain 'not run' with the published metrics (V-09 RMSE 14.09 pp, bias −7.19 pp; V-10 RMSE 3.13 pp, bias −0.74 pp; observer height 0 m assumed). No criteria are approved. Closure requires establishing AVGVISIB's observer height and approving criteria before a new run."*

**If A or B is chosen instead:** the approval must state the exact criteria, and must accept the code change and the rerun of every external validation.

---

## D3: U-06 performance criteria

### Existing evidence (`../u06_2026-11-11/`, status "BLOCKED (provisional measurements)")
- **No approved criterion exists.** C05 says only "measured performance", and the blueprint's U-06 text is not in the repository.
- **Tested hardware and software:**
  - HP Laptop 15-fd0xxx: Intel Core 5 120U, 15.7 GB RAM, Intel graphics, NVMe;
  - Windows 11;
  - Chrome 157 headless, 1440 × 900;
  - server on loopback with the production kernels and terrain.
- **Profiles:** native; 4× CPU; 4× CPU + 10 Mbit/s with 40 ms latency.
- **Samples:** 3 cold and 2 warm loads per profile, plus one workflow per CPU profile, while other desktop applications were running.

**Final-build results (medians):**

| Metric | native | 4× CPU | 4× CPU + 10 Mbit/s |
| --- | --- | --- | --- |
| FCP = LCP, cold / warm | 180 / 170 ms | 480 / 444 ms | 852 / 540 ms |
| Worst cold FCP (spread) | 192 ms | 632 ms | 1,044 ms |
| CLS | 0 | 0 | 0 |
| TBT, cold / warm | 0 / 0 ms | 410 / 249 ms | 214 / 282 ms |

- **Time-cursor step** (Event Timing, an INP-style measure), median / p95: 16 / 32 ms native, 16 / 40 ms at 4× CPU.
- **Other single-frame interactions:** 3D rotate, mode switch and comparison metric switch take ≤ 32 ms.
- **Data-loading interactions** take longer, timed to completion rather than next paint:
  - cached analysis → result painted: 299 / 632 ms;
  - → 3D data loaded: 675 / 955 ms;
  - 2 × 2 comparison → matrix: about 650 ms.
- **Playback:** 60 fps with 0 long tasks.
- **Memory:** 5 mount/unmount cycles gave +0.3 MB heap, no leak and no WebGL warnings.
- **Bundle:** initial JS 295 KB raw / 93 KB gzip.
- **Backend analysis time (A7, not part of U-06):** Site01 30-day analysis 15.9 s cold, 9.2 s with a cached horizon.

**Open caveat:** the two pathological basemap tiles (zoom 0, and 1/0/1 after the fix) were **blocked** during measurement. Without blocking, every page load starts one slow backend tile render (minutes, GB of memory); the backend fix was recommended but not made.

### Options

| Option | Criteria | Against the existing evidence |
| --- | --- | --- |
| **A. Core Web Vitals "good" limits plus a no-leak rule (recommended)**, scoped to the documented laptop and profiles | **LCP ≤ 2.5 s, CLS ≤ 0.1, INP ≤ 200 ms** (published web.dev "good" thresholds), and heap growth over 5 remount cycles within run-to-run noise with no WebGL context loss | **Met in all three profiles:** worst LCP 1,044 ms, CLS 0, INP-style p95 ≤ 40 ms, +0.3 MB heap. TBT and the data-loading timings are reported, not gated. |
| **B. A plus Lighthouse TBT ≤ 200 ms (lab "good")** | as A, plus TBT | **Not met** at 4× CPU (cold 410 ms, warm 249–282 ms). U-06 would fail unless the TBT profile is limited to native. |
| **C. Regression baseline** | No absolute thresholds; this measurement set becomes the baseline, and future builds must not regress beyond the recorded spread | Met by definition now. It is a regression gate rather than an acceptance criterion and does not say whether performance is good enough. |
| **D. Defer** | U-06 stays "not run" | Every label stays Pending, because U-06 gates every quantity |

**Recommendation: A**, with the following conditions written into the approval:
- **Scope:** lab measurement on the stated laptop, Chrome 157 and the three profiles, with few samples; Core Web Vitals are field (75th-percentile) metrics, so this is an approximation.
- **What INP covers:** INP is evidenced only for the keyboard time-cursor and the single-frame interactions. Data-loading interactions are reported, not gated.
- **Tile caveat:** the measurements excluded the slow basemap tiles. Either accept that, or make the backend tile fix (a code change, which changes the code fingerprint and so requires every result to be regenerated) a condition of U-06.
- **No new thresholds:** none were invented. A uses only the published Web Vitals limits; C is relative.

**Registering U-06 if A is approved:**
- **Who may report it:** `validation/common.OWNERS` already allows `frontend_u06` to report U-06.
- **No producer script exists.** A docs-side generator, kept outside `backend/` so no fingerprint changes, would write `frontend_u06.json` with:
  - `meta = run_meta("frontend_u06")`;
  - `tests = {"U-06": {"status": "passed", "detail": …}}`;
  - the `frontend/dist` hashes and the evidence path.
- **The merge guard does not check the frontend build:** it binds the file to the *backend* fingerprints only, so the frontend build must be recorded in the file and its README.
- **Recording it:** a separately approved `run_validation` merge (about 24 min) with all eligible files.

**Exact approval required:** *"D3: I approve U-06 criteria LCP ≤ 2.5 s, CLS ≤ 0.1, INP ≤ 200 ms and no memory leak over 5 remount cycles, for the tested laptop (Core 5 120U) and the native, 4× CPU and 4× CPU + 10 Mbit/s profiles in Chrome 157, with TBT and data-loading timings reported but not gated, and with the slow basemap tiles excluded [or: on condition that the tile fix is made]. I accept the existing 2026-11-11 measurements and approve writing a `frontend_u06` result file."*

---

## D4: U-04 accessibility (scoped audit)

### Existing evidence (`../u04_2026-11-11/`, final status "PASS (scoped)")
- **Coverage:** all 55 WCAG 2.2 A/AA success criteria assessed; 24 defects found, fixed and re-verified live; no A/AA failure remains in scope.
- **Views:** welcome, Technical and Public result views, sidebar states, Compare, Data, Guide and the top bar, at 320 px and 390 px.
- **Methods:**
  - the browser's accessibility tree;
  - contrast measured on every visible text node (minimum 4.78:1);
  - a real Tab walk;
  - target size, reflow and text spacing;
  - functional keyboard and pointer tests.
- **Regression checks:** `check-a11y.mjs` gates `npm test` and the build.
- **Limits:**
  - no assistive-technology user session (NVDA, JAWS, VoiceOver, Narrator, TalkBack);
  - one engine (Chromium 157);
  - zoom emulated through the viewport;
  - speech input not tested;
  - the curated-site list was empty, and backend-failure states were not rendered live.
- **Build gap found in this review:** the live audit ran on the build *before* U-06.
  - U-06 then changed the frontend: lazy-loaded map and 3D panes with "Loading…" placeholders, and the map tile `minZoom`.
  - U-06 states that "the live U-04 browser audit was not rerun for this change" and recommends rerunning `npm run audit:a11y` before release. Only the static accessibility check was run on the final source (15/15, 0 problems).

### Options

| Option | What it means | Consequences |
| --- | --- | --- |
| **A. Accept the scoped PASS as it is** | Sign off the existing evidence with its limits | Fastest. The passed status would describe a build that differs from the current one (U-06 changes not audited live). |
| **B. Accept on condition of a re-run of the existing live audit on the current build (recommended)** | Run `npm run audit:a11y` (an existing script, no installs) against the current `frontend/dist`; accept if it matches the release run (0 A/AA failures) | Closes the build gap at low cost: one audit run on the existing tooling, no code change. If it finds a regression, U-04 stays pending until it is fixed. |
| **C. Require extra human or cross-browser testing** | An NVDA or Narrator spot check and/or Firefox | Removes the main scope limits; needs manual effort and possibly software not installed here |
| **D. Defer** | U-04 stays "not run" | Every label stays Pending |

**Recommendation: B, with C recommended (not required) before any formal WCAG conformance claim.**

**Registering U-04:** the same mechanism as U-06.
- **Who may report it:** `OWNERS["frontend_u04"]` exists.
- **The result file:** a docs-side generator writes `frontend_u04.json` (`meta = run_meta("frontend_u04")`, U-04 `passed`, the scope limits in `detail`, the audit run file and the `frontend/dist` hashes).
- **Recording it:** one approved merge, best done together with U-06 (D3) and V-05 (full `horizons.json`, D1), so the report is regenerated once.

**Consequence of D3 and D4 together:** `sun_earth_azel` becomes Validated in the product, and `horizon` becomes Validated on the status page (see Summary).

**Exact approval required:** *"D4: I accept the U-04 scoped audit (WCAG 2.2 AA; Chromium 157; no assistive-technology user session; viewport-emulated zoom) on condition that `npm run audit:a11y` re-run on the current build reports no A/AA failure, and I approve writing a `frontend_u04` result file with these limitations recorded."*

**For option A:** omit the condition. **For option C:** name the additional tests required.

---

## D5: IB-5 licensing and distribution (formal deferral proposal)

**Source:** only the existing inventory (`../ib5_2026-11-11/`); no further research.

### Unresolved items
1. **44 of 49 vendored native binaries ship no licence text:**
   - rasterio ×34 (e.g. OpenSSL 3.6.1, curl, libpq, libxml2, LibTIFF, SQLite, HDF5, netCDF, GEOS, PCRE2);
   - pyproj ×7;
   - `msvcp140` ×2 (numpy, llvmlite);
   - CSPICE in SpiceyPy.
2. **Data terms not confirmed:**
   - PGDA 78/81/90 and PGDA 69;
   - PDS/LROC (the 2026-11-07 statement not re-verified);
   - JPL Horizons outputs;
   - the NAIF general statement;
   - the USGS release `Use_Constraints` (data not registered);
   - ShadowCam (unused).
3. **`lerc@3.0.0`:** no licence file (Apache-2.0 declared; not shipped in the bundle).
4. **GSFC acknowledgment:** whether it covers the per-eclipse PDF figures is not stated.

### Distribution risks (still present; checked read-only today)
- **The browser bundle drops licence notices:**
  - `frontend/dist` keeps licence comments only for React and three.js, so the notices of 21 other shipped packages are missing;
  - `dist` contains no licence or notice file (checked).
- **The Archivo font's OFL-1.1 text is not shipped** (OFL condition 2).
- **The reference rasters are not git-ignored:**
  - `data/reference_validation/` (256 MB; PGDA LPSR, PDS AVGVISIB and LROC rasters with unresolved terms) is **not git-ignored** (checked `.gitignore`);
  - a routine `git add` would commit it, and one 154 MB file exceeds GitHub's 100 MB limit.
- **Committed third-party evidence:**
  - Horizons responses: 47 in each of the A8/A9 and refresh folders;
  - GSFC pages and PDFs: in the A13 and refresh folders;
  - their redistribution terms are not confirmed beyond the GSFC acknowledgment.
- **Python wheels:** not redistributed by the repository (it ships `requirements.txt`). Item 1 matters only if the environment is packaged (container, installer).

### Proposed formal deferral (for approval)
- **Deferred:** items 1–4 above, until after the hackathon.
- **Interim conditions** (proposed; the owner selects):
  1. **No redistribution** of a packaged Python environment (container or installer) or of `data/reference_validation/` until items 1–2 are resolved.
  2. **`frontend/dist`:** before `frontend/dist` is published or hosted, add a generated third-party notices file and `OFL.txt`. This is a build or frontend change needing its own approval.
  3. **`.gitignore`:** add `data/reference_validation/*` before any commit that could include it. This is a repository change needing approval.
  4. **Committed Horizons and GSFC evidence:** keep it as validation evidence with the GSFC acknowledgment in `ATTRIBUTION.md` (already present). Re-confirm Horizons terms before any separate data release.
- **Conditions for resolution:** for each item, an upstream licence text for the exact version, or a published terms statement, recorded in `ATTRIBUTION.md` and the IB-5 inventory. The owner signs off when all items are closed.
- **Consequences:**
  - No effect on validation, labels, fingerprints or `report.json`.
  - The repository source can be shared under Apache-2.0 with `ATTRIBUTION.md`.
  - The risks above remain until the conditions are met.

**Exact approval required:** *"D5: I formally defer IB-5 items 1–4 (vendored-binary licences, data terms, lerc, GSFC figure coverage) until after the hackathon, under interim conditions [list 1–4 or a subset], and accept the stated distribution risks until they are resolved."*

---

## D7: A15

### Search of authoritative project records (read-only)
- **Searched:** every text file in the repository (excluding dependencies, data and builds) for `A15`, `A-15`, `Task 15` and `A1–A15`.
- **The only independent mention:** `docs/validation_evidence/c10_2026-11-11/README.md` line 125, *"…left for the final A1–A15 traceability update"*. It names a range, not a task.
- **Other mentions:** all the rest were written by the closure review itself (TRACEABILITY, AUDIT, README, closure README), recording that A15 is undefined.
- **No task definition is recorded:** the A1–A14 scopes come from the evidence folders and AUDIT sections, and none defines A15.
- **The Phase 1.1 blueprint**, the presumed source of the A-numbering, is not in the repository.
- **Git history was not searched** (no Git operations).

### Options

| Option | What it means |
| --- | --- |
| **A. Record A15 as formally undefined (recommended unless the owner has a definition)** | A one-line decision: "A15 has no defined scope in project records; no task, deliverable or acceptance is assigned; it is not a Phase 4 completion criterion." The register shows A15 as "Undefined (owner decision)" instead of "open". |
| **B. Owner supplies the definition** | The owner states A15's scope from the blueprint or the plan. It is then added to the register with its own status and evidence, and may become new work. |
| **C. Treat the "A1–A15 traceability update" as A15** | Name the closure documentation task (already done: closure, merge and D1 records) as A15 and mark it complete. **Not recommended** without the owner's confirmation, because it would assign scope that no record states. |

**Exact approval required (option A):** *"D7: A15 has no defined scope in any project record. I record it as undefined: no task, deliverable or acceptance is assigned, and it is not a criterion for Phase 4 completion."*

**For option B:** the owner provides the scope text.

---

## What would follow approval (each step needs its own go-ahead)
1. **Documentation-only steps:** acceptance or deferral records for D2, D5 and D7; register updates.
2. **D4 (if B):** one run of `npm run audit:a11y` on the current build.
3. **Result files:** docs-side `frontend_u04.json` and `frontend_u06.json`, with no `backend/` changes.
4. **Merge:** one approved `run_validation` merge with:
   - V-09/V-10, V-11 and V-12;
   - the **full** `horizons.json` (V-04 and V-05, D1);
   - V-13 and V-14;
   - `frontend_u04.json` and `frontend_u06.json`.
5. **Documentation sync.** Phase 4 can only be declared complete once the owner accepts the D2 deferral and the D5 deferral as satisfying Phase 4.

## Files in this folder
| File | Contents |
| --- | --- |
| `README.md` | This report |
| `d2_strata.py` / `.log` | V-09/V-10 metrics re-derived per stratum from the stored final points |
| `label_projection.py` / `.log` | Hypothetical label outcomes with the engine's own rule (in memory) |
| `SHA256SUMS` | Checksums |
