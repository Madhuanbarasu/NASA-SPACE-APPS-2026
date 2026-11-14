# U-06: frontend performance audit (2026-11-11)

## Final status: **BLOCKED (provisional measurements)**

**No approved U-06 acceptance criterion exists.** The repository references U-06 only as:
- a gate (`engine/provenance.GLOBAL_TESTS`);
- an owner slot (`validation/common.OWNERS["frontend_u06"]`);
- "performance benchmarks" in the README.

Requirement C05 says "Measured performance" with no threshold, and the blueprint's U-06 text is not in the repository. This audit therefore **measures and documents performance but cannot pass or fail U-06**. No threshold was invented.

**To unblock:** the team must approve U-06 criteria, for example limits on first paint, time to interactive or interaction latency, on a stated device and network profile. These measurements can then be compared against them, or repeated with the scripts below.

**Not touched:**
- `backend/validation/report.json`: its SHA-256 still equals `report_production_merged.json`;
- V-09…V-12 evidence;
- backend code (fingerprints unchanged, `logs/backend_fingerprints_after.txt`);
- algorithm version 1.5.0.

No A6/A7 measurement was rerun. V-04/V-05/V-13/V-14 were not started.

## What was found and done

| # | Finding | Evidence | Action |
| --- | --- | --- | --- |
| 1 | **One 1.24 MB JavaScript bundle on the critical path.** Nothing renders until all of it has downloaded and executed. Before minification it is OpenLayers 45 %, three.js 30 % and proj4 8 % (`raw/bundle_modules_before.json`). On a 4× slower CPU with a 10 Mbit/s, 40 ms connection, first paint waited 2.0 s, of which about 1.1 s was transfer. | baseline loads (below) | **Fixed:** the map pane (OpenLayers, proj4) and the 3D pane (three.js) are code-split with `React.lazy`/`Suspense`; each pane shows its existing "Loading…" text meanwhile (`src/components/SiteView.tsx`). |
| 2 | **The welcome map's only tile request (zoom 0) never completes.** The backend renders it from every registered DEM over the whole polar window: no response within 120 s, while zoom-1 tiles take about 0.5 s. Every page load starts another such render; the server reached 2.0 GB working set and 5,494 CPU-seconds. This is the likely cause of the earlier memory pressure, and it contaminated the first measurements. | `logs/tile_z0_finding.txt` | **Mitigated in the frontend:** the map's tile grid has `minZoom: 1`, so OpenLayers draws the zoomed-out view from zoom-1 tiles and never requests zoom 0 (`src/components/MapView.tsx`). Three quadrants now show hillshade within seconds (`screenshots/final-welcome-map-6s.png`; before: graticule only, `../u04_2026-11-11/screenshots/release-site-welcome.png`). **Not fully fixable here:** the lower-left zoom-1 tile `1/0/1` contains Site01's 5 m DEM and is equally pathological. The remedy belongs in `backend/lunaops/api/tiles.py render_tile`, which may not be changed in this task (see "Recommendation"). |
| 3 | Animation playback | 60 fps, 0 long tasks, 31–34 of 35 expected steps at native and 4× CPU, even with both tables open | **No problem demonstrated → the prepared memoisation fix was not applied.** |
| 4 | 3D and map mount/unmount (5 cycles, forced GC) | heap +0.3–0.4 MB, +5 DOM nodes, no WebGL context warnings | **No leak demonstrated → no change.** |
| 5 | Idle prefetch of the 3D chunk (first fix variant) | It added three.js (480 KB) to every cold visit without lowering the post-paint blocking time or the time to 3D (`raw/perf-after-clean-*.json` vs `raw/perf-variant-noprefetch-*.json`) | **Removed:** the final build loads three.js only when a result needs it. |

## Test environment

