import * as d3 from "d3";
import { useMemo, useState } from "react";
import type { Interval, Result } from "../api/types";
import { S, timeLocale } from "../i18n";
import { RULE_NAMES, fmtDuration, fmtUTC } from "../lib/format";
import { useWidth } from "../lib/useWidth";

interface Props { result: Result; cursor: number; onCursor: (i: number) => void }

const V = S.viz;
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
  const rows: { key: string; label: string; color: string }[] = [
    { key: `sun_${p.sunlit}`, label: S.timeline.sunlit(RULE_NAMES[p.sunlit].toLowerCase()), color: "#f2b544" },
    { key: `earth_${p.dte}`, label: S.timeline.earthInView(RULE_NAMES[p.dte].toLowerCase()), color: "#5fa8e8" },
    { key: "overlap", label: S.timeline.overlap, color: "#e9dfb8" },
  ];
  const W = Math.max(320, width);
  const m = { l: 190, r: 12, t: 8, b: 26 };
  const rowH = 26, gap = 8;
  const H = m.t + rows.length * (rowH + gap) + m.b;
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

  return (
    <div className="timeline-wrap" ref={ref}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img"
           aria-label={S.timeline.label}
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
              <text x={m.l - 10} y={yy + rowH / 2 + 4} textAnchor="end" fontSize="12.5" fill="#e7ecf1">{row.label}</text>
              {(result.intervals[row.key] ?? []).map((iv, k) => bar(iv, row.color, yy, k, row.label))}
            </g>
          );
        })}
        {eclipses.map((ev, i) => (
          <line key={i} x1={x(etToMs(ev.et))} x2={x(etToMs(ev.et))} y1={m.t} y2={H - m.b} stroke="#cfe6fb" strokeDasharray="1 3" />
        ))}
        {x.ticks(Math.max(3, Math.floor(W / 140))).map((t) => (
          <g key={t.getTime()}>
            <line x1={x(t)} x2={x(t)} y1={H - m.b} y2={H - m.b + 4} stroke="#7d8d9d" />
            <text x={x(t)} y={H - 8} textAnchor="middle" fontSize="11" fill="#a3b1bf">{tickFormat(t)}</text>
          </g>
        ))}
        <line x1={x(etToMs(curEt))} x2={x(etToMs(curEt))} y1={m.t - 4} y2={H - m.b} stroke="#ffd98a" strokeWidth={1.5} />
      </svg>
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
