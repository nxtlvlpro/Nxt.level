import React from "react";
import {
  Home,
  Users,
  Map,
  Bell,
  Mic,
} from "lucide-react";

// Mobile bottom navigation — strictly 5 items, designed to fit on a 360px
// screen with no horizontal scroll.
//
// The other views (cmd, ops, graph, os) are now reachable from the header
// burger menu (see `BurgerMenu`). On lg+ screens this component is hidden
// anyway because `SideNav` takes over with the full 9-item list.
const NAV_ITEMS = [
  { id: "home",   label: "HOME",   icon: Home },
  { id: "agents", label: "AGENTS", icon: Users },
  { id: "map",    label: "MAP",    icon: Map },
  { id: "alerts", label: "ALERTS", icon: Bell, badge: true },
  { id: "mic",    label: "MIC",    icon: Mic },
];

export default function BottomNav({ active, onChange, alertCount = 0 }) {
  return (
    <footer
      className="relative mt-2 glass-card window-border glow-turquoise-subtle pt-3 pb-6 px-3 rounded-2xl"
      data-testid="bottom-nav"
    >
      <div className="flex justify-between items-center w-full max-w-md mx-auto">
        {NAV_ITEMS.map((it) => {
          const isActive = active === it.id;
          const Icon = it.icon;
          const showBadge = it.badge && alertCount > 0;
          return (
            <button
              key={it.id}
              onClick={() => onChange(it.id)}
              data-testid={`nav-${it.id}`}
              className={`flex flex-col items-center space-y-1 transition-colors min-w-0 flex-1 ${
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
