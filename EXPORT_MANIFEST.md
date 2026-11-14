# Export manifest: public GitHub export of LUNA-OPS

| Item | Value |
|---|---|
| Source project | local working copy (not modified by the export; read only) |
| Export folder | `LUNA-OPS-GITHUB-EXPORT` |
| Intended repository | https://github.com/Madhuanbarasu/NASA-SPACE-APPS-2026 (public) |
| Export date | 2026-11-14 |
| Git | Not initialised; nothing pushed |
| Size | **4,753 files, about 529 MB** (excluding `.git`). 477.5 MB of that is PNG screenshots in `docs/validation_evidence/`; code and documentation are about 4 MB. |
| Largest file | 1.6 MB. No file is larger than 25 MB, and none exceeds GitHub's 50 MB warning or 100 MB limit. |

## 1. What is included

- **Source code** (byte-identical to the working copy, checked with `diff -r`):
  - `backend/` without the virtual environment and caches;
  - `frontend/` without `node_modules` and `dist`, including the 2026-11-14 Landing hazard map repair and every current interface feature;
  - `start.py`, `scripts/`, `staging_a5/` and `staging_240m/` (download and verification scripts with their reports);
  - `.github/workflows/ci.yml`.
- **Data manifests and registries only:**
  - `data/dem/registry.json`;
  - `data/kernels/lock.json`;
  - `data/landing/manifest.json`;
  - `data/comms/manifest.json`;
  - empty `.gitkeep` placeholders.
- **Validation:**
  - `backend/validation/` with reference metadata;
  - the historical `report.json` (sha256 `8c03ebaf…`, unchanged) and `report.json.bak_5135efe8`;
  - all evidence folders in `docs/validation_evidence/` (unchanged).
  - The two evidence checksum manifests checked in the export pass: Phase 7, 329/329; landing repair, 54/54.
- **Preserved outcomes.** **V-10 remains FAILED.** The Phase 7 interim report contains `"V-10": {"status": "failed"}`. No validation outcome, label, criterion or evidence file was changed.
- **Documentation:** `LICENSE`, `ATTRIBUTION.md`, `docs/AUDIT_2026-11.md`, `docs/TRACEABILITY.md`, `docs/screenshots/`.

## 2. Changes made in the export only

| Change | Why |
|---|---|
| New `README.md` | The previous README described the validation status of 2026-11-12, before Phase 7. The new one states the current status (V-10 Failed, pytest skipped, no Validated label). It keeps setup steps 1–5 and the CI section word for word; the interface refers to "README, step 4". |
| Previous README moved to `docs/TECHNICAL_REFERENCE_2026-11-12.md` | Kept as the detailed technical reference, with a note at the top saying its validation status is out of date. Text below the note is unchanged. |
| New `PROJECT_FEATURES.md`, `PRESENTATION_SOURCE_GUIDE.md`, `EXPORT_MANIFEST.md` | Requested documents |
| New `docs/screenshots_current/` (17 PNG) | Copies of the latest screenshots from the evidence folders (the originals stay in place), plus 3 captured on 2026-11-14 for the README (south polar map, 3D Moon globe, local terrain 16 km ×4) |
| `data/comms/gm_de440.tpc` removed | NAIF kernel. Not redistributed under licence decision D5. Its URL and SHA-256 are in `data/comms/manifest.json`, and README step 6 shows how to download it. |
| `data/cache/.gitkeep` added (empty) | Keeps the folder, as in the original repository |

## 3. Excluded (8.26 GB)

| Excluded | Files | Size | Reason |
|---|---|---|---|
| `data/dem/` terrain rasters: PGDA 90 20 m, 80 m, 240 m DEMs and error maps; PGDA 78 Site01 DEM and error map | 8 | 7,307 MB | NASA LOLA data: large, not redistributed (D5). Download via README step 3; checksums are in `registry.json`. |
| `data/dem/registry.json.bak_synthetic` | 1 | < 0.1 MB | Old registry backup for synthetic terrain; not needed |
| `data/reference_validation/` (PGDA LPSR, PDS LOLA 2017 40 m LDEM/LDEC, other reference rasters) | 11 | 420.5 MB | Unresolved redistribution terms; must never be committed (`.gitignore`, IB-5/D5). Includes 3 files over 50 MB. |
| `backend/.venv/` | 6,829 | 382.0 MB | Python virtual environment (recreate from `backend/requirements.txt`). Contains `llvmlite.dll`, 114.8 MB. |
| `frontend/node_modules/` | 7,394 | 116.9 MB | npm packages (`npm ci`) |
| `data/cache/` (runtime results, horizons, `cache.sqlite`) | 162 | 48.7 MB | Server cache: regenerated, and it holds local analysis history |
| `data/landing/pgda78_site01/` (LDEC count, slope, slope error) | 3 | 117.3 MB | NASA PGDA 78 data; URLs and SHA-256 are in `data/landing/manifest.json` |
| `data/kernels/` (DE440s, lunar PCK/FK, LSK, PCK00011, DE421 files) | 7 | 45.3 MB | NAIF kernels, not redistributed; `python -m lunaops.acquire kernels` installs them. `lock.json` is kept. |
| `data/comms/gm_de440.tpc` | 1 | 12 KB | NAIF kernel (see section 2) |
| `frontend/dist/` | 30 | 2.3 MB | Build output; `start.py` or `npm run build` recreates it |
| `.git/` | 147 | 2.6 MB | Git history; a fresh repository is intended |
| `__pycache__/` (11 folders), `.pytest_cache/`, `frontend/tsconfig.tsbuildinfo` | about 280 | 9.8 MB | Bytecode and tool caches |
| `staging_a5/temp/`, `staging_240m/temp/` | 0 | 0 | Empty scratch folders |

