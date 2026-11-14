// Renders every view of the LUNA-OPS frontend to static markup under many store states, plus the outputs of the
// formatting library, so the baseline and the C10 build can be compared byte for byte. "@src" is resolved by the
// bundler to either source tree; "../state/store" is replaced by a mock whose state each scenario sets.
import { renderToStaticMarkup } from "react-dom/server";
import { TopBar } from "@src/components/TopBar";
import { Sidebar } from "@src/components/Sidebar";
import { SiteView } from "@src/components/SiteView";
import { CompareView } from "@src/components/CompareView";
import { DataView } from "@src/components/DataView";
import { GuideView } from "@src/components/GuideView";
import { HorizonPanorama } from "@src/components/HorizonPanorama";
import { Timeline } from "@src/components/Timeline";
import * as fmt from "@src/lib/format";
import { nextChange } from "@src/lib/countdown";

declare const globalThis: any;

// ---------------------------------------------------------------- fixtures
const N = 49;
const START_ET = 846979269.18;
const iso = (k: number) => new Date(Date.UTC(2026, 10, 14, 0, 0, 0) + k * 1800_000).toISOString().replace(/\.\d{3}Z$/, "Z");
const ser = (f: (k: number) => number | null) => Array.from({ length: N }, (_, k) => f(k));
const iv = (a: number, b: number, state: boolean | null, extra: any = {}) => ({
  start_utc: iso(a), end_utc: iso(b), start_et: START_ET + a * 1800, end_et: START_ET + b * 1800, state,
  duration_h: (b - a) / 2, brief: false, uncertain: false, ...extra });

