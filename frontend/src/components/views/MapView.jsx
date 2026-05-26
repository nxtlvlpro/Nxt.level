import React, { useEffect, useState } from "react";
import api from "../../lib/api";
import CollapsibleCard from "../CollapsibleCard";
import { useT } from "../../i18n/LanguageContext";

function StatCard({ label, value, accent = "text-brand-turquoise", testId }) {
  return (
    <div
      className="bg-brand-dark/40 border border-white/5 rounded-xl p-3"
      data-testid={testId}
    >
      <div className="text-[9px] uppercase tracking-widest text-slate-500">
        {label}
      </div>
      <div className={`mt-1 text-lg font-bold ${accent}`}>{value}</div>
    </div>
  );
}

function fmtUsd(n) {
  if (n == null) return "—";
  return `$${Number(n).toFixed(2)}`;
}
function fmtPct(n) {
  if (n == null) return "—";
  return `${(Number(n) * 100).toFixed(1)}%`;
}

export default function MapView() {
  const { t } = useT();
  const [snap, setSnap] = useState(null);
  const [trend, setTrend] = useState([]);

  useEffect(() => {
    api.roiCurrent().then(setSnap).catch(() => {});
    api.roiTrend(24).then((d) => setTrend(d.items || [])).catch(() => {});
  }, []);

  const byAgentCost = Object.entries(snap?.by_agent_cost || {}).sort(
    (a, b) => b[1] - a[1]
  );

  return (
    <div
      className="space-y-3 lg:space-y-0 lg:grid lg:grid-cols-2 lg:gap-4"
      data-testid="map-view"
    >
      <CollapsibleCard
        storageKey="map-roi"
        testId="map-roi-card"
        className="lg:col-span-2"
        title={
          <span className="text-brand-turquoise font-light text-xs">
            {t("map.title")}
          </span>
        }
        titleRight={
          <span className="text-slate-500 text-[10px] uppercase tracking-widest">
            {snap?.alert ? t("map.alert") : t("map.stable")}
          </span>
        }
      >
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-2">
            <StatCard
              label="ROI/h"
              value={fmtPct(snap?.roi)}
              accent={
                snap?.roi != null && snap.roi < 0
                  ? "text-orange-400"
                  : "text-brand-turquoise"
              }
              testId="roi-card"
            />
            <StatCard
              label="Cost"
              value={fmtUsd(snap?.total_cost)}
              accent="text-orange-400"
              testId="cost-card"
            />
            <StatCard
              label="Revenue"
              value={fmtUsd(snap?.total_revenue)}
              accent="text-emerald-400"
              testId="rev-card"
            />
          </div>
          {snap?.alert && (
            <div
              className="border border-orange-500/30 bg-orange-500/5 rounded-md p-2 text-[11px] text-orange-300"
              data-testid="roi-alert"
            >
              {snap.alert}
            </div>
          )}
        </div>
      </CollapsibleCard>

      <CollapsibleCard
        storageKey="map-cost"
        testId="map-cost-card"
        title={
          <span className="text-brand-turquoise font-light text-xs">
            {t("map.cost.title")}
          </span>
        }
      >
        <div className="space-y-2">
          {byAgentCost.length === 0 && (
            <div className="text-slate-500 text-xs">{t("map.no_data")}</div>
          )}
          {byAgentCost.map(([agent, amount]) => {
            const max = byAgentCost[0][1] || 1;
            const w = Math.min(100, (amount / max) * 100);
            return (
              <div key={agent} data-testid={`bar-${agent}`}>
                <div className="flex justify-between text-[11px] text-slate-300">
                  <span>{agent}</span>
                  <span className="text-orange-400">${amount.toFixed(2)}</span>
                </div>
                <div className="h-1.5 bg-white/5 rounded-full overflow-hidden mt-1">
                  <div
                    className="h-full bg-gradient-to-r from-brand-turquoise to-orange-400 rounded-full"
                    style={{ width: `${w}%` }}
                  ></div>
                </div>
              </div>
            );
          })}
        </div>
      </CollapsibleCard>

      <CollapsibleCard
        storageKey="map-trend"
        testId="map-trend-card"
        title={
          <span className="text-brand-turquoise font-light text-xs">
            {t("map.trend.title")}
          </span>
        }
        titleRight={
          <span className="text-slate-500 text-[10px]">
            {t("map.trend.hours", { n: trend.length })}
          </span>
        }
      >
        <div className="flex items-end gap-0.5 h-20" data-testid="roi-trend-bars">
          {trend.length === 0 && (
            <div className="text-slate-500 text-xs">{t("map.trend.collecting")}</div>
          )}
          {trend
            .slice()
            .reverse()
            .map((h, i) => {
              const v = h.roi == null ? 0 : h.roi;
              const norm = Math.max(-1, Math.min(1, v));
              const height = `${Math.abs(norm) * 90 + 4}%`;
              const bg = norm < 0 ? "bg-orange-400/70" : "bg-brand-turquoise/70";
              return (
                <div
                  key={h.hour_end || `trend-${i}`}
                  className={`flex-1 ${bg} rounded-sm`}
                  style={{ height }}
                  title={`${(v * 100).toFixed(1)}%`}
                />
              );
            })}
        </div>
      </CollapsibleCard>
    </div>
  );
}
