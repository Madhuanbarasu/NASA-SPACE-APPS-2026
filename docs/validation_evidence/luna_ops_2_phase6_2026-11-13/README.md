# LUNA-OPS 2.0, Phase 6: Mission Communication Simulation (2026-11-13)

**Status: implemented; awaiting the owner's review.** Phase 7 has not been started.

This is a **preliminary, geometry-based and parameter-driven simulation**. Geometric visibility, RF feasibility under user-entered parameters, and path availability are kept separate. A visible Earth is never called a working link.
- No reliability score, recommendation, invented hardware value, real-relay claim, DSN schedule, communication certification or LunaNet compatibility is claimed.

**Documents:**
- `ARCHITECTURE.md`: package, data flow, fingerprint protection, API, caching.
- `METHODS.md`: geometry, link-budget equations and assumptions, relay method and the effects of the two-body approximation, timelines, planner.
- `SOURCES.md`: data, NASA references, scenario provenance.
- `baseline/README.md`.

## Approved decisions (owner)
1. **Reuse the engine analysis.** Earth geometry and Earth-visibility events come from completed engine results and are never recomputed.
2. **Relay input:** Keplerian elements only, with CSV ephemeris deferred. Two frames: J2000, and the epoch-frozen lunar mean-equator inertial frame (LME_EPOCH). Propagation is in an inertial frame, with states turned into the lunar body-fixed frame through SPICE.
3. **Lunar GM** from NAIF `gm_de440.tpc` in `data/comms/`: SHA-256 `924ddf4f…` recorded, `BODY301_GM` parsed as text and verified as 4902.8001184575496 km³/s². It is not loaded into the engine's SPICE pool.
4. **Labels.** Engine labels are passed through exactly as each analysis result states them, with the engine's reasons. Everything new is labelled "Preliminary simulation, not part of the validated engine".
5. **Store-and-forward:** a simple conceptual contact-planning simulation, labelled as such.

## Validation protection
- **Unchanged after Phase 6:**
  - algorithm 1.5.0;
  - code fingerprint `84cbd4ea…`;
  - suite fingerprint `1632af16…`;
  - terrain acceptance digest `e48eb8ed…`;
  - `report.json` SHA-256 `8c03ebaf…`;
  - all `backend/lunaops` files byte-identical;
  - `backend/lunaops_landing` (Phase 5) byte-identical;
  - `registry.json`, the landing manifest, the kernel `lock.json`, `datasets.json` and `requirements.txt` unchanged.
  
  See `logs/backend_fingerprints_after.txt` and `logs/changed_files.txt`. The running app reports the report's code fingerprint with no validation blockers.
- **Only change outside the new package:** four lines in `start.py` that attach `/api/comms/*` after the Phase 5 landing routes. The fingerprint scope is listed in `baseline/code_fingerprint_scope.txt` and `baseline/suite_fingerprint_scope.txt`; `backend/lunaops_comms/` and `data/comms/` are outside both.
- **Engine labels.** `/api/status` reports the terrain horizon as "Validated". The analysis results used here label it "Pending validation" because they use the horizon-uncertainty model, which rests on the uncalibrated L_corr = 250 m assumption. This is the engine's own per-result reason. The Communication tab shows each **result's** labels and reasons unchanged; it never takes or upgrades a label.

## 1. Communication features implemented
- **Backend `backend/lunaops_comms/` (comms 0.1.0):**
  - direct-to-Earth values from the engine result;
  - the free-space link-budget chain per sample distance, with every input user-entered and no defaults;
  - a hypothetical two-body relay with both legs computed separately;
  - three-valued timelines (open, closed, unknown) with AND/OR, gaps, statistics and next changes;
  - comparison statistics and the store-and-forward planner;
  - full provenance;
  - routes `/api/comms/meta`, `/api/comms/linkbudget` and `/api/comms/simulate`.
