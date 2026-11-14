import { S } from "../i18n";
import { fmtLatLon } from "../lib/format";
import { parseSite } from "../lib/moonGeo";
import { windowValid } from "../lib/timeWindow";
import { useStore } from "../state/store";

// Phase 5: the selected site (one source: the store's site coordinates, set by the globe, the map, the catalogue or
// typing) with its registered-terrain coverage from GET /api/coverage, and the way into local terrain and the analysis.
// Every value shown comes from the API; nothing is estimated here.

const E = S.explorer;

export interface SiteExplorerProps {
  onInspect: () => void;
  onShowGlobe?: () => void;
  onShowMap?: () => void;
}

/** Whether the store's coverage answer belongs to the current site coordinates (never show a stale answer). */
export function useSiteCoverage() {
  const { state } = useStore();
  const s = state.settings;
  const site = parseSite(s.lat, s.lon);
  const fresh = state.coverageFor === `${s.lat},${s.lon}`;
  const coverage = fresh ? state.coverage : null;
  const error = fresh ? state.coverageError : null;
  return { site, coverage, error, checking: !!site && !fresh, covered: !!coverage?.covered };
}

export function SiteExplorer({ onInspect, onShowGlobe, onShowMap }: SiteExplorerProps) {
  const { state, dispatch, runAnalysis } = useStore();
  const parked = state.parked?.result;
  const { site, coverage, error, checking, covered } = useSiteCoverage();
  const s = state.settings;
  const busy = !!state.job;
  const kernelsReady = !!state.status?.kernels.loaded;
  const levels = state.status?.terrain.levels ?? {};
  const finestKey = coverage?.products?.[0];
  const finestName = finestKey ? (levels[finestKey]?.product ?? finestKey) : null;
  const coverageText = !site ? "" : error ? E.error(error) : checking || !coverage ? E.checking
    : coverage.covered ? E.covered(coverage.levels.join(", ")) : E.notCovered(coverage.reason ?? S.common.unknown);
  const tone = error || (coverage && !coverage.covered) ? "bad" : covered ? "good" : "";

  return (
    <section className="explorer pane" aria-labelledby="explorer-title">
      <div className="pane-head"><h3 id="explorer-title">{E.heading}</h3></div>
      <div className="explorer-body">
        {!site ? <p className="hint">{E.none}</p> : (
          <>
            <p className="explorer-coords"><strong>{fmtLatLon(site.lat, site.lon)}</strong></p>
            {s.siteName && <p className="explorer-name">{s.siteName}</p>}
            <p className="hint">{S.globe.signed(site.lat.toFixed(6), site.lon.toFixed(6))}</p>
            <p className={`hint ${tone}`} aria-live="polite">{coverageText}</p>
            {covered && coverage?.finest && finestName && <p className="hint">{E.finest(coverage.finest, finestName)}</p>}
            <div className="explorer-actions">
              <button type="button" className="quiet-button" disabled={!covered} onClick={onInspect}>{E.inspect}</button>
              <button type="button" className="run-button explorer-run" disabled={!covered || !kernelsReady || busy || !windowValid(s.start, s.end)}
                      onClick={() => runAnalysis()}>{busy ? S.sidebar.analysing : E.analyse}</button>
            </div>
            <div className="explorer-actions">
              {onShowGlobe && <button type="button" className="quiet-button" onClick={onShowGlobe}>{E.showGlobe}</button>}
              {onShowMap && <button type="button" className="quiet-button" onClick={onShowMap}>{E.showMap}</button>}
            </div>
            {state.job && <p className="hint">{state.job.message}</p>}
            {state.error && <p className="hint bad">{state.error}</p>}
            <p className="hint">{E.analysisNote}</p>
          </>
        )}
        {parked && (
          <div className="explorer-actions">
            <button type="button" className="quiet-button" onClick={() => dispatch({ type: "restoreResult" })}>
              {E.returnToResult(parked.site.name ?? fmtLatLon(parked.site.lat, parked.site.lon))}</button>
          </div>
        )}
        <p className="hint">{E.integrity}</p>
      </div>
    </section>
  );
}
