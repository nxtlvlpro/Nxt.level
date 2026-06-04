import React, { useEffect, useState } from "react";
import "./App.css";
import TopTicker from "./components/TopTicker";
import Header from "./components/Header";
import BottomNav from "./components/BottomNav";
import SideNav from "./components/SideNav";
import HomeView from "./components/views/HomeView";
import ChatView from "./components/views/ChatView";
import AgentsView from "./components/views/AgentsView";
import MapView from "./components/views/MapView";
import AlertsView from "./components/views/AlertsView";
import MicView from "./components/views/MicView";
import OpsView from "./components/views/OpsView";
import GraphView from "./components/views/GraphView";
import api from "./lib/api";
import { useT } from "./i18n/LanguageContext";
import { HEADER_LOCKED } from "./config/header.locked";

function App() {
  const { t } = useT();
  const [view, setView] = useState("home");
  const [alertCount, setAlertCount] = useState(0);
  const [seedStatus, setSeedStatus] = useState("idle");

  useEffect(() => {
    // Auto-seed on first load (idempotent on backend side)
    setSeedStatus("seeding");
    api
      .seed()
      .then(() => setSeedStatus("ready"))
      .catch(() => setSeedStatus("error"));
  }, []);

  useEffect(() => {
    let mounted = true;
    const poll = () => {
      api
        .alerts(50)
        .then((d) => {
          if (!mounted) return;
          setAlertCount((d.alerts || []).length);
        })
        .catch(() => {});
    };
    poll();
    const t = setInterval(poll, 15000);
    return () => {
      mounted = false;
      clearInterval(t);
    };
  }, []);

  const renderView = () => {
    switch (view) {
      case "cmd":
        return <ChatView />;
      case "agents":
        return <AgentsView />;
      case "map":
        return <MapView />;
      case "alerts":
        return <AlertsView />;
      case "mic":
        return <MicView />;
      case "ops":
        return <OpsView />;
      case "graph":
        return <GraphView />;
      case "home":
      default:
        return <HomeView />;
    }
  };

  return (
    <div
      className="App led-matrix h-screen flex flex-col relative overflow-hidden"
      data-testid="app-root"
    >
      <div className="fixed inset-0 led-matrix pointer-events-none -z-10"></div>

      {/* Full-width ticker — pinned at very top */}
      <div className="shrink-0 z-20" data-testid="app-shell-ticker">
        <TopTicker />
      </div>

      {/* Body row: optional left sidebar (lg+) + main column */}
      <div className="flex-1 flex min-h-0 overflow-hidden">
        <SideNav
          active={view}
          onChange={setView}
          alertCount={alertCount}
        />

        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          <div
            className={`shrink-0 z-20 w-full max-w-md lg:max-w-screen-2xl mx-auto px-4 lg:px-8 ${HEADER_LOCKED.shellTopPaddingClass}`}
            data-testid="app-shell-header"
          >
            <Header aiIndex={8.1} streakDays={14} />
            {seedStatus === "error" && (
              <div
                className="text-[10px] text-red-400 border border-red-500/30 bg-red-500/5 rounded-md p-2 mt-2"
                data-testid="seed-error"
              >
                {t("seed.error")}
              </div>
            )}
          </div>

          <main
            className="relative z-10 flex-1 overflow-y-auto overscroll-contain w-full max-w-md lg:max-w-screen-2xl mx-auto px-4 lg:px-8"
            data-testid="main-scroll"
          >
            <div
              className={view === "home" ? HEADER_LOCKED.homeViewPaddingClass : "py-4"}
              data-testid={`view-${view}`}
            >
              {renderView()}
            </div>
          </main>
        </div>
      </div>

      {/* Bottom nav — mobile/tablet only; sidebar replaces it on lg+ */}
      <div
        className="shrink-0 w-full max-w-md mx-auto px-4 pb-2 z-20 lg:hidden"
        data-testid="app-shell-bottom"
      >
        <BottomNav active={view} onChange={setView} alertCount={alertCount} />
      </div>
    </div>
  );
}

export default App;
