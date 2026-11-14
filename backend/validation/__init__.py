"""Validation scripts. Run them as modules: python -m validation.<script>.

Importing the package selects the kernel set every script records and uses, the same rule as the
automated tests: the production set in data/kernels when one is installed, otherwise the demo set
in data/kernels_demo. An explicit LUNAOPS_KERNEL_SET always wins.
"""
from __future__ import annotations

import json
import os
from pathlib import Path


def _select_kernel_set() -> None:
    if os.environ.get("LUNAOPS_KERNEL_SET"):
        return
    data = Path(os.environ.get("LUNAOPS_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))
    prod = data / "kernels" / "lock.json"
    try:
        if prod.exists() and json.loads(prod.read_text()).get("profile") == "production":
            os.environ["LUNAOPS_KERNEL_SET"] = "production"
            return
    except (OSError, ValueError):
        pass
    if (data / "kernels_demo" / "lock.json").exists():
        os.environ["LUNAOPS_KERNEL_SET"] = "demo"


_select_kernel_set()
