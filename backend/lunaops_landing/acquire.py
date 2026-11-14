"""Register an auxiliary PGDA product for landing screening in data/landing/manifest.json.

    python -m lunaops_landing.acquire register --kind count --dem-key 5m:Site01_final_adj_5mpp_surf.tif \
        --file E:/Temp/LUNA-OPS/downloads/pgda78_site01/Site01_final_adj_5mpp_ldec.tif \
        --source-url https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site01/Site01_final_adj_5mpp_ldec.tif

The file is accepted only if its CRS, transform and size equal those of the registered DEM (so it lies on the DEM's
own grid and frame). It is copied into data/landing/<dem folder>/ and recorded with its SHA-256. The production
terrain registry (data/dem/registry.json) is never written.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from lunaops.engine import dem as edem

from .sources import _sha256, landing_dir, manifest_path, read_manifest

KINDS = {
    "count": ("LDEC count map: number of LOLA returns in each pixel", "LOLA returns per pixel"),
    "slope": ("NASA PGDA 78 slope product", "degrees"),
    "slope_error": ("NASA PGDA 78 slope uncertainty (formally the RMS error)", "degrees"),
}


def register(kind: str, dem_key: str, file: Path, source_url: str | None, last_modified: str | None) -> dict:
    import rasterio
    from pyproj import CRS

    dem = next((p for p in edem.read_registry()["products"] if edem.product_key(p) == dem_key), None)
    if dem is None:
        raise SystemExit(f"No registered DEM with key {dem_key}.")
    with rasterio.open(file) as src:
        tr = [float(v) for v in list(src.transform)[:6]]
        info = {"width": src.width, "height": src.height, "transform": tr, "dtype": src.dtypes[0],
                "nodata": src.nodata, "crs_wkt": src.crs.to_wkt() if src.crs else None,
                "area_or_point": src.tags().get("AREA_OR_POINT")}
    if info["width"] != dem["width"] or info["height"] != dem["height"] or info["transform"] != dem["transform"]:
        raise SystemExit("Refused: the file's grid differs from the DEM's grid.")
    if not info["crs_wkt"] or not CRS.from_wkt(info["crs_wkt"]).equals(CRS.from_wkt(dem["crs_wkt"])):
        raise SystemExit("Refused: the file's CRS differs from the DEM's CRS.")
    sub = landing_dir() / Path(dem["path"]).parent.name
    sub.mkdir(parents=True, exist_ok=True)
    dst = sub / file.name
    if file.resolve() != dst.resolve():
        shutil.copyfile(file, dst)
    name, units = KINDS[kind]
    entry = {"key": f"{dem_key}#{kind}", "kind": kind, "dem_product_key": dem_key, "dem_sha256": dem["sha256"],
             "product": f"{name} ({file.name})", "units": units, "path": dst.relative_to(landing_dir()).as_posix(),
             "bytes": dst.stat().st_size, "sha256": _sha256(dst), "source_url": source_url,
             "source_last_modified": last_modified, "frame": "MOON_ME (DE421), south polar stereographic (PGDA README)",
             "citation": dem.get("citation"), "page": dem.get("page"),
             "registered_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
             **info}
    man = read_manifest()
    man["notes"] = ("Auxiliary products for LUNA-OPS landing screening (lunaops_landing). Each is tied to one "
                    "registered DEM by SHA-256 and grid. This file is separate from data/dem/registry.json, which "
                    "landing screening never writes.")
    man["products"] = [e for e in man.get("products", []) if e.get("key") != entry["key"]] + [entry]
    manifest_path().write_text(json.dumps(man, indent=2, sort_keys=True))
    return entry


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="lunaops_landing.acquire")
    sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("register")
    r.add_argument("--kind", choices=sorted(KINDS), required=True)
    r.add_argument("--dem-key", required=True)
    r.add_argument("--file", type=Path, required=True)
    r.add_argument("--source-url")
    r.add_argument("--last-modified")
    a = ap.parse_args(argv)
    e = register(a.kind, a.dem_key, a.file, a.source_url, a.last_modified)
    json.dump({k: v for k, v in e.items() if k != "crs_wkt"}, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