- **Frontend: a lazily loaded "Comms" tab** (`CommsView`, `CommsCharts`, `comms.css`):
  - **A. Location:** coordinates, site name, coverage, window, steps, rule, horizon incomplete share, and the engine labels as badges.
  - **B. Direct to Earth**, with a time cursor: Earth elevation, azimuth, distance, light time and clearance; geometric visibility; terrain blocking; RF status; next change; current or next window.
  - **E. Timeline and elevation chart:** geometry rows and RF rows with separate styles and separate legends, unknown time hatched, uncertain windows outlined, and a list of open windows.
  - **C. RF link budget** for three links (direct, lander → relay, relay → Earth): a form in physical units, a breakdown at the shortest and longest distance with the formula of each term, "not evaluated: missing …", and the illustrative or specification tag with a reference.
  - **D. Hypothetical relay:** elements, frame and epoch; period and altitudes; the two legs and both together (open time, windows, range, notes); the hypothetical-orbit warning.
  - **F. Comparison:** a table of six paths (open time, windows, mean and longest gap, unknown time, uncertain windows), the time the relay adds when direct is closed, and bars.
  - **Store-and-forward planner.**
  - **G. Provenance:** engine result and labels with reasons, kernels, frames, terrain products, GM with its SHA-256, constants, methods, versions, limitations and the NASA references.
- **Mission dashboard:**
  - "Open in Communication" on the selected-site card;
  - a "Communication" action on every candidate card (selects the site, opens the tab, and runs the analysis if the session has none);
  - a "Communication simulation in this session" block on each card: Earth-visibility windows and hours, next window, the relay's two-leg windows if configured, and whether the direct RF budget was evaluated.
  
  The landing block, the selection, the comparison metrics, the 6 h2 headings and the `li` structure are unchanged (preview: `h2 = 6`, `nestedLi = 0`, integrity pattern not matched).
- **Top bar (`shell.css`).** The seventh view pushed the Technical/Public switch off the bar at 1440 px, so the existing compact menu now applies below 1600 px (it was below 1440 px since Phase 5). There is no overflow from 320 to 1920 px (`previews/topbar.json`, `previews/screenshots/topbar-menu-1280.png`).

## 2. Direct-to-Earth results (real engine analyses; `examples/*.json`)
The illustrative direct RF set is in `SOURCES.md`: 20 W, 20/60 dBi, 8450 MHz, 1 Mbit/s, required Eb/N0 2.5 dB.

| Site, window | Earth visible (engine) | Earth above 0° but behind terrain | Direct margin over the window | Direct RF-feasible |
|---|---|---|---|---|
| Site01 89.4632° S 222.5104° E, 13–20 Dec 2026 | 50.4 h, 1 window | 81.6 h | +14.0 to +14.8 dB | 50.4 h (all visible time) |
| 89.2° S 200° E, 14–21 Nov 2026 | **0 h** (Earth never above the terrain) | 67.2 h | +14.0 to +14.6 dB | **0 h**: a positive budget does not create a path |
| 84.31° S 359.05° E, 13 Nov–13 Dec 2026 | 545.0 h, 2 windows, longest gap 157.6 h | 38.7 h | +14.0 to +15.0 dB | 545.0 h |
| 78.40° S 21.87° E, 13 Nov–13 Dec 2026 | **0 h** | **720 h**: the Earth stays above 0° all month but behind terrain | +14.0 to +15.0 dB | 0 h |

- **Hand check of the direct breakdown** (browser, Site01, 1440 px):
  - FSPL 222.41 dB;
  - EIRP 10·log10(20) + 20 − 1 = 32.01 dBW;
  - Pr = 32.01 − 222.41 − 3 + 60 − 1 = −134.40 dBW;
  - C/N0 = −134.40 + 228.60 − 10·log10(50) = 77.21 dB-Hz;
  - Eb/N0 = 77.21 − 60 = 17.21 dB;
  - margin 14.71 dB;
  - C/N in 2 MHz = 14.20 dB.
- **Margin range:** the reported margin range covers every sample distance in the window, whether or not the path is open. RF feasibility always needs the path open as well.

