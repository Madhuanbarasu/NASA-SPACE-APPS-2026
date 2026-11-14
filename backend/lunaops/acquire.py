"""Data acquisition and registration (blueprint Sections 5-6; Q10, Q13, Q15).

    python -m lunaops.acquire kernels                 # pinned NAIF kernels -> data/kernels/lock.json
    python -m lunaops.acquire kernels --from-dir DIR  # same checks, using files you downloaded yourself
    python -m lunaops.acquire verify-kernels          # re-check the installed production set and load it
    python -m lunaops.acquire register-dem --product pgda90_20m --file LDEM_80S_20MPP_ADJ.TIF [--error-map ERR.TIF]
    python -m lunaops.acquire register-dem --product pgda78_site --file <site DEM>.TIF   # repeat per site
    python -m lunaops.acquire register-catalog --usgs <zip-or-folder> | --pgda <SiteNN_ROIs.tgz, zip or folder>
    python -m lunaops.acquire status
    python -m lunaops.acquire verify                  # re-hash every registered DEM and error map
    python -m lunaops.acquire sandbox-kernels         # demo/test kernels -> data/kernels_demo (no NAIF access)
    python -m lunaops.acquire synthetic-terrain       # automated tests only (clearly flagged)

Every file is hashed (SHA-256) and recorded with its source and retrieval time.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from . import settings
from .engine.kernels import sha256_of

MANIFEST_DIR = Path(__file__).parent / "manifests"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _download(url: str, dest: Path) -> int:
    req = urllib.request.Request(url, headers={"User-Agent": "LUNA-OPS/0.1 (data acquisition)"})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f, length=1 << 20)
    return dest.stat().st_size


_HEX_RE = None
_KNAME_RE = None


def parse_checksum_text(text: str) -> dict:
    """{filename: hexdigest} from a checksum listing, whatever its layout: "<hash> <name>",
    "<name> <hash>" or "MD5 (<name>) = <hash>". The hash type is inferred from its length."""
    import re
    global _HEX_RE, _KNAME_RE
    if _HEX_RE is None:
        _HEX_RE = re.compile(r"(?<![0-9A-Fa-f])([0-9A-Fa-f]{64}|[0-9A-Fa-f]{40}|[0-9A-Fa-f]{32})(?![0-9A-Fa-f])")
        _KNAME_RE = re.compile(r"[\w.+\-]+\.(?:bsp|bpc|tpc|tf|tls|ti|tsc|bc|bds|xsp|txt|tm)\b", re.IGNORECASE)
    out = {}
    for line in text.splitlines():
        h = _HEX_RE.search(line)
        n = _KNAME_RE.search(line)
        if h and n:
            out[n.group(0)] = h.group(1).lower()
    return out


def _checksum_list(url: str) -> dict:
    """Fetch and parse a NAIF checksum listing (aa_checksums.txt); {} if it cannot be read."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LUNA-OPS/0.1 (data acquisition)"})
        with urllib.request.urlopen(req, timeout=60) as r:
            text = r.read().decode("utf-8", "replace")
    except Exception:
        return {}
    return parse_checksum_text(text)


def _hash_as(path: Path, hexlen: int) -> str:
    algo = {32: "md5", 40: "sha1", 64: "sha256"}.get(hexlen)
    if algo is None:
        return ""
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify_candidate(entry: dict, name: str, path: Path, primary: bool, sums_cache: dict) -> tuple[bool, dict, str]:
    """Check a staged kernel against every published value; returns (ok, record extras, reason)."""
    extra: dict = {}
    size = path.stat().st_size
    if primary and entry.get("expected_bytes") and size != entry["expected_bytes"]:
        return False, extra, f"{size} bytes, NAIF publishes {entry['expected_bytes']}"
    if primary and entry.get("expected_md5"):
        md5 = _hash_as(path, 32)
        if md5 != entry["expected_md5"]:
            return False, extra, f"MD5 {md5} does not match the NAIF-published {entry['expected_md5']}"
        extra["naif_md5_match"] = True
        extra["naif_md5_source"] = entry.get("evidence")
    if primary and entry.get("checksum_list"):
        url = entry["checksum_list"]
        if url not in sums_cache:
            sums_cache[url] = _checksum_list(url)
        sums = sums_cache[url]
        if not sums:
            extra["naif_checksum_match"] = None
            extra["naif_checksum_note"] = f"could not read {url}; run verify-kernels later to check"
        elif name in sums:
            digest = _hash_as(path, len(sums[name]))
            if digest != sums[name]:
                return False, extra, f"does not match NAIF aa_checksums.txt ({sums[name]})"
            extra["naif_checksum_match"] = True
        else:
            extra["naif_checksum_match"] = None
            extra["naif_checksum_note"] = f"{name} is not listed in {url}"
    if not any(k in extra for k in ("naif_md5_match", "naif_checksum_match")):
        extra["naif_checksum_note"] = extra.get("naif_checksum_note") or \
            "no NAIF checksum published for this file; SHA-256 pinned on first download"
    return True, extra, ""


