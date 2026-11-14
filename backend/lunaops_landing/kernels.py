"""Numerical kernels for landing hazard screening (numba, float64 arithmetic, NaN = no data).

Conventions shared by every kernel:
* z is a 2-D height grid (metres) on the projected DEM grid; row 0 is the north edge of the projection grid.
* A result that would need a missing (NaN) input sample is NaN. Missing terrain is never filled, interpolated
  or replaced by a flat surface; edge pixels without a complete neighbourhood are NaN.
* Horizontal spacing is given per pixel (dx_m, dy_m arrays or scalars broadcast by the caller) so the
  projection's point scale and the height above the sphere are taken into account by the caller.
"""
from __future__ import annotations

import math

import numpy as np
from numba import njit


# ------------------------------------------------------------------ slope (Horn 1981)
@njit(cache=True)
def slope_horn(z, gx_m, gy_m):
    """Slope in degrees by Horn's (1981) 3x3 weighted finite differences.

    dz/dx = ((c + 2f + i) - (a + 2d + g)) / (8 dx),  dz/dy = ((g + 2h + i) - (a + 2b + c)) / (8 dy)
    over the neighbourhood  a b c / d e f / g h i.  gx_m, gy_m: ground spacing (m) between pixel centres along
    columns and rows, per pixel. NaN when any of the 9 samples is missing, and on the outer ring."""
    nr, nc = z.shape
    out = np.full((nr, nc), np.nan, dtype=np.float32)
    for r in range(1, nr - 1):
        for c in range(1, nc - 1):
            a = z[r - 1, c - 1]; b = z[r - 1, c]; cc = z[r - 1, c + 1]
            d = z[r, c - 1]; e = z[r, c]; f = z[r, c + 1]
            g = z[r + 1, c - 1]; h = z[r + 1, c]; i = z[r + 1, c + 1]
            s = a + b + cc + d + e + f + g + h + i
            if not np.isfinite(s):
                continue
            dzdx = ((cc + 2.0 * f + i) - (a + 2.0 * d + g)) / (8.0 * gx_m[r, c])
            dzdy = ((g + 2.0 * h + i) - (a + 2.0 * b + cc)) / (8.0 * gy_m[r, c])
            out[r, c] = math.degrees(math.atan(math.sqrt(dzdx * dzdx + dzdy * dzdy)))
    return out


# ------------------------------------------------------------------ roughness
@njit(cache=True)
def detrended_rms(z, half):
    """RMS (metres) of the residuals about the least-squares plane fitted to the (2*half+1)^2 window centred on
    each pixel. Only complete windows are evaluated (any missing sample -> NaN). Residuals are independent of the
    horizontal scale, so pixel indices serve as plane coordinates. Two-pass sums (window mean removed first) keep
    the result exact to float64 rounding."""
    nr, nc = z.shape
    out = np.full((nr, nc), np.nan, dtype=np.float32)
    w = 2 * half + 1
    n = w * w
    suu = 0.0
    for u in range(-half, half + 1):
        suu += u * u
    suu *= w                       # sum of u^2 over the full window (equal for v)
    for r in range(half, nr - half):
        for c in range(half, nc - half):
            s = 0.0
            ok = True
            for dr in range(-half, half + 1):
                for dc in range(-half, half + 1):
                    v = z[r + dr, c + dc]
                    if not np.isfinite(v):
                        ok = False
                        break
                    s += v
                if not ok:
                    break
            if not ok:
                continue
            m = s / n
            sse = 0.0
            suz = 0.0
            svz = 0.0
            for dr in range(-half, half + 1):
                for dc in range(-half, half + 1):
                    t = z[r + dr, c + dc] - m
                    sse += t * t
                    suz += dc * t
                    svz += dr * t
            rss = sse - suz * suz / suu - svz * svz / suu
            if rss < 0.0:
                rss = 0.0
            out[r, c] = math.sqrt(rss / n)
    return out


@njit(cache=True)
def tri_riley(z):
    """Terrain Ruggedness Index (Riley, DeGloria and Elliot 1999): square root of the sum of squared height
    differences between a pixel and its 8 neighbours (metres, at the DEM pixel scale). NaN unless all 9 exist."""
    nr, nc = z.shape
    out = np.full((nr, nc), np.nan, dtype=np.float32)
    for r in range(1, nr - 1):
        for c in range(1, nc - 1):
            e = z[r, c]
            if not np.isfinite(e):
                continue
            s = 0.0
            ok = True
            for dr in range(-1, 2):
                for dc in range(-1, 2):
                    if dr == 0 and dc == 0:
                        continue
                    v = z[r + dr, c + dc]
                    if not np.isfinite(v):
                        ok = False
                        break
                    s += (v - e) * (v - e)
                if not ok:
                    break
            if ok:
                out[r, c] = math.sqrt(s)
    return out


# ------------------------------------------------------------------ depressions (priority flood)
@njit(cache=True)
def _heap_push(keys, idx, n, k, i):
    j = n
    keys[j] = k
    idx[j] = i
    while j > 0:
        p = (j - 1) >> 1
        if keys[p] <= keys[j]:
            break
        keys[p], keys[j] = keys[j], keys[p]
        idx[p], idx[j] = idx[j], idx[p]
        j = p
    return n + 1


