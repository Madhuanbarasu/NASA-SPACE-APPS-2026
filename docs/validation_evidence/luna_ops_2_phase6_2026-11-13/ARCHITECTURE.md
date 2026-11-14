# Communication simulation architecture (comms 0.1.0)

```
                    validated engine (unchanged, fingerprinted)
  /api/analysis ──► lunaops.engine.analysis ──► result JSON in data/cache (series, intervals, horizon, labels)
                                                      │ read only (engine.cache.get_result)
                                                      ▼
  /api/comms/simulate ──► lunaops_comms.service ──┬─ direct:    engine Earth series + Earth-visibility intervals (not recomputed)
                         (separate package)       ├─ linkbudget: free-space RF chain per sample distance (user parameters only)
                                                  ├─ relay:     two-body orbit (GM from data/comms/gm_de440.tpc), SPICE pxform/spkpos
                                                  │             via the engine's kernel set and lock (read only), engine Site + HorizonProfile
                                                  ├─ windows:   three-valued timelines (open / closed / unknown), AND / OR, gaps, stats
                                                  └─ store_and_forward: conceptual queue across open windows
```

## Placement and validation protection
- **Package.** `backend/lunaops_comms/` has 7 modules: `__init__`, `constants`, `linkbudget`, `windows`, `relay`, `service`, `api`. Its 4 test files are in `tests/`.
- **Outside both fingerprints.** The code fingerprint covers `backend/lunaops/**.py` and its manifests. The suite fingerprint covers `backend/tests` and `backend/validation`. Both are unchanged (see `logs/backend_fingerprints_after.txt`).
- **Imports from the engine, read only:**
  - `engine.cache.get_result`, `engine.ephem.Site`, `engine.visibility.HorizonProfile`;
  - `engine.kernels.load` and `SPICE_LOCK`, `engine.timeutil.parse_utc` and `to_utc`;
  - `lunaops.settings`, `lunaops.fingerprint.code_fingerprint`.
  
  No engine file is edited. No kernel is added to the SPICE pool: `gm_de440.tpc` is parsed as text.
- **Startup.** The only change outside the package is four lines in `start.py` (`from lunaops_comms.api import install; install(app)`), after the Phase 5 landing hook. `install()` inserts the `/api/comms/*` routes ahead of the single-page-app catch-all.
- **Labels.**
  - Every comms output carries `comms_status` = "Preliminary simulation, not part of the validated engine" and `comms_version` 0.1.0.
  - The package's own code hash (`comms_code_sha256`, tests excluded) is reported. The final value is `8c4ffe5d…`.
  - The engine labels of the analysis result are passed through verbatim (`engine_labels`, `engine_label_reasons`) and never upgraded.

## API
| Route | Purpose |
|---|---|
| `GET /api/comms/meta` | Version, status, the verified lunar GM, link-field names and units, relay limits. It also states "no defaults". |
| `POST /api/comms/linkbudget` | One link budget at one distance (calculator). |
| `POST /api/comms/simulate` | Input: `result_id` (a completed engine analysis), and optionally `direct_link`, `relay`, `relay_up_link`, `relay_down_link`, `dtn`. Output: the engine direct-to-Earth values and labels, the link breakdowns, the relay legs, the timelines, the next changes, the comparison, the planner and the provenance. |

- **Errors:**
  - an unknown or expired result gives 404;
  - invalid orbital elements or limits give 422 with the reasons;
  - missing or invalid RF parameters do **not** error: the dependent terms are returned as "not evaluated", with the missing or invalid names.

## Caching and resources
- **Analysis results:** the latest 3 are held in memory, about 0.3–0.6 MB of JSON each.
- **Relay geometry:** the latest 4 are held in memory, keyed by result id, elements, step and grazing altitude. Editing a link budget or the planner never repeats the SPICE loop.
- **Relay sampling:** the step is 10–3600 s, and at most 50,000 samples are allowed (a 30-day window at a 60 s step is 43,201).
- **Measured cost (`examples/summary.json`):**
  - 7-day windows: 0.3–0.5 s;
  - 30-day windows at 60 s: 2.3–3.8 s in the final run, and 6–9 s in an earlier run on the same machine;
  - a link-budget edit afterwards: 0.07–0.6 s;
  - process working set: 130 MB peak.
- **Frontend:** a lazily loaded `CommsView` chunk (about 29 KB), with SVG charts only. There is no WebGL, so the one-context rule is unaffected.