function makeResult(opts: { synthetic?: boolean; incomplete?: boolean; name?: string | null; sigma?: boolean } = {}) {
  const nb = 360;
  return {
    id: "r1", sha256: "x",
    site: { lat: -89.463163, lon: 222.510447, name: opts.name === undefined ? "Site01 (Connecting Ridge)" : opts.name, id: "s1",
            ground_h_m: 1234.56, terrain_level_at_site: "5m", coverage: { levels: ["5m", "20m"] } },
    window: { start_utc: iso(0), end_utc: iso(N - 1), start_et: START_ET, end_et: START_ET + (N - 1) * 1800 },
    horizon: { nbins: nb, bin_deg: 1, h_deg: Array.from({ length: nb }, (_, i) => 1.5 * Math.sin(i / 20) + 0.3),
      incomplete: Array.from({ length: nb }, (_, i) => !!opts.incomplete && i > 100 && i < 130),
      incomplete_share: opts.incomplete ? 29 / nb : 0, max_deg: 1.8, min_deg: -1.2,
      sigma_deg: opts.sigma ? Array.from({ length: nb }, (_, i) => (i % 7 === 0 ? null : 0.05)) : null,
      ground_h_m: 1234.56, site_level: "5m", levels: [] },
    events: [
      { utc: iso(3) + "", et: START_ET + 5400, name: "sunrise (any part)", function: "sun_any", direction: 1, target: "sun" },
      { utc: iso(20), et: START_ET + 36000, name: "Earthset (centre)", function: "earth_centre", direction: -1, target: "earth" },
      { utc: iso(30), et: START_ET + 54000, name: "eclipse contact", function: "ecl_contact", direction: 1, target: "sun" },
    ],
    intervals: {
      sun_any: [iv(0, 3, false), iv(3, 30, true, { brief: true }), iv(30, 48, false)],
      sun_full: [iv(0, 48, null)],
      earth_centre: [iv(0, 20, true, { uncertain: true }), iv(20, 48, false)],
      overlap: [iv(0, 3, false), iv(3, 20, true), iv(20, 48, false)],
    },
    summary: {
      sun_any: { hours: 13.5, percent: 56.25, windows: 1, longest_window_h: 13.5, longest_gap_h: 9, unknown_hours: opts.incomplete ? 0.5 : 0, brief_windows: 1, uncertain_windows: 0, transitions: 2 },
      earth_centre: { hours: 10, percent: 41.7, windows: 1, longest_window_h: 10, longest_gap_h: 14, unknown_hours: 0.0, brief_windows: 0, uncertain_windows: 1, transitions: 1 },
      overlap: { hours: 8.5, percent: 35.4, windows: 1, longest_window_h: 8.5, longest_gap_h: 14 },
      power: { vertical_tracking: { mean: 0.4567, equivalent_full_sun_h: 10.96, coverage: 1 } },
      mean_sun_fraction: opts.synthetic ? null : 0.512,
    },
    series: {
      utc: ser(iso as any) as any, et: ser((k) => START_ET + k * 1800) as number[],
      sun: { az: ser((k) => (k * 7.3) % 360), el: ser((k) => (k === 5 ? null : 1.2 * Math.sin(k / 8))), rho: ser(() => 0.267),
             f: ser((k) => (k < 3 ? 0 : k < 30 ? (k === 4 ? 0.04 : k === 10 ? 0.955 : 1) : k === 31 ? null : 0)),
             c: ser((k) => 0.5 - k * 0.02), dist_km: ser(() => 1.48e8), unit: ser(() => [1, 0, 0]) as any },
      earth: { az: ser((k) => (350 + k * 0.1) % 360), el: ser((k) => 2 + Math.cos(k / 9)), rho: ser(() => 0.95),
               f: ser((k) => (k < 20 ? 1 : 0.5)), c: ser(() => 0.3), dist_km: ser(() => 384400),
               unit: ser(() => [0, 1, 0]) as any, light_time_s: ser((k) => (k === 7 ? null : 1.282)) },
      earth_occults_sun: ser(() => 0),
      power: { vertical_tracking: { series: ser((k) => (k === 2 ? null : 0.5)), metrics: { mean: 0.45, equivalent_full_sun_h: 10, coverage: 1 } },
               horizontal: { series: ser(() => 0.01), metrics: { mean: 0.01, equivalent_full_sun_h: 0.2, coverage: 1 } },
               fixed_vertical: { series: ser(() => 0.2), metrics: { mean: 0.2, equivalent_full_sun_h: 4, coverage: 1 } } },
      step_s: 1800, note: "",
    },
    labels: {
      sun_earth_azel: { kind: "Computed", validation: "Validated (V-01..V-04)", tests: { "V-01": "passed", "V-04": "passed" } },
      horizon: { kind: "Computed", validation: "Pending validation", tests: { "V-06": "passed", "U-04": "not run" }, reasons: ["U-04 not run", "U-06 not run"] },
      disk_visibility: { kind: "Computed", validation: "Synthetic test terrain - not a lunar result", tests: {} },
      events: { kind: "Computed", validation: "Pending validation", tests: {} },
      power_indicator: { kind: "Estimated", validation: "Pending validation", tests: {} },
      unknown_quantity: { kind: "Other", validation: "Pending validation", tests: {} },
    },
    warnings: ["Horizon uncertainty uses L_corr = 250 m (uncalibrated)."],
    provenance: { parameters: { panel: { model: "vertical_tracking" }, rules: { sunlit: "any", dte: "centre" } },
                  terrain: { synthetic: !!opts.synthetic } },
    geometric_not_radio: "Earth visibility is geometric line of sight, not a radio link.",
  };
}

const catalog = [
  { id: "s1", name: "Site01 (Connecting Ridge)", kind: "pgda78", lat: -89.463163, lon: 222.510447, point_label: "PGDA 78 site centre",
    extent_label: "16 km x 16 km DEM", source: { product: "PGDA 78" } },
  { id: "s2", name: "Haworth", kind: "usgs", lat: -86.8, lon: 355.2, point_label: "USGS region centroid", source: { product: "USGS ACC grids" },
    polygon_latlon: [[-86.7, 355], [-86.9, 355.4], [-86.8, 355.6]] },
];

