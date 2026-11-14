import * as d3 from "d3";
import { useState } from "react";
import type { CompareCell, Comparison } from "../api/types";
import { S } from "../i18n";
import { fmtPct } from "../lib/format";
import { useWidth } from "../lib/useWidth";
import { ChartTooltip } from "../ui/ChartTooltip";

// LUNA-OPS 2.0 Phase 3: the comparison charts (loaded on demand with the Compare tab's results). Both draw only values
// the API returned for each cell (site x window); a cell without a value is listed as Unavailable and never drawn as
// zero. No value is combined with another into a score.

const C = S.compare;
export interface ChartMetric { id: string; label: string; get: (c: CompareCell) => number | null; fmt: (v: number | null) => string; percent: boolean }
interface Props { cmp: Comparison; metric: ChartMetric; sunlit: (c: CompareCell) => number | null; earth: (c: CompareCell) => number | null;
  siteName: (si: number) => string; windowName: (wi: number) => string }

// categorical colours for sites (none is the Sun gold or Earth blue, which keep their meaning elsewhere)
const SITE_COLORS = ["#4cc9d6", "#c79bf2", "#9fd27c", "#f29cc4", "#e9dfb8", "#8fb3d1", "#f0a868", "#7fd6c2"];
const ink = "#e7ecf1", axis = "#a3b1bf", grid = "#2a3a4b";

export function CompareCharts({ cmp, metric, sunlit, earth, siteName, windowName }: Props) {
  return (
    <div className="compare-charts">
      <MetricBars cmp={cmp} metric={metric} siteName={siteName} windowName={windowName} />
      <SunEarthScatter cmp={cmp} sunlit={sunlit} earth={earth} siteName={siteName} windowName={windowName} />
    </div>
  );
}

/** The chosen metric for every site (row group) and window (bar), with its exact value. */
function MetricBars({ cmp, metric, siteName, windowName }: { cmp: Comparison; metric: ChartMetric; siteName: (si: number) => string; windowName: (wi: number) => string }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const W = Math.max(300, width);
  const nW = cmp.windows.length, nS = cmp.sites.length;
  // narrow screens: each site's name sits above its bars instead of beside them
  const stacked = W < 480;
  const barH = 16, barGap = 4, groupGap = 14, labelH = stacked ? 18 : 0;
  const m = { l: stacked ? 8 : Math.min(200, Math.max(110, W * 0.26)), r: stacked ? 72 : 92, t: 6, b: 30 };
  const groupH = labelH + nW * (barH + barGap) - barGap;
  const H = m.t + nS * (groupH + groupGap) - groupGap + m.b;
  const vals = cmp.cells.map((c) => metric.get(c)).filter((v): v is number => v != null && Number.isFinite(v));
  const max = metric.percent ? 100 : Math.max(1e-9, d3.max(vals) ?? 1);
  const x = d3.scaleLinear().domain([0, max]).nice().range([m.l, W - m.r]);
  return (
    <figure className="compare-chart" ref={ref}>
      <figcaption>{C.barHeading(metric.label)}</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={C.barLabel(metric.label)}>
        {x.ticks(stacked ? 3 : 5).map((t) => (
          <g key={t}>
            <line x1={x(t)} x2={x(t)} y1={m.t} y2={H - m.b} stroke={grid} strokeDasharray={t === 0 ? "" : "2 4"} />
            <text x={x(t)} y={H - m.b + 16} textAnchor="middle" fontSize="11" fill={axis}>{metric.percent ? S.format.percent(String(t)) : metric.fmt(t)}</text>
          </g>
        ))}
        {cmp.sites.map((_s, si) => {
          const gy = m.t + si * (groupH + groupGap);
          return (
            <g key={si}>
              {stacked ? <text x={m.l} y={gy + 12} fontSize="12" fill={ink}>{siteName(si)}</text>
                : <text x={m.l - 10} y={gy + groupH / 2 + 4} textAnchor="end" fontSize="12" fill={ink}>{siteName(si)}</text>}
              {cmp.windows.map((_w, wi) => {
                const cell = cmp.cells[si * nW + wi];
                const v = cell ? metric.get(cell) : null;
                const y = gy + labelH + wi * (barH + barGap);
                const ok = v != null && Number.isFinite(v);
                return (
                  <g key={wi}>
                    {/* Phase 7 (U-04): rendered only where it is shown; an invisible (opacity 0) label was still in the page */}
                    {nW > 1 && !ok && <text x={m.l + 4} y={y + barH - 4} fontSize="10" fill={axis}>{windowName(wi)}</text>}
                    {ok ? (
                      <rect x={x(0)} y={y} width={Math.max(1, x(v as number) - x(0))} height={barH} rx={2}
                            fill={SITE_COLORS[si % SITE_COLORS.length]} fillOpacity={nW > 1 ? 0.95 - 0.5 * (wi / Math.max(1, nW - 1)) : 0.9}>
                        <title>{C.barTitle(siteName(si), windowName(wi), metric.fmt(v))}</title>
                      </rect>
                    ) : null}
                    <text x={ok ? x(v as number) + 6 : m.l + 8 + (nW > 1 ? 30 : 0)} y={y + barH - 4} fontSize="11.5" fill={ok ? ink : "#ee9a6b"}
                          fontFamily="var(--font-mono)">{ok ? (nW > 1 ? C.barValue(windowName(wi), metric.fmt(v)) : metric.fmt(v)) : C.unavailable}</text>
                  </g>
                );
              })}
            </g>
          );
        })}
      </svg>
      <p className="hint">{metric.percent ? C.barNotePercent : C.barNoteScale}</p>
    </figure>
  );
}

