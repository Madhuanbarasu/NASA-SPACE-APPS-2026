"""Kernel setup: production/demo separation, the staged install pipeline, and verify-kernels.

The install pipeline is exercised end to end (staging, published-checksum checks, fallback, SPICE
test load, commit) by pointing a test manifest at the kernel files of the session's kernel set.
That lock carries the profile "pipeline-test", lives only in a temporary folder, and can never be
taken for production kernels.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

from conftest import SRC_KERNELS, needs_kernels

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture
def isolated_dirs(tmp_path, monkeypatch):
    """Point the production and demo kernel folders at empty temporary folders for one test."""
    from lunaops import settings
    from lunaops.engine import kernels as K

    prod, demo = tmp_path / "kernels", tmp_path / "kernels_demo"
    prod.mkdir()
    demo.mkdir()
    monkeypatch.setattr(settings, "PRODUCTION_KERNEL_DIR", prod)
    monkeypatch.setattr(settings, "DEMO_KERNEL_DIR", demo)
    yield prod, demo
    # restore the session's kernel pool for the tests that follow
    K.reset()
    monkeypatch.undo()
    K.load()


def _md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def _source_set() -> tuple[Path, dict]:
    lock = json.loads((SRC_KERNELS / "lock.json").read_text())
    return SRC_KERNELS, lock


def _test_manifest(tmp_path: Path, src: Path, lock: dict, wrong_fk_md5: bool = True) -> tuple[Path, Path]:
    """A manifest naming the session's kernel files, with published-value checks that must pass or fail."""
    from_dir = tmp_path / "downloads"
    from_dir.mkdir()
    entries = []
    for f in lock["files"]:
        shutil.copyfile(src / f["name"], from_dir / f["name"])
        e = {"role": f["role"], "name": f["name"], "urls": [f"https://example.invalid/{f['name']}"]}
        if f["role"] == "spk":
            e["expected_md5"] = _md5(src / f["name"])                 # a correct published value
            e["expected_bytes"] = (src / f["name"]).stat().st_size
        if f["role"] == "lunar_fk" and wrong_fk_md5:
            e["expected_md5"] = "0" * 32                              # a wrong published value ...
            fb = "fallback_" + f["name"]
            shutil.copyfile(src / f["name"], from_dir / fb)           # ... so the fallback must be used
            e["fallback"] = {"name": fb, "urls": [f"https://example.invalid/{fb}"], "reason": "test fallback"}
        entries.append(e)
    man = {"profile": "pipeline-test", "body_fixed_frame": lock["body_fixed_frame"], "pa_frame": lock.get("pa_frame"),
           "files": entries}
    mp = tmp_path / "manifest.json"
    mp.write_text(json.dumps(man))
    return mp, from_dir


def _snapshot(d: Path) -> dict:
    return {p.relative_to(d).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(d.rglob("*")) if p.is_file()}


# --------------------------------------------------------------------------- separation
def test_kernel_sets_live_in_separate_folders(tmp_path):
    code = "from lunaops import settings as s; print(s.KERNEL_SET, s.KERNEL_DIR.name, s.PRODUCTION_KERNEL_DIR.name, s.DEMO_KERNEL_DIR.name)"
    out = {}
    for ks in ("production", "demo"):
        env = {**os.environ, "LUNAOPS_DATA_DIR": str(tmp_path), "LUNAOPS_KERNEL_SET": ks}
        out[ks] = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=env, capture_output=True,
                                 text=True, check=True).stdout.split()
    assert out["production"] == ["production", "kernels", "kernels", "kernels_demo"]
    assert out["demo"] == ["demo", "kernels_demo", "kernels", "kernels_demo"]
    env = {**os.environ, "LUNAOPS_DATA_DIR": str(tmp_path), "LUNAOPS_KERNEL_SET": "both"}
    assert subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=env, capture_output=True).returncode != 0


