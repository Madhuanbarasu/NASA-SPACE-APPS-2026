import { Suspense, lazy, useEffect, useMemo, useState } from "react";
import type { Result } from "../api/types";
import { S, rich } from "../i18n";
import { cursorEt, nextChange } from "../lib/countdown";
import { PANEL_NAMES, RULE_NAMES, fmtCountdown, fmtDeg, fmtDuration, fmtFraction, fmtLatLon, fmtNum, fmtPct, fmtUTC } from "../lib/format";
import { siteCoords, type GlobeLocation } from "../lib/moonGeo";
import { useStore, type SiteViewMode } from "../state/store";
import { HorizonPanorama } from "./HorizonPanorama";
import { LazyBoundary } from "./LazyBoundary";
import { DataKey, SiteContext } from "./ResultContext";
import { VisibilityChart } from "./VisibilityChart";
import { SiteExplorer, useSiteCoverage } from "./SiteExplorer";
import { Timeline } from "./Timeline";
import { Welcome } from "./Welcome";

// U-06: the map (OpenLayers, proj4) and the 3D view (three.js) are about 80 % of the JavaScript; they load on demand
// so the first screen does not wait for them. Each pane shows its loading text meanwhile.
const MapView = lazy(() => import("./MapView").then((m) => ({ default: m.MapView })));
const Terrain3D = lazy(() => import("./Terrain3D").then((m) => ({ default: m.Terrain3D })));
// Phase 5: the 3D Moon globe and the pre-analysis local terrain (three.js) load only when the user opens them
const MoonGlobe = lazy(() => import("./MoonGlobe").then((m) => ({ default: m.MoonGlobe })));
const TerrainPreview = lazy(() => import("./TerrainPreview").then((m) => ({ default: m.TerrainPreview })));
// welcome-pane views (internal tokens, never displayed); the current one lives in the store (state.siteView)
const VIEW = { map: "map", globe: "globe", terrain: "terrain" } as const;

function PaneLoading({ text }: { text: string }) {
  return <div className="pane-body"><div className="pane-empty">{text}</div></div>;
}

const T = S.site;
const QUANTITY_NAMES: Record<string, string> = S.quantities;
// prefixes of the API's validation status words (protocol values, not display text)
const VALIDATED_PREFIX = "Validated";
const SYNTHETIC_PREFIX = "Synthetic";

/** Phase 5 prompt 4: ids of the result-view sections the mission dashboard links to (internal tokens). */
export const RESULT_SECTIONS = { panorama: "result-panorama", timeline: "result-timeline", visibility: "result-visibility",
  terrain: "result-terrain", tables: "result-tables" } as const;

export function LabelChips({ result }: { result: Result }) {
  return (
    <div className="label-row" aria-label={T.labelsLabel}>
      {Object.entries(result.labels).map(([k, v]) => {
        const cls = v.validation.startsWith(VALIDATED_PREFIX) ? "validated" : v.validation.startsWith(SYNTHETIC_PREFIX) ? "synthetic" : "pending";
        return <span key={k} className={`chip ${cls}`} title={[...(v.reasons ?? []).map((r) => T.labelNotValidated(r)), ...Object.entries(v.tests).map(([t, s]) => T.labelTest(t, s))].join("\n")}>
          {T.labelChip(QUANTITY_NAMES[k] ?? k, v.kind, v.validation.toLowerCase())}</span>;
      })}
    </div>
  );
}

function Readout({ r, i, playing }: { r: Result; i: number; playing: boolean }) {
  const s = r.series;
  const pm = r.provenance.parameters.panel.model;
  const R = S.readout;
  return (
    <div className="readout" aria-live={playing ? "off" : "polite"} aria-atomic="true">
      <div><div className="k">{R.sunElevation}</div><div className="v sun">{fmtDeg(s.sun.el[i])}</div>
        <div className="sub">{R.azimuth(fmtDeg(s.sun.az[i], 1))}</div></div>
      <div><div className="k">{R.sunVisible}</div><div className="v sun">{fmtFraction(s.sun.f[i])}</div>
        <div className="sub">{R.clearance(fmtDeg(s.sun.c[i]))}</div></div>
      <div><div className="k">{R.earthElevation}</div><div className="v earth">{fmtDeg(s.earth.el[i])}</div>
        <div className="sub">{R.azimuth(fmtDeg(s.earth.az[i], 1))}</div></div>
      <div><div className="k">{R.earthVisible}</div><div className="v earth">{fmtFraction(s.earth.f[i])}</div>
        <div className="sub">{R.lightTime(fmtNum(s.earth.light_time_s?.[i] ?? null, 3))}</div></div>
      <div><div className="k">{R.power}</div><div className="v">{fmtNum(s.power[pm as keyof typeof s.power].series[i], 3)}</div>
        <div className="sub">{R.relative(PANEL_NAMES[pm].toLowerCase())}</div></div>
    </div>
  );
}

