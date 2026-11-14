import { Suspense, lazy, useCallback, useEffect, useState } from "react";
import { TopBar } from "./components/TopBar";
import { Sidebar } from "./components/Sidebar";
import { SiteView } from "./components/SiteView";
import { CompareView } from "./components/CompareView";
import { DataView } from "./components/DataView";
import { GuideView } from "./components/GuideView";
import { LazyBoundary } from "./components/LazyBoundary";
import { S } from "./i18n";
import { useMediaQuery } from "./lib/useMediaQuery";
import { useStore } from "./state/store";

// Phase 5 prompt 4: the mission dashboard loads when its tab is first opened
const MissionView = lazy(() => import("./components/MissionView").then((m) => ({ default: m.MissionView })));
// LUNA-OPS 2.0 Phase 5: the landing screening workspace loads when its tab is first opened
const LandingView = lazy(() => import("./components/LandingView").then((m) => ({ default: m.LandingView })));

// LUNA-OPS 2.0 shell. Wide screens (>= 1200 px) dock the Mission Parameters panel on the left; it can be collapsed (the
// choice is remembered in this browser) to give the workspace the full width. Narrower screens open it as a drawer over
// the workspace, closed by default.
const WIDE = "(min-width: 1200px)";
const DOCKED_KEY = "luna-ops.params-docked.v1";
const readDocked = () => { try { return window.localStorage.getItem(DOCKED_KEY) !== "closed"; } catch { return true; } };
const writeDocked = (open: boolean) => { try { window.localStorage.setItem(DOCKED_KEY, open ? "open" : "closed"); } catch { /* storage unavailable */ } };

export default function App() {
  const { state } = useStore();
  const wide = useMediaQuery(WIDE);
  const [docked, setDocked] = useState(readDocked);
  const [drawer, setDrawer] = useState(false);
  const open = wide ? docked : drawer;

  const focusToggle = () => document.querySelector<HTMLButtonElement>(".params-toggle")?.focus();
  const closeDrawer = useCallback(() => { setDrawer(false); focusToggle(); }, []);
  const toggle = () => {
    if (wide) setDocked((v) => { writeDocked(!v); return !v; });
    else setDrawer((v) => !v);
  };
  // leaving the narrow layout closes the drawer
  useEffect(() => { if (wide) setDrawer(false); }, [wide]);
  // drawer: focus moves into it; Escape or a press outside it closes it
  useEffect(() => {
    if (!drawer) return;
    document.getElementById("params-close")?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") closeDrawer(); };
    const onDown = (e: PointerEvent) => {
      const t = e.target as Node | null;
      if (!t || document.getElementById("mission-parameters")?.contains(t) || document.querySelector(".params-toggle")?.contains(t)) return;
      setDrawer(false);
    };
    window.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onDown);
    return () => { window.removeEventListener("keydown", onKey); document.removeEventListener("pointerdown", onDown); };
  }, [drawer, closeDrawer]);

  const layout = wide ? (docked ? "params-docked" : "params-collapsed") : (drawer ? "params-open" : "params-closed");
  return (
    <div className="shell">
      <a className="skip-link" href="#main">{S.app.skipToContent}</a>
      <TopBar paramsOpen={open} onToggleParams={toggle} />
      <div className={`workspace ${layout}`}>
        <Sidebar open={open} onClose={wide ? toggle : closeDrawer} />
        {!wide && drawer && <div className="scrim" aria-hidden="true" />}
        <main className="main" id="main" tabIndex={-1}>
          <div role="tabpanel" id="view-panel" aria-labelledby={`tab-${state.tab}`}>
          {state.tab === "mission" && (
            <LazyBoundary fallback={<div className="pane-empty">{S.mission.loadFailed}</div>}>
              <Suspense fallback={<div className="pane-empty">{S.mission.loading}</div>}><MissionView /></Suspense>
            </LazyBoundary>
          )}
          {state.tab === "site" && <SiteView />}
          {state.tab === "landing" && (
            <LazyBoundary fallback={<div className="pane-empty">{S.landing.loadFailed}</div>}>
              <Suspense fallback={<div className="pane-empty">{S.landing.loading}</div>}><LandingView /></Suspense>
            </LazyBoundary>
          )}
          {state.tab === "compare" && <CompareView />}
          {state.tab === "data" && <DataView />}
          {state.tab === "guide" && <GuideView />}
          </div>
        </main>
      </div>
    </div>
  );
}
