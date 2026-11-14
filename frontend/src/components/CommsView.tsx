import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import type { CommsBreakdown, CommsDtnForm, CommsInputs, CommsLink, CommsLinkForm, CommsRelayForm, CommsRow, CommsStats } from "../api/types";
import { S } from "../i18n";
import { fmtDuration, fmtLatLon, fmtNum, fmtUTC } from "../lib/format";
import { landingKey, useStore } from "../state/store";
import { CommsTimeline, ElevationChart } from "./CommsCharts";
import { useSiteCoverage } from "./SiteExplorer";
import { Metric } from "../ui/Metric";
import { StatusBadge } from "../ui/StatusBadge";
import { ViewHeader } from "../ui/ViewHeader";

// LUNA-OPS 2.0 Phase 6: Mission communication simulation. Direct-to-Earth geometry and its validation labels come
// unchanged from a completed engine analysis (the same result the Site tab shows); the separate lunaops_comms backend
// adds the user-configured RF link budgets, a hypothetical relay's two legs, availability timelines, comparison
// statistics and a conceptual store-and-forward planner, all labelled preliminary. Nothing is assumed: an empty field
// stays empty and the dependent results stay "not evaluated". Geometric visibility, RF feasibility and availability are
// shown apart; there are no scores or recommendations.

const C = S.comms;
const DEBOUNCE_MS = 500;
const TAB_COMMS = "comms" as const;
const NEAR = 1e-6;
const LINK_KEYS = ["direct", "up", "down"] as const;
type LinkKey = (typeof LINK_KEYS)[number];
const DTN_PATHS = ["direct_rf", "earth_visible", "relay_rf", "relay_geometric", "any_rf", "any_geometric"] as const;
const num = (v: string | undefined): number | null => (v == null || v.trim() === "" || !isFinite(Number(v)) ? null : Number(v));
const scaled = (v: string | undefined, k: number) => { const n = num(v); return n == null ? null : n * k; };
const same = (a: { lat: number; lon: number }, b: { lat: number; lon: number }) =>
  Math.abs(a.lat - b.lat) < NEAR && Math.abs(((a.lon - b.lon + 540) % 360) - 180) < NEAR;

function linkBody(f: CommsLinkForm) {
  const p = num(f.power);
  return { pt_w: f.powerUnit === "dbw" ? null : p, pt_dbw: f.powerUnit === "dbw" ? p : null, gt_dbi: num(f.gt), ltx_db: num(f.ltx),
    gr_dbi: num(f.gr), lrx_db: num(f.lrx), lother_db: num(f.lother), ts_k: num(f.ts), freq_hz: scaled(f.freqMHz, 1e6),
    bandwidth_hz: scaled(f.bwkHz, 1e3), rb_bps: scaled(f.rbkbps, 1e3), ebn0_req_db: num(f.ebn0),
    basis: f.basis === "specification" ? "specification" : "illustrative", reference: f.reference?.trim() || null };
}
const hasAny = (f: CommsLinkForm) => Object.entries(f).some(([k, v]) => k !== "basis" && k !== "powerUnit" && !!v && v.trim() !== "");

function relayBody(r: CommsRelayForm) {
  return { name: r.name?.trim() || null, a_km: num(r.a), e: num(r.e), i_deg: num(r.i), raan_deg: num(r.raan), argp_deg: num(r.argp),
    m0_deg: num(r.m0), epoch_utc: r.epoch?.trim() || null, frame: r.frame === "J2000" ? "J2000" : r.frame === "LME_EPOCH" ? "LME_EPOCH" : null,
    step_s: num(r.step) ?? 60, grazing_alt_km: num(r.graze) ?? 0 };
}

function body(rid: string, inp: CommsInputs) {
  const dtnOk = num(inp.dtn.volume) != null && num(inp.dtn.rate) != null;
  return {
    result_id: rid,
    direct_link: hasAny(inp.direct) ? linkBody(inp.direct) : null,
    relay: inp.relayOn ? relayBody(inp.relay) : null,
    relay_up_link: inp.relayOn && hasAny(inp.up) ? linkBody(inp.up) : null,
    relay_down_link: inp.relayOn && hasAny(inp.down) ? linkBody(inp.down) : null,
    dtn: dtnOk ? { volume_mbit: num(inp.dtn.volume), rate_kbps: num(inp.dtn.rate), path: inp.dtn.path || "direct_rf",
                   start_utc: inp.dtn.start?.trim() || null } : null,
  };
}

const h = (v: number | null | undefined) => (v == null ? S.common.na : fmtDuration(v));

