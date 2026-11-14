# Communication tab: four UI fixes (2026-11-14)

**Scope:** the Communication tab and its navigation label only. There is no backend, engine, data or scientific change, and Phase 7 has not been started.

**Files changed:**
- `frontend/src/components/CommsView.tsx`
- `frontend/src/styles/comms.css`
- `frontend/src/i18n/en.ts`: the tab label and three new link-budget notes.

All other files are unchanged (`logs/frontend_files_sha256_after.txt` against `baseline/`).

## 1 and 2. Blank space below "Selected lunar location" and "Hypothetical relay"
- **Root cause:** in the two-column layout (wider than 1100 px) the configuration cards shared two-column grid rows: Selected lunar location beside Direct to Earth, and Hypothetical relay beside RF link budget. A grid row is as tall as its tallest card, so the shorter card was left with blank space below it.
  - **Ruled out:** fixed heights, `min-height`, margins and padding. Each card's own empty space below its content was 15 px, which is its padding.
  - **Single column (1024 and 390 px):** already 16 px.
  - **Why no pairing works:** RF link budget is about 1,000–1,550 px tall in every state, while its partner (relay) is 116–980 px depending on whether the relay is on. No column pairing can balance that.

| Card (1440 px) | Card / row partner | Blank below, before | Blank below, after |
|---|---|---|---|
| Selected lunar location | 416 / 522 px | **122 px** | **16 px** |
| Hypothetical relay, relay off | 134 / 1547 px | **1429 px** | **16 px** |
| Hypothetical relay, relay on | 977 / 1547 px | **586 px** | **16 px** |

- **Fix:** the four configuration cards (location, direct to Earth, RF link budget, relay) are full width, like the rest of the Communication cards (timeline, comparison, planner, provenance). Each is sized by its own content, with the standard 16 px gap. Their contents use responsive columns inside the card:
  - transmitter, receiver and signal groups side by side;
  - the shortest-distance and longest-distance breakdown tables side by side;
  - the relay's orbital fields in a field grid.
  
  The phone layout and the reading order (site, direct, timeline, link budget, relay, …) are unchanged.
- **Measured** (`before/` and `after/` JSON): every card has 16 px below it at 1440, 1024 and 390 px, with the relay on and off. There are no overlapping cards and no horizontal page scroll. Card heights at 1440 px also dropped, for example RF link budget from 1547 to 1034 px.

## 3. RF link budget: "Lander to relay" and "Relay to Earth" did nothing
- **Root cause:** both buttons were rendered `disabled` whenever "Simulate a hypothetical relay" was off (`disabled={k !== "direct" && !inp.relayOn}`). The shared segmented-button style has no disabled appearance, so they looked active, but clicks did nothing and no reason was given. The click handler and the state switching were otherwise correct: with the relay on, both buttons worked before the fix.
- **Fix:**
  - **Always clickable:** the `disabled` condition is removed.
  - **Relay leg selected without a relay:** the leg's own form is shown (its inputs are kept in the store), with a note. The note explains that the leg's distance comes from a hypothetical relay's orbit, so it is evaluated only when a relay is simulated, and offers a "Simulate a hypothetical relay" button. That button does the same as the relay checkbox: it turns the relay on and prefills only the epoch.
  - **Relay on but orbit incomplete:** the note asks for the orbit to be completed.
  - **No invented values:** no result or hardware value is invented, and an unevaluated leg shows no breakdown.
- **Test results** (`after/comms-ui-after.json`, `buttons`):

| Step | Before | After |
|---|---|---|
| Relay off: click "Lander to relay" | `disabled`; active link stays "Direct to Earth" | clicked; active "Lander to relay"; form `cl-up-*`; relay note shown; no breakdown |
| Relay off: click "Relay to Earth" | `disabled`; active link stays "Direct to Earth" | clicked; active "Relay to Earth"; form `cl-down-*`; relay note shown |
| Relay on, illustrative values: up, down, direct, up, down, up | worked | worked: each click activates its link and shows its own form values (power 5, 50, 20 W) and results (margin −11.63 to −5.46 dB, 27.86 to 28.67 dB, 13.98 to 14.71 dB) |

The RF equations, units, labels, validation and "no default hardware values" rule are unchanged. The backend comms tests still pass: 57.

## 4. Navigation label "Comms" → "Communication"
- **Change:** `S.shell.tabs.comms` is now "Communication". The route and tab id (`comms`, `#tab-comms`), the component and the active state (`aria-selected`) are unchanged.
- **Inline tabs (1600 px and wider):** they end 32 px before the status area at 1600 px, with nothing clipped and no overflow.
- **Compact menu (below 1600 px):** the toggle shows "Communication".
- **Overflow:** none at 390, 1024, 1440, 1599, 1600, 1680 or 1920 px (`logs/07_topbar.log`, `after/screenshots/after-topbar-*.png`).

## Checks performed
- `tsc --noEmit`: 0 errors.
- `npm test`: strings 1369 keys, 0 problems; accessibility 40 components and 52 colour pairs, 0 problems; check-moon-geo 238,972 checks.
- `npm run build`: OK.
- `check-bundle`: initial JS 314.0 KB (101.4 KB gzip), up from 313.7 KB because of the new strings.
- `pytest lunaops_comms/tests`: 57 passed.
- **Browser measurement:** one headless browser at 1440, 1024 and 390 px, with the relay off and on. It covered card spacing, overlap, horizontal overflow, the buttons, the tab label and 0 console errors.
- **Engine:** fingerprints and `report.json` hash unchanged.

**Not performed** (left for Phase 7):
- full live browser suite and the live-check script updates (they still expect the label "Comms" if they assert it);
- rendered-contrast audit, keyboard and screen-reader review;
- U-04/U-06 audits.
