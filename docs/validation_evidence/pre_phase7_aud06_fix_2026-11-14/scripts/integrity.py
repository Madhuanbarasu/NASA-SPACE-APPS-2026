"""Read-only integrity snapshot: engine and suite fingerprints, protected-file hashes, cached results and horizons.

Usage: python integrity.py   (prints a stable text report; compare a before and an after run with diff)
"""
import hashlib, sqlite3, sys
from pathlib import Path
ROOT = Path(r"E:\LUNA-OPS")
sys.path.insert(0, str(ROOT / "backend"))
from lunaops.fingerprint import code_fingerprint, suite_fingerprint  # noqa: E402

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
print("code_fingerprint", code_fingerprint())
print("suite_fingerprint", suite_fingerprint())
for rel in ("backend/validation/report.json", "backend/lunaops/api/tiles.py", "backend/lunaops/api/main.py", "data/dem/registry.json"):
    print("sha256", rel, sha(ROOT / rel))
tree = hashlib.sha256()
for p in sorted((ROOT / "backend/lunaops").rglob("*")):
    if p.is_file() and "__pycache__" not in p.parts:
        tree.update(p.relative_to(ROOT).as_posix().encode()); tree.update(sha(p).encode())
print("backend/lunaops tree digest (all files, no __pycache__)", tree.hexdigest())
cache = ROOT / "data/cache"
hz = sorted(cache.glob("horizon_*.npz"))
hd = hashlib.sha256()
for p in hz: hd.update(p.name.encode()); hd.update(sha(p).encode())
print("cached horizons", len(hz), "digest", hd.hexdigest())
con = sqlite3.connect(f"file:{(cache / 'cache.sqlite').as_posix()}?mode=ro", uri=True)
tables = [r[0] for r in con.execute("select name from sqlite_master where type='table' order by name")]
for t in tables:
    n = con.execute(f"select count(*) from {t}").fetchone()[0]
    cols = [r[1] for r in con.execute(f"pragma table_info({t})")]
    key = cols[0]
    d = hashlib.sha256()
    for (k,) in con.execute(f"select {key} from {t} order by {key}"):
        d.update(str(k).encode()); d.update(b"\0")
    print(f"cache table {t}: {n} rows; digest of {key} column {d.hexdigest()}")
con.close()
# the audit's 74 results: those created before the audit's own browser run (2026-11-13 20:00 UTC)
import datetime  # noqa: E402
con = sqlite3.connect(f"file:{(cache / 'cache.sqlite').as_posix()}?mode=ro", uri=True)
cut = datetime.datetime(2026, 11, 13, 20, 0, tzinfo=datetime.timezone.utc).timestamp()
ids = [r[0] for r in con.execute("select id from results where created < ? order by id", (cut,))]
missing = [i for i, p in con.execute("select id, path from results where created < ?", (cut,)) if not (cache / Path(p).name).exists() and not Path(p).exists()]
print(f"results created before 2026-11-13 20:00 UTC (the audit's count): {len(ids)}; files missing: {len(missing)}; "
      f"digest {hashlib.sha256(chr(0).join(ids).encode()).hexdigest()}")
hpaths = [p for (p,) in con.execute("select path from horizons")]
print(f"indexed horizons with their file present: {sum(1 for p in hpaths if (cache / Path(p).name).exists() or Path(p).exists())} of {len(hpaths)}")
con.close()
