import { useEffect, useState } from "react";
import { S } from "../i18n";
import { useStore, type Tab } from "../state/store";
import { BrandMark } from "../ui/BrandMark";
import { Icon } from "../ui/Icon";
import { UtcClock } from "../ui/UtcClock";

const T = S.topBar;
const SH = S.shell;
// Phase 5 prompt 4: the mission dashboard is listed first; the app still opens on the Site tab
const TABS: Tab[] = ["mission", "site", "landing", "compare", "data", "guide"];

interface TopBarProps {
  /** whether the Mission Parameters panel is shown (docked on wide screens, a drawer below 1200 px) */
  paramsOpen: boolean;
  onToggleParams: () => void;
}

// LUNA-OPS 2.0 command bar: parameters toggle, brand, primary navigation (tabs on wide screens, a compact menu below
// 1200 px), UTC clock, data status and the viewing mode.
export function TopBar({ paramsOpen, onToggleParams }: TopBarProps) {
  const { state, dispatch } = useStore();
  const [menuOpen, setMenuOpen] = useState(false);
  // WAI-ARIA tabs: one tab stop for the list; arrows, Home and End move between tabs and select them (in the compact
  // menu, which is a vertical list, Up and Down do the same)
  const onTabKey = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    const i = TABS.indexOf(state.tab);
    const fwd = e.key === "ArrowRight" || (menuOpen && e.key === "ArrowDown");
    const back = e.key === "ArrowLeft" || (menuOpen && e.key === "ArrowUp");
    const next = fwd ? (i + 1) % TABS.length : back ? (i - 1 + TABS.length) % TABS.length
      : e.key === "Home" ? 0 : e.key === "End" ? TABS.length - 1 : -1;
    if (next < 0) return;
    e.preventDefault();
    dispatch({ type: "tab", tab: TABS[next] });
    document.getElementById(`tab-${TABS[next]}`)?.focus();
  };
  // the compact menu closes with Escape (focus back on its button)
  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setMenuOpen(false);
      document.getElementById("nav-toggle")?.focus();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menuOpen]);
  const choose = (id: Tab) => { dispatch({ type: "tab", tab: id }); setMenuOpen(false); };

  const ks = state.status?.kernels;
  const terrain = state.status?.terrain;
  const nLevels = terrain ? Object.keys(terrain.levels).length : 0;
  const kernelOk = ks?.loaded && ks.profile === "production";
  return (
    <header className="topbar">
      <button type="button" className="icon-button params-toggle" aria-controls="mission-parameters" aria-expanded={paramsOpen}
              aria-label={paramsOpen ? SH.hideParams : SH.showParams} title={paramsOpen ? SH.hideParams : SH.showParams}
              onClick={onToggleParams}>
        <Icon name="sliders" />
      </button>
      <div className="brand">
        <BrandMark />
        <span className="brand-text">
          <span className="brand-mark">{S.app.brand}</span>
          <span className="brand-sub">{S.app.tagline}</span>
        </span>
      </div>
      <button type="button" id="nav-toggle" className="nav-toggle" aria-controls="primary-nav" aria-expanded={menuOpen}
              aria-label={`${SH.navMenu}: ${T.tabs[state.tab]}`} onClick={() => setMenuOpen((v) => !v)}>
        <Icon name={menuOpen ? "close" : "menu"} />
        <span aria-hidden="true">{T.tabs[state.tab]}</span>
      </button>
      <nav className="tabs" id="primary-nav" data-open={menuOpen} role="tablist" aria-label={T.tabsLabel}>
        {TABS.map((id) => (
          <button key={id} id={`tab-${id}`} role="tab" className="tab" aria-selected={state.tab === id} aria-controls="view-panel"
                  tabIndex={state.tab === id ? 0 : -1} onKeyDown={onTabKey}
                  onClick={() => choose(id)}>{T.tabs[id]}</button>
        ))}
      </nav>
      <div className="topbar-right">
        <UtcClock />
        <span className="data-pill" title={T.statusTitle}>
          <span className={`dot ${kernelOk ? "ok" : "warn"}`} aria-hidden />
          <span className="pill-label">{!ks ? T.connecting : ks.loaded ? (ks.profile === "production" ? T.naifKernels : T.testKernels) : T.noKernels}</span>
          <span className={`dot ${nLevels && !terrain?.synthetic_in_use ? "ok" : "warn"}`} aria-hidden />
          <span className="pill-label">{nLevels ? (terrain?.synthetic_in_use ? T.syntheticTerrain : T.lolaTerrain(nLevels)) : T.noTerrain}</span>
        </span>
        <div className="mode-switch" role="group" aria-label={T.modeLabel}>
          <button aria-pressed={state.mode === "technical"} onClick={() => dispatch({ type: "mode", mode: "technical" })}>{T.modes.technical}</button>
          <button aria-pressed={state.mode === "public"} onClick={() => dispatch({ type: "mode", mode: "public" })}>{T.modes.public}</button>
        </div>
      </div>
    </header>
  );
}
