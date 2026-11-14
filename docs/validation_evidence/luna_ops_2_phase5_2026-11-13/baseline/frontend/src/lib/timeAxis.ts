import * as d3 from "d3";
import type { Result } from "../api/types";
import { S, timeLocale } from "../i18n";

// LUNA-OPS 2.0 Phase 3: the one time axis shared by the analysis charts (event timeline, sunlight and Earth visibility).
// It only maps the result's own times (UTC strings and ET seconds) to pixels and back; nothing scientific is computed.

export interface TimeAxis {
  x: d3.ScaleTime<number, number>;
  /** window start and end, ms since the epoch (UTC) */
  t0: number; t1: number;
  /** ET seconds of the result to ms (UTC) */
  etToMs: (et: number) => number;
  /** ms (UTC) of display sample i */
  msOf: (i: number) => number;
  /** display sample at or after an ET (the convention of the existing charts) */
  idxAtEt: (et: number) => number;
  /** display sample nearest an ET (used when jumping to an event) */
  nearestIdx: (et: number) => number;
  /** display sample under a pointer x (client coordinates) on an element of `width` user units */
  idxAtClientX: (clientX: number, el: Element, width: number) => number;
  ticks: () => Date[];
  tickFormat: (d: Date) => string;
}

export function timeAxis(r: Result, left: number, right: number): TimeAxis {
  const t0 = new Date(r.window.start_utc).getTime(), t1 = new Date(r.window.end_utc).getTime();
  const et = r.series.et, n = et.length;
  const x = d3.scaleUtc().domain([t0, t1]).range([left, right]);
  const etToMs = (e: number) => t0 + (e - r.window.start_et) * 1000;
  const clamp = (i: number) => Math.max(0, Math.min(n - 1, i));
  const idxAtEt = (e: number) => clamp(d3.bisectLeft(et, e));
  const nearestIdx = (e: number) => {
    const i = idxAtEt(e);
    return i > 0 && Math.abs(et[i - 1] - e) <= Math.abs(et[i] - e) ? i - 1 : i;
  };
  const fmt = timeLocale.utcFormat(S.timeline.tickFormat);
  return {
    x, t0, t1, etToMs, msOf: (i) => etToMs(et[clamp(i)]), idxAtEt, nearestIdx,
    idxAtClientX: (clientX, el, width) => {
      const b = el.getBoundingClientRect();
      const ms = x.invert(((clientX - b.left) / b.width) * width).getTime();
      return idxAtEt(r.window.start_et + (ms - t0) / 1000);
    },
    // about one label per 120 px of plot, so dates never overlap on narrow screens
    ticks: () => spacedTicks(x, x.ticks(Math.max(2, Math.floor((right - left) / 120)))),
    tickFormat: (d) => fmt(d),
  };
}

/** Drops ticks closer than `minPx` to the previous kept one (d3's tick count is only a hint), so labels never overlap. */
export function spacedTicks(x: (d: Date) => number, ticks: Date[], minPx = 96): Date[] {
  const out: Date[] = [];
  let last = -Infinity;
  for (const t of ticks) { const px = x(t); if (px - last >= minPx) { out.push(t); last = px; } }
  return out;
}

/** Runs of consecutive indices where `missing(i)` holds, as [first, last] pairs. */
export function runs(n: number, missing: (i: number) => boolean): [number, number][] {
  const out: [number, number][] = [];
  let a = -1;
  for (let i = 0; i < n; i++) {
    const m = missing(i);
    if (m && a < 0) a = i;
    if (!m && a >= 0) { out.push([a, i - 1]); a = -1; }
  }
  if (a >= 0) out.push([a, n - 1]);
  return out;
}
