"""IB-5: build the inventory tables from the raw JSON and the copied licence texts (no network).

Obligations and restrictions are never inferred from a licence name: they are the clauses found verbatim in the
licence file that ships with the package. A package without a licence file gets "unresolved".
    python gen_tables.py <evidence_dir>
"""
import csv
import json
import re
import sys
from pathlib import Path

E = Path(sys.argv[1])
raw = E / "raw"
lic = E / "licence_texts"
py = json.loads((raw / "python_inventory.json").read_text())
npm = json.loads((raw / "npm_inventory.json").read_text())
vite = json.loads((raw / "vite_modules.json").read_text())
dlls = json.loads((raw / "dll_version_resources.json").read_text())

# clause -> label; detected verbatim (case-insensitive, whitespace-normalised) in the shipped licence text
OBLIGATIONS = [
    ("shall be included in all copies or substantial portions", "keep copyright + permission notice in all copies (MIT-style clause)"),
    ("redistributions in binary form must reproduce the above copyright", "binary redistribution must reproduce copyright, conditions and disclaimer (BSD-style clause)"),
    ("appear in all copies", "copyright and permission notice must appear in all copies (ISC/HPND-style clause)"),
    ("you must give any other recipients of the work or derivative works a copy of this license", "give recipients a copy of the Apache License; keep NOTICE attributions (Apache-2.0 clause 4)"),
    ("each copy contains the above copyright notice and this license", "each copy of the fonts must carry the copyright notice and the OFL (OFL-1.1 condition 2)"),
    ("this source code form is subject to the terms of the mozilla public license", "MPL-2.0 file-level terms"),
    ("mozilla public license", "MPL-2.0 terms (file-level copyleft for covered files)"),
]
RESTRICTIONS = [
    ("neither the name", "no endorsement using the authors' or contributors' names"),
    ("may not be used in advertising", "names may not be used in advertising/publicity"),
    ("not be used in advertising or publicity", "names may not be used in advertising/publicity"),
    ("gnu general public license", "mentions the GNU GPL (read the file for what it applies to)"),
    ("gnu lesser general public license", "mentions the GNU LGPL (read the file for what it applies to)"),
    ("gcc runtime library exception", "GCC Runtime Library Exception referenced"),
    ("reserved font name", "OFL Reserved Font Name rules may apply to modified fonts"),
]
norm = lambda s: re.sub(r"\s+", " ", s.lower())


def scan(paths):
    text = " ".join(norm(p.read_text(errors="replace")) for p in paths if p.is_file())
    ob = sorted({lab for k, lab in OBLIGATIONS if k in text})
    rs = sorted({lab for k, lab in RESTRICTIONS if k in text})
    return ob, rs


def first(lines):
    return lines[0] if lines else ""


# ---------------------------------------------------------------- Python
rows = []
for d in py["distributions"]:
    files = [lic / "python" / d["key"] / f for f in d["license_files_in_record"]]
    ob, rs = scan(files)
    scope = "direct (requirements.txt)" if d["direct"] else ("transitive" if d["in_dependency_closure"] else "environment tooling (not required)")
    declared = d["license_expression"] or d["license_field"] or "; ".join(c.split("::")[-1].strip() for c in d["license_classifiers"]) or ""
    src = "License-Expression" if d["license_expression"] else ("License field" if d["license_field"] else ("classifier" if d["license_classifiers"] else "none"))
    urls = [u.split(",", 1)[-1].strip() for u in d["project_urls"]]
    q = []
    if not files:
        q.append("no licence file in the wheel")
    rows.append({"name": d["name"], "version": d["version"], "scope": scope, "required_by": " ".join(d["required_by"]),
                 "declared_licence": declared, "declared_in": src,
                 "copyright_holder (first notice in licence file)": first(d["copyright_lines"]),
                 "licence_files (site-packages relative)": "; ".join(d["license_files_in_record"]),
                 "source_url": d["home_page"] or (urls[0] if urls else ""),
                 "attribution_obligations (clauses found in file)": "; ".join(ob) or ("unresolved" if not files else "none detected"),
                 "restrictions (clauses found in file)": "; ".join(rs),
                 "unresolved": "; ".join(q)})
