import React from "react";
import { ChevronRight } from "lucide-react";
import { useT } from "../../../i18n/LanguageContext";

export function WidgetCard({
  title,
  accent = "text-brand-turquoise",
  onOpen,
  testId,
  children,
  status,
}) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className="text-left w-full glass-card window-border glow-turquoise-subtle rounded-2xl p-4 hover:border-brand-turquoise/60 transition-colors group"
      data-testid={testId}
    >
      <div className="flex items-center justify-between mb-2">
        <span className={`font-light text-xs ${accent}`}>{title}</span>
        <div className="flex items-center gap-2">
          {status && (
            <span className="text-[9px] uppercase tracking-widest text-slate-500">
              {status}
            </span>
          )}
          <ChevronRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-brand-turquoise transition-colors" />
        </div>
      </div>
      {children}
    </button>
  );
}

export function Metric({ label, value, accent = "text-brand-turquoise", testId }) {
  return (
    <div
      className="border border-white/5 rounded-lg p-2 bg-brand-dark/30"
      data-testid={testId}
    >
      <div className="text-[9px] uppercase tracking-widest text-slate-500">
        {label}
      </div>
      <div className={`text-sm font-bold mt-0.5 ${accent}`}>{value}</div>
    </div>
  );
}

export function SectionHeader({ title, right }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-brand-turquoise font-light text-xs">{title}</span>
      {right && (
        <span className="text-slate-500 text-[10px] uppercase tracking-widest">
          {right}
        </span>
      )}
    </div>
  );
}

export function BackBar({ title, onBack }) {
  const { t } = useT();
  return (
    <div className="flex items-center justify-between mb-3">
      <button
        onClick={onBack}
        className="text-slate-400 hover:text-brand-turquoise text-[10px] uppercase tracking-widest flex items-center gap-1"
        data-testid="ops-back"
      >
        {t("ui.back_to_ops")}
      </button>
      <span className="text-brand-turquoise font-light text-xs">{title}</span>
    </div>
  );
}

export function EmptyHint({ children, testId }) {
  return (
    <div
      className="text-slate-500 text-xs text-center py-6 border border-dashed border-white/5 rounded-lg"
      data-testid={testId}
    >
      {children}
    </div>
  );
}
