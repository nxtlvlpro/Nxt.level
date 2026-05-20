import React, { useCallback, useEffect, useState } from "react";
import { Send } from "lucide-react";
import api from "../../../lib/api";
import { BackBar, SectionHeader, EmptyHint } from "./widgets";

function DeptTag({ name }) {
  return (
    <span className="text-[9px] uppercase tracking-widest px-1.5 py-0.5 rounded bg-brand-turquoise/15 text-brand-turquoise">
      {name}
    </span>
  );
}

function TaskCard({ task }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <button
      onClick={() => setExpanded((v) => !v)}
      className="text-left w-full border border-white/5 hover:border-brand-turquoise/40 bg-brand-dark/40 rounded-xl p-3 transition-colors"
      data-testid={`crossdept-task-${task.id}`}
    >
      <div className="flex justify-between items-start gap-2">
        <div className="min-w-0 flex-1">
          <div className="text-slate-200 text-[12px] truncate">{task.query}</div>
          <div className="flex flex-wrap gap-1 mt-1.5">
            {(task.departments || []).map((d) => (
              <DeptTag key={d} name={d} />
            ))}
            {task.multi_department && (
              <span className="text-[9px] uppercase tracking-widest px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400">
                multi
              </span>
            )}
          </div>
        </div>
        <div className="text-[9px] text-slate-600 whitespace-nowrap">
          {new Date(task.created_at).toLocaleTimeString("ru-RU")}
        </div>
      </div>
      {expanded && task.synthesis && (
        <div className="mt-3 pt-3 border-t border-white/5 text-[11px] text-slate-300 whitespace-pre-wrap">
          {task.synthesis}
          <div className="mt-2 text-[9px] text-slate-500">
            confidence {Math.round((task.confidence || 0) * 100)}% ·{" "}
            {task.provider || "—"}
          </div>
        </div>
      )}
    </button>
  );
}

export default function CrossDeptPanel({ onBack }) {
  const [query, setQuery] = useState("");
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [latest, setLatest] = useState(null);

  const refresh = useCallback(
    () =>
      api
        .crossDeptTasks(20)
        .then((d) => setTasks(d.tasks || []))
        .catch(() => {}),
    []
  );

  useEffect(() => {
    refresh();
  }, [refresh]);

  const run = async () => {
    const q = query.trim();
    if (!q || loading) return;
    setLoading(true);
    try {
      const res = await api.crossDeptCoordinate({ query: q });
      setLatest(res);
      setQuery("");
      refresh();
    } catch (e) {
      setLatest({ error: e.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <section
      className="glass-card rounded-2xl window-border glow-turquoise-subtle p-4 space-y-3"
      data-testid="ops-crossdept"
    >
      <BackBar title="cross-dept · coordinator" onBack={onBack} />

      <div className="space-y-2">
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
              e.preventDefault();
              run();
            }
          }}
          placeholder="Запрос, затрагивающий несколько отделов… (например: «что у нас по продажам и поддержке?»). Ctrl/⌘+Enter — отправить"
          rows={2}
          className="w-full bg-brand-dark/60 border border-white/10 rounded-xl px-3 py-2 text-[12px] text-slate-200 placeholder:text-slate-600 outline-none focus:border-brand-turquoise/50 resize-none"
          data-testid="crossdept-input"
        />
        <div className="flex justify-end">
          <button
            onClick={run}
            disabled={loading || !query.trim()}
            className="neo-btn rounded-full px-4 py-2 text-brand-turquoise text-[10px] uppercase tracking-widest flex items-center gap-2 disabled:opacity-40"
            data-testid="crossdept-run"
          >
            <Send className="w-3 h-3" />
            {loading ? "координирую…" : "coordinate"}
          </button>
        </div>
      </div>

      {latest && !latest.error && (
        <div className="border border-brand-turquoise/30 bg-brand-turquoise/5 rounded-xl p-3 space-y-2">
          <div className="flex flex-wrap gap-1.5 items-center">
            <span className="text-[10px] uppercase tracking-widest text-brand-turquoise">
              synthesis
            </span>
            {(latest.departments || []).map((d) => (
              <DeptTag key={d} name={d} />
            ))}
          </div>
          <div className="text-[12px] text-slate-200 whitespace-pre-wrap">
            {latest.synthesis}
          </div>
          <div className="text-[9px] text-slate-500">
            confidence {Math.round((latest.confidence || 0) * 100)}% ·{" "}
            {latest.provider || "—"}
          </div>
        </div>
      )}

      <SectionHeader
        title="recent tasks"
        right={`${tasks.length} items`}
      />
      <div className="space-y-2">
        {tasks.length === 0 && (
          <EmptyHint testId="crossdept-empty">
            ещё не было координаций — запустите первую
          </EmptyHint>
        )}
        {tasks.map((t) => (
          <TaskCard key={t.id} task={t} />
        ))}
      </div>
    </section>
  );
}
