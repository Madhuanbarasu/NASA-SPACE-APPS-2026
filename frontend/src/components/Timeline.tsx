import * as d3 from "d3";
import { useMemo, useState } from "react";
import type { Interval, Result } from "../api/types";
import { S, timeLocale } from "../i18n";
import { RULE_NAMES, fmtDuration, fmtUTC } from "../lib/format";
import { spacedTicks } from "../lib/timeAxis";
import { useWidth } from "../lib/useWidth";
import { ChartTooltip } from "../ui/ChartTooltip";

interface Props { result: Result; cursor: number; onCursor: (i: number) => void }

const V = S.viz;
const BODY_COLORS = { sun: "#f2b544", earth: "#5fa8e8" };
/** The flags the engine attaches to an interval, as text (Phase 2/3 fields; display planned for Phase 5). */
export function intervalNotes(iv: Interval): string {
  const out: string[] = [];
  if (iv.uncertain) out.push(V.reasonUncertain);
  for (const r of iv.uncertain_reasons ?? []) out.push(V.reasons[r] ?? r);
  if (iv.near_field) out.push(V.reasonNearField);
  if (iv.brief) out.push(V.reasonBrief);
  if (iv.subbin_peak === true) out.push(V.reasonSubbin);
  else if (iv.subbin_peak === null) out.push(V.reasonSubbinUnknown);
  return out.join("; ");
}
const stateText = (s: boolean | null) => (s === null ? V.stateUnknown : s ? V.stateOn : V.stateOff);

