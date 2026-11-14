import type { Result } from "../api/types";
import { S } from "../i18n";
import { fmtLatLon, fmtUTC } from "../lib/format";

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
