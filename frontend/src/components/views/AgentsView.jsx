import React, { useEffect, useState } from "react";
import { ChevronRight } from "lucide-react";
import api from "../../lib/api";
import CollapsibleCard from "../CollapsibleCard";

const LEVEL_COLOR = {
  junior: "text-orange-400",
  mid: "text-blue-400",
  senior: "text-brand-turquoise",
  lead: "text-emerald-400",
  strategist: "text-purple-400",
};

const PATTERN_LABEL = {
  low_accuracy: "точность ниже p30",
  high_escalation: "много эскалаций",
  repeating_errors: "повторяющиеся ошибки",
};

function EmployeeRow({ emp, patterns, onClick }) {
  const epats = patterns.filter((p) => p.employee_id === emp.employee_id);
  // Dedupe by pattern type, count occurrences
  const counts = {};
  for (const p of epats) {
    counts[p.pattern] = (counts[p.pattern] || 0) + 1;
  }
  const uniquePatterns = Object.entries(counts);
  return (
    <button
      onClick={() => onClick(emp)}
      className="w-full text-left bg-brand-dark/50 border border-white/5 hover:border-brand-turquoise/40 rounded-xl p-3 flex items-center justify-between transition-colors"
      data-testid={`emp-row-${emp.employee_id}`}
    >
      <div className="min-w-0">
        <div className="text-slate-200 text-xs font-medium truncate">
          {emp.name}
        </div>
        <div className="flex items-center gap-2 mt-0.5 text-[10px] tracking-widest uppercase">
          <span className={LEVEL_COLOR[emp.level] || "text-slate-400"}>
            {emp.level}
          </span>
          <span className="text-slate-600">·</span>
          <span className="text-slate-400">{emp.department}</span>
        </div>
        {uniquePatterns.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1">
            {uniquePatterns.map(([pattern, count]) => (
              <span
                key={pattern}
                className="text-[9px] px-1.5 py-0.5 rounded-md bg-red-500/15 text-red-400"
              >
                ! {PATTERN_LABEL[pattern] || pattern}
                {count > 1 && <span className="opacity-60"> ×{count}</span>}
              </span>
            ))}
          </div>
        )}
      </div>
      <ChevronRight className="w-4 h-4 text-slate-600" />
    </button>
  );
}

function EmployeeDetail({ employee, onClose }) {
  const [summary, setSummary] = useState(null);
  useEffect(() => {
    if (!employee) return;
    api.employeeSummary(employee.employee_id).then(setSummary).catch(() => {});
  }, [employee]);
  if (!employee) return null;
  return (
    <div
      className="glass-card rounded-2xl window-border p-4 space-y-3"
      data-testid="emp-detail"
    >
      <div className="flex justify-between items-start">
        <div>
          <div className="text-brand-turquoise font-light text-xs uppercase tracking-widest">
            mentor · profile
          </div>
          <div className="text-slate-100 text-lg font-medium mt-1">
            {employee.name}
          </div>
          <div className="text-[10px] uppercase tracking-widest text-slate-400 mt-0.5">
            {employee.level} · {employee.department} ·{" "}
            {employee.experience_months}mo
          </div>
        </div>
        <button
          onClick={onClose}
          className="text-slate-500 hover:text-slate-200 text-xs"
          data-testid="emp-detail-close"
        >
          close
        </button>
      </div>
      {summary && summary.history && summary.history.length > 0 && (
        <div className="grid grid-cols-2 gap-2">
          <Metric label="accuracy" value={summary.history[0].accuracy.toFixed(2)} />
          <Metric
            label="escalation"
            value={summary.history[0].escalation_rate.toFixed(2)}
          />
          <Metric label="speed" value={summary.history[0].speed.toFixed(2)} />
          <Metric
            label="err repeat"
            value={summary.history[0].error_repeat}
          />
        </div>
      )}
      {summary && summary.open_patterns && summary.open_patterns.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-[10px] uppercase tracking-widest text-slate-500">
            open patterns
          </div>
          {summary.open_patterns.map((p) => (
            <div
              key={p.id}
              className="border border-red-500/30 bg-red-500/5 rounded-md p-2 text-[11px]"
            >
              <div className="text-red-400 uppercase tracking-widest text-[9px]">
                {p.pattern}
              </div>
              <div className="text-slate-300 mt-0.5">{p.details}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="border border-white/5 rounded-lg p-2">
      <div className="text-[9px] uppercase text-slate-500">{label}</div>
      <div className="text-brand-turquoise text-sm font-bold">{value}</div>
    </div>
  );
}

export default function AgentsView() {
  const [employees, setEmployees] = useState([]);
  const [patterns, setPatterns] = useState([]);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const load = async (retry = 0) => {
      try {
        const emp = await api.employees();
        const pat = await api.patterns();
        if (cancelled) return;
        setEmployees(emp.employees || []);
        setPatterns(pat.patterns || []);
        // If still empty and seed may not have completed yet — retry once
        if ((emp.employees || []).length === 0 && retry < 2) {
          setTimeout(() => load(retry + 1), 1200);
        }
      } catch {
        if (retry < 2) setTimeout(() => load(retry + 1), 1500);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div
      className="space-y-3 lg:space-y-0 lg:grid lg:grid-cols-2 lg:gap-4"
      data-testid="agents-view"
    >
      <CollapsibleCard
        storageKey="agents-list"
        testId="agents-list-card"
        title={
          <span className="text-brand-turquoise font-light text-xs">
            mentor.engine
          </span>
        }
        titleRight={
          <span className="text-slate-500 text-[10px] uppercase tracking-widest">
            {employees.length} employees · {patterns.length} weak
          </span>
        }
      >
        <div className="space-y-2">
          {employees.map((e) => (
            <EmployeeRow
              key={e.employee_id}
              emp={e}
              patterns={patterns}
              onClick={setSelected}
            />
          ))}
          {employees.length === 0 && (
            <div className="text-slate-500 text-xs text-center py-6">
              нет данных — запустите seed
            </div>
          )}
        </div>
      </CollapsibleCard>
      {selected && (
        <EmployeeDetail
          employee={selected}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
