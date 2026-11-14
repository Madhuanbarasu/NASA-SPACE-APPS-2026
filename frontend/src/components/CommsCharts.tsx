import * as d3 from "d3";
import type { CommsResult, CommsRow, CommsSegment } from "../api/types";
import { S, timeLocale } from "../i18n";
import { spacedTicks } from "../lib/timeAxis";
import { useWidth } from "../lib/useWidth";
import { ChartLegend } from "../ui/ChartLegend";

// LUNA-OPS 2.0 Phase 6: communication timeline and elevation chart. They only draw /api/comms segments and series (times
// mapped to pixels); nothing is computed here. Geometry rows and RF rows use different styles and separate legends; unknown
// time is hatched and never drawn as open or closed.

const C = S.comms;
const ROW_H = 20, GAP = 6, LEFT_MIN = 150;
// style tokens (class-name suffixes, never displayed)
const KIND = { geo: "geo", rf: "rf", block: "block", none: "none" } as const;
export const GEOMETRY_ROWS: CommsRow[] = ["earth_visible", "terrain_blocked", "relay_leg1", "relay_leg2", "relay_geometric", "any_geometric", "no_geometric_path"];
export const RF_ROWS: CommsRow[] = ["direct_rf", "relay_rf", "any_rf"];

function useAxis(c: CommsResult, width: number, left: number) {
  const t0 = new Date(c.window.start_utc).getTime(), t1 = new Date(c.window.end_utc).getTime();
  const x = d3.scaleUtc().domain([t0, t1]).range([left, Math.max(left + 10, width - 12)]);
  const etMs = (et: number) => t0 + (et - c.window.start_et) * 1000;
  const ticks = spacedTicks(x, x.ticks(Math.max(2, Math.floor((width - left) / 120))));
  return { x, etMs, ticks, fmt: timeLocale.utcFormat(S.timeline.tickFormat) };
}

function Row({ segs, y, x, etMs, kind, label, above }: { segs: CommsSegment[]; y: number; x: d3.ScaleTime<number, number>;
  etMs: (et: number) => number; kind: "geo" | "rf" | "block" | "none"; label: string; above: boolean }) {
  return (
    <g>
      {above ? <text x={x.range()[0]} y={y - 4} className="ct-label">{label}</text>
        : <text x={x.range()[0] - 8} y={y + ROW_H / 2 + 4} textAnchor="end" className="ct-label">{label}</text>}
      <rect x={x.range()[0]} y={y} width={x.range()[1] - x.range()[0]} height={ROW_H} className="ct-track" />
      {segs.map((s, i) => {
        const a = x(etMs(s.start_et)), b = x(etMs(s.end_et));
        const w = Math.max(b - a, 0.8);
        if (s.state === null) return <rect key={i} x={a} y={y} width={w} height={ROW_H} className="ct-unknown" />;
        if (!s.state) return null;
        return <rect key={i} x={a} y={y + 2} width={w} height={ROW_H - 4} className={`ct-open is-${kind}${s.uncertain ? " is-uncertain" : ""}`} />;
      })}
    </g>
  );
}

