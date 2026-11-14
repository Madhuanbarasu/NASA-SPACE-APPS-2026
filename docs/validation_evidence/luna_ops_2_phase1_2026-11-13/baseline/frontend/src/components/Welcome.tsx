import { S } from "../i18n";
import { useStore, type State } from "../state/store";

const W = S.welcome;

/** Data readiness rows (kernels, terrain, catalogue, validation report), all from GET /api/status and the catalogue;
 *  shared with the mission dashboard. ok = null while unknown. */
export function readinessRows(state: State): { ok: boolean | null; text: string }[] {
  const st = state.status;
  const levels = st ? Object.keys(st.terrain.levels) : [];
  const rows: { ok: boolean | null; text: string }[] = [
    { ok: st ? !!st.kernels.loaded && st.kernels.profile === "production" : null,
      text: !st ? W.connecting : st.kernels.loaded
        ? (st.kernels.profile === "production" ? W.naifKernels(st.kernels.frame) : W.testKernels(st.kernels.frame))
        : W.noKernels(st.kernels.error ?? "") },
    { ok: st ? levels.length > 0 && !st.terrain.synthetic_in_use : null,
      text: !st ? W.checkingTerrain : levels.length
        ? (st.terrain.synthetic_in_use ? W.syntheticTerrain(levels.join(", ")) : W.lolaTerrain(levels.join(", ")))
        : W.noTerrain },
    { ok: state.catalog.length > 0, text: state.catalog.length ? W.curatedSites(state.catalog.length) : W.noCuratedSites },
    { ok: st?.validation ? true : null, text: st?.validation ? W.validationReport(st.validation.run_utc, st.validation.kernel_profile) : W.noValidationReport },
  ];
  return rows;
}

export function Welcome() {
  const { state } = useStore();
  const rows = readinessRows(state);
  return (
    <section className="welcome" aria-labelledby="welcome-title">
      <h1 id="welcome-title">{W.title}</h1>
      <p>{W.intro}</p>
      <ul className="welcome-status" aria-label={W.readinessLabel}>
        {rows.map((r, k) => (
          <li key={k}><span className={`dot ${r.ok === null ? "" : r.ok ? "ok" : "warn"}`} aria-hidden /> {r.text}</li>
        ))}
      </ul>
      <div className="steps">
        {W.steps.map((step) => <div key={step.title}><h3>{step.title}</h3><p>{step.text}</p></div>)}
      </div>
    </section>
  );
}
