# UI change: navigation entry and Mission/Site validation badges removed (2026-11-14)

This is a presentation-only change, made at the owner's request. No backend, engine, validation, report, criteria, cache, dataset or earlier evidence file was changed.

## What changed

| # | Request | Change |
|---|---|---|
| 1 | Remove "Data and validation" from the navigation | It is removed from the tab list that both the desktop tabs and the compact menu use; 6 items remain. The Data view, its data and the report are unchanged. The app had no URL routes, so the view now opens from the address bar at `http://127.0.0.1:8000/#data`. While it is shown, the panel is named "Data and validation" and the first tab stays keyboard-reachable. |
| 2 | Mission: remove "Pending validation" indicators | Removed: the per-quantity status badges and the two lines beside them ("Validation labels now…", "A quantity stays Pending…"); the "Validation labels" metric in the status strip; the label chips on the current result; the "N validated, N pending" text in the candidate cards; and the "Labels" column of the history and comparison tables. The integrity note keeps its first sentence; "Pending validation means…" is removed. |
| 3 | Site: remove "Pending validation" indicators | Removed: the label chips above the result; the five per-figure badges (Disk visibility and Events, and the Power indicator); and the duplicate per-quantity Status column of the "Validation and provenance" table. The tests, reasons and provenance stay. The "Data key" sentence that pointed to the labels "shown above" is shortened. |

Other views are unchanged: Landing, Communication, Compare and Guide keep their own badges.

## Files modified

All under `frontend/src`; the originals are in `originals/`, and the line-level diff is `changes.diff` (80 changed lines):
- `components/TopBar.tsx`
- `App.tsx`
- `components/MissionView.tsx`
- `components/ResultWorkspace.tsx`
- `components/ResultContext.tsx`
- `i18n/en.ts`: removed dictionary keys that are now unused (`mission.labelsNow`, `labelsNote`, `colLabels`, `labelsByQuantity`, `stripLabels`, `stripLabelsValue`, `analysis.colStatus`) and shortened two sentences.

`frontend/dist` was rebuilt. The previous build is in `originals/dist_before/`.

## Checks

| Check | Result | Log |
|---|---|---|
| TypeScript (`tsc --noEmit`) | 0 errors | `logs/01e_typecheck.log` |
| `npm test` | Exit 0: check-strings 0 problems (1,365 keys), check-a11y 0 problems, check-moon-geo 238,972 passed, check-window 20/20 | `logs/02e_npm_test.log` |
| Production build | Exit 0. Bundle content hashes are identical to the build tested in the browser. | `logs/03e_build.log` |
| Browser check (one headless Chrome, existing server, Site01 7-day result) | **40/40 passed, 0 console errors** | `ui_check/ui_check.json`, `logs/05_ui_check.log` |

The browser check covers:
- **Navigation** at 1920/1440/1024/390/320 px: 6 items, no "Data and validation", including the compact menu where shown.
- **Layout:** the 6 views at 5 widths. No horizontal scroll, no element past the viewport, no clipped control, no overlapping cards, no empty boxes.
- **Badges:** Mission has 0 status badges, chips or pending text. Site has 0 "Pending validation" badges, chips or figure badges.
- **Data view:** `#data` opens it at all 5 widths (450 table rows).

Screenshots are in `ui_check/screenshots/`. The first browser run (`ui_check_run1/`, `logs/04_ui_check_run1.log`, 30/40) found the remaining Mission strip metric, the Mission and Site sentences and the Site validation-table Status column; those were then removed.

Site still contains one "Pending validation" phrase. It is in the explanatory note of the "Validation and provenance" section, which is text, not a badge.

## Scientific integrity (`backend_integrity.txt`)

- Engine fingerprint `9cd7b08b…` and suite fingerprint `70606628…`: unchanged.
- `backend/validation/report.json`: sha256 `8c03ebaf…`, unchanged.
- No backend file was modified.
- `/api/status` still reports no Validated label and 2 blockers. Nothing was marked Validated or Passed.

## Notes for later audits

The earlier browser test scripts (`shell-live-check`, `a11y-live-audit`, `responsive_body`) click `#tab-data`. They need `location.hash = '#data'` instead before they are run again.
