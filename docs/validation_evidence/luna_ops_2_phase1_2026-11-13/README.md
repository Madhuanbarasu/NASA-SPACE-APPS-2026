# LUNA-OPS 2.0, Phase 1: Visual Foundation and UI Transformation (2026-11-13)

**Status: Phase 1 complete, with two live checks deferred.** On the final build, six of the eight browser checks passed. The map and end-to-end checks are **deferred, not passed** (see "Deferred checks").

**Verification history:**
- **First attempt:** this was stopped because the system was critically low on memory (about 2.8 GB free of 15.7 GB).
- **Disk:** drive C: then had 0 MB free.
- **Owner's decision:** use E: only and keep the files on C:. The 46 leftover `luna-*` browser profiles (about 1.94 GB) on C: were not deleted. All later runs used `TEMP`/`TMP` = `E:\Temp\LUNA-OPS`.
- **Final run:** there was one app server, and the checks ran one at a time.

## Approved scope
**In scope:** design system, global visual identity, navigation, responsive shell, reusable UI components, and foundational styling of every existing view.

**Approved decisions:**
- top tabs on desktop, with a compact menu on tablet and phone;
- a collapsible Mission Parameters sidebar;
- Archivo plus the system monospace, with no new font;
- both Technical and Public modes kept;
- deep links deferred.

**Not included:** Phases 2–5 (immersive globe and explorer, analysis and visualisation redesign, dashboard redesign, final release verification).

**Unchanged:** scientific calculations, APIs, data, validation labels and uncertainty statements.

## Protection of the stable state (before any change)
- **Baseline:** `baseline/` holds a copy of `frontend/src`, `scripts`, `public`, `index.html`, `vite.config.ts`, `package.json`, `package-lock.json` and `tsconfig.json`. It also holds their hashes (`frontend_files_sha256.txt`, 55 files), the build hashes (`dist_sha256.txt`) and the backend fingerprints with the report hash (`backend_fingerprints.txt`).
- **No Git:** no Git commands were used.
- **External backup:** not inspected.

## Documentation correction (requested)
- **README fix:** in `post_phase5_backend_and_ui_fixes_2026-11-12/README.md`, the frontend versions now read Vite 5.4.21, React 18.3.1, TypeScript 5.6.3 and Three.js 0.170.0, taken from `frontend/package.json`.
- **Checksums:** the folder's two manifests were updated.
- **Pre-existing mismatches:** two files already failed both manifests before this change (`report_merge/README.md` and `report_merge/check_mission_reflow.py`, edited after the manifests were written). Their entries were updated too. Every old and new hash is in that folder's `CHECKSUM_UPDATES.md`, and both manifests now verify.

## What changed
**Design system** (`frontend/src/styles/`): the single 432-line `app.css` is replaced by layers, with `app.css` kept as the entry point.
- **`tokens.css`:**
  - colour roles: deep-space surfaces at four levels, ice-white text, and one teal chrome accent for navigation and selection;
  - science colours unchanged in meaning and value (Sun gold, Earth blue, both cream, validated green, unknown/warning orange);
  - type scale with system-monospace telemetry, spacing, radii, depth, motion and layout tokens.
- **`base.css`:** reset, typography, focus ring, thin scrollbars, the `eyebrow` and `telemetry` utilities, and reduced motion.
- **`shell.css`:** command bar, navigation, Mission Parameters panel and drawer, workspace, breakpoints (1200 / 900 / 600 px).
- **`components.css`:** fields, segmented controls, buttons (amber primary, secondary, text toggles), panels, chips and tags, tables, notes, legends and the view header.
- **`views.css`:** every existing view restyled on the system. Telemetry numbers use monospace; the readiness list becomes a status board; the steps become numbered cards; the result view's sections become panels; Data and Guide become documents with section markers; Mission and Compare become panels. Layouts are kept, since their redesign belongs to Phases 2–4.

**Shell:**
- **`TopBar.tsx`:** the command bar has a Mission Parameters toggle, a brand mark, the primary tabs (WAI-ARIA, arrows, one tab stop) and a compact views menu below 1,200 px (open/choose/Escape, focus return). It also shows a UTC clock (decorative, hidden from assistive technology), a status pill whose labels stay readable by screen readers on small screens, and the mode switch.
- **`App.tsx`:**
  - **Wide screens:** the parameters are docked and collapsible, and the choice is remembered in this browser (`localStorage`).
  - **Below 1,200 px:** they open as a drawer, closed by default. Focus moves in; Escape, a press outside or the close button close it, and focus returns to the toggle.
- **`Sidebar.tsx`:**
  - **Panel header:** the panel has a header with a close button.
  - **Status line:** the screen-reader status line ("Results ready …") stays outside the hidden part, so it is announced while the panel is closed.

**Reusable components** (`frontend/src/ui/`):
- `ViewHeader`: eyebrow, the view's single h1, subtitle and actions; used by Mission, Compare, Data, Guide and the analysis result.
- `Icon`
- `BrandMark`
- `UtcClock`

Supporting hook: `lib/useMediaQuery.ts`.

**Strings:** `i18n/en.ts` gains a `shell` section (663 → 676 keys counted). Existing texts are unchanged.

**Gates and tools:**
- **`scripts/check-a11y.mjs`:** reads every stylesheet (tokens first) and checks 52 colour pairs, up from 33: text on the new `--space` surface, the teal accent as text and as indicator, the focus ring on the bar, and the input border on the sidebar.
- **`scripts/a11y-live-audit.mjs`:** every Tab walk now starts at the top of the page (see below).
- **`scripts/shell-live-check.mjs`:** new browser check for the shell.

