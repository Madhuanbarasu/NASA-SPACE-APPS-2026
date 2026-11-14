"""Curated site catalogue (requirement B02; Q11).

Sites come only from registered source files:
- USGS Artemis III candidate-region navigation grids (region extents sourced
  from LROC QuickMap; not an official NASA boundary),
- PGDA 78 site ROI shapefiles,
- user_sites.json entries that each carry a source citation.
Any point placed inside a region is labelled as derived. No coordinates are
built into the code.
"""
from __future__ import annotations

import json

from .. import settings


def catalog_path():
    return settings.CATALOG_DIR / "sites.json"


def user_sites_path():
    return settings.CATALOG_DIR / "user_sites.json"


def load_catalog() -> dict:
    sites = []
    sources = []
    p = catalog_path()
    if p.exists():
        data = json.loads(p.read_text())
        sites += data.get("sites", [])
        sources += data.get("sources", [])
    up = user_sites_path()
    if up.exists():
        for s in json.loads(up.read_text()).get("sites", []):
            if not s.get("source"):
                continue  # a curated site without a citation is not accepted
            s = dict(s)
            s.setdefault("kind", "user")
            s.setdefault("point_label", "User-supplied point with citation")
            sites.append(s)
    reason = None
    if not sites:
        reason = ("No curated sites are registered yet. Register the USGS Artemis III grids or PGDA ROI "
                  "shapefiles (README, step 4), or enter custom coordinates.")
    return {"sites": sites, "sources": sources, "empty_reason": reason}
