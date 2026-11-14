import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { Coverage } from "../api/types";
import { S } from "../i18n";
import { RULE_NAMES, fmtDuration, fmtLatLon, fmtPct, fmtUTC } from "../lib/format";
import { historyItem, useStore, type CompareSite, type HistoryItem, type SiteViewMode } from "../state/store";
import { LabelChips, RESULT_SECTIONS } from "./SiteView";
import { useSiteCoverage } from "./SiteExplorer";
import { ViewHeader } from "../ui/ViewHeader";
import { readinessRows } from "./Welcome";

// Phase 5 prompt 4: mission dashboard. An overview of what the app already holds: the selected site and its terrain
// coverage (GET /api/coverage), the system status (GET /api/status), the candidate sites (the comparison sites), the
// analyses opened in this session and the comparison. Every figure is a field of an API response, shown with its
// validation label and uncertainty; nothing is scored, ranked, combined or recommended here.

const M = S.mission;
const E = S.explorer;
const CM = S.compare.metrics;
// internal tokens (never displayed)
const VIEW = { map: "map", globe: "globe", terrain: "terrain" } as const;
const TAB = { site: "site", compare: "compare" } as const;
// prefix of the API's validation status word (protocol value, compared only)
const VALIDATED_PREFIX = "Validated";
const REDUCED_MOTION = "(prefers-reduced-motion: reduce)";
const SCROLL = { smooth: "smooth", instant: "auto" } as const;
const FOCUS_ATTR = "tabindex";
const FOCUS_VALUE = "-1";
const MAIN_ID = "main";
const NEAR = 1e-6; // degrees: same site (coordinates are rounded to 6 decimals when picked)
const SETTLE_FRAMES = 12, MAX_FRAMES = 120; // layout unchanged for 12 frames (about 0.2 s), at most about 2 s

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