const fullStatus = {
  version: "0.1.0", code_version: "0.1.0+c621f98", algorithm_version: "1.5.0", code_fingerprint: "5bf9753fa5c5493eadeb98",
  validation_blockers: ["U-04 not run", "U-06 not run"],
  kernels: { loaded: true, profile: "production", frame: "MOON_ME_DE440_ME421", coverage_utc: ["1550-01-01T00:00:00Z", "2650-01-22T00:00:00Z"],
             files: [{ role: "spk", name: "de440.bsp", sha256: "0123456789abcdef0123", source: "https://naif.jpl.nasa.gov/...", retrieved_utc: "2026-11-08" }],
             warnings: ["Four kernels are trusted on first download."] },
  terrain: { levels: { "5m": { product: "Site01_final_adj_5mpp_surf.tif", pixel_m: 5, bytes: 41000000, sha256: "3ba7b97cb00a2bcf2118", registered_utc: "2026-11-07" },
                       "240m": { product: "SYNTHETIC_CRATER", synthetic: true, pixel_m: 240, sha256: "aa" } },
             error_maps: ["5m:Site01", "20m:LDEM"], synthetic_in_use: false, synthetic_allowed: false },
  validation: { run_utc: "2026-11-10T21:19:33Z", code_version: "0.1.0+c621f98", kernel_profile: "production",
                tests: { "V-01": { status: "passed", detail: "3 case(s)" }, "V-09": { status: "not run", detail: null },
                         "V-99": { status: "failed", detail: "boom" }, "other:x": { status: "skipped" } } },
  labels: { sun_earth_azel: { kind: "Computed", validation: "Pending validation", tests: {} } },
  panels: {},
};

const baseSettings = { lat: "", lon: "", siteName: null, siteId: null, start: "2026-11-14T00:00:00Z", end: "2026-12-14T00:00:00Z",
  stepMin: 30, observerProfile: "surface", observerH: 0, sunlitRule: "any", dteRule: "centre", margin: 0, panel: "vertical_tracking", panelAz: 0 };
const baseState = { status: null, statusError: null, catalog: [], catalogReason: null, settings: baseSettings, result: null, job: null,
  error: null, cursor: 0, playing: false, mode: "technical", tab: "site", compareSites: [], compareWindows: [], comparison: null,
  compareJob: null, compareError: null, compareMetric: "sunlit" };

const comparison = {
  id: "c1", base: { sunlit_rule: "any", dte_rule: "centre", panel_model: "vertical_tracking" },
  sites: [{ name: "Site01", lat: -89.46, lon: 222.51 }, { name: null, lat: -86.8, lon: 355.2 }],
  windows: [{ start_utc: iso(0), end_utc: iso(10) }, { start_utc: iso(10), end_utc: iso(20) }],
  cells: [
    { site: {}, window: {}, result_id: "a", summary: makeResult().summary, error: null },
    { site: {}, window: {}, result_id: "b", summary: { ...makeResult().summary, sun_any: { ...makeResult().summary.sun_any, percent: 12.3 } }, error: null },
    { site: {}, window: {}, result_id: null, summary: null, error: "No terrain coverage at this site." },
    { site: {}, window: {}, result_id: "d", summary: { ...makeResult().summary, power: {} }, error: null },
  ],
};

// ---------------------------------------------------------------- scenarios
type Sc = [string, any, () => any];
const st = (patch: any) => ({ ...baseState, ...patch, settings: { ...baseSettings, ...(patch.settings ?? {}) } });
const scenarios: Sc[] = [];
const add = (name: string, state: any, el: () => any) => scenarios.push([name, state, el]);

