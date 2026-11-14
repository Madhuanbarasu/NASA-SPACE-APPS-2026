import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import type { LandingFinding, LandingFootprint, LandingLayer, LandingStats } from "../api/types";
import { S } from "../i18n";
import { fmtLatLon, fmtNum, fmtPct } from "../lib/format";
import { useMediaQuery } from "../lib/useMediaQuery";
import { landingKey, useStore } from "../state/store";
import { useSiteCoverage } from "./SiteExplorer";
import { LazyBoundary } from "./LazyBoundary";
import type { MapLayers, RasterLayer } from "./LandingMap";
import { Metric } from "../ui/Metric";
import { StatusBadge } from "../ui/StatusBadge";
import { ViewHeader } from "../ui/ViewHeader";

// LUNA-OPS 2.0 Phase 5: Landing Safety workspace. Preliminary DEM-based hazard screening served by the separate
// lunaops_landing backend package (outside the validated engine). Every number shown is an /api/landing field with its
// unit, source and basis; thresholds are the user's own assumptions (no defaults); findings are shown one by one with
// the API's status words. Nothing here combines findings, scores, ranks or certifies a site.

const LandingMap = lazy(() => import("./LandingMap").then((m) => ({ default: m.LandingMap })));
const L = S.landing;
const WINDOWS_M = [500, 1000, 1500, 2500, 3000, 6000];
const ROUGH_PX = [3, 5, 9, 15, 25];
// UI change 2026-11-14 (owner request): the "NASA slope product" raster is no longer offered on the hazard map. It
// exists only inside the Site01 5 m product set and is unavailable (a permanently disabled option) everywhere else.
// The product, the backend layer and the NASA slope statistics in the tables below are unchanged.
const RASTERS: RasterLayer[] = ["elevation", "slope", "roughness", "coverage", "uncertainty", "slope_exceed"];
const DEFAULT_RASTER: RasterLayer = "slope";
const NONE = "none";
const TWO_COLUMNS = "(min-width: 1101px)";   // landing.css: one column at max-width 1100px
const AUTO = "auto";
const DEBOUNCE_MS = 450;
const JSON_TYPE = "application/json";
const FILE_PREFIX = "luna-ops-landing-";
const num = (v: string): number | null => (v.trim() === "" || !isFinite(Number(v)) ? null : Number(v));

function Legend({ layer, raster, threshold, hasCount }: { layer: LandingLayer | undefined; raster: RasterLayer | null; threshold: number | null; hasCount: boolean }) {
  const LG = L.legend;
  if (!raster) return null;
  if (raster === "coverage") {
    return (
      <ul className="landing-legend" aria-label={LG.label}>
        {hasCount ? (
          <>
            <li><span className="lg-swatch is-measured" aria-hidden />{LG.measured}</li>
            <li><span className="lg-swatch is-interpolated" aria-hidden />{LG.interpolated}</li>
          </>
        ) : <li><span className="lg-swatch is-present" aria-hidden />{LG.present}</li>}
        <li><span className="lg-swatch is-missing" aria-hidden />{LG.missing}</li>
      </ul>
    );
  }
  if (raster === "slope_exceed") {
    return (
      <ul className="landing-legend" aria-label={LG.label}>
        <li><span className="lg-swatch is-exceed" aria-hidden />{threshold == null ? LG.needsThreshold : LG.exceeds(threshold)}</li>
      </ul>
    );
  }
  const lg = layer?.legend;
  if (!lg || !lg.ramp || !lg.range) return <p className="hint">{LG.noValues}</p>;
  return (
    <div className="landing-legend" aria-label={LG.label}>
      <span className="lg-ramp" aria-hidden style={{ background: `linear-gradient(90deg, ${lg.ramp.join(", ")})` }} />
      <span className="lg-range mono">
        <span>{fmtNum(lg.range[0], 2)}</span>
        <span>{LG.unit(L.units[layer!.unit as keyof typeof L.units] ?? layer!.unit)}</span>
        <span>{lg.clipped_above ? LG.orMore(fmtNum(lg.range[1], 0)) : fmtNum(lg.range[1], 2)}</span>
      </span>
      <span className="hint">{L.basis[layer!.name as keyof typeof L.basis] ?? layer!.basis}</span>
    </div>
  );
}

function StatsRow({ label, st, unit, basis, d = 2 }: { label: string; st: LandingStats | null | undefined; unit: string; basis: string; d?: number }) {
  const v = (x: number | null | undefined) => fmtNum(x, d);
  return (
    <tr>
      <th scope="row">{label}</th>
      {st && st.n > 0 ? (
        <><td className="num">{v(st.min)}</td><td className="num">{v(st.median)}</td><td className="num">{v(st.mean)}</td>
          <td className="num">{v(st.p95)}</td><td className="num">{v(st.max)}</td></>
      ) : <td colSpan={5} className="unavail">{L.unavailable}</td>}
      <td>{unit}</td><td className="basis">{basis}</td>
    </tr>
  );
}

