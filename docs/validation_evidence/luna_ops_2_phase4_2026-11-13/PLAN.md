# LUNA-OPS 2.0, Phase 4: Mission Dashboard (plan, awaiting approval)

## 1. Current state
`components/MissionView.tsx` (352 lines, loaded on demand, no WebGL and no map code) is one column of cards:
1. header;
2. a row of five text navigation buttons;
3. two cards: Selected site, and System status;
4. Current analysis (labels, five figures, uncertainty bullets, five section links);
5. Candidate sites (coverage per site from `/api/coverage`; Select, Analyse, Open result, Remove);
6. Analyses in this session (a table);
7. Comparison (a single status line);
8. integrity line.

Styling is Phase 1 only (`views.css`, the `.mission-*` rules). It doesn't yet use the Phase 3 instruments (`Metric`, `StatusBadge`, `SectionHeader`), and its section links predate the Phase 3 sections (Earth visibility, Validation).

**Data used** (all already in the store; nothing new is fetched except the existing per-candidate coverage):
- `/api/status`: readiness and label statuses;
- the store's site, coverage, `compareSites` (candidates), session `history` (each item: site, window, rules, summary, label words), the open or parked result, `comparison`, and job and error states.

**Phase 5 test hooks to keep:**
- section ids `mission-selected`, `mission-status`, `mission-current`, `mission-candidates`, `mission-history`, `mission-comparison`;
- `.mission-nav button`, `.mission-card`, `.mission-figures div > dt/dd` (labels such as "Sunlit time"), `.mission-flags li`, `.mission-links button`, `.label-row .chip`, `.explorer-coords`, `.hint[aria-live]`, `.mission-candidates li`, the history `tbody tr`.

**The rule that "no score, probability, ranking or recommendation" appears anywhere** (checked by `mission-live-check`).

## 2. Proposed dashboard

```
┌ Mission overview (eyebrow, h1, intro) ─────────────────────────────────────────────┐
│ STATUS STRIP: Kernels production · Terrain 4 LOLA products · Labels 1 validated / 4 pending │
│               · Candidates 2 · Session analyses 3 · Comparison 2 × 1 ready               │
│ QUICK ACTIONS: [3D Moon] [Polar map] [Local terrain] [Analysis] [Compare]  (icons + text) │
├──────────────────────────────────────────────┬──────────────────────────────────────┤
│ SELECTED SITE (focus card)                   │ SOUTH POLAR LOCATOR (schematic)       │
│ 89.463° S 222.510° E (mono, large) · name    │  polar plot -60°…-90°, 0° E at top   │
│ coverage: [5m][20m][80m][240m] finest 5m     │  ◉ selected  ○ candidates  · analysed │
│ [Inspect terrain] [Analyse] [Add as candidate]│  click a mark = Select that site      │
├──────────────────────────────────────────────┴──────────────────────────────────────┤
│ CURRENT ANALYSIS: site · window · status badges per label                          │
│  [Sunlit 100.0 %][Earth in view 0.0 %][Both 0.0 %][Longest dark 0 min][Longest Earth gap 7 d] │
│  uncertainty: unknown time, uncertain windows, near-field windows, lower-bound share, σ │
│  go to: Summary · Horizon · Timeline · Sunlight · Earth · Terrain · Validation · Tables │
├──────────────────────────────────────────────┬──────────────────────────────────────┤
│ CANDIDATE SITES (cards): coverage chips,     │ SYSTEM STATUS & VALIDATION            │
│  last session analysis (sunlit %, Earth %),  │  readiness rows; one badge per label  │
│  Select · Analyse · Open result · Remove     │  (API words); report date and profile │
├──────────────────────────────────────────────┴──────────────────────────────────────┤
│ ANALYSES IN THIS SESSION (table, mono numbers, label badges, Open)                 │
│ COMPARISON: status; when ready, each cell's sunlit % and Earth % (no score) · Open │
└ integrity statement ────────────────────────────────────────────────────────────────┘
```

- **Status strip:** counts and states read from the store and `/api/status` (kernel profile, terrain product count, label status counts, candidates, session analyses, comparison size). It reuses `Metric`.
- **Quick actions:** the existing five navigation buttons, with icons. Same targets and disabled rules.
- **Selected site:**
  - large monospace coordinates and the name;
  - coverage levels as chips with the finest product;
  - the existing actions: Inspect, Analyse, and Add (as candidate);
  - job progress and errors as now.
