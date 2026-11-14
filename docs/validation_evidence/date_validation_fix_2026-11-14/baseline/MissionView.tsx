import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { Coverage } from "../api/types";
import { S } from "../i18n";
import { RULE_NAMES, fmtDuration, fmtLatLon, fmtPct, fmtUTC } from "../lib/format";
import { historyItem, landingKey, useStore, type CommsSummary, type CompareSite, type HistoryItem, type LandingSummary, type SiteViewMode } from "../state/store";
import { LabelChips, RESULT_SECTIONS } from "./ResultLabels";
import { useSiteCoverage } from "./SiteExplorer";
import { MissionLocator } from "./MissionLocator";
import { Icon, type IconName } from "../ui/Icon";
import { Metric } from "../ui/Metric";
import { StatusBadge } from "../ui/StatusBadge";
import { ViewHeader } from "../ui/ViewHeader";
import { readinessRows } from "./Welcome";

// Phase 5 prompt 4: mission dashboard. An overview of what the app already holds: the selected site and its terrain
// coverage (GET /api/coverage), the system status (GET /api/status), the candidate sites (the comparison sites), the
// analyses opened in this session and the comparison. Every figure is a field of an API response, shown with its
// validation label and uncertainty; nothing is scored, ranked, combined or suggested here.
// LUNA-OPS 2.0 Phase 4: mission-control layout (status strip, quick actions, focus card and south polar locator,
// candidate cards with their latest session analysis, comparison cells side by side) on the Phase 1-3 design system.
// The selection, analyse, open-result, deep-link and coverage logic is unchanged.

const M = S.mission;
const E = S.explorer;
const CM = S.compare.metrics;
const QUANTITY_NAMES: Record<string, string> = S.quantities;
// internal tokens (never displayed)
const VIEW = { map: "map", globe: "globe", terrain: "terrain" } as const;
const TAB = { site: "site", compare: "compare", landing: "landing", comms: "comms" } as const;
// prefix of the API's validation status word (protocol value, compared only)
const VALIDATED_PREFIX = "Validated";
const REDUCED_MOTION = "(prefers-reduced-motion: reduce)";
const SCROLL = { smooth: "smooth", instant: "auto" } as const;
const FOCUS_ATTR = "tabindex";
const FOCUS_VALUE = "-1";
const MAIN_ID = "main";
const NEAR = 1e-6; // degrees: same site (coordinates are rounded to 6 decimals when picked)
const SETTLE_FRAMES = 12, MAX_FRAMES = 120; // layout unchanged for 12 frames (about 0.2 s), at most about 2 s
const FLAG = "flag" as const;

const siteKey = (lat: number, lon: number) => `${lat.toFixed(6)},${lon.toFixed(6)}`;
const sameSite = (a: { lat: number; lon: number }, b: { lat: number; lon: number }) =>
  Math.abs(a.lat - b.lat) < NEAR && Math.abs(((a.lon - b.lon + 540) % 360) - 180) < NEAR;

/** A site added without a name is named by its coordinates (current format, or the sidebar's earlier signed format);
 *  that is not a name, so it is not shown twice or copied into the site-name field. */
const coordLabel = (name: string | null | undefined, lat: number, lon: number) =>
  !!name && (name === fmtLatLon(lat, lon) || name === `${lat.toFixed(3)}°, ${lon.toFixed(3)}°`);
const isCoordName = (c: CompareSite) => coordLabel(c.name, c.lat, c.lon);

/** Moves focus to an element once the newly selected tab has rendered it, then scrolls it into view when the layout
 *  has settled (the result view's charts measure their width and its map and 3D panes load lazily, which moves the
 *  sections below them). The scroll is instant when the user prefers reduced motion. */
