# Site tab: vertical spacing of "Events and intervals" and "Sunlight and illumination" (2026-11-14)

This is a presentation-only fix, made at the owner's request. One file changed: `frontend/src/styles/analysis.css`, 22 lines in one commented block. The original is in `originals/` and the diff is `changes.diff`. No backend, engine, validation, report, cache or dataset file was changed (see `backend_integrity.txt`).

## Root causes, measured before the change (`diagnosis/`, 1440 px)

Both sections place two columns in one CSS grid row. The row takes the height of the **taller** column, so the shorter column leaves an empty block beneath it. Nothing had a fixed height, a min-height or a stray margin.

1. **Events and intervals** (`.timeline-grid`: timeline | event list).
   - The event list column is a heading, a list allowed to grow to 380 px, and a note.
   - With several events it is taller than the timeline column (chart 160 px, legend, note and the "Intervals (n) Show" line; 275 px in total).
   - The difference shows as blank space under "Intervals (n) Show".
2. **Sunlight and illumination** (`.body-grid`: statistics card | chart; the Earth section uses the same layout).
   - The statistics card set nine metrics in two narrow columns, with labels wrapping to two or three lines ("WINDOWS A SUB-BIN PEAK COULD HIDE"). That made the card 422 px tall.
   - The chart column has a fixed aspect ratio, 351 px at 1440.
   - The result was about 71 px of blank space under the chart notes.

## Corrections (two-column layouts only; single-column layouts unchanged)

- **Timeline (≥ 1101 px):** the grid stretches its items. The event-list box uses `contain: size`, so its content no longer sets the row height. It is a flex column whose list fills the remaining height and scrolls (minimum box height 220 px). Expanding "Intervals" grows both columns together; collapsing restores them.
- **Sunlight / Earth (≥ 901 px):** each statistic is one label-value line in a single column (all nine are kept), with a 3 px gap and line-height 1.35. The grid stretches the card to the chart column's height.

No negative margins, hidden content or removed components.

## Verification (one headless browser on the existing server; `verify/`, `logs/09_verify.log`)

Two results were checked:
- **A:** 85.3305° S, 285.2104° E, 13–20 Nov 2026, with 3 rise and set events.
- **B:** Site01, the same window, with no events.

Each was checked at 1920, 1440, 1024, 390 and 320 px.

| Width | Timeline, two columns: blank under timeline / under event list | Sunlight: blank under chart / spare inside card | Intervals expand and collapse | Overflow, clipping |
|---|---|---|---|---|
| 1920 | 6 px (heading margin) / 0 px; list 168 px, scrolls | 0 / 2 px | OK | none |
| 1440 | 6 px (heading margin) / 0 px | 0 / 19 px | OK | none |
| 1024 | single column (list below the timeline) | 0 / 19 px | OK | none |
| 390 | single column | single column | OK | none |
| 320 | single column | single column | OK | none |

- Section padding below the content is 0 px slack in every case.
- No statistic label is clipped.
- There was no horizontal scroll and no console error.

Result: **10/10 after one documented re-evaluation.** The first evaluation of this run gave 8/10 (`verify.json`). The 2 rows failed only because 6 px under the timeline exceeded my 2 px threshold. Those 6 px are the intervals heading's own bottom margin (`.intervals-head { margin: 0 0 6px }`), unchanged; B shows the same 6 px. The re-evaluation is in `verify/verify_evaluated.json`, with the original verdicts kept.

An earlier run (`verify_run1/`, `logs/05_verify_run1.log`) showed the Sunlight gap reduced but not removed (25–42 px). That led to the tighter metric spacing. It also measured the intervals toggle by page position, which the screenshot scrolling invalidated; the run above judges it by size.

## Builds and tests

- `tsc --noEmit`: 0 errors.
- `npm test`: exit 0. check-strings and check-a11y found 0 problems.
- Production build: exit 0. Logs 06–08.
