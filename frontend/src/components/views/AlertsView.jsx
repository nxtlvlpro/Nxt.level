import React, { useEffect, useState } from "react";
import { Bell, AlertTriangle, Info } from "lucide-react";
import api from "../../lib/api";
import CollapsibleCard from "../CollapsibleCard";

const SEV_STYLE = {
  critical: { color: "text-red-400", border: "border-red-500/40", icon: AlertTriangle },
  warning: { color: "text-orange-400", border: "border-orange-500/40", icon: AlertTriangle },
  info: { color: "text-brand-turquoise", border: "border-brand-turquoise/40", icon: Info },
};

export default function AlertsView() {
  const [alerts, setAlerts] = useState([]);

  useEffect(() => {
    api.alerts(40).then((d) => setAlerts(d.alerts || [])).catch(() => {});
  }, []);

  return (
    <div className="lg:max-w-3xl lg:mx-auto">
      <CollapsibleCard
        storageKey="alerts-feed"
        testId="alerts-view"
      title={
        <span className="text-brand-turquoise font-light text-xs flex items-center gap-2">
          <Bell className="w-3.5 h-3.5" /> alerts.feed
        </span>
      }
      titleRight={
        <span className="text-slate-500 text-[10px] uppercase tracking-widest">
          {alerts.length} events
        </span>
      }
    >
      <div className="space-y-2">
        {alerts.length === 0 && (
          <div className="text-slate-500 text-xs text-center py-8">
            всё спокойно — алертов нет
          </div>
        )}
        {alerts.map((a) => {
          const style = SEV_STYLE[a.severity] || SEV_STYLE.info;
          const Icon = style.icon;
          return (
            <div
              key={a.id}
              className={`border ${style.border} bg-brand-dark/40 rounded-xl p-3 flex items-start gap-3`}
              data-testid={`alert-${a.id}`}
            >
              <Icon className={`w-4 h-4 ${style.color} shrink-0 mt-0.5`} />
              <div className="min-w-0 flex-1">
                <div className="flex justify-between items-center">
                  <span
                    className={`text-[9px] uppercase tracking-widest ${style.color}`}
                  >
                    {a.severity} · {a.source}
                  </span>
                  <span className="text-[9px] text-slate-600">
                    {new Date(a.created_at).toLocaleTimeString("ru-RU")}
                  </span>
                </div>
                <div className="text-slate-200 text-[12px] mt-1 break-words">
                  {a.message}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </CollapsibleCard>
    </div>
  );
}