## 3. RF link-budget functionality
- **Equations:** see `METHODS.md` section 2.
- **Tests:** 24, with analytic checks:
  - FSPL equals both 20 log10(4πR/λ) and the handbook form with 32.4478 dB; Earth–Moon distance at 2.2 GHz gives 211.0 dB;
  - the full chain is checked by hand;
  - W and dBW inputs agree;
  - the inverse-square law holds: 6.02 dB per doubling of distance;
  - each of 8 missing inputs leaves its term and every later term unevaluated;
  - 10 invalid values are reported and never used: power 0 or negative, frequency 0, negative or NaN, data rate 0 or negative, noise temperature 0, negative losses, non-numeric input;
  - inconsistent W and dBW values are refused;
  - an empty set gives nothing evaluated;
  - the illustrative and specification tags work.
- **In the browser:** setting the data rate to 0 turned the budget to "incomplete" and showed "Data rate must be greater than 0 bit/s" (`04-desktop-link-budget-invalid.png`).

## 4. Relay simulation capabilities and results
- **Capabilities:**
  - Keplerian elements in J2000 or LME_EPOCH;
  - analytic two-body propagation with the verified GM;
  - SPICE transformations to the lunar body-fixed frame;
  - leg 1 against the site's terrain horizon and the lunar sphere, with unknown and uncertain kept;
  - leg 2 against the lunar disk with an optional grazing altitude;
  - relay-assisted contact = both legs open;
  - optional link budgets per leg;
  - 10–3600 s sampling, at most 50,000 samples.

| Case | Leg 1 open | Leg 2 open | Both legs | Relay with both budgets met | Time the relay adds when direct is closed |
|---|---|---|---|---|---|
| Site01 + H1 (7 d) | 128.2 h | 163.4 h | 128.2 h, 23 windows, longest gap 2.8 h | **0 h**: uplink margin −11.6 to −5.5 dB with the illustrative 5 W / 1 Mbit/s uplink | 88.6 h geometric, 0 h RF |
| 89.2° S 200° E + H1 (7 d) | 125.8 h | 163.4 h | 125.4 h, 17 windows | 0 h (same uplink) | 125.4 h geometric where direct-to-Earth never exists |
| 89.2° S 200° E + H2 100 km lunar-polar (7 d) | 14.1 h | 118.8 h | 13.4 h, 91 short contacts, longest gap 1.83 h | 13.4 h (uplink margin up to +26.6 dB at short range) | 13.4 h |
| 89.2° S 200° E + **H3 = H2 in J2000** (7 d) | **0 h** | 107.3 h | 0 h | 0 h | 0 h: the same elements polar to the Earth's equator never pass near the lunar south pole (frame demonstration) |
| 84.31° S 359.05° E + H1 (30 d) | 520.6 h | 701.2 h | 520.6 h, 86 windows | 0 h | 129.0 h geometric |
| 78.40° S 21.87° E + H1 (30 d) | 489.8 h | 701.2 h | 489.8 h, 64 windows | 0 h | 489.8 h geometric |

- **Store-and-forward** (20,000 Mbit at 1 Mbit/s, "any path meeting its link budget"):
  - Site01: complete on 18 Dec 15:52 UTC, 123.1 h after the data was ready (the first direct window opens on 18 Dec);
  - 84° S: complete after 23.0 h in 1 contact;
  - H2 case: complete after 74.1 h over 40 relay contacts;
  - cases with no RF-feasible path: all 20,000 Mbit still queued at the window end.
- **Example orbits.** An earlier draft of the examples had two wrong scenario choices: ω = 270° put H1's apoapsis over the lunar *north*, and H2 was polar in J2000. The simulation correctly showed few or no contacts for both. The orbits were corrected (`SOURCES.md`), and the J2000 version is kept as the documented frame demonstration H3.
- **A sphere-test fault found and fixed while checking:** a site lower than the 1737.4 km sphere (common on polar crater floors) would have counted every line as crossing the Moon. The occulting sphere is now the lower of 1737.4 km and just below the site, with a test (`test_site_below_the_reference_sphere_still_sees_overhead_relay`).

