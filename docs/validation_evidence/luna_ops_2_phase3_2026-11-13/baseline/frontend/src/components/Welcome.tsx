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

/** LUNA-OPS 2.0 Phase 2: the explorer's compact title (the page's h1), beside the stage so it never covers the Moon. */
export function Welcome() {
  return (
    <section className="welcome welcome-intro" aria-labelledby="welcome-title">
      <p className="eyebrow">{S.shell.eyebrows.explorer}</p>
      <h1 id="welcome-title">{W.title}</h1>
    </section>
  );
}

/** The introduction, data readiness board and first steps, under the explorer stage (Phase 2). */
export function WelcomeDetails() {
  const { state } = useStore();
  const rows = readinessRows(state);
  return (
    <section className="welcome-details" aria-labelledby="welcome-details-title">
      <h2 id="welcome-details-title" className="eyebrow">{W.detailsHeading}</h2>
      <p className="welcome-lead">{W.intro}</p>
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
