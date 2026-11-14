import * as d3 from "d3";
import { useEffect, useMemo, useState } from "react";
import type { Result } from "../api/types";
import { S } from "../i18n";
import { useWidth } from "../lib/useWidth";

interface Props { result: Result; cursor: number; height?: number }

// Splits an (az, el) track wherever it wraps through 0/360 so lines do not streak across the chart.
function trackSegments(az: (number | null)[], el: (number | null)[]): [number, number][][] {
  const segs: [number, number][][] = [];
  let cur: [number, number][] = [];
  for (let i = 0; i < az.length; i++) {
    const a = az[i], e = el[i];
    if (a == null || e == null) { if (cur.length) segs.push(cur); cur = []; continue; }
    if (cur.length && Math.abs(a - cur[cur.length - 1][0]) > 180) { segs.push(cur); cur = []; }
    cur.push([a, e]);
  }
  if (cur.length) segs.push(cur);
  return segs;
}

export function HorizonPanorama({ result, cursor, height = 300 }: Props) {
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
  const m = { l: 44, r: 12, t: 14, b: 30 };
  const W = Math.max(320, width), H = height;

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
      band = d3.area<number>()
        .defined((i) => sig[i] != null)
        .x((i) => x(i * h.bin_deg)).y0((i) => y(h.h_deg[i] - (sig[i] ?? 0))).y1((i) => y(h.h_deg[i] + (sig[i] ?? 0)))(
          d3.range(h.nbins)) ?? "";
    }
    const incRuns: [number, number][] = [];
    let start = -1;
    h.incomplete.forEach((v, i) => {
      if (v && start < 0) start = i;
      if (!v && start >= 0) { incRuns.push([start, i]); start = -1; }
    });
    if (start >= 0) incRuns.push([start, h.nbins]);
    const line = d3.line<[number, number]>().x((d) => x(d[0])).y((d) => y(d[1]));
    const sunPaths = trackSegments(s.sun.az, s.sun.el).map((seg) => line(seg) ?? "");
    // near-field bins (horizon set by terrain within 2 site pixels): marked along the bottom of the chart
    const nearRuns: [number, number][] = [];
    let ns = -1;
    (h.near_field ?? []).forEach((v, i) => {
      if (v && ns < 0) ns = i;
      if (!v && ns >= 0) { nearRuns.push([ns, i]); ns = -1; }
    });
    if (ns >= 0) nearRuns.push([ns, h.nbins]);
    const earthPaths = trackSegments(s.earth.az, s.earth.el).map((seg) => line(seg) ?? "");
    return { x, y, area, band, incRuns, nearRuns, sunPaths, earthPaths };
  }, [result, W, H]); // eslint-disable-line react-hooks/exhaustive-deps

  const { x, y } = geom;
  const disk = (body: "sun" | "earth") => {
    const b = s[body];
    const az = b.az[cursor], el = b.el[cursor], rho = b.rho[cursor];
    if (az == null || el == null || rho == null) return null;
    const cosEl = Math.max(Math.cos((el * Math.PI) / 180), 1e-6);
    const rx = Math.abs(x(rho / cosEl) - x(0));
    const ry = Math.abs(y(0) - y(rho));
    return { cx: x(az), cy: y(el), rx: Math.max(rx, 1.5), ry: Math.max(ry, 1.5), az, el };
  };
  const sun = disk("sun"), earth = disk("earth");
  const compass = [0, 90, 180, 270];
  const names: Record<number, string> = S.panorama.compass;
  const hoverBin = hover == null ? null : Math.round(hover / h.bin_deg) % h.nbins;
  // readout: azimuth and horizon (as before), then the bin's 1-sigma uncertainty and near-field flag where the result has them
  const readout = hoverBin == null || hover == null ? undefined
    : S.panorama.hover(hover.toFixed(1), h.h_deg[hoverBin].toFixed(2), h.incomplete[hoverBin])
      + (h.sigma_deg?.[hoverBin] != null ? S.panorama.hoverSigma((h.sigma_deg[hoverBin] as number).toFixed(2)) : "")
      + (h.near_field?.[hoverBin] ? S.panorama.hoverNearField : "");

  return (
    <div className="panorama" ref={ref}>
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
            <line x1="0" y1="0" x2="0" y2="6" stroke="#ee9a6b" strokeWidth="1.4" />
          </pattern>
          <linearGradient id="sky" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="#141d27" />
            <stop offset="1" stopColor="#1d2a38" />
          </linearGradient>
        </defs>
        <rect x={m.l} y={m.t} width={W - m.l - m.r} height={H - m.t - m.b} fill="url(#sky)" />
        {y.ticks(5).map((t) => (
          <g key={t}>
            <line x1={m.l} x2={W - m.r} y1={y(t)} y2={y(t)} stroke={t === 0 ? "#5a6e82" : "#2a3a4b"} strokeDasharray={t === 0 ? "" : "2 4"} />
            <text x={m.l - 6} y={y(t) + 4} textAnchor="end" fontSize="11" fill="#a3b1bf">{S.format.degrees(t)}</text>
          </g>
        ))}
        {geom.sunPaths.map((p, i) => <path key={`s${i}`} d={p} fill="none" stroke="#f2b544" strokeOpacity={0.55} strokeWidth={1.5} />)}
        {geom.earthPaths.map((p, i) => <path key={`e${i}`} d={p} fill="none" stroke="#5fa8e8" strokeOpacity={0.6} strokeWidth={1.5} />)}
        {earth && <ellipse cx={earth.cx} cy={earth.cy} rx={earth.rx} ry={earth.ry} fill="#5fa8e8" fillOpacity={0.9} stroke="#cfe6fb" strokeWidth={1} />}
        {sun && <ellipse cx={sun.cx} cy={sun.cy} rx={sun.rx} ry={sun.ry} fill="#f2b544" stroke="#ffe3a3" strokeWidth={1} />}
        {geom.band && <path d={geom.band} fill="#a3b1bf" fillOpacity={0.18} />}
        <path d={geom.area} fill="#4b5c6d" stroke="#8a9aab" strokeWidth={0.8} />
        {geom.incRuns.map(([a, b]) => (
          <rect key={a} x={x(a * h.bin_deg)} width={Math.max(1, x(b * h.bin_deg) - x(a * h.bin_deg))} y={m.t}
                height={H - m.t - m.b} fill="url(#hatch)" opacity={0.5} />
        ))}
        {geom.nearRuns.map(([a, b]) => (
          <rect key={`nf${a}`} x={x(a * h.bin_deg)} width={Math.max(1, x(b * h.bin_deg) - x(a * h.bin_deg))} y={H - m.b - 4}
                height={4} fill="#c79bf2" opacity={0.85} />
        ))}
        {compass.map((a) => (
          <text key={a} x={x(a)} y={H - 10} textAnchor="middle" fontSize="12" fontWeight={600} fill="#e7ecf1">{names[a]}</text>
        ))}
        {d3.range(30, 360, 30).filter((a) => !compass.includes(a)).map((a) => (
          <text key={a} x={x(a)} y={H - 10} textAnchor="middle" fontSize="11" fill="#7d8d9d">{S.format.degrees(a)}</text>
        ))}
        {hover != null && hoverBin != null && (
          <g pointerEvents="none">
            <line x1={x(hover)} x2={x(hover)} y1={m.t} y2={H - m.b} stroke="#e7ecf1" strokeOpacity={0.35} />
            <text x={Math.min(x(hover) + 6, W - 260)} y={m.t + 14} fontSize="12" fill="#e7ecf1">{readout}</text>
          </g>
        )}
      </svg>
    </div>
  );
}