@njit(cache=True)
def _heap_pop(keys, idx, n):
    k = keys[0]
    i = idx[0]
    n -= 1
    keys[0] = keys[n]
    idx[0] = idx[n]
    j = 0
    while True:
        l = 2 * j + 1
        if l >= n:
            break
        m = l
        if l + 1 < n and keys[l + 1] < keys[l]:
            m = l + 1
        if keys[j] <= keys[m]:
            break
        keys[j], keys[m] = keys[m], keys[j]
        idx[j], idx[m] = idx[m], idx[j]
        j = m
    return k, i, n


@njit(cache=True)
def fill_depth(z):
    """Depth (m) of each pixel below its depression's spill level: Priority-Flood depression filling
    (Barnes, Lehman and Mulla 2014, Algorithm 1; 8-connectivity) minus the original height.

    The flood starts from the grid border and from every pixel next to missing data, so depth is measured only
    below the lowest level at which a hollow could drain to the window edge or into a data gap: a gap can never make
    a hollow look deeper, and a hollow open to the edge or to a gap has no depth. Missing pixels stay NaN.
    """
    nr, nc = z.shape
    n_all = nr * nc
    filled = np.empty((nr, nc), dtype=np.float64)
    for r in range(nr):
        for c in range(nc):
            filled[r, c] = z[r, c]
    closed = np.zeros((nr, nc), dtype=np.uint8)
    keys = np.empty(n_all, dtype=np.float64)
    idx = np.empty(n_all, dtype=np.int64)
    n = 0
    for r in range(nr):
        for c in range(nc):
            if not np.isfinite(z[r, c]):
                closed[r, c] = 1
                continue
            seed = r == 0 or c == 0 or r == nr - 1 or c == nc - 1
            if not seed:
                for dr in range(-1, 2):
                    for dc in range(-1, 2):
                        if not np.isfinite(z[r + dr, c + dc]):
                            seed = True
            if seed:
                closed[r, c] = 1
                n = _heap_push(keys, idx, n, filled[r, c], r * nc + c)
    while n > 0:
        k, i, n = _heap_pop(keys, idx, n)
        r = i // nc
        c = i - r * nc
        for dr in range(-1, 2):
            for dc in range(-1, 2):
                rr = r + dr
                cc = c + dc
                if rr < 0 or cc < 0 or rr >= nr or cc >= nc or closed[rr, cc]:
                    continue
                closed[rr, cc] = 1
                if filled[rr, cc] < k:
                    filled[rr, cc] = k
                n = _heap_push(keys, idx, n, filled[rr, cc], rr * nc + cc)
    out = np.full((nr, nc), np.nan, dtype=np.float32)
    for r in range(nr):
        for c in range(nc):
            if np.isfinite(z[r, c]):
                out[r, c] = filled[r, c] - z[r, c]
    return out


@njit(cache=True)
def label8(mask):
    """8-connected component labels (1..n, 0 = background) of a boolean mask; returns (labels, n)."""
    nr, nc = mask.shape
    lab = np.zeros((nr, nc), dtype=np.int32)
    stack = np.empty(nr * nc, dtype=np.int64)
    n = 0
    for r0 in range(nr):
        for c0 in range(nc):
            if not mask[r0, c0] or lab[r0, c0] != 0:
                continue
            n += 1
            lab[r0, c0] = n
            sp = 0
            stack[sp] = r0 * nc + c0
            sp += 1
            while sp > 0:
                sp -= 1
                i = stack[sp]
                r = i // nc
                c = i - r * nc
                for dr in range(-1, 2):
                    for dc in range(-1, 2):
                        rr = r + dr
                        cc = c + dc
                        if 0 <= rr < nr and 0 <= cc < nc and mask[rr, cc] and lab[rr, cc] == 0:
                            lab[rr, cc] = n
                            stack[sp] = rr * nc + cc
                            sp += 1
    return lab, n


@njit(cache=True)
def component_moments(lab, n, depth, err, count):
    """Per component k (row k-1): [pixels, sum_r, sum_c, sum_rr, sum_cc, sum_rc, max_depth, r_at_max, c_at_max,
    err_sum, err_n, measured_n, count_n]. err/count may be all-NaN arrays when unavailable."""
    nr, nc = lab.shape
    m = np.zeros((n, 13), dtype=np.float64)
    for k in range(n):
        m[k, 6] = -1.0
    for r in range(nr):
        for c in range(nc):
            k = lab[r, c]
            if k == 0:
                continue
            row = k - 1
            m[row, 0] += 1.0
            m[row, 1] += r
            m[row, 2] += c
            m[row, 3] += r * r
            m[row, 4] += c * c
            m[row, 5] += r * c
            d = depth[r, c]
            if d > m[row, 6]:
                m[row, 6] = d
                m[row, 7] = r
                m[row, 8] = c
            e = err[r, c]
            if np.isfinite(e):
                m[row, 9] += e
                m[row, 10] += 1.0
            q = count[r, c]
            if np.isfinite(q):
                m[row, 12] += 1.0
                if q > 0:
                    m[row, 11] += 1.0
    return m
