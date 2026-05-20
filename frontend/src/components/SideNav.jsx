import React from "react";
import {
  Home,
  Terminal,
  Users,
  Map,
  Bell,
  Mic,
  LayoutGrid,
} from "lucide-react";

const NAV_ITEMS = [
  { id: "home", label: "HOME", icon: Home },
  { id: "cmd", label: "CMD", icon: Terminal },
  { id: "ops", label: "OPS", icon: LayoutGrid },
  { id: "agents", label: "AGENTS", icon: Users },
  { id: "map", label: "MAP", icon: Map },
  { id: "alerts", label: "ALERTS", icon: Bell, badge: true },
  { id: "mic", label: "MIC", icon: Mic },
];

export default function SideNav({ active, onChange, alertCount = 0 }) {
  return (
    <aside
      className="hidden lg:flex flex-col w-24 xl:w-28 shrink-0 py-6 px-3 border-r border-white/5 bg-brand-dark/40 backdrop-blur-md gap-2"
      data-testid="side-nav"
    >
      {NAV_ITEMS.map((it) => {
        const isActive = active === it.id;
        const Icon = it.icon;
        const showBadge = it.badge && alertCount > 0;
        return (
          <button
            key={it.id}
            onClick={() => onChange(it.id)}
            data-testid={`sidenav-${it.id}`}
            className={`group flex flex-col items-center justify-center gap-1.5 py-3 rounded-xl transition-colors ${
              isActive
                ? "text-brand-turquoise bg-brand-turquoise/5 border border-brand-turquoise/30"
                : "text-slate-500 hover:text-slate-200 border border-transparent"
            }`}
          >
            <div
              className={`w-9 h-9 rounded-lg flex items-center justify-center relative ${
                isActive
                  ? "neo-icon-active"
                  : it.id === "mic"
                  ? "mic-nav-pulse"
                  : ""
              }`}
            >
              <Icon className="w-5 h-5" strokeWidth={1.6} />
              {showBadge && (
                <span
                  className="absolute top-0 right-1 w-2 h-2 bg-red-500 rounded-full border border-brand-dark"
                  data-testid="sidenav-alert-badge"
                />
              )}
            </div>
            <span
              className={`text-[9px] uppercase tracking-widest ${
                isActive ? "font-bold" : "font-light"
              }`}
            >
              {it.label}
            </span>
          </button>
        );
      })}
    </aside>
  );
}