## 5. NASA resources used
- NAIF `gm_de440.tpc` (data).
- NASA Glenn Lunar Surface Propagation, and NASA Delay/Disruption Tolerant Networking (scope and concept only; neither is implemented).
- The engine's NAIF kernel set (unchanged).

Links and details are in `SOURCES.md`.

## 6. Files modified and added
See `logs/changed_files.txt`.
- **Frontend, new:**
  - `src/components/CommsView.tsx`
  - `src/components/CommsCharts.tsx`
  - `src/styles/comms.css`
- **Frontend, modified:**
  - `src/App.tsx`
  - `src/api/client.ts`
  - `src/api/types.ts`
  - `src/components/MissionView.tsx`
  - `src/components/TopBar.tsx`
  - `src/i18n/en.ts`
  - `src/state/store.tsx`
  - `src/styles/app.css`
  - `src/styles/shell.css`
- **Backend:**
  - new: `backend/lunaops_comms/` (7 modules plus `tests/` with 4 test files and `__init__`);
  - modified: `start.py`, 4 lines.
- **Data:** new `data/comms/` (`manifest.json`, `gm_de440.tpc`).
- **No new dependency.**

## 7. Focused test results (no 440-test suite, no U-04/U-06 audits)
- **Backend:** `pytest lunaops_comms/tests`: **57 passed** (`logs/05_comms_pytest.log`).
  - **Link budget (24):** see section 3.
  - **Timelines (7):** interpolated crossings; NaN samples stay unknown; three-valued AND, OR and AND-NOT; window intersection of two legs; gaps and statistics; next change and next open; engine intervals keep their uncertainty flags, and source gaps become unknown.
  - **Relay (17):**
    - GM verified against the file and its SHA-256, read from data blocks only;
    - the Kepler solver;
    - a circular orbit keeps its radius and speed and returns after one period;
    - an elliptic orbit conserves vis-viva and angular momentum, with periapsis at M0 = 0;
    - the LME_EPOCH frame: an equatorial orbit has z = 0 in the body frame at the epoch, and a polar orbit at ω = 90° has z = a;
    - the J2000 frame is the identity, and the two frames differ;
    - 8 invalid or incomplete element cases;
    - relay-to-Earth blocked behind the Moon, with the exact limb angle;
    - lander leg: flat horizon, a 20° terrain wall, below the local horizon, incomplete bins giving unknown;
    - a line through the Moon is blocked even when the DEM horizon is low;
    - a site below the reference sphere.
  - **Service and API (9),** on synthetic results built in memory:
    - routes precede the catch-all; GM in `meta`;
    - direct windows equal the engine intervals, and labels pass through verbatim with reasons;
    - a 10° terrain wall blocks a 3° Earth;
    - RF-feasible needs both margin and geometry;
    - the relay is assisted only where both legs are open; no relay budgets gives "not evaluated";
    - an incomplete horizon gives unknown;
    - store-and-forward arithmetic: 36 Mbit at 1 kbit/s = 10 h, an incomplete case, and not evaluated without a budget;
    - 404 and 422 handling;
    - no reliability, ranking or certification vocabulary in the response keys.
- **Phase 5 regression:** `pytest lunaops_landing/tests`: 35 passed (`logs/05b_landing_pytest_regression.log`).
- **Frontend:**
  - `tsc` 0 errors;
  - `npm test`: strings 1366 keys, 0 problems; accessibility 40 components and 52 colour pairs, 0 problems; check-moon-geo 238,972 checks;
  - build OK;
  - `check-bundle`: initial JS 313.7 KB (101.3 KB gzip; 301.0 KB in Phase 5, growth from the new strings), `CommsView` lazy chunk about 29 KB.