function focusWhenReady(id: string) {
  let waited = 0, frames = 0, stable = 0, lastTop = NaN;
  const settle = (el: HTMLElement) => {
    const top = el.getBoundingClientRect().top + (document.getElementById(MAIN_ID)?.scrollTop ?? 0) + window.scrollY;
    stable = Math.abs(top - lastTop) < 1 ? stable + 1 : 0;
    lastTop = top;
    if (stable < SETTLE_FRAMES && ++frames < MAX_FRAMES) { requestAnimationFrame(() => settle(el)); return; }
    const reduce = window.matchMedia?.(REDUCED_MOTION).matches;
    el.scrollIntoView({ behavior: reduce ? SCROLL.instant : SCROLL.smooth, block: "start" });
  };
  const find = () => {
    const el = document.getElementById(id);
    if (!el) { if (waited++ < 300) requestAnimationFrame(find); return; }   // Phase 3: the analysis workspace loads on demand
    if (!el.hasAttribute(FOCUS_ATTR)) el.setAttribute(FOCUS_ATTR, FOCUS_VALUE);
    el.focus({ preventScroll: true });
    settle(el);
  };
  requestAnimationFrame(find);
}

function labelCounts(labels: Record<string, string>) {
  const v = Object.values(labels);
  const ok = v.filter((x) => x.startsWith(VALIDATED_PREFIX)).length;
  return { ok, pending: v.length - ok };
}

type CovEntry = { coverage: Coverage | null; error: string | null };

/** Terrain coverage of each candidate site (same endpoint as the selected site), fetched once per site. */
function useCandidateCoverage(sites: CompareSite[]) {
  const [cov, setCov] = useState<Record<string, CovEntry>>({});
  const asked = useRef(new Set<string>());
  const alive = useRef(true);
  useEffect(() => () => { alive.current = false; }, []);
  useEffect(() => {
    for (const c of sites) {
      const k = siteKey(c.lat, c.lon);
      if (asked.current.has(k)) continue;
      asked.current.add(k);
      api.coverage(c.lat, c.lon)
        .then((r) => { if (alive.current) setCov((m) => ({ ...m, [k]: { coverage: r, error: null } })); })
        .catch((e) => { if (alive.current) setCov((m) => ({ ...m, [k]: { coverage: null, error: String(e.message || e) } })); });
    }
  }, [sites]);
  return cov;
}

function coverageText(entry: CovEntry | undefined) {
  if (!entry) return { text: E.checking, tone: "" };
  if (entry.error) return { text: E.error(entry.error), tone: "bad" };
  const c = entry.coverage!;
  return c.covered ? { text: E.covered(c.levels.join(", ")), tone: "good" } : { text: E.notCovered(c.reason ?? S.common.unknown), tone: "bad" };
}

/** The registered terrain levels at a point as chips (the API's level names; the finest is marked). */
function LevelChips({ coverage }: { coverage: Coverage | null | undefined }) {
  if (!coverage?.covered || !coverage.levels.length) return null;
  return (
    <div className="level-chips" aria-label={M.levelsLabel}>
      {coverage.levels.map((lv) => <span key={lv} className={lv === coverage.finest ? "level-chip is-finest" : "level-chip"}>{lv}</span>)}
      {coverage.finest && <span className="level-note">{M.finestLevel(coverage.finest)}</span>}
    </div>
  );
}

function SummaryFigures({ item }: { item: HistoryItem }) {
  const sun = item.summary[`sun_${item.rules.sunlit}`];
  const earth = item.summary[`earth_${item.rules.dte}`];
  const ov = item.summary.overlap;
  // [label, value, rule note, tone]; the label texts are the dashboard's figure names (kept for the checks)
  const rows: [string, string, string, string][] = [
    [CM.sunlit, fmtPct(sun?.percent ?? null), RULE_NAMES[item.rules.sunlit] ?? "", "is-sun"],
    [CM.dark, fmtDuration(sun?.longest_gap_h ?? null), "", "is-sun"],
    [CM.dte, fmtPct(earth?.percent ?? null), RULE_NAMES[item.rules.dte] ?? "", "is-earth"],
    [CM.dtegap, fmtDuration(earth?.longest_gap_h ?? null), "", "is-earth"],
    [CM.overlap, fmtPct(ov?.percent ?? null), "", "is-both"],
  ];
  return (
    <dl className="mission-figures">
      {rows.map(([k, v, rule, tone]) => (
        <div key={k} className={tone}><dt>{k}</dt><dd>{v}{rule && <span className="mission-rule">{rule}</span>}</dd></div>
      ))}
    </dl>
  );
}

/** LUNA-OPS 2.0 Phase 5: the latest landing screening of a site in this session, finding by finding (status words as the
 *  API states them; nothing combined). Unknown and unavailable findings keep their own words. */
