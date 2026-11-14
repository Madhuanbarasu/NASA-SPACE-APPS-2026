import type { Interval, Result } from "../api/types";

// Countdowns are lookups into the served interval lists: no scientific quantity is
// computed here (blueprint C09); the browser only finds the next served transition.
export interface NextChange { label: string; seconds: number | null; state: boolean | null; at: string | null }

export function nextChange(ivs: Interval[] | undefined, et: number, onLabel: string, offLabel: string): NextChange {
  if (!ivs || !ivs.length) return { label: onLabel, seconds: null, state: null, at: null };
  const i = ivs.findIndex((iv) => et >= iv.start_et && et < iv.end_et);
  if (i < 0) return { label: onLabel, seconds: null, state: null, at: null };
  const cur = ivs[i];
  for (let j = i + 1; j < ivs.length; j++) {
    if (ivs[j].state !== cur.state) {
      return { label: cur.state ? offLabel : onLabel, seconds: ivs[j].start_et - et, state: cur.state, at: ivs[j].start_utc };
    }
  }
  return { label: cur.state ? offLabel : onLabel, seconds: null, state: cur.state, at: null };
}

export function cursorEt(r: Result, cursor: number): number {
  return r.series.et[Math.max(0, Math.min(cursor, r.series.et.length - 1))];
}
