# Pre-Phase 7 audit, addendum (2026-11-14)

**What this is:** a follow-up review of the evidence from `../pre_phase7_audit_2026-11-14/`, plus one offline diagnosis of the map grid (AUD-06). It updates AUD-01, AUD-04, AUD-05 and AUD-06 and confirms that the Site tab "blank space" was a false positive. The detailed findings are in [`FINDINGS.md`](FINDINGS.md).

**Restrictions kept:**
- The original audit folder and its README were not changed. The original audit still verifies against its own `SHA256SUMS`.
- No application source code, CSS or configuration was changed.
- The code and suite fingerprints are unchanged (`logs/fingerprints_before.txt`, `logs/fingerprints_after.txt`). The files named in the findings have the same hashes before and after (`logs/source_hashes_before.txt`, `logs/source_hashes_after.txt`).
- The server was not restarted, and the browser audit was not rerun.
- Phase 7 was not started.

**How the evidence was produced:**
- The browser findings use only the saved `browser_run2/` results and screenshots.
- The map-grid diagnosis ran Python offline: it read the registered LOLA files and called the app's own tile-drawing function (`render_tile`) without the server. It is read only; the script output images went to the session scratchpad and `E:\Temp\LUNA-OPS\addendum_probe\`.
- The two scripts were run again for this addendum and gave the same numbers as the first investigation (`logs/`).

## How findings are classified
| Class | Meaning | Items |
|---|---|---|
| **Confirmed defect** | Reproduced or measured, with the cause traced to a specific file and code path. | AUD-01 invalid latitude; AUD-06 map grid; AUD-04 Landing 76 px gap (cosmetic) |
| **Possible issue** | Seen in the evidence, but the cause was not confirmed. More investigation is needed before calling it a defect. | AUD-05 lighter rectangle on the Landing hazard map |
| **False positive** | Reported by the audit script, but the evidence shows the application behaves correctly; the measurement was at fault. | Site tab "blank space" below the figure cards |

AUD-02, AUD-03 and AUD-07 are unchanged from the original report.

## Summary of confirmed defects
| ID | Severity | Responsible code | Recommended correction | Constraint |
|---|---|---|---|---|
| AUD-01 | Low | `frontend/src/components/Sidebar.tsx:38–39` (`Sidebar`: `coordsGiven`, `latBad`, `lonBad`); `frontend/src/state/store.tsx:252–264` (`StoreProvider`, coverage `useEffect`, check at line 256) | Use `parseSite` (`frontend/src/lib/moonGeo.ts:82`) in both places. Update the message `invalidCoordinates` (`frontend/src/i18n/en.ts:170`) to state the ranges. | Frontend only; no fingerprint impact |
| AUD-06 | Low (display only) | `backend/lunaops/api/tiles.py` `render_tile`, read at lines 83–86 (`boundless=True`) | Read the part of the window inside the file with `boundless=False`, and fill the rest with NaN | `tiles.py` is inside the fingerprinted engine. **Owner decision:** either accept a fingerprint change, or serve tiles from a separate package installed by `start.py`, as Landing and Communication are. |
| AUD-04 | Low (cosmetic) | `frontend/src/styles/landing.css:20–23` (`.landing-band`, `.landing-col`, the map card's grow rule); `frontend/src/components/LandingView.tsx:435–438` | Let the last card in each column grow, or accept the gap | Frontend only |

## Contents
| Path | What it is |
|---|---|
| `README.md` | This file |
| `FINDINGS.md` | Detailed updated findings, root cause and measurements |
| `images/tile_7_63_64_x3.png` | The server's own hillshade tile (zoom 7, tile 63/64, 56.8 m/px around Site01), enlarged 3× with no smoothing; the grid is visible |
| `images/lvl_20m.png` | The same tile area drawn from the 20 m product alone, read the way `tiles.py` reads it (3×); it shows the same grid |
| `scripts/ovr_probe.py` | The script that compares read methods (the root-cause measurements) |
| `scripts/level_probe.py` | Draws the tile from each LOLA level separately and scores the lines. `ovr_probe.py` takes its path as an argument; see `FINDINGS.md` for why. |
| `scripts/tile_probe.py` | Draws the server tiles around Site01 offline at zooms 6–8 (it produced the tile image) |
| `logs/ovr_probe_output.txt`, `logs/level_probe_output.txt` | Output of the two scripts when re-run for this addendum |
| `logs/layout_metrics_landing_site.json` | The Landing and Site layout measurements, the SITE-02 result, and the network and console entries, copied unchanged from `browser_run2/audit-results.json` |
| `logs/fingerprints_*.txt`, `logs/source_hashes_*.txt` | The no-change checks |
| `SHA256SUMS` | Checksums of every file above (LF line endings) |

The copies in `images/` and `scripts/` are byte-identical to the originals in the session scratchpad, which were left in place.