export function Timeline({ result, cursor, onCursor }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const p = result.provenance.parameters.rules;
  // `short` labels the rows on narrow screens (the rule is in the full label, the tooltips and the intervals table)
  const rows: { key: string; label: string; short: string; color: string }[] = [
    { key: `sun_${p.sunlit}`, label: S.timeline.sunlit(RULE_NAMES[p.sunlit].toLowerCase()), short: V.tlSunlit, color: "#f2b544" },
    { key: `earth_${p.dte}`, label: S.timeline.earthInView(RULE_NAMES[p.dte].toLowerCase()), short: V.tlEarth, color: "#5fa8e8" },
    { key: "overlap", label: S.timeline.overlap, short: V.tlBoth, color: "#e9dfb8" },
  ];
  const W = Math.max(320, width);
  const narrow = W < 560;
  const m = { l: narrow ? 92 : 190, r: 12, t: 8, b: 26 };
  const rowH = 26, gap = 8, evH = 18;
  // Phase 3: a row of event markers (rise and set of each body, from the API's events) under the interval rows
  const evY = m.t + rows.length * (rowH + gap);
  const H = evY + evH + 6 + m.b;
  const [tip, setTip] = useState<{ k: number; px: number; py: number } | null>(null);
  const markers = result.events.filter((e) => e.function !== "ecl_contact");
  const t0 = new Date(result.window.start_utc).getTime();
  const t1 = new Date(result.window.end_utc).getTime();
  const x = useMemo(() => d3.scaleUtc().domain([t0, t1]).range([m.l, W - m.r]), [t0, t1, W]);
  const etToMs = (et: number) => t0 + (et - result.window.start_et) * 1000;
  const curEt = result.series.et[cursor];
  const tickFormat = timeLocale.utcFormat(S.timeline.tickFormat);
  const eclipses = result.events.filter((e) => e.function === "ecl_contact");

  const bar = (iv: Interval, color: string, yy: number, k: number, label: string) => {
    const xa = x(etToMs(iv.start_et)), xb = x(etToMs(iv.end_et));
    const w = Math.max(1, xb - xa);
    const tip = V.intervalTitle(label, stateText(iv.state), fmtUTC(iv.start_utc), fmtUTC(iv.end_utc), fmtDuration(iv.duration_h), intervalNotes(iv));
    if (iv.state === null) return <rect key={k} x={xa} y={yy} width={w} height={rowH} fill="url(#tl-hatch)"><title>{tip}</title></rect>;
    // off periods (darkness, Earth out of view): transparent hit area so they have a tooltip too
    if (!iv.state) return <rect key={k} x={xa} y={yy} width={w} height={rowH} fill="#ffffff" fillOpacity={0.001}><title>{tip}</title></rect>;
    return (
      <g key={k}>
        <title>{tip}</title>
        <rect x={xa} y={yy} width={w} height={rowH} fill={color} fillOpacity={0.9}
              stroke={iv.uncertain ? "#ee9a6b" : "none"} strokeDasharray={iv.uncertain ? "3 2" : undefined} />
        {iv.brief && <path d={`M${xa + w / 2 - 4},${yy - 1} l4,-6 l4,6 z`} fill="#ee9a6b" />}
      </g>
    );
  };

  // event markers: hover shows the event (HTML panel; the event list beside the chart is the keyboard way in)
  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const ux = ((e.clientX - r.left) / r.width) * W, uy = ((e.clientY - r.top) / r.height) * H;
    if (uy < evY - 2 || uy > evY + evH + 2 || !markers.length) { if (tip) setTip(null); return; }
    let best = -1, bd = 7;
    markers.forEach((ev, k) => { const d = Math.abs(x(etToMs(ev.et)) - ux); if (d < bd) { bd = d; best = k; } });
    setTip(best < 0 ? null : { k: best, px: e.clientX - r.left, py: e.clientY - r.top });
  };
  const colorOf = (target: string) => (target === "sun" ? BODY_COLORS.sun : BODY_COLORS.earth);

  return (
    <div className="timeline-wrap" ref={ref}>
      <div className="chart-box">
      <svg viewBox={`0 0 ${W} ${H}`} role="img"
           aria-label={S.timeline.label}
           onMouseMove={onMove}
           onMouseLeave={() => setTip(null)}
           onClick={(e) => {
             const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
             const ms = x.invert(((e.clientX - r.left) / r.width) * W).getTime();
             const et = result.window.start_et + (ms - t0) / 1000;
             const idx = d3.bisectLeft(result.series.et, et);
             onCursor(Math.max(0, Math.min(result.series.et.length - 1, idx)));
           }}>
        <defs>
          <pattern id="tl-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="6" stroke="#ee9a6b" strokeWidth="1.4" />
          </pattern>
        </defs>
        {rows.map((row, i) => {
          const yy = m.t + i * (rowH + gap);
          return (
            <g key={row.key}>
              <rect x={m.l} y={yy} width={W - m.l - m.r} height={rowH} fill="#1e2a37" />
              <text x={m.l - 10} y={yy + rowH / 2 + 4} textAnchor="end" fontSize={narrow ? 10.5 : 12.5} fill="#e7ecf1">{narrow ? row.short : row.label}</text>
              {(result.intervals[row.key] ?? []).map((iv, k) => bar(iv, row.color, yy, k, row.label))}
            </g>
          );
        })}
        <text x={m.l - 10} y={evY + evH / 2 + 4} textAnchor="end" fontSize={narrow ? 10.5 : 12.5} fill="#a3b1bf">{S.analysis.eventsAxis}</text>
        <line x1={m.l} x2={W - m.r} y1={evY + evH / 2} y2={evY + evH / 2} stroke="#2a3a4b" />
        {markers.map((ev, k) => {
          const cx = x(etToMs(ev.et)), up = ev.direction > 0, c = colorOf(ev.target);
          const d = up ? `M${cx - 5},${evY + evH - 3} L${cx},${evY + 3} L${cx + 5},${evY + evH - 3} Z`
            : `M${cx - 5},${evY + 3} L${cx},${evY + evH - 3} L${cx + 5},${evY + 3} Z`;
          return <path key={`ev${k}`} d={d} fill={up ? c : "#1b2633"} stroke={c} strokeWidth={1.2} opacity={tip?.k === k ? 1 : 0.9} />;
        })}
        {eclipses.map((ev, i) => (
          <line key={i} x1={x(etToMs(ev.et))} x2={x(etToMs(ev.et))} y1={m.t} y2={H - m.b} stroke="#cfe6fb" strokeDasharray="1 3" />
        ))}
        {spacedTicks(x, x.ticks(Math.max(2, Math.floor((W - m.l - m.r) / 120)))).map((t) => (
          <g key={t.getTime()}>
            <line x1={x(t)} x2={x(t)} y1={H - m.b} y2={H - m.b + 4} stroke="#7d8d9d" />
            <text x={x(t)} y={H - 8} textAnchor="middle" fontSize="11" fill="#a3b1bf">{tickFormat(t)}</text>
          </g>
        ))}
        <line x1={x(etToMs(curEt))} x2={x(etToMs(curEt))} y1={m.t - 4} y2={H - m.b} stroke="#ffd98a" strokeWidth={1.5} />
      </svg>
      {tip && markers[tip.k] && (
        <ChartTooltip x={tip.px} y={tip.py} boxWidth={ref.current?.clientWidth ?? W}>
          <strong>{markers[tip.k].name}</strong>
          <dl>
            <div><dt>{S.eventsTable.time}</dt><dd>{fmtUTC(markers[tip.k].utc, true)}</dd></div>
            <div><dt>{S.eventsTable.body}</dt><dd>{markers[tip.k].target === "sun" ? S.common.bodies.sun : S.common.bodies.earth}</dd></div>
          </dl>
        </ChartTooltip>
      )}
      </div>
      <ul className="legend timeline-legend" aria-label={V.timelineHint}>
        <li><i className="sw sw-sun" aria-hidden />{V.tlSunlit}</li>
        <li><i className="sw sw-earth" aria-hidden />{V.tlEarth}</li>
        <li><i className="sw sw-both" aria-hidden />{V.tlBoth}</li>
        <li><i className="sw sw-off" aria-hidden />{V.tlOff}</li>
        <li><i className="sw sw-unknown" aria-hidden />{V.tlUnknown}</li>
        <li><i className="sw sw-uncertain" aria-hidden />{V.tlUncertain}</li>
        <li><i className="sw tl-brief" aria-hidden />{V.tlBrief}</li>
        <li><i className="sw sw-eclipse" aria-hidden />{V.tlEclipse}</li>
        <li><i className="sw sw-cursor" aria-hidden />{V.tlCursor}</li>
        <li><i className="sw sw-rise" aria-hidden />{S.analysis.tlRise}</li>
        <li><i className="sw sw-set" aria-hidden />{S.analysis.tlSet}</li>
      </ul>
      <p className="hint">{V.timelineHint}</p>
      <IntervalsTable result={result} rows={rows} />
    </div>
  );
}

