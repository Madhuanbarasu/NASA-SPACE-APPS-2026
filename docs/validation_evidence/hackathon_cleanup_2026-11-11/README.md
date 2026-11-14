# Hackathon readiness cleanup (2026-11-11)

**Goal:**
- remove personal-name branding and judge-facing development clutter from the visible application;
- keep the project name LUNA-OPS, every scientific function, the citations and acknowledgments, and the validation safeguards.

## 1. Personal-name branding

The repository was searched (excluding `node_modules`, `.venv` and copied licence texts) for `Thilakhaesh`, `Thilak`, `Madhu`, `Anbu` and `Anbarasu`. Email addresses and author/credit phrases were also searched in `frontend/src`, `frontend/index.html`, `frontend/package.json`, `README.md`, `ATTRIBUTION.md`, `LICENSE` and `start.py`.

- **Visible application: no personal name anywhere.** None in `frontend/src`, `frontend/index.html`, the built `frontend/dist` (JS, CSS and HTML checked), the welcome screen, the top bar or the Data page footer.
- **Project branding** is "LUNA-OPS" and "Lunar Landing Site Navigator". `LICENSE` reads "Copyright 2026 The LUNA-OPS team".
- **No change was needed in the UI.**

**Remaining occurrences, intentionally not changed** (they are records, not branding):

| Location | What | Why it stays |
| --- | --- | --- |
| `backend/validation/reference/terrain_acceptance.json` (approver ×6, source ×3) | Phase 4 A6 terrain acceptance record | A formal approval record. Its SHA-256 digest gates the merging of V-09…V-12; editing it would invalidate the V-11/V-12 production results. |
| `backend/tests/test_phase4_terrain_gate.py` (lines 162, 170) | Test asserting the recorded approver | A test (suite fingerprint); it must match the record. |
| `docs/validation_evidence/terrain_a6_2026-11-10/ACCEPTANCE.md` | Human-readable acceptance record | Existing evidence |
| `docs/AUDIT_2026-11.md` line 14 | A Windows user-folder path quoted while describing a fixed portability bug | Audit history |
| `docs/validation_evidence/c10_2026-11-11/hardcoded_scan_baseline.json` (`srcDir`) | A scratch-folder path containing the Windows user name | Existing evidence. It is not personal branding, but it can be redacted on request. |

None of these appear in the running application.

## 2. Judge-facing clutter

All interface text is in `frontend/src/i18n/en.ts` (C10), so it was reviewed in full. Searched for:
- requirement and tracking IDs: `C0x`/`C1x`, `VT-`, `IB-`, "Phase", "item N", "blueprint", "audit";
- README references, developer commands;
- placeholder, demo, debug and TODO text.

The API strings the interface displays as received (warnings, label reasons, job messages, catalogue reasons) were searched the same way in `backend/lunaops`. Matches there are docstrings only, which are never shown.

**Removed (1 item):**

| Where | Text shown to users | Why |
| --- | --- | --- |
| Compare page, next to the Compare button | "Team target: at least 4 sites × 3 windows (C01)." / "Meets the team target of at least 4 sites × 3 windows (C01)." | An internal requirement ID (C01) and team acceptance target, with no meaning for users. The comparison itself is unchanged: any number of sites and windows, the same matrix, metrics, CSV and cell links. The U-03/C01 capability is not affected. |

**Reviewed and kept on purpose:**

| Item | Why it stays |
| --- | --- |
| Validation label chips ("Pending validation" with reasons) and the Data page test table | Scientific safeguard (C06): shows what is and isn't validated |
| Provenance footer (engine, code, algorithm 1.5.0, fingerprint) | Requirement C03: reproducibility information |
| Kernel and terrain status pill; welcome readiness list | Tell the user whether real NAIF kernels and LOLA terrain are loaded |
| Synthetic-terrain warnings | Required so test terrain is never mistaken for lunar data |
| Data sources and attribution table; Guide | NASA/USGS citations and user help |
| "No terrain is registered… (README, step 3)" and "Run `python -m validation.run_validation` in backend" | Shown only on an unconfigured installation, as setup guidance; never visible on a configured demo |

## 3. Protected scope (unchanged)

The following were not touched:
- site selection and the polar map;
- horizon panorama, timeline, illumination and shadow figures, Earth visibility, the power indicator and the 3D terrain;
- site comparison;
- data, citations and acknowledgments;
- the Guide;
- all validation evidence, tests, the validation report and the terrain gate.

No backend file was modified. Backend fingerprints after the cleanup: code `5bf9753f…`, suite `1632af16…`, terrain acceptance `e48eb8ed…`, algorithm 1.5.0, all unchanged (`logs/backend_fingerprints_after.txt`).

## Changes

| File | Change |
| --- | --- |
| `frontend/src/components/CompareView.tsx` | Removed the target hint `<span>` and its `target` variable (−2 lines) |
| `frontend/src/i18n/en.ts` | Removed the strings `compare.targetMet` and `compare.target` (−2 lines) |
| `frontend/dist/` | Rebuilt (not tracked in git). New bundle `index-BrcnGpKY.js` (`logs/dist_before_sha256.txt`, `logs/dist_after_sha256.txt`) |

The exact diff is in `cleanup.diff`.

## Checks

| Check | Result | Evidence |
| --- | --- | --- |
| `npm run typecheck` | exit 0 | `logs/01_typecheck.log` |
| `npm test` (string-check self-test, then check) | self-test 37/37; 418 keys, 418 referenced, 0 problems | `logs/02_npm_test.log` |
| `npm run build` (tsc, string check, vite) | exit 0 | `logs/03_npm_run_build.log` |
| Rendered UI before vs after (C10 SSR harness, 54 scenarios) | 41 identical. 13 differ, all Compare views, and each differs **only** by removal of the C01 hint `<span>` (verified per scenario). 0 render errors | `ssr_equivalence/ssr_diff_summary.json` |
| Backend fingerprints and algorithm version | unchanged | `logs/backend_fingerprints_after.txt` |

**Note:** the C10 report (`../c10_2026-11-11/`) records 420 dictionary keys. After this cleanup there are 418, because the two removed strings were the only change.

## For the team to decide (not changed)

**`README.md` "Event rules" section.** It states that the code was written before the Space Apps 2026 start time (14 November 2026, 9:00 a.m. local) at the team's request, and should be treated as a non-competition build unless the Local Lead confirms otherwise. This is a rules disclosure, not clutter, so it was left as written. Whether and how to address it with the Local Lead is the team's decision.