**Class names:** all 1.0 class names that tests and audits address are kept.

## Results

| Check | Result | Build |
| --- | --- | --- |
| TypeScript | exit 0 | final (`logs/00`) |
| `npm test`: strings 676 keys, 0 problems; static a11y 25 components, 52 colour pairs, 0 problems; geometry 238,972 | exit 0 | final (`logs/01`) |
| Production build; bundle | exit 0; initial JS 326.9 KB / 102.9 KB gzip (+5.6 KB over the Phase 5 final build); 3D and map still lazy | final (`logs/02`, `logs/03`) |
| **Accessibility audit (U-04 method), 10 views** | **0 automated problems in every view**; Tab stops exactly the Phase 5 counts + 1 (the parameters toggle); 16 release and 4 Phase 5 functional tests unchanged | **final** (`logs/20`, `logs/21`, `u04_audit/`) |
| Live checks: shell 14/14, mission 42/42, visualisation 25/25, explorer 27/27, globe 31/31, globe targeting 9/9, map 21/21, end-to-end 16/16 | all passed | the build before the last three CSS-only fixes (`logs/*_pre_final_css.log`) |
| **Live checks on the final build:** shell **14/14**, mission **42/42**, visualisation **25/25**, explorer **27/27**, globe **31/31**, globe targeting **9/9** | **passed** (exit 0, no FAIL lines) | **final** (`logs/10`–`15_*_live_check.log`, `checks/`) |
| Live check on the final build: map (21 checks) | **deferred**: the run stalled with no output and was stopped; 0 of 21 completed | final (`logs/16_map_live_check_STALLED_empty.log`, `logs/16_17_stall_record.txt`) |
| Live check on the final build: end-to-end (16 checks) | **deferred**: it was never started (queued after the map check) | none |
| Served build | `index-ZnayDHTI.js`, `index-DCMBg5-B.css`; `frontend/dist` matches `logs/dist_after_sha256.txt` (17 files); the frontend source matches `logs/frontend_files_after_sha256.txt` (66 files) | final |

### Deferred checks (map and end-to-end)
**Map check (stalled):**
- **Start:** 2026-11-13 05:37:35 (node PID 21948, headless Chrome PID 3336).
- **Inspection:** at 17:30, about 11 h 53 min later.
- **Output:** the log was still 0 bytes and `checks/map/screenshots/` was empty.
- **Activity:** node and every Chrome process were at 0 % CPU, the DevTools socket was open but idle, and the server log had no activity after 05:37:37.

**Action taken:**
- Only the check chain was stopped (node and its Chrome exited with it).
- The app server was kept: PID 25476, listening on 127.0.0.1:8000, with `/api/status` returning HTTP 200.
- The empty log is kept as evidence.

**End-to-end check:** it was queued after the map check in the same chain and never started.

**Context, not a pass:** both checks passed on the build before the last three CSS-only fixes (map 21/21, end-to-end 16/16; `logs/16_map_live_check_pre_final_css.log`, `logs/17_e2e_live_check_pre_final_css.log`). Those fixes changed only:
- the amber button's background colour;
- the height of the short tables on the Data page;
- the welcome eyebrow's selector.

The checks were not repeated in this session. The commands to finish them are in `logs/16_17_stall_record.txt`.

**The last three fixes** (CSS only, after the passing check run):
- **Amber primary buttons:** a solid amber fill under their sheen (the audit had measured the dark label against the page, because the gradient left the background colour transparent).
- **Short Data tables:** shown in full, so the 7-row kernels table no longer becomes an inner scroll area and an extra Tab stop.
- **Welcome eyebrow:** a selector fix.

**Audit-tool note:**
- **Problem:** the release views' Tab walks used to start wherever the previous step had left the browser's focus starting point. With the new shell, Data started on a scrolling table, whose changing position meant the walk never closed (195 stops), and Guide on a date field (1 stop).
- **Fix:** all walks now start at the skip link, as the Phase 5 views already did.
- **Confirmation:** the resulting counts equal the expected ones exactly.
- **Kept:** attempts 1 and 2 are kept (`logs/*attempt*`, `u04_audit_attempt*`).

**Screenshots:**
- **Before:** `screenshots_before/` has every view at 1440, 1024 and 390 px.
- **First Phase 1 build:** `screenshots_iter1/`.
- **Shell states:** `shell_trial/` has docked, menu open, drawer open, 390 and 320 px.
- **Final set (final build):** `screenshots_after/` (log `logs/30_screenshots_after.log`) has 24 images:
  - every view at 1440, 1024 and 390 px;
  - the navigation states: desktop sidebar docked and collapsed, and the views menu open and parameters drawer open at 1024 and 390 px.
  - `shots-after.json` records no sideways scrolling at any size.
- **Not in the final set:** the `--essential` run left out the four desktop result screenshots, which need a new one-week Site analysis. That is the only long step, and it was skipped after the map check stalled. The earlier result-view images are in `screenshots_iter1/`.

**Unchanged (`logs/backend_fingerprints_after.txt` = `logs/backend_fingerprints_final.txt` = `baseline/backend_fingerprints.txt`; recomputed at the end):**
- backend code;
- algorithm 1.5.0, code `84cbd4ea…`, suite `1632af16…` and terrain acceptance `e48eb8ed…`;
- `backend/validation/report.json` (`8c03ebaf…`).

No dependency was added and no Git command was run.

## Notes for later phases
- **Data tables:** the Data page's tables still break long file names mid-word. This is a 1.0 rule that keeps tables inside the page at 320 px; it is left for the Phase 3 table redesign.
- **U-04/U-06 in the official report:** they still describe the build before Phase 1. Re-registration belongs to Phase 5.
