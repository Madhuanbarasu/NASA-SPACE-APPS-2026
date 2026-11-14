# Landing screening algorithms and parameters (landing 0.1.0)

**Code:** `backend/lunaops_landing/` (kernels in `kernels.py`, orchestration in `assess.py`). Every algorithm and parameter below is also returned in each result's `provenance.algorithms` and `provenance.config`.

## Data access (`sources.py`)
- **Product choice.** The finest usable registered product whose grid fully contains the square analysis window, or the product the user names; it is refused if it does not cover the window.
- **Window size.** At most 1201 × 1201 pixels (`MAX_SIDE_PX`); larger requests are reduced, and the size used is reported.
- **Heights.** Read through the engine's `dem._read_block` (nodata, scale, offset and ±20 km plausibility exactly as in the validated engine).
- **Refusal (C08).** `dem._refuse_broken` refuses the window if a registered product that would cover it is missing or changed.
- **Error map.** The DEM's registered error map, used only if registered for these exact DEM bytes and on the same grid. Negative and non-finite values become missing.
- **Auxiliary products.** Read from `data/landing/manifest.json`. Each is used only if its `dem_sha256`, transform, size, byte count and SHA-256 match (hashed once per process). A refused file is reported in `provenance.notes`.
- **Projection.** Forward: the engine's `south_polar_stereo_xy`. Inverse: ρ = 2R tan(α/2), x = ρ sin λ, y = ρ cos λ. Point scale k = 1 + (ρ/2R)² = 2/(1 − sin φ).

## Slope (Horn 1981)
- **Gradients:** dz/dx = ((c + 2f + i) − (a + 2d + g)) / (8 Δx) and dz/dy = ((g + 2h + i) − (a + 2b + c)) / (8 Δy). The slope is atan(√(dz/dx² + dz/dy²)), in degrees.
- **Ground spacing:** Δ = pixel / k × (R + h)/R. That is the projected pixel size divided by the point scale, at the pixel's height above the 1737.4 km sphere. At Site01 k = 1.00003, and (R + h)/R is up to about 1.001.
- **Missing data:** NaN if any of the 9 samples is missing, and on the outer ring of the window.
- **Statistics:** min, max, mean, median and 95th percentile over valid pixels. Display bands are 0, 5, 10, 15, 20, 25, 30 and 90°; they are not thresholds.

## Roughness
- **Detrended RMS.** The RMS of the residuals about the least-squares plane fitted to a w × w window (w = 3, 5, 9, 15 or 25 pixels; the physical baseline is w × pixel).
  - Only complete windows are evaluated; one missing sample gives NaN.
  - It uses two-pass sums, with the window mean removed first. It matches `numpy.linalg.lstsq` to a relative 1e-5 in the tests.
- **Multi-scale table:** w = 3, 5, 9 and 15 for every window.
- **TRI (Riley, DeGloria and Elliot 1999):** the square root of the sum of squared height differences to the 8 neighbours, in metres, at the pixel scale.
- **Interpretation.** These measures describe the DEM surface at its resolution. They are not rock or boulder detection.

## Depression candidates
1. **Priority-Flood depression filling** (Barnes, Lehman and Mulla 2014, Algorithm 1; 8-connectivity; no epsilon gradient).
   - Seeds are the window border and every pixel next to missing data.
   - Depth is the filled height minus the DEM height, so it counts only below the level at which a hollow could drain to the window edge or into a data gap; a gap never deepens a hollow.
2. **Regions.** Pixels with depth above 0.01 m (`DEPTH_FLOOR_M`) are grouped into 8-connected regions (`label8`).
3. **Kept regions.** A region is kept if it has at least 9 pixels (`MIN_CANDIDATE_PX`), a maximum depth at least the user's minimum depth (default 1.0 m, a user setting), and an area-equivalent diameter inside the user's optional range. At most 1000 are listed.
4. **Per candidate:**
   - centre (centroid) and deepest point, in latitude and longitude;
   - area-equivalent diameter: D = 2√(A/π), with A = pixels × (pixel/k)²;
   - depth below the spill level;
   - second-moment ellipse: axes 4√λ (pixel discretisation 1/12 added), orientation, axis ratio √(λ₂/λ₁), and ellipse fill n / (4π√(λ₁λ₂));
   - mean RMS height uncertainty inside the region, and depth / uncertainty;
   - share of pixels with a LOLA return, where a count map exists.
5. **Quality class** (a screening convention of landing 0.1.0, not a published criterion):
   - **defined:** depth ≥ 3 × uncertainty, axis ratio ≥ 0.5 and fill ≥ 0.6;
   - **weak:** depth ≥ 1 × uncertainty, otherwise;
   - **within uncertainty:** depth < 1 × uncertainty;
   - **shape only:** no error map.
6. **Status.** Every candidate is `unconfirmed_candidate`; no crater catalogue is integrated.

## Footprint
- **Geometry.** A circle of radius r metres on the 1737.4 km sphere becomes a map radius of r × k at the centre. The footprint takes the pixels whose centres lie inside it.
- **Outside the window.** If the circle does not lie fully inside the analysed window, every terrain finding is "Insufficient terrain data". The workspace offers to screen a window centred on the footprint.
- **Coverage reported:** pixels; valid share; measured share (count map) or "unavailable"; mean and maximum of the height uncertainty; mean and maximum of the NASA slope uncertainty; median and maximum of the NASA slope product.
- **Findings** (each separate; there is no combination):

| Finding | Values | Status rule (in this order) |
|---|---|---|
| Slope | min, median, max; % above threshold | valid share < minimum terrain data (user, default 95%) → *Insufficient terrain data*; footprint narrower than 3 pixels → *Requires higher-resolution data*; no threshold → *No threshold configured (values shown)*; any valid pixel above threshold → *Potential hazard detected*; otherwise *No configured threshold exceeded* |
| Roughness (chosen window) | the same | the same |
| Elevation range | max − min | the same, with the relief threshold |
| Depressions | intersecting candidate ids | low coverage → *Insufficient*; any candidate pixel inside → *Potential hazard detected*; footprint < 3 pixels → *Requires higher-resolution data*; otherwise *No candidate detected at this resolution* (with the detection limits stated) |
| Obstacles | – | always *Not available - manual review required* |

**Thresholds.** There are no defaults; every threshold is a user-defined assumption and is recorded with the result. The landing package supplies no published landing limit.

## Rendering (`render.py`)
- **Grid.** One PNG pixel per DEM pixel, row 0 at the north edge of the projection grid, and missing data transparent. The image's extent is the window's pixel-edge bounds, so OpenLayers' `ImageStatic` aligns it pixel for pixel, with interpolation off.
- **Ramps.** Cividis-like for elevation, magma-like for slope, plasma-like for roughness and viridis-like for uncertainty.
- **Ranges.**
  - Slope: fixed 0–40°, clipped above, and the legend says "40 or more".
  - Elevation: the 2nd to 98th percentile.
  - Roughness and uncertainty: 0 to the 98th percentile.
  - Each range is returned with the layer, so the key matches the image.
- **Coverage classes:** measured, interpolated and missing; or present and missing where there is no count map.