function Countdowns({ r, i }: { r: Result; i: number }) {
  const et = cursorEt(r, i);
  const p = r.provenance.parameters.rules;
  const C = S.countdowns;
  const items = [
    nextChange(r.intervals[`sun_${p.sunlit}`], et, C.nextSunrise, C.nextSunset),
    nextChange(r.intervals["sun_full"], et, C.wholeSunClears, C.terrainCoversSun),
    nextChange(r.intervals[`earth_${p.dte}`], et, C.nextEarthrise, C.nextEarthset),
    nextChange(r.intervals["overlap"], et, C.windowOpens, C.windowCloses),
  ];
  return (
    <div className="countdowns" aria-label={C.label}>
      {items.map((c) => (
        <div className="countdown" key={c.label}>
          <div className="k">{c.label}</div>
          <div className="v">{c.seconds == null ? C.notInWindow : C.inTime(fmtCountdown(c.seconds))}</div>
        </div>
      ))}
    </div>
  );
}

function Figures({ r }: { r: Result }) {
  const p = r.provenance.parameters;
  const sun = r.summary[`sun_${p.rules.sunlit}`];
  const earth = r.summary[`earth_${p.rules.dte}`];
  const ov = r.summary.overlap;
  const pw = r.summary.power[p.panel.model];
  const F = S.figures;
  return (
    <div className="figures">
      <div className="figure">
        <h3>{F.sunlight}</h3><div className="rule">{RULE_NAMES[p.rules.sunlit]}</div>
        <div className="big" style={{ color: "var(--sun)" }}>{fmtPct(sun.percent)}</div>
        <dl><dt>{F.sunlitTime}</dt><dd>{fmtDuration(sun.hours)}</dd>
          <dt>{F.longestDarkness}</dt><dd>{fmtDuration(sun.longest_gap_h)}</dd>
          <dt>{F.sunlitWindows}</dt><dd>{sun.windows}{sun.brief_windows ? F.briefWindows(sun.brief_windows) : ""}</dd>
          {sun.unknown_hours > 0 && <><dt>{F.unknown}</dt><dd>{fmtDuration(sun.unknown_hours)}</dd></>}</dl>
      </div>
      <div className="figure">
        <h3>{F.dte}</h3><div className="rule">{F.dteRule(RULE_NAMES[p.rules.dte])}</div>
        <div className="big" style={{ color: "var(--earth)" }}>{fmtPct(earth.percent)}</div>
        <dl><dt>{F.earthInView}</dt><dd>{fmtDuration(earth.hours)}</dd>
          <dt>{F.longestWindow}</dt><dd>{fmtDuration(earth.longest_window_h)}</dd>
          <dt>{F.longestGap}</dt><dd>{fmtDuration(earth.longest_gap_h)}</dd>
          {earth.unknown_hours > 0 && <><dt>{F.unknown}</dt><dd>{fmtDuration(earth.unknown_hours)}</dd></>}</dl>
      </div>
      <div className="figure">
        <h3>{F.overlap}</h3><div className="rule">{F.overlapRule}</div>
        <div className="big" style={{ color: "var(--both)" }}>{fmtPct(ov.percent)}</div>
        <dl><dt>{F.total}</dt><dd>{fmtDuration(ov.hours)}</dd>
          <dt>{F.longestWindow}</dt><dd>{fmtDuration(ov.longest_window_h)}</dd>
          <dt>{F.longestGap}</dt><dd>{fmtDuration(ov.longest_gap_h)}</dd></dl>
      </div>
      <div className="figure">
        <h3>{F.power}</h3><div className="rule">{F.powerRule(PANEL_NAMES[p.panel.model].toLowerCase())}</div>
        <div className="big">{fmtNum(pw.mean, 3)}</div>
        <dl><dt>{F.equivalentFullSun}</dt><dd>{fmtDuration(pw.equivalent_full_sun_h)}</dd>
          <dt>{F.meanVisibleSun}</dt><dd>{r.summary.mean_sun_fraction == null ? S.common.na : fmtPct(r.summary.mean_sun_fraction * 100)}</dd></dl>
      </div>
    </div>
  );
}

