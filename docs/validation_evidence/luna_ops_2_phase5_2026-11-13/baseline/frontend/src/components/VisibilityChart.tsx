import * as d3 from "d3";
import { useMemo, useRef, useState } from "react";
import type { EventItem, Interval, Result } from "../api/types";
import { S } from "../i18n";
import { RULE_NAMES, fmtDeg, fmtDuration, fmtFraction, fmtUTC } from "../lib/format";
import { runs, timeAxis } from "../lib/timeAxis";
import { useWidth } from "../lib/useWidth";
import { ChartLegend, type ChartLegendItem } from "../ui/ChartLegend";
import { ChartTooltip } from "../ui/ChartTooltip";
import { intervalNotes } from "./Timeline";

// LUNA-OPS 2.0 Phase 3: one body's visibility over the window (used twice: Sun and Earth). Everything is read from the
// result: the calculated visible share of the disc at every display step (series.*.f), the rule's intervals with their
// flags (intervals[...]), and the rise/set events (events, by target). Missing values are hatched gaps, never
// interpolated; unknown intervals are hatched in the band; uncertain intervals keep their dashed edge.

export type Body = "sun" | "earth";
interface Props { result: Result; body: Body; cursor: number; onCursor: (i: number) => void }

const A = S.analysis;
const V = S.viz;
const COLORS = { sun: "#f2b544", earth: "#5fa8e8", unknown: "#ee9a6b", grid: "#2a3a4b", axis: "#a3b1bf", ink: "#e7ecf1", cursor: "#ffd98a",
  off: "#1b2633", plot: "#141e29", contact: "#cfe6fb" };

/** The interval containing an ET (intervals are sorted and contiguous), or null. */
export function intervalAt(ivs: Interval[], et: number): Interval | null {
  const k = d3.bisectRight(ivs.map((iv) => iv.start_et), et) - 1;
  return k >= 0 && et <= ivs[k].end_et ? ivs[k] : null;
}
const stateText = (s: boolean | null) => (s === null ? V.stateUnknown : s ? V.stateOn : V.stateOff);

