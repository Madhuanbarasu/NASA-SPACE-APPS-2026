import { S, rich } from "../i18n";
import { useStore } from "../state/store";

const D = S.data;
const TEST_NAMES: Record<string, string> = D.testNames;

export function DataView() {
  const { state } = useStore();
  const st = state.status;
  if (!st) return <div className="prose"><p>{state.statusError ? S.common.apiUnreachable(state.statusError) : D.loading}</p></div>;
  const tests = st.validation?.tests ?? {};
  const K = D.kernelColumns, TC = D.terrainColumns, VC = D.testColumns, LC = D.labelColumns;
  return (
    <div className="prose" style={{ maxWidth: 1100 }}>
      <h1>{D.title}</h1>
      <p>{D.intro}</p>

      <h2>{D.kernelsHeading}</h2>
      {st.kernels.loaded ? (
        <>
          <p>{rich(D.kernelsSummary, { profile: <strong>{st.kernels.profile}</strong>, frame: <strong>{st.kernels.frame}</strong>,
            start: st.kernels.coverage_utc?.[0], end: st.kernels.coverage_utc?.[1] })}</p>
          <div className="table-scroll"><table className="data">
            <thead><tr><th>{K.role}</th><th>{K.file}</th><th>{K.sha256}</th><th>{K.source}</th><th>{K.retrieved}</th></tr></thead>
            <tbody>{(st.kernels.files ?? []).map((f: any) => (
              <tr key={f.name}><td>{f.role}</td><td>{f.name}</td><td className="mono">{f.sha256?.slice(0, 16)}{S.common.ellipsis}</td>
                <td style={{ maxWidth: 360, overflowWrap: "anywhere" }}>{f.source}</td><td>{f.retrieved_utc}</td></tr>))}</tbody>
          </table></div>
          {(st.kernels.warnings ?? []).map((w, k) => <div className="note alert" key={k} style={{ marginTop: 8 }}>{w}</div>)}
        </>
      ) : <div className="note alert">{st.kernels.error}</div>}

      <h2>{D.terrainHeading}</h2>
      {Object.keys(st.terrain.levels).length ? (
        <div className="table-scroll"><table className="data">
          <thead><tr><th>{TC.product}</th><th>{TC.source}</th><th className="num">{TC.pixel}</th><th className="num">{TC.size}</th><th>{TC.sha256}</th><th>{TC.registered}</th></tr></thead>
          <tbody>{Object.entries(st.terrain.levels).map(([k, v]: [string, any]) => (
            <tr key={k}><td>{k}</td><td>{v.product}{v.synthetic ? D.syntheticProduct : ""}</td>
              <td className="num">{D.pixelSize(v.pixel_m)}</td><td className="num">{v.bytes ? D.gigabytes((v.bytes / 1e9).toFixed(2)) : ""}</td>
              <td className="mono">{v.sha256?.slice(0, 16)}{S.common.ellipsis}</td><td>{v.registered_utc ?? ""}</td></tr>))}</tbody>
        </table></div>
      ) : <p>{D.noTerrain}</p>}
      <p>{D.errorMaps(st.terrain.error_maps.length ? st.terrain.error_maps.join(", ") : D.noErrorMaps)}</p>

      <h2>{D.reportHeading}</h2>
      {st.validation ? (
        <>
          <p>{rich(D.reportSummary, { run: st.validation.run_utc, code: st.validation.code_version,
            profile: <strong>{st.validation.kernel_profile}</strong> })}</p>
          <div className="table-scroll" style={{ maxHeight: 520 }}><table className="data">
            <thead><tr><th>{VC.test}</th><th>{VC.checks}</th><th>{VC.status}</th><th>{VC.detail}</th></tr></thead>
            <tbody>{Object.entries(tests).map(([id, t]: [string, any]) => (
              <tr key={id}><td>{id}</td><td>{TEST_NAMES[id] ?? ""}</td>
                <td style={{ color: t.status === "passed" ? "var(--valid)" : t.status === "failed" ? "var(--alert)" : "var(--muted)" }}>{t.status}</td>
                <td>{t.detail ?? ""}</td></tr>))}</tbody>
          </table></div>
        </>
      ) : <p>{rich(D.noReport, { command: <span className="mono">{D.runValidationCommand}</span> })}</p>}

      <h2>{D.labelsHeading}</h2>
      {(st.validation_blockers ?? []).length > 0 && (
        <div className="note alert" style={{ marginBottom: 10 }}>{D.blockers((st.validation_blockers ?? []).join("; "))}</div>
      )}
      {st.labels && (
        <table className="data"><thead><tr><th>{LC.quantity}</th><th>{LC.kind}</th><th>{LC.status}</th></tr></thead>
          <tbody>{Object.entries(st.labels).map(([k, v]) => <tr key={k}><td>{k.replace(/_/g, " ")}</td><td>{v.kind}</td><td>{v.validation}</td></tr>)}</tbody>
        </table>
      )}

      <h2>{D.attributionHeading}</h2>
      <table className="data"><tbody>{D.attribution.map(([a, b]) => <tr key={a}><th scope="row">{a}</th><td>{b}</td></tr>)}</tbody></table>
      <p className="hint">{rich(D.footer, { version: st.version, code: st.code_version, algorithm: st.algorithm_version,
        fingerprint: <span className="mono">{st.code_fingerprint?.slice(0, 16)}</span> })}</p>
    </div>
  );
}
