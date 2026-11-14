import type { ObserverProfile, PanelModel, Rule } from "../api/types";
import { S } from "../i18n";
import { PANEL_NAMES, RULE_NAMES, fmtLatLon, fromInputValue, toInputValue } from "../lib/format";
import { lon360, parseSite } from "../lib/moonGeo";
import { windowValid } from "../lib/timeWindow";
import { useStore } from "../state/store";
import { Icon } from "../ui/Icon";

function Segmented<T extends string>({ value, options, onChange, label }:
  { value: T; options: { v: T; t: string }[]; onChange: (v: T) => void; label: string }) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.v} type="button" aria-pressed={value === o.v} onClick={() => onChange(o.v)}>{o.t}</button>
      ))}
    </div>
  );
}

const T = S.sidebar;
const RULES: { v: Rule; t: string }[] = (["any", "centre", "full"] as const).map((v) => ({ v, t: S.ruleOptions[v] }));
const PROFILES: { v: ObserverProfile; t: string }[] =
  (["surface", "astronaut", "equipment"] as const).map((v) => ({ v, t: S.observerProfiles[v] }));

interface SidebarProps {
  /** shown (docked on wide screens, the open drawer below 1200 px) or hidden */
  open: boolean;
  onClose: () => void;
}

// LUNA-OPS 2.0: the Mission Parameters panel (site, dates, observer, visibility rules, power indicator panel)
export function Sidebar({ open, onClose }: SidebarProps) {
  const { state, dispatch, runAnalysis } = useStore();
  const s = state.settings;
  const set = (patch: Partial<typeof s>) => dispatch({ type: "settings", patch });
  // typed coordinates are no longer the curated site: drop its id and its name (a name the user typed is kept)
  const typedCoords: Partial<typeof s> = s.siteId ? { siteId: null, siteName: null } : { siteId: null };

  // AUD-01 (pre-Phase 7 audit): typed coordinates are checked with the same rules as the backend and the Site explorer
  // (lib/moonGeo parseSite: a number, latitude -90 to 90, longitude -360 to 360). Each field is checked on its own (the
  // other one replaced by a valid 0) so only the field that is wrong is marked invalid.
  const latN = Number(s.lat), lonN = Number(s.lon);
  const coordsGiven = parseSite(s.lat, s.lon) !== null;
  const latBad = s.lat.trim() !== "" && parseSite(s.lat, "0") === null;
  const lonBad = s.lon.trim() !== "" && parseSite("0", s.lon) === null;

  // terrain coverage is looked up once in the store and shared with the explorer and globe (Phase 5)
  const cov = state.coverage, covErr = state.coverageError;

  const busy = !!state.job;
  const kernelsReady = !!state.status?.kernels.loaded;
  // E2E-07: the end must be strictly after the start (UTC); otherwise the end field is marked and Analyse disabled
  const windowBad = !windowValid(s.start, s.end);
  const azUsed = lon360(s.panelAz);
  const canRun = coordsGiven && cov?.covered && kernelsReady && !busy && !windowBad;

  const addToCompare = () => {
    if (!coordsGiven) return;
    // a site without a name is named by its coordinates, in the same format as every other view
    const name = s.siteName || fmtLatLon(latN, lonN);
    if (state.compareSites.some((x) => x.lat === latN && x.lon === lonN)) return;
    dispatch({ type: "compareSites", sites: [...state.compareSites, { lat: latN, lon: lonN, name, id: s.siteId }] });
  };

  return (
    <aside className="sidebar" id="mission-parameters" aria-label={T.label}>
      <div className="sidebar-panel" hidden={!open}>
      <div className="sidebar-head">
        <p className="eyebrow">{S.shell.paramsTitle}</p>
        <button type="button" id="params-close" className="icon-button sidebar-close" aria-label={S.shell.closeParams}
                title={S.shell.closeParams} onClick={onClose}><Icon name="close" /></button>
      </div>
      <section className="side-section">
        <h2>{T.siteHeading}</h2>
        {state.catalog.length > 0 ? (
          <ul className="site-list" aria-label={T.curatedSitesLabel}>
            {state.catalog.map((c) => (
              <li key={c.id}>
                <button aria-pressed={s.siteId === c.id}
                        onClick={() => set({ lat: c.lat.toFixed(6), lon: c.lon.toFixed(6), siteName: c.name, siteId: c.id })}>
                  <span className="site-name">{c.name}</span>
                  <span className="site-meta">{T.siteMeta(c.point_label, c.extent_label ?? c.source?.product)}</span>
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="empty-note">{state.catalogReason ?? T.loadingCatalogue}</p>
        )}
        <div className="field-row">
          <div className="field">
            <label htmlFor="lat">{T.latitude}</label>
            <input id="lat" type="text" inputMode="decimal" placeholder={T.latitudePlaceholder} value={s.lat}
                   aria-invalid={latBad || undefined} aria-describedby="coord-hint"
                   onChange={(e) => set({ lat: e.target.value, ...typedCoords })} />
          </div>
          <div className="field">
            <label htmlFor="lon">{T.longitude}</label>
            <input id="lon" type="text" inputMode="decimal" placeholder={T.longitudePlaceholder} value={s.lon}
                   aria-invalid={lonBad || undefined} aria-describedby="coord-hint"
                   onChange={(e) => set({ lon: e.target.value, ...typedCoords })} />
          </div>
        </div>
        <div className="field">
          <label htmlFor="sname">{T.siteName}</label>
          <input id="sname" type="text" value={s.siteName ?? ""} onChange={(e) => set({ siteName: e.target.value || null })} />
        </div>
        <p id="coord-hint" className={`hint ${latBad || lonBad ? "bad" : cov ? (cov.covered ? "good" : "bad") : covErr ? "bad" : ""}`} aria-live="polite">
          {latBad || lonBad ? T.invalidCoordinates
            : !coordsGiven ? T.pickHint
            : covErr ? covErr
            : !cov ? T.checkingCoverage
            : cov.covered ? T.coverage(cov.levels.join(", "))
            : T.noCoverage(cov.reason)}
        </p>
        <button className="quiet-button" type="button" onClick={addToCompare} disabled={!coordsGiven}>{T.addToCompare}</button>
      </section>

      <section className="side-section">
        <h2>{T.datesHeading}</h2>
        <div className="field">
          <label htmlFor="start">{T.start}</label>
          <input id="start" type="datetime-local" value={toInputValue(s.start)} onChange={(e) => set({ start: fromInputValue(e.target.value) })} />
        </div>
        <div className="field">
          <label htmlFor="end">{T.end}</label>
          <input id="end" type="datetime-local" value={toInputValue(s.end)} onChange={(e) => set({ end: fromInputValue(e.target.value) })}
                 aria-invalid={windowBad || undefined} aria-describedby={windowBad ? "window-hint" : undefined} />
        </div>
        {windowBad && <p id="window-hint" className="hint bad" aria-live="polite">{T.invalidWindow}</p>}
        <div className="field">
          <label htmlFor="step">{T.displayStep}</label>
          <select id="step" value={s.stepMin} onChange={(e) => set({ stepMin: Number(e.target.value) })}>
            {[5, 15, 30, 60].map((m) => <option key={m} value={m}>{T.stepOption(m)}</option>)}
          </select>
          <p className="hint">{T.stepHint}</p>
        </div>
      </section>

      <section className="side-section">
        <h2>{T.observerHeading}</h2>
        <Segmented<ObserverProfile> label={T.observerProfile} value={s.observerProfile}
          options={PROFILES}
          onChange={(v) => set({ observerProfile: v, observerH: v === "surface" ? 0 : s.observerH })} />
        <div className="field" style={{ marginTop: 10 }}>
          <label htmlFor="obsh">{T.observerHeight}</label>
          <input id="obsh" type="number" min={0} max={100} step={0.1} value={s.observerH}
                 disabled={s.observerProfile === "surface"}
                 onChange={(e) => set({ observerH: Math.max(0, Math.min(100, Number(e.target.value))) })} />
          {s.observerProfile === "surface" && <p className="hint">{T.surfaceHint}</p>}
        </div>
      </section>

      <section className="side-section">
        <h2>{T.rulesHeading}</h2>
        <div className="field">
          <span className="label">{T.sunlitMeans}</span>
          <Segmented<Rule> label={T.sunlitRule} value={s.sunlitRule} options={RULES} onChange={(v) => set({ sunlitRule: v })} />
        </div>
        <div className="field">
          <span className="label">{T.dteMeans}</span>
          <Segmented<Rule> label={T.dteRule} value={s.dteRule} options={RULES} onChange={(v) => set({ dteRule: v })} />
          <p className="hint">{T.dteHint(RULE_NAMES[s.dteRule])}</p>
        </div>
        <div className="field">
          <label htmlFor="margin">{T.margin}</label>
          <input id="margin" type="number" min={0} max={10} step={0.1} value={s.margin}
                 onChange={(e) => set({ margin: Math.max(0, Math.min(10, Number(e.target.value))) })} />
        </div>
      </section>

      <section className="side-section">
        <h2>{T.panelHeading}</h2>
        <div className="field">
          <label htmlFor="panel">{T.referencePanel}</label>
          <select id="panel" value={s.panel} onChange={(e) => set({ panel: e.target.value as PanelModel })}>
            {Object.entries(PANEL_NAMES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
        {s.panel === "fixed_vertical" && (
          <div className="field">
            <label htmlFor="paz">{T.panelAzimuth}</label>
            <input id="paz" type="number" min={0} max={360} step={1} value={s.panelAz}
                   onChange={(e) => set({ panelAz: Number(e.target.value) })} />
            {Number.isFinite(azUsed) && azUsed !== s.panelAz && <p className="hint">{T.panelAzimuthNormalized(azUsed)}</p>}
          </div>
        )}
        <p className="hint">{T.panelHint}</p>
      </section>

      <section className="side-section" style={{ borderBottom: 0 }}>
        <button className="run-button" type="button" disabled={!canRun} onClick={() => runAnalysis()}>
          {busy ? T.analysing : T.analyse}
        </button>
        {!kernelsReady && state.status && <p className="hint bad">{state.status.kernels.error}</p>}
        {state.statusError && <p className="hint bad">{S.common.apiUnreachable(state.statusError)}</p>}
        {state.job && (
          <>
            <div className="progress" aria-hidden><div style={{ width: `${Math.round(state.job.progress * 100)}%` }} /></div>
            <p className="hint" aria-live="polite">{state.job.message}</p>
          </>
        )}
        {state.error && <p className="hint bad" role="alert">{state.error}</p>}
      </section>
      </div>
      {/* outside the panel, so it is announced even while the panel is collapsed or the drawer is closed */}
      <p className="sr-only" role="status">{!busy && state.result ? T.resultReady(state.result.site.name ?? S.site.customSite) : ""}</p>
    </aside>
  );
}