- **Preview** (one headless browser, `previews/comms-preview.json`, 24 screenshots plus the top-bar menu):
  - analysis, then simulation, then the direct budget (with its invalid case), the relay, both relay budgets, the cursor, the planner, the provenance;
  - the Mission block and the open-in-Communication action;
  - returning to the tab keeps the inputs;
  - no horizontal scroll at 1920, 1440, 1024, 390 or 320 px;
  - 0 console errors.

## 8. Performance results (`examples/summary.json`; Windows working set of the Python process)
- **Timings:**
  - 7-day windows: 0.3–0.5 s per first simulation, including the relay at 60 s or 30 s steps (10,000–20,000 samples);
  - 30-day windows at 60 s (43,201 samples): 2.3–3.8 s in the final run, 6–9 s in an earlier run on the same machine under other load;
  - link-budget or planner edits on a cached relay: 0.07–0.6 s;
  - first simulation in the browser after the cached analysis: about 0.65 s.
- **Memory:** process working set from 67 MB at start to 130 MB peak.
- **Resources:** one browser at a time; the server is the only background process; all temporary files on `E:\Temp\LUNA-OPS`.

## 9. Scientific assumptions and limitations
- **Geometry is not a link.** Line of sight to the Earth's centre or the relay says nothing about pointing, polarisation, interference or scheduling.
- **Free space only.** No surface multipath, diffraction or reflection (the subject of NASA Glenn's Lunar Surface Propagation research), atmosphere or rain at the Earth end, Doppler or interference.
- **Your parameters only.** Every RF value is the user's. A positive margin does not guarantee a data rate without matching modulation, coding and receiver design.
- **Earth end:** the Earth's centre. No ground stations, DSN availability or scheduling.
- **Two-body relay:** an idealised orbit (`METHODS.md` section 3). Contacts shorter than one sampling step can be missed. Leg 2 tests the Earth's centre only.
- **Engine values:** they inherit the engine's own limitations, including the uncalibrated L_corr horizon-uncertainty assumption and the leap-second warning for dates after the last LSK leap second. Unknown and incomplete-terrain time is never counted as open or closed.
- **Planner:** conceptual; not DTN and not LunaNet.

## 10. Outstanding for Phase 7 (deferred; not passed)
- **Earlier deferred work:**
  - all live browser checks, including the map and e2e checks deferred since Phase 1;
  - the `viz-live-check` and `mission-live-check` updates;
  - `shell-live-check` for seven tabs and the compact menu now below 1600 px;
  - the U-04 Tab counts;
  - rendered contrast, including the new chips and timeline colours;
  - long-window performance;
  - the Phase 5 landing keyboard and screen-reader review.
- **Phase 6:**
  - keyboard and screen-reader review of the Communication tab: the SVG timeline has a text alternative in the window list, but no per-segment focus;
  - mission-live-check assertions for the new Communication buttons and card block;
  - an independent review of the link-budget and relay methods;
  - CSV relay ephemeris input (deferred by decision);
  - perturbation-aware propagation, if wanted;
  - ground-station geometry, if real station data is supplied;
  - long-window SPICE cost (the relay loop is serial) and the memory of many cached relays.

## Integrity and reproduction
- **Commands:**
  - Backend tests: from `backend/`, with TEMP and TMP set to `E:\Temp\LUNA-OPS`, run `python -m pytest lunaops_comms/tests -p no:cacheprovider`.
  - Examples: `python <evidence>/scripts/real_examples.py <out>`. These use cached engine results.
  - Preview: concatenate `../luna_ops_2_phase1_2026-11-13/cdp_harness.txt` with `scripts/comms_preview_body.mjs`, then run it with `node … --base http://127.0.0.1:8000 --out <dir>`.
- **Manifest:** `SHA256SUMS` covers every file in this folder.
- **Constraints observed:**
  - no Git commands;
  - downloads and temporary files on E:;
  - the LUNA-OPS 1.0 backup, `report.json` and the Phase 1–5 evidence untouched (their `SHA256SUMS` verify).
