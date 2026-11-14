// Types mirror the LUNA-OPS result object served by the API. The browser never
// computes a scientific quantity (blueprint C09); it only reads these fields.

export type Rule = "any" | "centre" | "full";
export type PanelModel = "vertical_tracking" | "horizontal" | "fixed_vertical";
export type ObserverProfile = "surface" | "astronaut" | "equipment";

export interface Label { kind: string; validation: string; tests: Record<string, string>; reasons?: string[] }

export interface Interval {
  start_utc: string; end_utc: string; start_et: number; end_et: number;
  state: boolean | null; duration_h: number; brief: boolean; uncertain: boolean | null;
  // Phase 2 (display planned for Phase 5): why the interval is uncertain, and whether it depends on near-field terrain
  uncertain_reasons?: ("below_k_sigma" | "sigma_nonlinear" | "cross_product_discrepancy_unknown")[];
  near_field?: boolean;
  // Phase 3 item 7: a window a peak between horizon nodes (as high as measured) could hide; null = unknown
  subbin_peak?: boolean | null;
}

export interface Summary {
  hours: number; percent: number; windows: number; longest_window_h: number; longest_gap_h: number;
  unknown_hours: number; brief_windows: number; uncertain_windows: number; transitions: number;
  uncertain_gaps?: number; near_field_windows?: number;
}

export interface PowerMetrics {
  mean: number | null; equivalent_full_sun_h: number | null; coverage: number;
  // Phase 3: time-weighted coverage, unknown time never interpolated; equivalent_full_sun_h is a lower bound when lower_bound
  known_hours?: number; unknown_hours?: number; lower_bound?: boolean; policy?: string;
}

export interface BodySeries {
  az: (number | null)[]; el: (number | null)[]; rho: (number | null)[]; f: (number | null)[];
  c: (number | null)[]; dist_km: (number | null)[]; unit: number[][]; light_time_s?: (number | null)[];
  f_ld?: (number | null)[];   // Sun only: limb-darkened visible flux fraction (algorithm 1.4.0)
}

export interface EventItem { utc: string; et: number; name: string; function: string; direction: number; target: string }

export interface Horizon {
  nbins: number; bin_deg: number; h_deg: number[]; incomplete: boolean[]; incomplete_share: number;
  max_deg: number; min_deg: number; sigma_deg: (number | null)[] | null; ground_h_m: number; site_level: string;
  levels: { level: string; pixel_m: number; product: string | null; synthetic: boolean }[];
  near_field?: boolean[] | null; near_field_share?: number | null; blocker_product?: number[] | null;
  cross_product?: boolean[] | null; discrepancy_unknown?: boolean[] | null; sigma_nonlinear?: boolean[] | null;
}

export interface Result {
  id: string; sha256: string;
  site: { lat: number; lon: number; name: string | null; id: string | null; ground_h_m: number;
          terrain_level_at_site: string; coverage: { levels: string[] } };
  window: { start_utc: string; end_utc: string; start_et: number; end_et: number };
  horizon: Horizon;
  events: EventItem[];
  intervals: Record<string, Interval[]>;
  summary: Record<string, any>;
  series: { utc: string[]; et: number[]; sun: BodySeries; earth: BodySeries; earth_occults_sun: (number | null)[];
            power: Record<PanelModel, { series: (number | null)[]; metrics: PowerMetrics;
                                        // limb-darkened companion (algorithm 1.4.0, D01); series/metrics unchanged
                                        series_ld?: (number | null)[]; metrics_ld?: PowerMetrics }>;
            step_s: number; note: string };
  labels: Record<string, Label>;
  warnings: string[];
  provenance: any;
  geometric_not_radio: string;
}

export interface CatalogSite {
  id: string; name: string; kind: string; lat: number; lon: number; point_label: string;
  extent_label?: string; polygon_latlon?: [number, number][]; source: Record<string, string>;
}

export interface Status {
  version: string; code_version: string; algorithm_version: string; code_fingerprint?: string;
  validation_blockers?: string[];
  kernels: { loaded: boolean; profile?: string; frame?: string; coverage_utc?: [string, string];
             files?: any[]; warnings?: string[]; error?: string };
  terrain: { levels: Record<string, any>; error_maps: string[]; synthetic_in_use: boolean; synthetic_allowed: boolean };
  validation: any; labels: Record<string, Label> | null; panels: Record<PanelModel, string>;
}

export interface Job { id: string; status: "queued" | "running" | "done" | "error"; progress: number; message: string;
                       result_id: string | null; error: string | null }

export interface CompareCell { site: { lat: number; lon: number; name?: string; id?: string };
  window: { start_utc: string; end_utc: string; label?: string }; result_id: string | null;
  summary: Record<string, any> | null; error: string | null; labels?: Record<string, Label> }
export interface Comparison { id: string; sites: any[]; windows: any[]; base: any; cells: CompareCell[] }

