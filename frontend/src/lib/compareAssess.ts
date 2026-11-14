// Compare summary: transparent, criteria-based assessments of calculated values (no scores, no default thresholds).
// A site is "favourable" for an objective only when the user entered at least one criterion for it and every entered
// criterion is met by the calculated value; "review" when any entered criterion is not met; "insufficient" when the
// values needed are missing (or the terrain product is too coarse); "not_assessed" when no criterion was entered.

export const VERDICTS = ["favourable", "review", "insufficient", "not_assessed"] as const;
export type Verdict = (typeof VERDICTS)[number];
const [FAVOURABLE, REVIEW, INSUFFICIENT, NOT_ASSESSED] = VERDICTS;

/** a criterion as typed (empty or not a number = not set) */
export const criterion = (v: string | undefined): number | null =>
  v == null || v.trim() === "" || !Number.isFinite(Number(v)) ? null : Number(v);

export interface Check { key: string; value: number; limit: number; atLeast: boolean; met: boolean }

/** one check per entered criterion; a value that is missing makes the objective "insufficient" */
export function runChecks(items: { key: string; value: number | null | undefined; limit: number | null; atLeast: boolean }[]):
  { checks: Check[]; missing: string[] } {
  const checks: Check[] = [];
  const missing: string[] = [];
  for (const it of items) {
    if (it.limit == null) continue;
    if (it.value == null || !Number.isFinite(it.value)) { missing.push(it.key); continue; }
    checks.push({ key: it.key, value: it.value, limit: it.limit, atLeast: it.atLeast,
                  met: it.atLeast ? it.value >= it.limit : it.value <= it.limit });
  }
  return { checks, missing };
}

export function verdictOf(checks: Check[], missing: string[], dataOk: boolean): Verdict {
  if (!dataOk || missing.length) return INSUFFICIENT;
  if (!checks.length) return NOT_ASSESSED;
  return checks.every((c) => c.met) ? FAVOURABLE : REVIEW;
}

/** the site with the best value of one metric, the runner-up's value, and whether the two are too close to call */
export interface Lead { index: number; value: number; runnerUp: number; tie: boolean; flagged: boolean }
export function leadOf(values: (number | null | undefined)[], higherIsBetter: boolean, tolerance: number,
                       flagged: boolean[] = []): Lead | null {
  const ok = values.map((v, i) => ({ v, i })).filter((x): x is { v: number; i: number } => x.v != null && Number.isFinite(x.v));
  if (ok.length < 2) return null;
  ok.sort((a, b) => (higherIsBetter ? b.v - a.v : a.v - b.v));
  const [best, second] = ok;
  return { index: best.i, value: best.v, runnerUp: second.v, tie: Math.abs(best.v - second.v) <= tolerance,
           flagged: !!flagged[best.i] || !!flagged[second.i] };
}

/** event function of the engine's rise/set events for a visibility rule (any part / centre / whole disk) */
export const EVENT_FN: Record<string, string> = { any: "top", centre: "c", full: "bot" };