@needs_kernels
def test_demo_lock_in_production_folder_is_refused_then_migrated(isolated_dirs, monkeypatch):
    from lunaops import settings
    from lunaops.engine import kernels as K

    prod, demo = isolated_dirs
    src, lock = _source_set()
    if lock.get("profile") != "sandbox-test":
        pytest.skip("needs the sandbox test set as the session's kernel source")
    for f in lock["files"]:
        shutil.copyfile(src / f["name"], prod / f["name"])
    shutil.copyfile(src / "lock.json", prod / "lock.json")         # the layout used before separation
    monkeypatch.setattr(settings, "KERNEL_SET", "production")
    monkeypatch.setattr(settings, "KERNEL_DIR", prod)
    K.reset()
    with pytest.raises(K.KernelError, match="sandbox TEST"):
        K.load()
    msg = K.migrate_misplaced_demo_lock()
    assert msg and not (prod / "lock.json").exists() and (demo / "lock.json").exists()
    assert not any((prod / f["name"]).exists() for f in lock["files"])
    monkeypatch.setattr(settings, "KERNEL_SET", "demo")
    monkeypatch.setattr(settings, "KERNEL_DIR", demo)
    K.reset()
    assert K.load().profile == "sandbox-test"
    assert K.migrate_misplaced_demo_lock() is None                  # idempotent


# ---------------------------------------------------------------------- install pipeline
@needs_kernels
def test_install_pipeline_checks_stages_loads_and_commits(isolated_dirs, tmp_path):
    from lunaops.acquire import cmd_kernels

    prod, _ = isolated_dirs
    src, lock = _source_set()
    mp, from_dir = _test_manifest(tmp_path, src, lock)
    cmd_kernels(Namespace(from_dir=str(from_dir), manifest=str(mp)))
    new = json.loads((prod / "lock.json").read_text())
    assert new["profile"] == "pipeline-test" and not (prod / ".staging").exists()
    by_role = {f["role"]: f for f in new["files"]}
    assert by_role["spk"]["naif_md5_match"] is True
    assert by_role["lunar_fk"]["name"].startswith("fallback_") and "Fallback used" in by_role["lunar_fk"]["notes"]
    assert "trusted on first" in json.dumps(new) or "SHA-256 pinned" in json.dumps(new)
    for f in new["files"]:
        assert hashlib.sha256((prod / f["name"]).read_bytes()).hexdigest() == f["sha256"]
        assert f["obtained"].startswith("manual download")
    # a second install keeps the previous set
    cmd_kernels(Namespace(from_dir=str(from_dir), manifest=str(mp)))
    kept = [d for d in prod.iterdir() if d.name.startswith("superseded_")]
    assert len(kept) == 1 and (kept[0] / "lock.json").exists()


@needs_kernels
def test_failed_install_leaves_existing_set_untouched(isolated_dirs, tmp_path):
    from lunaops.acquire import cmd_kernels

    prod, _ = isolated_dirs
    src, lock = _source_set()
    mp, from_dir = _test_manifest(tmp_path, src, lock)
    cmd_kernels(Namespace(from_dir=str(from_dir), manifest=str(mp)))
    before = _snapshot(prod)
    # a required file missing from the download folder
    spk = next(f["name"] for f in lock["files"] if f["role"] == "spk")
    (from_dir / spk).unlink()
    with pytest.raises(SystemExit, match="was not changed"):
        cmd_kernels(Namespace(from_dir=str(from_dir), manifest=str(mp)))
    assert _snapshot(prod) == before and not (prod / ".staging").exists()
    # a file that fails its published size, with no fallback
    shutil.copyfile(src / spk, from_dir / spk)
    man = json.loads(mp.read_text())
    next(e for e in man["files"] if e["role"] == "spk")["expected_bytes"] += 1
    mp.write_text(json.dumps(man))
    with pytest.raises(SystemExit, match="NAIF publishes"):
        cmd_kernels(Namespace(from_dir=str(from_dir), manifest=str(mp)))
    assert _snapshot(prod) == before


@needs_kernels
def test_set_that_does_not_load_is_not_installed(isolated_dirs, tmp_path):
    from lunaops.acquire import cmd_kernels

    prod, _ = isolated_dirs
    src, lock = _source_set()
    mp, from_dir = _test_manifest(tmp_path, src, lock, wrong_fk_md5=False)
    man = json.loads(mp.read_text())
    man["body_fixed_frame"] = "NO_SUCH_FRAME"                      # SPICE cannot define it
    mp.write_text(json.dumps(man))
    with pytest.raises(SystemExit, match="did not load"):
        cmd_kernels(Namespace(from_dir=str(from_dir), manifest=str(mp)))
    assert not (prod / "lock.json").exists() and not (prod / ".staging").exists()