export interface TerrainGrid { level: string; product: string; n: number; radius_m: number; heights: (number | null)[];
  grid_basis_bodyfixed: { x: number[]; y: number[]; up: number[] }; note: string }

/** GET /api/coverage: which registered terrain products have data at a point (backend dem.coverage_check). */
export interface Coverage { lat: number; lon: number; covered: boolean; levels: string[]; products?: string[];
  finest?: string; reason: string | null }

// ---------------------------------------------------------------- LUNA-OPS 2.0 Phase 5: landing screening
// Mirrors /api/landing (backend/lunaops_landing, preliminary screening outside the validated engine). Every value is
// the API's own; null means unavailable and is shown as such.
export interface LandingStats { n: number; min: number | null; max: number | null; mean: number | null; median: number | null; p95: number | null }
export type LandingFindingKey = "slope" | "roughness" | "relief" | "depressions" | "obstacles";
export interface LandingFinding {
  key: LandingFindingKey; status: string; status_text: string;
  reason?: string; basis?: string; unit?: string; stats?: Partial<LandingStats> & { value?: number | null };
  threshold?: number | null; above_threshold_pct?: number | null; baseline_m?: number | null; window_px?: number;
  elevation_m?: LandingStats; candidates?: number[];
  detection_limits?: { min_depth_m: number; min_diameter_m: number | null; min_pixels: number; pixel_m: number };
}
export interface LandingThresholds { slope_deg: number | null; roughness_m: number | null; relief_m: number | null; min_valid_pct: number }
export interface LandingFootprint {
  center: { lat: number; lon: number; x: number; y: number }; radius_m: number; pixel_m_ground: number; pixels_across: number;
  inside_window: boolean; thresholds: LandingThresholds; threshold_basis: string; pixels: number;
  coverage: { pixels: number; valid_pct: number | null; measured_pct: number | null; measured_basis: string;
    height_sigma_m: LandingStats | null; slope_sigma_deg: LandingStats | null; nasa_slope_deg: LandingStats | null } | null;
  findings: LandingFinding[];
}
export interface LandingCandidate {
  id: number; lat: number; lon: number; x: number; y: number; diameter_m: number; depth_m: number;
  deepest: { lat: number; lon: number }; pixels: number; axis_ratio: number; fill_ratio: number;
  sigma_m: number | null; depth_to_sigma: number | null; measured_share: number | null;
  quality: "defined" | "weak" | "within_uncertainty" | "shape_only"; status: string; orientation_deg: number; axes_m: [number, number];
}
export interface LandingLayer { name: string; unit: string; basis: string; available: boolean;
  legend: { ramp: string[] | null; range: [number, number] | null; clipped_above: boolean } | null }
export interface LandingAssessment {
  id: string;
  config: { lat: number; lon: number; window_half_m: number; window_half_m_used: number; product: string;
    roughness_window_px: number; min_depth_m: number; min_diameter_m: number | null; max_diameter_m: number | null };
  summary: {
    pixels: number; valid_share: number | null; measured_share: number | null;
    elevation_m: LandingStats; slope_deg: LandingStats; slope_hist: { edges_deg: number[]; counts: number[] };
    roughness_m: LandingStats; tri_m: LandingStats;
    roughness_multiscale: (LandingStats & { window_px: number; baseline_m: number })[];
    height_sigma_m: LandingStats | null; nasa_slope_deg: LandingStats | null; slope_sigma_deg: LandingStats | null;
    depressions: { count: number; by_quality: Record<string, number>; truncated: boolean }; basis: string;
  };
  candidates: LandingCandidate[];
  provenance: {
    landing_version: string; landing_code_sha256: string; validation_status: string; validation_note: string;
    engine_code_fingerprint: string;
    dem: { key: string; product: string; product_id: string; file: string; sha256: string; pixel_m: number; level: string;
      page: string | null; citation: string | null; frame: string; crs: string; vertical: string; synthetic: boolean };
    error_map: { product: string; file: string; sha256: string; units: string } | null;
    auxiliary: Record<string, { product: string; path: string; sha256: string; units: string; source_url: string | null; citation: string | null; frame: string }>;
    window: { bounds_xy_m: number[]; pixels: [number, number]; half_m_requested: number; half_m_used: number };
    algorithms: Record<string, string | Record<string, string>>; notes: string[]; limitations: string[];
  };
  layers: LandingLayer[]; extent_xy_m: [number, number, number, number]; roughness_windows_m: number[];
  footprint?: LandingFootprint;
}
export interface LandingPoint {
  inside: boolean; elevation_m?: number | null; slope_deg?: number | null; roughness_m?: number | null; tri_m?: number | null;
  height_sigma_m?: number | null; nasa_slope_deg?: number | null; slope_sigma_deg?: number | null; lola_returns?: number | null;
  missing?: boolean; depression_id?: number | null; depression_depth_m?: number | null;
}