with open(E / "inventory_python.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)

# ---------------------------------------------------------------- native binaries vendored in wheels
LICENCE_SHIPPED = {  # verified: which shipped licence file covers the binary (by reading those files)
    "rasterio.libs/gdal": "rasterio/gdal_data/LICENSE.TXT (GDAL/OGR licensing; version resource says 'See LICENSE.TXT')",
    "rasterio.libs/proj_9": "rasterio/proj_data/copyright (PROJ MIT-style terms)",
    "pyproj.libs/proj_9": "pyproj-3.8.0.dist-info/licenses/LICENSE_proj; pyproj/proj_dir/share/proj/copyright",
    "numpy.libs/libscipy_openblas64_": "numpy-2.5.4.dist-info/licenses/LICENSE.txt (OpenBLAS BSD-3-Clause; LAPACK BSD-3-Clause-Open-MPI; GCC runtime GPL-3.0-or-later WITH GCC-exception-3.1)",
    "llvmlite/binding/llvmlite": "llvmlite-0.50.0.dist-info/licenses/LICENSE (BSD, Anaconda) + LICENSE.thirdparty (LLVM: Apache License v2.0 with LLVM Exceptions)",
}
nrows = []
for r in dlls:
    stem = re.sub(r"-[0-9a-f]{32}\.dll$|\.dll$", "", r["file"])
    v = r["version_resource"]
    covered = LICENCE_SHIPPED.get(stem, "")
    nrows.append({"file": r["file"], "bytes": r["bytes"], "sha256": r["sha256"],
                  "product (version resource)": v.get("ProductName", ""),
                  "version (version resource)": v.get("ProductVersion", v.get("FileVersion", "")),
                  "LegalCopyright (version resource)": v.get("LegalCopyright", ""),
                  "licence text shipped with wheel": covered or "NONE",
                  "status": "verified (licence file shipped)" if covered else "UNRESOLVED: no licence text for this library in the wheel"})
with open(E / "inventory_native_binaries.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(nrows[0]))
    w.writeheader()
    w.writerows(nrows)

# ---------------------------------------------------------------- npm
shipped = set(vite["shipped_with_rendered_code"]) | {"@fontsource-variable/archivo"}
mrows = []
for p in npm["packages"]:
    if not p["installed"]:
        continue
    files = [lic / "npm" / p["path"].replace("node_modules/", "") / f for f in p["licence_files"]]
    ob, rs = scan(files)
    top = p["path"] == "node_modules/" + p["name"]
    role = ("shipped in browser bundle" if top and p["name"] in shipped else
            "runtime dependency, not in bundle (tree-shaken or unused)" if not p["dev"] else "build/dev tooling only")
    mrows.append({"name": p["name"], "version": p["version"], "path": p["path"], "role": role, "direct": p["direct"],
                  "declared_licence (package.json)": p["package_json_license"] or "", "lockfile_licence": p["lock_license"] or "",
                  "copyright_holder (first notice in licence file)": first(p["copyright_lines"]),
                  "licence_files": "; ".join(p["licence_files"]), "source_url": p["repository"] or p["homepage"] or "",
                  "attribution_obligations (clauses found in file)": "; ".join(ob) or ("unresolved" if not files else "none detected"),
                  "restrictions (clauses found in file)": "; ".join(rs),
                  "unresolved": "no licence file in the installed package" if not files else ""})
order = {"shipped in browser bundle": 0, "runtime dependency, not in bundle (tree-shaken or unused)": 1, "build/dev tooling only": 2}
mrows.sort(key=lambda r: (order[r["role"]], r["name"]))
with open(E / "inventory_npm.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(mrows[0]))
    w.writeheader()
    w.writerows(mrows)

summary = {
    "python": {"distributions": len(rows), "direct": sum(r["scope"].startswith("direct") for r in rows),
               "transitive": sum(r["scope"] == "transitive" for r in rows), "tooling": sum(r["scope"].startswith("environment") for r in rows),
               "without_licence_file": [r["name"] for r in rows if r["unresolved"]]},
    "native_binaries": {"total": len(nrows), "licence_shipped": sum(r["status"].startswith("verified") for r in nrows),
                        "unresolved": [r["file"] for r in nrows if r["status"].startswith("UNRESOLVED")]},
    "npm": {"installed": len(mrows), **{k: sum(r["role"] == k for r in mrows) for k in order},
            "without_licence_file": [f"{r['name']}@{r['version']} ({r['role']})" for r in mrows if r["unresolved"]],
            "shipped_restrictions": {r["name"]: r["restrictions (clauses found in file)"] for r in mrows if r["role"].startswith("shipped") and r["restrictions (clauses found in file)"]}},
}
(E / "raw" / "summary.json").write_text(json.dumps(summary, indent=1))
print(json.dumps(summary, indent=1))