| Item | Value |
| --- | --- |
| Machine | HP Laptop 15-fd0xxx; Intel Core 5 120U (10 cores / 12 threads, 1.4 GHz base); 15.7 GB RAM; Intel Graphics (driver 32.0.101.7076); SK hynix BC901 NVMe SSD |
| OS | Windows 11 Home Single Language 10.0.26200 |
| Browser | Chrome 157.0.8103.39, headless, via the Chrome DevTools Protocol; WebGL on the real GPU: "ANGLE (Intel, Intel(R) Graphics (0x0000A7AC) Direct3D11 vs_5_0 ps_5_0, D3D11)" |
| Viewport | 1440 × 900, device scale factor 1 |
| Server | `start.py --no-browser --port 8765` on the same machine (loopback); production NAIF kernels, registered PGDA terrain (5/20/80/240 m), algorithm 1.5.0, code fingerprint `5bf9753f…`; restarted fresh before the clean baseline and before the clean after-runs |
| Load on the machine | Your desktop applications stayed open (about 4–4.7 GB RAM free during the runs). Run-to-run spread is reported below. |
| Tools | `frontend/scripts/perf-audit.mjs`. Nothing was installed or downloaded. |

## Workloads and methodology

**Profiles** (one per run, as requested):

| Profile | CPU | Network |
| --- | --- | --- |
| `native` | 1× | unthrottled loopback |
| `cpu4x` | 4× CPU throttle (`Emulation.setCPUThrottlingRate`) | unthrottled |
| `cpu4x-net10mbps` | 4× | 10 Mbit/s down and up, 40 ms latency (`Network.emulateNetworkConditions`) |

**Loads per profile:**
- 3 cold-cache loads (HTTP cache disabled and cleared);
- 2 warm-cache loads;
- medians reported, all runs kept.

**Metrics:**
- **Navigation Timing:** time to first byte (TTFB), DOMContentLoaded (DCL), load.
- **Paint and layout:** first contentful paint (FCP), largest contentful paint (LCP), cumulative layout shift (CLS).
- **Long tasks**, and total blocking time (TBT): the sum of (long task − 50 ms) after FCP.
- **App ready:** status loaded and the welcome heading shown.
- **Transfer bytes** per resource type, from Network events.
- **Chrome performance metrics:** JS heap, DOM nodes, script, layout and style time.

**One interaction workflow** per CPU profile, on the real data. Each step is timed from the action to the first frame after the expected DOM state, measured in the page with requestAnimationFrame:
1. **Tab switches:** Site → Compare → Data → Guide → Site.
2. **Cached Site01 analysis** (−89.463163°, 222.510447°, 14–21 Nov 2026): click to result painted, and click to 3D terrain data loaded. Result JSON: 320 KB; terrain grid: 190 KB.
3. **20 time-cursor steps by keyboard**, measured with Event Timing (an INP-style per-interaction duration).
4. **5 s of animation playback**, tables closed and then open: steps achieved, frame intervals, long tasks, script time per step.
5. **12 clicks on "Rotate view left"** (3D), each to the next frame.
6. **Technical ↔ Public mode switch.**
7. **Result view away and back:** this unmounts and remounts the map, 3D view and charts.
8. **Cached 2 × 2 comparison:** Site01 and (−89.9°, 0°) × the panel dates and one synodic month later. Click to matrix, metric switch, and opening a cell.

**Memory:** 5 mount/unmount cycles of the result view with forced garbage collection, plus console warnings (WebGL context limits). Native profile only.

**Backend compute is not timed here.** The analysis and comparison come from the server's cache, so the figures are the interface's own cost: transfer, parse, render. Uncached analysis time is covered by Phase 4 A7 (`../terrain_a7_2026-11-11/README.md`):
- Site01 30-day analysis: 15.90 s cold (horizon computed plus Numba compilation), 9.22 s with a cached horizon;
- regional 7-day analysis: 9.61 s and 1.97 s.

It was not re-measured.

**Isolation:** to keep the pathological basemap tiles (finding 2) from loading the server during measurements, Chrome blocked them in every clean run (`--block`): `0/0/0` in the baseline, plus `1/0/1` after the fix (the only tiles of that kind each build requests). In the baseline this means the welcome map shows no hillshade, which is exactly what a user sees for minutes anyway.

## Results: bundle (`raw/bundle_baseline_build.json`, `raw/bundle_final_build.json`)

