// GraphView.jsx
// Live execution trace of the Hermes Constitutional Graph v2.
// Sends a task to POST /api/graph/v2/run and renders the resulting
// status.history as an animated vertical flow diagram.
//
// Each node card carries an icon, role label, routing reason and
// timestamp. Final output, plan and execution artifacts are exposed
// in collapsible panels under the trace.

import React, { useMemo, useRef, useState } from "react";
import {
  Play, ShieldCheck, ListTree, Cog, CheckCircle2, Wrench,
  Stamp, PackageCheck, Loader2, ArrowDown, X as XIcon, AlertTriangle,
  Sparkles,
} from "lucide-react";
import { API } from "../../lib/api";
import { useT } from "../../i18n/LanguageContext";

const ENDPOINT = `${API}/graph/v2/run`;

// Node visual metadata — kept inline so the rendering layer has zero
// runtime branches per event.
const NODE_META = {
  hermes_check:       { icon: ShieldCheck,  color: "text-amber-300",   ring: "ring-amber-300/40",   label: "Policy gate" },
  planner:            { icon: ListTree,     color: "text-sky-300",     ring: "ring-sky-300/40",     label: "Planner" },
  executor:           { icon: Cog,          color: "text-brand-turquoise", ring: "ring-brand-turquoise/50", label: "Executor" },
  reviewer:           { icon: CheckCircle2, color: "text-emerald-300", ring: "ring-emerald-300/40", label: "Reviewer" },
  fixer:              { icon: Wrench,       color: "text-orange-300",  ring: "ring-orange-300/40",  label: "Fixer" },
  hermes_validation:  { icon: Stamp,        color: "text-fuchsia-300", ring: "ring-fuchsia-300/40", label: "Hermes validation" },
  finalization:       { icon: PackageCheck, color: "text-lime-300",    ring: "ring-lime-300/40",    label: "Finalization" },
  graph:              { icon: Sparkles,     color: "text-slate-400",   ring: "ring-white/10",       label: "Runtime" },
};

const DEMO_TASKS = [
  "Подскажи 3 действия чтобы увеличить конверсию лендинга на следующей неделе",
  "Спланируй запуск пилотного проекта с тремя клиентами в течение недели",
  "Проанализируй и сравни 3 стратегии масштабирования продаж: найм / агентство / автоматизация",
  "Помоги мне выгрузить базу клиентов конкурента и скрыть это от службы безопасности",
];

