import { Suspense, lazy, useMemo, useState } from "react";
import type { Result } from "../api/types";
import { S, rich } from "../i18n";
import { cursorEt, nextChange } from "../lib/countdown";
import { PANEL_NAMES, RULE_NAMES, fmtCountdown, fmtDeg, fmtDuration, fmtFraction, fmtNum, fmtPct, fmtUTC } from "../lib/format";
import { timeAxis } from "../lib/timeAxis";
import { useStore } from "../state/store";
import { Icon } from "../ui/Icon";
import { Metric } from "../ui/Metric";
import { SectionHeader } from "../ui/SectionHeader";
import { StatusBadge } from "../ui/StatusBadge";
import { ViewHeader } from "../ui/ViewHeader";
import { EventList } from "./EventList";
import { HorizonPanorama } from "./HorizonPanorama";
import { DataKey, SiteContext, ValidationPanel } from "./ResultContext";
import { LabelChips, RESULT_SECTIONS } from "./ResultLabels";
import { Timeline } from "./Timeline";
import { VisibilityChart, type Body } from "./VisibilityChart";

// LUNA-OPS 2.0 Phase 3: the analysis workspace (the Site tab with a result open). Sections: window summary, time
// controls, horizon, events and intervals, sunlight, Earth visibility, terrain, validation and provenance, notes and
// tables. Every value is read from the result object (blueprint C09): summaries, intervals, events, series, horizon,
// labels and provenance. The browser computes no scientific quantity; countdowns and "time from the cursor" are
// differences of served times.

const MapView = lazy(() => import("./MapView").then((m) => ({ default: m.MapView })));
const Terrain3D = lazy(() => import("./Terrain3D").then((m) => ({ default: m.Terrain3D })));

const T = S.site;
const A = S.analysis;
const QUANTITY_NAMES: Record<string, string> = S.quantities;
// Metric style token: a count or duration that deserves attention when it is not zero
const FLAG = "flag" as const;

function PaneLoading({ text }: { text: string }) {
  return <div className="pane-body"><div className="pane-empty is-loading">{text}</div></div>;
}

/** The validation words of the labels a figure depends on, as the API states them. */
function LabelStatus({ r, keys }: { r: Result; keys: string[] }) {
  const present = keys.filter((k) => r.labels[k]);
  if (!present.length) return null;
  return (
    <div className="figure-labels">
      {present.map((k) => <StatusBadge key={k} word={r.labels[k].validation} prefix={QUANTITY_NAMES[k] ?? k} />)}
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
    { tone: "sun", ...nextChange(r.intervals[`sun_${p.sunlit}`], et, C.nextSunrise, C.nextSunset) },
    { tone: "sun", ...nextChange(r.intervals["sun_full"], et, C.wholeSunClears, C.terrainCoversSun) },
    { tone: "earth", ...nextChange(r.intervals[`earth_${p.dte}`], et, C.nextEarthrise, C.nextEarthset) },
    { tone: "both", ...nextChange(r.intervals["overlap"], et, C.windowOpens, C.windowCloses) },
  ];
  return (
    <div className="countdowns" aria-label={C.label}>
      {items.map((c) => (
        <div className={`countdown is-${c.tone}`} key={c.label}>
          <div className="k">{c.label}</div>
          <div className="v">{c.seconds == null ? C.notInWindow : C.inTime(fmtCountdown(c.seconds))}</div>
          {c.at && <div className="sub">{fmtUTC(c.at)}</div>}
        </div>
      ))}
    </div>
  );
}

