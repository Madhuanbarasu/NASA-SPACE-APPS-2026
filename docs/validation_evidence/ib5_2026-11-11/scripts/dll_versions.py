"""Read the version resource (VS_VERSIONINFO StringFileInfo) of every vendored DLL/PYD via the Win32 API.
Also records size and SHA-256. Local files only.
    python -I dll_versions.py <site-packages> <out.json>
"""
import ctypes
import hashlib
import json
import sys
from ctypes import wintypes
from pathlib import Path

site, out = Path(sys.argv[1]), Path(sys.argv[2])
ver = ctypes.WinDLL("version")
ver.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
ver.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
ver.VerQueryValueW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.UINT)]
FIELDS = ("CompanyName", "FileDescription", "FileVersion", "ProductName", "ProductVersion", "LegalCopyright", "OriginalFilename", "Comments")


def info(p: Path) -> dict:
    size = ver.GetFileVersionInfoSizeW(str(p), None)
    if not size:
        return {}
    buf = ctypes.create_string_buffer(size)
    if not ver.GetFileVersionInfoW(str(p), 0, size, buf):
        return {}
    ptr, n = ctypes.c_void_p(), wintypes.UINT()
    langs = []
    if ver.VerQueryValueW(buf, "\\VarFileInfo\\Translation", ctypes.byref(ptr), ctypes.byref(n)) and n.value:
        arr = (wintypes.WORD * (n.value // 2)).from_address(ptr.value)
        langs = [(arr[i], arr[i + 1]) for i in range(0, len(arr), 2)]
    langs += [(0x0409, 0x04B0), (0x0409, 0x04E4), (0x0000, 0x04B0)]
    res = {}
    for lang, cp in langs:
        for f in FIELDS:
            if f in res:
                continue
            q = f"\\StringFileInfo\\{lang:04x}{cp:04x}\\{f}"
            if ver.VerQueryValueW(buf, q, ctypes.byref(ptr), ctypes.byref(n)) and n.value:
                v = ctypes.wstring_at(ptr.value, n.value).rstrip("\x00").strip()
                if v:
                    res[f] = v
    return res


targets = []
for d in sorted(site.glob("*.libs")):
    targets += sorted(d.glob("*.dll"))
for rel in ("llvmlite/binding/llvmlite.dll", "spiceypy/utils/cspice.dll"):
    if (site / rel).exists():
        targets.append(site / rel)
rows = []
for p in targets:
    rows.append({"file": p.relative_to(site).as_posix(), "bytes": p.stat().st_size,
                 "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "version_resource": info(p)})
json.dump(rows, open(out, "w"), indent=1)
for r in rows:
    v = r["version_resource"]
    print(f"{r['file']:62} | {v.get('ProductName', '-')[:28]:28} | {v.get('ProductVersion', v.get('FileVersion', '-'))[:16]:16} | {v.get('LegalCopyright', '-')[:80]}")
