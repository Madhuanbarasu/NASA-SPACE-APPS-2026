// Scale bar of the south polar map (display only, no scientific value). Distances are great-circle distances on the
// 1737.4 km reference sphere, the radius the map's polar stereographic projection uses (MapView). OpenLayers' own
// ScaleLine is not used: it measures with the Earth's radius.

export const MOON_RADIUS_M = 1737400;
const RAD = Math.PI / 180;

/** Great-circle distance in metres between two latitude/longitude points (degrees) on the reference sphere. */
export function greatCircleM(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const p1 = lat1 * RAD, p2 = lat2 * RAD, dp = p2 - p1, dl = (lon2 - lon1) * RAD;
  const a = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * MOON_RADIUS_M * Math.atan2(Math.sqrt(a), Math.sqrt(Math.max(0, 1 - a)));
}

/** The longest 1, 2 or 5 x 10^k metre length that fits in maxPx at `metresPerPx`, and its length in pixels. */
export function niceScale(metresPerPx: number, maxPx = 120): { metres: number; px: number } | null {
  if (!(metresPerPx > 0) || !Number.isFinite(metresPerPx)) return null;
  const target = metresPerPx * maxPx;
  const p = 10 ** Math.floor(Math.log10(target));
  let best = p;
  for (const n of [2, 5]) if (n * p <= target) best = n * p;
  return { metres: best, px: best / metresPerPx };
}
