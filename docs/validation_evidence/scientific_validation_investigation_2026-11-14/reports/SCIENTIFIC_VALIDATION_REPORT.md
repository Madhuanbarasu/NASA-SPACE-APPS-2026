# LUNA-OPS 2.0: scientific validation investigation of five items (2026-11-14)

**Scope.** This is a focused investigation of V-09, V-10, Earth-disk visibility, geometric event detection and the estimated power indicator. It is not the Phase 7 suite.

**Nothing in the engine was changed:**
- code fingerprint `84cbd4ea…`, suite fingerprint `1632af16…`, `report.json` `8c03ebaf…` and `tiles.py` are all unchanged (`../logs/09_integrity_after.txt`);
- no dataset, terrain file, cache entry or earlier evidence was modified or deleted;
- no threshold or label was changed, and no criterion was approved.

**One core-engine correction is proposed for approval** (section 4.5). It was not implemented.

**Cache counts:** the cache grew from 78 to 80 results and from 27 to 29 indexed horizons during this session. The additions were created at 2026-11-14 01:51–01:53 UTC for sites none of these scripts used, and are consistent with someone using the running app. This investigation wrote nothing to the cache: its scripts open it read only, or call `compute_horizon`, which does not cache. The audit's 74 results are all present.

## Summary

| Item | Original status | Status after this investigation | Key finding |
|---|---|---|---|
| **V-09** LOLA average illumination | Not run (criteria provisional) | **Investigated** (no Pass/Fail: criteria not approved) | No implementation defect found. The 14.09 pp RMSE / −7.19 pp bias come from (a) a near-field and observer-height definition difference at the brightest ridge and rim points, and (b) equal-per-stratum sampling that gives 32 % of the points to 0.007 % of the area. Where the reference is spatially smooth: RMSE 1.15 pp, bias −0.34 pp. Area-weighted: 3.77 / −0.97. |
| **V-10** LOLA average Earth visibility | Not run (criteria provisional) | **Investigated** | Same mechanism at a few crater-floor points where Earth grazes the terrain. 10 points carry 93 % of the squared error. Smooth subset: RMSE 1.04 pp, bias −0.19 pp. |
| **Earth-disk visibility** | Pending validation (Geometric) | **Pending validation**, with strong independent evidence | An independent spheroid ray-cast agrees on all 23 comparable cases: visible fraction within 1.4e-4 (limited by the reference grid), edges within the grid × horizon slope, and any/centre/full verdicts identical. No defect found. |
| **Event detection** | Pending validation (Geometric) | **Pending validation; a confirmed defect blocks validation** | Timing is correct: every window edge within 0.5 s, including windows of 8.8 s and windows at the analysis start and end. **Defect:** time during which a disk rests on incomplete (lower-bound) horizon bins is not always reported as unknown. One real 30-day result reports 37.3 h as visible that should be unknown. The fix is inside `backend/lunaops`, so it is proposed, not made. |
| **Power indicator** | Pending validation (Estimated) | **Pending validation**; implementation verified exactly | It is a dimensionless solar-availability indicator, not RF and not electrical output. All 240 stored series and metrics (80 results × 3 panel models) reproduce independently; 14/14 edge cases behave as defined; the UI matches the backend. Its usefulness as an estimate of power is not validated against any measured data. |

No item is **Validated** and none is **Failed**: the only quantitative criteria (V-09/V-10) are unapproved, and no other approved criterion was missed.

---

## 1. V-09: LOLA average illumination

**Original status:**
- The existing result reads "not run": 200/200 points scored, RMSE 14.09 pp, bias −7.19 pp, maximum 53.09 pp.
- The criteria (RMSE ≤ 5 pp, |bias| ≤ 2 pp) are provisional and unapproved.

**Implementation:**
- `backend/validation/v09_v10_avgvisib.py`:
  - `stratified_points` selects the points;
  - `track` gives the hourly Sun and Earth positions from the Moon's centre over 18.6 years (163,048 epochs);
  - `visible_any` applies the engine's "any part of the disc" rule. It uses `disk_edges_many`, routes ambiguous hours to the engine's `full_state`, and includes Earth occulting the Sun;
  - `evaluate_point` computes the horizon with `compute_horizon` at observer height 0 m.
