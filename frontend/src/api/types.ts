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

// ---------------------------------------------------------------- LUNA-OPS 2.0 Phase 6: communication simulation
// Mirrors /api/comms (backend/lunaops_comms, preliminary simulation outside the validated engine). Direct-to-Earth values
// and their validation labels come unchanged from an engine analysis result; null means not evaluated or unavailable.
export interface CommsSegment { start_et: number; end_et: number; start_utc: string; end_utc: string; duration_h: number;
  state: boolean | null; uncertain: boolean; flags?: Record<string, unknown> }
export interface CommsStats { open_h: number; open_share: number; windows: number; uncertain_windows: number; longest_window_h: number;
  gaps_between_windows: number; mean_gap_h: number | null; longest_gap_h: number | null; unknown_h: number; starts_open: boolean; ends_open: boolean }
export interface CommsBudgetRow { key: string; label: string; unit: string; formula: string; evaluated: boolean; value: number | null;
  missing?: string[]; invalid?: string[]; blocked_by_earlier?: boolean }
export interface CommsBreakdown { distance_km: number; rows: CommsBudgetRow[]; cn_db: number | null; problems: Record<string, string>;
  notes: string[]; complete: boolean; basis: string; reference: string | null }
export interface CommsLink { complete: boolean; problems: Record<string, string>; basis: string; reference: string | null; notes: string[];
  at_min_distance?: CommsBreakdown; at_max_distance?: CommsBreakdown; margin_db?: { min: number; max: number } }
export interface CommsNext { state: boolean | null; until_utc: string; seconds_to_change: number | null; next_state: boolean | null; next_open_utc: string | null }
export type CommsRow = "earth_visible" | "terrain_blocked" | "direct_rf" | "relay_leg1" | "relay_leg2" | "relay_geometric" | "relay_rf"
  | "any_geometric" | "any_rf" | "no_geometric_path";
export interface CommsResult {
  comms_version: string; comms_status: string; result_id: string; relay_name?: string | null;
  site: { lat: number; lon: number; name: string | null; ground_h_m: number; terrain_level_at_site: string };
  window: { start_utc: string; end_utc: string; start_et: number; end_et: number }; series_step_s: number; reference_utc: string;
  engine_labels: Record<string, string | null>; engine_label_reasons: Record<string, string[]>; geometric_not_radio: string | null;
  direct: { rule: string; stats: CommsStats; terrain_blocked_stats: CommsStats; horizon_incomplete_share: number | null;
    series: { utc: string[]; el: (number | null)[]; az: (number | null)[]; dist_km: (number | null)[]; light_time_s: (number | null)[];
      clearance_deg: (number | null)[]; f: (number | null)[] }; link: CommsLink };
  relay: null | {
    label: string; elements: Record<string, number | string>; orbit: { period_h: number; periapsis_alt_km: number; apoapsis_alt_km: number; mean_motion_deg_per_h: number };
    step_s: number; samples: number; grazing_alt_km: number;
    leg1: { range_km: { min: number | null; max: number | null; mean: number | null }; el_deg: { min: number | null; max: number | null; mean: number | null };
      unknown_share: number; uncertain_share: number; stats: CommsStats; link: CommsLink };
    leg2: { range_km: { min: number | null; max: number | null; mean: number | null }; stats: CommsStats; link: CommsLink };
    both: CommsStats; rf: CommsStats | null;
    series: { utc: string[]; el_deg: (number | null)[]; clearance_deg: (number | null)[]; range_km: (number | null)[];
      earth_limb_clearance_deg: (number | null)[]; earth_range_km: (number | null)[]; alt_km: (number | null)[]; decimated: boolean };
  };
  timeline: Record<CommsRow, CommsSegment[] | null>;
  next: Partial<Record<CommsRow, CommsNext | null>>;
  comparison: Record<string, CommsStats | number | null> & { direct_geometric: CommsStats; direct_rf: CommsStats | null;
    relay_geometric: CommsStats | null; relay_rf: CommsStats | null; any_geometric: CommsStats; any_rf: CommsStats | null;
    relay_adds_geometric_h?: number; relay_adds_rf_h?: number };
  dtn: null | { path: string; evaluated: boolean; reason?: string; volume_mbit?: number; rate_kbps?: number; transmit_time_h?: number;
    start_utc?: string; contacts_used?: number; complete?: boolean; completion_utc?: string | null; elapsed_h?: number | null;
    sent_mbit?: number; remaining_mbit?: number; queued_h?: number | null; note?: string;
    plan?: { start_utc: string; end_utc: string; sent_mbit: number; uncertain: boolean }[] };
  provenance: { comms_version: string; comms_code_sha256: string; status: string; status_note: string;
    engine: Record<string, unknown> & { result_id: string; algorithm_version: string; code_fingerprint: string; labels: Record<string, string | null> };
    engine_code_fingerprint_now: string; kernels: { name: string; role: string; sha256: string }[]; frame: string;
    terrain: { horizon_levels: string[]; incomplete_share: number | null };
    gm: { gm_km3_s2: number; name: string; file: string; sha256: string; source_url: string; citation: string };
    constants: Record<string, string | number>; methods: Record<string, string>; limitations: string[] };
}
/** Form text exactly as typed (units of the form, converted when sent). Empty means not given. */
export type CommsLinkForm = Partial<Record<"power" | "powerUnit" | "gt" | "ltx" | "gr" | "lrx" | "lother" | "ts" | "freqMHz" | "bwkHz"
  | "rbkbps" | "ebn0" | "basis" | "reference", string>>;
export type CommsRelayForm = Partial<Record<"name" | "a" | "e" | "i" | "raan" | "argp" | "m0" | "epoch" | "frame" | "step" | "graze", string>>;
export type CommsDtnForm = Partial<Record<"volume" | "rate" | "path" | "start", string>>;
export interface CommsInputs { direct: CommsLinkForm; up: CommsLinkForm; down: CommsLinkForm; relay: CommsRelayForm; relayOn: boolean; dtn: CommsDtnForm }