**Files larger than 50 MB in the original project (10), all excluded:**
- `LDEM_80S_20MPP_ADJ_ERR.TIF` (3,771.5 MB)
- `LDEM_80S_20MPP_ADJ.TIF` (2,571.2 MB)
- `LDEM_60S_240MPP_ADJ_ERR.TIF` (254.6 MB)
- `LDEM_80S_80MPP_ADJ_ERR.tiff` (243.0 MB)
- `LDEM_60S_240MPP_ADJ.TIF` (208.8 MB)
- `LDEM_80S_80MPP_ADJ.tiff` (180.4 MB)
- `LPSR_80S_20MPP_ADJ.TIF` (147.1 MB)
- `llvmlite.dll` (114.8 MB)
- `ldem_85s_40m.img` (109.7 MB)
- `ldec_85s_40m.img` (54.9 MB)

## 4. Security review (public repository)

| Check | Result |
|---|---|
| `.env` / `.env.*`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `id_rsa*`, credential files | **None found** in the project (outside dependency folders) or in the export |
| High-confidence secret formats | **None found.** Searched: AWS keys, GitHub tokens (`ghp_`, `github_pat_`, `gho_`), Slack tokens, OpenAI/Anthropic keys, Google API keys, private-key blocks, JWTs, URLs with embedded credentials. |
| Literal assignments of password, secret, API key or token | **None found** (licence texts and lock files excluded from the search) |
| CI workflow | Uses no repository secrets |
| Email addresses | Only public ones: package authors in licence texts and npm/Python inventories, and NASA/JPL contacts in published data headers. **The owner's email is not present.** |
| Private IP addresses or internal hostnames | None |
| Databases or local history | `data/cache/cache.sqlite` and the analysis cache excluded |
| Absolute machine paths in code and config | Only Chrome install-path defaults in browser test scripts and one example download path in a docstring. `data/dem/registry.json` uses relative paths. |
| API exposure | The server accepts browser requests only from local origins. Nothing in the export is a deployed service. |

### Personal information still present: owner decision needed

These are records, not branding. They were reviewed in the 2026-11-11 hackathon cleanup (`docs/validation_evidence/hackathon_cleanup_2026-11-11/README.md`) and deliberately kept:

| Where | What | Can it be changed? |
|---|---|---|
| `backend/validation/reference/terrain_acceptance.json` (approver ×6, source ×3) | The owner's name as approver of the Phase 4 terrain acceptance, and the GitHub user name | **No.** Its SHA-256 gates the V-11/V-12 results, and editing it would invalidate them. |
| `backend/tests/test_phase4_terrain_gate.py` (lines 162, 170) | The same name, asserted by a test | **No.** It is part of the suite fingerprint. |
| `docs/validation_evidence/terrain_a6_2026-11-10/ACCEPTANCE.md` | Human-readable acceptance record | Evidence; keep |
| `docs/validation_evidence/hackathon_cleanup_2026-11-11/README.md` | Lists the names that were searched for | Evidence; keep or redact |
| 6 evidence logs and notes with the Windows user-profile path (`C:\Users\<name>\AppData\...`):<ul><li>`docs/AUDIT_2026-11.md`</li><li>`c10_2026-11-11/hardcoded_scan_baseline.json`</li><li>`luna_ops_2_phase1_2026-11-13/logs/server_final.log`</li><li>`luna_ops_2_phase1_2026-11-13/logs/21_u04_compare_attempt1.log`</li><li>`phase4_closure_2026-11-11/checks.log`</li><li>`scientific_validation_followup_2026-11-14/logs/server.log`</li></ul> | A Windows user folder name in temporary-file paths | **Not changed in this export.** Redacting would make those evidence folders' SHA256SUMS entries fail. It can be done on request, with the affected entries listed. |

No other personal data was found. Screenshots show only the application (no desktop, browser profile or account).

## 5. Before uploading

- **Use the Git command line or GitHub Desktop.** The GitHub web uploader accepts at most 100 files per upload, and this export has 4,753 files.
- **`.gitignore` (unchanged from the project) ignores `backend/validation/report.json`.** A normal `git add .` therefore leaves out the historical report. Use `git add -f backend/validation/report.json` if it should be published. The Phase 7 interim report in `docs/validation_evidence/` is not ignored.
- **About 478 MB of the 527 MB is evidence screenshots.** This is within GitHub's recommended repository size (under 1 GB). Pruning can be done on request.
- **Before every later commit**, check that `git status` lists no `.env`, `data/dem/*.tif`, `data/kernels/*.bsp` or `data/reference_validation/` files.

## 6. How the export was made

A script copied the project, reading only. It skipped the folders and patterns above, logged every exclusion with its size and reason, and refused to write into a non-empty destination. The tree was then scanned as described in section 4. The script and its log are in the export work folder, outside the repository.