function PublicSummary({ r }: { r: Result }) {
  const p = r.provenance.parameters;
  const sun = r.summary[`sun_${p.rules.sunlit}`];
  const earth = r.summary[`earth_${p.rules.dte}`];
  const ov = r.summary.overlap;
  const days = (r.window.end_et - r.window.start_et) / 86400;
  const P = S.publicSummary;
  return (
    <div className="public-summary">
      <p>{rich(P.sunlight, { days: days.toFixed(0), percent: <strong className="sun">{fmtPct(sun.percent, 0)}</strong>,
        gap: <strong className="sun">{fmtDuration(sun.longest_gap_h)}</strong> })}</p>
      <p>{rich(P.earth, { percent: <strong className="earth">{fmtPct(earth.percent, 0)}</strong> })}</p>
      <p>{P.both(fmtPct(ov.percent, 0))}</p>
    </div>
  );
}

function EventsTable({ r }: { r: Result }) {
  const [open, setOpen] = useState(false);
  const E = S.eventsTable;
  return (
    <div className="section">
      <h2>{E.heading(r.events.length)}{" "}<button className="toggle-table" onClick={() => setOpen(!open)} aria-expanded={open}>{open ? E.hide : E.show}</button></h2>
      {open && (
        <div className="table-scroll">
          <table className="data"><thead><tr><th>{E.time}</th><th>{E.body}</th><th>{E.event}</th></tr></thead>
            <tbody>{r.events.map((e, k) => <tr key={k}><td>{fmtUTC(e.utc, true)}</td><td>{e.target === "sun" ? S.common.bodies.sun : S.common.bodies.earth}</td><td>{e.name}</td></tr>)}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function SeriesTable({ r }: { r: Result }) {
  const [open, setOpen] = useState(false);
  const s = r.series;
  const step = Math.max(1, Math.ceil(s.utc.length / 400));
  const idx = useMemo(() => s.utc.map((_, i) => i).filter((i) => i % step === 0), [s.utc, step]);
  const Q = S.seriesTable;
  return (
    <div className="section">
      <h2>{Q.heading}{" "}<button className="toggle-table" onClick={() => setOpen(!open)} aria-expanded={open}>{open ? Q.hide : Q.show}</button></h2>
      {open && (
        <div className="table-scroll">
          <table className="data">
            <caption className="sr-only">{Q.caption}</caption>
            <thead><tr><th>{Q.time}</th><th className="num">{Q.sunAz}</th><th className="num">{Q.sunEl}</th><th className="num">{Q.sunVisible}</th>
              <th className="num">{Q.earthAz}</th><th className="num">{Q.earthEl}</th><th className="num">{Q.earthVisible}</th></tr></thead>
            <tbody>{idx.map((i) => (
              <tr key={i}><td>{fmtUTC(s.utc[i])}</td><td className="num">{fmtDeg(s.sun.az[i])}</td><td className="num">{fmtDeg(s.sun.el[i])}</td>
                <td className="num">{fmtFraction(s.sun.f[i])}</td>
                <td className="num">{fmtDeg(s.earth.az[i])}</td><td className="num">{fmtDeg(s.earth.el[i])}</td>
                <td className="num">{fmtFraction(s.earth.f[i])}</td></tr>))}</tbody>
          </table>
        </div>
      )}
      {open && step > 1 && <p className="hint">{Q.decimated(step)}</p>}
    </div>
  );
}

export function SiteView() {
  const { state, dispatch } = useStore();
  const r = state.result;
  const s = state.settings;
  const latN = s.lat.trim() === "" ? null : Number(s.lat);
  const lonN = s.lon.trim() === "" ? null : Number(s.lon);

  useEffect(() => {
    if (!state.playing || !r) return;
    const t = setInterval(() => {
      dispatch({ type: "cursor", cursor: state.cursor + 1 >= r.series.et.length ? 0 : state.cursor + 1 });
    }, 140);
    return () => clearInterval(t);
  }, [state.playing, state.cursor, r, dispatch]);

  const pick = (lat: number, lon: number) =>
    dispatch({ type: "settings", patch: { lat: String(lat), lon: String(lon), siteId: null, siteName: null } });
  // Phase 5: South Pole explorer. One site selection for every view: the store's site coordinates (sidebar fields).
  // The globe shows them and writes picks through the same conversion as the map (lib/moonGeo siteCoords).
  const view = state.siteView;
  const setView = (v: SiteViewMode) => dispatch({ type: "siteView", view: v });
  const { site, covered, coverage } = useSiteCoverage();
  const onGlobePick = (loc: GlobeLocation) => { const c = siteCoords(loc.lat, loc.lon); pick(c.lat, c.lon); };

  if (!r) {
    const heading = view === VIEW.globe ? S.globe.heading
      : view === VIEW.terrain && site ? S.terrainPreview.heading(fmtLatLon(site.lat, site.lon)) : S.common.southPolarMap;
    return (
      <>
        <Welcome />
        <div className="explore-grid">
          <section className="pane" aria-label={heading}>
            <div className="pane-head">
              <h3>{heading}</h3>
              <div className="mode-switch view-switch" role="group" aria-label={S.globe.viewSwitchLabel}>
                <button type="button" aria-pressed={view === VIEW.map} onClick={() => setView(VIEW.map)}>{S.globe.mapView}</button>
                <button type="button" aria-pressed={view === VIEW.globe} onClick={() => setView(VIEW.globe)}>{S.globe.globeView}</button>
                <button type="button" aria-pressed={view === VIEW.terrain} disabled={!covered && view !== VIEW.terrain}
                        onClick={() => setView(VIEW.terrain)}>{S.globe.terrainView}</button>
              </div>
            </div>
            {view === VIEW.map && (
              <Suspense fallback={<PaneLoading text={S.map.loadingTiles} />}>
                <MapView lat={latN} lon={lonN} catalog={state.catalog} selectedId={s.siteId} onPick={pick} />
              </Suspense>
            )}
            {view === VIEW.globe && (
              <LazyBoundary fallback={<PaneLoading text={S.globe.loadFailed} />}>
                <Suspense fallback={<PaneLoading text={S.globe.loadingModule} />}>
                  <MoonGlobe selected={site} onSelect={onGlobePick} selectedCovered={coverage ? coverage.covered : null} selectionPanel={false}
                             startAt={site} />
                </Suspense>
              </LazyBoundary>
            )}
            {view === VIEW.terrain && (site && covered ? (
              <LazyBoundary fallback={<PaneLoading text={S.globe.loadFailed} />}>
                <Suspense fallback={<PaneLoading text={S.terrainPreview.loading} />}>
                  <TerrainPreview lat={site.lat} lon={site.lon} finest={coverage?.finest ?? null} />
                </Suspense>
              </LazyBoundary>
            ) : <PaneLoading text={!site ? S.explorer.none : coverage ? S.terrainPreview.notCovered : S.explorer.checking} />)}
          </section>
          <SiteExplorer onInspect={() => setView(VIEW.terrain)}
                        onShowGlobe={view !== VIEW.globe ? () => setView(VIEW.globe) : undefined}
                        onShowMap={view !== VIEW.map ? () => setView(VIEW.map) : undefined} />
        </div>
        <div className="footer-space" />
      </>
    );
  }

  const i = Math.min(state.cursor, r.series.et.length - 1);
  const synthetic = r.provenance.terrain.synthetic;
  return (
    <div>
      <div className="site-header">
        <div>
          <h1 className="site-title">{r.site.name ?? T.customSite}</h1>
          <div className="site-coords">{T.coords(r.site.lat.toFixed(5), r.site.lon.toFixed(5), r.site.ground_h_m.toFixed(1),
            fmtUTC(r.window.start_utc), fmtUTC(r.window.end_utc))}</div>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button type="button" className="quiet-button" onClick={() => dispatch({ type: "closeResult" })}>{S.explorer.backToExplorer}</button>
          <a className="quiet-button" href={`/api/results/${r.id}/series.csv`} download>{T.downloads.series}</a>
          <a className="quiet-button" href={`/api/results/${r.id}/events.csv`} download>{T.downloads.events}</a>
          <a className="quiet-button" href={`/api/results/${r.id}/intervals.csv`} download>{T.downloads.intervals}</a>
          <a className="quiet-button" href={`/api/results/${r.id}/result.json`} download>{T.downloads.result}</a>
        </div>
      </div>
      <div style={{ padding: "0 24px 10px" }}><LabelChips result={r} /><DataKey /></div>
      <SiteContext r={r} />

      {state.mode === "public" && <PublicSummary r={r} />}

      <section className="panorama-wrap" id={RESULT_SECTIONS.panorama} aria-label={T.panoramaRegion}>
        <div className="panorama-head">
          <h2>{T.panoramaHeading}</h2>
          <div className="legend">
            <span><i style={{ background: "var(--sun)" }} />{T.legend.sunPath}</span>
            <span><i style={{ background: "var(--earth)" }} />{T.legend.earthPath}</span>
            <span><i style={{ background: "var(--terrain)", height: 8 }} />{T.legend.terrain(r.horizon.site_level)}</span>
            {r.horizon.incomplete_share > 0 && <span><i style={{ background: "repeating-linear-gradient(45deg,#ee9a6b 0 2px,transparent 2px 5px)", height: 8 }} />{T.legend.coverageRanOut}</span>}
            {r.horizon.sigma_deg && <span><i style={{ background: "rgba(163, 177, 191, 0.45)", height: 8 }} />{T.legend.sigmaBand}</span>}
            {(r.horizon.near_field ?? []).some(Boolean) && <span><i style={{ background: "#c79bf2", height: 4 }} />{T.legend.nearField}</span>}
          </div>
        </div>
        <HorizonPanorama result={r} cursor={i} />
        <p className="hint" style={{ margin: "2px 0 0" }}>{T.panoramaHint}</p>
      </section>

      <Readout r={r} i={i} playing={state.playing} />
      <div className="scrubber">
        <button className="play" onClick={() => dispatch({ type: "playing", playing: !state.playing })}
                aria-label={state.playing ? T.pause : T.play}>{state.playing ? T.pauseIcon : T.playIcon}</button>
        <input type="range" min={0} max={r.series.et.length - 1} value={i} aria-label={T.timeCursor}
               aria-valuetext={fmtUTC(r.series.utc[i])}
               onChange={(e) => dispatch({ type: "cursor", cursor: Number(e.target.value) })} />
        <span className="cursor-time">{fmtUTC(r.series.utc[i])}</span>
      </div>
      <Countdowns r={r} i={i} />
      <div id={RESULT_SECTIONS.timeline}><Timeline result={r} cursor={i} onCursor={(c) => dispatch({ type: "cursor", cursor: c })} /></div>
      <section className="section vis-section" id={RESULT_SECTIONS.visibility} aria-labelledby="vis-heading">
        <h2 id="vis-heading">{S.viz.visHeading}</h2>
        <VisibilityChart result={r} cursor={i} onCursor={(c) => dispatch({ type: "cursor", cursor: c })} />
      </section>

      <div className="grid-2" id={RESULT_SECTIONS.terrain}>
        <section className="pane" aria-label={S.common.mapRegion}>
          <div className="pane-head"><h3>{S.common.southPolarMap}</h3></div>
          <Suspense fallback={<PaneLoading text={S.map.loadingTiles} />}>
            <MapView lat={r.site.lat} lon={r.site.lon} catalog={state.catalog} selectedId={r.site.id} onPick={pick} />
          </Suspense>
        </section>
        <section className="pane" aria-label={T.terrainRegion}>
          <div className="pane-head"><h3>{T.terrainHeading}</h3></div>
          <Suspense fallback={<PaneLoading text={S.terrain3d.loading} />}>
            <Terrain3D result={r} cursor={i} />
          </Suspense>
        </section>
      </div>

      {state.mode === "technical" && <Figures r={r} />}
      {state.mode === "public" && <div style={{ marginTop: 22 }}><Figures r={r} /></div>}

      <div className="notes">
        {synthetic && <div className="note alert">{T.syntheticAlert}</div>}
        <div className="note radio">{r.geometric_not_radio}</div>
        {r.warnings.map((w, k) => <div className="note alert" key={k}>{w}</div>)}
      </div>

      {state.mode === "technical" && <div id={RESULT_SECTIONS.tables}><EventsTable r={r} /><SeriesTable r={r} /></div>}
      <div className="footer-space" />
    </div>
  );
}