function Finding({ f }: { f: LandingFinding }) {
  const F = L.findings;
  const st = f.stats;
  return (
    <li className={`landing-finding is-${f.status}`}>
      <div className="finding-head">
        <strong>{F.names[f.key]}</strong>
        <span className={`finding-status is-${f.status}`}>{f.status_text}</span>
      </div>
      {f.key === "relief" && st && <p className="mono">{F.relief(fmtNum(st.value, 2))}</p>}
      {(f.key === "slope" || f.key === "roughness") && st && st.n != null && st.n > 0 && (
        <p className="mono">{F.range(fmtNum(st.min, 2), fmtNum(st.median, 2), fmtNum(st.max, 2), L.units[f.unit as keyof typeof L.units] ?? f.unit ?? "")}</p>
      )}
      {f.threshold != null && <p className="hint">{F.threshold(fmtNum(f.threshold, 2), L.units[f.unit as keyof typeof L.units] ?? f.unit ?? "", f.above_threshold_pct != null ? fmtPct(f.above_threshold_pct, 1) : S.common.na)}</p>}
      {f.baseline_m != null && <p className="hint">{F.baseline(fmtNum(f.baseline_m, 1))}</p>}
      {f.candidates && f.candidates.length > 0 && <p className="hint">{F.candidates(f.candidates.join(", "))}</p>}
      {f.reason && <p className="hint">{f.reason}</p>}
      {f.basis && <p className="hint basis">{F.basis(f.basis)}</p>}
    </li>
  );
}