# --------------------------------------------------------------------------- verify
@needs_kernels
def test_verify_kernels_passes_then_catches_tampering(isolated_dirs, capsys):
    from lunaops.acquire import cmd_verify_kernels

    _, demo = isolated_dirs
    src, lock = _source_set()
    if lock.get("profile") != "sandbox-test":
        pytest.skip("checks the demo folder with the sandbox set")
    for f in lock["files"]:
        shutil.copyfile(src / f["name"], demo / f["name"])
    shutil.copyfile(src / "lock.json", demo / "lock.json")
    cmd_verify_kernels(Namespace(demo=True, offline=True))
    out = capsys.readouterr().out
    assert "Kernel set verified." in out and "V-02e prerequisites" in out and "NOT met" in out
    victim = demo / next(f["name"] for f in lock["files"] if f["role"] == "lunar_fk")
    victim.write_bytes(victim.read_bytes() + b"\n")
    with pytest.raises(SystemExit):
        cmd_verify_kernels(Namespace(demo=True, offline=True))
    assert "FAILED" in capsys.readouterr().out


# -------------------------------------------------------------------------- manifest
def test_production_manifest_is_pinned_and_checkable():
    man = json.loads((BACKEND / "lunaops" / "manifests" / "kernels.production.json").read_text())
    assert man["profile"] == "production" and man["body_fixed_frame"] == "MOON_ME_DE440_ME421"
    roles = {f["role"] for f in man["files"]}
    assert {"lsk", "text_pck", "spk", "lunar_pck", "lunar_fk", "de421_pck", "de421_fk"} <= roles
    for f in man["files"]:
        names = [f["name"]] + ([f["fallback"]["name"]] if f.get("fallback") else [])
        assert not any("latest" in n for n in names)                      # Q15: never a moving link
        urls = f["urls"] + (f["fallback"]["urls"] if f.get("fallback") else [])
        assert all(u.startswith("https://naif.jpl.nasa.gov/pub/naif/") for u in urls)
        if "expected_md5" in f:
            assert len(f["expected_md5"]) == 32 and int(f["expected_md5"], 16) >= 0
    by = {f["role"]: f for f in man["files"]}
    assert by["lsk"]["expected_bytes"] == 5257 and by["lsk"]["expected_md5"] == "25a2fff30b0dedb4d76c06727b1895b1"
    assert by["lunar_fk"]["expected_bytes"] == 19478
    # IB-2 (resolved 2026-11-09): 250416 is the authoritative DE440 FK; the superseded 220930 is only a fallback,
    # fetched from NAIF's a_old_versions folder (its former fk/satellites URL returns 404 and is not listed)
    assert by["lunar_fk"]["name"] == "moon_de440_250416.tf" and by["lunar_fk"]["expected_md5"] == "3556dde4bb7ca54a89917c301e650bbf"
    assert by["lunar_fk"]["fallback"]["urls"] == [
        "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/fk/satellites/a_old_versions/moon_de440_220930.tf"]
    assert "open_issue" not in by["lunar_fk"] and by["lunar_fk"]["resolved_issue"].startswith("IB-2 resolved")
    assert by["de421_fk"]["name"] == "moon_080317.tf"                     # DE421 frames for V-02e, retained
    assert by["de421_pck"].get("optional") and by["de421_fk"].get("optional")


def test_checksum_listing_parsed_in_any_common_layout():
    from lunaops.acquire import parse_checksum_text

    h = "3917ee56769db332790c751e2168843d"
    for text in (f"{h}  de440s.bsp", f"de440s.bsp   {h}", f"MD5 (de440s.bsp) = {h}", f"{h} *de440s.bsp",
                 f"de440.bsp  {'0' * 32}\nde440s.bsp  {h.upper()}"):
        assert parse_checksum_text(text)["de440s.bsp"] == h, text
    assert parse_checksum_text(f"{h}0  de440s.bsp") == {}          # 33 hex digits is not a digest
    assert "de440s.bsp" not in parse_checksum_text(f"{h}  de440.bsp")
