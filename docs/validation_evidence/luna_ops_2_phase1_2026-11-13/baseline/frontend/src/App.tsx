import { Suspense, lazy } from "react";
import { TopBar } from "./components/TopBar";
import { Sidebar } from "./components/Sidebar";
import { SiteView } from "./components/SiteView";
import { CompareView } from "./components/CompareView";
import { DataView } from "./components/DataView";
import { GuideView } from "./components/GuideView";
import { LazyBoundary } from "./components/LazyBoundary";
import { S } from "./i18n";
import { useStore } from "./state/store";

// Phase 5 prompt 4: the mission dashboard loads when its tab is first opened
const MissionView = lazy(() => import("./components/MissionView").then((m) => ({ default: m.MissionView })));

export default function App() {
  const { state } = useStore();
  return (
    <div className="shell">
      <a className="skip-link" href="#main">{S.app.skipToContent}</a>
      <TopBar />
      <div className="workspace">
        <Sidebar />
        <main className="main" id="main" tabIndex={-1}>
          <div role="tabpanel" id="view-panel" aria-labelledby={`tab-${state.tab}`}>
          {state.tab === "mission" && (
            <LazyBoundary fallback={<div className="pane-empty">{S.mission.loadFailed}</div>}>
              <Suspense fallback={<div className="pane-empty">{S.mission.loading}</div>}><MissionView /></Suspense>
            </LazyBoundary>
          )}
          {state.tab === "site" && <SiteView />}
          {state.tab === "compare" && <CompareView />}
          {state.tab === "data" && <DataView />}
          {state.tab === "guide" && <GuideView />}
          </div>
        </main>
      </div>
    </div>
  );
}
