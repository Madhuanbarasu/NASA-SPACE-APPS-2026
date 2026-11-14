import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, type ReactNode } from "react";
import { api, waitForJob } from "../api/client";
import type { CatalogSite, CommsInputs, CommsResult, Comparison, Coverage, Job, LandingAssessment, ObserverProfile, PanelModel, Result, Rule, Status } from "../api/types";
import { S } from "../i18n";
import { isoNoMs } from "../lib/format";
import { parseSite } from "../lib/moonGeo";

export interface Settings {
  lat: string; lon: string; siteName: string | null; siteId: string | null;
  start: string; end: string; stepMin: number;
  observerProfile: ObserverProfile; observerH: number;
  sunlitRule: Rule; dteRule: Rule; margin: number;
  panel: PanelModel; panelAz: number;
}
export interface CompareSite { lat: number; lon: number; name: string; id?: string | null }
export interface CompareWindow { start: string; end: string; label: string }
export type Tab = "mission" | "site" | "landing" | "comms" | "compare" | "data" | "guide";
/** Phase 5: which view the Site tab shows before an analysis (kept here so it survives tab switches). */
export type SiteViewMode = "map" | "globe" | "terrain";

/** Phase 5 prompt 4: a compact copy of a result the user opened in this session (fields copied from the API result,
 *  nothing derived), so the mission dashboard can list and reopen it without recomputing anything. */
export interface HistoryItem {
  id: string; site: { lat: number; lon: number; name: string | null; ground_h_m: number; level: string };
  window: { start_utc: string; end_utc: string }; rules: { sunlit: string; dte: string };
  summary: Result["summary"]; labels: Record<string, string>; incomplete_share: number; near_field_share: number | null;
  sigma: boolean;
}
export type Mode = "technical" | "public";

/** LUNA-OPS 2.0 Phase 5: the latest landing screening of a site in this session (fields copied from the API's
 *  /api/landing response, nothing derived), so the mission dashboard can show its separate findings. */
export interface LandingSummary {
  key: string; lat: number; lon: number; id: string; product: string; pixel_m: number;
  findings: { key: string; status: string; status_text: string }[]; candidates: number; radius_m: number;
}
export const landingKey = (lat: number, lon: number) => `${lat.toFixed(6)},${lon.toFixed(6)}`;
const LANDING_MAX = 20;

/** LUNA-OPS 2.0 Phase 6: the latest communication simulation of a site in this session (fields copied from the API's
 *  /api/comms response, nothing derived), so the mission dashboard can show its availability facts. */
export interface CommsSummary {
  key: string; lat: number; lon: number; resultId: string;
  directWindows: number; directOpenH: number; nextDirectOpenUtc: string | null; directState: boolean | null;
  relayName: string | null; relayWindows: number | null; relayOpenH: number | null;
  directRf: "evaluated" | "not_evaluated"; window: { start_utc: string; end_utc: string };
}
const COMMS_MAX = 20;
export const EMPTY_COMMS_INPUTS: CommsInputs = { direct: {}, up: {}, down: {}, relay: {}, relayOn: false, dtn: {} };

export interface State {
  status: Status | null; statusError: string | null;
  catalog: CatalogSite[]; catalogReason: string | null;
  settings: Settings;
  result: Result | null; job: Job | null; error: string | null;
  cursor: number; playing: boolean;
  mode: Mode; tab: Tab;
  compareSites: CompareSite[]; compareWindows: CompareWindow[];
  comparison: Comparison | null; compareJob: Job | null; compareError: string | null; compareMetric: string;
  /** Phase 5: terrain coverage of the current site coordinates (one lookup shared by the sidebar, explorer and globe);
   *  `coverageFor` is the "lat,lon" text it was fetched for, so a stale answer is never shown for new coordinates. */
  coverage: Coverage | null; coverageError: string | null; coverageFor: string | null;
  siteView: SiteViewMode;
  /** results opened in this session, newest first (at most HISTORY_MAX) */
  history: HistoryItem[];
  /** Phase 5 final: a result the user left for the explorer, kept (with its time cursor) so it can be returned to */
  parked: { result: Result; cursor: number } | null;
  /** Phase 5: the landing assessment on screen (kept across tab switches), the latest screening per site, and a site
   *  whose screening was requested from the mission dashboard (run when the Landing tab opens) */
  landing: LandingAssessment | null;
  landingSummaries: LandingSummary[];
  landingRequest: string | null;
  /** Phase 6: the communication simulation on screen, its inputs (kept across tab switches), the latest simulation per
   *  site, and a site whose simulation was requested from the mission dashboard */
  comms: CommsResult | null;
  commsInputs: CommsInputs;
  commsSummaries: CommsSummary[];
  commsRequest: string | null;
}

