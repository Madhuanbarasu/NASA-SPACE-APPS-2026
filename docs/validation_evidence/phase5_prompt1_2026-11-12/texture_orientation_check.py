"""Orientation check of the NASA SVS CGI Moon Kit textures against known lunar features (read-only).
Run with the backend venv Python (Pillow is already installed):  python -I texture_orientation_check.py <colour.jpg> <ldem.jpg>
Equirectangular, centred on 0 deg longitude (SVS page): x = (lon_signed + 180)/360 * W, y = (90 - lat)/180 * H.
A feature is checked against its mirror positions (longitude sign flipped, latitude sign flipped); the dark maria and
crater floors must be darker than the highland mirror positions if the map is neither mirrored nor flipped."""
import sys
from PIL import Image

def mean(im, lat, lon, half=3):
    W, H = im.size
    x = int((((lon + 180) % 360) / 360) * W); y = int((90 - lat) / 180 * H)
    px = [im.getpixel(((x + dx) % W, min(H - 1, max(0, y + dy)))) for dx in range(-half, half + 1) for dy in range(-half, half + 1)]
    px = [sum(p) / 3 if isinstance(p, tuple) else p for p in px]
    return sum(px) / len(px)

col = Image.open(sys.argv[1]).convert("RGB"); dem = Image.open(sys.argv[2]).convert("L")
ok = True
tests = [  # (name, lat, lon signed east, mirror kind)
    ("Mare Moscoviense (farside mare)", 27.3, 147.9, "lon"),
    ("Tsiolkovskiy crater floor", -20.4, 129.1, "lon"),
    ("Mare Crisium", 17.0, 59.1, "lat"),
    ("Mare Imbrium", 32.8, -15.6, "lat"),
    ("Mare Orientale (inner)", -19.9, -92.8, "lon")]
print("colour map (mean 0-255 in a 7x7 window): feature vs mirror")
for name, lat, lon, kind in tests:
    m_lat, m_lon = (lat, -lon) if kind == "lon" else (-lat, lon)
    a, b = mean(col, lat, lon), mean(col, m_lat, m_lon)
    good = a < b
    ok &= good
    print(f"  {name:32s} ({lat:+.1f}, {lon:+.1f}) {a:6.1f}  vs mirror ({m_lat:+.1f}, {m_lon:+.1f}) {b:6.1f}  -> {'darker: OK' if good else 'NOT darker'}")
print("relief map (8-bit, brighter = higher is expected): South Pole-Aitken basin floor vs farside highlands")
spa, high = mean(dem, -53.0, -169.0, 4), mean(dem, 5.0, -160.0, 4)   # SPA interior is the deepest large basin; the farside highlands near 5N 160W are among the highest terrain
good = spa < high
ok &= good
print(f"  SPA (-53, -169) {spa:6.1f}  vs farside highlands (+5, -160) {high:6.1f}  -> {'lower: OK' if good else 'NOT lower'}")
print("ORIENTATION OK" if ok else "ORIENTATION CHECK FAILED")
sys.exit(0 if ok else 1)