function LandingBlock({ summary, covered }: { summary: LandingSummary | undefined; covered: boolean }) {
  const LN = S.landing.findings.names;
  return (
    <div className="cand-landing">
      <span className="cand-analysis-title">{M.landingTitle}</span>
      {!summary ? <span className="cand-none">{covered ? M.landingNotRun : M.landingUnavailable}</span> : (
        <>
          <span className="cand-landing-findings">
            {summary.findings.map((f) => (
              <span key={f.key} className={`finding-status is-${f.status}`}>{LN[f.key as keyof typeof LN] ?? f.key}{": "}{f.status_text}</span>
            ))}
          </span>
          <span className="cand-window">{M.landingMeta(summary.product, summary.radius_m.toFixed(0), summary.candidates)}</span>
        </>
      )}
    </div>
  );
}

/** LUNA-OPS 2.0 Phase 6: the latest communication simulation of a site in this session (facts copied from the API: the
 *  engine's Earth-visibility windows, the next one, a configured hypothetical relay's two-leg windows, and whether the
 *  user's direct link budget was evaluated). Geometric visibility is never presented as a working link. */
function CommsBlock({ summary }: { summary: CommsSummary | undefined }) {
  return (
    <div className="cand-landing">
      <span className="cand-analysis-title">{M.commsTitle}</span>
      {!summary ? <span className="cand-none">{M.commsNotRun}</span> : (
        <>
          <span className="cand-window">{M.commsDirect(summary.directWindows, fmtDuration(summary.directOpenH))}</span>
          <span className="cand-window">{summary.directState ? M.commsOpenNow : summary.nextDirectOpenUtc ? M.commsNext(fmtUTC(summary.nextDirectOpenUtc)) : M.commsNoNext}</span>
          {summary.relayWindows != null && (
            <span className="cand-window">{M.commsRelay(summary.relayName ?? M.commsRelayUnnamed, summary.relayWindows, fmtDuration(summary.relayOpenH ?? 0))}</span>
          )}
          <span className="cand-labels">{summary.directRf === "evaluated" ? M.commsRfYes : M.commsRfNot}</span>
        </>
      )}
    </div>
  );
}