const HISTORY_MAX = 20;
/** Phase 5 final: the session list is kept in this browser tab's sessionStorage (cleared when the tab closes). It is
 *  restored only for the same backend build and validation report, so restored figures and labels can never be stale. */
const SESSION_KEY = "luna-ops.session-results.v1";
interface StoredSession { code: string; report: string | null; items: HistoryItem[] }
const buildKey = (st: Status | null) => (st ? { code: st.code_fingerprint ?? st.code_version, report: st.validation?.run_utc ?? null } : null);
function readSession(): StoredSession | null {
  try {
    const raw = window.sessionStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const v = JSON.parse(raw);
    if (!v || typeof v.code !== "string" || !Array.isArray(v.items)) return null;
    const items = v.items.filter((h: any) => h && typeof h.id === "string" && h.site && h.window && h.rules && h.summary && h.labels);
    return { code: v.code, report: v.report ?? null, items: items.slice(0, HISTORY_MAX) };
  } catch { return null; }
}
function writeSession(s: StoredSession | null) {
  try { if (s) window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(s)); else window.sessionStorage.removeItem(SESSION_KEY); }
  catch { /* storage unavailable or full: the list simply is not kept */ }
}

export function historyItem(r: Result): HistoryItem {
  return { id: r.id, site: { lat: r.site.lat, lon: r.site.lon, name: r.site.name, ground_h_m: r.site.ground_h_m, level: r.site.terrain_level_at_site },
    window: { start_utc: r.window.start_utc, end_utc: r.window.end_utc },
    rules: { sunlit: r.provenance?.parameters?.rules?.sunlit, dte: r.provenance?.parameters?.rules?.dte },
    summary: r.summary, labels: Object.fromEntries(Object.entries(r.labels).map(([k, v]) => [k, v.validation])),
    incomplete_share: r.horizon.incomplete_share, near_field_share: r.horizon.near_field_share ?? null, sigma: !!r.horizon.sigma_deg };
}

type Action =
  | { type: "status"; status: Status | null; error: string | null }
  | { type: "catalog"; sites: CatalogSite[]; reason: string | null }
  | { type: "settings"; patch: Partial<Settings> }
  | { type: "result"; result: Result | null }
  | { type: "job"; job: Job | null }
  | { type: "error"; error: string | null }
  | { type: "cursor"; cursor: number }
  | { type: "playing"; playing: boolean }
  | { type: "mode"; mode: Mode }
  | { type: "tab"; tab: Tab }
  | { type: "compareSites"; sites: CompareSite[] }
  | { type: "compareWindows"; windows: CompareWindow[] }
  | { type: "comparison"; comparison: Comparison | null }
  | { type: "compareJob"; job: Job | null }
  | { type: "compareError"; error: string | null }
  | { type: "compareMetric"; metric: string }
  | { type: "coverage"; coverage: Coverage | null; error: string | null; key: string | null }
  | { type: "siteView"; view: SiteViewMode }
  | { type: "closeResult" } | { type: "restoreResult" }
  | { type: "historyRestore"; items: HistoryItem[] }
  | { type: "landing"; landing: LandingAssessment | null }
  | { type: "landingRequest"; key: string | null }
  | { type: "comms"; comms: CommsResult | null }
  | { type: "commsInputs"; inputs: CommsInputs }
  | { type: "commsRequest"; key: string | null };

function defaultWindow(): { start: string; end: string } {
  const now = new Date();
  const start = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  const end = new Date(start.getTime() + 30 * 86400_000);
  return { start: isoNoMs(start), end: isoNoMs(end) };
}

const w = defaultWindow();
const initial: State = {
  status: null, statusError: null, catalog: [], catalogReason: null,
  settings: { lat: "", lon: "", siteName: null, siteId: null, start: w.start, end: w.end, stepMin: 30,
              observerProfile: "surface", observerH: 0, sunlitRule: "any", dteRule: "centre", margin: 0,
              panel: "vertical_tracking", panelAz: 0 },
  result: null, job: null, error: null, cursor: 0, playing: false, mode: "technical", tab: "site",
  compareSites: [], compareWindows: [], comparison: null, compareJob: null, compareError: null,
  compareMetric: "sunlit", coverage: null, coverageError: null, coverageFor: null, siteView: "map", history: [], parked: null,
  landing: null, landingSummaries: [], landingRequest: null,
  comms: null, commsInputs: EMPTY_COMMS_INPUTS, commsSummaries: [], commsRequest: null,
};

