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

export default function BottomNav({ active, onChange, alertCount = 0 }) {
  return (
    <footer
      className="relative mt-2 glass-card window-border glow-turquoise-subtle pt-3 pb-6 px-4 rounded-2xl"
      data-testid="bottom-nav"
    >
      <div className="flex justify-between items-center max-w-md mx-auto">
        {NAV_ITEMS.map((it) => {
          const isActive = active === it.id;
          const Icon = it.icon;
          const showBadge = it.badge && alertCount > 0;
          return (
            <button
              key={it.id}
              onClick={() => onChange(it.id)}
              data-testid={`nav-${it.id}`}
              className={`flex flex-col items-center space-y-1 transition-colors ${
                isActive ? "text-brand-turquoise" : "text-slate-600"
              }`}
            >
              <div
                className={`w-8 h-8 rounded-lg flex items-center justify-center relative ${
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
                    data-testid="alert-badge"
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
      </div>
    </footer>
  );
}
