// Analysis time window check (E2E-07 correction, 2026-11-14). Dependency-free so scripts/check-window.mjs can import it.
//
// The sidebar stores start and end as UTC ISO strings ending in "Z" (lib/format fromInputValue), so the comparison is
// in UTC whatever the browser's time zone. The backend's rule is the same: the end must be strictly after the start.

/** Milliseconds since the epoch of a UTC ISO time, or NaN when it is missing or not a valid time. */
export function utcMs(iso: string | null | undefined): number {
  if (typeof iso !== "string" || iso.trim() === "") return NaN;
  return Date.parse(iso);
}

/** True only when both times are valid and the end is strictly after the start (equal times are not a window). */
export function windowValid(startIso: string | null | undefined, endIso: string | null | undefined): boolean {
  const a = utcMs(startIso), b = utcMs(endIso);
  return Number.isFinite(a) && Number.isFinite(b) && b > a;
}