// TopBar
for (const [n, s] of [["connecting", st({})], ["production", st({ status: fullStatus })],
  ["test-kernels-synthetic", st({ status: { ...fullStatus, kernels: { loaded: true, profile: "demo", frame: "F" }, terrain: { ...fullStatus.terrain, synthetic_in_use: true } } })],
  ["no-kernels-no-terrain", st({ status: { ...fullStatus, kernels: { loaded: false, error: "missing" }, terrain: { levels: {}, error_maps: [], synthetic_in_use: false } } })],
  ["one-product", st({ status: { ...fullStatus, terrain: { ...fullStatus.terrain, levels: { "5m": {} } } }, mode: "public", tab: "guide" })]] as [string, any][]) {
  add(`TopBar/${n}`, s, () => <TopBar />);
}
// Sidebar
const sidebarStates: [string, any][] = [
  ["empty", st({})], ["catalog-reason", st({ catalogReason: "No curated sources are registered." })],
  ["catalog", st({ catalog, settings: { siteId: "s1", lat: "-89.463163", lon: "222.510447", siteName: "Site01" } })],
  ["coords-typed", st({ status: fullStatus, settings: { lat: "-89.5", lon: "10" } })],
  ["kernels-error", st({ status: { ...fullStatus, kernels: { loaded: false, error: "No SPICE kernels installed." } } })],
  ["status-error", st({ statusError: "Failed to fetch" })],
  ["job", st({ status: fullStatus, job: { id: "j", status: "running", progress: 0.42, message: "Computing horizon", result_id: null, error: null } })],
  ["error", st({ error: "The analysis stopped." })],
  ["astronaut-fixed-panel", st({ settings: { observerProfile: "astronaut", observerH: 1.8, panel: "fixed_vertical", panelAz: 90, dteRule: "full", sunlitRule: "centre", margin: 0.5 } })],
  ["equipment", st({ settings: { observerProfile: "equipment", observerH: 3, dteRule: "any" } })],
];
for (const [n, s] of sidebarStates) add(`Sidebar/${n}`, s, () => <Sidebar />);
// SiteView without a result (Welcome + map)
for (const [n, s] of [["connecting", st({})], ["ready", st({ status: fullStatus, catalog })],
  ["demo", st({ status: { ...fullStatus, kernels: { loaded: true, profile: "demo", frame: "F" }, terrain: { ...fullStatus.terrain, synthetic_in_use: true }, validation: null }, settings: { lat: "-89", lon: "5" } })],
  ["no-kernels", st({ status: { ...fullStatus, kernels: { loaded: false }, terrain: { levels: {}, error_maps: [], synthetic_in_use: false } } })]] as [string, any][]) {
  add(`SiteView/welcome-${n}`, s, () => <SiteView />);
}
// SiteView with a result
const results: [string, any][] = [
  ["technical", st({ result: makeResult(), catalog, status: fullStatus })],
  ["technical-cursor", st({ result: makeResult({ incomplete: true, sigma: true }), cursor: 31, playing: true })],
  ["public", st({ result: makeResult(), mode: "public", cursor: 4 })],
  ["public-synthetic-custom", st({ result: makeResult({ synthetic: true, name: null, incomplete: true }), mode: "public", cursor: 10 })],
  ["cursor-end", st({ result: makeResult(), cursor: 999 })],
];
for (const [n, s] of results) add(`SiteView/${n}`, s, () => <SiteView />);
for (const c of [0, 5, 20, 31, 48]) {
  add(`HorizonPanorama/cursor-${c}`, st({}), () => <HorizonPanorama result={makeResult({ incomplete: true, sigma: true }) as any} cursor={c} />);
  add(`Timeline/cursor-${c}`, st({}), () => <Timeline result={makeResult() as any} cursor={c} onCursor={() => {}} />);
}
// CompareView
const sites = [{ lat: -89.46, lon: 222.51, name: "Site01", id: "s1" }, { lat: -86.8, lon: 355.2, name: "-86.800°, 355.200°", id: null }];
const wins = [{ start: iso(0), end: iso(10), label: "Window 1" }, { start: iso(10), end: iso(20), label: "Window 2" }, { start: iso(20), end: iso(30), label: "Window 3" }];
const four = [...sites, { lat: -88, lon: 1, name: "A" }, { lat: -87, lon: 2, name: "B" }];
for (const [n, s] of [["empty", st({})], ["catalog", st({ catalog, compareSites: sites })],
  ["windows", st({ compareSites: sites, compareWindows: wins, settings: { sunlitRule: "full", dteRule: "any" } })],
  ["target", st({ compareSites: four, compareWindows: wins })],
  ["busy-error", st({ compareSites: four, compareWindows: wins, compareJob: { id: "j", status: "running", progress: 0.1, message: "Cell 2 of 12", result_id: null, error: null }, compareError: "The comparison stopped." })],
  ...["sunlit", "dark", "dte", "dtegap", "overlap", "power", "efsh", "bogus"].map((m) => [`matrix-${m}`, st({ compareSites: sites, compareWindows: wins.slice(0, 2), comparison, compareMetric: m })])] as [string, any][]) {
  add(`CompareView/${n}`, s, () => <CompareView />);
}
// DataView
for (const [n, s] of [["loading", st({})], ["api-error", st({ statusError: "Failed to fetch" })], ["full", st({ status: fullStatus })],
  ["no-kernels-terrain-report", st({ status: { ...fullStatus, kernels: { loaded: false, error: "No kernels." }, terrain: { levels: {}, error_maps: [], synthetic_in_use: false }, validation: null, validation_blockers: [], labels: null } })],
  ["kernels-no-coverage", st({ status: { ...fullStatus, kernels: { loaded: true, profile: "demo", frame: "F" } } })]] as [string, any][]) {
  add(`DataView/${n}`, s, () => <DataView />);
}
add("GuideView", st({}), () => <GuideView />);