export function LandingView() {
  const { state, dispatch } = useStore();
  const { site, coverage, error: covError, checking, covered } = useSiteCoverage();
  const a = state.landing;
  // the inputs start from the screening held in the store (so returning to this tab shows the settings of the results
  // on screen), otherwise from neutral defaults; no threshold has a default value
  const text = (v: number | null | undefined) => (v == null ? "" : String(v));
  const [half, setHalf] = useState(a ? a.config.window_half_m : 1500);
  const [product, setProduct] = useState(AUTO);   // the API records the product it resolved, not whether "auto" was chosen
  const [roughPx, setRoughPx] = useState(a ? a.config.roughness_window_px : 5);
  const [minDepth, setMinDepth] = useState(a ? String(a.config.min_depth_m) : "1");
  const [minDiam, setMinDiam] = useState(text(a?.config.min_diameter_m));
  const [maxDiam, setMaxDiam] = useState(text(a?.config.max_diameter_m));
  const [radius, setRadius] = useState(a?.footprint ? String(a.footprint.radius_m) : "50");
  const [fpPos, setFpPos] = useState<{ lat: number; lon: number } | null>(a?.footprint ? { lat: a.footprint.center.lat, lon: a.footprint.center.lon } : null);
  const [th, setTh] = useState(() => {
    const t = a?.footprint?.thresholds;
    return { slope: text(t?.slope_deg), rough: text(t?.roughness_m), relief: text(t?.relief_m), minValid: t ? String(t.min_valid_pct) : "95" };
  });
  const [busy, setBusy] = useState(false);
  const [fpBusy, setFpBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [layers, setLayers] = useState<MapLayers>({ raster: DEFAULT_RASTER, depressions: true, footprint: true, window: true, opacity: 0.85 });
  // a raster that is no longer offered (for example the removed NASA slope option) falls back to the default
  useEffect(() => {
    if (layers.raster && !RASTERS.includes(layers.raster)) setLayers((v) => ({ ...v, raster: DEFAULT_RASTER }));
  }, [layers.raster]);
  const [selected, setSelected] = useState<number | null>(null);
  const fp: LandingFootprint | undefined = a?.footprint;
  const wide = useMediaQuery(TWO_COLUMNS);

  const thresholds = useMemo(() => ({ slope_deg: num(th.slope), roughness_m: num(th.rough), relief_m: num(th.relief),
    min_valid_pct: num(th.minValid) ?? 95 }), [th]);
  const radiusM = Math.min(5000, Math.max(1, num(radius) ?? 50));

  const run = useCallback(async (centre?: { lat: number; lon: number }) => {
    const c = centre ?? site;
    if (!c) return;
    setBusy(true); setError(null);
    try {
      const pos = centre ?? fpPos ?? c;
      const res = await api.landingAssess({
        lat: c.lat, lon: c.lon, window_half_m: half, product: product === AUTO ? null : product, roughness_window_px: roughPx,
        min_depth_m: num(minDepth) ?? 1, min_diameter_m: num(minDiam), max_diameter_m: num(maxDiam),
        footprint: { lat: pos.lat, lon: pos.lon, radius_m: radiusM, thresholds },
      });
      setFpPos({ lat: res.footprint!.center.lat, lon: res.footprint!.center.lon });
      setSelected(null);
      dispatch({ type: "landing", landing: res });
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  }, [site, fpPos, half, product, roughPx, minDepth, minDiam, maxDiam, radiusM, thresholds, dispatch]);

  // a screening requested from the mission dashboard runs once the selected site's coverage is known
  const reqKey = site ? landingKey(site.lat, site.lon) : null;
  useEffect(() => {
    if (!state.landingRequest || state.landingRequest !== reqKey || checking || busy) return;
    dispatch({ type: "landingRequest", key: null });
    if (covered) { setFpPos(null); void run(site!); }
  }, [state.landingRequest, reqKey, checking, covered, busy, run, site, dispatch]);

  // footprint changes (position, radius, thresholds) are re-evaluated on the assessment already held by the server
  const aRef = useRef(a);
  aRef.current = a;

  // The server holds only its latest few screenings (backend/lunaops_landing/assess.py CACHE_MAX), so the one on screen
  // can be dropped when other screenings run (another site, the mission dashboard, another browser tab). Its layer
  // images and footprint requests then fail with 404 and the overlay used to vanish without explanation. The screening
  // is re-run with the configuration the server reported for it (same site, window, resolved product, roughness window
  // and depression limits). The assessment id is a hash of exactly these inputs, the product checksum and the landing
  // code, so the server recomputes the same result from the same data; nothing is computed or substituted here.
  const [rev, setRev] = useState(0);
  const restores = useRef(new Map<string, number>());
  const restoring = useRef(false);
  const restore = useCallback(async () => {
    const cur = aRef.current;
    if (!cur || restoring.current) return;
    const n = restores.current.get(cur.id) ?? 0;
    if (n >= 2) { setError(L.restoreFailed); return; }   // at most two re-runs per screening, never a loop
    restores.current.set(cur.id, n + 1);
    restoring.current = true;
    try {
      const c = cur.config;
      const res = await api.landingAssess({
        lat: c.lat, lon: c.lon, window_half_m: c.window_half_m, product: c.product, roughness_window_px: c.roughness_window_px,
        min_depth_m: c.min_depth_m, min_diameter_m: c.min_diameter_m ?? null, max_diameter_m: c.max_diameter_m ?? null,
        footprint: { lat: fpPos?.lat ?? c.lat, lon: fpPos?.lon ?? c.lon, radius_m: radiusM, thresholds },
      });
      if (aRef.current?.id !== cur.id) return;          // another screening replaced it in the meantime
      setError(null);
      dispatch({ type: "landing", landing: res });
      setRev((r) => r + 1);
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      restoring.current = false;
    }
  }, [fpPos, radiusM, thresholds, dispatch]);
  const restoreRef = useRef(restore);
  restoreRef.current = restore;

  // a terrain product chosen for an earlier site is not carried to a site it does not cover (the request would fail)
  useEffect(() => {
    if (product !== AUTO && coverage?.products && !coverage.products.includes(product)) setProduct(AUTO);
  }, [product, coverage]);
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    const cur = aRef.current;
    if (!cur || !fpPos) return;
    let live = true;
    const t = window.setTimeout(() => {
      setFpBusy(true);
      api.landingFootprint(cur.id, { lat: fpPos.lat, lon: fpPos.lon, radius_m: radiusM, thresholds })
        .then((res) => { if (live) dispatch({ type: "landing", landing: { ...cur, footprint: res } }); })
        .catch((e) => { if (!live) return; if (e?.status === 404) void restoreRef.current(); else setError(String(e?.message || e)); })
        .finally(() => { if (live) setFpBusy(false); });
    }, DEBOUNCE_MS);
    return () => { live = false; window.clearTimeout(t); };
  }, [fpPos, radiusM, thresholds, dispatch]);

  const stale = !!a && !!site && landingKey(a.config.lat, a.config.lon) !== landingKey(site.lat, site.lon);
  const exportJson = () => {
    if (!a) return;
    const blob = new Blob([JSON.stringify(a, null, 1)], { type: JSON_TYPE });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url; link.download = `${FILE_PREFIX}${a.id}.json`;
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  const recentre = () => {
    if (!fpPos) return;
    dispatch({ type: "settings", patch: { lat: fpPos.lat.toFixed(6), lon: fpPos.lon.toFixed(6), siteName: null, siteId: null } });
    void run(fpPos);
  };
  const covText = !site ? L.noSite : covError ? S.explorer.error(covError) : checking || !coverage ? S.explorer.checking
    : coverage.covered ? S.explorer.covered(coverage.levels.join(", ")) : S.explorer.notCovered(coverage.reason ?? S.common.unknown);
  const layerOf = (n: string) => a?.layers.find((x) => x.name === n);
  const rasterAvailable = (r: RasterLayer) => r === "slope_exceed" || r === "coverage" || !!layerOf(r)?.available;
  // a value layer with no values in the analysed window (no colour range from the server) is said so on the map itself
  const shownLayer = layers.raster && layers.raster !== "coverage" && layers.raster !== "slope_exceed" ? layerOf(layers.raster) : undefined;
  const mapNotice = shownLayer && (!shownLayer.available || !shownLayer.legend?.range)
    ? L.layerNoData(L.layers[layers.raster as keyof typeof L.layers]) : null;
  // A footprint finer than the DEM pixels cannot be resolved (the server reports "Requires higher-resolution data").
  // Name the finer registered products that cover this site, from the coverage check; the pixel size is the level
  // prefix of the product key ("20m:..."). Nothing is resampled here.
  const pixelOf = (k: string) => { const m = /^(\d+(?:\.\d+)?)m:/.exec(k); return m ? Number(m[1]) : null; };
  const coarseFp = !!fp && fp.findings.some((f) => f.key !== "obstacles" && f.status === "higher_res");
  const finer = a && coarseFp && !stale ? (coverage?.products ?? []).filter((k) => { const p = pixelOf(k); return p != null && p < a.provenance.dem.pixel_m; }) : [];
  const sm = a?.summary;
  const prov = a?.provenance;
  const histMax = sm ? Math.max(1, ...sm.slope_hist.counts) : 1;
  const histTotal = sm ? sm.slope_hist.counts.reduce((p, q) => p + q, 0) : 0;

  // The four main cards. Wide screens (two columns) stack them in two independent columns, so a short card never
  // inherits the height of a taller card beside it (the cause of the blank space that used to sit below Selected
  // landing site and Terrain analysis); narrower screens keep the single-column order.
  // A. selected landing site and analysis configuration
  const siteCard = (
    <section className="landing-card" aria-labelledby="landing-site">
      <h2 id="landing-site">{L.siteHeading}</h2>
      {site && <p className="mono landing-coords">{fmtLatLon(site.lat, site.lon, 5)}</p>}
      <p className={`hint ${coverage?.covered ? "good" : covError || (coverage && !coverage.covered) ? "bad" : ""}`} aria-live="polite">{covText}</p>
      {coverage?.products && coverage.products.length > 0 && (
        <p className="hint">{L.products(coverage.products.join(", "))}</p>
      )}
      {a && prov && (
        <dl className="metrics landing-metrics">
          <Metric label={L.resolution} value={L.metres(fmtNum(prov.dem.pixel_m, 0))} note={prov.dem.level} />
          <Metric label={L.windowSize} value={L.windowValue(fmtNum(2 * a.config.window_half_m_used / 1000, 1), prov.window.pixels[0], prov.window.pixels[1])} />
          <Metric label={L.validCover} value={fmtPct(sm!.valid_share != null ? 100 * sm!.valid_share : null, 1)} />
          <Metric label={L.measuredCover} value={sm!.measured_share != null ? fmtPct(100 * sm!.measured_share, 1) : L.unavailable}
                  note={sm!.measured_share == null ? L.noCountMap : L.countMapNote} state={sm!.measured_share == null ? "unknown" : undefined} />
        </dl>
      )}
      <h3 className="landing-subhead">{L.configHeading}</h3>
      <div className="field-row">
        <div className="field">
          <label htmlFor="ls-window">{L.window}</label>
          <select id="ls-window" value={half} onChange={(e) => setHalf(Number(e.target.value))}>
            {WINDOWS_M.map((w) => <option key={w} value={w}>{L.windowOption(fmtNum(2 * w / 1000, 1))}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="ls-product">{L.product}</label>
          <select id="ls-product" value={product} onChange={(e) => setProduct(e.target.value)}>
            <option value={AUTO}>{L.productAuto}</option>
            {(coverage?.products ?? []).map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
      </div>
      <div className="field-row">
        <div className="field">
          <label htmlFor="ls-rough">{L.roughWindow}</label>
          <select id="ls-rough" value={roughPx} onChange={(e) => setRoughPx(Number(e.target.value))}>
            {ROUGH_PX.map((p) => <option key={p} value={p}>{a ? L.roughOptionM(p, fmtNum(p * a.provenance.dem.pixel_m, 0)) : L.roughOption(p)}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="ls-depth">{L.minDepth}</label>
          <input id="ls-depth" type="text" inputMode="decimal" value={minDepth} onChange={(e) => setMinDepth(e.target.value)} />
        </div>
      </div>
      <div className="field-row">
        <div className="field">
          <label htmlFor="ls-dmin">{L.minDiameter}</label>
          <input id="ls-dmin" type="text" inputMode="decimal" placeholder={L.optional} value={minDiam} onChange={(e) => setMinDiam(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="ls-dmax">{L.maxDiameter}</label>
          <input id="ls-dmax" type="text" inputMode="decimal" placeholder={L.optional} value={maxDiam} onChange={(e) => setMaxDiam(e.target.value)} />
        </div>
      </div>
      <p className="hint">{L.configNote}</p>
    </section>
  );
  // D. hazard map
  const mapCard = (
    <section className={a ? "landing-card landing-mapcard has-map" : "landing-card landing-mapcard"} aria-labelledby="landing-map">
      <h2 id="landing-map">{L.mapHeading}</h2>
      {!a ? <p className="hint">{L.mapEmpty}</p> : (
        <>
          <fieldset className="landing-layers">
            <legend>{L.layersLegend}</legend>
            <div className="layer-options" role="radiogroup" aria-label={L.rasterLabel}>
              {[NONE, ...RASTERS].map((r) => {
                const ok = r === NONE || rasterAvailable(r as RasterLayer);
                return (
                  <label key={r} className={ok ? undefined : "is-off"}>
                    <input type="radio" name="ls-raster" value={r} disabled={!ok} checked={(layers.raster ?? NONE) === r}
                           onChange={() => setLayers((v) => ({ ...v, raster: r === NONE ? null : (r as RasterLayer) }))} />
                    {L.layers[r as keyof typeof L.layers]}
                  </label>
                );
              })}
            </div>
            <div className="layer-options">
              <label><input type="checkbox" checked={layers.depressions} onChange={(e) => setLayers((v) => ({ ...v, depressions: e.target.checked }))} />{L.layers.depressions}</label>
              <label><input type="checkbox" checked={layers.footprint} onChange={(e) => setLayers((v) => ({ ...v, footprint: e.target.checked }))} />{L.layers.footprint}</label>
              <label><input type="checkbox" checked={layers.window} onChange={(e) => setLayers((v) => ({ ...v, window: e.target.checked }))} />{L.layers.window}</label>
              <label className="opacity">{L.opacity}
                <input type="range" min={0.2} max={1} step={0.05} value={layers.opacity} aria-valuetext={fmtPct(layers.opacity * 100, 0)}
                       onChange={(e) => setLayers((v) => ({ ...v, opacity: Number(e.target.value) }))} />
              </label>
            </div>
            <p className="hint">{L.obstacleLayer}</p>
          </fieldset>
          <LazyBoundary fallback={<div className="pane-empty">{L.mapFailed}</div>}>
            <Suspense fallback={<div className="pane-empty">{L.mapLoading}</div>}>
              <LandingMap key={a.id} assessment={a} layers={layers} slopeThreshold={thresholds.slope_deg}
                          footprint={{ lat: fpPos?.lat ?? a.config.lat, lon: fpPos?.lon ?? a.config.lon, radius_m: radiusM }}
                          onMoveFootprint={(la, lo) => setFpPos({ lat: la, lon: lo })} selected={selected} onSelect={setSelected}
                          rev={rev} onLayerError={() => void restore()} notice={mapNotice} />
            </Suspense>
          </LazyBoundary>
          <Legend layer={layers.raster ? layerOf(layers.raster) : undefined} raster={layers.raster} threshold={thresholds.slope_deg}
                  hasCount={a.summary.measured_share != null} />
          <ul className="landing-legend">
            <li><span className="lg-ring is-defined" aria-hidden />{L.legend.defined}</li>
            <li><span className="lg-ring is-weak" aria-hidden />{L.legend.weak}</li>
            <li><span className="lg-ring is-within" aria-hidden />{L.legend.within}</li>
            <li><span className="lg-ring is-footprint" aria-hidden />{L.legend.footprint}</li>
            <li><span className="lg-ring is-window" aria-hidden />{L.legend.window}</li>
          </ul>
          <p className="hint">{L.mapNote}</p>
        </>
      )}
    </section>
  );
  // C. landing footprint
  const footprintCard = a && fp ? (
    <section className="landing-card" aria-labelledby="landing-footprint">
      <h2 id="landing-footprint">{L.footprintHeading}</h2>
      <div className="field-row">
        <div className="field">
          <label htmlFor="ls-fplat">{L.fpLat}</label>
          <input id="ls-fplat" type="text" inputMode="decimal" value={fpPos ? fpPos.lat.toFixed(6) : ""}
                 onChange={(e) => { const v = num(e.target.value); if (v != null && fpPos) setFpPos({ ...fpPos, lat: v }); }} />
        </div>
        <div className="field">
          <label htmlFor="ls-fplon">{L.fpLon}</label>
          <input id="ls-fplon" type="text" inputMode="decimal" value={fpPos ? fpPos.lon.toFixed(6) : ""}
                 onChange={(e) => { const v = num(e.target.value); if (v != null && fpPos) setFpPos({ ...fpPos, lon: v }); }} />
        </div>
      </div>
      <div className="field">
        <label htmlFor="ls-radius">{L.radius}</label>
        <input id="ls-radius" type="text" inputMode="decimal" value={radius} onChange={(e) => setRadius(e.target.value)} aria-describedby="ls-radius-hint" />
        <span id="ls-radius-hint" className="hint">{L.radiusHint(fmtNum(fp.pixels_across, 1), fmtNum(fp.pixel_m_ground, 2))}</span>
      </div>
      <fieldset className="landing-thresholds">
        <legend>{L.thresholdsLegend}</legend>
        <div className="field-row">
          <div className="field"><label htmlFor="ls-tslope">{L.tSlope}</label>
            <input id="ls-tslope" type="text" inputMode="decimal" placeholder={L.notSet} value={th.slope} onChange={(e) => setTh({ ...th, slope: e.target.value })} /></div>
          <div className="field"><label htmlFor="ls-trough">{L.tRough}</label>
            <input id="ls-trough" type="text" inputMode="decimal" placeholder={L.notSet} value={th.rough} onChange={(e) => setTh({ ...th, rough: e.target.value })} /></div>
        </div>
        <div className="field-row">
          <div className="field"><label htmlFor="ls-trelief">{L.tRelief}</label>
            <input id="ls-trelief" type="text" inputMode="decimal" placeholder={L.notSet} value={th.relief} onChange={(e) => setTh({ ...th, relief: e.target.value })} /></div>
          <div className="field"><label htmlFor="ls-tvalid">{L.tValid}</label>
            <input id="ls-tvalid" type="text" inputMode="decimal" value={th.minValid} onChange={(e) => setTh({ ...th, minValid: e.target.value })} /></div>
        </div>
        <p className="hint">{L.thresholdNote}</p>
      </fieldset>
      {!fp.inside_window && <button type="button" className="quiet-button" disabled={busy} onClick={recentre}>{L.recentre}</button>}
      {fp.coverage && (
        <dl className="metrics landing-metrics">
          <Metric label={L.fpPixels} value={String(fp.coverage.pixels)} />
          <Metric label={L.validCover} value={fmtPct(fp.coverage.valid_pct, 1)} />
          <Metric label={L.measuredCover} value={fp.coverage.measured_pct != null ? fmtPct(fp.coverage.measured_pct, 1) : L.unavailable}
                  note={fp.coverage.measured_basis} state={fp.coverage.measured_pct == null ? "unknown" : undefined} />
          <Metric label={L.heightSigma} value={fp.coverage.height_sigma_m ? L.metresRange(fmtNum(fp.coverage.height_sigma_m.mean, 2), fmtNum(fp.coverage.height_sigma_m.max, 2)) : L.unavailable}
                  state={fp.coverage.height_sigma_m ? undefined : "unknown"} />
          <Metric label={L.slopeSigma} value={fp.coverage.slope_sigma_deg ? L.degRange(fmtNum(fp.coverage.slope_sigma_deg.mean, 2), fmtNum(fp.coverage.slope_sigma_deg.max, 2)) : L.unavailable}
                  state={fp.coverage.slope_sigma_deg ? undefined : "unknown"} />
          <Metric label={L.nasaSlope} value={fp.coverage.nasa_slope_deg ? L.degRange(fmtNum(fp.coverage.nasa_slope_deg.median, 2), fmtNum(fp.coverage.nasa_slope_deg.max, 2)) : L.unavailable}
                  note={fp.coverage.nasa_slope_deg ? L.nasaSlopeNote : undefined} state={fp.coverage.nasa_slope_deg ? undefined : "unknown"} />
        </dl>
      )}
      <h3 className="landing-subhead">{L.findingsHeading}{fpBusy && <span className="hint"> {L.updating}</span>}</h3>
      {coarseFp && (
        <p className="hint warn landing-footprint-hint">
          {finer.length > 0 ? L.fpCoarseFiner(a.provenance.dem.key, fmtNum(a.provenance.dem.pixel_m, 0), finer.join(", "))
            : L.fpCoarseNone(a.provenance.dem.key, fmtNum(a.provenance.dem.pixel_m, 0))}
        </p>
      )}
      <ul className="landing-findings" aria-live="polite">{fp.findings.map((f) => <Finding key={f.key} f={f} />)}</ul>
      <p className="hint">{L.findingsNote}</p>
    </section>
  ) : null;
  // B. terrain analysis of the window
  const terrainCard = a && fp ? (
    <section className="landing-card" aria-labelledby="landing-terrain">
      <h2 id="landing-terrain">{L.terrainHeading}</h2>
      <p className="hint">{L.terrainIntro(L.windowValue(fmtNum(2 * a.config.window_half_m_used / 1000, 1), prov!.window.pixels[0], prov!.window.pixels[1]), prov!.dem.key)}</p>
      <div className="table-scroll"><table className="data landing-stats">
        <thead><tr><th>{L.cols.quantity}</th><th className="num">{L.cols.min}</th><th className="num">{L.cols.median}</th><th className="num">{L.cols.mean}</th>
          <th className="num">{L.cols.p95}</th><th className="num">{L.cols.max}</th><th>{L.cols.unit}</th><th>{L.cols.basis}</th></tr></thead>
        <tbody>
          <StatsRow label={L.rows.slope} st={sm!.slope_deg} unit={L.units.deg} basis={L.basis.slope} />
          <StatsRow label={L.rows.roughness(a.config.roughness_window_px)} st={sm!.roughness_m} unit={L.units.m} basis={L.basis.roughness} d={3} />
          <StatsRow label={L.rows.tri} st={sm!.tri_m} unit={L.units.m} basis={L.basis.tri} d={3} />
          <StatsRow label={L.rows.elevation} st={sm!.elevation_m} unit={L.units.m} basis={sm!.basis} />
          <StatsRow label={L.rows.heightSigma} st={sm!.height_sigma_m} unit={L.units.m} basis={L.basis.uncertainty} d={3} />
          <StatsRow label={L.rows.nasaSlope} st={sm!.nasa_slope_deg} unit={L.units.deg} basis={L.basis.nasa_slope} />
          <StatsRow label={L.rows.slopeSigma} st={sm!.slope_sigma_deg} unit={L.units.deg} basis={L.basis.slope_error} />
        </tbody>
      </table></div>
      <h3 className="landing-subhead">{L.histHeading}</h3>
      <ul className="landing-hist" aria-label={L.histLabel}>
        {sm!.slope_hist.counts.map((n, i) => (
          <li key={i}>
            <span className="hist-k mono">{L.histBin(sm!.slope_hist.edges_deg[i], sm!.slope_hist.edges_deg[i + 1])}</span>
            <span className="hist-bar" aria-hidden><span style={{ width: `${(100 * n) / histMax}%` }} /></span>
            <span className="hist-v mono">{fmtPct(histTotal ? (100 * n) / histTotal : null, 1)}</span>
          </li>
        ))}
      </ul>
      <p className="hint">{L.histNote}</p>
      <h3 className="landing-subhead">{L.multiHeading}</h3>
      <div className="table-scroll"><table className="data landing-stats">
        <thead><tr><th>{L.cols.window}</th><th className="num">{L.cols.median}</th><th className="num">{L.cols.mean}</th><th className="num">{L.cols.p95}</th><th className="num">{L.cols.max}</th></tr></thead>
        <tbody>{sm!.roughness_multiscale.map((m) => (
          <tr key={m.window_px}><th scope="row">{L.roughOptionM(m.window_px, fmtNum(m.baseline_m, 0))}</th>
            <td className="num">{fmtNum(m.median, 3)}</td><td className="num">{fmtNum(m.mean, 3)}</td><td className="num">{fmtNum(m.p95, 3)}</td><td className="num">{fmtNum(m.max, 3)}</td></tr>
        ))}</tbody>
      </table></div>
      <p className="hint">{L.roughNote}</p>
    </section>
  ) : null;

  return (
    <div className="landing">
      <ViewHeader eyebrow={L.eyebrow} title={L.title}
                  subtitle={site ? fmtLatLon(site.lat, site.lon) : L.noSite}
                  actions={<button type="button" className="run-button landing-run" disabled={!site || !covered || busy} onClick={() => { setFpPos(null); void run(site!); }}>
                    {busy ? L.running : a && !stale ? L.rerun : L.run}</button>} />
      <div className="landing-disclaimer" role="note">
        <StatusBadge word={prov?.validation_status ?? L.preliminary} />
        <p>{L.disclaimer}</p>
      </div>
      {error && <p className="hint bad landing-pad" role="alert">{L.failed(error)}</p>}
      {stale && <p className="hint warn landing-pad" role="status">{L.stale(fmtLatLon(a!.config.lat, a!.config.lon))}</p>}

      {wide ? (
        <div className="landing-grid landing-band">
          <div className="landing-col">{siteCard}{footprintCard}</div>
          <div className="landing-col landing-col-map">{mapCard}{terrainCard}</div>
        </div>
      ) : (
        <>
          <div className="landing-grid">{siteCard}{mapCard}</div>
          {footprintCard && <div className="landing-grid">{footprintCard}{terrainCard}</div>}
        </>
      )}

      {a && (
        <section className="landing-card landing-wide" aria-labelledby="landing-candidates">
          <h2 id="landing-candidates">{L.candHeading(a.candidates.length)}</h2>
          <p className="hint">{L.candIntro(fmtNum(a.config.min_depth_m, 2))}</p>
          {a.summary.depressions.truncated && <p className="hint warn">{L.candTruncated}</p>}
          {a.candidates.length === 0 ? <p className="hint">{L.candNone}</p> : (
            <div className="table-scroll landing-cand-scroll"><table className="data landing-cands">
              <thead><tr><th>{L.cc.id}</th><th>{L.cc.centre}</th><th className="num">{L.cc.diameter}</th><th className="num">{L.cc.depth}</th>
                <th className="num">{L.cc.ratio}</th><th className="num">{L.cc.shape}</th><th className="num">{L.cc.measured}</th><th>{L.cc.quality}</th><th>{L.cc.status}</th></tr></thead>
              <tbody>{a.candidates.map((c) => (
                <tr key={c.id} className={c.id === selected ? "is-selected" : undefined}>
                  <td><button type="button" className="link-button" aria-pressed={c.id === selected} aria-label={L.cc.show(c.id)}
                              onClick={() => setSelected(c.id === selected ? null : c.id)}>{c.id}</button></td>
                  <td className="mono">{fmtLatLon(c.lat, c.lon, 4)}</td>
                  <td className="num">{fmtNum(c.diameter_m, 0)}</td><td className="num">{fmtNum(c.depth_m, 2)}</td>
                  <td className="num">{c.depth_to_sigma != null ? fmtNum(c.depth_to_sigma, 1) : S.common.na}</td>
                  <td className="num">{L.cc.shapeValue(fmtNum(c.axis_ratio, 2), fmtNum(c.fill_ratio, 2))}</td>
                  <td className="num">{c.measured_share != null ? fmtPct(100 * c.measured_share, 0) : S.common.na}</td>
                  <td>{L.quality[c.quality]}</td><td>{L.cc.unconfirmed}</td>
                </tr>
              ))}</tbody>
            </table></div>
          )}
          <p className="hint">{L.candNote}</p>
        </section>
      )}

      {a && prov && (
        <section className="landing-card landing-wide" aria-labelledby="landing-provenance">
          <h2 id="landing-provenance">{L.provHeading}</h2>
          <dl className="landing-prov">
            <dt>{L.prov.status}</dt><dd>{prov.validation_status}. {prov.validation_note}</dd>
            <dt>{L.prov.dataset}</dt><dd>{prov.dem.product}{prov.dem.synthetic ? L.prov.synthetic : ""}</dd>
            <dt>{L.prov.productId}</dt><dd className="mono">{prov.dem.product_id} ({prov.dem.key})</dd>
            <dt>{L.prov.file}</dt><dd className="mono">{prov.dem.file} {L.prov.sha(prov.dem.sha256.slice(0, 16))}</dd>
            <dt>{L.prov.resolution}</dt><dd>{L.metres(fmtNum(prov.dem.pixel_m, 0))}</dd>
            <dt>{L.prov.frame}</dt><dd>{prov.dem.frame}; {prov.dem.crs}</dd>
            <dt>{L.prov.vertical}</dt><dd>{prov.dem.vertical}</dd>
            <dt>{L.prov.citation}</dt><dd>{prov.dem.citation ?? S.common.na}{prov.dem.page ? ` (${prov.dem.page})` : ""}</dd>
            <dt>{L.prov.errorMap}</dt><dd>{prov.error_map ? `${prov.error_map.product} ${L.prov.sha(prov.error_map.sha256.slice(0, 16))}` : L.unavailable}</dd>
            <dt>{L.prov.auxiliary}</dt><dd>{Object.keys(prov.auxiliary).length === 0 ? L.prov.noAux : (
              <ul>{Object.entries(prov.auxiliary).map(([k, v]) => <li key={k}>{v.product} {L.prov.sha(v.sha256.slice(0, 16))}{v.source_url ? ` (${v.source_url})` : ""}</li>)}</ul>)}</dd>
            <dt>{L.prov.window}</dt><dd className="mono">{L.prov.bounds(prov.window.bounds_xy_m.map((v) => fmtNum(v, 0)).join(", "))}</dd>
            <dt>{L.prov.algorithms}</dt><dd><ul>{Object.entries(prov.algorithms).map(([k, v]) => (
              <li key={k}><strong>{L.prov.algo[k as keyof typeof L.prov.algo] ?? k}</strong>{": "}{typeof v === "string" ? v : Object.entries(v).map(([q, t]) => `${q}: ${t}`).join("; ")}</li>))}</ul></dd>
            <dt>{L.prov.version}</dt><dd className="mono">{L.prov.versionValue(prov.landing_version, prov.landing_code_sha256.slice(0, 16), prov.engine_code_fingerprint.slice(0, 16))}</dd>
            <dt>{L.prov.config}</dt><dd className="mono">{JSON.stringify(a.config)}</dd>
            {prov.notes.length > 0 && <><dt>{L.prov.notes}</dt><dd><ul>{prov.notes.map((n, i) => <li key={i}>{n}</li>)}</ul></dd></>}
            <dt>{L.prov.limitations}</dt><dd><ul>{prov.limitations.map((n, i) => <li key={i}>{n}</li>)}</ul></dd>
          </dl>
          <button type="button" className="quiet-button" onClick={exportJson}>{L.export}</button>
        </section>
      )}
    </div>
  );
}
