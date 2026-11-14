import * as d3 from "d3";
import { useMemo, useState } from "react";
import type { Result } from "../api/types";
import { S, timeLocale } from "../i18n";
import { fmtFraction, fmtUTC } from "../lib/format";
import { useWidth } from "../lib/useWidth";

// Phase 5 prompt 3: the calculated visible share of the Sun's disc and of Earth's disc at every display step
// (result.series.sun.f / earth.f), as two separate panels on one time axis, so sunlight and Earth visibility are never
// confused. Missing values (null) are drawn as hatched gaps, never interpolated across.

interface Props { result: Result; cursor: number; onCursor: (i: number) => void }
const V = S.viz;
const COLORS = { sun: "#f2b544", earth: "#5fa8e8", unknown: "#ee9a6b", grid: "#2a3a4b", axis: "#a3b1bf", ink: "#e7ecf1", cursor: "#ffd98a" };

export function VisibilityChart({ result, cursor, onCursor }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const W = Math.max(320, width);
  const m = { l: 56, r: 12, t: 10, b: 30 };
  const panelH = 92, gap = 26;
  const H = m.t + 2 * panelH + gap + m.b;
  const s = result.series;
  const t0 = new Date(result.window.start_utc).getTime(), t1 = new Date(result.window.end_utc).getTime();
  const ms = (i: number) => t0 + (s.et[i] - result.window.start_et) * 1000;

  const geom = useMemo(() => {
    const x = d3.scaleUtc().domain([t0, t1]).range([m.l, W - m.r]);
    const panels = (["sun", "earth"] as const).map((body, k) => {
      const top = m.t + k * (panelH + gap);
      const y = d3.scaleLinear().domain([0, 100]).range([top + panelH, top]);
      const vals = s[body].f;
      const idx = d3.range(vals.length);
      const def = (i: number) => vals[i] != null && Number.isFinite(vals[i] as number);
      const area = d3.area<number>().defined(def).x((i) => x(ms(i))).y0(top + panelH).y1((i) => y(100 * (vals[i] as number)))
        .curve(d3.curveStepAfter)(idx) ?? "";
      const line = d3.line<number>().defined(def).x((i) => x(ms(i))).y((i) => y(100 * (vals[i] as number)))
        .curve(d3.curveStepAfter)(idx) ?? "";
      // runs of unknown values (half a step either side, so a single missing sample stays visible)
      const gaps: [number, number][] = [];
      let a = -1;
      vals.forEach((v, i) => {
        const miss = v == null || !Number.isFinite(v);
        if (miss && a < 0) a = i;
        if (!miss && a >= 0) { gaps.push([a, i - 1]); a = -1; }
      });
      if (a >= 0) gaps.push([a, vals.length - 1]);
      return { body, top, y, area, line, gaps };
    });
    return { x, panels };
  }, [result, W]); // eslint-disable-line react-hooks/exhaustive-deps

  const { x } = geom;
  const half = (s.step_s * 1000) / 2;
  const tickFormat = timeLocale.utcFormat(S.timeline.tickFormat);
  const idxAt = (clientX: number, svg: SVGSVGElement) => {
    const r = svg.getBoundingClientRect();
    const t = x.invert(((clientX - r.left) / r.width) * W).getTime();
    const et = result.window.start_et + (t - t0) / 1000;
    return Math.max(0, Math.min(s.et.length - 1, d3.bisectLeft(s.et, et)));
  };
  const hi = hover ?? cursor;
  const readout = V.visHover(fmtUTC(s.utc[hi]), fmtFraction(s.sun.f[hi]), fmtFraction(s.earth.f[hi]));

  return (
    <div className="vis-chart" ref={ref}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={V.visLabel}
           onClick={(e) => onCursor(idxAt(e.clientX, e.currentTarget))}
           onMouseMove={(e) => setHover(idxAt(e.clientX, e.currentTarget))}
           onMouseLeave={() => setHover(null)}>
        <defs>
          <pattern id="vis-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="6" stroke={COLORS.unknown} strokeWidth="1.4" />
          </pattern>
        </defs>
        {geom.panels.map((p) => (
          <g key={p.body}>
            <rect x={m.l} y={p.top} width={W - m.l - m.r} height={panelH} fill="#1e2a37" />
            {[0, 50, 100].map((v) => (
              <g key={v}>
                <line x1={m.l} x2={W - m.r} y1={p.y(v)} y2={p.y(v)} stroke={COLORS.grid} strokeDasharray={v === 0 ? "" : "2 4"} />
                <text x={m.l - 6} y={p.y(v) + 4} textAnchor="end" fontSize="11" fill={COLORS.axis}>{S.format.percent(String(v))}</text>
              </g>
            ))}
            <path d={p.area} fill={COLORS[p.body]} fillOpacity={0.28} />
            <path d={p.line} fill="none" stroke={COLORS[p.body]} strokeWidth={1.6} />
            {p.gaps.map(([a, b]) => (
              <rect key={a} x={x(ms(a) - half)} y={p.top} height={panelH} fill="url(#vis-hatch)" opacity={0.7}
                    width={Math.max(2, x(ms(b) + half) - x(ms(a) - half))}><title>{V.visUnknown}</title></rect>
            ))}
            <text x={m.l + 6} y={p.top + 14} fontSize="12" fontWeight={600} fill={COLORS[p.body]}>{p.body === "sun" ? V.visSun : V.visEarth}</text>
          </g>
        ))}
        <text x={14} y={m.t + panelH + gap / 2} fontSize="11" fill={COLORS.axis} textAnchor="middle"
              transform={`rotate(-90 14 ${m.t + panelH + gap / 2})`}>{V.visAxis}</text>
        {x.ticks(Math.max(3, Math.floor(W / 140))).map((t) => (
          <g key={t.getTime()}>
            <line x1={x(t)} x2={x(t)} y1={H - m.b} y2={H - m.b + 4} stroke={COLORS.axis} />
            <text x={x(t)} y={H - 12} textAnchor="middle" fontSize="11" fill={COLORS.axis}>{tickFormat(t)}</text>
          </g>
        ))}
        <text x={W - m.r} y={H - 1} textAnchor="end" fontSize="10.5" fill={COLORS.axis}>{V.timeAxis}</text>
        <line x1={x(ms(cursor))} x2={x(ms(cursor))} y1={m.t - 4} y2={H - m.b} stroke={COLORS.cursor} strokeWidth={1.5} />
        {hover != null && <line x1={x(ms(hover))} x2={x(ms(hover))} y1={m.t} y2={H - m.b} stroke={COLORS.ink} strokeOpacity={0.35} />}
      </svg>
      <p className="vis-readout" aria-hidden>{readout}</p>
      <p className="hint">{V.visNote}</p>
    </div>
  );
}