/** The timeline's intervals as a table (keyboard and screen-reader access to the same information, flags included). */
function IntervalsTable({ result, rows }: { result: Result; rows: { key: string; label: string }[] }) {
  const [open, setOpen] = useState(false);
  const all = rows.flatMap((row) => (result.intervals[row.key] ?? []).map((iv) => ({ row: row.label, iv })));
  return (
    <div className="intervals">
      <h3 className="intervals-head">{V.intervalsHeading(all.length)}{" "}
        <button className="toggle-intervals" onClick={() => setOpen(!open)} aria-expanded={open}>{open ? S.eventsTable.hide : S.eventsTable.show}</button></h3>
      {open && (
        <div className="table-scroll">
          <table className="data">
            <caption className="sr-only">{V.intervalsCaption}</caption>
            <thead><tr><th>{V.colRow}</th><th>{V.colState}</th><th>{V.colStart}</th><th>{V.colEnd}</th><th className="num">{V.colDuration}</th><th>{V.colNotes}</th></tr></thead>
            <tbody>{all.map(({ row, iv }, k) => (
              <tr key={k}><td>{row}</td><td>{stateText(iv.state)}</td><td>{fmtUTC(iv.start_utc, true)}</td><td>{fmtUTC(iv.end_utc, true)}</td>
                <td className="num">{fmtDuration(iv.duration_h)}</td><td>{intervalNotes(iv)}</td></tr>))}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}
