# Phase 5, Prompt 4: advanced mission dashboard (2026-11-12)

**Status:** implemented and tested; frontend only.
- **Mission check:** 42/42 live checks compare the dashboard with the API's own responses (`/api/status`, `/api/coverage`, `/api/results/{id}`).
- **Regression:** visualisation 25/25, explorer 27/27, globe 31/31; the full live U-04 audit is unchanged apart from the documented Phase 5 additions.
- **Unchanged:** no backend, scientific calculation, label or validation result changed; algorithm 1.5.0, the fingerprints and `report.json` (`2279606c…`) are identical to Prompt 3 (§6).

## 1. Dashboard features (existing components and API data reused; nothing calculated)

| Area | What it does | Data used |
| --- | --- | --- |
| **Mission tab** | New first tab, "Mission". The app still opens on the Site tab, and the tab list stays one tab stop (arrow keys, Home, End). The dashboard is a lazily loaded chunk (12.5 KB), loaded when the tab is first opened. | none |
| **Quick navigation** | Buttons for **3D Moon**, **South polar map**, **Local terrain**, **Analysis** and **Comparison**. The first three open the explorer view for the selected site. Local terrain is enabled only when the site is covered. Analysis opens the open result, or the latest result from this session. Focus moves to the main region. | store |
| **Selected site** | Coordinates (shared formatter), signed form, registered terrain coverage or the backend's refusal reason. Actions: inspect local terrain, analyse, add to the candidates. | `GET /api/coverage` (the shared store lookup) |
| **System status** | The same readiness rows as the welcome screen: kernels and frame, terrain products, catalogue, validation report. Also the current label counts ("2 validated, 3 pending validation") and a note that Pending means not yet validated. | `GET /api/status` |
| **Current analysis** | Site, window, the validation chips (the result view's `LabelChips`, unchanged), and the main figures: sunlit %, longest darkness, Earth in view %, longest Earth gap, both %, each with its rule. Uncertainty: unknown sunlit time, uncertain and near-field sunlit windows, unknown Earth time, horizon lower-bound share, and the σ statement with its L_corr caveat. **Deep links** go to the panorama, timeline, visibility chart, 3D terrain and map, and the tables (technical mode only). | result fields: `summary`, `labels`, `horizon` |
| **Candidate sites** | The comparison sites as cards, each with its own coverage lookup. Actions: Select (makes it the selected site everywhere), Analyse (selects it, then runs the existing analysis), Open result (when this session has one) and Remove. Add the selected site (no duplicates), and Compare candidates. | `GET /api/coverage` per candidate |
| **Analyses in this session** | Every result run or opened in this session, newest first (at most 20; this browser session only). Shows site, window, the five figures, label counts and an Open button. The rows are copies of API fields made when the result arrived; nothing is derived. | `Result` (copied by `historyItem`) |
| **Comparison** | Whether a comparison ran ("2 sites × 2 windows compared."), its progress or error, and a link to it. | store |

**Navigation and workflow improvements**
- **View survives tab switches:** the Site tab's explorer view (map, globe or local terrain) now lives in the store, so it is kept when the user switches tabs.
- **Context is kept:** the selected site, dates, candidates, comparison and session results are kept across tab switches.
- **Leaving a result:** going from the dashboard to the explorer closes the open result, which stays in the session list and reopens from Analysis.
- **Deep links:** the target section gets focus at once. Scrolling waits until the result view's layout has settled (charts measure their width; the map and 3D panes load lazily). It jumps without animation when the user prefers reduced motion.
- **Candidate names:** a candidate added without a name is named by its coordinates. That label is not copied into the site-name field when the candidate is selected.

**3D terrain marker/message overlap (fixed):**
- **Before:** in the result view's `Terrain3D`, when no single terrain product covers the 8 km window, the backend's message was shown but the Earth marker was still drawn over it (Prompt 3, `screenshots/05-edge-site-60S-missing-data.png`).
- **Now:** the site, Sun and Earth markers are created hidden and shown only once terrain and vectors exist. The message is an opaque overlay (`.pane-message`, `role="status"`) above the canvas.
- **Evidence:** `mission_check/screenshots/08-terrain3d-message-no-marker-overlap.png`.

## 2. Scientific integrity
- **Nothing computed:** every figure on the dashboard is a field of an API response, shown with the existing formatters. Nothing is scored, ranked, combined, weighted or recommended. The live check scans the dashboard text for score, probability, rank or recommendation; none was found outside the disclaimer.
- **Labels unchanged:** labels are shown exactly as the API gives them, and counted from the API status words. In every tested result the four terrain-dependent quantities are Pending and only Sun and Earth positions are Validated.
- **Missing values stay missing:** they show as "n/a" or "unknown", and lower-bound horizons are reported as such.

## 3. Results

| Check | Result | Evidence |
| --- | --- | --- |
| TypeScript | exit 0 | `logs/00_typecheck.log` |
| `npm test`: strings (654 keys, 0 problems; self-test 38/38), static a11y (21 components, 0 problems; self-test 15/15), geometry (238,972) | exit 0 | `logs/01_npm_test.log` |
| Production build; bundle split | exit 0; three.js still lazy; initial JS 319.1 KB / 100.4 KB gzip (+4.4 / +1.4 KB over Prompt 3: store history, readiness rows, strings); dashboard chunk 12.5 KB lazy | `logs/02_npm_run_build.log`, `logs/03_check_bundle.log` |
| **Mission live check** (`scripts/mission-live-check.mjs`) | **42/42** | `logs/04_mission_live_check.log`, `mission_check/mission-check.json`, `mission_check/screenshots/` (11) |
| Visualisation regression (Prompt 3 check) | 25/25 | `logs/05_viz_live_check.log`, `viz_check/` |
| Explorer regression (Prompt 2 check) | 27/27 | `logs/06_explorer_live_check.log`, `explorer_check/` |
| Globe regression (Prompt 1 check) | 31/31 | `logs/07_globe_live_check.log`, `globe_check/` |
| **Full live U-04 audit** compared with the U-04 release run | **0 problems in all six views; functional tests unchanged** | `logs/08_audit_a11y.log`, `a11y_regression/`, `a11y_regression_compare.py`, `logs/09_a11y_regression_compare.log` |

**What the 42 mission checks cover** (Chrome headless, real API, real analyses):
- **Tab and loading:** Mission is listed first and Site stays the default; the dashboard chunk loads only on first open, without three.js.
- **Empty states:** each one is explained; unavailable navigation is disabled.
- **Status:** each status value equals `/api/status`.
- **Keyboard:** ArrowLeft from Site reaches Mission, and the tab list stays one tab stop.
- **Selected site and navigation:**
  - Site01 coordinates and levels equal `/api/coverage`.
  - 3D Moon, map and local terrain open the right view for the selected site.
  - The globe view and the site survive leaving and returning to the Site tab.
- **Analysis from the dashboard (Site01, 14–21 Nov):**
  - percentages equal the API summary, and durations equal the result view's figures;
  - the chips equal the API labels (1 Validated, 4 Pending);
  - uncertainty values equal the API's.
- **Deep links:**
  - the visibility chart, panorama and 3D terrain links open the same result with focus on the section, which is in view;
  - with reduced motion the jump is one step; by default the page scrolls smoothly through many positions.
- **Candidates:**
  - add, with no duplicate;
  - Select switches the site everywhere;
  - Analyse runs the analysis for (−89.9°, 0°);
  - the session table rows equal both API results;
  - Open result and Open reopen the right result;
  - Remove works.
- **Unsupported location (−30°, 10°):**
  - the backend's reason is shown, and analysis and terrain are disabled;
  - as a candidate it shows the reason, with Analyse disabled.
- **Error state:** with `/api/coverage` blocked, "Coverage could not be checked" is shown and analysis stays disabled.
- **Missing data, real case (−60.02°, 0°, 14–15 Nov):**
  - "Horizon lower bounds: 49.6 % of bins" and "Earth-in-view time unknown: 1 d 0 h" come from the API result;
  - the terrain quantities stay Pending;
  - the 3D terrain message covers its pane, opaque and on top at five sample points.
- **Comparison:** Compare candidates opens the Compare tab; after a 2 × 2 run the dashboard reports "2 sites × 2 windows compared." and links back to it.
- **Public mode:** the tables link is hidden (that section does not exist in public mode).
- **Accessibility:** all 27 controls are named, ids are unique, there is one h1 with six labelled h2 regions, the table has a caption, and the focus indicator is visible.
- **390 px:** no sideways scroll, the cards stack, and only the table scrolls inside its box.
- **Errors:** no page exceptions or console errors (only the deliberately blocked request is excluded).

**Accessibility regression** (`logs/09_a11y_regression_compare.log`):
- **Tab stops:** identical to Prompt 3 (welcome +2, result view +3 over the release); the new tab adds no tab stop.
- **Panorama readout:** equivalent (release text kept, σ and near field appended).
- **Functional tests:** all others the same.
- **Section ids:** the deep-link ids added to the result view change no tab stop; `tabindex="-1"` is set only on a section the user deep-links to.

## 4. Notes from testing
- **Deep links and layout:** the first deep-link version scrolled at the first frame and ended up to 104 px off, because the result view's layout was still changing (chart widths, lazy panes). Scrolling now waits for 12 unchanged frames, at most about 2 s.
- **Status dot:** in the status card the dot beside the wrapped terrain-products line was squeezed. It now keeps its size and aligns to the first line. The mobile padding now matches the page header.
- **Interrupted session:** the session was interrupted while the globe check, audit and comparison were running. Their logs (`07`–`09`, written 03:50–03:57) show the runs completed with exit 0. All source files predate the build (03:38) used by every live run, so the resumed session verified these runs instead of repeating them.

## 5. Limitations
- **Audit scope:** the full live U-04 audit covers its six release views. The dashboard is covered by the mission check's accessibility checks and the static a11y check, not yet by the full live audit (contrast, target size, 320 px reflow and text spacing for the Mission view). Recommended when U-04 is re-registered.
- **Session history:** the analyses list is held in memory for the browser session only, and is cleared on reload. Results stay retrievable from the API by id.
- **Leaving a result:** going from the dashboard to the explorer closes the open result, which can be reopened from the session list.
- **Existing sidebar behaviour (unchanged):** typing new coordinates keeps a previously entered site name.
- **Browser coverage:** tested in Chrome headless only.
- **Official report:** U-04 and U-06 there still describe the pre-Phase 5 build; re-registration is recommended, as noted in Prompts 1 to 3.

## 6. Files changed
| File | Change |
| --- | --- |
| `frontend/src/components/MissionView.tsx` | **new**: mission dashboard |
| `frontend/scripts/mission-live-check.mjs` | **new**: live check against the API responses |
| `frontend/src/state/store.tsx` | `mission` tab; explorer view (`siteView`) and session results (`history`, `historyItem`) in the store |
| `frontend/src/components/SiteView.tsx` | explorer view read from the store; section ids for deep links (`RESULT_SECTIONS`); `LabelChips` exported |
| `frontend/src/components/Terrain3D.tsx` | markers hidden until terrain and vectors exist; message is an opaque status overlay |
| `frontend/src/components/Welcome.tsx` | readiness rows exported (`readinessRows`) for the status card; output unchanged |
| `frontend/src/components/TopBar.tsx` | Mission tab first in the tab list |
| `frontend/src/App.tsx` | Mission panel, lazy-loaded with loading and failure fallbacks |
| `frontend/src/i18n/en.ts` | `mission` section and `topBar.tabs.mission` (593 → 654 keys) |
| `frontend/src/styles/app.css` | dashboard styles; `.pane-message` overlay |
| `frontend/scripts/check-strings.mjs` | allow-list entry for the API status word "Validated" compared in MissionView (as for SiteView and CompareView) |
| `frontend/dist/` | rebuilt; hashes in `logs/dist_before_sha256.txt` and `logs/dist_after_sha256.txt` |

**Not changed:**
- backend code;
- algorithm 1.5.0, code `5bf9753f…`, suite `1632af16…` and terrain acceptance `e48eb8ed…` (`logs/backend_fingerprints_after.txt`, identical to Prompt 3);
- `backend/validation/report.json` (`2279606c…`);
- Phase 4 and Prompt 1–3 evidence (every `SHA256SUMS` verified);
- `package.json` and the lock file.

No dependency was installed and no Git operation was run.