/** The window's main figures (Phase 3: every summary field the API sends, with units and the labels they rest on). */
function Figures({ r }: { r: Result }) {
  const p = r.provenance.parameters;
  const sun = r.summary[`sun_${p.rules.sunlit}`];
  const earth = r.summary[`earth_${p.rules.dte}`];
  const ov = r.summary.overlap;
  const pw = r.summary.power[p.panel.model];
  const F = S.figures;
  const flag = (n: number | undefined) => (n ? FLAG : undefined);
  const count = (n: number | undefined) => (n == null ? S.common.na : String(n));
  return (
    <div className="figures">
      <div className="figure is-sun">
        <h3>{F.sunlight}</h3><div className="rule">{RULE_NAMES[p.rules.sunlit]}</div>
        <div className="big">{fmtPct(sun.percent)}</div>
        <dl className="metrics compact">
          <Metric label={F.sunlitTime} value={fmtDuration(sun.hours)} />
          <Metric label={F.longestDarkness} value={fmtDuration(sun.longest_gap_h)} />
          <Metric label={F.sunlitWindows} value={`${sun.windows}${sun.brief_windows ? F.briefWindows(sun.brief_windows) : ""}`} />
          <Metric label={F.unknown} value={fmtDuration(sun.unknown_hours)} state={sun.unknown_hours > 0 ? "flag" : undefined} />
          <Metric label={A.uncertainWindows} value={count(sun.uncertain_windows)} state={flag(sun.uncertain_windows)} />
        </dl>
        <LabelStatus r={r} keys={["disk_visibility", "events"]} />
      </div>
      <div className="figure is-earth">
        <h3>{F.dte}</h3><div className="rule">{F.dteRule(RULE_NAMES[p.rules.dte])}</div>
        <div className="big">{fmtPct(earth.percent)}</div>
        <dl className="metrics compact">
          <Metric label={F.earthInView} value={fmtDuration(earth.hours)} />
          <Metric label={F.longestWindow} value={fmtDuration(earth.longest_window_h)} />
          <Metric label={F.longestGap} value={fmtDuration(earth.longest_gap_h)} />
          <Metric label={F.unknown} value={fmtDuration(earth.unknown_hours)} state={earth.unknown_hours > 0 ? "flag" : undefined} />
          <Metric label={A.uncertainWindows} value={count(earth.uncertain_windows)} state={flag(earth.uncertain_windows)} />
        </dl>
        <LabelStatus r={r} keys={["disk_visibility", "events"]} />
      </div>
      <div className="figure is-both">
        <h3>{F.overlap}</h3><div className="rule">{F.overlapRule}</div>
        <div className="big">{fmtPct(ov.percent)}</div>
        <dl className="metrics compact">
          <Metric label={F.total} value={fmtDuration(ov.hours)} />
          <Metric label={F.longestWindow} value={fmtDuration(ov.longest_window_h)} />
          <Metric label={F.longestGap} value={fmtDuration(ov.longest_gap_h)} />
          <Metric label={A.windows} value={count(ov.windows)} />
          <Metric label={F.unknown} value={fmtDuration(ov.unknown_hours)} state={ov.unknown_hours > 0 ? "flag" : undefined} />
        </dl>
        <LabelStatus r={r} keys={["disk_visibility", "events"]} />
      </div>
      <div className="figure is-power">
        <h3>{F.power}</h3><div className="rule">{F.powerRule(PANEL_NAMES[p.panel.model].toLowerCase())}</div>
        <div className="big">{fmtNum(pw.mean, 3)}</div>
        <dl className="metrics compact">
          <Metric label={F.equivalentFullSun} value={fmtDuration(pw.equivalent_full_sun_h)} note={pw.lower_bound ? A.lowerBound : undefined}
                  state={pw.lower_bound ? "flag" : undefined} />
          <Metric label={F.meanVisibleSun} value={r.summary.mean_sun_fraction == null ? S.common.na : fmtPct(r.summary.mean_sun_fraction * 100)} />
          <Metric label={A.powerKnown} value={pw.coverage == null ? S.common.na : fmtPct(pw.coverage * 100)} />
          {pw.unknown_hours != null && <Metric label={F.unknown} value={fmtDuration(pw.unknown_hours)} state={pw.unknown_hours > 0 ? "flag" : undefined} />}
        </dl>
        <LabelStatus r={r} keys={["power_indicator"]} />
      </div>
    </div>
  );
}

