# E2E-07 correction: analysis date-range validation and panel-azimuth normalisation (2026-11-14)

**Scope:** frontend only.

**Not changed:**
- `backend/lunaops`, scientific calculations, RF calculations;
- thresholds, labels, caches and existing evidence.

**Fingerprints unchanged** (`logs/05_fingerprints_after.txt`): code `9cd7b08b…`, suite `519a8e4c…`.

**Server:** the existing server was used; no new server was started. Phase 7 was not started.

## Correction
- **Rule:** the analysis end must be **strictly after** the start, compared in UTC. The sidebar stores both as UTC ISO strings ending in `Z`, so the browser's time zone does not matter.
- **New `frontend/src/lib/timeWindow.ts`:** `windowValid(start, end)`. It is dependency-free, so the check script can test it directly.
- **Sidebar** (the date fields):
  - the end field gets `aria-invalid` and `aria-describedby="window-hint"`;
  - an inline message reads "The end must be after the start (UTC). Analyse is disabled until it is.";
  - Analyse is disabled.
- **The other two Analyse buttons** (Site explorer, Mission dashboard) are also disabled for an invalid window.
- **`runAnalysis` (store)** refuses an invalid window before any request, with the same message. This covers any other caller, such as the Communication tab's Analyse.
- **Panel azimuth:**
  - values are normalised modulo 360° with the existing `lon360` (400° → 40°) in the analysis and comparison request bodies, so the request, the stored result and the display carry the same value;
  - the sidebar shows "Azimuths are taken modulo 360°: this value is used as 40°." when the typed value differs;
  - the indicator is periodic in azimuth, so results are mathematically unchanged (`azimuth_equivalence.json`: 40 / 400 / −320° agree to 2e-15 on 1,442 real samples).

## Modified and new files (`source_changes.diff`; originals in `baseline/`)
| File | Change |
|---|---|
| `frontend/src/lib/timeWindow.ts` (new) | `utcMs`, `windowValid` |
| `frontend/scripts/check-window.mjs` (new) | 20 focused checks (window cases, time-zone offset, azimuth normalisation) |
| `frontend/src/components/Sidebar.tsx` | Window check, inline message, aria attributes, Analyse condition, azimuth note |
| `frontend/src/state/store.tsx` | Guard in `runAnalysis`; `panel_az_deg: lon360(...)` in both request bodies |
| `frontend/src/components/SiteExplorer.tsx`, `MissionView.tsx` | Analyse disabled for an invalid window |
| `frontend/src/i18n/en.ts` | `invalidWindow`, `panelAzimuthNormalized` |
| `frontend/package.json` | `npm test` also runs `check-window.mjs` (line endings preserved) |

## Results
| Check | Result | Log |
|---|---|---|
| TypeScript (`tsc --noEmit`) | 0 errors | `logs/01_typecheck.log` |
| `npm test` | strings 1371 keys, 0 problems; a11y 0 problems; moon-geo 238,972; **check-window 20/20** | `logs/02_npm_test.log` |
| Build | OK | `logs/03_build.log` |
| Browser, one cycle (`browser-results.json`, `screenshots/`) | **6/6 Pass** | `logs/04_browser.log` |

**Browser cases:**
- **Valid ranges** (30-day window; 1-minute boundary): no message, Analyse enabled.
- **Invalid ranges** (equal start and end; reversed; reversed by 1 minute): end field `aria-invalid="true"`, inline message shown, sidebar and explorer Analyse disabled. Clicking them sent **0** analysis requests.
- **Panel azimuth 400°:** the note says "used as 40°"; the request carried `panel_az_deg: 40`; the stored result has `azimuth_deg: 40`; the displayed value equals the backend's.

**Transparency notes:**
- **Clean-up crash:** the browser script stopped in its final clean-up step, after every check had completed: it reset the azimuth field after the field had been removed. `browser-results.json` was rebuilt from the complete log lines; no check was repeated. The script is fixed for future runs.
- **Discarded comparison:** a first comparison of the 40° result with the earlier 400° result was not like for like (900 s and 1800 s steps, and both series zero). It is recorded and superseded by `azimuth_equivalence.json`.

**Known limitation:** the azimuth input keeps its 0–360 browser hint. A value outside that range is accepted and normalised, with the note shown.