| JavaScript | Raw | gzip | brotli |
| --- | --- | --- | --- |
| Before: one file (`index-gL-Ccy3m.js`), all initial | 1,243,968 B | 356,759 B | 297,258 B |
| After: initial `index-kvDT7UBF.js` | **295,267 B (−76 %)** | **93,422 B (−74 %)** | 81,788 B |
| After: `MapView-CSDBvknB.js` (OpenLayers, proj4), on demand; the welcome screen loads it right after first paint | 456,582 B | 139,289 B | 118,188 B |
| After: `Terrain3D-_0dC8YFW.js` (three.js), on demand, only once a result is shown | 492,225 B | 123,700 B | 101,997 B |

The two on-demand chunks total 948,807 B raw / 262,989 B gzip. JavaScript transferred on a cold visit to the welcome screen drops from **1,215 KB to 735 KB**, because three.js is no longer downloaded unless an analysis is opened. CSS (20.9 KB) and fonts (88 KB) are unchanged.

## Results: initial load (medians, before → after; all runs in `summary.json` and `raw/`)

| Profile | Cache | FCP (= LCP) | App ready | DCL | TBT | Longest task | JS transferred |
| --- | --- | --- | --- | --- | --- | --- | --- |
| native | cold | 328 → **180 ms** | 452 → 401 ms | 217 → 85 ms | 0 → 0 ms | 114 → 76 ms | 1,215 → 735 KB |
| native | warm | 338 → **170 ms** | 428 → 399 ms | 199 → 61 ms | 0 → 0 ms | 101 → 82 ms | from cache |
| cpu4x | cold | 1,064 → **480 ms** | 1,490 → 1,166 ms | 568 → 78 ms | 32 → 410 ms | 467 → 435 ms | 1,215 → 735 KB |
| cpu4x | warm | 834 → **444 ms** | 1,164 → 1,023 ms | 472 → 74 ms | 56 → 249 ms | 396 → 280 ms | from cache |
| cpu4x + 10 Mbit/s | cold | 2,000 → **852 ms** | 2,356 → 1,280 ms | 1,643 → 479 ms | 50 → 214 ms | 357 → 343 ms | 1,215 → 735 KB |
| cpu4x + 10 Mbit/s | warm | 890 → **540 ms** | 1,340 → 1,138 ms | 471 → 117 ms | 42 → 282 ms | 380 → 308 ms | from cache |

- CLS is 0 in every run.
- The JS heap after load stays about 23 MB, and total script time is about the same, because the same code still runs; only the order changes.
- **About TBT:** before, all start-up work ran *before* first paint, while the user saw a blank page. That work is invisible to TBT, which only counts long tasks after first paint. After the change, the welcome screen paints first, then the map chunk initialises: one or two long tasks of up to about 0.4 s at 4× CPU, counted by TBT. The longest task got shorter in every profile. TBT rising here reflects work moved behind a visible page, not new work. A variant without the idle prefetch confirmed this blocking is the map's own initialisation, not three.js.

**Run-to-run spread** (cold FCP, before → after): native 280–428 → 160–192 ms; cpu4x 748–1,128 → 416–632 ms; cpu4x + 10 Mbit/s 1,936–2,084 → 820–1,044 ms (see `summary.json` `min_fcp`/`max_fcp`). The before and after ranges do not overlap in any profile.

## Results: interactions on the real workloads (before → after)

