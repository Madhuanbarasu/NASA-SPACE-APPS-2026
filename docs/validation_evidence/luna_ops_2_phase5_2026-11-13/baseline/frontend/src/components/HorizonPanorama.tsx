import * as d3 from "d3";
import { useEffect, useMemo, useState } from "react";
import type { Result } from "../api/types";
import { S } from "../i18n";
import { fmtDeg } from "../lib/format";
import { useWidth } from "../lib/useWidth";
import { ChartLegend, type ChartLegendItem } from "../ui/ChartLegend";
import { Metric } from "../ui/Metric";

// The terrain horizon around the site with the Sun and Earth tracks over the window (all from the result: horizon
// profile, its 1-sigma band, incomplete and near-field bins, and the series of azimuth, elevation, angular radius and
// clearance). LUNA-OPS 2.0 Phase 3: larger, titled axes, a readout panel, and each track drawn dashed where the API's
// clearance says the body's centre is below the terrain horizon (series.*.c < 0). Nothing is computed here.

interface Props { result: Result; cursor: number }
const A = S.analysis;
const COLORS = { sun: "#f2b544", sunEdge: "#ffe3a3", earth: "#5fa8e8", earthEdge: "#cfe6fb", terrain: "#4b5c6d", terrainEdge: "#8a9aab",
  sigma: "#a3b1bf", hatch: "#ee9a6b", near: "#c79bf2", grid: "#2a3a4b", zero: "#5a6e82", axis: "#a3b1bf", ink: "#e7ecf1", faint: "#7d8d9d" };

interface Run { pts: [number, number][]; below: boolean }

/** Splits an (az, el) track where it wraps through 0/360 and where the centre crosses the terrain horizon (clearance). */
function trackRuns(az: (number | null)[], el: (number | null)[], c: (number | null)[]): Run[] {
  const out: Run[] = [];
  let cur: Run | null = null;
  for (let i = 0; i < az.length; i++) {
    const a = az[i], e = el[i];
    if (a == null || e == null) { if (cur) out.push(cur); cur = null; continue; }
    const below = c[i] != null && (c[i] as number) < 0;
    if (cur && Math.abs(a - cur.pts[cur.pts.length - 1][0]) > 180) { out.push(cur); cur = null; }
    if (cur && cur.below !== below) { cur.pts.push([a, e]); out.push(cur); cur = { pts: [[a, e]], below }; continue; }
    if (!cur) cur = { pts: [], below };
    cur.pts.push([a, e]);
  }
  if (cur) out.push(cur);
  return out;
}
const firstPoint = (az: (number | null)[], el: (number | null)[]) => {
  for (let i = 0; i < az.length; i++) if (az[i] != null && el[i] != null) return [az[i] as number, el[i] as number] as const;
  return null;
};

