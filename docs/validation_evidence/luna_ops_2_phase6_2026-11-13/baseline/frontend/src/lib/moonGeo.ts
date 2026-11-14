// Geometry of the 3D Moon globe (display only; no scientific computation).
//
// Globe frame: unit sphere, +y = lunar north pole, (lat 0, lon 0) on +x, east longitude increasing towards -z.
// This is exactly the frame three.js SphereGeometry uses for an equirectangular texture centred on 0 deg longitude
// (u = (lon + 180) / 360, v = (lat + 90) / 180), so a vertex, its texture coordinate and its latitude/longitude agree.
// Latitudes are planetocentric degrees (+north); longitudes are degrees east in [0, 360), the convention LUNA-OPS uses for
// site coordinates. scripts/check-moon-geo.mjs tests these functions against three.js itself.

export interface GlobeLocation {
  /** degrees, +north, [-90, 90] */
  lat: number;
  /** degrees east, [0, 360) */
  lon: number;
}

const RAD = Math.PI / 180;

/** Longitude in [0, 360). */
export function lon360(lon: number): number {
  const v = ((lon % 360) + 360) % 360;
  return v === 360 ? 0 : v;
}

/** Longitude in [-180, 180). */
export function lon180(lon: number): number {
  const v = lon360(lon);
  return v >= 180 ? v - 360 : v;
}

/** Unit vector of a latitude/longitude in the globe frame. */
export function latLonToUnit(lat: number, lon: number): [number, number, number] {
  const la = lat * RAD, lo = lon * RAD;
  return [Math.cos(la) * Math.cos(lo), Math.sin(la), -Math.cos(la) * Math.sin(lo)];
}

/** Latitude/longitude of a (not necessarily unit) vector in the globe frame. */
export function unitToLatLon(x: number, y: number, z: number): GlobeLocation {
  const r = Math.hypot(x, y, z);
  const lat = Math.asin(Math.max(-1, Math.min(1, y / r))) / RAD;
  const lon = Math.abs(lat) > 90 - 1e-9 ? 0 : lon360(Math.atan2(-z, x) / RAD);
  return { lat, lon };
}

/** Equirectangular texture coordinate (three.js convention, v = 0 at the bottom) of a latitude/longitude. */
export function textureUV(lat: number, lon: number): [number, number] {
  return [(lon180(lon) + 180) / 360, (lat + 90) / 180];
}

/**
 * First intersection of a ray with the unit sphere (exact, so a pick does not depend on the mesh tessellation).
 * Returns null when the ray misses.
 */
export function raySphere(origin: [number, number, number], dir: [number, number, number]): [number, number, number] | null {
  const [ox, oy, oz] = origin;
  const n = Math.hypot(dir[0], dir[1], dir[2]);
  const dx = dir[0] / n, dy = dir[1] / n, dz = dir[2] / n;
  const b = ox * dx + oy * dy + oz * dz;
  const c = ox * ox + oy * oy + oz * oz - 1;
  const disc = b * b - c;
  if (disc < 0) return null;
  const t = -b - Math.sqrt(disc);
  if (t < 0) return null;
  return [ox + t * dx, oy + t * dy, oz + t * dz];
}

/**
 * The one conversion from a picked location (globe or map) to the site coordinates kept in the store: latitude and
 * east longitude rounded to 1e-6 deg (about 3 cm, the precision the map already used), longitude in [0, 360) after
 * rounding (so 359.9999999 becomes 0, never 360), latitude clamped to [-90, 90].
 */
export function siteCoords(lat: number, lon: number): GlobeLocation {
  const la = Math.max(-90, Math.min(90, Number(lat.toFixed(6))));
  let lo = Number(lon360(lon).toFixed(6));
  if (lo >= 360) lo -= 360;
  return { lat: la === 0 ? 0 : la, lon: lo === 0 ? 0 : lo };
}

/**
 * Site coordinates as typed (strings in the store) -> a location, or null when either is empty, not a number or out of
 * range. Accepts the same inputs as the backend (latitude -90..90, longitude -360..360, normalised to [0, 360)).
 */
export function parseSite(lat: string, lon: string): GlobeLocation | null {
  if (lat.trim() === "" || lon.trim() === "") return null;
  const la = Number(lat), lo = Number(lon);
  if (!Number.isFinite(la) || !Number.isFinite(lo) || la < -90 || la > 90 || lo < -360 || lo > 360) return null;
  return { lat: la, lon: lon360(lo) };
}

/** Great-circle angle between two locations, degrees (atan2 form: accurate for tiny and near-antipodal angles). */
export function angularDistance(a: GlobeLocation, b: GlobeLocation): number {
  const p = latLonToUnit(a.lat, a.lon), q = latLonToUnit(b.lat, b.lon);
  const cx = p[1] * q[2] - p[2] * q[1], cy = p[2] * q[0] - p[0] * q[2], cz = p[0] * q[1] - p[1] * q[0];
  return Math.atan2(Math.hypot(cx, cy, cz), p[0] * q[0] + p[1] * q[1] + p[2] * q[2]) / RAD;
}