function SummaryFigures({ item }: { item: HistoryItem }) {
  const sun = item.summary[`sun_${item.rules.sunlit}`];
  const earth = item.summary[`earth_${item.rules.dte}`];
  const ov = item.summary.overlap;
  const rows: [string, string, string][] = [
    [CM.sunlit, fmtPct(sun?.percent ?? null), RULE_NAMES[item.rules.sunlit] ?? ""],
    [CM.dark, fmtDuration(sun?.longest_gap_h ?? null), ""],
    [CM.dte, fmtPct(earth?.percent ?? null), RULE_NAMES[item.rules.dte] ?? ""],
    [CM.dtegap, fmtDuration(earth?.longest_gap_h ?? null), ""],
    [CM.overlap, fmtPct(ov?.percent ?? null), ""],
  ];
  return (
    <dl className="mission-figures">
      {rows.map(([k, v, rule]) => (
        <div key={k}><dt>{k}</dt><dd>{v}{rule && <span className="mission-rule">{rule}</span>}</dd></div>
      ))}
    </dl>
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

  const nav: { label: string; disabled: boolean; go: () => void }[] = [
    { label: M.navGlobe, disabled: false, go: () => toExplorer(VIEW.globe) },
    { label: M.navMap, disabled: false, go: () => toExplorer(VIEW.map) },
    { label: M.navTerrain, disabled: !covered, go: () => toExplorer(VIEW.terrain) },
    { label: M.navAnalysis, disabled: !r && !state.parked && !state.history.length, go: () => { void toAnalysis(); } },
    { label: M.navCompare, disabled: false, go: toCompare },
  ];
  const links: { label: string; id: string; show: boolean }[] = [
    { label: M.linkPanorama, id: RESULT_SECTIONS.panorama, show: true },
    { label: M.linkTimeline, id: RESULT_SECTIONS.timeline, show: true },
    { label: M.linkVisibility, id: RESULT_SECTIONS.visibility, show: true },
    { label: M.linkTerrain, id: RESULT_SECTIONS.terrain, show: true },
    { label: M.linkTables, id: RESULT_SECTIONS.tables, show: state.mode === "technical" },
  ];

  return (
    <div className="mission">
      <ViewHeader eyebrow={S.shell.eyebrows.mission} title={M.title} subtitle={M.intro} />

      <nav className="mission-nav" aria-label={M.navLabel}>
        {nav.map((n) => (
          <button key={n.label} type="button" className="quiet-button" disabled={n.disabled} onClick={n.go}>{n.label}</button>
        ))}
      </nav>
      <p className="hint mission-pad">{M.navNote}</p>

      <div className="mission-grid">
        <section className="mission-card" aria-labelledby="mission-selected">
          <h2 id="mission-selected">{M.selectedHeading}</h2>
          {!site ? <p className="hint">{E.none}</p> : (
            <>
              <p className="explorer-coords"><strong>{fmtLatLon(site.lat, site.lon)}</strong></p>
              {s.siteName && <p className="explorer-name">{s.siteName}</p>}
              <p className="hint">{S.globe.signed(site.lat.toFixed(6), site.lon.toFixed(6))}</p>
              {selCov && <p className={`hint ${selCov.tone}`} aria-live="polite">{selCov.text}</p>}
              <div className="explorer-actions">
                <button type="button" className="quiet-button" disabled={!covered} onClick={() => toExplorer(VIEW.terrain)}>{E.inspect}</button>
                <button type="button" className="quiet-button" disabled={!covered || !kernelsReady || busy}
                        onClick={() => runAnalysis()}>{busy ? S.sidebar.analysing : E.analyse}</button>
                <button type="button" className="quiet-button" disabled={selectedIsCandidate} onClick={addSelected}>{M.addSelected}</button>
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
          {statusLabels && <p className="hint">{M.labelsNow(statusLabels.ok, statusLabels.pending)}</p>}
          <p className="hint">{M.labelsNote}</p>
        </section>

        <section className="mission-card mission-wide" aria-labelledby="mission-current">
          <h2 id="mission-current">{M.currentHeading}</h2>
          {!cr || !current ? <p className="hint">{M.noResult}</p> : (
            <>
              <p className="explorer-coords">{coordLabel(cr.site.name, cr.site.lat, cr.site.lon) ? <strong>{fmtLatLon(cr.site.lat, cr.site.lon)}</strong>
                : <><strong>{cr.site.name ?? S.site.customSite}</strong>{" "}{fmtLatLon(cr.site.lat, cr.site.lon)}</>}</p>
              <p className="hint">{M.windowRange(fmtUTC(cr.window.start_utc), fmtUTC(cr.window.end_utc))}</p>
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

        <section className="mission-card mission-wide" aria-labelledby="mission-candidates">
          <h2 id="mission-candidates">{M.candidatesHeading(sites.length)}</h2>
          {sites.length === 0 ? <p className="hint">{M.candidatesEmpty}</p> : (
            <ul className="mission-candidates">
              {sites.map((c) => {
                const k = siteKey(c.lat, c.lon);
                const cv = coverageText(candCov[k]);
                const ok = !!candCov[k]?.coverage?.covered;
                const isSel = !!site && sameSite(c, site);
                const last = latestFor(c);
                return (
                  <li key={k} className={isSel ? "is-selected" : undefined}>
                    <div className="mission-cand-head">
                      <strong>{c.name}</strong>{!isCoordName(c) && <span className="hint">{fmtLatLon(c.lat, c.lon)}</span>}
                      {isSel && <span className="chip mission-badge">{M.selectedBadge}</span>}
                    </div>
                    <p className={`hint ${cv.tone}`}>{cv.text}</p>
                    <div className="explorer-actions">
                      <button type="button" className="quiet-button" disabled={isSel} aria-label={M.selectSite(c.name)}
                              onClick={() => select(c)}>{M.select}</button>
                      <button type="button" className="quiet-button" disabled={!ok || !kernelsReady || busy} aria-label={M.analyseSite(c.name)}
                              onClick={() => setPendingRun(select(c))}>{M.analyse}</button>
                      {last && <button type="button" className="quiet-button" aria-label={M.openResultFor(c.name)}
                                       onClick={() => { void open(last.id); }}>{M.openResult}</button>}
                      <button type="button" className="quiet-button" aria-label={M.removeSite(c.name)}
                              onClick={() => dispatch({ type: "compareSites", sites: sites.filter((x) => x !== c) })}>{S.common.remove}</button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
          <div className="explorer-actions">
            <button type="button" className="quiet-button" disabled={!site || selectedIsCandidate} onClick={addSelected}>{M.addSelected}</button>
            <button type="button" className="quiet-button" disabled={sites.length === 0} onClick={toCompare}>{M.compareCandidates}</button>
          </div>
          <p className="hint">{M.candidatesHint}</p>
        </section>

        <section className="mission-card mission-wide" aria-labelledby="mission-history">
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

        <section className="mission-card mission-wide" aria-labelledby="mission-comparison">
          <h2 id="mission-comparison">{M.comparisonHeading}</h2>
          {state.compareJob ? <p className="hint" aria-live="polite">{state.compareJob.message}</p>
            : cmp ? <p className="hint">{M.comparisonReady(cmp.sites.length, cmp.windows.length)}</p>
            : <p className="hint">{M.comparisonNone}</p>}
          {state.compareError && <p className="hint bad">{state.compareError}</p>}
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