function commsSummary(c: CommsResult): CommsSummary {
  const lat = c.site.lat, lon = c.site.lon;
  const nd = c.next.earth_visible;
  return { key: landingKey(lat, lon), lat, lon, resultId: c.result_id,
    directWindows: c.direct.stats.windows, directOpenH: c.direct.stats.open_h,
    nextDirectOpenUtc: nd ? nd.next_open_utc : null, directState: nd ? nd.state : null,
    relayName: c.relay ? (c.relay_name ?? null) : null, relayWindows: c.comparison.relay_geometric ? c.comparison.relay_geometric.windows : null,
    relayOpenH: c.comparison.relay_geometric ? c.comparison.relay_geometric.open_h : null,
    directRf: c.timeline.direct_rf ? "evaluated" : "not_evaluated",
    window: { start_utc: c.window.start_utc, end_utc: c.window.end_utc } };
}

function landingSummary(a: LandingAssessment): LandingSummary | null {
  const fp = a.footprint;
  if (!fp) return null;
  const lat = a.config.lat, lon = a.config.lon;
  return { key: landingKey(lat, lon), lat, lon, id: a.id, product: a.provenance.dem.key, pixel_m: a.provenance.dem.pixel_m,
    findings: fp.findings.map((x) => ({ key: x.key, status: x.status, status_text: x.status_text })),
    candidates: a.candidates.length, radius_m: fp.radius_m };
}

function reducer(s: State, a: Action): State {
  switch (a.type) {
    case "status": return { ...s, status: a.status, statusError: a.error };
    case "catalog": return { ...s, catalog: a.sites, catalogReason: a.reason };
    case "settings": return { ...s, settings: { ...s.settings, ...a.patch } };
    case "result": return { ...s, result: a.result, cursor: 0, playing: false, parked: a.result ? null : s.parked,
      history: a.result ? [historyItem(a.result), ...s.history.filter((h) => h.id !== a.result!.id)].slice(0, HISTORY_MAX) : s.history };
    case "job": return { ...s, job: a.job };
    case "error": return { ...s, error: a.error };
    case "cursor": return { ...s, cursor: a.cursor };
    case "playing": return { ...s, playing: a.playing };
    case "mode": return { ...s, mode: a.mode };
    case "tab": return { ...s, tab: a.tab };
    case "compareSites": return { ...s, compareSites: a.sites };
    case "compareWindows": return { ...s, compareWindows: a.windows };
    case "comparison": return { ...s, comparison: a.comparison };
    case "compareJob": return { ...s, compareJob: a.job };
    case "compareError": return { ...s, compareError: a.error };
    case "compareMetric": return { ...s, compareMetric: a.metric };
    case "coverage": return { ...s, coverage: a.coverage, coverageError: a.error, coverageFor: a.key };
    case "siteView": return { ...s, siteView: a.view };
    case "closeResult": return s.result ? { ...s, parked: { result: s.result, cursor: s.cursor }, result: null, playing: false } : s;
    case "restoreResult": return s.parked ? { ...s, result: s.parked.result, cursor: s.parked.cursor, parked: null, playing: false } : s;
    case "landing": {
      const sum = a.landing ? landingSummary(a.landing) : null;
      return { ...s, landing: a.landing, landingSummaries: sum
        ? [sum, ...s.landingSummaries.filter((x) => x.key !== sum.key)].slice(0, LANDING_MAX) : s.landingSummaries };
    }
    case "landingRequest": return { ...s, landingRequest: a.key };
    case "comms": {
      const sum = a.comms ? commsSummary(a.comms) : null;
      return { ...s, comms: a.comms, commsSummaries: sum
        ? [sum, ...s.commsSummaries.filter((x) => x.key !== sum.key)].slice(0, COMMS_MAX) : s.commsSummaries };
    }
    case "commsInputs": return { ...s, commsInputs: a.inputs };
    case "commsRequest": return { ...s, commsRequest: a.key };
    case "historyRestore": {
      const ids = new Set(s.history.map((h) => h.id));
      return { ...s, history: [...s.history, ...a.items.filter((h) => !ids.has(h.id))].slice(0, HISTORY_MAX) };
    }
  }
}

interface Ctx {
  state: State;
  dispatch: React.Dispatch<Action>;
  runAnalysis: () => Promise<void>;
  runComparison: () => Promise<void>;
  /** opens a stored result; false (with state.error set) when it cannot be loaded */
  openResult: (id: string) => Promise<boolean>;
}
const StoreCtx = createContext<Ctx | null>(null);

export function requestBody(s: Settings) {
  return {
    lat: Number(s.lat), lon: Number(s.lon), start_utc: s.start, end_utc: s.end, step_s: s.stepMin * 60,
    observer_profile: s.observerProfile, observer_h_m: s.observerH, sunlit_rule: s.sunlitRule, dte_rule: s.dteRule,
    margin_deg: s.margin, panel_model: s.panel, panel_az_deg: s.panelAz, site_name: s.siteName, site_id: s.siteId,
  };
}