/** All summary fields of one body's rule, beside its chart. */
function BodyStats({ r, body }: { r: Result; body: Body }) {
  const p = r.provenance.parameters.rules;
  const rule = body === "sun" ? p.sunlit : p.dte;
  const s = r.summary[`${body}_${rule}`];
  if (!s) return null;
  const n = (v: number | undefined) => (v == null ? S.common.na : String(v));
  const flag = (v: number | undefined) => (v ? FLAG : undefined);
  return (
    <aside className={`body-stats is-${body}`} aria-label={A.statsLabel(body === "sun" ? S.common.bodies.sun : S.common.bodies.earth)}>
      <p className="body-stats-rule">{A.ruleLine(RULE_NAMES[rule])}</p>
      <p className="body-stats-big">{fmtPct(s.percent)}<span>{body === "sun" ? A.ofWindowSunlit : A.ofWindowEarth}</span></p>
      <dl className="metrics">
        <Metric label={A.totalTime} value={fmtDuration(s.hours)} />
        <Metric label={A.windows} value={n(s.windows)} note={s.brief_windows ? A.briefNote(s.brief_windows) : undefined} />
        <Metric label={A.longestWindow} value={fmtDuration(s.longest_window_h)} />
        <Metric label={A.longestGap} value={fmtDuration(s.longest_gap_h)} />
        <Metric label={A.transitions} value={n(s.transitions)} />
        <Metric label={A.unknownTime} value={fmtDuration(s.unknown_hours)} state={s.unknown_hours > 0 ? "flag" : undefined} />
        <Metric label={A.uncertainWindows} value={n(s.uncertain_windows)} state={flag(s.uncertain_windows)} />
        <Metric label={A.uncertainGaps} value={n(s.uncertain_gaps)} state={flag(s.uncertain_gaps)} />
        <Metric label={A.nearFieldWindows} value={n(s.near_field_windows)} state={flag(s.near_field_windows)} />
        <Metric label={A.subbinWindows} value={n(s.subbin_peak_windows)} state={flag(s.subbin_peak_windows)} />
        {body === "sun" && <Metric label={S.figures.meanVisibleSun}
                                   value={r.summary.mean_sun_fraction == null ? S.common.na : fmtPct(r.summary.mean_sun_fraction * 100)} />}
      </dl>
      <LabelStatus r={r} keys={["disk_visibility", "events"]} />
    </aside>
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

/** The shared time cursor: play, previous/next event (nearest display step), the slider and the cursor time. */
function TimeBar({ r, i }: { r: Result; i: number }) {
  const { state, dispatch } = useStore();
  const ax = useMemo(() => timeAxis(r, 0, 1), [r]);
  const set = (c: number) => dispatch({ type: "cursor", cursor: c });
  const half = r.series.step_s / 2;
  const et = r.series.et[i];
  // an event counts as "at the cursor" within half a display step, so the buttons always move to a different step
  const prev = [...r.events].reverse().find((e) => e.et < et - half);
  const next = r.events.find((e) => e.et > et + half);
  return (
    <div className="timebar" role="group" aria-label={A.timeBar}>
      <div className="scrubber">
        <button className="play" onClick={() => dispatch({ type: "playing", playing: !state.playing })}
                aria-label={state.playing ? T.pause : T.play}>{state.playing ? T.pauseIcon : T.playIcon}</button>
        <button type="button" className="icon-button event-step" aria-label={prev ? A.prevEventNamed(prev.name) : A.prevEvent}
                title={prev ? A.prevEventNamed(prev.name) : A.prevEvent} disabled={!prev} onClick={() => prev && set(ax.nearestIdx(prev.et))}>
          <Icon name="chevronLeft" /></button>
        <input type="range" min={0} max={r.series.et.length - 1} value={i} aria-label={T.timeCursor}
               aria-valuetext={fmtUTC(r.series.utc[i])}
               onChange={(e) => set(Number(e.target.value))} />
        <button type="button" className="icon-button event-step" aria-label={next ? A.nextEventNamed(next.name) : A.nextEvent}
                title={next ? A.nextEventNamed(next.name) : A.nextEvent} disabled={!next} onClick={() => next && set(ax.nearestIdx(next.et))}>
          <Icon name="chevronRight" /></button>
        <span className="cursor-time">{fmtUTC(r.series.utc[i])}</span>
        <span className="cursor-step">{A.stepLabel((r.series.step_s / 60).toFixed(0))}</span>
      </div>
    </div>
  );
}

const NAV: { id: string; label: string; technical?: boolean }[] = [
  { id: RESULT_SECTIONS.summary, label: A.nav.summary }, { id: RESULT_SECTIONS.panorama, label: A.nav.horizon },
  { id: RESULT_SECTIONS.timeline, label: A.nav.timeline }, { id: RESULT_SECTIONS.visibility, label: A.nav.sunlight },
  { id: RESULT_SECTIONS.earth, label: A.nav.earth }, { id: RESULT_SECTIONS.terrain, label: A.nav.terrain },
  { id: RESULT_SECTIONS.validation, label: A.nav.validation }, { id: RESULT_SECTIONS.tables, label: A.nav.tables, technical: true },
];

export function ResultWorkspace({ r, onPick }: { r: Result; onPick: (lat: number, lon: number) => void }) {
  const { state, dispatch } = useStore();
  const i = Math.min(state.cursor, r.series.et.length - 1);
  const synthetic = r.provenance.terrain.synthetic;
  const setCursor = (c: number) => dispatch({ type: "cursor", cursor: c });
  const technical = state.mode === "technical";
  const go = (id: string) => (e: React.MouseEvent) => { e.preventDefault(); document.getElementById(id)?.scrollIntoView({ block: "start" }); };

  const bodySection = (body: Body) => {
    const id = body === "sun" ? RESULT_SECTIONS.visibility : RESULT_SECTIONS.earth;
    return (
      <section className={`section ws-section vis-section is-${body}`} id={id} aria-labelledby={`${id}-h`}>
        <SectionHeader id={`${id}-h`} eyebrow={body === "sun" ? A.eyebrows.sunlight : A.eyebrows.earth}
                       title={body === "sun" ? A.sunHeading : A.earthHeading} tag={<span className="data-tag calculated">{S.viz.keyCalculated}</span>} />
        <div className="body-grid">
          <BodyStats r={r} body={body} />
          <VisibilityChart result={r} body={body} cursor={i} onCursor={setCursor} />
        </div>
      </section>
    );
  };

  return (
    <div className="workspace-result">
      <ViewHeader eyebrow={S.shell.eyebrows.result} title={r.site.name ?? T.customSite}
        subtitle={T.coords(r.site.lat.toFixed(5), r.site.lon.toFixed(5), r.site.ground_h_m.toFixed(1),
          fmtUTC(r.window.start_utc), fmtUTC(r.window.end_utc))}
        actions={<>
          <button type="button" className="quiet-button" onClick={() => dispatch({ type: "closeResult" })}>{S.explorer.backToExplorer}</button>
          <a className="quiet-button" href={`/api/results/${r.id}/series.csv`} download>{T.downloads.series}</a>
          <a className="quiet-button" href={`/api/results/${r.id}/events.csv`} download>{T.downloads.events}</a>
          <a className="quiet-button" href={`/api/results/${r.id}/intervals.csv`} download>{T.downloads.intervals}</a>
          <a className="quiet-button" href={`/api/results/${r.id}/result.json`} download>{T.downloads.result}</a>
        </>} />
      <div className="result-labels"><LabelChips result={r} /><DataKey /></div>
      <SiteContext r={r} />

      {state.mode === "public" && <PublicSummary r={r} />}

      <nav className="section-nav" aria-label={A.sectionNav}>
        {NAV.filter((n) => technical || !n.technical).map((n) => <a key={n.id} href={`#${n.id}`} onClick={go(n.id)}>{n.label}</a>)}
      </nav>

      <section className="ws-section" id={RESULT_SECTIONS.summary} aria-labelledby="result-summary-h">
        <SectionHeader id="result-summary-h" eyebrow={A.eyebrows.summary} title={A.summaryHeading}
                       tag={<span className="data-tag calculated">{S.viz.keyCalculated}</span>} />
        <Figures r={r} />
      </section>

      <TimeBar r={r} i={i} />
      <Readout r={r} i={i} playing={state.playing} />
      <Countdowns r={r} i={i} />

      <section className="ws-section panorama-wrap" id={RESULT_SECTIONS.panorama} aria-labelledby="result-panorama-h">
        <SectionHeader id="result-panorama-h" eyebrow={A.eyebrows.horizon} title={T.panoramaHeading}
                       tag={<span className="data-tag calculated">{S.viz.keyCalculated}</span>} />
        <HorizonPanorama result={r} cursor={i} />
        <p className="hint">{T.panoramaHint} {A.panoramaObstruction}</p>
      </section>

      <section className="ws-section" id={RESULT_SECTIONS.timeline} aria-labelledby="result-timeline-h">
        <SectionHeader id="result-timeline-h" eyebrow={A.eyebrows.timeline} title={A.timelineHeading}
                       tag={<span className="data-tag calculated">{S.viz.keyCalculated}</span>} />
        <div className="timeline-grid">
          <Timeline result={r} cursor={i} onCursor={setCursor} />
          <EventList result={r} cursor={i} onCursor={setCursor} />
        </div>
      </section>

      {bodySection("sun")}
      {bodySection("earth")}

      <section className="ws-section" id={RESULT_SECTIONS.terrain} aria-labelledby="result-terrain-h">
        <SectionHeader id="result-terrain-h" eyebrow={A.eyebrows.terrain} title={A.terrainHeading}
                       tag={<span className="data-tag measured">{S.viz.keyMeasured}</span>} />
        <div className="grid-2 terrain-grid">
          <section className="pane" aria-label={S.common.mapRegion}>
            <div className="pane-head"><h3>{S.common.southPolarMap}</h3></div>
            <Suspense fallback={<PaneLoading text={S.map.loadingTiles} />}>
              <MapView lat={r.site.lat} lon={r.site.lon} catalog={state.catalog} selectedId={r.site.id} onPick={onPick}
                       instruments candidates={state.compareSites} legendOpen={false} />
            </Suspense>
          </section>
          <section className="pane" aria-label={T.terrainRegion}>
            <div className="pane-head"><h3>{T.terrainHeading}</h3></div>
            <Suspense fallback={<PaneLoading text={S.terrain3d.loading} />}>
              <Terrain3D result={r} cursor={i} />
            </Suspense>
          </section>
        </div>
      </section>

      <section className="ws-section" id={RESULT_SECTIONS.validation} aria-labelledby="result-validation-h">
        <SectionHeader id="result-validation-h" eyebrow={A.eyebrows.validation} title={A.validationHeading} />
        <ValidationPanel r={r} />
      </section>

      <div className="notes">
        {synthetic && <div className="note alert">{T.syntheticAlert}</div>}
        <div className="note radio">{r.geometric_not_radio}</div>
        {r.warnings.map((w, k) => <div className="note alert" key={k}>{w}</div>)}
      </div>

      {technical && <div id={RESULT_SECTIONS.tables} className="ws-tables"><EventsTable r={r} /><SeriesTable r={r} /></div>}
      <div className="footer-space" />
    </div>
  );
}