/** Sunlit time (x) against Earth in view (y), one point per site and window, from the two calculated percentages. */
function SunEarthScatter({ cmp, sunlit, earth, siteName, windowName }: { cmp: Comparison; sunlit: (c: CompareCell) => number | null;
  earth: (c: CompareCell) => number | null; siteName: (si: number) => string; windowName: (wi: number) => string }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<{ k: number; px: number; py: number } | null>(null);
  const W = Math.max(300, width);
  const H = Math.round(Math.min(420, Math.max(280, W * 0.62)));
  const m = { l: 52, r: 16, t: 12, b: 44 };
  const x = d3.scaleLinear().domain([0, 100]).range([m.l, W - m.r]);
  const y = d3.scaleLinear().domain([0, 100]).range([H - m.b, m.t]);
  const nW = cmp.windows.length;
  const pts = cmp.cells.map((c, k) => ({ k, si: Math.floor(k / nW), wi: k % nW, sx: sunlit(c), ey: earth(c) }));
  const shown = pts.filter((p) => p.sx != null && p.ey != null && Number.isFinite(p.sx) && Number.isFinite(p.ey));
  const missing = pts.length - shown.length;
  const hp = hover ? pts[hover.k] : null;
  return (
    <figure className="compare-chart" ref={ref}>
      <figcaption>{C.scatterHeading}</figcaption>
      <div className="chart-box">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={C.scatterLabel(shown.length)} onMouseLeave={() => setHover(null)}>
          <rect x={m.l} y={m.t} width={W - m.l - m.r} height={H - m.t - m.b} fill="#141e29" />
          {[0, 25, 50, 75, 100].map((t) => (
            <g key={t}>
              <line x1={x(t)} x2={x(t)} y1={m.t} y2={H - m.b} stroke={grid} strokeDasharray={t === 0 ? "" : "2 4"} />
              <line x1={m.l} x2={W - m.r} y1={y(t)} y2={y(t)} stroke={grid} strokeDasharray={t === 0 ? "" : "2 4"} />
              <text x={x(t)} y={H - m.b + 16} textAnchor="middle" fontSize="11" fill={axis}>{S.format.percent(String(t))}</text>
              <text x={m.l - 6} y={y(t) + 4} textAnchor="end" fontSize="11" fill={axis}>{S.format.percent(String(t))}</text>
            </g>
          ))}
          <text x={W - m.r} y={H - 6} textAnchor="end" fontSize="11" fill="#f2b544">{C.scatterX}</text>
          <text x={14} y={(m.t + H - m.b) / 2} textAnchor="middle" fontSize="11" fill="#5fa8e8"
                transform={`rotate(-90 14 ${(m.t + H - m.b) / 2})`}>{C.scatterY}</text>
          {shown.map((p) => {
            const cx = x(p.sx as number), cy = y(p.ey as number), col = SITE_COLORS[p.si % SITE_COLORS.length];
            return (
              <g key={p.k} onMouseEnter={(e) => { const b = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect();
                setHover({ k: p.k, px: e.clientX - b.left, py: e.clientY - b.top }); }}>
                <circle cx={cx} cy={cy} r={hover?.k === p.k ? 8 : 6} fill={col} fillOpacity={0.85} stroke="#0b121b" strokeWidth={1.5} />
                {nW > 1 && <text x={cx + 9} y={cy + 4} fontSize="10" fill={axis}>{windowName(p.wi)}</text>}
              </g>
            );
          })}
        </svg>
        {hp && hover && (
          <ChartTooltip x={hover.px} y={hover.py} boxWidth={ref.current?.clientWidth ?? W}>
            <strong>{siteName(hp.si)}</strong>
            <dl>
              <div><dt>{C.windowShortLabel}</dt><dd>{windowName(hp.wi)}</dd></div>
              <div><dt>{C.scatterX}</dt><dd>{fmtPct(hp.sx)}</dd></div>
              <div><dt>{C.scatterY}</dt><dd>{fmtPct(hp.ey)}</dd></div>
            </dl>
          </ChartTooltip>
        )}
      </div>
      <ul className="chart-legend">
        {cmp.sites.map((_s, si) => (
          <li key={si}><i className="lg lg-dot" aria-hidden style={{ "--lg": SITE_COLORS[si % SITE_COLORS.length] } as React.CSSProperties} />{siteName(si)}</li>
        ))}
      </ul>
      <p className="hint">{C.scatterNote}{missing > 0 ? ` ${C.unavailableCells(missing)}` : ""}</p>
    </figure>
  );
}
