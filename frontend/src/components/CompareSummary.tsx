import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { CompareCell, Comparison, LandingFinding, Result } from "../api/types";
import { S } from "../i18n";
import { hasAny, linkBody } from "../lib/commsLink";
import { EVENT_FN, criterion, leadOf, runChecks, verdictOf, type Check, type Verdict } from "../lib/compareAssess";
import { fmtDuration, fmtNum, fmtPct, fmtUTC } from "../lib/format";
import { useStore, type CompareRf, type CompareTerrain } from "../state/store";

// UI simplification (Compare summary): one panel per mission objective (sunlight, Earth and communication, preliminary
// terrain) and a trade-off line. Every value is a field of a calculated result: the comparison cells (POST /api/compare),
// the cells' full results (GET /api/results/{id}: events and Sun/Earth series), the landing screening of each site
// (POST /api/landing/assess) and, only when the user entered a link budget, the RF evaluation (POST /api/comms/simulate).
// Assessments compare those values with criteria the user typed; there are no default limits and no overall score.

const T = S.compare.sum;
const C = T.crit;
const LANDING_HALF_M = 1500;        // the Landing tab's default analysis window (3 km square)
const LANDING_ROUGH_PX = 5;         // the Landing tab's default roughness window
const LANDING_MIN_DEPTH_M = 1;      // the Landing tab's default minimum depression depth
const LANDING_MIN_VALID_PCT = 95;   // the Landing tab's default minimum terrain data in the footprint
const DEFAULT_RADIUS_M = 50;        // the Landing tab's default footprint radius

const maxOf = (a: (number | null)[] | undefined) => {
  let m: number | null = null, k = -1;
  (a ?? []).forEach((v, i) => { if (v != null && Number.isFinite(v) && (m == null || v > m)) { m = v; k = i; } });
  return { max: m as number | null, index: k };
};

function VerdictChip({ v }: { v: Verdict }) {
  return <span className={`verdict is-${v}`}>{T.verdict[v]}</span>;
}

function Checks({ checks, missing, labels, units }: { checks: Check[]; missing: string[]; labels: Record<string, string>; units: Record<string, (x: number) => string> }) {
  if (!checks.length && !missing.length) return <p className="verdict-why">{T.noCriteria}</p>;
  return (
    <ul className="verdict-why">
      {checks.map((c) => <li key={c.key} className={c.met ? "is-met" : "is-unmet"}>{T.checkLine(labels[c.key], units[c.key](c.value), c.atLeast ? T.atLeast : T.atMost, units[c.key](c.limit), c.met)}</li>)}
      {missing.map((k) => <li key={k} className="is-unmet">{T.missingValue(labels[k])}</li>)}
    </ul>
  );
}

interface Props { cmp: Comparison; win: number; siteName: (si: number) => string; sr: string; dr: string; pm: string }

