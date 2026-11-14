import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Comparison } from "../api/types";
import { S } from "../i18n";
import { fmtNum, fmtPct } from "../lib/format";

// Site verdict (2026-11-14): after a comparison, one plain line per site saying what it is good for (landing,
// communication, sun, visibility). Each rating comes from one calculated value checked against a stated guideline
// threshold shown next to it: sunlit time, Earth in view, both at once, and the median footprint slope from the
// Landing tab's terrain screening (run here once per site with the Landing tab's defaults).

const V = S.compare.verdict;
const RATINGS = ["good", "limited", "poor", "unknown"] as const;
type Rating = (typeof RATINGS)[number];
const [GOOD, LIMITED, POOR, UNKNOWN] = RATINGS;
// guideline thresholds [good at or above / below, limited at or above / below]
const SUN = [50, 20], EARTH = [50, 20], BOTH = [30, 10], SLOPE = [8, 15];
const atLeast = (v: number | null | undefined, [g, l]: number[]): Rating =>
  v == null || !Number.isFinite(v) ? UNKNOWN : v >= g ? GOOD : v >= l ? LIMITED : POOR;
const atMost = (v: number | null | undefined, [g, l]: number[]): Rating =>
  v == null || !Number.isFinite(v) ? UNKNOWN : v <= g ? GOOD : v <= l ? LIMITED : POOR;

interface Props { cmp: Comparison; win: number; sr: string; dr: string; siteName: (si: number) => string }

export function SiteVerdict({ cmp, win, sr, dr, siteName }: Props) {
  const nW = cmp.windows.length;
  // median footprint slope per site (null = terrain too coarse or unavailable), fetched once per comparison
  const [slope, setSlope] = useState<{ id: string; v: (number | null | undefined)[] }>({ id: "", v: [] });
  useEffect(() => {
    let live = true;
    (async () => {
      const out: (number | null)[] = [];
      for (const s0 of cmp.sites) {
        try {
          const a = await api.landingAssess({ lat: s0.lat, lon: s0.lon, window_half_m: 1500, product: null, roughness_window_px: 5,
            min_depth_m: 1, min_diameter_m: null, max_diameter_m: null,
            footprint: { lat: s0.lat, lon: s0.lon, radius_m: 50, thresholds: { slope_deg: null, roughness_m: null, relief_m: null, min_valid_pct: 95 } } });
          const f = a.footprint?.findings?.find((x) => x.key === "slope");
          out.push(f && f.status !== "higher_res" && f.status !== "insufficient" ? f.stats?.median ?? null : null);
        } catch { out.push(null); }
        if (live) setSlope({ id: cmp.id, v: [...out] });
      }
    })();
    return () => { live = false; };
  }, [cmp.id, cmp.sites]);

  const rows = cmp.sites.map((_s, si) => {
    const cell = cmp.cells[si * nW + win], sum = cell?.summary;
    const sun = sum?.[`sun_${sr}`]?.percent as number | null | undefined;
    const earth = sum?.[`earth_${dr}`]?.percent as number | null | undefined;
    const both = sum?.overlap?.percent as number | null | undefined;
    const sl = slope.id === cmp.id ? slope.v[si] : undefined;
    const items: { key: keyof typeof V.objectives; r: Rating; why: string }[] = [
      { key: "landing", r: atMost(sl, SLOPE), why: sl === undefined ? V.checking : sl == null ? V.noTerrain : V.slopeWhy(fmtNum(sl, 1)) },
      { key: "communication", r: atLeast(earth, EARTH), why: V.earthWhy(fmtPct(earth)) },
      { key: "sun", r: atLeast(sun, SUN), why: V.sunWhy(fmtPct(sun)) },
      { key: "visibility", r: atLeast(both, BOTH), why: V.bothWhy(fmtPct(both)) },
    ];
    const list = (r: Rating) => items.filter((x) => x.r === r).map((x) => V.objectives[x.key].toLowerCase());
    return { si, items, error: cell?.error, good: list(GOOD), limited: list(LIMITED), poor: list(POOR) };
  });
  const join = (a: string[]) => (a.length < 2 ? a.join("") : `${a.slice(0, -1).join(", ")} ${V.and} ${a[a.length - 1]}`);
  const best = rows.length > 1 ? [...rows].sort((a, b) => b.good.length - a.good.length || a.poor.length - b.poor.length) : [];
  const bestTie = best.length > 1 && best[0].good.length === best[1].good.length && best[0].poor.length === best[1].poor.length;

  return (
    <section className="site-verdict" aria-labelledby="site-verdict-h">
      <h3 id="site-verdict-h">{V.heading}</h3>
      {best.length > 1 && <p className="verdict-best">{bestTie || !best[0].good.length ? V.noBest
        : V.recommend(siteName(best[0].si), join(best[0].good), best[0].poor.length ? join(best[0].poor) : null)}</p>}
      <ul className="verdict-sites">
        {rows.map((row) => (
          <li key={row.si} className="verdict-site">
            <h4>{siteName(row.si)}</h4>
            <p className="verdict-line">
              {row.error ? V.unavailable(row.error) : row.good.length ? V.goodFor(join(row.good)) : V.goodForNone}
              {row.limited.length > 0 && <> {V.limitedFor(join(row.limited))}</>}
              {row.poor.length > 0 && <> {V.poorFor(join(row.poor))}</>}
            </p>
            <ul className="verdict-items">
              {row.items.map((x) => (
                <li key={x.key}><span className="verdict-obj">{V.objectives[x.key]}</span>
                  <span className={`rating is-${x.r}`}>{V.rating[x.r]}</span><span className="verdict-val">{x.why}</span></li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
      <p className="hint">{V.note}</p>
    </section>
  );
}