export function MissionView() {
  const { state, dispatch, runAnalysis, openResult } = useStore();
  const s = state.settings;
  const r = state.result;
  // the result on screen, or the one kept while the user explores (shown here, reopened by Analysis or a link)
  const cr = r ?? state.parked?.result ?? null;
  const { site, coverage, error, checking, covered } = useSiteCoverage();
  const sites = state.compareSites;
  const candCov = useCandidateCoverage(sites);
  const busy = !!state.job;
  const kernelsReady = !!state.status?.kernels.loaded;
  const [pendingRun, setPendingRun] = useState<string | null>(null);
  const [openFailed, setOpenFailed] = useState(false);

  // "Analyse" on a candidate selects it first; the analysis starts once the store holds the new coordinates
  useEffect(() => {
    if (pendingRun && pendingRun === `${s.lat},${s.lon}`) { setPendingRun(null); runAnalysis(); }
  }, [pendingRun, s.lat, s.lon, runAnalysis]);

  const select = (c: CompareSite) => {
    const lat = c.lat.toFixed(6), lon = c.lon.toFixed(6);
    dispatch({ type: "settings", patch: { lat, lon, siteName: isCoordName(c) ? null : c.name, siteId: c.id ?? null } });
    return `${lat},${lon}`;
  };
  const toExplorer = (view: SiteViewMode) => {
    if (r) dispatch({ type: "closeResult" });
    dispatch({ type: "siteView", view });
    dispatch({ type: "tab", tab: TAB.site });
    focusWhenReady(MAIN_ID);
  };
  const toAnalysis = async (section?: string) => {
    if (!r && state.parked) dispatch({ type: "restoreResult" });
    else if (!r && state.history[0] && !(await openResult(state.history[0].id))) { setOpenFailed(true); return; }
    dispatch({ type: "tab", tab: TAB.site });
    focusWhenReady(section ?? MAIN_ID);
  };
  const toCompare = () => { dispatch({ type: "tab", tab: TAB.compare }); focusWhenReady(MAIN_ID); };
  // Phase 5: open a site in the Landing Safety workspace; its screening runs there once the site's coverage is known
  const toLanding = (key: string) => {
    dispatch({ type: "landingRequest", key });
    dispatch({ type: "tab", tab: TAB.landing });
    focusWhenReady(MAIN_ID);
  };
  const landingFor = (c: { lat: number; lon: number }) => state.landingSummaries.find((x) => sameSite(x, c));
  // Phase 6: open a site in the Communication workspace (it runs the analysis there when this session has none)
  const toComms = (key: string) => {
    dispatch({ type: "commsRequest", key });
    dispatch({ type: "tab", tab: TAB.comms });
    focusWhenReady(MAIN_ID);
  };
  const commsFor = (c: { lat: number; lon: number }) => state.commsSummaries.find((x) => sameSite(x, c));
  const open = async (id: string) => {
    const ok = await openResult(id);
    setOpenFailed(!ok);
    if (ok) focusWhenReady(MAIN_ID);
  };

  const selectedIsCandidate = !!site && sites.some((c) => sameSite(c, site));
  const addSelected = () => {
    if (!site || selectedIsCandidate) return;
    dispatch({ type: "compareSites", sites: [...sites, { lat: site.lat, lon: site.lon, name: s.siteName || fmtLatLon(site.lat, site.lon), id: s.siteId }] });
  };
  const latestFor = (c: { lat: number; lon: number }) => state.history.find((h) => sameSite(h.site, c));

  const selCov = !site ? null : error ? { text: E.error(error), tone: "bad" } : checking || !coverage ? { text: E.checking, tone: "" }
    : coverage.covered ? { text: E.covered(coverage.levels.join(", ")), tone: "good" } : { text: E.notCovered(coverage.reason ?? S.common.unknown), tone: "bad" };
  const statusLabels = state.status?.labels ? labelCounts(Object.fromEntries(Object.entries(state.status.labels).map(([k, v]) => [k, v.validation]))) : null;
  const current = cr ? historyItem(cr) : null;
  const sunNow = cr ? cr.summary[`sun_${cr.provenance.parameters.rules.sunlit}`] : null;
  const earthNow = cr ? cr.summary[`earth_${cr.provenance.parameters.rules.dte}`] : null;
  const cmp = state.comparison;
  const st = state.status;
  const nLevels = st ? Object.keys(st.terrain.levels).length : 0;

  const nav: { label: string; icon: IconName; disabled: boolean; go: () => void }[] = [
    { label: M.navGlobe, icon: "globe", disabled: false, go: () => toExplorer(VIEW.globe) },
    { label: M.navMap, icon: "map", disabled: false, go: () => toExplorer(VIEW.map) },
    { label: M.navTerrain, icon: "terrain", disabled: !covered, go: () => toExplorer(VIEW.terrain) },
    { label: M.navAnalysis, icon: "chart", disabled: !r && !state.parked && !state.history.length, go: () => { void toAnalysis(); } },
    { label: M.navCompare, icon: "compare", disabled: false, go: toCompare },
  ];
  // Phase 4: every section of the Phase 3 analysis workspace (the data tables exist in Technical mode only)
  const links: { label: string; id: string; show: boolean }[] = [
    { label: M.linkSummary, id: RESULT_SECTIONS.summary, show: true },
    { label: M.linkPanorama, id: RESULT_SECTIONS.panorama, show: true },
    { label: M.linkTimeline, id: RESULT_SECTIONS.timeline, show: true },
    { label: M.linkVisibility, id: RESULT_SECTIONS.visibility, show: true },
    { label: M.linkEarth, id: RESULT_SECTIONS.earth, show: true },
    { label: M.linkTerrain, id: RESULT_SECTIONS.terrain, show: true },
    { label: M.linkValidation, id: RESULT_SECTIONS.validation, show: true },
    { label: M.linkTables, id: RESULT_SECTIONS.tables, show: state.mode === "technical" },
  ];
  // comparison cells (site x window) with the two calculated percentages under the comparison's own rules
  const cmpRows = cmp ? cmp.cells.map((c, k) => {
    const nW = cmp.windows.length, si = Math.floor(k / nW), wi = k % nW;
    const site0 = cmp.sites[si] ?? c.site;
    return { k, name: site0.name ?? fmtLatLon(site0.lat, site0.lon), wi, win: cmp.windows[wi], error: c.error,
      sun: c.summary?.[`sun_${cmp.base.sunlit_rule}`]?.percent ?? null, earth: c.summary?.[`earth_${cmp.base.dte_rule}`]?.percent ?? null,
      labels: c.labels ? labelCounts(Object.fromEntries(Object.entries(c.labels).map(([lk, lv]) => [lk, lv.validation]))) : null };
  }) : [];

  return (
    <div className="mission">
      <ViewHeader eyebrow={S.shell.eyebrows.mission} title={M.title} subtitle={M.intro} />

      {/* status strip: states and counts the app already holds (GET /api/status and this session) */}
      <section className="mission-strip" aria-label={M.stripLabel}>
        <dl className="metrics">
          <Metric label={M.stripKernels} value={!st ? S.common.unknown : st.kernels.loaded ? (st.kernels.profile ?? S.common.unknown) : M.stripNotLoaded}
                  note={st?.kernels.frame} state={st && (!st.kernels.loaded || st.kernels.profile !== "production") ? FLAG : undefined} />
          <Metric label={M.stripTerrain} value={!st ? S.common.unknown : M.stripProducts(nLevels)}
                  note={st?.terrain.synthetic_in_use ? S.viz.synthetic : undefined} state={st?.terrain.synthetic_in_use || (st && !nLevels) ? FLAG : undefined} />
          <Metric label={M.stripLabels} value={statusLabels ? M.stripLabelsValue(statusLabels.ok, statusLabels.pending) : S.common.na} />
          <Metric label={M.stripCandidates} value={String(sites.length)} />
          <Metric label={M.stripSession} value={String(state.history.length)} />
          <Metric label={M.stripComparison} value={state.compareJob ? M.stripRunning : cmp ? M.stripCells(cmp.sites.length, cmp.windows.length) : M.stripNone} />
        </dl>
      </section>

      <nav className="mission-nav" aria-label={M.navLabel}>
        {nav.map((n) => (
          <button key={n.label} type="button" className="quiet-button mission-action" disabled={n.disabled} onClick={n.go}>
            <Icon name={n.icon} />{n.label}</button>
        ))}
      </nav>
      <p className="hint mission-pad">{M.navNote}</p>

      <div className="mission-grid">
        {/* UI review: two independent stacks (selected site and system status; the locator, whose plot fills the height
            the left stack has), so a short card never leaves a row's leftover height below it */}
        <div className="mission-band">
          <div className="mission-col">
            <section className="mission-card" aria-labelledby="mission-selected">
              <h2 id="mission-selected">{M.selectedHeading}</h2>
              {!site ? <p className="hint">{E.none}</p> : (
                <>
                  <p className="explorer-coords mission-coords"><strong>{fmtLatLon(site.lat, site.lon)}</strong></p>
                  {s.siteName && <p className="explorer-name">{s.siteName}</p>}
                  <p className="hint">{S.globe.signed(site.lat.toFixed(6), site.lon.toFixed(6))}</p>
                  {selCov && <p className={`hint ${selCov.tone}`} aria-live="polite">{selCov.text}</p>}
                  <LevelChips coverage={coverage} />
                  <div className="explorer-actions">
                    <button type="button" className="quiet-button" disabled={!covered} onClick={() => toExplorer(VIEW.terrain)}>{E.inspect}</button>
                    <button type="button" className="quiet-button" disabled={!covered || !kernelsReady || busy}
                            onClick={() => runAnalysis()}>{busy ? S.sidebar.analysing : E.analyse}</button>
                    <button type="button" className="quiet-button" disabled={selectedIsCandidate} onClick={addSelected}>{M.addSelected}</button>
                    <button type="button" className="quiet-button" disabled={!covered} onClick={() => toLanding(landingKey(site.lat, site.lon))}>{M.openLandingSelected}</button>
                    <button type="button" className="quiet-button" disabled={!covered} onClick={() => toComms(landingKey(site.lat, site.lon))}>{M.openCommsSelected}</button>
                  </div>
                  {state.job && <p className="hint" aria-live="polite">{state.job.message}</p>}
                  {state.error && <p className="hint bad" role="alert">{state.error}</p>}
                  <p className="hint">{E.analysisNote}</p>
                </>
              )}
            </section>
            <section className="mission-card" aria-labelledby="mission-status">
              <h2 id="mission-status">{M.statusHeading}</h2>
              {state.statusError ? <p className="hint bad">{S.common.apiUnreachable(state.statusError)}</p> : (
                <ul className="welcome-status">
                  {readinessRows(state).map((row, k) => (
                    <li key={k}><span className={`dot ${row.ok === null ? "" : row.ok ? "ok" : "warn"}`} aria-hidden /> {row.text}</li>
                  ))}
                </ul>
              )}
              {st?.labels && (
                <div className="mission-badges" aria-label={M.labelsByQuantity}>
                  {Object.entries(st.labels).map(([k, v]) => <StatusBadge key={k} word={v.validation} prefix={QUANTITY_NAMES[k] ?? k} />)}
                </div>
              )}
              {statusLabels && <p className="hint">{M.labelsNow(statusLabels.ok, statusLabels.pending)}</p>}
              <p className="hint">{M.labelsNote}</p>
            </section>
          </div>
          <section className="mission-card mission-locator" aria-label={M.locatorHeading}>
            <h3 className="mission-subhead">{M.locatorHeading}</h3>
            <MissionLocator selected={site}
                            candidates={sites.map((c) => ({ lat: c.lat, lon: c.lon, name: c.name, isSelected: !!site && sameSite(c, site) }))}
                            analysed={state.history.filter((h) => !sites.some((c) => sameSite(c, h.site)) && !(site && sameSite(h.site, site)))
                              .map((h) => ({ lat: h.site.lat, lon: h.site.lon, name: h.site.name ?? fmtLatLon(h.site.lat, h.site.lon) }))}
                            onSelect={(k) => select(sites[k])} />
          </section>
        </div>

        <section className="mission-card" aria-labelledby="mission-current">
          <h2 id="mission-current">{M.currentHeading}</h2>
          {!cr || !current ? <p className="hint">{M.noResult}</p> : (
            <>
              <div className="mission-current-head">
                <p className="explorer-coords">{coordLabel(cr.site.name, cr.site.lat, cr.site.lon) ? <strong>{fmtLatLon(cr.site.lat, cr.site.lon)}</strong>
                  : <><strong>{cr.site.name ?? S.site.customSite}</strong>{" "}{fmtLatLon(cr.site.lat, cr.site.lon)}</>}</p>
                <p className="hint mono">{M.windowRange(fmtUTC(cr.window.start_utc), fmtUTC(cr.window.end_utc))}</p>
              </div>
              {!r && <p className="hint">{M.parkedNote}</p>}
              <LabelChips result={cr} />
              <SummaryFigures item={current} />
              <ul className="mission-flags">
                {sunNow && <li>{M.uncertainty(fmtDuration(sunNow.unknown_hours), String(sunNow.uncertain_windows ?? S.common.na),
                  sunNow.near_field_windows == null ? S.common.na : String(sunNow.near_field_windows))}</li>}
                {earthNow && earthNow.unknown_hours > 0 && <li>{M.earthUnknown(fmtDuration(earthNow.unknown_hours))}</li>}
                {cr.horizon.incomplete_share > 0 && <li>{M.lowerBounds((100 * cr.horizon.incomplete_share).toFixed(1))}</li>}
                <li>{cr.horizon.sigma_deg ? M.sigmaYes : M.sigmaNo}</li>
              </ul>
              <div className="mission-links" role="group" aria-label={M.linksLabel}>
                {links.filter((l) => l.show).map((l) => (
                  <button key={l.id} type="button" className="quiet-button" onClick={() => { void toAnalysis(l.id); }}>{l.label}</button>
                ))}
              </div>
            </>
          )}
        </section>

        <section className="mission-card" aria-labelledby="mission-candidates">
          <h2 id="mission-candidates">{M.candidatesHeading(sites.length)}</h2>
          {sites.length === 0 ? <p className="hint">{M.candidatesEmpty}</p> : (
            <ul className="mission-candidates">
              {sites.map((c) => {
                const k = siteKey(c.lat, c.lon);
                const cv = coverageText(candCov[k]);
                const ok = !!candCov[k]?.coverage?.covered;
                const isSel = !!site && sameSite(c, site);
                const last = latestFor(c);
                const lsun = last ? last.summary[`sun_${last.rules.sunlit}`]?.percent ?? null : null;
                const learth = last ? last.summary[`earth_${last.rules.dte}`]?.percent ?? null : null;
                const llc = last ? labelCounts(last.labels) : null;
                return (
                  <li key={k} className={isSel ? "is-selected" : undefined}>
                    <div className="mission-cand-head">
                      <strong>{c.name}</strong>{!isCoordName(c) && <span className="hint">{fmtLatLon(c.lat, c.lon)}</span>}
                      {isSel && <span className="chip mission-badge">{M.selectedBadge}</span>}
                    </div>
                    <p className={`hint ${cv.tone}`}>{cv.text}</p>
                    <LevelChips coverage={candCov[k]?.coverage} />
                    {/* the latest analysis of this site in this session (stored history), or a plain statement that there is none */}
                    <div className="cand-analysis">
                      {!last ? (
                        <span className="cand-none">{isSel && busy ? (state.job?.message ?? S.sidebar.analysing) : M.candNotAnalysed}</span>
                      ) : (
                        <>
                          <span className="cand-analysis-title">{M.candLatest}</span>
                          <span className="cand-window mono">{M.windowRange(fmtUTC(last.window.start_utc), fmtUTC(last.window.end_utc))}</span>
                          <span className="cand-values">
                            <span className="cand-value is-sun"><span className="cand-k">{CM.sunlit}</span><span className="cand-v">{fmtPct(lsun)}</span></span>
                            <span className="cand-value is-earth"><span className="cand-k">{CM.dte}</span><span className="cand-v">{fmtPct(learth)}</span></span>
                          </span>
                          {llc && <span className="cand-labels">{S.viz.cellLabels(llc.ok, llc.pending)}</span>}
                        </>
                      )}
                    </div>
                    <LandingBlock summary={landingFor(c)} covered={ok} />
                    <CommsBlock summary={commsFor(c)} />
                    <div className="explorer-actions">
                      <button type="button" className="quiet-button" disabled={isSel} aria-label={M.selectSite(c.name)}
                              onClick={() => select(c)}>{M.select}</button>
                      <button type="button" className="quiet-button" disabled={!ok || !kernelsReady || busy} aria-label={M.analyseSite(c.name)}
                              onClick={() => setPendingRun(select(c))}>{M.analyse}</button>
                      {last && <button type="button" className="quiet-button" aria-label={M.openResultFor(c.name)}
                                       onClick={() => { void open(last.id); }}>{M.openResult}</button>}
                      <button type="button" className="quiet-button" disabled={!ok} aria-label={M.openLandingFor(c.name)}
                              onClick={() => { select(c); toLanding(landingKey(c.lat, c.lon)); }}>{M.openLanding}</button>
                      <button type="button" className="quiet-button" disabled={!ok} aria-label={M.openCommsFor(c.name)}
                              onClick={() => { select(c); toComms(landingKey(c.lat, c.lon)); }}>{M.openComms}</button>
                      <button type="button" className="quiet-button" aria-label={M.removeSite(c.name)}
                              onClick={() => dispatch({ type: "compareSites", sites: sites.filter((x) => x !== c) })}>{S.common.remove}</button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
          {sites.length > 0 && <p className="hint">{M.landingNote}</p>}
          <div className="explorer-actions">
            <button type="button" className="quiet-button" disabled={!site || selectedIsCandidate} onClick={addSelected}>{M.addSelected}</button>
            <button type="button" className="quiet-button" disabled={sites.length === 0} onClick={toCompare}>{M.compareCandidates}</button>
          </div>
          <p className="hint">{M.candidatesHint}</p>
        </section>


        <section className="mission-card" aria-labelledby="mission-history">
          <h2 id="mission-history">{M.historyHeading(state.history.length)}</h2>
          {openFailed && state.error && <p className="hint bad" role="alert">{state.error}</p>}
          {state.history.length === 0 ? <p className="hint">{M.historyEmpty}</p> : (
            <div className="table-scroll">
              <table className="data">
                <caption className="sr-only">{M.historyCaption}</caption>
                <thead><tr><th>{M.colSite}</th><th>{M.colWindow}</th><th className="num">{M.colSunlit}</th><th className="num">{M.colDark}</th>
                  <th className="num">{M.colEarth}</th><th className="num">{M.colOverlap}</th><th>{M.colLabels}</th><th>{M.colOpen}</th></tr></thead>
                <tbody>{state.history.map((h) => {
                  const sun = h.summary[`sun_${h.rules.sunlit}`], earth = h.summary[`earth_${h.rules.dte}`];
                  const lc = labelCounts(h.labels);
                  const named = !!h.site.name && !coordLabel(h.site.name, h.site.lat, h.site.lon);
                  const name = named ? h.site.name! : fmtLatLon(h.site.lat, h.site.lon);
                  return (
                    <tr key={h.id} className={cr?.id === h.id ? "is-selected" : undefined}>
                      <td>{name}{named && <div className="hint">{fmtLatLon(h.site.lat, h.site.lon)}</div>}</td>
                      <td>{M.windowRange(fmtUTC(h.window.start_utc), fmtUTC(h.window.end_utc))}</td>
                      <td className="num">{fmtPct(sun?.percent ?? null)}</td>
                      <td className="num">{fmtDuration(sun?.longest_gap_h ?? null)}</td>
                      <td className="num">{fmtPct(earth?.percent ?? null)}</td>
                      <td className="num">{fmtPct(h.summary.overlap?.percent ?? null)}</td>
                      <td>{S.viz.cellLabels(lc.ok, lc.pending)}</td>
                      <td><button type="button" className="quiet-button" aria-label={M.openFor(name)} onClick={() => { void open(h.id); }}>{M.open}</button></td>
                    </tr>
                  );
                })}</tbody>
              </table>
            </div>
          )}
          <p className="hint">{M.historyKept}</p>
        </section>

        <section className="mission-card" aria-labelledby="mission-comparison">
          <h2 id="mission-comparison">{M.comparisonHeading}</h2>
          {state.compareJob ? <p className="hint" aria-live="polite">{state.compareJob.message}</p>
            : cmp ? <p className="hint">{M.comparisonReady(cmp.sites.length, cmp.windows.length)}</p>
            : <p className="hint">{M.comparisonNone}</p>}
          {state.compareError && <p className="hint bad">{state.compareError}</p>}
          {cmp && cmpRows.length > 0 && (
            <div className="table-scroll mission-cmp">
              <table className="data">
                <caption className="sr-only">{M.cmpCaption}</caption>
                <thead><tr><th>{M.colSite}</th><th>{M.colWindow}</th>
                  <th className="num">{M.cmpSunlit(RULE_NAMES[cmp.base.sunlit_rule] ?? String(cmp.base.sunlit_rule))}</th>
                  <th className="num">{M.cmpEarth(RULE_NAMES[cmp.base.dte_rule] ?? String(cmp.base.dte_rule))}</th><th>{M.colLabels}</th></tr></thead>
                <tbody>{cmpRows.map((c) => (
                  <tr key={c.k}>
                    <td>{c.name}</td>
                    <td>{c.win ? M.windowRange(fmtUTC(c.win.start_utc), fmtUTC(c.win.end_utc)) : S.common.na}</td>
                    {c.error ? <td colSpan={2} className="cmp-unavailable">{S.compare.cardUnavailable(c.error)}</td> : (<>
                      <td className="num cmp-sun">{c.sun == null ? S.compare.unavailable : fmtPct(c.sun)}</td>
                      <td className="num cmp-earth">{c.earth == null ? S.compare.unavailable : fmtPct(c.earth)}</td>
                    </>)}
                    <td>{c.labels ? S.viz.cellLabels(c.labels.ok, c.labels.pending) : S.common.na}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
          {cmp && <p className="hint">{M.cmpNote}</p>}
          <div className="explorer-actions">
            <button type="button" className="quiet-button" onClick={toCompare}>{cmp ? M.openComparison : M.compareCandidates}</button>
          </div>
        </section>
      </div>
      <p className="hint mission-pad">{M.integrity}</p>
      <div className="footer-space" />
    </div>
  );
}