export function HorizonPanorama({ result, cursor }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const h = result.horizon;
  // U-04 (1.4.13): the hover readout can be dismissed with Escape without moving the pointer
  useEffect(() => {
    if (hover == null) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setHover(null); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [hover]);
  const s = result.series;
  const m = { l: 54, r: 14, t: 14, b: 46 };
  const W = Math.max(320, width);
  const H = Math.round(Math.min(470, Math.max(320, W * 0.34)));

  const geom = useMemo(() => {
    const els = [...s.sun.el, ...s.earth.el].filter((v): v is number => v != null);
    const lo = Math.min(-2, h.min_deg - 0.5, ...els.filter((e) => e > -10));
    const hiData = Math.max(h.max_deg + 1, ...els.map((e) => e + 1.2));
    const hi = Math.min(90, Math.max(lo + 4, hiData));
    const x = d3.scaleLinear().domain([0, 360]).range([m.l, W - m.r]);
    const y = d3.scaleLinear().domain([Math.max(lo, -12), hi]).range([H - m.b, m.t]).clamp(true);
    const pts: [number, number][] = h.h_deg.map((v, i) => [i * h.bin_deg, v]);
    pts.push([360, h.h_deg[0]]);
    const area = d3.area<[number, number]>().x((d) => x(d[0])).y0(H - m.b).y1((d) => y(d[1]))(pts) ?? "";
    let band = "";
    if (h.sigma_deg) {
      const sig = h.sigma_deg;
      band = d3.area<number>().defined((i) => sig[i] != null)
        .x((i) => x(i * h.bin_deg)).y0((i) => y(h.h_deg[i] - (sig[i] ?? 0))).y1((i) => y(h.h_deg[i] + (sig[i] ?? 0)))(d3.range(h.nbins)) ?? "";
    }
    const binRuns = (flags: boolean[] | null | undefined) => {
      const out: [number, number][] = [];
      let st = -1;
      (flags ?? []).forEach((v, i) => { if (v && st < 0) st = i; if (!v && st >= 0) { out.push([st, i]); st = -1; } });
      if (st >= 0) out.push([st, h.nbins]);
      return out;
    };
    const line = d3.line<[number, number]>().x((d) => x(d[0])).y((d) => y(d[1]));
    const tracks = (body: "sun" | "earth") => trackRuns(s[body].az, s[body].el, s[body].c).map((r) => ({ d: line(r.pts) ?? "", below: r.below }));
    return { x, y, area, band, incRuns: binRuns(h.incomplete), nearRuns: binRuns(h.near_field), sun: tracks("sun"), earth: tracks("earth"),
      sunStart: firstPoint(s.sun.az, s.sun.el), earthStart: firstPoint(s.earth.az, s.earth.el) };
  }, [result, W, H]); // eslint-disable-line react-hooks/exhaustive-deps

  const { x, y } = geom;
  const disk = (body: "sun" | "earth") => {
    const b = s[body];
    const az = b.az[cursor], el = b.el[cursor], rho = b.rho[cursor];
    if (az == null || el == null || rho == null) return null;
    const cosEl = Math.max(Math.cos((el * Math.PI) / 180), 1e-6);
    const rx = Math.abs(x(rho / cosEl) - x(0));
    const ry = Math.abs(y(0) - y(rho));
    return { cx: x(az), cy: y(el), rx: Math.max(rx, 1.5), ry: Math.max(ry, 1.5) };
  };
  const sun = disk("sun"), earth = disk("earth");
  const compass = [0, 90, 180, 270];
  const names: Record<number, string> = S.panorama.compass;
  const binOf = (az: number) => ((Math.round(az / h.bin_deg) % h.nbins) + h.nbins) % h.nbins;
  const hoverBin = hover == null ? null : binOf(hover);
  // the slider's value text (unchanged wording): azimuth and horizon, then the bin's 1-sigma and near-field flag
  const readout = hoverBin == null || hover == null ? undefined
    : S.panorama.hover(hover.toFixed(1), h.h_deg[hoverBin].toFixed(2), h.incomplete[hoverBin])
      + (h.sigma_deg?.[hoverBin] != null ? S.panorama.hoverSigma((h.sigma_deg[hoverBin] as number).toFixed(2)) : "")
      + (h.near_field?.[hoverBin] ? S.panorama.hoverNearField : "");
  const sunAz = s.sun.az[cursor];
  const horizonAtSun = sunAz == null ? null : h.h_deg[binOf(sunAz)];
  const bodyState = (body: "sun" | "earth") => {
    const c = s[body].c[cursor];
    return c == null ? S.common.unknown : c < 0 ? A.centreBelow : A.centreAbove;
  };
  const legend: ChartLegendItem[] = [
    { swatch: "line", color: COLORS.sun, text: S.site.legend.sunPath },
    { swatch: "dashed", color: COLORS.sun, text: A.pathBelow },
    { swatch: "line", color: COLORS.earth, text: S.site.legend.earthPath },
    { swatch: "ring", color: COLORS.ink, text: A.trackStart },
    { swatch: "fill", color: COLORS.terrain, text: S.site.legend.terrain(h.site_level) },
    ...(h.sigma_deg ? [{ swatch: "fill", color: "rgba(163, 177, 191, 0.45)", text: S.site.legend.sigmaBand } as ChartLegendItem] : []),
    ...(h.incomplete_share > 0 ? [{ swatch: "hatch", color: COLORS.hatch, text: S.site.legend.coverageRanOut } as ChartLegendItem] : []),
    ...((h.near_field ?? []).some(Boolean) ? [{ swatch: "band", color: COLORS.near, text: S.site.legend.nearField } as ChartLegendItem] : []),
  ];

  return (
    <div className="panorama" ref={ref}>
      <dl className="metrics panorama-readout" aria-hidden>
        {hover != null && hoverBin != null ? (<>
          <Metric label={A.rdAzimuth} value={fmtDeg(hover, 1)} />
          <Metric label={A.rdHorizon} value={fmtDeg(h.h_deg[hoverBin])} note={h.incomplete[hoverBin] ? A.lowerBound : undefined}
                  state={h.incomplete[hoverBin] ? "flag" : undefined} />
          <Metric label={A.rdSigma} value={h.sigma_deg?.[hoverBin] != null ? A.plusMinus(fmtDeg(h.sigma_deg[hoverBin])) : S.common.na}
                  state={h.sigma_deg?.[hoverBin] != null ? undefined : "unknown"} />
          <Metric label={A.rdNearField} value={h.near_field?.[hoverBin] ? A.yes : A.no} state={h.near_field?.[hoverBin] ? "flag" : undefined} />
        </>) : (<>
          <Metric label={A.rdSun} value={A.azEl(fmtDeg(s.sun.az[cursor], 1), fmtDeg(s.sun.el[cursor]))} note={bodyState("sun")} />
          <Metric label={A.rdEarth} value={A.azEl(fmtDeg(s.earth.az[cursor], 1), fmtDeg(s.earth.el[cursor]))} note={bodyState("earth")} />
          <Metric label={A.rdHorizonAtSun} value={fmtDeg(horizonAtSun)} />
          <Metric label={A.rdHorizonRange} value={A.range(fmtDeg(h.min_deg), fmtDeg(h.max_deg))} />
        </>)}
      </dl>
      <svg viewBox={`0 0 ${W} ${H}`} role="slider" tabIndex={0}
           aria-label={`${S.panorama.label(h.max_deg.toFixed(2))} ${S.panorama.keyboardHint}`}
           aria-valuemin={0} aria-valuemax={360} aria-valuenow={hover == null ? 0 : Math.round(hover)}
           aria-valuetext={readout}
           onFocus={() => setHover((v) => v ?? Math.round(s.sun.az[cursor] ?? 0))}
           onBlur={() => setHover(null)}
           onKeyDown={(e) => {
             const step = e.key === "ArrowRight" || e.key === "ArrowUp" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowDown" ? -1
               : e.key === "PageUp" ? 10 : e.key === "PageDown" ? -10 : 0;
             if (e.key === "Home" || e.key === "End") { e.preventDefault(); setHover(e.key === "Home" ? 0 : 359); return; }
             if (!step) return;
             e.preventDefault();
             setHover((v) => ((Math.round(v ?? 0) + step) % 360 + 360) % 360);
           }}
           onMouseMove={(e) => {
             const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
             const az = x.invert(((e.clientX - r.left) / r.width) * W);
             setHover(az >= 0 && az <= 360 ? az : null);
           }}
           onMouseLeave={() => setHover(null)}>
        <defs>
          <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="6" stroke={COLORS.hatch} strokeWidth="1.4" />
          </pattern>
          <linearGradient id="sky" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="#101822" />
            <stop offset="1" stopColor="#1d2a38" />
          </linearGradient>
        </defs>
        <rect x={m.l} y={m.t} width={W - m.l - m.r} height={H - m.t - m.b} fill="url(#sky)" />
        {d3.range(0, 361, 30).map((a) => (
          <line key={`v${a}`} x1={x(a)} x2={x(a)} y1={m.t} y2={H - m.b} stroke={COLORS.grid} strokeOpacity={compass.includes(a % 360) ? 0.9 : 0.45} />
        ))}
        {y.ticks(6).map((t) => (
          <g key={t}>
            <line x1={m.l} x2={W - m.r} y1={y(t)} y2={y(t)} stroke={t === 0 ? COLORS.zero : COLORS.grid} strokeDasharray={t === 0 ? "" : "2 4"} />
            <text x={m.l - 6} y={y(t) + 4} textAnchor="end" fontSize="11" fill={COLORS.axis}>{S.format.degrees(t)}</text>
          </g>
        ))}
        {geom.sun.map((p, i) => <path key={`s${i}`} d={p.d} fill="none" stroke={COLORS.sun} strokeOpacity={p.below ? 0.5 : 0.85}
                                      strokeWidth={p.below ? 1.2 : 1.8} strokeDasharray={p.below ? "4 4" : undefined} />)}
        {geom.earth.map((p, i) => <path key={`e${i}`} d={p.d} fill="none" stroke={COLORS.earth} strokeOpacity={p.below ? 0.5 : 0.85}
                                        strokeWidth={p.below ? 1.2 : 1.8} strokeDasharray={p.below ? "4 4" : undefined} />)}
        {geom.sunStart && <circle cx={x(geom.sunStart[0])} cy={y(geom.sunStart[1])} r={4} fill="none" stroke={COLORS.sun} strokeWidth={1.5} />}
        {geom.earthStart && <circle cx={x(geom.earthStart[0])} cy={y(geom.earthStart[1])} r={4} fill="none" stroke={COLORS.earth} strokeWidth={1.5} />}
        {earth && <ellipse cx={earth.cx} cy={earth.cy} rx={earth.rx} ry={earth.ry} fill={COLORS.earth} fillOpacity={0.9} stroke={COLORS.earthEdge} strokeWidth={1} />}
        {sun && <ellipse cx={sun.cx} cy={sun.cy} rx={sun.rx} ry={sun.ry} fill={COLORS.sun} stroke={COLORS.sunEdge} strokeWidth={1} />}
        {geom.band && <path d={geom.band} fill={COLORS.sigma} fillOpacity={0.18} />}
        <path d={geom.area} fill={COLORS.terrain} stroke={COLORS.terrainEdge} strokeWidth={0.8} />
        {geom.incRuns.map(([a, b]) => (
          <rect key={a} x={x(a * h.bin_deg)} width={Math.max(1, x(b * h.bin_deg) - x(a * h.bin_deg))} y={m.t}
                height={H - m.t - m.b} fill="url(#hatch)" opacity={0.5} />
        ))}
        {geom.nearRuns.map(([a, b]) => (
          <rect key={`nf${a}`} x={x(a * h.bin_deg)} width={Math.max(1, x(b * h.bin_deg) - x(a * h.bin_deg))} y={H - m.b - 4}
                height={4} fill={COLORS.near} opacity={0.85} />
        ))}
        {compass.map((a) => (
          <text key={a} x={x(a)} y={H - m.b + 17} textAnchor="middle" fontSize="12" fontWeight={650} fill={COLORS.ink}>{names[a]}</text>
        ))}
        {d3.range(30, 360, 30).filter((a) => !compass.includes(a)).map((a) => (
          <text key={a} x={x(a)} y={H - m.b + 17} textAnchor="middle" fontSize="11" fill={COLORS.faint}>{S.format.degrees(a)}</text>
        ))}
        <text x={14} y={(m.t + H - m.b) / 2} fontSize="11" fill={COLORS.axis} textAnchor="middle"
              transform={`rotate(-90 14 ${(m.t + H - m.b) / 2})`}>{A.elAxis}</text>
        <text x={W - m.r} y={H - 6} textAnchor="end" fontSize="11" fill={COLORS.axis}>{A.azAxis}</text>
        {hover != null && hoverBin != null && (
          <g pointerEvents="none">
            <line x1={x(hover)} x2={x(hover)} y1={m.t} y2={H - m.b} stroke={COLORS.ink} strokeOpacity={0.45} />
            <circle cx={x(hover)} cy={y(h.h_deg[hoverBin])} r={3.5} fill={COLORS.ink} />
          </g>
        )}
      </svg>
      <ChartLegend items={legend} label={A.legendLabel} className="panorama-legend" />
    </div>
  );
}