export function CompareSummary({ cmp, win, siteName, sr, dr, pm }: Props) {
  const { state, dispatch } = useStore();
  const crit = state.compareCriteria;
  const setCrit = (k: string, v: string) => dispatch({ type: "compareCriteria", criteria: { ...crit, [k]: v } });
  const nW = cmp.windows.length, nS = cmp.sites.length;
  const cells: (CompareCell | undefined)[] = Array.from({ length: nS }, (_, si) => cmp.cells[si * nW + win]);
  const extra = state.compareExtra?.cmpId === cmp.id ? state.compareExtra : null;
  const names = Array.from({ length: nS }, (_, si) => siteName(si));

  // full results of the cells (events and series), fetched once per result id
  const [full, setFull] = useState<Record<string, Result | null>>({});
  const ids = cells.map((c) => c?.result_id).filter((x): x is string => !!x);
  useEffect(() => {
    let live = true;
    (async () => {
      for (const id of ids) {
        if (id in full) continue;
        try { const r = await api.result(id); if (live) setFull((f) => ({ ...f, [id]: r })); }
        catch { if (live) setFull((f) => ({ ...f, [id]: null })); }
      }
    })();
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ids.join(",")]);

  // ---------------------------------------------------------------- sunlight
  const sun = cells.map((c) => (c?.summary ? c.summary[`sun_${sr}`] : null));
  const earth = cells.map((c) => (c?.summary ? c.summary[`earth_${dr}`] : null));
  const ov = cells.map((c) => c?.summary?.overlap ?? null);
  const pw = cells.map((c) => c?.summary?.power?.[pm] ?? null);
  const flaggedSun = sun.map((x) => !!x && ((x.unknown_hours ?? 0) > 0 || (x.uncertain_windows ?? 0) > 0));
  const flaggedEarth = earth.map((x) => !!x && ((x.unknown_hours ?? 0) > 0 || (x.uncertain_windows ?? 0) > 0));
  const fr = cells.map((c) => (c?.result_id ? full[c.result_id] ?? null : null));
  const firstEvent = (r: Result | null, target: "sun" | "earth", rule: string, dir: 1 | -1) =>
    (r?.events as { function: string; direction: number; utc: string }[] | undefined)?.find((e) => e.function === `${target}_${EVENT_FN[rule]}` && e.direction === dir) ?? null;

  const pct = (v: number) => fmtPct(v);
  const hrs = (v: number) => fmtDuration(v);
  const deg = (v: number) => S.format.degrees(fmtNum(v, 1));
  const metre = (v: number) => S.format.metres(fmtNum(v, 2));
  const sunAssess = sun.map((x, i) => {
    const r = runChecks([{ key: "sunPctMin", value: x?.percent, limit: criterion(crit.sunPctMin), atLeast: true },
                         { key: "darkMaxH", value: x?.longest_gap_h, limit: criterion(crit.darkMaxH), atLeast: false }]);
    return { ...r, verdict: verdictOf(r.checks, r.missing, !!x && !cells[i]?.error) };
  });
  const earthAssess = earth.map((x, i) => {
    const r = runChecks([{ key: "earthPctMin", value: x?.percent, limit: criterion(crit.earthPctMin), atLeast: true },
                         { key: "earthGapMaxH", value: x?.longest_gap_h, limit: criterion(crit.earthGapMaxH), atLeast: false },
                         { key: "overlapPctMin", value: ov[i]?.percent, limit: criterion(crit.overlapPctMin), atLeast: true }]);
    return { ...r, verdict: verdictOf(r.checks, r.missing, !!x && !cells[i]?.error) };
  });

  // ---------------------------------------------------------------- RF (only with the user's own link budget)
  const direct = state.commsInputs.direct;
  const haveLink = hasAny(direct);
  const rfKey = JSON.stringify(linkBody(direct));
  const [rfBusy, setRfBusy] = useState(false);
  const runRf = async () => {
    setRfBusy(true);
    const out: Record<number, CompareRf> = {};
    for (let i = 0; i < nS; i++) {
      const id = cells[i]?.result_id;
      if (!id) { out[i] = { ok: false, error: T.noData }; continue; }
      try {
        const res = await api.commsSimulate({ result_id: id, direct_link: linkBody(direct) });
        out[i] = { ok: true, complete: res.direct.link.complete, rfOpenH: res.comparison.direct_rf?.open_h ?? null,
                   geoOpenH: res.comparison.direct_geometric?.open_h ?? null, marginDb: res.direct.link.margin_db ?? null };
      } catch (e: any) { out[i] = { ok: false, error: String(e?.message || e) }; }
    }
    dispatch({ type: "compareExtra", extra: { ...(extra ?? { cmpId: cmp.id }), cmpId: cmp.id, rf: out, rfKey } });
    setRfBusy(false);
  };
  const rf = extra?.rf;
  const windowH = (Date.parse(cmp.windows[win].end_utc) - Date.parse(cmp.windows[win].start_utc)) / 3_600_000;

  // ---------------------------------------------------------------- preliminary terrain screening (Landing method)
  const radius = criterion(crit.fpRadius) ?? DEFAULT_RADIUS_M;
  const th = { slope_deg: criterion(crit.slopeMax), roughness_m: criterion(crit.roughMax), relief_m: criterion(crit.reliefMax), min_valid_pct: LANDING_MIN_VALID_PCT };
  const terrainKey = JSON.stringify({ radius, th });
  const [scr, setScr] = useState<{ k: number; n: number } | null>(null);
  const runTerrain = async () => {
    const out: Record<number, CompareTerrain> = {};
    for (let i = 0; i < nS; i++) {
      setScr({ k: i + 1, n: nS });
      const s0 = cmp.sites[i];
      try {
        const a = await api.landingAssess({ lat: s0.lat, lon: s0.lon, window_half_m: LANDING_HALF_M, product: null,
          roughness_window_px: LANDING_ROUGH_PX, min_depth_m: LANDING_MIN_DEPTH_M, min_diameter_m: null, max_diameter_m: null,
          footprint: { lat: s0.lat, lon: s0.lon, radius_m: radius, thresholds: th } });
        const fp = a.footprint;
        out[i] = { ok: true, product: a.provenance.dem.key, pixelM: a.provenance.dem.pixel_m, findings: fp?.findings ?? [],
                   coverage: fp?.coverage ?? null, pixelsAcross: fp?.pixels_across };
      } catch (e: any) { out[i] = { ok: false, error: String(e?.message || e) }; }
    }
    dispatch({ type: "compareExtra", extra: { ...(extra ?? { cmpId: cmp.id }), cmpId: cmp.id, terrain: out, terrainKey } });
    setScr(null);
  };
  const terr = extra?.terrain;
  const finding = (t: CompareTerrain | undefined, key: string): LandingFinding | undefined => t?.findings?.find((f) => f.key === key);
  const terrAssess = useMemo(() => Array.from({ length: nS }, (_, i) => {
    const t = terr?.[i];
    if (!t) return null;
    if (!t.ok) return { verdict: "insufficient" as Verdict, reasons: [T.terrain.error(t.error ?? S.common.unknown)] };
    const fs = ["slope", "roughness", "relief", "depressions"].map((k) => finding(t, k)).filter((f): f is LandingFinding => !!f);
    const reasons: string[] = [];
    let insufficient = false, hazard = false, assessed = false;
    for (const f of fs) {
      if (f.status === "higher_res" || f.status === "insufficient") { insufficient = true; reasons.push(`${f.status_text}${f.reason ? `: ${f.reason}` : ""}`); }
      else if (f.status === "hazard") { hazard = true; assessed = true; reasons.push(f.reason ?? f.status_text); }
      else if (f.status === "clear") { assessed = true; reasons.push(`${f.status_text}`); }
    }
    const verdict: Verdict = insufficient ? "insufficient" : hazard ? "review" : assessed ? "favourable" : "not_assessed";
    return { verdict, reasons: reasons.length ? [...new Set(reasons)] : [T.noCriteria] };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [terr, nS]);

  // ---------------------------------------------------------------- leads (who is ahead on each objective)
  const lead = (vals: (number | null | undefined)[], higher: boolean, tol: number, fl: boolean[], fmt: (v: number) => string,
                line: (site: string, a: string, b: string) => string, what: string) => {
    const l = leadOf(vals, higher, tol, fl);
    if (!l) return null;
    if (l.tie) return T.tie(what);
    return `${line(names[l.index], fmt(l.value), fmt(l.runnerUp))}${l.flagged ? ` ${T.caution}` : ""}`;
  };
  const sunLeads = [lead(sun.map((x) => x?.percent), true, 0.05, flaggedSun, pct, T.sun.leadPct, T.sun.whatPct),
                    lead(sun.map((x) => x?.longest_gap_h), false, 0.01, flaggedSun, hrs, T.sun.leadDark, T.sun.whatDark)].filter(Boolean) as string[];
  const earthLeads = [lead(earth.map((x) => x?.percent), true, 0.05, flaggedEarth, pct, T.earth.leadPct, T.earth.whatPct),
                      lead(earth.map((x) => x?.longest_gap_h), false, 0.01, flaggedEarth, hrs, T.earth.leadGap, T.earth.whatGap),
                      lead(ov.map((x) => x?.percent), true, 0.05, flaggedSun.map((f, i) => f || flaggedEarth[i]), pct, T.earth.leadOverlap, T.earth.whatOverlap)].filter(Boolean) as string[];
  const slopeMed = Array.from({ length: nS }, (_, i) => {
    const t = terr?.[i]; const f = finding(t, "slope");
    return t?.ok && f && f.status !== "higher_res" && f.status !== "insufficient" ? f.stats?.median ?? null : null;
  });
  const terrLeads = terr ? [lead(slopeMed, false, 0.05, [], deg, T.terrain.leadSlope, T.terrain.whatSlope)].filter(Boolean) as string[] : [];
  const headline = (vals: (number | null | undefined)[], higher: boolean, tol: number) => {
    const l = leadOf(vals, higher, tol); return l && !l.tie ? names[l.index] : null;
  };
  const tradeRows = [
    { obj: T.sun.heading, site: headline(sun.map((x) => x?.percent), true, 0.05) },
    { obj: T.earth.heading, site: headline(earth.map((x) => x?.percent), true, 0.05) },
    { obj: T.terrain.heading, site: terr ? headline(slopeMed, false, 0.05) : null },
  ];
  const anyCriteria = ["sunPctMin", "darkMaxH", "earthPctMin", "earthGapMaxH", "overlapPctMin", "slopeMax", "roughMax", "reliefMax"].some((k) => criterion(crit[k]) != null);
  const meetsAll = names.filter((_, i) => {
    const vs = [sunAssess[i].verdict, earthAssess[i].verdict, terrAssess[i]?.verdict ?? "not_assessed"].filter((v) => v !== "not_assessed");
    return vs.length > 0 && vs.every((v) => v === "favourable");
  });

  const critField = (k: keyof typeof C) => (
    <div className="field" key={k}>
      <label htmlFor={`crit-${k}`}>{C[k]}</label>
      <input id={`crit-${k}`} type="text" inputMode="decimal" value={crit[k] ?? ""} placeholder={k === "fpRadius" ? String(DEFAULT_RADIUS_M) : S.comms.link.notSet}
             onChange={(e) => setCrit(k, e.target.value)} aria-describedby={k === "fpRadius" ? "crit-fp-hint" : undefined} />
    </div>
  );
  const sunLabels = { sunPctMin: C.sunPctMin, darkMaxH: C.darkMaxH };
  const earthLabels = { earthPctMin: C.earthPctMin, earthGapMaxH: C.earthGapMaxH, overlapPctMin: C.overlapPctMin };

  return (
    <div className="cmp-summary">
      <p className="hint">{T.intro}</p>
      <p className="hint">{T.windowNote(fmtUTC(cmp.windows[win].start_utc), fmtUTC(cmp.windows[win].end_utc))}</p>

      <details className="cmp-criteria" open={anyCriteria || undefined}>
        <summary>{T.criteriaHeading}</summary>
        <p className="hint">{T.criteriaIntro}</p>
        <div className="crit-groups">
          <fieldset><legend>{T.critGroups.sun}</legend>{critField("sunPctMin")}{critField("darkMaxH")}</fieldset>
          <fieldset><legend>{T.critGroups.earth}</legend>{critField("earthPctMin")}{critField("earthGapMaxH")}{critField("overlapPctMin")}</fieldset>
          <fieldset><legend>{T.critGroups.terrain}</legend>{critField("slopeMax")}{critField("roughMax")}{critField("reliefMax")}{critField("fpRadius")}
            <p id="crit-fp-hint" className="hint">{T.fpRadiusHint}</p></fieldset>
        </div>
        <p className="hint">{T.verdictHelp}</p>
      </details>

      {/* trade-offs first: the answer to "which site is better for what" */}
      <section className="objective obj-trade" aria-labelledby="obj-trade-h">
        <h3 id="obj-trade-h">{T.trade.heading}</h3>
        <ul className="trade-list">
          {tradeRows.map((t) => <li key={t.obj}>{t.site ? T.trade.leads(t.obj, t.site) : T.trade.noLead(t.obj)}</li>)}
        </ul>
        <p className="hint">{!anyCriteria ? T.trade.noCriteria : meetsAll.length ? T.trade.allMet(meetsAll.join(", ")) : T.trade.noneMet}</p>
        <p className="hint">{T.trade.noScore}</p>
      </section>

      {/* sunlight */}
      <section className="objective obj-sun" aria-labelledby="obj-sun-h">
        <h3 id="obj-sun-h">{T.sun.heading}</h3>
        <p className="hint">{T.sun.intro}</p>
        {sunLeads.length ? <ul className="lead-list">{sunLeads.map((l) => <li key={l}>{l}</li>)}</ul> : <p className="hint">{T.leadNone}</p>}
        <div className="table-scroll"><table className="data obj-table">
          <thead><tr><th>{T.siteCol}</th><th className="num">{T.sun.cols.pct}</th><th className="num">{T.sun.cols.hours}</th><th className="num">{T.sun.cols.dark}</th>
            <th className="num">{T.sun.cols.windows}</th><th className="num">{T.sun.cols.power}</th><th className="num">{T.sun.cols.el}</th>
            <th>{T.sun.cols.rise}</th><th>{T.sun.cols.set}</th><th>{T.assessCol}</th></tr></thead>
          <tbody>{names.map((n, i) => {
            const x = sun[i], r = fr[i], el = maxOf(r?.series?.sun?.el as (number | null)[] | undefined);
            const rise = firstEvent(r, "sun", sr, 1), set = firstEvent(r, "sun", sr, -1);
            return (
              <tr key={n}><th scope="row">{n}</th>
                {!x ? <td colSpan={8} className="unavail">{cells[i]?.error ?? T.noData}</td> : <>
                  <td className="num">{fmtPct(x.percent)}</td><td className="num">{fmtDuration(x.hours)}</td><td className="num">{fmtDuration(x.longest_gap_h)}</td>
                  <td className="num">{x.windows}</td><td className="num">{fmtNum(pw[i]?.mean, 3)}</td>
                  <td className="num">{el.max == null ? S.common.na : deg(el.max)}</td>
                  <td>{rise ? fmtUTC(rise.utc) : S.common.na}</td><td>{set ? fmtUTC(set.utc) : S.common.na}</td></>}
                <td><VerdictChip v={sunAssess[i].verdict} />{flaggedSun[i] && <p className="verdict-why">{T.flagged}</p>}
                  <Checks checks={sunAssess[i].checks} missing={sunAssess[i].missing} labels={sunLabels} units={{ sunPctMin: pct, darkMaxH: hrs }} /></td>
              </tr>
            );
          })}</tbody>
        </table></div>
      </section>

      {/* Earth visibility and communication */}
      <section className="objective obj-earth" aria-labelledby="obj-earth-h">
        <h3 id="obj-earth-h">{T.earth.heading}</h3>
        <p className="hint">{T.earth.intro}</p>
        {earthLeads.length ? <ul className="lead-list">{earthLeads.map((l) => <li key={l}>{l}</li>)}</ul> : <p className="hint">{T.leadNone}</p>}
        <div className="obj-actions">
          {haveLink
            ? <button type="button" className="quiet-button" disabled={rfBusy} onClick={() => { void runRf(); }}>{rfBusy ? T.earth.rfRunning : T.earth.rfRun}</button>
            : <p className="hint">{T.earth.rfNotAssessed}</p>}
          {rf && extra?.rfKey !== rfKey && <p className="hint warn">{T.earth.rfStale}</p>}
        </div>
        <div className="table-scroll"><table className="data obj-table">
          <thead><tr><th>{T.siteCol}</th><th className="num">{T.earth.cols.pct}</th><th className="num">{T.earth.cols.gap}</th><th className="num">{T.earth.cols.windows}</th>
            <th className="num">{T.earth.cols.overlap}</th><th className="num">{T.earth.cols.el}</th><th className="num">{T.earth.cols.az}</th>
            <th className="num">{T.earth.cols.clr}</th><th>{T.earth.cols.rf}</th><th>{T.assessCol}</th></tr></thead>
          <tbody>{names.map((n, i) => {
            const x = earth[i], r = fr[i];
            const el = maxOf(r?.series?.earth?.el as (number | null)[] | undefined);
            const az = el.index >= 0 ? (r?.series?.earth?.az as (number | null)[] | undefined)?.[el.index] ?? null : null;
            const clr = maxOf(r?.series?.earth?.c as (number | null)[] | undefined);
            const q = rf?.[i];
            const rfText = !haveLink || !q ? T.earth.rfNotAssessed : !q.ok ? (q.error ?? S.common.unknown) : !q.complete ? T.earth.rfIncomplete
              : q.rfOpenH == null ? S.common.na : T.earth.rfValue(fmtDuration(q.rfOpenH), fmtPct(windowH > 0 ? (100 * q.rfOpenH) / windowH : null));
            return (
              <tr key={n}><th scope="row">{n}</th>
                {!x ? <td colSpan={7} className="unavail">{cells[i]?.error ?? T.noData}</td> : <>
                  <td className="num">{fmtPct(x.percent)}</td><td className="num">{fmtDuration(x.longest_gap_h)}</td><td className="num">{x.windows}</td>
                  <td className="num">{fmtPct(ov[i]?.percent)}</td><td className="num">{el.max == null ? S.common.na : deg(el.max)}</td>
                  <td className="num">{az == null ? S.common.na : deg(az)}</td><td className="num">{clr.max == null ? S.common.na : deg(clr.max)}</td></>}
                <td className="rf-cell">{rfText}</td>
                <td><VerdictChip v={earthAssess[i].verdict} />{flaggedEarth[i] && <p className="verdict-why">{T.flagged}</p>}
                  <Checks checks={earthAssess[i].checks} missing={earthAssess[i].missing} labels={earthLabels} units={{ earthPctMin: pct, earthGapMaxH: hrs, overlapPctMin: pct }} /></td>
              </tr>
            );
          })}</tbody>
        </table></div>
        <p className="hint">{T.earth.rfNote}</p>
      </section>

      {/* preliminary terrain assessment */}
      <section className="objective obj-terrain" aria-labelledby="obj-terrain-h">
        <h3 id="obj-terrain-h">{T.terrain.heading}</h3>
        <p className="hint">{T.terrain.intro}</p>
        {terrLeads.length > 0 && <ul className="lead-list">{terrLeads.map((l) => <li key={l}>{l}</li>)}</ul>}
        <div className="obj-actions">
          <button type="button" className="quiet-button" disabled={!!scr} onClick={() => { void runTerrain(); }}>{scr ? T.terrain.running(scr.k, scr.n) : T.terrain.run}</button>
          {terr && extra?.terrainKey !== terrainKey && <p className="hint warn">{T.terrain.stale}</p>}
        </div>
        {!terr ? <p className="hint">{T.terrain.notRun}</p> : (
          <div className="table-scroll"><table className="data obj-table">
            <thead><tr><th>{T.siteCol}</th><th>{T.terrain.cols.product}</th><th className="num">{T.terrain.cols.across}</th><th className="num">{T.terrain.cols.slope}</th>
              <th className="num">{T.terrain.cols.rough}</th><th className="num">{T.terrain.cols.relief}</th><th>{T.terrain.cols.dep}</th>
              <th>{T.terrain.cols.data}</th><th>{T.assessCol}</th></tr></thead>
            <tbody>{names.map((n, i) => {
              const t = terr[i]; const a = terrAssess[i];
              const sl = finding(t, "slope"), ro = finding(t, "roughness"), re = finding(t, "relief"), de = finding(t, "depressions");
              const ok = (f?: LandingFinding) => !!f && f.status !== "higher_res" && f.status !== "insufficient";
              return (
                <tr key={n}><th scope="row">{n}</th>
                  {!t || !t.ok ? <td colSpan={7} className="unavail">{t ? T.terrain.error(t.error ?? S.common.unknown) : T.noData}</td> : <>
                    <td className="mono">{t.product}</td>
                    <td className="num">{t.pixelsAcross == null ? S.common.na : T.terrain.pixels(fmtNum(t.pixelsAcross, 1))}</td>
                    <td className="num">{ok(sl) ? `${deg(sl!.stats?.median ?? NaN)} / ${deg(sl!.stats?.max ?? NaN)}` : T.terrain.coarse}</td>
                    <td className="num">{ok(ro) ? `${metre(ro!.stats?.median ?? NaN)} / ${metre(ro!.stats?.max ?? NaN)}` : T.terrain.coarse}</td>
                    <td className="num">{ok(re) && re!.stats?.value != null ? metre(re!.stats.value) : T.terrain.coarse}</td>
                    <td>{de?.status_text ?? S.common.na}</td>
                    <td>{T.terrain.dataValue(fmtPct(t.coverage?.valid_pct), t.coverage?.measured_pct == null ? S.common.na : fmtPct(t.coverage.measured_pct),
                      t.coverage?.height_sigma_m?.median == null ? S.common.na : metre(t.coverage.height_sigma_m.median))}</td></>}
                  <td>{a && <><VerdictChip v={a.verdict} /><ul className="verdict-why">{a.reasons.map((x) => <li key={x}>{x}</li>)}</ul></>}</td>
                </tr>
              );
            })}</tbody>
          </table></div>
        )}
      </section>
    </div>
  );
}