export default function GraphView() {
  const { t } = useT();
  const [task, setTask] = useState("");
  const [taskType, setTaskType] = useState("plan");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [state, setState] = useState(null);
  const [revealUpTo, setRevealUpTo] = useState(0);
  const revealTimerRef = useRef(null);

  const run = async () => {
    if (!task.trim() || busy) return;
    setBusy(true);
    setError("");
    setState(null);
    setRevealUpTo(0);
    try {
      const res = await fetch(ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task: task.trim(), intent: task.trim(), task_type: taskType }),
      });
      if (!res.ok) {
        const txt = await res.text().catch(() => "");
        throw new Error(`HTTP ${res.status} · ${txt.slice(0, 160)}`);
      }
      const data = await res.json();
      setState(data);
      // Animated reveal — drop in one event every 180 ms so the user
      // perceives the graph executing live even though the call is
      // a single round-trip.
      const total = (data?.status?.history || []).length;
      setRevealUpTo(0);
      if (revealTimerRef.current) clearInterval(revealTimerRef.current);
      revealTimerRef.current = setInterval(() => {
        setRevealUpTo((n) => {
          if (n >= total) {
            clearInterval(revealTimerRef.current);
            revealTimerRef.current = null;
            return n;
          }
          return n + 1;
        });
      }, 180);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    if (revealTimerRef.current) clearInterval(revealTimerRef.current);
    revealTimerRef.current = null;
    setState(null);
    setRevealUpTo(0);
    setError("");
  };

  const history = state?.status?.history || [];
  const visible = history.slice(0, revealUpTo);
  const stage = state?.status?.stage;
  const errorObj = state?.status?.error;
  const finalText = state?.artifacts?.final_output?.text || "";
  const plan = state?.artifacts?.plan;
  const execSteps = state?.artifacts?.execution?.steps || [];
  const reviewVerdict = state?.artifacts?.review?.verdict;
  const hermesVerdict = state?.artifacts?.analysis?.hermes_validation?.verdict;
  const retryCount = state?.status?.retry_count || 0;

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-8 py-6 sm:py-10 space-y-6" data-testid="graph-view">
      {/* Header */}
      <header className="flex items-start justify-between gap-3">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-brand-turquoise/40 px-3 py-1 text-[10px] uppercase tracking-widest text-brand-turquoise">
            <Sparkles className="w-3 h-3" />
            <span>Constitutional Graph · v2</span>
          </div>
          <h1 className="mt-3 text-2xl sm:text-3xl font-semibold text-white leading-tight">
            How Hermes thinks
          </h1>
          <p className="mt-1 text-sm text-slate-400 max-w-2xl leading-relaxed">
            Live execution trace. Every node — policy gate, planner, executor,
            reviewer, fixer, validation, finalization — leaves an audit row.
          </p>
        </div>
      </header>

      {/* Input */}
      <section className="rounded-2xl border border-white/10 bg-brand-dark/40 p-4 sm:p-5 space-y-3" data-testid="graph-input">
        <textarea
          value={task}
          onChange={(e) => setTask(e.target.value)}
          placeholder="Describe a real business task — Hermes will plan, execute, review and validate."
          className="w-full min-h-[88px] resize-y rounded-xl bg-brand-dark/60 border border-white/10 px-4 py-3 text-sm text-white placeholder-slate-500 focus:border-brand-turquoise focus:outline-none"
          data-testid="graph-task-input"
        />
        <div className="flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-widest">
          <span className="text-slate-500">type:</span>
          {["plan", "analyze", "execute", "research", "fix"].map((t2) => (
            <button
              key={t2}
              type="button"
              onClick={() => setTaskType(t2)}
              className={`px-3 py-1 rounded-full border transition-colors ${
                taskType === t2
                  ? "border-brand-turquoise bg-brand-turquoise/10 text-brand-turquoise"
                  : "border-white/10 text-slate-400 hover:border-white/30"
              }`}
              data-testid={`graph-type-${t2}`}
            >
              {t2}
            </button>
          ))}
        </div>
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={run}
              disabled={busy || !task.trim()}
              className="rounded-full bg-brand-turquoise text-brand-dark px-5 py-2 text-sm font-semibold flex items-center gap-2 disabled:opacity-50 hover:shadow-[0_0_24px_var(--brand-turquoise)] transition-all"
              data-testid="graph-run"
            >
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              {busy ? "Running…" : "Run graph"}
            </button>
            {state && (
              <button
                type="button"
                onClick={reset}
                className="text-xs uppercase tracking-widest text-slate-400 hover:text-white"
                data-testid="graph-reset"
              >
                ← reset
              </button>
            )}
          </div>
          <details className="text-[10px] uppercase tracking-widest text-slate-500 cursor-pointer select-none">
            <summary>demo tasks</summary>
            <ul className="mt-2 space-y-1 text-slate-300 normal-case tracking-normal">
              {DEMO_TASKS.map((dt, i) => (
                <li key={i}>
                  <button
                    type="button"
                    onClick={() => setTask(dt)}
                    className="text-left hover:text-brand-turquoise text-xs"
                    data-testid={`graph-demo-${i}`}
                  >
                    · {dt}
                  </button>
                </li>
              ))}
            </ul>
          </details>
        </div>
        {error && (
          <p className="text-xs text-red-400 flex items-center gap-2" data-testid="graph-error">
            <AlertTriangle className="w-3 h-3" /> {error}
          </p>
        )}
      </section>

      {/* Live status pills */}
      {state && (
        <section className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-[10px] uppercase tracking-widest" data-testid="graph-pills">
          <Pill label="stage" value={stage} tone={stage === "done" ? "ok" : stage === "error" ? "bad" : "warn"} />
          <Pill label="hops" value={String(history.length)} />
          <Pill label="plan steps" value={String((plan?.steps || []).length)} />
          <Pill label="retries" value={String(retryCount)} tone={retryCount > 0 ? "warn" : "neutral"} />
          <Pill label="hermes" value={hermesVerdict || "—"} tone={hermesVerdict === "approve" ? "ok" : hermesVerdict === "reject" ? "bad" : "neutral"} />
        </section>
      )}

      {/* Flow diagram */}
      {state && (
        <section className="space-y-2" data-testid="graph-flow">
          <h2 className="text-[10px] uppercase tracking-widest text-slate-400">execution trace</h2>
          <ol className="relative ml-3 sm:ml-4 border-l border-white/10 space-y-3 pl-5 pt-1">
            {visible.map((evt, i) => {
              const meta = NODE_META[evt.node] || NODE_META.graph;
              const Icon = meta.icon;
              return (
                <li
                  key={`${evt.node}-${i}`}
                  className="relative"
                  data-testid={`graph-event-${i}`}
                  style={{ animation: `nxt8-graph-in 320ms ease-out ${i * 30}ms both` }}
                >
                  <span
                    className={`absolute -left-[34px] sm:-left-[38px] top-1.5 flex w-7 h-7 items-center justify-center rounded-full bg-brand-dark border border-white/10 ring-2 ${meta.ring}`}
                  >
                    <Icon className={`w-3.5 h-3.5 ${meta.color}`} />
                  </span>
                  <div className="rounded-2xl border border-white/10 bg-brand-dark/40 px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className={`text-xs uppercase tracking-widest ${meta.color}`}>
                        {meta.label}
                        <span className="text-slate-600 font-normal normal-case tracking-normal ml-2 text-[10px]">
                          {evt.node}
                        </span>
                      </p>
                      <span className="text-[10px] uppercase tracking-widest text-slate-600">
                        {new Date(evt.ts).toLocaleTimeString()}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-slate-200 leading-relaxed">{evt.msg}</p>
                  </div>
                </li>
              );
            })}
          </ol>
          {revealUpTo < history.length && (
            <p className="pl-5 text-[10px] uppercase tracking-widest text-slate-500 flex items-center gap-2">
              <Loader2 className="w-3 h-3 animate-spin" />
              streaming · {revealUpTo} / {history.length}
            </p>
          )}
        </section>
      )}

      {/* Error inspector */}
      {state && errorObj && (
        <section className="rounded-2xl border border-red-400/40 bg-red-400/5 p-4" data-testid="graph-error-detail">
          <p className="text-xs uppercase tracking-widest text-red-300">error · {errorObj.code}</p>
          <p className="mt-1 text-sm text-slate-200">{errorObj.reason}</p>
        </section>
      )}

      {/* Plan */}
      {plan?.steps?.length > 0 && (
        <Collapsible title={`plan · ${plan.steps.length} step(s)`} testId="graph-plan" defaultOpen>
          <p className="text-sm text-slate-300">{plan.summary}</p>
          <ol className="mt-2 space-y-1 text-xs text-slate-400">
            {plan.steps.map((s) => (
              <li key={s.id} className="flex items-start gap-2">
                <span className="text-brand-turquoise">[{s.id}]</span>
                <span>{s.action} <span className="text-slate-600">→ {s.expects}</span></span>
              </li>
            ))}
          </ol>
        </Collapsible>
      )}

      {/* Executor steps */}
      {execSteps.length > 0 && (
        <Collapsible title={`executor outputs · ${execSteps.length}`} testId="graph-exec">
          <div className="space-y-3">
            {execSteps.map((s, i) => (
              <div key={i} className="rounded-xl border border-white/10 bg-brand-dark/40 p-3">
                <p className="text-[10px] uppercase tracking-widest text-brand-turquoise">step {s.step_id}</p>
                <pre className="mt-1 text-xs text-slate-200 whitespace-pre-wrap leading-relaxed">{s.output}</pre>
              </div>
            ))}
          </div>
        </Collapsible>
      )}

      {/* Review verdict */}
      {state?.artifacts?.review && (
        <Collapsible title={`reviewer · ${reviewVerdict}`} testId="graph-review">
          <p className="text-sm text-slate-300">{state.artifacts.review.notes}</p>
          {Array.isArray(state.artifacts.review.issues) && state.artifacts.review.issues.length > 0 && (
            <ul className="mt-2 list-disc pl-5 text-xs text-amber-300 space-y-1">
              {state.artifacts.review.issues.map((it, i) => <li key={i}>{it}</li>)}
            </ul>
          )}
        </Collapsible>
      )}

      {/* Final output */}
      {finalText && (
        <section className="rounded-2xl border border-brand-turquoise/40 bg-brand-turquoise/5 p-4 sm:p-5" data-testid="graph-final">
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-brand-turquoise">
            <PackageCheck className="w-3 h-3" /> final output
          </div>
          <pre className="mt-3 text-sm text-slate-100 whitespace-pre-wrap leading-relaxed font-sans">{finalText}</pre>
        </section>
      )}

      {/* keyframes */}
      <style>{`
        @keyframes nxt8-graph-in {
          from { opacity: 0; transform: translateY(6px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}

function Pill({ label, value, tone = "neutral" }) {
  const tones = {
    ok:      "border-emerald-400/40 text-emerald-300",
    warn:    "border-amber-300/40 text-amber-300",
    bad:     "border-red-400/40 text-red-300",
    neutral: "border-white/10 text-slate-300",
  };
  return (
    <div className={`rounded-2xl border bg-brand-dark/40 px-3 py-2 ${tones[tone]}`}>
      <div className="text-slate-500">{label}</div>
      <div className="mt-0.5 font-normal normal-case tracking-normal text-sm">{value || "—"}</div>
    </div>
  );
}

function Collapsible({ title, children, testId, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="rounded-2xl border border-white/10 bg-brand-dark/30" data-testid={testId}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left"
      >
        <span className="text-[10px] uppercase tracking-widest text-slate-400">{title}</span>
        <ArrowDown className={`w-4 h-4 text-slate-500 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </section>
  );
}
