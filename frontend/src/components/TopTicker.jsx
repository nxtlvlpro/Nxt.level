import React from "react";

const TICKER_ITEMS = [
  { name: "ALEX M.", value: 9.1, delta: 0.4 },
  { name: "CARLA R.", value: 8.4, delta: 0.2 },
  { name: "MIKE C.", value: 9.6, delta: 0.1 },
  { name: "ROI/HR", value: 1.2, delta: 0.18 },
  { name: "CONF AVG", value: 0.82, delta: 0.03 },
  { name: "ALERTS", value: 2, delta: -1 },
  { name: "MEM DOCS", value: 6, delta: 0 },
];

export default function TopTicker() {
  const items = [...TICKER_ITEMS, ...TICKER_ITEMS, ...TICKER_ITEMS];
  return (
    <nav
      className="relative z-10 px-4 py-2 border-b border-white/5 led-ticker overflow-hidden bg-brand-dark/80 backdrop-blur-md flex items-center gap-3"
      data-testid="top-ticker"
    >
      <span className="text-brand-turquoise font-medium shrink-0 text-[10px] uppercase tracking-widest z-10 bg-brand-dark px-1">
        AI INDEX:
      </span>
      <div className="flex items-center text-[10px] uppercase tracking-widest text-slate-500 overflow-hidden flex-1">
        <div className="ticker-track flex items-center space-x-6 whitespace-nowrap">
          {items.map((it, idx) => (
            <span key={`${it.name}-${idx}`} className="text-slate-300 shrink-0">
              {it.name}{" "}
              <span
                className={
                  it.delta >= 0 ? "text-brand-turquoise" : "text-orange-400"
                }
              >
                {it.delta >= 0 ? "▲" : "▼"} {it.value} {it.delta >= 0 ? "+" : ""}
                {it.delta}
              </span>
            </span>
          ))}
        </div>
      </div>
    </nav>
  );
}
