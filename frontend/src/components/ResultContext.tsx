import type { Result } from "../api/types";
import { S } from "../i18n";
import { fmtLatLon, fmtUTC } from "../lib/format";
import { StatusBadge } from "../ui/StatusBadge";

// Phase 5 prompt 3: what kind of value each part of the result view is, and the site/observer/terrain context of the
// analysis. Every number is read from the result object (blueprint C09); nothing is estimated or filled in.

const V = S.viz;

/** Key to the four classes of information on the result page (calculated, measured, illustrative, unavailable). */
export function DataKey() {
  const items = [
    { cls: "calculated", name: V.keyCalculated, text: V.keyCalculatedText },
    { cls: "measured", name: V.keyMeasured, text: V.keyMeasuredText },
    { cls: "illustrative", name: V.keyIllustrative, text: V.keyIllustrativeText },
    { cls: "unavailable", name: V.keyUnavailable, text: V.keyUnavailableText },
  ];
  return (
    <details className="data-key">
      <summary>{V.keyHeading}</summary>
      <dl>
        {items.map((it) => (
          <div key={it.cls}>
            <dt><span className={`data-tag ${it.cls}`}>{it.name}</span></dt>
            <dd>{it.text}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}

const pct = (v: number) => (100 * v).toFixed(1);

/** Site, observer and terrain context of an analysis (all from the result's site, horizon and provenance fields). */
export function SiteContext({ r }: { r: Result }) {
  const h = r.horizon;
  const obs = r.provenance?.parameters?.observer ?? null;
  const levels: { level: string; pixel_m: number; product: string | null; synthetic: boolean; band_m?: number }[] =
    r.provenance?.horizon?.levels ?? h.levels;
  const stepMin = (r.series.step_s / 60).toFixed(0);
  return (
    <section className="context-grid" aria-label={V.contextHeading}>
      <div className="context-card">
        <h3>{V.contextSite} <span className="data-tag calculated">{V.keyCalculated}</span></h3>
        <p className="context-main">{fmtLatLon(r.site.lat, r.site.lon)}</p>
        <p>{S.globe.signed(r.site.lat.toFixed(6), r.site.lon.toFixed(6))}</p>
        <p>{V.ground(r.site.ground_h_m.toFixed(1), r.site.terrain_level_at_site)}</p>
      </div>
      <div className="context-card">
        <h3>{V.contextObserver} / {V.contextWindow}</h3>
        <p>{obs ? V.observer(obs.label, Number(obs.height_m).toFixed(1)) : S.common.na}</p>
        <p>{V.window(fmtUTC(r.window.start_utc), fmtUTC(r.window.end_utc), stepMin)}</p>
      </div>
      <div className="context-card">
        <h3>{V.contextHorizon} <span className="data-tag calculated">{V.keyCalculated}</span></h3>
        <p>{V.horizonRange(h.min_deg.toFixed(2), h.max_deg.toFixed(2), h.nbins, String(h.bin_deg))}</p>
        <p>{h.incomplete_share > 0 ? V.horizonIncomplete(pct(h.incomplete_share)) : V.horizonComplete}</p>
        {h.near_field_share != null && h.near_field_share > 0 && <p>{V.nearField(pct(h.near_field_share))}</p>}
        <p className="hint">{h.sigma_deg ? V.sigma : V.noSigma}</p>
      </div>
      <div className="context-card">
        <h3>{V.contextTerrain} <span className="data-tag measured">{V.keyMeasured}</span></h3>
        <ul>
          {levels.map((lv) => (
            <li key={lv.level}>
              {V.level(lv.level, String(lv.pixel_m), lv.band_m != null ? (lv.band_m / 1000).toFixed(0) : S.common.na, lv.product ?? S.common.unknown)}
              {lv.synthetic && <> <span className="data-tag unavailable">{V.synthetic}</span></>}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

const A = S.analysis;
const QUANTITY_NAMES: Record<string, string> = S.quantities;
const short = (v: unknown, n = 12) => (typeof v === "string" && v.length > n ? `${v.slice(0, n)}…` : v == null || v === "" ? S.common.na : String(v));

/**
 * LUNA-OPS 2.0 Phase 3: every validation label of the result with each test's status in the API's own words, and the
 * run's provenance as recorded by the engine (result.provenance). Nothing is summarised into a score; a quantity is
 * shown as the API labels it ("Validated" only when the engine says so).
 */
export function ValidationPanel({ r }: { r: Result }) {
  const p = r.provenance ?? {};
  const products: { level?: string; product?: string; sha256?: string; used_for_this_site?: boolean; synthetic?: boolean }[] =
    p.terrain?.products ?? [];
  const used = products.filter((x) => x.used_for_this_site);
  const rows: [string, string, string?][] = [
    [A.pvAlgorithm, short(p.algorithm_version, 40)],
    [A.pvCode, short(p.code_version, 40), p.code_fingerprint ? A.pvFingerprint(short(p.code_fingerprint, 16)) : undefined],
    [A.pvReport, short(p.validation_report_sha256, 16)],
    [A.pvLabelRules, short(p.label_rules_digest, 16)],
    [A.pvKernels, p.kernels ? A.pvKernelsValue(short(p.kernels.profile, 30), short(p.kernels.frame, 40)) : S.common.na,
      Array.isArray(p.kernels?.coverage_utc) ? A.pvCoverage(fmtUTC(p.kernels.coverage_utc[0]), fmtUTC(p.kernels.coverage_utc[1])) : undefined],
    [A.pvHorizonKey, short(p.horizon?.key, 24)],
    [A.pvInterpolation, short(p.terrain?.interpolation, 80)],
    [A.pvAberration, short(p.aberration, 40)],
    [A.pvRefraction, short(p.refraction, 60)],
    [A.pvEarthShape, short(p.earth_shape?.model, 120)],
    [A.pvResult, short(r.id, 24), A.pvSha(short(r.sha256, 16))],
  ];
  return (
    <div className="validation-panel">
      <div className="table-scroll validation-table">
        <table className="data">
          <caption className="sr-only">{A.valCaption}</caption>
          <thead><tr><th scope="col">{A.colQuantity}</th><th scope="col">{A.colKind}</th>
            <th scope="col">{A.colTests}</th><th scope="col">{A.colReasons}</th></tr></thead>
          <tbody>
            {Object.entries(r.labels).map(([k, v]) => (
              <tr key={k}>
                <th scope="row">{QUANTITY_NAMES[k] ?? k}</th>
                <td>{v.kind}</td>
                <td><ul className="test-list">{Object.entries(v.tests).map(([t, st]) => <li key={t}><StatusBadge word={st} prefix={t} /></li>)}</ul></td>
                <td>{(v.reasons ?? []).length ? (v.reasons ?? []).join("; ") : S.common.na}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="hint">{A.valNote}</p>
      <div className="provenance">
        <h3>{A.pvHeading}</h3>
        <dl className="provenance-list">
          {rows.map(([k, v, sub]) => <div key={k}><dt>{k}</dt><dd><span className="mono">{v}</span>{sub && <span className="provenance-sub">{sub}</span>}</dd></div>)}
        </dl>
        {used.length > 0 && (
          <>
            <h4>{A.pvProducts}</h4>
            <ul className="provenance-products">
              {used.map((x, k) => (
                <li key={k}><strong>{short(x.level, 12)}</strong> {short(x.product, 140)} <span className="mono provenance-sub">{A.pvSha(short(x.sha256, 16))}</span>
                  {x.synthetic && <> <span className="data-tag unavailable">{V.synthetic}</span></>}</li>
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  );
}