- **South polar locator (new, optional, decision 1):** a light SVG plot of the region south of 60°.
  - **Projection:** azimuthal equidistant (radius proportional to colatitude), oriented like the Phase 2 polar map (0° E up, 90° E right). It is labelled as schematic.
  - **Marks:** the selected site, the candidates and the analysed sites, with their names on hover and focus.
  - **Interaction:** choosing a candidate mark selects it (the same action as its Select button).
  - **No map or 3D code is loaded.**
- **Current analysis:**
  - **Status badges:** each label's validation status in the API's words, with the existing chips kept.
  - **Five figures:** the same fields and formatter as now, as `Metric` tiles in Sun, Earth and both colours.
  - **Uncertainty:** the same API fields as now, as flagged items.
  - **Section links:** now all eight Phase 3 sections (the data tables only in Technical mode).
- **Candidates:**
  - **Card grid:** coverage chips, a selected badge, and the existing actions.
  - **Last session analysis (decision 2):** each card shows the candidate's latest session analysis (sunlit %, Earth in view %, window) when one exists. These are read from the stored history item, as the history table already does.
- **System status and validation:**
  - the readiness rows (shared with the explorer);
  - one `StatusBadge` per label from `/api/status`, in the API's words;
  - the report date and kernel profile.
- **Session analyses:** the same table, restyled (monospace numbers, label counts, Open).
- **Comparison:**
  - status as now;
  - **when ready (decision 3):** a compact list of each cell's sunlit % and Earth-in-view %, side by side, from `cmp.cells`, with no combined value, and the link to the Compare tab.
- **Integrity statement:** kept. No score, probability, ranking or recommendation is added anywhere.

**Responsive layout:**

| Width | Layout |
| --- | --- |
| ≥ 1200 | two-column grid (focus card and locator; candidates and system status) |
| ≤ 1199 | the same, narrower |
| ≤ 900 | one column |
| ≤ 600 | the strip wraps into a 2 × 3 grid; quick actions wrap; the locator is 280 px |

## 3. Files
**Modified:**
- `components/MissionView.tsx`: restructure only; selection, analyse, open, deep-link and coverage logic unchanged;
- `i18n/en.ts`: new mission strings; existing texts kept;
- `styles/views.css`: the mission rules move out;
- `styles/app.css`: one import.

**New:**
- `components/MissionLocator.tsx`
- `styles/mission.css`

**Reused:** `ui/Metric`, `ui/StatusBadge`, `ui/SectionHeader`, `ui/ChartLegend`, `ui/Icon`, `components/ResultLabels` (`LabelChips`, `RESULT_SECTIONS`).

**Not touched:** backend, APIs, datasets, `report.json`, the store logic, and the explorer, analysis and comparison views.

## 4. Risks
- **Test coupling:** the hooks above are kept. These Phase 5 assertions will change:
  - `mission-live-check`: the number of `.mission-links` buttons (8 instead of 5) and of nav labels with icons (same text);
  - the a11y audit Tab count: new locator marks, and the section links.
- **Integrity wording:** new text must avoid "score", "probability", "rank" and "recommend" (the check's regex).
- **Locator accuracy:** the plot uses an exact azimuthal-equidistant formula. It is labelled as schematic, not to scale for distances, and gives no coordinates beyond the sites' own. It is checked numerically against the map's orientation with a small Node script.
- **Memory and size:** SVG only, inside the existing lazy dashboard chunk (about 13 KB now; expected about 22 KB). No new requests apart from the existing coverage lookups.

## 5. Order of work
1. **Baseline:** already saved (`baseline/`).
2. Mission styles and shell (status strip, quick actions, grid).
3. Selected site and current analysis.
4. Locator.
5. Candidates, then system status and validation.
6. Session analyses and comparison.
7. Responsive pass.
8. Gates: typecheck, `npm test`, build, bundle.
9. A short preview at 1440, 1024 and 390 px (empty state, with one result, with candidates and a comparison; cached results).
10. Evidence README and checksums.

## Decisions needed
1. **South polar locator:** include it (recommended) or leave it out.
2. **Candidate cards:** show the candidate's latest session analysis figures (recommended), or coverage only.
3. **Comparison panel:** a compact per-cell sunlit % and Earth % list (recommended), or the status line only.
