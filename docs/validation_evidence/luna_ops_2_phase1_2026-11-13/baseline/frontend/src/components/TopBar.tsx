import { S } from "../i18n";
import { useStore, type Tab } from "../state/store";

const T = S.topBar;
// Phase 5 prompt 4: the mission dashboard is listed first; the app still opens on the Site tab
const TABS: Tab[] = ["mission", "site", "compare", "data", "guide"];

export function TopBar() {
  const { state, dispatch } = useStore();
  // WAI-ARIA tabs: one tab stop for the list; arrows, Home and End move between tabs and select them
  const onTabKey = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    const i = TABS.indexOf(state.tab);
    const next = e.key === "ArrowRight" ? (i + 1) % TABS.length : e.key === "ArrowLeft" ? (i - 1 + TABS.length) % TABS.length
      : e.key === "Home" ? 0 : e.key === "End" ? TABS.length - 1 : -1;
    if (next < 0) return;
    e.preventDefault();
    dispatch({ type: "tab", tab: TABS[next] });
    document.getElementById(`tab-${TABS[next]}`)?.focus();
  };
  const ks = state.status?.kernels;
  const terrain = state.status?.terrain;
  const nLevels = terrain ? Object.keys(terrain.levels).length : 0;
  const kernelOk = ks?.loaded && ks.profile === "production";
  return (
    <header className="topbar">
      <div className="brand">
        <span className="brand-mark">{S.app.brand}</span>
        <span className="brand-sub">{S.app.tagline}</span>
      </div>
      <nav className="tabs" role="tablist" aria-label={T.tabsLabel}>
        {TABS.map((id) => (
          <button key={id} id={`tab-${id}`} role="tab" className="tab" aria-selected={state.tab === id} aria-controls="view-panel"
                  tabIndex={state.tab === id ? 0 : -1} onKeyDown={onTabKey}
                  onClick={() => dispatch({ type: "tab", tab: id })}>{T.tabs[id]}</button>
        ))}
      </nav>
      <div className="topbar-right">
        <span className="data-pill" title={T.statusTitle}>
          <span className={`dot ${kernelOk ? "ok" : "warn"}`} aria-hidden />
          {!ks ? T.connecting : ks.loaded ? (ks.profile === "production" ? T.naifKernels : T.testKernels) : T.noKernels}
          <span className={`dot ${nLevels && !terrain?.synthetic_in_use ? "ok" : "warn"}`} aria-hidden />
          {nLevels ? (terrain?.synthetic_in_use ? T.syntheticTerrain : T.lolaTerrain(nLevels)) : T.noTerrain}
        </span>
        <div className="mode-switch" role="group" aria-label={T.modeLabel}>
          <button aria-pressed={state.mode === "technical"} onClick={() => dispatch({ type: "mode", mode: "technical" })}>{T.modes.technical}</button>
          <button aria-pressed={state.mode === "public"} onClick={() => dispatch({ type: "mode", mode: "public" })}>{T.modes.public}</button>
        </div>
      </div>
    </header>
  );
}