// ---------------------------------------------------------------- link form and breakdown
function LinkForm({ id, f, onChange }: { id: string; f: CommsLinkForm; onChange: (f: CommsLinkForm) => void }) {
  const L = C.link;
  const field = (k: keyof CommsLinkForm, label: string, unit: string) => (
    <div className="field" key={k}>
      <label htmlFor={`${id}-${k}`}>{L.field(label, unit)}</label>
      <input id={`${id}-${k}`} type="text" inputMode="decimal" placeholder={L.notSet} value={f[k] ?? ""}
             onChange={(e) => onChange({ ...f, [k]: e.target.value })} />
    </div>
  );
  return (
    <div className="comms-linkform">
      <div className="comms-linkform-groups">
      <fieldset>
        <legend>{L.tx}</legend>
        <div className="field-row">
          <div className="field">
            <label htmlFor={`${id}-power`}>{L.field(L.power, f.powerUnit === "dbw" ? L.unitDbw : L.unitW)}</label>
            <input id={`${id}-power`} type="text" inputMode="decimal" placeholder={L.notSet} value={f.power ?? ""}
                   onChange={(e) => onChange({ ...f, power: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor={`${id}-pu`}>{L.powerUnit}</label>
            <select id={`${id}-pu`} value={f.powerUnit ?? "w"} onChange={(e) => onChange({ ...f, powerUnit: e.target.value })}>
              <option value="w">{L.unitW}</option><option value="dbw">{L.unitDbw}</option>
            </select>
          </div>
        </div>
        <div className="field-row">{field("gt", L.gt, L.dbi)}{field("ltx", L.ltx, L.db)}</div>
      </fieldset>
      <fieldset>
        <legend>{L.rx}</legend>
        <div className="field-row">{field("gr", L.gr, L.dbi)}{field("lrx", L.lrx, L.db)}</div>
        <div className="field-row">{field("ts", L.ts, L.kelvin)}{field("lother", L.lother, L.db)}</div>
      </fieldset>
      <fieldset>
        <legend>{L.signal}</legend>
        <div className="field-row">{field("freqMHz", L.freq, L.mhz)}{field("bwkHz", L.bw, L.khz)}</div>
        <div className="field-row">{field("rbkbps", L.rb, L.kbps)}{field("ebn0", L.ebn0, L.db)}</div>
      </fieldset>
      </div>
      <div className="field-row">
        <div className="field">
          <label htmlFor={`${id}-basis`}>{L.basisLabel}</label>
          <select id={`${id}-basis`} value={f.basis ?? "illustrative"} onChange={(e) => onChange({ ...f, basis: e.target.value })}>
            <option value="illustrative">{L.illustrative}</option><option value="specification">{L.specification}</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${id}-ref`}>{L.reference}</label>
          <input id={`${id}-ref`} type="text" placeholder={L.optional} value={f.reference ?? ""} onChange={(e) => onChange({ ...f, reference: e.target.value })} />
        </div>
      </div>
    </div>
  );
}

function Breakdown({ link, title }: { link: CommsLink | undefined; title: string }) {
  const L = C.link;
  if (!link) return null;
  const tables: [string, CommsBreakdown | undefined][] = [[L.atMin, link.at_min_distance], [L.atMax, link.at_max_distance]];
  const problems = Object.values(link.problems ?? {});
  return (
    <div className="comms-breakdown">
      <p className="comms-linkstatus">
        <strong>{title}</strong>{" "}
        <span className={`finding-status ${link.complete ? "is-clear" : "is-insufficient"}`}>{link.complete ? L.complete : L.incomplete}</span>
        {link.margin_db && <span className="mono">{" "}{L.marginRange(fmtNum(link.margin_db.min, 2), fmtNum(link.margin_db.max, 2))}</span>}
      </p>
      {problems.length > 0 && <ul className="hint bad">{problems.map((p, i) => <li key={i}>{p}</li>)}</ul>}
      <p className="hint">{link.basis}{link.reference ? ` (${link.reference})` : ""}</p>
      {link.notes.map((n, i) => <p key={i} className="hint mono">{n}</p>)}
      <div className="comms-breakdown-tables">
      {tables.map(([cap, b]) => b && (
        <div className="table-scroll" key={cap}><table className="data comms-budget">
          <caption>{cap} {L.distance(fmtNum(b.distance_km, 0))}</caption>
          <thead><tr><th>{L.cols.term}</th><th className="num">{L.cols.value}</th><th>{L.cols.unit}</th><th>{L.cols.formula}</th></tr></thead>
          <tbody>{b.rows.map((r) => (
            <tr key={r.key}><th scope="row">{r.label}</th>
              <td className="num">{r.evaluated && r.value != null ? fmtNum(r.value, 2) : (
                <span className="unavail">{L.notEvaluated}{r.missing && r.missing.length ? ` (${L.missingList(r.missing.map((m) => L.names[m as keyof typeof L.names] ?? m).join(", "))})` : ""}</span>)}</td>
              <td>{r.unit}</td><td className="mono formula">{r.formula}</td></tr>
          ))}
          {b.cn_db != null && <tr><th scope="row">{L.cn}</th><td className="num">{fmtNum(b.cn_db, 2)}</td><td>{L.db}</td><td className="mono formula">{L.cnFormula}</td></tr>}
          </tbody>
        </table></div>
      ))}
      </div>
    </div>
  );
}

function StatsRow({ name, st, rfOff }: { name: string; st: CommsStats | null | undefined; rfOff?: boolean }) {
  return (
    <tr>
      <th scope="row">{name}</th>
      {st ? (<>
        <td className="num">{h(st.open_h)}</td><td className="num">{st.windows}</td><td className="num">{h(st.mean_gap_h)}</td>
        <td className="num">{h(st.longest_gap_h)}</td><td className="num">{h(st.unknown_h)}</td><td className="num">{st.uncertain_windows}</td>
      </>) : <td colSpan={6} className="unavail">{rfOff ? C.cmp.rfOff : C.cmp.notConfigured}</td>}
    </tr>
  );
}

// ---------------------------------------------------------------- view
export function CommsView() {
  const { state, dispatch, runAnalysis } = useStore();
  const { site, coverage, covered } = useSiteCoverage();
  const inp = state.commsInputs;
  const setInp = (patch: Partial<CommsInputs>) => dispatch({ type: "commsInputs", inputs: { ...inp, ...patch } });
  const c = state.comms;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [linkTab, setLinkTab] = useState<LinkKey>("direct");
  const [cursor, setCursor] = useState(0);
  const running = !!state.job;

  // the analysis result for the selected site: the open one, the one kept while exploring, or the latest in this session
  const rid = useMemo(() => {
    if (!site) return null;
    if (state.result && same(state.result.site, site)) return state.result.id;
    if (state.parked && same(state.parked.result.site, site)) return state.parked.result.id;
    return state.history.find((x) => same(x.site, site))?.id ?? null;
  }, [site, state.result, state.parked, state.history]);

  const seq = useRef(0);
  const reqBody = useMemo(() => (rid ? JSON.stringify(body(rid, inp)) : null), [rid, inp]);
  useEffect(() => {
    if (!reqBody) return;
    const my = ++seq.current;
    const t = window.setTimeout(() => {
      setBusy(true);
      api.commsSimulate(JSON.parse(reqBody))
        .then((res) => { if (my === seq.current) { setError(null); dispatch({ type: "comms", comms: { ...res, relay_name: inp.relayOn ? (inp.relay.name?.trim() || null) : null } }); } })
        .catch((e) => { if (my === seq.current) setError(String(e?.message || e)); })
        .finally(() => { if (my === seq.current) setBusy(false); });
    }, DEBOUNCE_MS);
    return () => window.clearTimeout(t);
  }, [reqBody, dispatch, inp.relayOn, inp.relay.name]);

  const analyse = async () => { await runAnalysis(); dispatch({ type: "tab", tab: TAB_COMMS }); };
  // a simulation requested from the mission dashboard: run the analysis first when this session has none for the site
  const key = site ? landingKey(site.lat, site.lon) : null;
  useEffect(() => {
    if (!state.commsRequest || state.commsRequest !== key) return;
    dispatch({ type: "commsRequest", key: null });
    if (!rid && covered && !running) void analyse();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.commsRequest, key, rid, covered, running]);

  const shown = c && site && same(c.site, site) && c.result_id === rid ? c : null;
  const se = shown?.direct.series;
  const n = se?.utc.length ?? 0;
  const ci = Math.min(cursor, Math.max(0, n - 1));
  const cursorEt = shown && n ? shown.window.start_et + (new Date(se!.utc[ci]).getTime() - new Date(shown.window.start_utc).getTime()) / 1000 : null;
  const stateAt = (row: CommsRow) => {
    const segs = shown?.timeline[row];
    if (!segs || cursorEt == null) return undefined;
    const sIdx = segs.findIndex((s) => s.start_et <= cursorEt && cursorEt < s.end_et);
    if (sIdx < 0) return undefined;
    const nextOpen = segs.slice(sIdx).find((s) => s.state === true && s.start_et > cursorEt);
    return { seg: segs[sIdx], next: segs[sIdx + 1] ?? null, nextOpen: segs[sIdx].state === true ? segs[sIdx] : nextOpen ?? null };
  };
  const word = (v: boolean | null | undefined, on: string, off: string) => (v == null ? C.unknownState : v ? on : off);
  const dirNow = stateAt("earth_visible");
  const blkNow = stateAt("terrain_blocked");
  const rfNow = stateAt("direct_rf");
  const linkOf: Record<LinkKey, CommsLink | undefined> = { direct: shown?.direct.link, up: shown?.relay?.leg1.link, down: shown?.relay?.leg2.link };
  const linkTitles: Record<LinkKey, string> = { direct: C.link.tabDirect, up: C.link.tabUp, down: C.link.tabDown };
  const R = C.relay;
  const rf = inp.relay;
  const setRelay = (r: CommsRelayForm) => setInp({ relay: r });
  const rfield = (k: keyof CommsRelayForm, label: string) => (
    <div className="field" key={k}>
      <label htmlFor={`cr-${k}`}>{label}</label>
      <input id={`cr-${k}`} type="text" inputMode={k === "epoch" || k === "name" ? "text" : "decimal"} placeholder={C.link.notSet}
             value={rf[k] ?? ""} onChange={(e) => setRelay({ ...rf, [k]: e.target.value })} />
    </div>
  );
  const setDtn = (d: CommsDtnForm) => setInp({ dtn: d });
  // turning the relay on prefills only its epoch with the window start (editable); every orbital element stays empty
  const enableRelay = () => setInp({ relayOn: true, relay: !inp.relay.epoch && shown ? { ...inp.relay, epoch: shown.window.start_utc } : inp.relay });

  return (
    <div className="comms">
      <ViewHeader eyebrow={C.eyebrow} title={C.title} subtitle={site ? fmtLatLon(site.lat, site.lon) : C.noSite}
                  actions={!rid && site ? <button type="button" className="run-button comms-run" disabled={!covered || running || !state.status?.kernels.loaded}
                                                  onClick={() => { void analyse(); }}>{running ? S.sidebar.analysing : C.runAnalysis}</button> : undefined} />
      <div className="landing-disclaimer comms-disclaimer" role="note">
        <StatusBadge word={shown?.comms_status ?? C.preliminary} />
        <p>{C.disclaimer}</p>
      </div>
      {error && <p className="hint bad comms-pad" role="alert">{C.failed(error)}</p>}
      {state.job && <p className="hint comms-pad" aria-live="polite">{state.job.message}</p>}

      {/* UI review: every Communication card is full width and sized by its own content. The configuration cards used to
          share two-column rows (location beside direct-to-Earth, relay beside the link budget), so the shorter card of each
          row was left with the taller card's height below it. Their contents use responsive columns inside the card. */}
      {/* A. selected location and analysis */}
      <section className="landing-card landing-wide" aria-labelledby="comms-site">
          <h2 id="comms-site">{C.siteHeading}</h2>
          {!site ? <p className="hint">{C.noSite}</p> : (
            <>
              <p className="mono landing-coords">{fmtLatLon(site.lat, site.lon, 5)}</p>
              {state.settings.siteName && <p className="hint">{C.candidate(state.settings.siteName)}</p>}
              <p className={`hint ${coverage?.covered ? "good" : ""}`}>{coverage ? (coverage.covered ? S.explorer.covered(coverage.levels.join(", ")) : S.explorer.notCovered(coverage.reason ?? S.common.unknown)) : S.explorer.checking}</p>
              {!rid ? <p className="hint">{C.needAnalysis(fmtUTC(state.settings.start), fmtUTC(state.settings.end))}</p> : shown && (
                <dl className="metrics landing-metrics">
                  <Metric label={C.window} value={C.windowValue(fmtUTC(shown.window.start_utc), fmtUTC(shown.window.end_utc))} />
                  <Metric label={C.step} value={C.seconds(fmtNum(shown.series_step_s, 0))} note={C.stepNote} />
                  <Metric label={C.rule} value={S.rules[shown.direct.rule as keyof typeof S.rules] ?? shown.direct.rule} />
                  <Metric label={C.horizonIncomplete} value={shown.direct.horizon_incomplete_share == null ? S.common.na : C.pct(fmtNum(100 * shown.direct.horizon_incomplete_share, 1))} />
                </dl>
              )}
              {shown && (
                <div className="mission-badges" aria-label={C.engineLabels}>
                  {Object.entries(shown.engine_labels).map(([k, v]) => v && <StatusBadge key={k} word={v} prefix={C.labelNames[k as keyof typeof C.labelNames] ?? k} />)}
                </div>
              )}
              {shown && <p className="hint">{C.labelsNote}</p>}
            </>
          )}
        </section>

      {/* B. direct-to-Earth */}
      <section className="landing-card landing-wide" aria-labelledby="comms-direct">
          <h2 id="comms-direct">{C.directHeading}</h2>
          {!shown ? <p className="hint">{busy ? C.loading : C.directEmpty}</p> : (
            <>
              <div className="field">
                <label htmlFor="comms-cursor">{C.cursor}</label>
                <input id="comms-cursor" type="range" min={0} max={Math.max(0, n - 1)} value={ci} aria-valuetext={fmtUTC(se!.utc[ci])}
                       onChange={(e) => setCursor(Number(e.target.value))} />
                <span className="hint mono">{fmtUTC(se!.utc[ci])}</span>
              </div>
              <dl className="metrics landing-metrics">
                <Metric label={C.earthEl} value={se!.el[ci] == null ? S.common.na : C.deg(fmtNum(se!.el[ci], 3))} note={C.validatedSource} />
                <Metric label={C.earthAz} value={se!.az[ci] == null ? S.common.na : C.deg(fmtNum(se!.az[ci], 3))} note={C.azNote} />
                <Metric label={C.distance} value={se!.dist_km[ci] == null ? S.common.na : C.km(fmtNum(se!.dist_km[ci], 0))} note={C.distanceNote} />
                <Metric label={C.lightTime} value={se!.light_time_s[ci] == null ? S.common.na : C.seconds(fmtNum(se!.light_time_s[ci], 3))} />
                <Metric label={C.clearance} value={se!.clearance_deg[ci] == null ? S.common.na : C.deg(fmtNum(se!.clearance_deg[ci], 3))} note={C.clearanceNote} />
                <Metric label={C.geoNow} value={word(dirNow?.seg.state, C.visible, C.notVisible)} state={dirNow?.seg.state == null ? "unknown" : undefined}
                        note={dirNow?.seg.uncertain ? C.uncertainNote : undefined} />
                <Metric label={C.blockedNow} value={word(blkNow?.seg.state, C.blocked, C.notBlocked)} />
                <Metric label={C.rfNow} value={shown.timeline.direct_rf ? word(rfNow?.seg.state, C.rfOk, C.rfNot) : C.rfNotEvaluated}
                        state={shown.timeline.direct_rf ? undefined : "unknown"} />
                <Metric label={C.nextChange} value={dirNow?.next ? fmtUTC(dirNow.next.start_utc) : C.noneInWindow}
                        note={dirNow?.next && cursorEt != null ? C.inTime(fmtDuration((dirNow.next.start_et - cursorEt) / 3600)) : undefined} />
                <Metric label={C.nextWindow} value={dirNow?.nextOpen ? fmtUTC(dirNow.nextOpen.start_utc) : C.noneInWindow}
                        note={dirNow?.nextOpen ? C.lasting(fmtDuration(dirNow.nextOpen.duration_h)) : undefined} />
              </dl>
              <p className="hint">{C.directStats(shown.direct.stats.windows, h(shown.direct.stats.open_h), h(shown.direct.stats.longest_gap_h), h(shown.direct.terrain_blocked_stats.open_h))}</p>
              {shown.geometric_not_radio && <p className="hint">{shown.geometric_not_radio}</p>}
            </>
          )}
      </section>

      {shown && (
        <section className="landing-card landing-wide" aria-labelledby="comms-timeline">
          <h2 id="comms-timeline">{C.timelineHeading}{busy && <span className="hint"> {C.updating}</span>}</h2>
          <ElevationChart c={shown} cursorEt={cursorEt} />
          <CommsTimeline c={shown} cursorEt={cursorEt} />
          <p className="hint">{C.timelineNote(C.seconds(fmtNum(shown.series_step_s, 0)), shown.relay ? C.seconds(fmtNum(shown.relay.step_s, 0)) : S.common.na)}</p>
          <details className="comms-windows">
            <summary>{C.windowsList}</summary>
            <div className="table-scroll"><table className="data">
              <thead><tr><th>{C.wl.path}</th><th>{C.wl.start}</th><th>{C.wl.end}</th><th className="num">{C.wl.duration}</th><th>{C.wl.flags}</th></tr></thead>
              <tbody>{(["earth_visible", "direct_rf", "relay_geometric", "relay_rf"] as CommsRow[]).flatMap((r) =>
                (shown.timeline[r] ?? []).filter((s) => s.state === true).slice(0, 60).map((s, i) => (
                  <tr key={`${r}-${i}`}><td>{C.rows[r]}</td><td className="mono">{fmtUTC(s.start_utc)}</td><td className="mono">{fmtUTC(s.end_utc)}</td>
                    <td className="num">{fmtDuration(s.duration_h)}</td><td>{s.uncertain ? C.wl.uncertain : ""}</td></tr>)))}</tbody>
            </table></div>
          </details>
        </section>
      )}

      {rid && (
        <>
          {/* C. RF link budgets */}
          <section className="landing-card landing-wide" aria-labelledby="comms-link">
            <h2 id="comms-link">{C.link.heading}</h2>
            <div className="segmented comms-linktabs" role="group" aria-label={C.link.which}>
              {LINK_KEYS.map((k) => (
                <button key={k} type="button" aria-pressed={linkTab === k} onClick={() => setLinkTab(k)}>{linkTitles[k]}</button>
              ))}
            </div>
            <p className="hint">{C.link.note}</p>
            {/* a relay leg's distance comes from the relay's orbit: without a simulated relay its budget cannot be evaluated */}
            {linkTab !== "direct" && !shown?.relay && (
              <p className="hint warn comms-relay-needed" role="status">
                {inp.relayOn ? C.link.relayIncomplete : C.link.relayOff}{" "}
                {!inp.relayOn && <button type="button" className="quiet-button" onClick={enableRelay}>{C.link.enableRelay}</button>}
              </p>
            )}
            <LinkForm id={`cl-${linkTab}`} f={inp[linkTab]} onChange={(f) => setInp({ [linkTab]: f } as Partial<CommsInputs>)} />
            <Breakdown link={linkOf[linkTab]} title={linkTitles[linkTab]} />
          </section>

          {/* D. hypothetical relay */}
          <section className="landing-card landing-wide" aria-labelledby="comms-relay">
            <h2 id="comms-relay">{R.heading}</h2>
            <label className="comms-toggle">
              <input type="checkbox" checked={inp.relayOn} onChange={(e) => (e.target.checked ? enableRelay() : setInp({ relayOn: false }))} />
              {R.enable}
            </label>
            <p className="hint warn">{R.hypothetical}</p>
            {inp.relayOn && (
              <>
                <div className="comms-relay-fields">
                  {rfield("name", R.name)}
                  <div className="field">
                    <label htmlFor="cr-frame">{R.frame}</label>
                    <select id="cr-frame" value={rf.frame ?? ""} onChange={(e) => setRelay({ ...rf, frame: e.target.value })}>
                      <option value="">{C.link.notSet}</option>
                      <option value="LME_EPOCH">{R.frames.LME_EPOCH}</option><option value="J2000">{R.frames.J2000}</option>
                    </select>
                  </div>
                  {rfield("a", R.a)}{rfield("e", R.e)}{rfield("i", R.i)}{rfield("raan", R.raan)}
                  {rfield("argp", R.argp)}{rfield("m0", R.m0)}{rfield("epoch", R.epoch)}{rfield("step", R.step)}{rfield("graze", R.graze)}
                </div>
                <p className="hint">{R.frameNote}</p>
                <p className="hint">{R.modelNote}</p>
                {shown?.relay && (
                  <>
                    <dl className="metrics landing-metrics">
                      <Metric label={R.period} value={fmtDuration(shown.relay.orbit.period_h)} />
                      <Metric label={R.alt} value={R.altValue(fmtNum(shown.relay.orbit.periapsis_alt_km, 0), fmtNum(shown.relay.orbit.apoapsis_alt_km, 0))} />
                      <Metric label={R.samples} value={String(shown.relay.samples)} note={C.seconds(fmtNum(shown.relay.step_s, 0))} />
                    </dl>
                    <div className="table-scroll"><table className="data">
                      <thead><tr><th>{R.leg}</th><th className="num">{R.open}</th><th className="num">{R.windows}</th><th className="num">{R.range}</th><th>{R.note}</th></tr></thead>
                      <tbody>
                        <tr><th scope="row">{R.leg1}</th><td className="num">{h(shown.relay.leg1.stats.open_h)}</td><td className="num">{shown.relay.leg1.stats.windows}</td>
                          <td className="num">{R.rangeValue(fmtNum(shown.relay.leg1.range_km.min, 0), fmtNum(shown.relay.leg1.range_km.max, 0))}</td>
                          <td>{R.leg1Note(fmtNum(100 * shown.relay.leg1.unknown_share, 1), fmtNum(shown.relay.leg1.el_deg.max, 1))}</td></tr>
                        <tr><th scope="row">{R.leg2}</th><td className="num">{h(shown.relay.leg2.stats.open_h)}</td><td className="num">{shown.relay.leg2.stats.windows}</td>
                          <td className="num">{R.rangeValue(fmtNum(shown.relay.leg2.range_km.min, 0), fmtNum(shown.relay.leg2.range_km.max, 0))}</td><td>{R.leg2Note}</td></tr>
                        <tr><th scope="row">{R.both}</th><td className="num">{h(shown.relay.both.open_h)}</td><td className="num">{shown.relay.both.windows}</td>
                          <td className="num">{S.common.na}</td><td>{R.bothNote(h(shown.relay.both.longest_gap_h))}</td></tr>
                      </tbody>
                    </table></div>
                  </>
                )}
              </>
            )}
          </section>
        </>
      )}

      {shown && (
        <>
          {/* F. comparison */}
          <section className="landing-card landing-wide" aria-labelledby="comms-compare">
            <h2 id="comms-compare">{C.cmp.heading}</h2>
            <div className="table-scroll"><table className="data comms-cmp">
              <thead><tr><th>{C.cmp.path}</th><th className="num">{C.cmp.open}</th><th className="num">{C.cmp.windows}</th><th className="num">{C.cmp.meanGap}</th>
                <th className="num">{C.cmp.longestGap}</th><th className="num">{C.cmp.unknown}</th><th className="num">{C.cmp.uncertain}</th></tr></thead>
              <tbody>
                <StatsRow name={C.rows.earth_visible} st={shown.comparison.direct_geometric} />
                <StatsRow name={C.rows.direct_rf} st={shown.comparison.direct_rf} rfOff />
                <StatsRow name={C.rows.relay_geometric} st={shown.comparison.relay_geometric} />
                <StatsRow name={C.rows.relay_rf} st={shown.comparison.relay_rf} rfOff={!!shown.relay} />
                <StatsRow name={C.rows.any_geometric} st={shown.comparison.any_geometric} />
                <StatsRow name={C.rows.any_rf} st={shown.comparison.any_rf} rfOff />
              </tbody>
            </table></div>
            {shown.comparison.relay_adds_geometric_h != null && (
              <p className="hint">{C.cmp.adds(h(shown.comparison.relay_adds_geometric_h), shown.comparison.relay_adds_rf_h != null ? h(shown.comparison.relay_adds_rf_h) : C.rfNotEvaluated)}</p>
            )}
            <ul className="comms-bars" aria-label={C.cmp.barsLabel}>
              {([["earth_visible", shown.comparison.direct_geometric], ["direct_rf", shown.comparison.direct_rf], ["relay_geometric", shown.comparison.relay_geometric],
                 ["relay_rf", shown.comparison.relay_rf], ["any_geometric", shown.comparison.any_geometric], ["any_rf", shown.comparison.any_rf]] as [CommsRow, CommsStats | null][]).map(([k, st]) => {
                const total = (shown.window.end_et - shown.window.start_et) / 3600;
                return (
                  <li key={k}>
                    <span className="hist-k">{C.rows[k]}</span>
                    <span className="hist-bar" aria-hidden><span className={k.endsWith("rf") ? "is-rf" : "is-geo"} style={{ width: st ? `${(100 * st.open_h) / total}%` : 0 }} /></span>
                    <span className="hist-v mono">{st ? h(st.open_h) : C.cmp.na}</span>
                  </li>
                );
              })}
            </ul>
            <p className="hint">{C.cmp.note}</p>
          </section>

          {/* store-and-forward planner */}
          <section className="landing-card landing-wide" aria-labelledby="comms-dtn">
            <h2 id="comms-dtn">{C.dtn.heading}</h2>
            <p className="hint warn">{C.dtn.label}</p>
            <div className="field-row">
              <div className="field"><label htmlFor="cd-vol">{C.dtn.volume}</label>
                <input id="cd-vol" type="text" inputMode="decimal" placeholder={C.link.notSet} value={inp.dtn.volume ?? ""} onChange={(e) => setDtn({ ...inp.dtn, volume: e.target.value })} /></div>
              <div className="field"><label htmlFor="cd-rate">{C.dtn.rate}</label>
                <input id="cd-rate" type="text" inputMode="decimal" placeholder={C.link.notSet} value={inp.dtn.rate ?? ""} onChange={(e) => setDtn({ ...inp.dtn, rate: e.target.value })} /></div>
            </div>
            <div className="field-row">
              <div className="field"><label htmlFor="cd-path">{C.dtn.path}</label>
                <select id="cd-path" value={inp.dtn.path ?? "direct_rf"} onChange={(e) => setDtn({ ...inp.dtn, path: e.target.value })}>
                  {DTN_PATHS.map((p) => <option key={p} value={p}>{C.rows[p]}</option>)}
                </select></div>
              <div className="field"><label htmlFor="cd-start">{C.dtn.start}</label>
                <input id="cd-start" type="text" placeholder={shown.window.start_utc} value={inp.dtn.start ?? ""} onChange={(e) => setDtn({ ...inp.dtn, start: e.target.value })} /></div>
            </div>
            {shown.dtn && (shown.dtn.evaluated ? (
              <dl className="metrics landing-metrics">
                <Metric label={C.dtn.transmit} value={h(shown.dtn.transmit_time_h)} />
                <Metric label={C.dtn.contacts} value={String(shown.dtn.contacts_used ?? 0)} />
                <Metric label={C.dtn.completion} value={shown.dtn.complete && shown.dtn.completion_utc ? fmtUTC(shown.dtn.completion_utc) : C.dtn.notInWindow}
                        state={shown.dtn.complete ? undefined : "unknown"} note={shown.dtn.complete ? C.dtn.elapsed(h(shown.dtn.elapsed_h)) : undefined} />
                <Metric label={C.dtn.remaining} value={C.dtn.mbit(fmtNum(shown.dtn.remaining_mbit, 1))} />
              </dl>
            ) : <p className="hint">{shown.dtn.reason}</p>)}
            {shown.dtn?.note && <p className="hint">{shown.dtn.note}</p>}
          </section>
        </>
      )}

      {shown && (
        <section className="landing-card landing-wide" aria-labelledby="comms-provenance">
          <h2 id="comms-provenance">{C.prov.heading}</h2>
          <dl className="landing-prov">
            <dt>{C.prov.status}</dt><dd>{shown.provenance.status}. {shown.provenance.status_note}</dd>
            <dt>{C.prov.engine}</dt><dd className="mono">{C.prov.engineValue(shown.provenance.engine.result_id, shown.provenance.engine.algorithm_version, String(shown.provenance.engine.code_fingerprint).slice(0, 16))}</dd>
            <dt>{C.prov.labels}</dt><dd><ul>{Object.entries(shown.engine_labels).map(([k, v]) => (
              <li key={k}><strong>{C.labelNames[k as keyof typeof C.labelNames] ?? k}</strong>{": "}{v ?? S.common.na}
                {(shown.engine_label_reasons?.[k] ?? []).length > 0 && <>{" "}{C.prov.reasons((shown.engine_label_reasons[k] ?? []).join("; "))}</>}</li>))}</ul></dd>
            <dt>{C.prov.kernels}</dt><dd className="mono">{shown.provenance.kernels.map((k) => k.name).join(", ") || S.common.na}</dd>
            <dt>{C.prov.frame}</dt><dd>{shown.provenance.frame}</dd>
            <dt>{C.prov.terrain}</dt><dd className="mono">{shown.provenance.terrain.horizon_levels.join(", ") || S.common.na}</dd>
            <dt>{C.prov.gm}</dt><dd>{C.prov.gmValue(String(shown.provenance.gm.gm_km3_s2), shown.provenance.gm.file, shown.provenance.gm.sha256.slice(0, 16))} {shown.provenance.gm.citation}</dd>
            <dt>{C.prov.constants}</dt><dd>{Object.entries(shown.provenance.constants).map(([k, v]) => `${k}: ${v}`).join("; ")}</dd>
            <dt>{C.prov.methods}</dt><dd><ul>{Object.entries(shown.provenance.methods).map(([k, v]) => <li key={k}><strong>{k}</strong>{": "}{v}</li>)}</ul></dd>
            <dt>{C.prov.version}</dt><dd className="mono">{C.prov.versionValue(shown.provenance.comms_version, shown.provenance.comms_code_sha256.slice(0, 16))}</dd>
            <dt>{C.prov.limitations}</dt><dd><ul>{shown.provenance.limitations.map((l, i) => <li key={i}>{l}</li>)}</ul></dd>
            <dt>{C.prov.references}</dt><dd><ul>
              <li>{C.prov.refLsp}</li><li>{C.prov.refDtn}</li><li>{C.prov.refGm}</li>
            </ul></dd>
          </dl>
        </section>
      )}
    </div>
  );
}
