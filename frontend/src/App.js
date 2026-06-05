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
import HermesOSView from "./components/views/HermesOSView";
import PaymentReturnView from "./components/views/PaymentReturnView";
import { PrivacyView, TermsView } from "./components/views/LegalViews";
import CookieBanner from "./components/CookieBanner";
import DemoTour from "./components/DemoTour";
import api from "./lib/api";
import { useT } from "./i18n/LanguageContext";
import { HEADER_LOCKED } from "./config/header.locked";
import { AuthProvider, useUser } from "./auth/AuthContext";
import AuthCallback from "./auth/AuthCallback";
import LoginPage from "./auth/LoginPage";
import AppErrorBoundary from "./components/AppErrorBoundary";
import { Toaster } from "./components/ui/sonner";

function AppShell() {
  const { t } = useT();
  // Pathname routing: payment return / cancel pages render standalone,
  // bypassing the main app shell so the user is never confused mid-flow.
  const pathname =
    typeof window !== "undefined" ? window.location.pathname : "/";
  const isPaymentReturn = pathname.startsWith("/payment/return");
  const isPrivacyPage = pathname.startsWith("/privacy");
  const isTermsPage = pathname.startsWith("/terms");
  const isStandalonePage = isPaymentReturn || isPrivacyPage || isTermsPage;

  const [view, setView] = useState("home");
  const [alertCount, setAlertCount] = useState(0);
  const [seedStatus, setSeedStatus] = useState("idle");

  // Viral referral tracking — if the visitor arrived via `?ref=<share_id>`,
  // remember it for later checkout-conversion attribution and ping the
  // backend (which both records an open event and validates the id).
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const params = new URLSearchParams(window.location.search);
      const ref = params.get("ref");
      if (!ref) return;
      localStorage.setItem("nxt8.share.ref", ref);
      api.shareGet(ref, document.referrer || undefined).catch(() => {
        /* a 404 means the share id is invalid — silently ignore */
      });
    } catch { /* ignore */ }
  }, []);

  // Demo Tour — auto-complete the "open_agents" step as soon as the
  // visitor lands on the Agents view (no matter how they got there).
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (view !== "agents") return;
    try {
      window.dispatchEvent(
        new CustomEvent("nxt8:tour-complete", { detail: { step_id: "open_agents" } })
      );
    } catch { /* ignore */ }
  }, [view]);

  // `/api/seed` is now admin-only (Iteration 1 / Task 3). We no longer
  // auto-trigger it on every page load. To seed demo data, run:
  //   curl -X POST -H "X-Admin-Token: $SEED_ADMIN_TOKEN" $API/api/seed

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
      case "os":
        return <HermesOSView />;
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
      {isStandalonePage ? (
        isPaymentReturn ? (
          <PaymentReturnView />
        ) : isPrivacyPage ? (
          <PrivacyView />
        ) : (
          <TermsView />
        )
      ) : (
        <></>
      )}
      {isStandalonePage ? null : (
        <>
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
      <CookieBanner />
      <DemoTour />
        </>
      )}
    </div>
  );
}

// Lightweight router: pathname + URL fragment.
function AppRouter() {
  if (typeof window === "undefined") return null;
  const path = window.location.pathname || "/";
  const hash = window.location.hash || "";

  // OAuth callback: detect the session_id fragment synchronously
  // (NOT in an effect — that would race with AuthProvider's /me check).
  if (hash.includes("session_id=") || path.startsWith("/auth/callback")) {
    return <AuthCallback />;
  }
  if (path.startsWith("/login")) {
    return <LoginPage />;
  }
  // Standalone public pages are handled inside AppShell.
  if (
    path.startsWith("/payment/return") ||
    path.startsWith("/privacy") ||
    path.startsWith("/terms")
  ) {
    return <AppShell />;
  }
  // Test-mode entry: the site lands DIRECTLY on the home/landing view —
  // no auth wall, no redirect to /login. /login still exists for any
  // user who wants to sign in (CTA in the header), but the landing is
  // fully public.
  return <AppShell />;
}

function App() {
  return (
    <AppErrorBoundary>
      <AuthProvider>
        <AppRouter />
      </AuthProvider>
      {/* Sonner toast portal — rendered once, used by lib/api.js interceptor */}
      <Toaster richColors closeButton position="top-right" />
    </AppErrorBoundary>
  );
}

export default App;
