import { Suspense, lazy, useMemo, useState } from "react";
import type { CompareCell } from "../api/types";
import { S } from "../i18n";
import { PANEL_NAMES, RULE_NAMES, fmtDuration, fmtNum, fmtPct, fmtUTC, fromInputValue, isoNoMs, toInputValue } from "../lib/format";
import { useStore } from "../state/store";
import { Metric } from "../ui/Metric";
import { SectionHeader } from "../ui/SectionHeader";
import { ViewHeader } from "../ui/ViewHeader";
import type { ChartMetric } from "./CompareCharts";

// LUNA-OPS 2.0 Phase 3: the comparison workspace. The builder (sites and date windows) and the run are unchanged; the
// results show the sites side by side for one window, the matrix (bars, better/worse shading and label counts as
// before), a bar chart of the chosen metric and a sunlit-against-Earth-in-view scatter. Every number is a field of a
// cell's own calculated result (cells[*].summary); nothing is combined into a score.

const CompareCharts = lazy(() => import("./CompareCharts").then((m) => ({ default: m.CompareCharts })));

const SYNODIC_DAYS = 29.530589; // mean synodic month, used only to suggest the next window's dates
const T = S.compare;
const M = T.metrics;
const V = S.viz;
const OBSERVERS: Record<string, string> = S.observerProfiles;
// metrics measured in percent get an absolute 0-100 bar; the others a bar relative to the table's largest value
const PERCENT_METRICS = new Set(["sunlit", "dte", "overlap"]);
// prefix of the API's validation status word (protocol value, compared only)
const VALIDATED_PREFIX = "Validated";

const METRICS: { id: string; label: string; get: (c: CompareCell, sr: string, dr: string, pm: string) => number | null;
                 fmt: (v: number | null) => string; higherIsBetter: boolean }[] = [
  { id: "sunlit", label: M.sunlit, get: (c, sr) => c.summary?.[`sun_${sr}`]?.percent ?? null, fmt: (v) => fmtPct(v), higherIsBetter: true },
  { id: "dark", label: M.dark, get: (c, sr) => c.summary?.[`sun_${sr}`]?.longest_gap_h ?? null, fmt: fmtDuration, higherIsBetter: false },
  { id: "dte", label: M.dte, get: (c, _s, dr) => c.summary?.[`earth_${dr}`]?.percent ?? null, fmt: (v) => fmtPct(v), higherIsBetter: true },
  { id: "dtegap", label: M.dtegap, get: (c, _s, dr) => c.summary?.[`earth_${dr}`]?.longest_gap_h ?? null, fmt: fmtDuration, higherIsBetter: false },
  { id: "overlap", label: M.overlap, get: (c) => c.summary?.overlap?.percent ?? null, fmt: (v) => fmtPct(v), higherIsBetter: true },
  { id: "power", label: M.power, get: (c, _s, _d, pm) => c.summary?.power?.[pm]?.mean ?? null, fmt: (v) => fmtNum(v, 3), higherIsBetter: true },
  { id: "efsh", label: M.efsh, get: (c, _s, _d, pm) => c.summary?.power?.[pm]?.equivalent_full_sun_h ?? null, fmt: fmtDuration, higherIsBetter: true },
];
const metricById = (id: string) => METRICS.find((m) => m.id === id) ?? METRICS[0];

