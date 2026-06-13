/* eslint-disable */
import React, { useCallback, useEffect, useState } from "react";
import {
  Send,
  RefreshCw,
  Plus,
  Bot,
  Loader2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ArrowUpRight,
} from "lucide-react";
import api from "../../../lib/api";
import { BackBar, SectionHeader, EmptyHint } from "./widgets";
import { useT } from "../../../i18n/LanguageContext";

function statusDotColor(status) {
  if (status === "online") return "bg-emerald-400";
  if (status === "degraded") return "bg-yellow-400";
  if (status === "loading") return "bg-slate-400 animate-pulse";
  return "bg-red-400";
}

function StatusDot({ status }) {
  const color = statusDotColor(status);
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${color} shadow-[0_0_8px_currentColor]`}
    />
  );
}

function formatPersonaLabel(persona) {
  return String(persona || "agent")
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatConfidence(value) {
  if (typeof value !== "number") return "—";
  return `${Math.round(value * 100)}%`;
}

function formatLatency(value) {
  if (typeof value !== "number") return "—";
  return `${Math.round(value)} ms`;
}

function benchmarkState(row) {
  if (!row?.success || row?.error) {
    return {
      icon: XCircle,
      tone: "text-rose-300",
      bg: "bg-rose-500/10 ring-rose-400/30",
      label: "issue",
    };
  }
  if ((row?.confidence ?? 0) > 0.6) {
    return {
      icon: CheckCircle2,
      tone: "text-emerald-300",
      bg: "bg-emerald-500/10 ring-emerald-400/30",
      label: "healthy",
    };
  }
  return {
    icon: AlertTriangle,
    tone: "text-amber-300",
    bg: "bg-amber-500/10 ring-amber-400/30",
    label: "low-confidence",
  };
}

function AuditMetricCard({ label, value, hint, danger = false, testId }) {
  return (
    <div
      className={`rounded-2xl border p-4 ${danger ? "border-rose-400/30 bg-rose-500/10" : "border-emerald-400/20 bg-emerald-500/5"}`}
      data-testid={testId}
    >
      <div className="text-[10px] uppercase tracking-[0.24em] text-white/45" data-testid={`${testId}-label`}>
        {label}
      </div>
      <div
        className={`mt-2 text-3xl font-semibold ${danger ? "text-rose-200" : "text-white"}`}
        data-testid={`${testId}-value`}
      >
        {value}
      </div>
      <div className="mt-2 text-[11px] text-white/45" data-testid={`${testId}-hint`}>
        {hint}
      </div>
    </div>
  );
}

function AuditBenchmarkRow({ row }) {
  const state = benchmarkState(row);
  const Icon = state.icon;
  return (
    <div
      className="grid grid-cols-[auto,1fr,auto] gap-3 items-center rounded-xl border border-white/8 bg-brand-dark/40 px-3 py-3"
      data-testid={`hermes-audit-benchmark-row-${row.persona}`}
    >
      <div
        className={`inline-flex h-9 w-9 items-center justify-center rounded-full ring-1 ${state.bg}`}
        data-testid={`hermes-audit-benchmark-state-${row.persona}`}
      >
        <Icon className={`w-4 h-4 ${state.tone}`} />
      </div>

      <div className="min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm text-white" data-testid={`hermes-audit-benchmark-persona-${row.persona}`}>
            {formatPersonaLabel(row.persona)}
          </span>
          <span
            className="text-[10px] uppercase tracking-[0.2em] text-white/35"
            data-testid={`hermes-audit-benchmark-provider-${row.persona}`}
          >
            {row.provider || state.label}
          </span>
        </div>
        <div
          className="mt-1 text-[11px] text-white/45 flex flex-wrap gap-x-3 gap-y-1"
          data-testid={`hermes-audit-benchmark-meta-${row.persona}`}
        >
          <span>confidence · {formatConfidence(row.confidence)}</span>
          <span>latency · {formatLatency(row.latency_ms)}</span>
          {row.error ? <span className="text-rose-300">{row.error}</span> : null}
        </div>
      </div>

      <div
        className={`text-[10px] uppercase tracking-[0.2em] ${state.tone}`}
        data-testid={`hermes-audit-benchmark-label-${row.persona}`}
      >
        {state.label}
      </div>
    </div>
  );
}

function findingTone(urgency) {
  if (urgency === "high") {
    return "border-rose-400/30 bg-rose-500/10 text-rose-100";
  }
  if (urgency === "medium") {
    return "border-amber-400/30 bg-amber-500/10 text-amber-100";
  }
  return "border-emerald-400/30 bg-emerald-500/10 text-emerald-100";
}

function AnalystFindingRow({ finding }) {
  return (
    <li
      className={`rounded-xl border px-3 py-3 space-y-1 ${findingTone(finding.urgency)}`}
      data-testid={`analyst-finding-${finding.id}`}
    >
      <div className="flex items-center justify-between gap-3">
        <strong className="text-sm uppercase tracking-[0.18em]" data-testid={`analyst-finding-type-${finding.id}`}>
          {finding.type}
        </strong>
        <span className="text-[10px] uppercase tracking-[0.18em]" data-testid={`analyst-finding-urgency-${finding.id}`}>
          {finding.urgency}
        </span>
      </div>
      <div className="text-[11px] text-white/60" data-testid={`analyst-finding-time-${finding.id}`}>
        {finding.timestamp ? new Date(finding.timestamp).toLocaleTimeString() : "—"}
      </div>
      <div className="text-[12px] text-white/80 leading-relaxed" data-testid={`analyst-finding-summary-${finding.id}`}>
        {finding.summary || "—"}
      </div>
      {finding.resolved ? (
        <span className="text-green-400 text-[9px]" data-testid={`analyst-finding-resolved-${finding.id}`}>
          ✓ Решено
        </span>
      ) : null}
    </li>
  );
}

function JobRow({ job }) {
  return (
    <div
      className="border border-white/5 bg-brand-dark/40 rounded-xl p-3"
      data-testid={`hermes-job-${job.job_id || job.id}`}
    >
      <div className="flex justify-between items-center mb-1">
        <span className="text-[10px] uppercase tracking-widest text-purple-400">
          {job.name || job.job_id || "job"}
        </span>
        <span className="text-[9px] text-slate-500">
          {job.schedule || "manual"}
        </span>
      </div>
      <div className="text-[11px] text-slate-300 line-clamp-2">
        {job.prompt || job.input || "—"}
      </div>
      {job.status && (
        <div className="text-[9px] uppercase tracking-widest text-slate-500 mt-1">
          status · {job.status}
        </div>
      )}
    </div>
  );
}

function CreateJobForm({ onCreated }) {
  const { t } = useT();
  const [open, setOpen] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [schedule, setSchedule] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    if (!prompt.trim() || submitting) return;
    setSubmitting(true);
    setError("");
    try {
      const res = await api.hermesJobCreate({
        prompt: prompt.trim(),
        schedule: schedule.trim() || undefined,
        deliver: "log",
      });
      if (!res.ok) {
        setError(
          t("ops.hermes.error.unavailable", {
            code: res.status_code || "—",
            msg: res.error || t("ops.hermes.error.gateway_hint"),
          })
        );
      } else {
        setPrompt("");
        setSchedule("");
        setOpen(false);
        onCreated?.();
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="neo-btn rounded-full px-3 py-1.5 text-purple-400 text-[10px] uppercase tracking-widest flex items-center gap-1.5"
        data-testid="hermes-create-open"
      >
        <Plus className="w-3 h-3" /> создать задание
      </button>
    );
  }

  return (
    <div
      className="border border-purple-500/30 bg-purple-500/5 rounded-xl p-3 space-y-2"
      data-testid="hermes-create-form"
    >
      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="prompt для фонового задания (Hermes выполнит асинхронно)"
        rows={2}
        className="w-full bg-brand-dark/60 border border-white/10 rounded-lg px-3 py-2 text-[12px] outline-none focus:border-purple-500/50 resize-none"
        data-testid="hermes-prompt"
      />
      <input
        value={schedule}
        onChange={(e) => setSchedule(e.target.value)}
        placeholder="cron (опционально, например: 0 9 * * *)"
        className="w-full bg-brand-dark/60 border border-white/10 rounded-lg px-3 py-2 text-[11px] outline-none focus:border-purple-500/50"
        data-testid="hermes-schedule"
      />
      {error && (
        <div className="text-[10px] text-red-400 border border-red-500/30 rounded px-2 py-1">
          {error}
        </div>
      )}
      <div className="flex justify-end gap-2">
        <button
          onClick={() => setOpen(false)}
          className="text-slate-500 text-[10px] uppercase tracking-widest px-2"
        >
          cancel
        </button>
        <button
          onClick={submit}
          disabled={submitting || !prompt.trim()}
          className="neo-btn rounded-full px-3 py-1.5 text-purple-400 text-[10px] uppercase tracking-widest flex items-center gap-1.5 disabled:opacity-40"
          data-testid="hermes-create-submit"
        >
          <Send className="w-3 h-3" />
          {submitting ? "submitting…" : "submit"}
        </button>
      </div>
    </div>
  );
}

export default function HermesPanel({ onBack }) {
  const { t } = useT();
  const [health, setHealth] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [telegram, setTelegram] = useState(null);
  const [audit, setAudit] = useState(null);
  const [analystFindings, setAnalystFindings] = useState([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState("");
  const [firstLoaded, setFirstLoaded] = useState(false);

  const refresh = useCallback(async () => {
    const [h, j, tg] = await Promise.all([
      api.hermesHealth().catch(() => null),
      api.hermesJobsList().catch(() => ({ jobs: [] })),
      api.telegramStatus().catch(() => null),
    ]);
    setHealth(h);
    setJobs(j.jobs || []);
    setTelegram(tg);
    setFirstLoaded(true);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const loadFindings = async () => {
      try {
        const res = await api.analystFindings(5);
        setAnalystFindings(res.findings || []);
      } catch (err) {
        console.warn("Не удалось загрузить findings аналитика", err);
      }
    };
    loadFindings();
  }, []);

  const runAudit = async () => {
    if (auditLoading) return;
    setAuditLoading(true);
    setAuditError("");
    try {
      const res = await api.hermesSelfAudit();
      setAudit(res);
    } catch (e) {
      setAuditError(e?.response?.data?.detail || e?.message || "Не удалось запустить аудит");
    } finally {
      setAuditLoading(false);
    }
  };

  const openTelegram = () => {
    if (!telegram?.connected || !telegram?.bot_username) return;
    window.open(`https://t.me/${telegram.bot_username}`, "_blank", "noopener,noreferrer");
  };

  const handleEscalate = async (id) => {
    try {
      await api.escalateFinding(id);
      const res = await api.analystFindings(5);
      setAnalystFindings(res.findings || []);
    } catch (err) {
      console.warn("Не удалось эскалировать finding аналитика", err);
    }
  };

  const handleMarkResolved = async (id) => {
    try {
      await api.markFindingResolved(id);
      setAnalystFindings((prev) => prev.map((finding) => (
        finding.id === id ? { ...finding, resolved: true } : finding
      )));
    } catch (err) {
      console.warn("Не удалось отметить finding как решённый", err);
    }
  };

  const status = health?.status || (firstLoaded ? "offline" : "loading");
  const auditHealth = audit?.health || null;
  const auditRows = audit?.benchmark?.benchmark || [];
  const lowConfidence = typeof auditHealth?.avg_confidence === "number" && auditHealth.avg_confidence < 0.7;
  const telegramReady = !!telegram?.connected && !!telegram?.bot_username;

  return (
    <section
      className="glass-card rounded-2xl window-border glow-turquoise-subtle p-4 space-y-3"
      data-testid="ops-hermes"
    >
      <BackBar title="hermes · agent" onBack={onBack} />

      <div
        className="flex items-center justify-between border border-white/5 rounded-xl bg-brand-dark/40 px-3 py-2 gap-3 flex-wrap"
        data-testid="hermes-toolbar"
      >
        <div className="flex items-center gap-2">
          <StatusDot status={status} />
          <span className="text-[11px] text-slate-200 uppercase tracking-widest" data-testid="hermes-status-text">
            {status}
          </span>
          <span className="text-[9px] text-slate-500" data-testid="hermes-base-url">
            {health?.base_url || "—"}
          </span>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            onClick={runAudit}
            disabled={auditLoading}
            className="neo-btn rounded-full px-3 py-1.5 text-emerald-300 text-[10px] uppercase tracking-widest flex items-center gap-1.5 disabled:opacity-40"
            data-testid="hermes-run-audit-button"
          >
            {auditLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Bot className="w-3 h-3" />}
            {auditLoading ? "Scanning agents..." : "Run Audit"}
          </button>
          <button
            type="button"
            onClick={refresh}
            className="neo-btn rounded-full px-3 py-1.5 text-purple-400 text-[10px] uppercase tracking-widest flex items-center gap-1.5"
            data-testid="hermes-refresh"
          >
            <RefreshCw className="w-3 h-3" />
            {t("ui.refresh")}
          </button>
        </div>
      </div>

      {status === "offline" && firstLoaded && (
        <div className="text-[11px] text-yellow-300 border border-yellow-500/30 bg-yellow-500/5 rounded-xl p-3">
          {t("ops.hermes.unreachable")}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.9fr)] gap-4 items-start">
        <div className="space-y-3" data-testid="hermes-audit-card">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <SectionHeader
              title="self-audit · operator console"
              right={auditRows.length ? `${auditRows.length} routed agents` : "manual trigger"}
            />
            <button
              type="button"
              onClick={openTelegram}
              disabled={!telegramReady}
              title={telegramReady ? "Открыть чат Hermes в Telegram" : "Подключите Telegram, чтобы открыть чат"}
              className="neo-btn rounded-full px-3 py-1.5 text-sky-300 text-[10px] uppercase tracking-widest flex items-center gap-1.5 disabled:opacity-40"
              data-testid="hermes-view-telegram-button"
            >
              <ArrowUpRight className="w-3 h-3" />
              View in Telegram
            </button>
          </div>

          {auditError ? (
            <div
              className="rounded-xl border border-rose-400/30 bg-rose-500/10 px-3 py-3 text-[11px] text-rose-200"
              data-testid="hermes-audit-error"
            >
              {auditError}
            </div>
          ) : null}

          {!audit ? (
            <div
              className="rounded-2xl border border-dashed border-white/10 bg-brand-dark/30 px-4 py-5 text-[12px] text-white/55 leading-relaxed"
              data-testid="hermes-audit-empty"
            >
              Нажмите <span className="text-white">Run Audit</span>, чтобы получить health-report по tenant и sandbox benchmark по routed агентам. Telegram-кнопка останется read-only на этом этапе.
            </div>
          ) : (
            <div className="space-y-4" data-testid="hermes-audit-results">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <AuditMetricCard
                  label="avg confidence"
                  value={formatConfidence(auditHealth?.avg_confidence)}
                  hint={`scanned · ${auditHealth?.scanned ?? 0} · contradictions · ${auditHealth?.contradiction_count ?? 0}`}
                  danger={lowConfidence}
                  testId="hermes-audit-health-confidence"
                />
                <AuditMetricCard
                  label="avg latency"
                  value={formatLatency(auditHealth?.avg_latency_ms)}
                  hint={`escalation rate · ${formatConfidence(auditHealth?.escalation_rate)} · mock rate · ${formatConfidence(auditHealth?.mock_rate)}`}
                  danger={false}
                  testId="hermes-audit-health-latency"
                />
              </div>

              <div
                className="rounded-2xl border border-white/8 bg-brand-dark/35 p-4 space-y-3"
                data-testid="hermes-audit-benchmark-panel"
              >
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <div>
                    <div className="text-[10px] uppercase tracking-[0.24em] text-white/45" data-testid="hermes-audit-benchmark-title">
                      benchmark
                    </div>
                    <div className="mt-1 text-sm text-white/80" data-testid="hermes-audit-benchmark-summary">
                      passed · {audit?.benchmark?.passed ?? 0} / {audit?.benchmark?.total_personas ?? auditRows.length}
                    </div>
                  </div>
                  <div className="text-[11px] text-white/45" data-testid="hermes-audit-message">
                    {audit?.message || "Self-audit completed"}
                  </div>
                </div>

                <div className="space-y-2" data-testid="hermes-audit-benchmark-list">
                  {auditRows.map((row) => (
                    <AuditBenchmarkRow key={row.persona} row={row} />
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        <div
          className="rounded-2xl border border-white/8 bg-brand-dark/35 p-4 space-y-3"
          data-testid="analyst-findings-card"
        >
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <SectionHeader title="🔍 Аналитик: Самодиагностика" right={`${analystFindings.length} findings`} />
          </div>

          {analystFindings.length === 0 ? (
            <p className="text-[12px] text-white/55" data-testid="analyst-findings-empty">
              <small>Нет активных находок</small>
            </p>
          ) : (
            <ul className="space-y-2 findings-list" data-testid="analyst-findings-list">
              {analystFindings.slice(0, 5).map((f) => (
                <li key={f.id} className="space-y-2 list-none" data-testid={`analyst-finding-wrapper-${f.id}`}>
                  <AnalystFindingRow finding={f} />
                  {!f.resolved ? (
                    <div className="flex gap-2 mt-2 text-[9px]" data-testid={`analyst-finding-actions-${f.id}`}>
                      <button
                        onClick={() => handleEscalate(f.id)}
                        className="text-orange-400 hover:text-orange-300 underline"
                        data-testid={`escalate-finding-${f.id}`}
                      >
                        ➔ Эскалировать Гермесу
                      </button>
                      <button
                        onClick={() => handleMarkResolved(f.id)}
                        className="text-slate-400 hover:text-slate-300 underline"
                        data-testid={`resolve-finding-${f.id}`}
                      >
                        ✓ Отметить как решённое
                      </button>
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="flex justify-between items-center">
        <SectionHeader
          title={t("ops.hermes.scheduled")}
          right={t("ops.hermes.jobs_count", { n: jobs.length })}
        />
        <CreateJobForm onCreated={refresh} />
      </div>

      <div className="space-y-2">
        {jobs.length === 0 && (
          <EmptyHint testId="hermes-empty">
            {t("ops.hermes.empty")}
          </EmptyHint>
        )}
        {jobs.map((j, i) => (
          <JobRow key={j.job_id || j.id || `job-${i}`} job={j} />
        ))}
      </div>

      <div className="text-[10px] text-slate-500 leading-relaxed border-t border-white/5 pt-2">
        <Bot className="w-3 h-3 inline mr-1" />
        {t("ops.hermes.footer")}
      </div>
    </section>
  );
}
