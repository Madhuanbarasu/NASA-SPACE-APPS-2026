import { Suspense, lazy, useEffect, useMemo } from "react";
import { S } from "../i18n";
import { fmtLatLon } from "../lib/format";
import { siteCoords, type GlobeLocation } from "../lib/moonGeo";
import { useStore, type SiteViewMode } from "../state/store";
import { LazyBoundary } from "./LazyBoundary";
import { SiteExplorer, useSiteCoverage } from "./SiteExplorer";
import { Welcome, WelcomeDetails } from "./Welcome";

// U-06: the map (OpenLayers, proj4) and the 3D views (three.js) are about 80 % of the JavaScript; they load on demand
// so the first screen does not wait for them (the analysis map and terrain: ResultWorkspace).
const MapView = lazy(() => import("./MapView").then((m) => ({ default: m.MapView })));
// Phase 5: the 3D Moon globe and the pre-analysis local terrain (three.js) load only when the user opens them
const MoonGlobe = lazy(() => import("./MoonGlobe").then((m) => ({ default: m.MoonGlobe })));
const TerrainPreview = lazy(() => import("./TerrainPreview").then((m) => ({ default: m.TerrainPreview })));
// welcome-pane views (internal tokens, never displayed); the current one lives in the store (state.siteView)
const VIEW = { map: "map", globe: "globe", terrain: "terrain" } as const;

function PaneLoading({ text }: { text: string }) {
  return <div className="pane-body"><div className="pane-empty">{text}</div></div>;
}

// LUNA-OPS 2.0 Phase 3: the analysis result is the ResultWorkspace; its labels and section ids are re-exported here for
// the mission dashboard.
export { LabelChips, RESULT_SECTIONS } from "./ResultLabels";
// the workspace (charts, panorama, timeline) loads when a result is first opened
const ResultWorkspace = lazy(() => import("./ResultWorkspace").then((m) => ({ default: m.ResultWorkspace })));

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
  // Phase 2: the comparison candidates are marked on the globe and the map alike
  const candidates = state.compareSites;
  const candidateLocs = useMemo(() => candidates.map((c) => ({ lat: c.lat, lon: c.lon })), [candidates]);

  if (!r) {
    const heading = view === VIEW.globe ? S.globe.heading
      : view === VIEW.terrain && site ? S.terrainPreview.heading(fmtLatLon(site.lat, site.lon)) : S.common.southPolarMap;
    // LUNA-OPS 2.0 Phase 2: the explorer stage. The map, globe or local terrain fills the workspace height under the
    // command bar; the compact title and the selected-site panel sit beside it (under it on small screens). One WebGL
    // view at a time: switching unmounts the previous one. The readiness board and the steps follow under the stage.
    return (
      <>
        <div className="explore">
          <div className="explore-grid">
            <Welcome />
            <section className="pane explore-pane" aria-label={heading}>
              <div className="pane-head">
                <h3>{heading}</h3>
                <div className="mode-switch view-switch" role="group" aria-label={S.globe.viewSwitchLabel}>
                  <button type="button" aria-pressed={view === VIEW.map} onClick={() => setView(VIEW.map)}>{S.globe.mapView}</button>
                  <button type="button" aria-pressed={view === VIEW.globe} onClick={() => setView(VIEW.globe)}>{S.globe.globeView}</button>
                  <button type="button" aria-pressed={view === VIEW.terrain} disabled={!covered && view !== VIEW.terrain}
                          onClick={() => setView(VIEW.terrain)}>{S.globe.terrainView}</button>
                </div>
              </div>
              {/* keyed by the view: each switch fades the new view in (instant with reduced motion) */}
              <div className="stage-swap" key={view}>
                {view === VIEW.map && (
                  <Suspense fallback={<PaneLoading text={S.map.loadingTiles} />}>
                    <MapView lat={latN} lon={lonN} catalog={state.catalog} selectedId={s.siteId} onPick={pick}
                             instruments candidates={candidates} />
                  </Suspense>
                )}
                {view === VIEW.globe && (
                  <LazyBoundary fallback={<PaneLoading text={S.globe.loadFailed} />}>
                    <Suspense fallback={<PaneLoading text={S.globe.loadingModule} />}>
                      <MoonGlobe selected={site} onSelect={onGlobePick} selectedCovered={coverage ? coverage.covered : null} selectionPanel={false}
                                 startAt={site} candidates={candidateLocs} />
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
              </div>
            </section>
            <SiteExplorer onInspect={() => setView(VIEW.terrain)}
                          onShowGlobe={view !== VIEW.globe ? () => setView(VIEW.globe) : undefined}
                          onShowMap={view !== VIEW.map ? () => setView(VIEW.map) : undefined} />
          </div>
        </div>
        <WelcomeDetails />
        <div className="footer-space" />
      </>
    );
  }

  return (
    <LazyBoundary fallback={<PaneLoading text={S.analysis.loadFailed} />}>
      <Suspense fallback={<PaneLoading text={S.analysis.loading} />}>
        <ResultWorkspace r={r} onPick={pick} />
      </Suspense>
    </LazyBoundary>
  );
}