export function CompareView() {
  const { state, dispatch, runComparison, openResult } = useStore();
  const s = state.settings;
  const sites = state.compareSites;
  const wins = state.compareWindows;
  const setWins = (w: typeof wins) => dispatch({ type: "compareWindows", windows: w });
  const [cardWin, setCardWin] = useState(0);

  const addCurrentWindow = () => setWins([...wins, { start: s.start, end: s.end, label: T.windowLabel(wins.length + 1) }]);
  const addNextMonth = () => {
    const base = wins.length ? wins[wins.length - 1] : { start: s.start, end: s.end };
    const shift = SYNODIC_DAYS * 86400_000;
    const st = new Date(new Date(base.start).getTime() + shift);
    const en = new Date(new Date(base.end).getTime() + shift);
    setWins([...wins, { start: isoNoMs(st), end: isoNoMs(en), label: T.windowLabel(wins.length + 1) }]);
  };
  const metric = metricById(state.compareMetric);
  const cmp = state.comparison;
  const sr = cmp?.base.sunlit_rule ?? s.sunlitRule, dr = cmp?.base.dte_rule ?? s.dteRule, pm = cmp?.base.panel_model ?? s.panel;

  const range = useMemo(() => {
    if (!cmp) return [0, 1];
    const vals = cmp.cells.map((c) => metric.get(c, sr, dr, pm)).filter((v): v is number => v != null && isFinite(v));
    return vals.length ? [Math.min(...vals), Math.max(...vals)] : [0, 1];
  }, [cmp, metric, sr, dr, pm]);

  const barPct = (v: number | null) => {
    if (v == null || !isFinite(v)) return 0;
    if (PERCENT_METRICS.has(metric.id)) return Math.max(0, Math.min(100, v));
    return range[1] > 0 ? Math.max(0, Math.min(100, (100 * v) / range[1])) : 0;
  };
  const labelCounts = (cell: CompareCell) => {
    const l = Object.values(cell.labels ?? {});
    const ok = l.filter((x) => x.validation.startsWith(VALIDATED_PREFIX)).length;
    return { ok, pending: l.length - ok, n: l.length };
  };
  const shade = (v: number | null) => {
    if (v == null) return "transparent";
    const [lo, hi] = range;
    let t = hi > lo ? (v - lo) / (hi - lo) : 0.5;
    if (!metric.higherIsBetter) t = 1 - t;
    return `rgba(242, 181, 68, ${0.06 + 0.3 * t})`;
  };

  const busy = !!state.compareJob;
  const nW = cmp?.windows.length ?? 0;
  const win = Math.min(cardWin, Math.max(0, nW - 1));
  const siteName = (si: number) => { const x = cmp?.sites[si]; return x ? (x.name ?? T.siteCoords(x.lat.toFixed(3), x.lon.toFixed(3))) : ""; };
  const windowName = (wi: number) => T.windowShort(wi + 1);
  const chartMetric: ChartMetric = { id: metric.id, label: metric.label, get: (c) => metric.get(c, sr, dr, pm), fmt: metric.fmt,
    percent: PERCENT_METRICS.has(metric.id) };
  const base = cmp?.base ?? {};

  return (
    <div className="compare">
      <ViewHeader eyebrow={S.shell.eyebrows.compare} title={T.title}
                  subtitle={T.intro(RULE_NAMES[s.sunlitRule].toLowerCase(), RULE_NAMES[s.dteRule].toLowerCase())} />
      <div className="compare-builder">
        <section aria-labelledby="cmp-sites-h">
          <h2 id="cmp-sites-h" className="builder-head">{T.sitesHeading(sites.length)}</h2>
          {sites.length === 0 && <p className="empty-note">{T.noSites(S.sidebar.addToCompare)}</p>}
          <ul className="list-edit">
            {sites.map((x, k) => (
              <li key={k}><span>{x.name} <span className="hint mono">{S.format.coordPair(x.lat.toFixed(4), x.lon.toFixed(4))}</span></span>
                <button className="quiet-button" onClick={() => dispatch({ type: "compareSites", sites: sites.filter((_, j) => j !== k) })}
                        aria-label={T.removeSite(x.name)}>{S.common.remove}</button></li>
            ))}
          </ul>
          {state.catalog.length > 0 && (
            <details className="builder-more">
              <summary className="hint">{T.addCurated}</summary>
              <ul className="list-edit">
                {state.catalog.map((c) => (
                  <li key={c.id}><span>{c.name}</span>
                    <button className="quiet-button" disabled={sites.some((x) => x.id === c.id)}
                            onClick={() => dispatch({ type: "compareSites", sites: [...sites, { lat: c.lat, lon: c.lon, name: c.name, id: c.id }] })}>{S.common.add}</button></li>
                ))}
              </ul>
            </details>
          )}
        </section>
        <section aria-labelledby="cmp-windows-h">
          <h2 id="cmp-windows-h" className="builder-head">{T.windowsHeading(wins.length)}</h2>
          <ul className="list-edit">
            {wins.map((w, k) => (
              <li key={k} className="window-row">
                <input type="datetime-local" aria-label={T.windowStart(k + 1)} value={toInputValue(w.start)}
                       onChange={(e) => setWins(wins.map((x, j) => (j === k ? { ...x, start: fromInputValue(e.target.value) } : x)))} />
                <input type="datetime-local" aria-label={T.windowEnd(k + 1)} value={toInputValue(w.end)}
                       onChange={(e) => setWins(wins.map((x, j) => (j === k ? { ...x, end: fromInputValue(e.target.value) } : x)))} />
                <button className="quiet-button" onClick={() => setWins(wins.filter((_, j) => j !== k))} aria-label={T.removeWindow(k + 1)}>{S.common.remove}</button>
              </li>
            ))}
          </ul>
          <div className="builder-actions">
            <button className="quiet-button" onClick={addCurrentWindow}>{T.addPanelDates}</button>
            <button className="quiet-button" onClick={addNextMonth}>{T.addNextMonth}</button>
          </div>
        </section>
      </div>
      <div className="compare-run">
        <button className="run-button" disabled={!sites.length || !wins.length || busy}
                onClick={() => runComparison()}>{busy ? T.comparing : T.run(sites.length, wins.length)}</button>
        {state.compareJob && <span className="hint" aria-live="polite">{state.compareJob.message}</span>}
        {state.compareError && <span className="hint bad" role="alert">{state.compareError}</span>}
        <span className="sr-only" role="status">{!busy && cmp ? T.ready(cmp.sites.length, cmp.windows.length) : ""}</span>
      </div>

      {cmp && (
        <>
          <p className="compare-provenance">
            {T.provenance(RULE_NAMES[sr] ?? sr, RULE_NAMES[dr] ?? dr, PANEL_NAMES[pm] ?? pm,
              OBSERVERS[base.observer_profile] ?? String(base.observer_profile ?? S.common.na),
              base.observer_h_m != null ? Number(base.observer_h_m).toFixed(1) : S.common.na,
              base.step_s != null ? (Number(base.step_s) / 60).toFixed(0) : S.common.na)}
          </p>

          <section className="section ws-section" aria-labelledby="cmp-cards-h">
            <SectionHeader id="cmp-cards-h" eyebrow={T.eyebrowCards} title={T.cardsHeading}
                           actions={nW > 1 ? (
                             <div className="segmented-mini" role="group" aria-label={T.windowPick}>
                               {cmp.windows.map((w: any, wi: number) => (
                                 <button key={wi} type="button" aria-pressed={wi === win} onClick={() => setCardWin(wi)}
                                         title={T.windowRange(fmtUTC(w.start_utc), fmtUTC(w.end_utc))}>{windowName(wi)}</button>
                               ))}
                             </div>) : undefined} />
            <p className="hint">{T.cardsWindow(fmtUTC(cmp.windows[win].start_utc), fmtUTC(cmp.windows[win].end_utc))}</p>
            <ul className="site-cards">
              {cmp.sites.map((_site: any, si: number) => {
                const cell = cmp.cells[si * nW + win];
                const sum = cell?.summary;
                const sun = sum?.[`sun_${sr}`], earth = sum?.[`earth_${dr}`], ov = sum?.overlap, pw = sum?.power?.[pm];
                const lc = cell ? labelCounts(cell) : null;
                return (
                  <li key={si} className="site-card">
                    <h3>{siteName(si)}</h3>
                    <p className="hint mono">{T.siteCoords(cmp.sites[si].lat.toFixed(4), cmp.sites[si].lon.toFixed(4))}</p>
                    {!cell || cell.error || !sum ? (
                      <p className="cell-unavailable">{cell?.error ? T.cardUnavailable(cell.error) : T.unavailable}</p>
                    ) : (
                      <>
                        <dl className="metrics compact">
                          <Metric label={M.sunlit} value={fmtPct(sun?.percent)} state={sun?.percent == null ? "unknown" : undefined} />
                          <Metric label={M.dte} value={fmtPct(earth?.percent)} state={earth?.percent == null ? "unknown" : undefined} />
                          <Metric label={M.overlap} value={fmtPct(ov?.percent)} state={ov?.percent == null ? "unknown" : undefined} />
                          <Metric label={M.dark} value={fmtDuration(sun?.longest_gap_h)} />
                          <Metric label={M.dtegap} value={fmtDuration(earth?.longest_gap_h)} />
                          <Metric label={M.power} value={fmtNum(pw?.mean, 3)} note={PANEL_NAMES[pm]} />
                          <Metric label={S.figures.unknown} value={fmtDuration(sun?.unknown_hours)} state={sun?.unknown_hours > 0 ? "flag" : undefined} />
                        </dl>
                        {lc && lc.n > 0 && <p className="card-labels">{V.cellLabels(lc.ok, lc.pending)}</p>}
                        {cell.result_id && <button type="button" className="quiet-button" onClick={() => openResult(cell.result_id!)}>{T.cardOpen}</button>}
                      </>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>

          <section className="section ws-section" aria-label={T.matrixRegion}>
            <SectionHeader id="cmp-matrix-h" eyebrow={T.eyebrowMatrix} title={T.matrixHeading}
                           actions={<a className="quiet-button" href={`/api/compare/${cmp.id}/compare.csv`} download>{T.csv}</a>} />
            <div className="segmented segmented-wrap metric-switch" role="group" aria-label={T.metricLabel}>
              {METRICS.map((m) => (
                <button key={m.id} aria-pressed={metric.id === m.id} onClick={() => dispatch({ type: "compareMetric", metric: m.id })}>{m.label}</button>
              ))}
            </div>
            <div className="matrix-scroll">
              <table className="matrix">
                <caption className="sr-only">{T.caption(metric.label)}</caption>
                <thead>
                  <tr><th scope="col">{T.siteColumn}</th>
                    {cmp.windows.map((w: any, k: number) => <th key={k} scope="col"><span className="matrix-win">{windowName(k)}</span>{fmtUTC(w.start_utc)}<br />{T.windowTo(fmtUTC(w.end_utc))}</th>)}</tr>
                </thead>
                <tbody>
                  {cmp.sites.map((site: any, si: number) => (
                    <tr key={si}>
                      <th scope="row">{site.name ?? T.siteCoords(site.lat.toFixed(3), site.lon.toFixed(3))}</th>
                      {cmp.windows.map((_w: any, wi: number) => {
                        const cell = cmp.cells[si * cmp.windows.length + wi];
                        const v = cell ? metric.get(cell, sr, dr, pm) : null;
                        return (
                          <td key={wi} style={{ background: shade(v) }}>
                            {cell?.error ? <span className="cell-sub" style={{ color: "var(--alert)" }}>{cell.error}</span>
                              : cell?.result_id ? (
                                <button type="button" className="cell-open" onClick={() => openResult(cell.result_id!)}>
                                  {metric.fmt(v)}
                                  <span className="cell-bar" aria-hidden><span style={{ width: `${barPct(v)}%` }} /></span>
                                  {labelCounts(cell).n > 0 && <span className="cell-sub">{V.cellLabels(labelCounts(cell).ok, labelCounts(cell).pending)}</span>}
                                  <span className="cell-sub">{T.openResult}</span>
                                </button>)
                              : metric.fmt(v)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="compare-legend">
              <span className="shade-scale" aria-hidden><i /></span>
              <span>{V.shadeScale(metric.fmt(metric.higherIsBetter ? range[0] : range[1]), metric.fmt(metric.higherIsBetter ? range[1] : range[0]))}
                {" "}({metric.higherIsBetter ? V.betterHigh : V.betterLow})</span>
            </div>
            <p className="hint">{T.shadingHint}</p>
            <p className="hint">{V.compareNote}</p>
          </section>

          <section className="section ws-section" aria-labelledby="cmp-charts-h">
            <SectionHeader id="cmp-charts-h" eyebrow={T.eyebrowCharts} title={T.chartsHeading} />
            <Suspense fallback={<p className="hint">{T.chartsLoading}</p>}>
              <CompareCharts cmp={cmp} metric={chartMetric} siteName={siteName} windowName={windowName}
                             sunlit={(c) => metricById("sunlit").get(c, sr, dr, pm)} earth={(c) => metricById("dte").get(c, sr, dr, pm)} sr={sr} dr={dr} />
            </Suspense>
          </section>
        </>
      )}
      <div className="footer-space" />
    </div>
  );
}
