"""IB-5: inventory of the backend Python environment from installed metadata only (no network, no installs).

Run with the project venv's interpreter in isolated mode:
    backend/.venv/Scripts/python.exe -I py_inventory.py <site-packages> <requirements.txt> <out.json> <licence_copy_dir>
"""
import json
import re
import shutil
import sys
from importlib import metadata
from pathlib import Path

site, reqfile, out, copydir = (Path(a) for a in sys.argv[1:5])
from packaging.requirements import Requirement  # noqa: E402  (packaging is installed in the venv)
from packaging.utils import canonicalize_name  # noqa: E402

LIC_RE = re.compile(r"(^|/)(licen[cs]e|copying|notice|copyright|authors|third[-_]?party|legal)[^/]*$", re.I)
COPY_RE = re.compile(r"^\s*(?:Copyright|\(c\)|©)\s.*", re.I | re.M)

direct = {}
for line in reqfile.read_text().splitlines():
    line = line.split("#")[0].strip()
    if line:
        r = Requirement(line)
        direct[canonicalize_name(r.name)] = str(r.specifier)

dists = {canonicalize_name(d.metadata["Name"]): d for d in metadata.distributions(path=[str(site)])}
records = []
for key, d in sorted(dists.items()):
    m = d.metadata
    files = [str(f) for f in (d.files or [])]
    lic_files = sorted({f.replace("\\", "/") for f in files if LIC_RE.search(f.replace("\\", "/")) and not f.endswith((".py", ".pyc"))})
    # requirements (no extras), evaluated for this platform
    reqs = []
    for r in m.get_all("Requires-Dist") or []:
        req = Requirement(r)
        if req.marker is None or req.marker.evaluate({"extra": ""}):
            reqs.append(canonicalize_name(req.name))
    copyrights, copied = [], []
    for lf in lic_files:
        p = site / lf
        if p.is_file() and p.stat().st_size < 5_000_000:
            text = p.read_text(errors="replace")
            copyrights += [c.strip()[:200] for c in COPY_RE.findall(text)]
            dest = copydir / key / lf
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, dest)
            copied.append(lf)
    classifiers = [c for c in (m.get_all("Classifier") or []) if c.startswith("License")]
    records.append({
        "name": m["Name"], "key": key, "version": m["Version"],
        "direct": key in direct, "pinned": direct.get(key),
        "license_field": (m.get("License") or "").strip()[:400] or None,
        "license_expression": m.get("License-Expression"),
        "license_classifiers": classifiers,
        "license_file_metadata": m.get_all("License-File") or [],
        "license_files_in_record": lic_files,
        "copyright_lines": list(dict.fromkeys(copyrights))[:60],
        "author": m.get("Author") or m.get("Author-email"), "maintainer": m.get("Maintainer") or m.get("Maintainer-email"),
        "home_page": m.get("Home-page"), "project_urls": m.get_all("Project-URL") or [],
        "requires": sorted(set(reqs)), "summary": m.get("Summary"),
    })

# transitive closure from the direct requirements
graph = {r["key"]: r["requires"] for r in records}
reach, stack, via = set(), list(direct), {}
while stack:
    k = stack.pop()
    if k in reach:
        continue
    reach.add(k)
    for c in graph.get(k, []):
        via.setdefault(c, set()).add(k)
        stack.append(c)
for r in records:
    r["required_by"] = sorted(via.get(r["key"], []))
    r["in_dependency_closure"] = r["key"] in reach

# vendored native libraries (delvewheel *.libs folders and in-package DLLs/PYDs)
libs = {}
for p in sorted(site.glob("*.libs")):
    libs[p.name] = sorted(f.name for f in p.iterdir())
for pkg in ("rasterio", "pyproj", "numpy", "numba", "llvmlite", "PIL", "spiceypy", "pydantic_core"):
    root = site / pkg
    if root.exists():
        libs[pkg + " (in package)"] = sorted({f.relative_to(site).as_posix() for f in root.rglob("*") if f.suffix.lower() in (".dll", ".so", ".dylib")})
data_dirs = {pkg: [d.relative_to(site).as_posix() for d in (site / pkg).iterdir() if d.is_dir() and re.search(r"data|share|proj|gdal", d.name, re.I)]
             for pkg in ("rasterio", "pyproj") if (site / pkg).exists()}

missing = sorted(k for k in direct if k not in dists)
mismatch = {k: (direct[k], dists[k].version) for k in direct if k in dists and direct[k] and dists[k].version not in direct[k]}
json.dump({"python": sys.version, "site_packages": str(site), "direct_requirements": direct, "missing_direct": missing,
           "pin_mismatch": mismatch, "distributions": records, "vendored_native_libraries": libs, "bundled_data_dirs": data_dirs},
          open(out, "w"), indent=1)
print(f"{len(records)} distributions; {len(direct)} direct; {sum(r['in_dependency_closure'] for r in records)} in closure; "
      f"missing direct {missing}; pin mismatches {mismatch}")
for r in records:
    lic = r["license_expression"] or r["license_field"] or "; ".join(c.split("::")[-1].strip() for c in r["license_classifiers"]) or "?"
    print(f"{'D' if r['direct'] else ' '} {'C' if r['in_dependency_closure'] else '-'} {r['name']:22} {r['version']:12} "
          f"{lic[:60]!r:64} files={len(r['license_files_in_record'])} by={','.join(r['required_by'])}")
for k, v in libs.items():
    print(k, len(v), v[:40])
print("data dirs", data_dirs)
