import { S } from "../i18n";
import { lon360 } from "./moonGeo";

// Text comes from src/i18n/en.ts (C10); this file only arranges numbers and dates into it.
const F = S.format;
const MONTHS = F.timeLocale.shortMonths;

export function fmtUTC(iso: string, withSeconds = false): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/.exec(iso);
  if (!m) return iso;
  const [, y, mo, d, h, mi, s] = m;
  return F.utc(Number(d), MONTHS[Number(mo) - 1], y, withSeconds ? F.timeHMS(h, mi, s) : F.timeHM(h, mi));
}

export function fmtShortDate(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(iso);
  return m ? F.shortDate(Number(m[3]), MONTHS[Number(m[2]) - 1], F.timeHM(m[4], m[5])) : iso;
}

export function fmtDuration(hours: number | null | undefined): string {
  if (hours == null || !isFinite(hours)) return S.common.na;
  const totalMin = Math.round(hours * 60);
  if (totalMin < 1) return F.lessThanOneMinute;
  const d = Math.floor(totalMin / 1440);
  const h = Math.floor((totalMin % 1440) / 60);
  const m = totalMin % 60;
  if (d > 0) return F.durationDays(d, h);
  if (h > 0) return F.durationHours(h, m);
  return F.durationMinutes(m);
}

export function fmtCountdown(seconds: number): string {
  if (seconds < 0) return F.countdownPassed;
  return fmtDuration(seconds / 3600);
}

export const fmtDeg = (v: number | null | undefined, d = 2) => (v == null || !isFinite(v) ? S.common.na : F.degrees(v.toFixed(d)));
export const fmtPct = (v: number | null | undefined, d = 1) => (v == null || !isFinite(v) ? S.common.na : F.percent(v.toFixed(d)));
export const fmtNum = (v: number | null | undefined, d = 3) => (v == null || !isFinite(v) ? S.common.na : v.toFixed(d));

/** Display names of the visibility rules, keyed by the API's rule value. */
export const RULE_NAMES: Record<string, string> = S.rules;

/** Display names of the reference panels, keyed by the API's panel model. */
export const PANEL_NAMES: Record<string, string> = S.panels;

export function isoNoMs(d: Date): string {
  return d.toISOString().replace(/\.\d{3}Z$/, "Z");
}

export function toInputValue(iso: string): string {
  return iso.replace(/Z$/, "").slice(0, 16);
}

export function fromInputValue(v: string): string {
  return v.length === 16 ? `${v}:00Z` : v.endsWith("Z") ? v : `${v}Z`;
}

/** Visible fraction as a percentage that never rounds a partial disk up to 100% or down to 0%. */
export function fmtFraction(v: number | null | undefined): string {
  if (v == null || !isFinite(v)) return S.common.unknown;
  if (v >= 1) return F.percent("100");
  if (v <= 0) return F.percent("0");
  const p = v * 100;
  return F.percent(Math.min(99.9, Math.max(0.1, p)).toFixed(p < 10 || p > 90 ? 1 : 0));
}

/** A location as shown everywhere (globe, explorer, analysis): "89.463° S, 222.510° E" (east longitude 0-360). */
export function fmtLatLon(lat: number, lon: number, d = 3): string {
  const G = S.globe;
  // round first, then normalise: 359.9999996 shows as 0.000 E (never 360.000) and -0.0001 as 0.000 N (never "0.000 S")
  const la = Number(lat.toFixed(d));
  let lo = Number(lon360(lon).toFixed(d));
  if (lo >= 360) lo -= 360;
  return G.selected(G.latText(Math.abs(la).toFixed(d), la >= 0), G.lonText(Math.abs(lo).toFixed(d)));
}
