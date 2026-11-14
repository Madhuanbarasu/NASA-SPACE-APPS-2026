import type { TerrainGrid } from "../api/types";

// Statistics of a served terrain grid (GET /api/terrain), shared by the explorer's local terrain and the analysis
// terrain (Phase 3). Valid cells only: cells without data are never filled, and they are counted as missing.

export interface GridStats { valid: number; total: number; min: number; max: number; mean: number; centre: number | null; cellM: number }

/** Statistics of the served grid (valid cells only); `centre` is the mean of the four central cells that have data. */
export function gridStats(g: TerrainGrid): GridStats | null {
  const vals = g.heights.filter((v): v is number => v != null && Number.isFinite(v));
  if (!vals.length) return null;
  let min = Infinity, max = -Infinity, sum = 0;
  for (const v of vals) { if (v < min) min = v; if (v > max) max = v; sum += v; }
  const n = g.n, a = Math.floor((n - 1) / 2), b = Math.ceil((n - 1) / 2);
  const mid = [g.heights[a * n + a], g.heights[a * n + b], g.heights[b * n + a], g.heights[b * n + b]]
    .filter((v): v is number => v != null && Number.isFinite(v));
  return { valid: vals.length, total: g.heights.length, min, max, mean: sum / vals.length,
    centre: mid.length ? mid.reduce((s, v) => s + v, 0) / mid.length : null, cellM: (2 * g.radius_m) / (n - 1) };
}

/**
 * Triangle indices of a grid mesh drawing only cells whose four corners have data (no height is filled in), and the
 * display colour of each vertex: the same height-to-grey ramp in both terrain views (dark = lowest, light = highest).
 */
export function gridMesh(g: TerrainGrid, stats: GridStats): { index: number[]; colors: Float32Array } {
  const n = g.n;
  const has = (i: number) => g.heights[i] != null && Number.isFinite(g.heights[i] as number);
  const index: number[] = [];
  for (let r = 0; r < n - 1; r++) {
    for (let c = 0; c < n - 1; c++) {
      const a = r * n + c, b = a + 1, d = a + n, e = d + 1;
      if (has(a) && has(b) && has(d) && has(e)) index.push(a, d, b, d, e, b);
    }
  }
  const colors = new Float32Array(n * n * 3);
  const span = Math.max(1, stats.max - stats.min);
  for (let i = 0; i < n * n; i++) {
    const k = has(i) ? ((g.heights[i] as number) - stats.min) / span : 0;
    colors.set([0.32 + 0.6 * k, 0.34 + 0.58 * k, 0.38 + 0.52 * k], 3 * i);
  }
  return { index, colors };
}