// ---------------------------------------------------------------- run
const out: Record<string, string> = {};
for (const [name, state, el] of scenarios) {
  globalThis.__MOCK_STORE__ = { state, dispatch() {}, runAnalysis: async () => {}, runComparison: async () => {}, openResult: async () => {} };
  try { out[name] = renderToStaticMarkup(el()); } catch (e: any) { out[name] = "RENDER ERROR: " + (e?.stack || e); }
}
// formatting library over a grid of inputs
const isos = ["2026-11-14T00:00:00Z", "2026-01-05T09:07:03.250Z", "2026-12-31T23:59:59Z", "not a date", "2026-06-01T12:30"];
const hrs = [null, undefined, NaN, Infinity, 0, 0.004, 0.01, 0.5, 1, 1.999, 23.99, 24, 25.5, 100.25, 1000];
const nums = [null, undefined, NaN, -Infinity, -1.23456, 0, 0.0004, 0.5, 1, 12.3456, 99.99, 100, 359.999];
const fr = [null, undefined, NaN, -0.1, 0, 0.0001, 0.001, 0.05, 0.099, 0.1, 0.5, 0.9, 0.901, 0.9995, 0.99999, 1, 1.2];
out["format"] = JSON.stringify({
  fmtUTC: isos.flatMap((s) => [fmt.fmtUTC(s), fmt.fmtUTC(s, true)]),
  fmtShortDate: isos.map((s) => fmt.fmtShortDate(s)),
  fmtDuration: hrs.map((h) => fmt.fmtDuration(h as any)),
  fmtCountdown: [-5, 0, 30, 59, 60, 3600, 90061].map((s) => fmt.fmtCountdown(s)),
  fmtDeg: nums.flatMap((v) => [fmt.fmtDeg(v as any), fmt.fmtDeg(v as any, 1), fmt.fmtDeg(v as any, 0)]),
  fmtPct: nums.flatMap((v) => [fmt.fmtPct(v as any), fmt.fmtPct(v as any, 0)]),
  fmtNum: nums.flatMap((v) => [fmt.fmtNum(v as any), fmt.fmtNum(v as any, 1)]),
  fmtFraction: fr.map((v) => fmt.fmtFraction(v as any)),
  RULE_NAMES: fmt.RULE_NAMES, PANEL_NAMES: fmt.PANEL_NAMES, PANEL_ORDER: Object.keys(fmt.PANEL_NAMES),
  isoNoMs: fmt.isoNoMs(new Date(Date.UTC(2026, 0, 2, 3, 4, 5, 678))),
  inputs: [fmt.toInputValue("2026-11-14T00:00:00Z"), fmt.fromInputValue("2026-11-14T00:00"), fmt.fromInputValue("2026-11-14T00:00:30"), fmt.fromInputValue("2026-11-14T00:00:30Z")],
  nextChange: nextChange(makeResult().intervals.sun_any as any, START_ET + 1800 * 10, "on", "off"),
});
process.stdout.write(JSON.stringify(out));