export function VisibilityChart({ result, body, cursor, onCursor }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<{ i: number; px: number; py: number } | null>(null);
  const raf = useRef(0);
  const W = Math.max(320, width);
  const m = { l: 52, r: 14, t: 6, b: 34 };
  const bandH = 16, evH = 16, plotH = 150;
  const bandY = m.t, evY = bandY + bandH + 4, plotTop = evY + evH + 14;
  const H = plotTop + plotH + m.b;
  const s = result.series;
  const rules = result.provenance.parameters.rules;
  const key = body === "sun" ? `sun_${rules.sunlit}` : `earth_${rules.dte}`;
  const ivs = result.intervals[key] ?? [];
  const color = COLORS[body];

  const geom = useMemo(() => {
    const ax = timeAxis(result, m.l, W - m.r);
    const y = d3.scaleLinear().domain([0, 100]).range([plotTop + plotH, plotTop]);
    const vals = s[body].f;
    const idx = d3.range(vals.length);
    const def = (i: number) => vals[i] != null && Number.isFinite(vals[i] as number);
    const area = d3.area<number>().defined(def).x((i) => ax.x(ax.msOf(i))).y0(plotTop + plotH).y1((i) => y(100 * (vals[i] as number)))
      .curve(d3.curveStepAfter)(idx) ?? "";
    const line = d3.line<number>().defined(def).x((i) => ax.x(ax.msOf(i))).y((i) => y(100 * (vals[i] as number)))
      .curve(d3.curveStepAfter)(idx) ?? "";
    const gaps = runs(vals.length, (i) => !def(i));
    const events = result.events.filter((e) => e.target === body && e.function !== "ecl_contact");
    const contacts = body === "sun" ? result.events.filter((e) => e.function === "ecl_contact") : [];
    return { ax, y, area, line, gaps, events, contacts };
  }, [result, body, W]); // eslint-disable-line react-hooks/exhaustive-deps

  const { ax, y } = geom;
  const x = (ms: number) => ax.x(ms);
  const half = (s.step_s * 1000) / 2;
  const hi = hover?.i ?? cursor;
  const label = body === "sun" ? V.visSun : V.visEarth;
  const readout = A.visReadout(fmtUTC(s.utc[hi]), label, fmtFraction(s[body].f[hi]));
  const iv = intervalAt(ivs, s.et[hi]);
  const marker = (ev: EventItem, k: number) => {
    const cx = x(ax.etToMs(ev.et)), up = ev.direction > 0;
    const d = up ? `M${cx - 5},${evY + evH - 3} L${cx},${evY + 3} L${cx + 5},${evY + evH - 3} Z` : `M${cx - 5},${evY + 3} L${cx},${evY + evH - 3} L${cx + 5},${evY + 3} Z`;
    return <path key={k} d={d} fill={up ? color : COLORS.off} stroke={color} strokeWidth={1.2}><title>{A.eventTitle(ev.name, fmtUTC(ev.utc, true))}</title></path>;
  };
  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const svg = e.currentTarget, cx = e.clientX, cy = e.clientY;
    cancelAnimationFrame(raf.current);
    raf.current = requestAnimationFrame(() => {
      const b = svg.getBoundingClientRect();
      setHover({ i: ax.idxAtClientX(cx, svg, W), px: cx - b.left, py: cy - b.top });
    });
  };
  const legend: ChartLegendItem[] = [
    { swatch: "fill", color, text: A.lgVisible },
    { swatch: "hatch", color: COLORS.unknown, text: A.lgNoValue },
    { swatch: "band", color, text: body === "sun" ? A.lgBandSunlit : A.lgBandEarth },
    { swatch: "band", color: COLORS.off, text: body === "sun" ? A.lgBandDark : A.lgBandOut },
    { swatch: "outline-dashed", color: COLORS.unknown, text: V.tlUncertain },
    { swatch: "rise", color, text: body === "sun" ? A.lgSunRise : A.lgEarthRise },
    { swatch: "set", color, text: body === "sun" ? A.lgSunSet : A.lgEarthSet },
    ...(geom.contacts.length ? [{ swatch: "contact", color: COLORS.contact, text: V.tlEclipse } as ChartLegendItem] : []),
    { swatch: "cursor", color: COLORS.cursor, text: V.tlCursor },
  ];

  return (
    <div className={`vis-chart vis-${body}`} ref={ref}>
      <div className="chart-box">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={body === "sun" ? A.sunChartLabel : A.earthChartLabel}
             onClick={(e) => onCursor(ax.idxAtClientX(e.clientX, e.currentTarget, W))}
             onMouseMove={onMove}
             onMouseLeave={() => { cancelAnimationFrame(raf.current); setHover(null); }}>
          <defs>
            <pattern id={`vis-hatch-${body}`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <line x1="0" y1="0" x2="0" y2="6" stroke={COLORS.unknown} strokeWidth="1.4" />
            </pattern>
          </defs>
          {/* interval band: the rule's intervals (on, off, unknown, uncertain) */}
          <text x={m.l - 6} y={bandY + bandH - 4} textAnchor="end" fontSize="10.5" fill={COLORS.axis}>{A.bandAxis}</text>
          <rect x={m.l} y={bandY} width={W - m.l - m.r} height={bandH} fill={COLORS.off} />
          {ivs.map((v, k) => {
            const xa = x(ax.etToMs(v.start_et)), w = Math.max(1, x(ax.etToMs(v.end_et)) - xa);
            if (v.state === false && !v.uncertain) return null;
            return (
              <rect key={k} x={xa} y={bandY} width={w} height={bandH}
                    fill={v.state === null ? `url(#vis-hatch-${body})` : v.state ? color : COLORS.off} fillOpacity={v.state ? 0.9 : 1}
                    stroke={v.uncertain ? COLORS.unknown : "none"} strokeDasharray={v.uncertain ? "3 2" : undefined} />
            );
          })}
          {/* events of this body (rise and set) and, for the Sun, Earth-Sun contacts */}
          <text x={m.l - 6} y={evY + evH - 4} textAnchor="end" fontSize="10.5" fill={COLORS.axis}>{A.eventsAxis}</text>
          {geom.events.map(marker)}
          {geom.contacts.map((ev, k) => (
            <line key={`c${k}`} x1={x(ax.etToMs(ev.et))} x2={x(ax.etToMs(ev.et))} y1={evY} y2={plotTop + plotH} stroke={COLORS.contact}
                  strokeDasharray="1 3"><title>{A.eventTitle(ev.name, fmtUTC(ev.utc, true))}</title></line>
          ))}
          {/* visible share of the disc */}
          <rect x={m.l} y={plotTop} width={W - m.l - m.r} height={plotH} fill={COLORS.plot} />
          {[0, 25, 50, 75, 100].map((v) => (
            <g key={v}>
              <line x1={m.l} x2={W - m.r} y1={y(v)} y2={y(v)} stroke={COLORS.grid} strokeDasharray={v === 0 ? "" : "2 4"} />
              {v % 50 === 0 && <text x={m.l - 6} y={y(v) + 4} textAnchor="end" fontSize="11" fill={COLORS.axis}>{S.format.percent(String(v))}</text>}
            </g>
          ))}
          <path d={geom.area} fill={color} fillOpacity={0.26} />
          <path d={geom.line} fill="none" stroke={color} strokeWidth={1.6} />
          {geom.gaps.map(([a, b]) => (
            <rect key={a} x={x(ax.msOf(a) - half)} y={plotTop} height={plotH} fill={`url(#vis-hatch-${body})`} opacity={0.7}
                  width={Math.max(2, x(ax.msOf(b) + half) - x(ax.msOf(a) - half))}><title>{V.visUnknown}</title></rect>
          ))}
          <text x={14} y={plotTop + plotH / 2} fontSize="11" fill={COLORS.axis} textAnchor="middle"
                transform={`rotate(-90 14 ${plotTop + plotH / 2})`}>{V.visAxis}</text>
          {ax.ticks().map((t) => (
            <g key={t.getTime()}>
              <line x1={x(t.getTime())} x2={x(t.getTime())} y1={plotTop + plotH} y2={plotTop + plotH + 4} stroke={COLORS.axis} />
              <text x={x(t.getTime())} y={H - 14} textAnchor="middle" fontSize="11" fill={COLORS.axis}>{ax.tickFormat(t)}</text>
            </g>
          ))}
          <text x={W - m.r} y={H - 1} textAnchor="end" fontSize="10.5" fill={COLORS.axis}>{V.timeAxis}</text>
          <line x1={x(ax.msOf(cursor))} x2={x(ax.msOf(cursor))} y1={bandY - 2} y2={plotTop + plotH} stroke={COLORS.cursor} strokeWidth={1.5} />
          {hover && <line x1={x(ax.msOf(hover.i))} x2={x(ax.msOf(hover.i))} y1={bandY} y2={plotTop + plotH} stroke={COLORS.ink} strokeOpacity={0.4} />}
        </svg>
        {hover && (
          <ChartTooltip x={hover.px} y={hover.py} boxWidth={(ref.current?.clientWidth ?? W)}>
            <strong>{fmtUTC(s.utc[hover.i])}</strong>
            <dl>
              <div><dt>{label}</dt><dd>{fmtFraction(s[body].f[hover.i])}</dd></div>
              <div><dt>{A.tipElevation}</dt><dd>{fmtDeg(s[body].el[hover.i])}</dd></div>
              <div><dt>{A.tipAzimuth}</dt><dd>{fmtDeg(s[body].az[hover.i], 1)}</dd></div>
              <div><dt>{A.tipClearance}</dt><dd>{fmtDeg(s[body].c[hover.i])}</dd></div>
              {iv && <div><dt>{A.tipInterval}</dt><dd>{A.tipIntervalValue(stateText(iv.state), fmtDuration(iv.duration_h))}</dd></div>}
              {iv && <div><dt>{A.tipFrom}</dt><dd>{A.tipSpan(fmtUTC(iv.start_utc), fmtUTC(iv.end_utc))}</dd></div>}
              {iv && intervalNotes(iv) && <div><dt>{A.tipFlags}</dt><dd>{intervalNotes(iv)}</dd></div>}
            </dl>
          </ChartTooltip>
        )}
      </div>
      <p className="vis-readout" aria-hidden>{readout}</p>
      <ChartLegend items={legend} label={A.legendLabel} />
      <p className="hint">{body === "sun" ? A.sunNote(RULE_NAMES[rules.sunlit].toLowerCase()) : A.earthNote(RULE_NAMES[rules.dte].toLowerCase())}</p>
    </div>
  );
}