def cmd_kernels(args) -> None:
    """Install the pinned production kernel set into data/kernels.

    Files are fetched (or copied from --from-dir) into data/kernels/.staging, checked against every
    size and checksum NAIF publishes, test-loaded with SPICE, and only then moved into place, with
    lock.json written last. Any failure leaves the existing production set untouched.
    """
    from .engine import kernels as K

    moved = K.migrate_misplaced_demo_lock()
    if moved:
        print("  " + moved)
    man_path = Path(getattr(args, "manifest", None) or (MANIFEST_DIR / "kernels.production.json"))
    man = json.loads(man_path.read_text())
    prod = settings.PRODUCTION_KERNEL_DIR
    stage = prod / ".staging"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    from_dir = Path(args.from_dir).resolve() if getattr(args, "from_dir", None) else None
    files, problems, sums_cache = [], [], {}
    for entry in man["files"]:
        candidates = [(entry["name"], entry["urls"], None, True)]
        if entry.get("fallback"):
            fb = entry["fallback"]
            candidates.append((fb["name"], fb["urls"], fb["reason"], False))
        got = None
        for name, urls, reason, primary in candidates:
            dest = stage / name
            sources = [None] if from_dir else urls
            for url in sources:
                try:
                    if from_dir:
                        src = from_dir / name
                        if not src.exists():
                            raise FileNotFoundError(f"{src} not found")
                        print(f"  copying {name} from {from_dir}")
                        shutil.copyfile(src, dest)
                    else:
                        print(f"  downloading {name} from {url}")
                        _download(url, dest)
                except Exception as exc:
                    print(f"    failed: {exc}")
                    dest.unlink(missing_ok=True)
                    continue
                ok, extra, why = _verify_candidate(entry, name, dest, primary, sums_cache)
                if not ok:
                    print(f"    REJECTED {name}: {why}")
                    problems.append(f"{name}: {why}")
                    dest.unlink(missing_ok=True)
                    continue
                got = (name, urls[0] if from_dir else url, reason, extra)
                break
            if got:
                break
        if not got:
            if entry.get("optional"):
                print(f"  optional kernel {entry['name']} unavailable; V-02e will be skipped")
                continue
            shutil.rmtree(stage, ignore_errors=True)
            detail = ("; ".join(problems[-3:]) + ". ") if problems else ""
            sys.exit(f"Required kernel {entry['name']} could not be obtained. {detail}"
                     + (f"Put the file in {from_dir}." if from_dir else
                        "Check your connection to naif.jpl.nasa.gov, or download the files yourself and use --from-dir.")
                     + f" The existing production set in {prod} was not changed.")
        name, url, reason, extra = got
        path = stage / name
        rec = {"role": entry["role"], "name": name, "source": url, "bytes": path.stat().st_size,
               "sha256": sha256_of(path), "retrieved_utc": now_utc(), "evidence": entry.get("evidence"), **extra}
        if from_dir:
            rec["obtained"] = f"manual download, copied from {from_dir}"
        if reason:
            rec["notes"] = f"Fallback used: {reason}"
        files.append(rec)
    lock = {"profile": man.get("profile", "production"), "body_fixed_frame": man["body_fixed_frame"],
            "pa_frame": man["pa_frame"], "manifest_sha256": sha256_of(man_path), "created_utc": now_utc(),
            "files": files}
    (stage / "lock.json").write_text(json.dumps(lock, indent=2))
    print("  test-loading the staged set with SPICE ...")
    try:
        ks = K.check_set(stage, lock)
    except Exception as exc:
        shutil.rmtree(stage, ignore_errors=True)
        sys.exit(f"The downloaded kernels did not load: {exc}. The existing production set in {prod} was not changed.")
    # commit: keep the previous set (if any) in superseded_<UTC>/, then move files in, lock.json last
    old_lock = prod / "lock.json"
    if old_lock.exists():
        keep = prod / ("superseded_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
        keep.mkdir()
        try:
            old = json.loads(old_lock.read_text())
            for f in old.get("files", []):
                if (prod / f["name"]).exists():
                    shutil.copy2(prod / f["name"], keep / f["name"])
        except Exception:
            pass
        shutil.copy2(old_lock, keep / "lock.json")
        print(f"  previous production set kept in {keep}")
    for f in files:
        os.replace(stage / f["name"], prod / f["name"])
    os.replace(stage / "lock.json", prod / "lock.json")
    shutil.rmtree(stage, ignore_errors=True)
    print(f"Installed {len(files)} kernels in {prod} (lock.json written last).")
    print(f"  frame {ks.frame}; coverage {ks.coverage_utc[0]} to {ks.coverage_utc[1]}; "
          f"DE421 validation kernels {'present' if ks.de421_available else 'absent (V-02e will be skipped)'}")
    for w in ks.warnings:
        print(f"  note: {w}")
    print("Next: `python -m lunaops.acquire verify-kernels`, then `python -m validation.run_validation`.")


def cmd_verify_kernels(args) -> None:
    """Re-check an installed kernel set: files, sizes, SHA-256 against the lock, NAIF checksums, and a load."""
    from .engine import kernels as K

    kd = settings.DEMO_KERNEL_DIR if args.demo else settings.PRODUCTION_KERNEL_DIR
    kd.mkdir(parents=True, exist_ok=True)       # settings import creates no folders
    want = "sandbox-test" if args.demo else "production"
    bad = []
    lp = kd / "lock.json"
    if not lp.exists():
        sys.exit(f"No lock.json in {kd}. " + ("Run `python start.py --demo`." if args.demo else
                                               "Run `python -m lunaops.acquire kernels`."))
    lock = json.loads(lp.read_text())
    print(f"Kernel set: {kd}")
    print(f"  profile {lock.get('profile')}; frame {lock.get('body_fixed_frame')}; created {lock.get('created_utc')}")
    if lock.get("profile") != want:
        bad.append(f"profile is {lock.get('profile')!r}, expected {want!r} in this folder")
    man = json.loads((MANIFEST_DIR / "kernels.production.json").read_text()) if not args.demo else {"files": []}
    by_name = {}
    for e in man["files"]:
        by_name[e["name"]] = (e, True)
        if e.get("fallback"):
            by_name[e["fallback"]["name"]] = (e, False)
    for f in lock.get("files", []):
        path = kd / f["name"]
        if not path.exists():
            bad.append(f"{f['name']}: missing")
            print(f"  MISSING  {f['role']:<14} {f['name']}")
            continue
        size = path.stat().st_size
        digest = sha256_of(path)
        notes = []
        ok = True
        if size != f.get("bytes"):
            ok = False
            notes.append(f"size {size} != lock {f.get('bytes')}")
        if digest != f.get("sha256"):
            ok = False
            notes.append("SHA-256 differs from lock")
        entry, primary = by_name.get(f["name"], (None, False))
        if entry and primary:
            if entry.get("expected_bytes") and size != entry["expected_bytes"]:
                ok = False
                notes.append(f"size differs from NAIF-published {entry['expected_bytes']}")
            if entry.get("expected_md5"):
                md5 = _hash_as(path, 32)
                if md5 != entry["expected_md5"]:
                    ok = False
                    notes.append("MD5 differs from NAIF-published value")
                else:
                    notes.append("NAIF MD5 ok")
            if entry.get("checksum_list") and not args.offline:
                sums = _checksum_list(entry["checksum_list"])
                if f["name"] in sums:
                    if _hash_as(path, len(sums[f["name"]])) != sums[f["name"]]:
                        ok = False
                        notes.append("differs from NAIF aa_checksums.txt")
                    else:
                        notes.append("NAIF aa_checksums ok")
                else:
                    notes.append("NAIF aa_checksums not reachable or file not listed")
        elif not args.demo and entry is None:
            notes.append("not in the production manifest")
        if ok:
            notes.insert(0, "SHA-256 matches lock")
            if not args.demo and entry is not None and not any("NAIF" in n for n in notes):
                notes.append("NAIF publishes no checksum for this file (trusted on first download)")
        print(f"  {'ok      ' if ok else 'FAILED  '} {f['role']:<14} {f['name']:<30} {size:>10} B  sha256 {digest[:16]}...  "
              + "; ".join(notes))
        if not ok:
            bad.append(f"{f['name']}: " + "; ".join(notes))
    try:
        ks = K.check_set(kd, lock)
        print(f"  load: ok; frame {ks.frame} defined; coverage {ks.coverage_utc[0]} to {ks.coverage_utc[1]}")
        print(f"  Moon radii in kernels: {ks.moon_radii_km} km (engine uses 1737.4 km)")
        v02e = ks.profile == "production" and ks.de421_available
        print(f"  V-02e prerequisites (production profile + DE421 PCK/FK + MOON_ME_DE421 frame): "
              f"{'met' if v02e else 'NOT met'}")
    except Exception as exc:
        bad.append(f"load failed: {exc}")
        print(f"  load: FAILED: {exc}")
    if bad:
        print(f"{len(bad)} problem(s):")
        for b in bad:
            print(f"  - {b}")
        sys.exit(1)
    print("Kernel set verified.")


# --------------------------------------------------------- sandbox kernels
TEST_LSK = """KPL/LSK

LUNA-OPS SANDBOX TEST LEAPSECONDS KERNEL
For automated tests in environments without access to naif.jpl.nasa.gov only.
Values are the published TAI-UTC history and standard LSK constants. Production
runs must use naif0012.tls downloaded from NAIF (python -m lunaops.acquire kernels).

\\begindata

DELTET/DELTA_T_A = 32.184
DELTET/K         = 1.657D-3
DELTET/EB        = 1.671D-2
DELTET/M         = ( 6.239996D0 1.99096871D-7 )
DELTET/DELTA_AT  = ( 10, @1972-JAN-1
                     11, @1972-JUL-1
                     12, @1973-JAN-1
                     13, @1974-JAN-1
                     14, @1975-JAN-1
                     15, @1976-JAN-1
                     16, @1977-JAN-1
                     17, @1978-JAN-1
                     18, @1979-JAN-1
                     19, @1980-JAN-1
                     20, @1981-JUL-1
                     21, @1982-JUL-1
                     22, @1983-JUL-1
                     23, @1985-JUL-1
                     24, @1988-JAN-1
                     25, @1990-JAN-1
                     26, @1991-JAN-1
                     27, @1992-JUL-1
                     28, @1993-JUL-1
                     29, @1994-JUL-1
                     30, @1996-JAN-1
                     31, @1997-JUL-1
                     32, @1999-JAN-1
                     33, @2006-JAN-1
                     34, @2009-JAN-1
                     35, @2012-JUL-1
                     36, @2015-JUL-1
                     37, @2017-JAN-1 )

\\begintext
"""

TEST_PCK = """KPL/PCK

LUNA-OPS SANDBOX TEST PCK: Moon radii only (LOLA 1737.4 km sphere), for tests.
Production uses pck00011.tpc from NAIF.

\\begindata
BODY301_RADII = ( 1737.4 1737.4 1737.4 )
\\begintext
"""


def cmd_sandbox_kernels(args) -> None:
    """Assemble a clearly labelled TEST kernel set without NAIF access.

    de440s.bsp from a GitHub mirror verified against the mirror's SHA256SUMS,
    NAIF's DE421 lunar PCK/FK as redistributed in the 'lunarsky' PyPI wheel,
    and generated LSK/PCK text kernels. Frame: MOON_ME_DE421. Written to data/kernels_demo, never to
    the production folder.
    """
    from .engine import kernels as K

    moved = K.migrate_misplaced_demo_lock()
    if moved:
        print("  " + moved)
    kd = settings.DEMO_KERNEL_DIR
    kd.mkdir(parents=True, exist_ok=True)       # settings import creates no folders
    mirror = "https://github.com/jayeshmepani/jpl-ephemeris/releases/download/jpl-kernels/"
    files = []
    try:
        sums_text = urllib.request.urlopen(mirror + "SHA256SUMS.txt", timeout=60).read().decode()
    except Exception as exc:
        sys.exit(f"Could not read {mirror}SHA256SUMS.txt ({exc}). GitHub must be reachable for the test kernels.")
    want = parse_checksum_text(sums_text).get("de440s.bsp")
    if not want or len(want) != 64:
        sys.exit(f"{mirror}SHA256SUMS.txt has no SHA-256 for de440s.bsp; refusing to install an unchecked file.")
    spk = kd / "de440s.bsp"
    if not spk.exists() or sha256_of(spk) != want:
        print("  downloading de440s.bsp from GitHub mirror")
        try:
            _download(mirror + "de440s.bsp", spk)
        except Exception as exc:
            sys.exit(f"Downloading {mirror}de440s.bsp failed: {exc}")
    digest = sha256_of(spk)
    if digest != want:
        sys.exit("de440s.bsp does not match the mirror SHA256SUMS")
    files.append({"role": "spk", "name": "de440s.bsp", "source": mirror + "de440s.bsp", "bytes": spk.stat().st_size,
                  "sha256": digest, "retrieved_utc": now_utc(),
                  "notes": "Mirror copy for tests; compare with NAIF aa_checksums.txt before production use"})
    import subprocess
    with tempfile.TemporaryDirectory(prefix="lunaops_lunarsky_") as td:
        tmp = Path(td)
        try:
            subprocess.run([sys.executable, "-m", "pip", "download", "lunarsky==1.0.1.post2", "--no-deps", "-q",
                            "-d", str(tmp)], check=True)
            whl = next(tmp.glob("lunarsky-*.whl"))
        except (subprocess.CalledProcessError, StopIteration, OSError) as exc:
            sys.exit(f"Could not download the lunarsky 1.0.1.post2 wheel from PyPI ({exc!r}). PyPI must be reachable.")
        with zipfile.ZipFile(whl) as z:
            for role, member in [("lunar_pck", "lunarsky/data/pck/moon_pa_de421_1900-2050.bpc"),
                                 ("lunar_fk", "lunarsky/data/fk/satellites/moon_080317.tf"),
                                 ("lunar_fk_assoc", "lunarsky/data/fk/satellites/moon_assoc_me.tf")]:
                name = member.split("/")[-1]
                (kd / name).write_bytes(z.read(member))
                files.append({"role": role, "name": name, "source": f"PyPI lunarsky 1.0.1.post2 wheel: {member}",
                              "bytes": (kd / name).stat().st_size, "sha256": sha256_of(kd / name),
                              "retrieved_utc": now_utc(),
                              "notes": "DE421 lunar kernel redistributed by a PyPI package; test use only"})
    for role, name, text in [("lsk", "lunaops_test_lsk.tls", TEST_LSK), ("text_pck", "lunaops_test_radii.tpc", TEST_PCK)]:
        (kd / name).write_text(text)
        files.append({"role": role, "name": name, "source": "generated by lunaops.acquire sandbox-kernels",
                      "bytes": (kd / name).stat().st_size, "sha256": sha256_of(kd / name), "retrieved_utc": now_utc(),
                      "notes": "Generated test kernel; production uses the NAIF file"})
    lock = {"profile": "sandbox-test", "body_fixed_frame": "MOON_ME_DE421", "pa_frame": "MOON_PA_DE421",
            "created_utc": now_utc(), "files": files}
    (kd / "lock.json").write_text(json.dumps(lock, indent=2))
    print(f"Wrote sandbox TEST kernel lock ({len(files)} files). Not for production results.")


# ---------------------------------------------------------------- DEMs
def _portable_dem_path(p: Path) -> str:
    p = p.resolve()
    for base in (settings.DEM_DIR.resolve(), (settings.REPO_ROOT / "data" / "dem").resolve()):
        try:
            return p.relative_to(base).as_posix()
        except ValueError:
            pass
    return str(p)


def _error_map_record(ep: Path, dem_rec: dict, spec: dict) -> dict:
    """Inspect an error map and check that it belongs with this DEM (same projection and pixel grid)."""
    from .engine.dem import TerrainError, inspect_raster

    if not ep.exists():
        sys.exit(f"{ep} does not exist")
    einfo = inspect_raster(ep, kind="error_map")
    if abs(einfo["pixel_m"] - dem_rec["pixel_m"]) > 0.01 * dem_rec["pixel_m"]:
        sys.exit(f"{ep.name}: pixel size {einfo['pixel_m']} m does not match its DEM {Path(dem_rec['path']).name} "
                 f"({dem_rec['pixel_m']} m); an error map must be on its DEM's grid")
    da, _, dc, _, de, df = dem_rec["transform"]
    ea, _, ec, _, ee, ef = einfo["transform"]
    # pixel corners must line up (offset an integer number of pixels) and the extents must overlap
    for off, step in ((ec - dc, da), (ef - df, de)):
        frac = abs(off / step - round(off / step))
        if frac > 1e-3:
            sys.exit(f"{ep.name}: its pixel grid is offset from {Path(dem_rec['path']).name} by a fraction of a pixel")
    dx0, dx1 = sorted((dc, dc + da * dem_rec["width"]))
    dy0, dy1 = sorted((df, df + de * dem_rec["height"]))
    ex0, ex1 = sorted((ec, ec + ea * einfo["width"]))
    ey0, ey1 = sorted((ef, ef + ee * einfo["height"]))
    if ex1 <= dx0 or ex0 >= dx1 or ey1 <= dy0 or ey0 >= dy1:
        sys.exit(f"{ep.name}: does not overlap {Path(dem_rec['path']).name}")
    same_grid = (einfo["width"] == dem_rec["width"] and einfo["height"] == dem_rec["height"]
                 and all(abs(a - b) < 1e-6 for a, b in zip(einfo["transform"], dem_rec["transform"])))
    if not same_grid:
        print(f"  note: {ep.name} covers a different extent than its DEM; bins outside it get no sigma")
    print("  hashing error map (SHA-256) ...")
    return {"path": _portable_dem_path(ep), "sha256": sha256_of(ep), "bytes": ep.stat().st_size, "product": spec.get("error_map"),
            "dem_sha256": dem_rec["sha256"], "dem_file": Path(dem_rec["path"]).name, "same_grid_as_dem": same_grid,
            "units": "m (RMS height uncertainty, declared by product)", "registered_utc": now_utc(), **einfo}


def cmd_register_dem(args) -> None:
    from .engine.dem import inspect_raster, product_key, read_registry, write_registry

    man = json.loads((MANIFEST_DIR / "datasets.json").read_text())
    specs = man["dem_levels"]
    if args.product:
        spec = next((d for d in specs if d["id"] == args.product), None)
        if spec is None:
            sys.exit(f"Unknown product {args.product}; choose one of {[d['id'] for d in specs]}")
    else:
        spec = next((d for d in specs if d["level"] == args.level and not d.get("multiple")), None)
        if spec is None:
            sys.exit(f"Unknown level {args.level}; give --product, one of {[d['id'] for d in specs]}")
    path = Path(args.file).resolve()
    if not path.exists():
        sys.exit(f"{path} does not exist")
    print(f"  inspecting {path.name} ...")
    info = inspect_raster(path)
    if abs(info["pixel_m"] - spec["pixel_m"]) > 0.01 * spec["pixel_m"]:
        sys.exit(f"{path.name}: pixel size {info['pixel_m']} m does not match {spec['id']} ({spec['pixel_m']} m)")
    if spec.get("expected_name"):
        exp = spec["expected_name"].upper()
        if path.name.upper() != exp and not (path.stem.upper() == Path(exp).stem and path.suffix.lower() in (".tif", ".tiff")):
            print(f"  note: file name differs from the expected {spec['expected_name']}")
    if spec.get("name_pattern") and not Path(path.name.lower()).match(spec["name_pattern"].lower()):
        print(f"  note: file name does not follow the product's pattern {spec['name_pattern']}")
    print("  hashing (SHA-256) ...")
    rec = {"level": spec["level"], "product_id": spec["id"], "path": _portable_dem_path(path), "sha256": sha256_of(path),
           "bytes": path.stat().st_size, "product": spec["product"], "page": spec["page"],
           "citation": spec.get("citation"), "priority": spec.get("priority", 50),
           "units": info["units_tag"] or "m (declared by product; not embedded in file)",
           "registered_utc": now_utc(), "synthetic": False, **info}
    reg = read_registry()
    from .engine.dem import resolve_dem_path
    same_file = [p for p in reg["products"] if resolve_dem_path(p["path"]).resolve() == path or p.get("sha256") == rec["sha256"]]
    removed = list(same_file)
    reg["products"] = [p for p in reg["products"] if p not in same_file]
    if not spec.get("multiple"):
        replaced = [p for p in reg["products"] if p.get("product_id") == spec["id"]]
        if replaced and not args.replace:
            sys.exit(f"{spec['id']} is already registered ({Path(replaced[0]['path']).name}). Use --replace to swap it.")
        reg["products"] = [p for p in reg["products"] if p not in replaced]
        removed += replaced
    # an error map belongs to one DEM file: drop maps of removed products and any stale map under this key
    for old in removed:
        if reg["error_maps"].pop(product_key(old), None) is not None and product_key(old) != product_key(rec):
            print(f"  removed the error map of the replaced product {product_key(old)}")
    stale = reg["error_maps"].get(product_key(rec))
    if stale and stale.get("dem_sha256") != rec["sha256"]:
        reg["error_maps"].pop(product_key(rec))
        print(f"  removed an error map registered for a different version of {path.name}")
    reg["products"].append(rec)
    if args.error_map:
        ep = Path(args.error_map).resolve()
        reg["error_maps"][product_key(rec)] = _error_map_record(ep, rec, spec)
    elif spec.get("error_map_pattern"):
        print(f"  tip: this product publishes an error map ({spec['error_map_pattern']}); "
              "add it with --error-map to get per-bin horizon uncertainty")
    write_registry(reg)
    n_level = sum(1 for p in reg["products"] if p["level"] == spec["level"])
    print(f"Registered {product_key(rec)} ({rec['bytes'] / 1e9:.2f} GB); {n_level} product(s) at {spec['level']}.")


def cmd_unregister_dem(args) -> None:
    from .engine.dem import product_key, read_registry, write_registry

    reg = read_registry()
    target = Path(args.file).name
    keep = [p for p in reg["products"] if Path(p["path"]).name != target]
    if len(keep) == len(reg["products"]):
        sys.exit(f"No registered product named {target}")
    gone = [product_key(p) for p in reg["products"] if p not in keep]
    reg["products"] = keep
    for k in gone:
        reg["error_maps"].pop(k, None)
    write_registry(reg)
    print("Unregistered " + ", ".join(gone))


def cmd_verify(args) -> int:
    """Re-hash every registered DEM and error map against the registry (full integrity check)."""
    from .engine.dem import product_key, read_registry, resolve_dem_path

    reg = read_registry()
    bad = 0
    items = [(product_key(p), p) for p in reg["products"]] + \
            [(f"error map of {k}", em) for k, em in reg.get("error_maps", {}).items()]
    for label, rec in items:
        path = resolve_dem_path(rec["path"])
        if not path.exists():
            print(f"  MISSING  {label}: {path}")
            bad += 1
            continue
        digest = sha256_of(path)
        if digest != rec.get("sha256"):
            print(f"  CHANGED  {label}: SHA-256 {digest[:16]}... != registered {str(rec.get('sha256'))[:16]}...")
            bad += 1
        else:
            print(f"  ok       {label}")
    for k, em in reg.get("error_maps", {}).items():
        owner = next((p for p in reg["products"] if product_key(p) == k), None)
        if owner is None:
            print(f"  ORPHAN   error map {k} has no registered DEM")
            bad += 1
        elif em.get("dem_sha256") != owner.get("sha256"):
            print(f"  UNLINKED error map {k} was not registered for this DEM version (it is not used); re-register it")
            bad += 1
    print("All registered terrain files verified." if not bad else f"{bad} problem(s) found.")
    if bad:
        sys.exit(1)
    return 0


# ------------------------------------------------------------- catalogue
def _safe_extract_tar(tf: tarfile.TarFile, dest: Path) -> None:
    dest = dest.resolve()
    for m in tf.getmembers():
        target = (dest / m.name).resolve()
        if not str(target).startswith(str(dest)) or m.issym() or m.islnk() or m.isdev():
            raise SystemExit(f"Refusing unsafe archive member {m.name}")
    try:
        tf.extractall(dest, filter="data")     # Python >= 3.11.4 / 3.12
    except TypeError:
        tf.extractall(dest)


def _iter_shapefiles(src: Path):
    """Shapefiles in a folder, a .zip, or a .tgz/.tar.gz/.tar archive (PGDA 78 ships ROIs as SiteNN_ROIs.tgz).

    Yields (shapefile path, id stem) where the stem is unique within the source: the path relative to
    the source root without extension, prefixed with the archive name for archives.
    """
    name = src.name.lower()
    if not src.exists():
        raise SystemExit(f"{src} does not exist")
    if src.is_dir():
        root, prefix = src, ""
    else:
        root = Path(tempfile.mkdtemp())
        if name.endswith(".zip"):
            with zipfile.ZipFile(src) as z:
                for m in z.namelist():
                    if not str((root / m).resolve()).startswith(str(root.resolve())):
                        raise SystemExit(f"Refusing unsafe archive member {m}")
                z.extractall(root)
            prefix = src.name[:-4] + "/"
        elif name.endswith((".tgz", ".tar.gz", ".tar")):
            with tarfile.open(src) as tf:
                _safe_extract_tar(tf, root)
            prefix = src.name.split(".")[0] + "/"
        else:
            raise SystemExit(f"{src.name}: give a folder, .zip, .tgz, .tar.gz or .tar")
    for shp in sorted(root.rglob("*.shp")):
        rel = shp.relative_to(root).with_suffix("").as_posix()
        yield shp, prefix + rel


def cmd_register_catalog(args) -> None:
    import shapefile
    from pyproj import CRS, Transformer

    if args.usgs:
        src, kind = Path(args.usgs), "artemis_region"
        label = ("Bounding box of a USGS LGRS ACC navigation-grid shapefile for this region (regions sourced "
                 "from LROC QuickMap; not an official NASA boundary)")
        source = {"product": "USGS: Down Selected Artemis III Candidate Landing Site Navigational Grids (McClernan 2024)",
                  "page": "https://sciencebase.gov/catalog/item/671a6fa8d34efed5620f89f8",
                  "doi": "10.5066/P1MEQ6UK"}
    elif args.pgda:
        src, kind = Path(args.pgda), "pgda_site"
        label = "Bounding box of a PGDA 78 region-of-interest shapefile"
        source = {"product": "PGDA 78: High-Resolution LOLA Topography for Lunar South Pole Sites (ROI shapefiles)",
                  "page": "https://pgda.gsfc.nasa.gov/products/78"}
    else:
        sys.exit("Give --usgs or --pgda")
    cat_path = settings.CATALOG_DIR / "sites.json"
    cat_path.parent.mkdir(parents=True, exist_ok=True)   # settings import creates no folders
    cat = json.loads(cat_path.read_text()) if cat_path.exists() else {"sites": [], "sources": []}
    added = 0
    for shp, stem in _iter_shapefiles(src):
        prj = shp.with_suffix(".prj")
        if not prj.exists():
            print(f"  skipping {shp.name}: no .prj, cannot georeference")
            continue
        crs = CRS.from_wkt(prj.read_text())
        to_geo = Transformer.from_crs(crs, crs.geodetic_crs, always_xy=True)
        r = shapefile.Reader(str(shp))
        if len(r) == 0:
            continue
        # header bounding box: exact for all shapes and O(1) even for 10 m grids with millions of cells
        x0, y0, x1, y1 = (float(v) for v in r.bbox)
        if not all(math.isfinite(v) for v in (x0, y0, x1, y1)) or x1 < x0 or y1 < y0:
            xs = [x for sh in r.iterShapes() for x, _ in sh.points]
            ys = [y for sh in r.iterShapes() for _, y in sh.points]
            if not xs:
                continue
            x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        ring = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
        poly = [list(to_geo.transform(x, y))[::-1] for x, y in ring]  # (lat, lon)
        clon, clat = to_geo.transform(0.5 * (x0 + x1), 0.5 * (y0 + y1))
        sid = f"{kind}:{stem}"
        legacy = f"{kind}:{shp.stem}"          # ids written by earlier versions
        cat["sites"] = [s_ for s_ in cat["sites"] if s_["id"] not in (sid, legacy)]
        cat["sites"].append({
            "id": sid, "name": stem.replace("_", " ").replace("/", " / "), "kind": kind, "lat": clat, "lon": clon % 360.0,
            "point_label": "Derived: centre of the bounding box (not a published landing point)",
            "extent_label": label,
            "polygon_latlon": [[round(a, 6), round(b % 360.0, 6)] for a, b in poly],
            "source": {**source, "archive": src.name, "file": shp.name, "sha256": sha256_of(shp)},
        })
        added += 1
    cat["sources"] = [s_ for s_ in cat["sources"] if not (s_["page"] == source["page"] and
                                                          s_.get("archive") in (None, src.name))] + \
        [{**source, "archive": src.name, "registered_utc": now_utc()}]
    cat_path.write_text(json.dumps(cat, indent=2))
    print(f"Registered {added} catalogue entries from {src}")
    if args.usgs:
        print("  note: the USGS release holds navigation grids (1 km, 100 m, 10 m) per region; each shapefile is a "
              "separate entry whose extent is that grid's bounding box.")


# ------------------------------------------------------- synthetic terrain
def cmd_synthetic_terrain(args) -> None:
    """Analytic synthetic DEMs for automated tests (V-06/V-07). Flagged synthetic everywhere."""
    from .engine.dem import read_registry, write_registry
    from .testing import write_synthetic_dem

    out = settings.DEM_DIR / "synthetic"
    out.mkdir(parents=True, exist_ok=True)
    reg = read_registry()
    reg["products"] = [p for p in reg["products"] if not p.get("synthetic")]
    for level, pixel, half in (("20m", 20.0, 45_000.0), ("240m", 240.0, 300_000.0)):
        p = out / f"SYNTHETIC_{level}.tif"
        write_synthetic_dem(p, pixel, half, kind=args.kind)
        reg["products"].append({"level": level, "product_id": f"synthetic_{level}", "path": str(p),
                                "sha256": sha256_of(p), "bytes": p.stat().st_size,
                                "product": f"SYNTHETIC TEST TERRAIN ({args.kind}) - not lunar data",
                                "page": None, "synthetic": True, "registered_utc": now_utc(),
                                "pixel_m": pixel, **_basic_info(p)})
    write_registry(reg)
    print("Registered synthetic test terrain. Set LUNAOPS_ALLOW_SYNTHETIC=1 to use it; it is flagged in every result.")


def _basic_info(p: Path) -> dict:
    import rasterio
    with rasterio.open(p) as src:
        t = src.transform
        return {"width": src.width, "height": src.height, "transform": [t.a, t.b, t.c, t.d, t.e, t.f],
                "nodata": src.nodata, "scale": 1.0, "offset": 0.0, "units_tag": "m"}


def cmd_status(args) -> None:
    from .engine.catalog import load_catalog
    from .engine.dem import read_registry

    for label, kd in (("Production kernels", settings.PRODUCTION_KERNEL_DIR), ("Demo kernels", settings.DEMO_KERNEL_DIR)):
        lock = kd / "lock.json"
        print(f"{label} ({kd}):", "none" if not lock.exists() else json.loads(lock.read_text())["profile"])
        if lock.exists():
            for f in json.loads(lock.read_text())["files"]:
                print(f"  {f['role']:<14} {f['name']:<30} {f['sha256'][:16]}...")
    print(f"Active kernel set for this process: {settings.KERNEL_SET}")
    from .engine.dem import broken_products, error_map_for, product_key
    reg = read_registry()
    print("Terrain products:", ", ".join(product_key(p) for p in reg["products"]) or "none")
    for p in reg["products"]:
        if error_map_for(p, reg):
            print(f"  error map linked: {product_key(p)}")
    for _rec, why in broken_products():
        print(f"  PROBLEM: {why}")
    cat = load_catalog()
    print("Catalogue sites:", len(cat["sites"]))


def main(argv=None) -> None:
    settings.ensure_dirs()
    ap = argparse.ArgumentParser(prog="lunaops.acquire", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("kernels", help="install the pinned production NAIF kernels into data/kernels")
    p.add_argument("--from-dir", help="use kernel files you downloaded yourself (same names as the manifest)")
    p.add_argument("--manifest", help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_kernels)
    p = sub.add_parser("verify-kernels", help="re-check the installed kernel set and test-load it")
    p.add_argument("--demo", action="store_true", help="check data/kernels_demo instead of the production set")
    p.add_argument("--offline", action="store_true", help="skip fetching NAIF aa_checksums.txt")
    p.set_defaults(func=cmd_verify_kernels)
    sub.add_parser("sandbox-kernels").set_defaults(func=cmd_sandbox_kernels)
    p = sub.add_parser("register-dem")
    p.add_argument("--product", help="pgda81_mosaic, pgda78_site (repeatable, one per site), pgda90_10m, pgda90_20m, pgda90_80m, pgda90_240m")
    p.add_argument("--level", choices=["5m", "10m", "20m", "80m", "240m"], help="shorthand for the single-file product at that level")
    p.add_argument("--file", required=True)
    p.add_argument("--error-map", help="the product's height-error GeoTIFF on the same grid "
                                       "(PGDA 90: LDEM_*_ADJ_ERR.TIF; PGDA 78: <Site>_final_adj_5mpp_toterr.tif)")
    p.add_argument("--replace", action="store_true", help="replace an already registered single-file product")
    p.set_defaults(func=cmd_register_dem)
    p = sub.add_parser("unregister-dem")
    p.add_argument("--file", required=True)
    p.set_defaults(func=cmd_unregister_dem)
    p = sub.add_parser("register-catalog")
    p.add_argument("--usgs", help="USGS Artemis III navigational grids release (zip or folder)")
    p.add_argument("--pgda", help="PGDA 78 ROI archive (SiteNN_ROIs.tgz), zip or folder; repeat per site")
    p.set_defaults(func=cmd_register_catalog)
    p = sub.add_parser("synthetic-terrain")
    p.add_argument("--kind", default="crater", choices=["sphere", "crater", "hills"])
    p.set_defaults(func=cmd_synthetic_terrain)
    sub.add_parser("status").set_defaults(func=cmd_status)
    sub.add_parser("verify").set_defaults(func=cmd_verify)
    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