export function CommsTimeline({ c, cursorEt }: { c: CommsResult; cursorEt: number | null }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  // narrow screens: labels above the bars (full width for the bars), otherwise in a left column
  const above = width < 560;
  const left = above ? 4 : Math.min(LEFT_MIN + 40, Math.max(LEFT_MIN - 30, width * 0.3));
  const pitch = ROW_H + GAP + (above ? 16 : 0);
  const { x, etMs, ticks, fmt } = useAxis(c, width, left);
  const geo = GEOMETRY_ROWS.filter((r) => c.timeline[r]);
  const rf = RF_ROWS;
  const kind = (r: CommsRow) => (r === "terrain_blocked" ? KIND.block : r === "no_geometric_path" ? KIND.none : KIND.geo);
  const yGeo = 22 + (above ? 16 : 0), yRf = yGeo + geo.length * pitch + 26 + (above ? 16 : 0);
  const h = yRf + rf.length * pitch + 28;
  const cx = cursorEt == null ? null : x(etMs(cursorEt));
  return (
    <div className="comms-timeline" ref={ref}>
      <svg width={width} height={h} role="img" aria-label={C.timeline.aria(fmt(new Date(c.window.start_utc)), fmt(new Date(c.window.end_utc)))}>
        <text x={left} y={14} className="ct-group">{C.timeline.geometryGroup}</text>
        {geo.map((r, i) => <Row key={r} segs={c.timeline[r]!} y={yGeo + i * pitch} x={x} etMs={etMs} kind={kind(r)} label={C.rows[r]} above={above} />)}
        <text x={left} y={yRf - 8 - (above ? 16 : 0)} className="ct-group">{C.timeline.rfGroup}</text>
        {rf.map((r, i) => {
          const y = yRf + i * pitch;
          const segs = c.timeline[r];
          return segs ? <Row key={r} segs={segs} y={y} x={x} etMs={etMs} kind={KIND.rf} label={C.rows[r]} above={above} /> : (
            <g key={r}>
              {above ? <text x={left} y={y - 4} className="ct-label">{C.rows[r]}</text>
                : <text x={left - 8} y={y + ROW_H / 2 + 4} textAnchor="end" className="ct-label">{C.rows[r]}</text>}
              <rect x={left} y={y} width={x.range()[1] - left} height={ROW_H} className="ct-track is-off" />
              <text x={left + 8} y={y + ROW_H / 2 + 4} className="ct-off">{C.timeline.notEvaluated}</text>
            </g>
          );
        })}
        {ticks.map((t, i) => (
          <g key={i}>
            <line x1={x(t)} x2={x(t)} y1={yGeo - 4} y2={h - 18} className="ct-tick" />
            <text x={x(t)} y={h - 4} textAnchor="middle" className="ct-ticklabel">{fmt(t)}</text>
          </g>
        ))}
        {cx != null && <line x1={cx} x2={cx} y1={yGeo - 6} y2={h - 18} className="ct-cursor" />}
      </svg>
      <ChartLegend label={C.timeline.geometryLegend} items={[
        { swatch: "fill", color: "var(--earth)", text: C.legend.geoOpen },
        { swatch: "fill", color: "var(--alert)", text: C.legend.blocked },
        { swatch: "fill", color: "var(--faint)", text: C.legend.noPath },
        { swatch: "hatch", text: C.legend.unknown },
        { swatch: "outline-dashed", text: C.legend.uncertain },
      ]} />
      <ChartLegend label={C.timeline.rfLegend} items={[
        { swatch: "fill", color: "var(--valid)", text: C.legend.rfOpen },
        { swatch: "outline-dashed", color: "var(--faint)", text: C.legend.rfOff },
      ]} />
    </div>
  );
}

/** Earth elevation, Earth clearance above the terrain horizon, and (if configured) the relay's elevation from the site. */
export function ElevationChart({ c, cursorEt }: { c: CommsResult; cursorEt: number | null }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const left = 46, h = 200, top = 10, bottom = 26;
  const { x, etMs, ticks, fmt } = useAxis(c, width, left);
  const se = c.direct.series;
  const rs = c.relay?.series;
  const vals = [...se.el, ...se.clearance_deg, ...(rs ? rs.el_deg : [])].filter((v): v is number => v != null);
  const lo = Math.min(-5, d3.min(vals) ?? -5), hi = Math.max(5, d3.max(vals) ?? 5);
  const y = d3.scaleLinear().domain([lo, hi]).nice().range([h - bottom, top]);
  const line = (ts: string[], vs: (number | null)[]) =>
    d3.line<[number, number | null]>().defined((d) => d[1] != null).x((d) => x(d[0])).y((d) => y(d[1] as number))(
      ts.map((t, i) => [new Date(t).getTime(), vs[i]] as [number, number | null]));
  const cx = cursorEt == null ? null : x(etMs(cursorEt));
  return (
    <div className="comms-elev" ref={ref}>
      <svg width={width} height={h} role="img" aria-label={C.elev.aria}>
        {y.ticks(5).map((v) => (
          <g key={v}><line x1={left} x2={x.range()[1]} y1={y(v)} y2={y(v)} className={v === 0 ? "ct-zero" : "ct-grid"} />
            <text x={left - 6} y={y(v) + 4} textAnchor="end" className="ct-ticklabel">{C.elev.deg(v)}</text></g>
        ))}
        {ticks.map((t, i) => <text key={i} x={x(t)} y={h - 6} textAnchor="middle" className="ct-ticklabel">{fmt(t)}</text>)}
        <path d={line(se.utc, se.el) ?? ""} className="ce-earth" />
        <path d={line(se.utc, se.clearance_deg) ?? ""} className="ce-clear" />
        {rs && <path d={line(rs.utc, rs.el_deg) ?? ""} className="ce-relay" />}
        {cx != null && <line x1={cx} x2={cx} y1={top} y2={h - bottom} className="ct-cursor" />}
      </svg>
      <ChartLegend label={C.elev.legend} items={[
        { swatch: "line", color: "var(--earth)", text: C.elev.earth },
        { swatch: "dashed", color: "var(--earth)", text: C.elev.clearance },
        ...(rs ? [{ swatch: "line" as const, color: "var(--candidate)", text: C.elev.relay }] : []),
      ]} />
      {rs?.decimated && <p className="hint">{C.elev.decimated}</p>}
    </div>
  );
}
