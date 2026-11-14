# Landing tab: blank space below "Selected landing site" and "Terrain analysis" (2026-11-14)

**Scope:** Landing tab layout only. No other tab, component, data or scientific value changed. Phase 7 has not been started.

## Root cause
In the two-column layout (wider than 1100 px), the four main Landing cards sat in two separate CSS grids of two columns each. A grid row is as tall as its tallest item, and each card kept its natural height (`align-items: start`). So the shorter card of each row left the rest of the row empty below it:

| Row | Left card | Right card | Blank below the shorter card (1440 px, after a screening) |
|---|---|---|---|
| 1 | Selected landing site, 625 px | Hazard map, 970 px | **359 px** below Selected landing site |
| 2 | Landing footprint, 1533 px | Terrain analysis, 894 px | **655 px** below Terrain analysis |

**Ruled out:**
- **Inside the cards:** none had a fixed height or `min-height`. The space inside each card below its content was 15 px, which is its own bottom padding.
- **Margins:** not the cause.
- **One column (1024 and 390 px):** both cards already had the normal 16 px gap (`before/spacing-before.json`).

## Fix (files: `frontend/src/components/LandingView.tsx`, `frontend/src/styles/landing.css`)
- **Two independent columns.** On two-column screens (`min-width: 1101px`, the same breakpoint at which `landing.css` switches to one column), the cards are laid out as two independent column stacks inside one `landing-grid landing-band`:
  - left: Selected landing site above Landing footprint;
  - right: Hazard map above Terrain analysis.
  
  Each card follows the one above it with the 16 px gap, so none inherits a neighbour's height.
- **Leftover height.** When the left stack is taller, the remaining height goes to the hazard map's display area instead of blank space. This uses `.landing-mapcard.has-map` and its `.landing-map` pane `flex: 1 0 auto`; the map's existing minimum height `clamp(360px, 58vh, 620px)` is unchanged. The map card is the only card with a resizable display area, and OpenLayers follows its container size.
- **Below 1101 px:** the original single-column markup and order are kept (site, map, footprint, terrain), so the DOM, focus and visual order are unchanged on tablets and phones.
- **Markup:** the four cards are unchanged; they were moved into variables (`siteCard`, `mapCard`, `footprintCard`, `terrainCard`) so both layouts render the same elements.
- **CSS:** the new classes (`landing-band`, `landing-col`, `has-map`) are Landing-only. `.landing-grid`, which the Comms tab also uses, is unchanged.

## Results (`before/` and `after/`: JSON measurements and screenshots; `scripts/spacing_body.mjs`)

| Width | Card | Blank below, before | Blank below, after |
|---|---|---|---|
| 1440 | Selected landing site | 359 px | **16 px** |
| 1440 | Terrain analysis | 655 px | **16 px** |
| 1440 | Landing footprint, hazard map | 16 / 14 px | 16 / 16 px (map card 970 → 1264 px; its map area took the leftover height) |
| 1024 | all cards | 16 px | 16 px (identical measurements) |
| 390 | all cards | 16 px | 16 px (identical measurements) |

- **Every width, before and after a screening:** no overlapping cards, no horizontal page scroll, card contents fit (15 px bottom padding), 0 console errors.
- **Before a screening:** the site card and the "Hazard map" placeholder are unchanged.

## Checks
- `tsc --noEmit`: 0 errors.
- `npm test`: strings 1366 keys, 0 problems; accessibility 40 components and 52 colour pairs, 0 problems; check-moon-geo 238,972 checks.
- `npm run build`: OK.
- `check-bundle`: initial JS 313.7 KB, unchanged.
- **Browser measurement:** one headless browser at 1440, 1024 and 390 px, before and after a screening at the Site01 point.
- **Files:** only the two files above differ from the Phase 6 final frontend (`logs/frontend_files_sha256_after.txt`). The Comms files are byte-identical. The backend fingerprints and `report.json` hash are unchanged (`logs/backend_fingerprints.txt`).
- **Not run** (left for Phase 7): full live browser checks, rendered contrast, keyboard review.