export function StoreProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initial);
  const stateRef = useRef(state);
  stateRef.current = state;

  useEffect(() => {
    api.status().then((st) => dispatch({ type: "status", status: st, error: null }))
      .catch((e) => dispatch({ type: "status", status: null, error: String(e.message || e) }));
    api.catalog().then((c) => dispatch({ type: "catalog", sites: c.sites, reason: c.empty_reason }))
      .catch(() => dispatch({ type: "catalog", sites: [], reason: S.errors.catalogue }));
  }, []);

  // Terrain coverage of the site coordinates, looked up once (debounced) for every view that shows it. Same request,
  // timing and error handling as the sidebar's former local lookup.
  const { lat: sLat, lon: sLon } = state.settings;
  useEffect(() => {
    const key = `${sLat},${sLon}`;
    dispatch({ type: "coverage", coverage: null, error: null, key: null });
    const la = Number(sLat), lo = Number(sLon);
    // AUD-01 (pre-Phase 7 audit): only coordinates the backend accepts are looked up (lib/moonGeo parseSite: a number,
    // latitude -90 to 90, longitude -360 to 360). Anything else is marked invalid in the sidebar and never sent, so an
    // out-of-range value no longer produces a 422 response and a console error. The request itself is unchanged.
    if (parseSite(sLat, sLon) === null) return;
    let live = true;
    const t = setTimeout(() => {
      api.coverage(la, lo).then((c) => { if (live) dispatch({ type: "coverage", coverage: c, error: null, key }); })
        .catch((e) => { if (live) dispatch({ type: "coverage", coverage: null, error: String(e.message || e), key }); });
    }, 350);
    return () => { live = false; clearTimeout(t); };
  }, [sLat, sLon]);

  // session list: restore once the backend build is known (same build and report only), then keep it saved
  const restored = useRef(false);
  useEffect(() => {
    if (restored.current || !state.status) return;
    restored.current = true;
    const saved = readSession(), key = buildKey(state.status);
    if (saved && key && saved.code === key.code && saved.report === key.report) dispatch({ type: "historyRestore", items: saved.items });
    else if (saved) writeSession(null);
  }, [state.status]);
  useEffect(() => {
    const key = buildKey(state.status);
    if (!restored.current || !key) return;
    writeSession(state.history.length ? { ...key, items: state.history } : null);
  }, [state.history, state.status]);

  const openResult = useCallback(async (id: string) => {
    let res: Result;
    try { res = await api.result(id); }
    catch (e: any) { dispatch({ type: "error", error: S.errors.openResult(String(e?.message || e)) }); return false; }
    dispatch({ type: "error", error: null });
    dispatch({ type: "result", result: res });
    dispatch({ type: "tab", tab: "site" });
    return true;
  }, []);

  const runAnalysis = useCallback(async () => {
    const s = stateRef.current.settings;
    dispatch({ type: "error", error: null });
    try {
      const r = await api.analysis(requestBody(s));
      let rid = r.result_id;
      if (!rid && r.job_id) {
        const j = await waitForJob(r.job_id, (job) => dispatch({ type: "job", job }));
        if (j.status === "error") throw new Error(j.error || S.errors.analysisStopped);
        rid = j.result_id;
      }
      if (rid) await openResult(rid);
    } catch (e: any) {
      dispatch({ type: "error", error: String(e.message || e) });
    } finally {
      dispatch({ type: "job", job: null });
    }
  }, [openResult]);

  const runComparison = useCallback(async () => {
    const st = stateRef.current;
    const s = st.settings;
    dispatch({ type: "compareError", error: null });
    try {
      const body = {
        sites: st.compareSites.map((x) => ({ lat: x.lat, lon: x.lon, name: x.name, id: x.id ?? null })),
        windows: st.compareWindows.map((x) => ({ start_utc: x.start, end_utc: x.end, label: x.label })),
        step_s: Math.max(s.stepMin * 60, 1800), observer_profile: s.observerProfile, observer_h_m: s.observerH,
        sunlit_rule: s.sunlitRule, dte_rule: s.dteRule, margin_deg: s.margin, panel_model: s.panel,
        panel_az_deg: s.panelAz,
      };
      const { job_id } = await api.compare(body);
      const j = await waitForJob(job_id, (job) => dispatch({ type: "compareJob", job }));
      if (j.status === "error" || !j.result_id) throw new Error(j.error || S.errors.comparisonStopped);
      dispatch({ type: "comparison", comparison: await api.comparison(j.result_id) });
    } catch (e: any) {
      dispatch({ type: "compareError", error: String(e.message || e) });
    } finally {
      dispatch({ type: "compareJob", job: null });
    }
  }, []);

  const value = useMemo(() => ({ state, dispatch, runAnalysis, runComparison, openResult }),
    [state, runAnalysis, runComparison, openResult]);
  return <StoreCtx.Provider value={value}>{children}</StoreCtx.Provider>;
}

export function useStore(): Ctx {
  const c = useContext(StoreCtx);
  if (!c) throw new Error("useStore outside provider");
  return c;
}