| Interaction | native | cpu4x |
| --- | --- | --- |
| Tab switch: Compare / Data / Guide / Site | 24 / 71 / 16 / 38 → 23 / 58 / 18 / 32 ms | 47 / 96 / 21 / 48 → 41 / 117 / 35 / 63 ms |
| Cached analysis: click → result painted | 354 → 299 ms | 543 → 632 ms |
| Cached analysis: click → 3D terrain data loaded | 378 → **675 ms** | 620 → **955 ms** |
| Leave result and return (remount map, 3D, charts) | 94 → 73 ms | 245 → 238 ms |
| Time-cursor step (keyboard), median / p95 | 16 / 32 → 16 / 32 ms | 32 / 48 → 16 / 40 ms |
| Playback, tables closed: fps, steps/35, long tasks, script per step | 60.3, 34, 0, 2.3 ms → 60.1, 34, 0, 3.2 ms | 60.2, 33, 0, 7.9 ms → 60.1, 33, 0, 8.8 ms |
| Playback, both tables open (5,795 DOM nodes) | 60.2, 34, 0, 4.6 ms → 60.2, 33, 0, 4.7 ms | 60.2, 31, 0, 13.0 ms → 60.2, 32, 0, 12.6 ms |
| 3D "Rotate view left" → next frame, median | 31.7 → 31.7 ms | 31.8 → 31.7 ms |
| Technical → Public mode | 31.9 → 31.6 ms | 32.1 → 30.7 ms |
| Comparison 2 × 2: click → matrix | 668 → 651 ms | 72 → 657 ms (see note) |
| Comparison metric switch | 30.5 → 31.6 ms | 20.9 → 25.9 ms |
| Comparison cell → full result | 66 → 74 ms | 221 → 194 ms |
| JS heap after the workflow | 37.7 → 37.4 MB | 29.4 → 33.8 MB |

- **One real regression from the change:** the 3D pane's data arrives about 0.3 s later on the first result of a session, because three.js now loads on demand. The pane shows "Loading terrain." meanwhile, and the result itself paints as before.
- **Comparison timings depend on the server's job cache.** In the before sequence, the 4× run reused the identical comparison the native run had just computed (72 ms). The native figures, where neither had that advantage, show no change (668 → 651 ms).
- **Animation playback:** the step interval is 140 ms (7.1 steps per second), so 35 steps are expected in 5 s. 31–34 were reached in every case, with no long tasks and 60 fps.

## Results: memory (native, 5 mount/unmount cycles of the result view, forced GC)

| | Heap before → after cycles | DOM nodes | Event listeners | Canvases | Console warnings |
| --- | --- | --- | --- | --- | --- |
| Before | 29.5 → 29.9 MB (+0.4) | +5 | +5 | 2 | none |
| After | 29.6 → 29.9 MB (+0.3) | +5 | +5 | 2 | none |

No leak and no WebGL context exhaustion were observed. The small constant growth is consistent with React and DevTools bookkeeping.

## Regression checks

| Check | Where | Status |
| --- | --- | --- |
| `frontend/scripts/check-bundle.mjs` (`npm run check:bundle`; 6-case self-test) | manual, after `vite build` | **Not wired into the build:** no documented or approved bundle-size limit exists, and none was invented. It checks the code split (three.js and OpenLayers must not be in the initial chunk) and reports raw/gzip/brotli sizes. It enforces a size limit only if `scripts/bundle-limit.json` exists with `initialJsGzipLimit`, `source` and `approved_date`; no such file was created. |
| `frontend/scripts/perf-audit.mjs` (`npm run audit:perf`) | manual, against a running app | Reruns this audit for one profile and saves after every step: `--profile native\|cpu4x\|cpu4x-net10mbps`, `--cold`, `--warm`, `--workflow`, `--leak-cycles`, `--block`. |
| Existing checks (`npm test`, `npm run build`) | build | All pass on the final source (below). |

## Checks after the changes (final source)

| Command | Result | Log |
| --- | --- | --- |
| `npm run typecheck` | exit 0 | `logs/05_typecheck_final.log` |
| `npm test` | string self-test 38/38, 433 keys, 0 problems; accessibility self-test 15/15, 33 colour pairs, 0 problems; exit 0 | `logs/06_npm_test_final.log` |
| `npm run build` | exit 0; the rebuild is byte-identical to the measured final build | `logs/07_npm_run_build_final.log`, `logs/dist_final_sha256.txt` |
| `npm run check:bundle` | 0 problems; no size limit approved (sizes reported only); self-test 6/6 | `logs/08_check_bundle_final.log` |
| Content preservation (C10 render harness, 54 scenarios) | 0 render errors. Differences are listed below. | `content_preservation/visible_text_comparison.json` |

**The 17 text differences in the content-preservation check:**
- 9 SiteView scenarios (this change): during server-side rendering, the lazy map and 3D panes render their loading text, so the map note and 3D controls are absent. In the browser the panes resolve and render fully: the live workflow used the map, the 3D canvas and the 3D buttons.
- 8 CompareView scenarios: U-04's screen-reader-only "Comparison ready: 2 sites × 2 windows." status message, not this change.
- 5 scenarios differ only by the earlier hackathon cleanup.