- The run used here is the 2026-11-12 run under the current engine (`../../backend_tiles_and_ui_fixes_2026-11-12/validation/v09_v10.json`, code `84cbd4ea…`). It is identical to the 2026-11-10 run.

**Scientific definition:**
- AVGVISIB's value is "the percentage of timesteps where each pixel was sunlit (by any fraction of the solar disc)", averaged over hourly timesteps spanning 18.6 years.
- The source is the PDS label `avgvisib_85s_060m_201608.lbl` and PGDA 69, recorded in A10 (`../../v09_v10_a10_2026-11-10/README.md`).

**Reference data and provenance:**
- LOLA `AVGVISIB_85S_060M_201608.IMG`: PDS Geosciences node, `lrolol_1xxx/extras/illumination/img/`; SHA-256 recorded in `backend/validation/reference/avgvisib/provenance.json`.
- Format: 5058 × 5058, 60 m polar stereographic, DN × 0.00004.
- Derived from LDEM_85S_060M (LOLA data 2009–2013).
- **Not documented by the reference:** observer height and start epoch. These are recorded assumptions: 0 m and 2026-01-01.

**Point selection:**
- 5 equal-width strata of the reference value, 40 points each, seeded and deterministic, shortfall reallocated.
- For V-09 the strata contain 9,603,791 / 8,529,795 / 1,940,619 / **1,460 / 19** pixels, and 46/45/45/**45/19** points were drawn.

**Investigation performed:**
1. **Statistics reproduced independently** from the per-point data with numpy, not the script's code: RMSE 14.09, bias −7.19, maximum 53.09 (`../logs/01_avgvisib_residuals.log`; per-point table `../V09_illumination/per_point_residuals.csv`).
2. **Where the error is:**

   | Stratum | n | RMSE | Bias |
   |---|---|---|---|
   | [0, 0.2] | 46 | 1.05 | −0.29 |
   | [0.2, 0.4] | 45 | 5.42 | −1.65 |
   | [0.4, 0.6] | 45 | 3.43 | −1.26 |
   | [0.6, 0.8] | 45 | **20.87** | **−16.59** |
   | [0.8, 1.0] | 19 | **30.97** | **−28.78** |

   - **One-sided:** all 64 points with |d| > 5 pp are too dark.
   - **Concentrated:** the worst 20 points carry 74 % of the squared error.
   - **Location-dependent, not time-dependent:** the residual correlates with the reference's own ±60 m variability (Spearman +0.85 on |d|), with ground height (−0.47) and with the reference value (−0.69).
   - **The worst points** are high ridges and rims near the pole, including the Site01 / Shackleton-rim area, where the Sun stays within about 1.5° of the horizon all year.
3. **Controlled experiment, 15 points** (10 worst, 5 controls). Same points, same hourly geometry, same scoring; only the horizon input varies. Script `../scripts/avgvisib_experiment.py`; results `../independent_checks/avgvisib_experiment.json`; log `../logs/02_avgvisib_experiment.log`.
   - **Reproduction:** the stored value reproduced exactly at all 15 points (A).

   | Variant | Worst 10: RMSE / bias | Controls: RMSE / bias |
   |---|---|---|
   | A: engine horizon, observer 0 m (as benchmarked) | 43.91 / −43.56 | 1.12 / −0.69 |
   | B: engine horizon, observer 2 m | **7.55 / −0.37** | 3.10 / +1.72 |
   | C: near field (to 40 km) from the 20 m LOLA product averaged to **60 m** (AVGVISIB's pixel size), 0 m | 22.56 / −21.42 | 11.67 / −6.55 |

   - **Example:** the worst point (−89.872°, 211.115° E) gives reference 65.1 %, A 12.0 %, B 70.1 %, C 57.9 %.
4. **Earlier, unchanged findings** (A10):
   - moving the 18.6-year start to 2009-07-13 changes results by ≤ 0.35 pp;
   - the hourly geometry agrees with the engine's per-site computation to 1.7e-6° (Sun);
   - the vectorised verdicts agree with the event detector (7,156 epochs, 0 mismatches).

**Root cause of the discrepancy.** A combination of factors, with no implementation defect found:
- **(a) Observer-point definition at grazing Sun:**
  - at 0 m on the bilinear DEM surface, the near-field horizon is the DEM's own local slope. The engine flags these bins as `near_field`;
  - with the Sun under 1.5°, a few metres of micro-relief decide visibility, so +2 m changes the worst points by about +40 pp;
  - AVGVISIB behaves much more like an elevated observer, or a smoother near field, at these points. Its true height and method are **undocumented**, so this cannot be resolved from the available evidence.
- **(b) Different terrain:** the reference used LDEM_85S_060M (2016); the engine uses PGDA 90 20/80/240 m and PGDA 78 5 m (Site01). The 60 m experiment shows resolution alone explains about half of the worst-point error, and that it worsens points that already agree. So resolution is not the whole story.
- **(c) The reference's own spatial roughness:** the median of its 3 × 3 range (±60 m) is 5.6 pp, and the 90th percentile 42.7 pp. 168 of the 200 computed values lie within that range.
- **(d) Benchmark weighting:** equal points per stratum make the summary RMSE a statistic of the rare bright extremes. Area-weighted, it is **3.77 pp, bias −0.97 pp** (`../logs/08_area_weighted.log`).
- **(e) Where the comparison is well posed** (reference 3 × 3 range ≤ 5 pp, 90 points): **RMSE 1.15 pp, bias −0.34 pp** (`../logs/06_smooth_subsets.log`).

**Corrections made:** none. No defect was found, and tuning the observer height to the benchmark was explicitly not done.

**Remaining limitations:**
- **Observer height:** AVGVISIB's observer height and near-field treatment are unknown. Mazarico et al. (2011) and the LOLA team were not consulted (not reachable here).
- **Experiment size:** run on 15 of the 200 points, not all of them.
- **LDEM_85S_060M itself** was not used. That would isolate the method from the data.

**Recommended next steps:**
1. **Establish the reference's observer height and near-field method** from Mazarico et al. 2011 or the LOLA team.
2. **Optionally**, rerun V-09 using LDEM_85S_060M for the horizon (one extra PDS download, about 0.1 GB) to separate data from method.
3. **Decide the criteria** (section 6).

## 2. V-10: LOLA average Earth visibility

**Original status:** not run. RMSE 3.13 pp, bias −0.74 pp, maximum 22.27 pp; criteria provisional.

**Implementation:** the same script. Earth's oblate silhouette is bracketed by circles of radius asin(b/d) and asin(a/d); ambiguous hours are routed to the engine's exact limb.

**Definition:**
- The reference value is "any part of the Earth disc" (`AVGVISIB_85S_060M_201608_EARTH`).
- PGDA 69: Earth is "considered visible if any part of its disc is not obscured".
- **Same definition in the engine:** both use the "any" rule, not the centre. The UI's default direct-to-Earth rule is "centre", which is a different, documented quantity.

**Frames and time:**
- DE421 mean-Earth (reference) against DE440 Moon ME (engine); the frame difference is negligible at this scale (V-01–V-05).
- Hourly sampling over 18.6 years; start-epoch effect ≤ 0.27 pp (A10).

**Investigation performed:**
- **Statistics reproduced exactly.** 10 points carry 92.6 % of the squared error. Without them: RMSE 0.87, bias −0.13.
- **Where the large errors are:** the 11 points with |d| > 5 pp are all negative, and most are crater floors 2–3 km below the reference sphere (for example −85.035°, 144.319° E: reference 26.18 %, computed 3.91 %).
- **Experiment** (6 worst, 4 controls):

  | Variant | Worst 6: RMSE / bias | Controls: RMSE / bias |
  |---|---|---|
  | A: 0 m | 16.07 / −15.50 | 0.01 / −0.01 |
  | B: 2 m | 4.60 / **+3.85** | 0.04 / +0.02 |
  | C: 60 m near field | 8.60 / −7.43 | 0.01 / 0.00 |

**Why the average is good but individual points differ:**
- Earth stands higher above the horizon than the Sun in most of the domain, so most points are insensitive to the near field (controls agree to 0.01 pp).
- At the few points where Earth grazes nearby terrain, the same near-field and observer-height definition dominates.
- At 2 m these points overshoot (bias +3.85), so no single height reconciles them. That is consistent with a combined resolution and definition difference rather than a height offset.

**Smooth subset** (160 points): RMSE 1.04 pp, bias −0.19 pp.

**Root cause:** different near-field and observer definitions together with terrain differences, at a few grazing points. No genuine calculation error was found.

**Corrections:** none. Limitations and next steps are as for V-09.

## 3. Earth-disk visibility (Geometric, Pending validation)

**Implementation:**
- `backend/lunaops/engine/earth.py`, `earth_disk_state`:
  - Earth is the IERS 2010 oblate spheroid with the pole of date;
  - the exact limb is a 3-D ellipse `q(t) = Q0 + cos t QA + sin t QB` (`limb_ellipse`);
  - edge clearances `g_top` / `g_bot` come from extrema of el(t) − H(az(t)) along the limb (Brent's method);
  - the visible solid-angle fraction `f` comes from azimuth strips;
  - the centre clearance `c` = el_c − H(az_c).
- **Sun:** `visibility.disk_state`, an exact spherical cap in closed form.
- **Rules:** any = f > 0; centre = c ≥ 0; full = g_bot ≥ margin.
- **Missing terrain:** incomplete bins are lower bounds. A hidden verdict over them stands; anything visible becomes unknown.

**Independent verification** (`../scripts/disk_independent.py`, `../disk_visibility/disk_independent.json`, `../logs/03_disk_independent.log`):
- **The reference shares no engine geometry.** It ray-casts a gnomonic grid of view directions against the spheroid by quadratic intersection, or against the cap for the Sun, and compares each direction's elevation with the horizon.
- **Grid sizes:**
  - partial cases on a 3201² grid (5.9e-4° step), checked against a 1601² grid for convergence;
  - grazing cases with a 1201² grid zoomed onto the top edge (about 1e-5° step);
  - the top-edge position itself found independently.
- **Cases:** fully visible; fully blocked; half; partial (upper part); crater wall (horizon slope 0.8°/°); jagged random horizon; below the local horizontal but above a lower terrain horizon (peak site); below both; grazing sliver visible / just hidden (±0.002° from the top edge); missing terrain under a visible part; missing terrain under a blocked part; perigee; apogee with the pole along the line of sight. Each for Earth and Sun where meaningful.

**Results:**
- **Verdicts:** all 23 comparable cases give identical any/centre/full verdicts.
- **Visible fraction:** |Δf| ≤ 1.4e-4. The differences shrink with the reference grid (Sun half case: 0.49959 at 1601², 0.49980 at 3201², engine 0.49993).
- **Edge clearances:** |Δg| ≤ 1e-3° in smooth cases. On the jagged horizon it is 4.7e-3°: the reference grid step times the horizon slope of about 8°/°, and the engine's value is the more extreme one, as expected of an exact optimiser.
- **Grazing sliver:** the engine gives f = 5.9e-5 with g_top = +0.00203°; the independent zoom gives g_top = +0.00200°.
- **Peak site:** a disk below 0° but above the terrain horizon is correctly visible; there is no clipping at the local horizontal.
- **Missing terrain:** a visible part over missing terrain is reported unknown, and a blocking lower bound is reported hidden, as documented.

**Defects:** none found in the disk calculation.

**Limitations:**
- The cases are synthetic geometries at Earth–Moon distances. The real-ephemeris path is covered by V-01–V-08 and V-13 (passed).
- Oblateness effects are small (about 3e-3°) and were included, not isolated.

**Status:** Pending validation. The evidence is strong, but the label requires the engine's own gates (U-04 and U-06 not run) and an approved acceptance tolerance.

**Recommended:** adopt this ray-cast as a regression test, with a tolerance on f of 5e-4, on edges of grid step × (1 + slope), and on verdicts of exact equality away from ±1e-3° grazing.

## 4. Geometric event detection (Geometric, Pending validation)

**Implementation:**
- `backend/lunaops/engine/events.py`, `EventDetector.run`: adaptive steps from 1 s to 600 s, governed by rigorous rate and curvature bounds on the event functions (Sun and Earth centre, top edge, bottom edge, Earth occultation), with bisection to 1 s.
- `build_intervals`: cuts the window at events and evaluates the state at each segment's midpoint (`full_state`).
- `summarize`: unknown time is never counted as on or off.

**Existing evidence:**
- **V-14 (passed):** a full synodic month at 3 sites against a 1-second brute force. 955 window edges ≥ 2 s; 0 missed, 0 spurious; worst 0.5 s.
- **V-13:** eclipses against GSFC.

### 4.1 Independent tests (`../scripts/events_independent.py`, `../event_detection/events_independent.json`, `../logs/04_events_independent.log`)
**Reference:** a fixed 0.5-second scan of the edge function, with each crossing placed by linear interpolation. It uses the engine's ephemeris (validated separately); the event finding is what is independent. The site is Site01's position with synthetic horizons.

| Case | Reference windows (duration) | Matched / missed / spurious | Worst edge error |
|---|---|---|---|
| Short windows: notch clears the top-edge path by 0.2 µdeg, 1, 5, 30, 200 µdeg | 8.8 s, 12.8 s, 25.2 s, 92.0 s, 420.6 s | 5/0/0 | 0.49 s |
| Several windows (five notches) | 4 windows, 143–2235 s | 4/0/0 | 0.46 s |
| Window open at the analysis start | 1 | 1/0/0 | 0.50 s* |
| Window open at the analysis end | 1 | 1/0/0 | 0.50 s* |
| No visibility / always visible | 0 / 1 | exact | — / 0.50 s* |
| Sun-centre rule, notched | 4 windows | 4/0/0 | 0.50 s |
| Uncertain terrain (σ = 0.01°) | 1 (615 s) | 1/0/0, **flagged uncertain** | 0.12 s |

\* 0.5 s is the reference scan's own step at the interval boundary. The detector's boundary edges are the exact interval ends.

**Timing tolerance:** the detector's tolerance is 1 s (`EVENT_TOL_S`, bisection); measured errors are ≤ 0.5 s. The justification for 1 s:
- it is three orders of magnitude finer than the 30-minute display step;
- the edge functions move at 1e-5–1e-4 °/s, so 1 s corresponds to ≤ 1e-4° of clearance, below the horizon's own uncertainty (σ about 1e-3–3e-2°).
- **Recommendation:** keep 1 s as the acceptance tolerance for edge timing and 2 s for durations.
- Windows much shorter than about 2 s are below the 1 s floor; detecting them is not guaranteed and was not claimed.

### 4.2 Confirmed defect: unknown time over incomplete horizon bins
- **The documented rule** (`visibility.py`, `analysis.py` warning): over incomplete bins, which are lower bounds, "anything visible becomes unknown".
- **Synthetic case:** the Sun's disk passes over incomplete bins with a low horizon for 6,782 s. The detector reports all 6,782 s as **visible** and 0 s unknown.
- **Real cached results** (`../scripts/incomplete_bins_check.py`, `../event_detection/incomplete_bins_real_results.json`, `../logs/05_incomplete_bins_real.log`):
  - 5 of 80 cached results use a horizon with incomplete bins.
  - The 30-day result `a667129a…` (−60.48°, 266.97° E, 19 % incomplete bins) had 8,404 minutes where the Sun's disk was over incomplete bins and cleared them. It reported 6,166 of those minutes as unknown and **2,238 minutes (37.3 h) as visible**. It also reported about 1,400 minutes as unknown that a minute-by-minute check does not require.
  - The four 1-day results at −60.02° report Earth unknown for the whole day, which is correct there.
- **Root cause:**
  - entering or leaving incomplete bins is not an event function (`FUNCS`), so `build_intervals` does not cut there;
  - each segment's state comes from its midpoint (`full_state` at `0.5 * (a + b)`);
  - a segment that only partly overlaps incomplete bins therefore takes one state for its whole length.
- **Affected outputs:** the unknown, visible and hidden totals and the window lists of sites whose horizon has incomplete bins. Only terrain-coverage edges produce these; sites with complete horizons are unaffected.
- **Unaffected:** the power indicator, mean Sun fraction and series. They use per-sample states (NaN where unknown); the reproduction in section 5 confirms their unknown placement.

### 4.3 Proposed core-engine correction (NOT implemented; approval required)
- **Files and functions:**
  - `backend/lunaops/engine/events.py`: `build_intervals`, and either `EventDetector.run` or a new helper;
  - possibly `visibility.HorizonProfile`, to add a helper listing runs of incomplete bins.
- **Change:**
  - for each target, compute the times at which the disk's azimuth span [az − hw, az + hw] enters or leaves a run of incomplete bins, from the detector's samples refined by bisection to 1 s, as for the other events;
  - add them as cuts in `build_intervals`, so every segment is homogeneous with respect to incompleteness and its midpoint state is valid for the whole segment;
  - no change to geometry, horizons or disk calculations.
- **Why it is necessary:** without it, unknown time can be reported as visible. That contradicts the engine's own rule and the C08 "never fill unknown" principle.
- **Effect on fingerprints and caches:**
  - the code fingerprint changes, so every label loses Validated until `report.json` is regenerated;
  - result IDs and horizon cache keys contain the fingerprint, so all cached results (80) and horizons (29) become stale and are recomputed on request;
  - numerical results change only for sites with incomplete horizon bins.
- **Regression tests and new baseline:**
  - this investigation's synthetic case: expect 6,782 ± 2 s unknown and 0 s visible over incomplete bins;
  - real case `a667129a`: expect 0 minutes reported visible where the disk rests on incomplete bins, and no unknown time where it does not;
  - V-14 full and V-13 unchanged;
  - V-09/V-10 unchanged (complete horizons only);
  - the full automated suite;
  - regeneration of the validation report under a new fingerprint, with the owner's approval.

**Status:** Pending validation. Timing is verified, but the confirmed unknown-handling defect blocks validation until a correction is approved and implemented.

## 5. Estimated power indicator (Estimated, Pending validation)

**What it is:**
- **Formula:** `backend/lunaops/engine/power.py`: P_rel(t) = f_sun(t) × (1 au / r_sun(t))² × k(t).
  - f_sun is the visible fraction of the solar disk, after terrain and Earth occultation;
  - r_sun is the Sun's distance from the site;
  - k is the cosine of incidence for a named reference panel: vertical tracking cos el (default), horizontal max(0, sin el), or fixed vertical cos el · max(0, cos Δaz).
- **Meaning:** dimensionless; 1.0 means full Sun at 1 au at normal incidence. It is a relative estimate of available sunlight.
- **Not:** electrical output. Efficiency, temperature and storage are out of scope (extension D02).
- **Window metrics:** mean over known time and equivalent full-Sun hours, using known intervals only (`window_metrics`). A limb-darkened companion `P_rel_LD` is reported beside it.
- **Inputs:** the panel model and the panel azimuth. There are **no hardware parameters**, so none can be defaulted.
- **Label:** "Estimated / Pending validation", never shown as measured.

**Trace:**
- `analysis.py:207–212` builds the series and metrics for all three models.
- `summary.power` and `mean_sun_fraction` go to `ResultWorkspace`.
- **UI check** (audit screenshot `../../pre_phase7_audit_2026-11-14/browser_run2/screenshots/layout-1920-site.png`, result `976a3d8f…`): the backend has power 0.5386, 387.81 h, mean visible Sun 0.52369 and Sunlight 55.54 %. The UI shows 0.539, "16 d 3 h", 52.4 % and 55.5 %.
  - **Presentation note:** 387.81 h = 16 d 3.8 h is shown truncated as "16 d 3 h", not rounded.

**Independent verification** (`../scripts/power_independent.py`, `../power_indicator/power_independent.json`, `../logs/07_power_independent.log`):
- **Series:** all 240 (80 results × 3 panel models) recomputed from the stored f, distance, azimuth and elevation with formulas written independently. The largest difference is 9.6e-6, the rounding of the stored series.
- **Unknown samples:** placed identically in every series.
- **Metrics:** recomputed by an independent trapezoid. Mean within 4.2e-8, equivalent full-Sun hours within 1.2e-5 h, coverage within 5e-11. Results with unknown time are flagged `lower_bound`.
- **Edge cases, 14/14 as defined:**
  - f = 0 gives 0, and NaN stays NaN;
  - 1 au at 0° on a vertical panel gives 1;
  - (1/0.983)² scaling at 0.983 au;
  - a horizontal panel with the Sun below 0° gives 0;
  - a fixed panel with the Sun behind it gives 0, and at 60° off normal gives 0.5;
  - all samples unknown gives mean None;
  - an isolated known sample adds no time;
  - an unknown panel model is refused.
- **Units:** dimensionless throughout. The au is 149,597,870.7 km (IAU 2012).
- **Not clamped:** `p_rel` does not clamp f. Its input is the disk fraction (0–1 or NaN), never user input.

**RF quantities:**
- They are not part of the power indicator.
- They live in the Communication link budget (`backend/lunaops_comms/linkbudget.py`, Phase 6, 57 tests).
- **Hand-worked check:** Pt 20 W, Gt 20 dBi, Gr 60 dBi, Ts 50 K, 8.45 GHz, 1 Mbit/s, 384,400 km: FSPL 222.6806 dB, EIRP 32.0103 dBW, Pr −134.6703 dBW, C/N0 76.9392 dB-Hz, Eb/N0 16.9392 dB, margin 14.4392 dB, C/N 13.9289 dB. The difference from the evaluator is **0.0**.
- **No invented values:** a missing noise temperature stops the chain from C/N0 onwards, and a data rate of 0 is refused as invalid.
- **RF-feasible indications:** shown only for an evaluated margin. The engine itself labels results "geometric, not radio".

**Defects:** none in the power indicator. The incomplete-bin defect (section 4) does not affect it, because it uses per-sample states.

**Limitations:**
- The indicator's physical adequacy as a power estimate is unvalidated. There is no measured-power dataset, and it inherits f_sun, so its accuracy is that of disk visibility and the terrain.
- Uncertainty is not propagated into the indicator.

**Status:** Pending validation; implementation verified.

**Next:** decide what "validated" means for an Estimated quantity. For example: definition verified; an independent benchmark against a published illumination–power study at one site; uncertainty propagated from the horizon σ.

## 6. Validation criteria (Part G): recommendations only, none approved
The provisional V-09/V-10 criteria (RMSE ≤ 5 pp, |bias| ≤ 2 pp over the 200 equal-per-stratum points) stay **provisional**.

**Why they are not well posed as they stand:**
1. **Weighting:** equal-per-stratum RMSE is dominated by 0.007 % of the area (V-09).
2. **The reference varies by up to 85 pp within ±60 m** at exactly those points. That exceeds any sensible tolerance, and reflects positional uncertainty: LOLA geolocation is of order tens of metres, and the pixel is 60 m.
3. **Undocumented reference definition:** observer height and near-field method change bright points by about 40 pp per 2 m.
4. **Different terrain products and epochs** (2016 LDEM against PGDA 90/78).
5. **Not limiting:** time sampling (≤ 0.35 pp) and geometry (≤ 2e-5°).

**Recommended criteria (for the owner's decision):**
- **(R1) Well-posed subset:** points whose reference 3 × 3 range is ≤ 5 pp. Proposed: RMSE ≤ 2 pp and |bias| ≤ 1 pp. The tolerance covers hourly sampling, epoch and DEM-version effects. Current values: V-09 1.15 / −0.34, V-10 1.04 / −0.19.
- **(R2) Map-level accuracy:** area-weighted RMSE ≤ 5 pp and |bias| ≤ 2 pp, the provisional numbers applied to the statistic they plausibly intended. Current: V-09 3.77 / −0.97, V-10 3.28 / −0.90.
- **(R3) All points reported, not gated:** the fraction of computed values within the reference's own 3 × 3 range (currently V-09 84 %, V-10 78.5 %), and the bright-point residuals with the near-field caveat.
- **Prerequisite:** confirm AVGVISIB's observer height. If it is not 0 m, rerun at that height before applying any criterion.

**Caution:** R1 and R2 were formulated after seeing these data. They are argued from the reference's resolution and sampling design, not from the results, but approving them carries that circularity risk. An alternative is to fix the criteria first and run a fresh, independently drawn point set.

## 7. Checklist
| Workstream | Reproduced | Definition established | Reference provenance | Independent check | Defect found | Correction | Status |
|---|---|---|---|---|---|---|---|
| V-09 | ✔ exact | ✔ | ✔ PDS / PGDA 69 | ✔ controlled experiment (15 points) | none | — | Investigated |
| V-10 | ✔ exact | ✔ | ✔ | ✔ (10 points) | none | — | Investigated |
| Earth-disk visibility | — | ✔ | n/a (geometry) | ✔ ray-cast, 24 cases | none | — | Pending validation |
| Event detection | ✔ V-14 / V-13 evidence | ✔ | n/a | ✔ 13 cases + 5 real results | **yes** (unknown over incomplete bins) | proposed (engine) | Pending validation (blocked) |
| Power indicator | ✔ 240 series | ✔ | n/a | ✔ series, metrics, 14 edge cases, UI | none | — | Pending validation |
| RF link budget (context) | ✔ | ✔ | n/a | ✔ hand-worked case | none | — | (Phase 6 package) |

## 8. End summary
1. **Successfully validated:** nothing is formally Validated. Implementation correctness was verified independently for:
   - disk visibility (geometry);
   - event timing (≤ 0.5 s);
   - the power indicator's computation;
   - the V-09/V-10 statistics, and their agreement with NASA where the comparison is well posed.
2. **Genuine defects corrected:** none. The defect found is in the core engine, and correcting it needs approval.
3. **Failed:** nothing. There are no approved criteria to fail.
4. **Still pending:** V-09 and V-10 (criteria and the reference definition); disk visibility (gates and tolerance); events (the defect fix, then validation); the power indicator (what validation means for an Estimated quantity).
5. **Could not be verified:**
   - AVGVISIB's observer height and near-field method;
   - V-09/V-10 against the reference's own DEM (LDEM_85S_060M);
   - the full 200-point rerun under alternative definitions (15 + 10 points were run);
   - the power indicator against measured power.
6. **Core-engine modification proposed:** yes, one, in `events.py` (section 4.3). It is not implemented, and it requires a new validation baseline.
7. **Minimum work before formal Phase 7 validation:**
   - approve or replace the V-09/V-10 criteria;
   - settle the AVGVISIB observer height (or document it as an accepted limitation);
   - decide on the events correction, implement it, and regenerate the validation report;
   - adopt the disk ray-cast and event cases as regression tests;
   - define the acceptance basis for the power indicator;
   - then run the deferred Phase 7 suite (the 440-test engine suite, U-04 and U-06).
8. **Remaining effort by workstream** (task size, not a time guarantee):

   | Workstream | Size | Main remaining work |
   |---|---|---|
   | V-09 | Medium | Literature/reference confirmation, optional LDEM_85S_060M run, criteria decision |
   | V-10 | Small (rides on V-09) | As V-09 |
   | Disk visibility | Small | Turn the ray-cast into regression tests; set a tolerance |
   | Events | Medium | Engine change plus tests plus re-validation (fingerprint change) |
   | Power indicator | Small to medium | Define the acceptance basis; optional uncertainty propagation |
