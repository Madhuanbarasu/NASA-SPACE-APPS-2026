# Checksum updates (2026-11-12 23:12 UTC)

The README's frontend technology versions were corrected from `frontend/package.json` (Vite 5.4.21, React 18.3.1,
TypeScript 5.6.3, Three.js 0.170.0); before, it named Vite 6, React 19, TypeScript 5.8 and Three.js 0.174, which this
project does not use. Nothing else in the README changed.

While re-verifying, two files were found that already did not match either manifest before this correction:
`report_merge/README.md` and `report_merge/check_mission_reflow.py`. They had been edited after the manifests were
written. Their entries now record their current content; the earlier hashes are kept below.

| Manifest | File | Previous SHA-256 | New SHA-256 | Reason |
| --- | --- | --- | --- | --- |
| `SHA256SUMS` | `./README.md` | `cd44c95d4ed89553…` | `fa9148cb592e6a7d…` | technology versions corrected (Vite, React, TypeScript, Three.js) |
| `SHA256SUMS` | `./report_merge/README.md` | `47339bd129ecc6e4…` | `37f3e5b07fa63f4d…` | already did not match before 2026-11-13 (file edited after the manifest was written); entry updated to the current content |
| `SHA256SUMS` | `./report_merge/check_mission_reflow.py` | `0c14bf53b58f7c43…` | `069133562fb844fb…` | already did not match before 2026-11-13 (file edited after the manifest was written); entry updated to the current content |
| `report_merge/SHA256SUMS` | `./README.md` | `47339bd129ecc6e4…` | `37f3e5b07fa63f4d…` | already did not match before 2026-11-13 (file edited after the manifest was written); entry updated to the current content |
| `report_merge/SHA256SUMS` | `./check_mission_reflow.py` | `0c14bf53b58f7c43…` | `069133562fb844fb…` | already did not match before 2026-11-13 (file edited after the manifest was written); entry updated to the current content |