The static accessibility check passes. **The live U-04 browser audit was not rerun** for this change, to limit memory use; rerunning it (`npm run audit:a11y`) is recommended before release.

## Recommendation (backend; outside this task)

In `backend/lunaops/api/tiles.py render_tile`, a DEM level is skipped only when it is far *coarser* than the tile (`lv["pixel_m"] > res * 4`). Levels far *finer* than the tile are read over the whole tile window with boundless, resampled reads. This makes coarse tiles that cover Site01's 5 m DEM, or the whole region, take minutes and gigabytes.

Skipping levels whose pixel size is far finer than the tile resolution, except where they are the only data, would make every tile fast and remove the memory risk. This changes only the cartographic basemap, not any analysis. It needs a separate, approved backend change; the backend code fingerprint would change and the validation report would need regenerating.

## Remaining limitations

1. **U-06 cannot be decided:** no approved acceptance criterion exists (see "Final status").
2. **Lighter rerun as instructed:** 3 cold + 2 warm loads and one workflow per profile, so the medians come from few samples. Your desktop applications were running, and the spread is reported. Absolute numbers are specific to this laptop; the 4× profile emulates a slower CPU but is not a real low-end device.
3. **One engine:** Chrome 157 headless only, with GPU rendering through ANGLE/D3D11. Firefox and Safari were not measured.
4. **The server runs on the same machine** (loopback), so network costs come only from the emulated profile. Real deployments add real latency.
5. **The pathological basemap tiles were blocked** during the clean runs. Without blocking, every page load also starts one slow backend render: zoom-0 before, tile 1/0/1 after. That would load the server and affect other requests.
6. **Contaminated runs are kept for transparency but not used** for the before/after comparison:
   - `raw/perf-before-native.json` and `raw/perf-before-loads-native.json`: the zoom-0 renders running; the tile wait timed out;
   - `raw/perf-after-native.json`: tile 1/0/1 renders running;
   - `raw/perf-after-clean-*.json`: the intermediate variant with the idle 3D prefetch, superseded.
   - The first full baseline (before this rerun) was stopped by Claude Code's memory protection before it saved anything. Its single smoke sample was not saved and is not used.
7. **The 3D pane's first appearance** after an analysis is about 0.3 s later than before (finding 1, interactions table).
8. **The welcome map's Site01 quadrant** still waits on the backend's slow tile (finding 2; backend recommendation above).

## Contents

| Path | What |
| --- | --- |
| `summary.json` | Before vs after per profile: load medians with min/max FCP, interactions, memory, bundle (built by `summarize.mjs` from `raw/`) |
| `raw/perf-before-clean-<profile>.json` | **Baseline** (U-04 build), one file per profile, written after every step |
| `raw/perf-variant-noprefetch-<profile>.json` | **Final build** (after), one file per profile |
| `raw/perf-after-clean-<profile>.json` | Intermediate variant with the idle 3D prefetch (superseded; kept) |
| `raw/perf-before-native.json`, `raw/perf-before-loads-native.json`, `raw/perf-after-native.json` | Contaminated runs (limitation 6; kept) |
| `raw/bundle_modules_before.json` | Per-package rendered size of the baseline bundle, from the real Rollup build |
| `raw/bundle_baseline_build.json`, `raw/bundle_after_build.json`, `raw/bundle_final_build.json` | `check-bundle` reports: baseline, prefetch variant, final |
| `logs/` | Run logs; `tile_z0_finding.txt` (tile timings, server memory/CPU, cause); `dist_*_sha256.txt`; build/test logs `01–08`; `backend_fingerprints_after.txt` |
| `screenshots/final-welcome-map-6s.png` | The welcome map on the final build, 6 s after load, nothing blocked |
| `content_preservation/visible_text_comparison.json` | Visible-text comparison (C10 harness) |
| `summarize.mjs`, `scripts_welcome_map_shot.mjs` | Scripts used to build the summary and the screenshot |
