import React, { useCallback, useEffect, useState } from "react";
import { Send, RefreshCw, Plus, Bot } from "lucide-react";
import api from "../../../lib/api";
import { BackBar, SectionHeader, EmptyHint } from "./widgets";

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
          `Hermes недоступен (${res.status_code || "—"}): ${
            res.error || "проверьте, что hermes gateway запущен на :8642"
          }`
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
  const [health, setHealth] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [firstLoaded, setFirstLoaded] = useState(false);

  const refresh = useCallback(async () => {
    const [h, j] = await Promise.all([
      api.hermesHealth().catch(() => null),
      api.hermesJobsList().catch(() => ({ jobs: [] })),
    ]);
    setHealth(h);
    setJobs(j.jobs || []);
    setFirstLoaded(true);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const runRefresh = async () => {
    if (loading) return;
    setLoading(true);
    try {
      await refresh();
    } finally {
      setLoading(false);
    }
  };

  const status = health?.status || (firstLoaded ? "offline" : "loading");

  return (
    <section
      className="glass-card rounded-2xl window-border glow-turquoise-subtle p-4 space-y-3"
      data-testid="ops-hermes"
    >
      <BackBar title="hermes · agent" onBack={onBack} />

      <div className="flex items-center justify-between border border-white/5 rounded-xl bg-brand-dark/40 px-3 py-2">
        <div className="flex items-center gap-2">
          <StatusDot status={status} />
          <span className="text-[11px] text-slate-200 uppercase tracking-widest">
            {status}
          </span>
          <span className="text-[9px] text-slate-500" data-testid="hermes-base-url">
            {health?.base_url || "—"}
          </span>
        </div>
        <button
          onClick={runRefresh}
          disabled={loading}
          className="neo-btn rounded-full px-3 py-1.5 text-purple-400 text-[10px] uppercase tracking-widest flex items-center gap-1.5 disabled:opacity-40"
          data-testid="hermes-refresh"
        >
          <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
          refresh
        </button>
      </div>

      {status === "offline" && firstLoaded && (
        <div className="text-[11px] text-yellow-300 border border-yellow-500/30 bg-yellow-500/5 rounded-xl p-3">
          Hermes API недоступен. Запустите{" "}
          <code className="bg-brand-dark/60 px-1.5 py-0.5 rounded text-[10px]">
            hermes gateway
          </code>{" "}
          с{" "}
          <code className="bg-brand-dark/60 px-1.5 py-0.5 rounded text-[10px]">
            API_SERVER_ENABLED=true
          </code>{" "}
          на порту 8642.
        </div>
      )}

      <div className="flex justify-between items-center">
        <SectionHeader
          title="scheduled jobs"
          right={`${jobs.length} jobs`}
        />
        <CreateJobForm onCreated={refresh} />
      </div>

      <div className="space-y-2">
        {jobs.length === 0 && (
          <EmptyHint testId="hermes-empty">
            нет фоновых заданий — создайте первое
          </EmptyHint>
        )}
        {jobs.map((j, i) => (
          <JobRow key={j.job_id || j.id || `job-${i}`} job={j} />
        ))}
      </div>

      <div className="text-[10px] text-slate-500 leading-relaxed border-t border-white/5 pt-2">
        <Bot className="w-3 h-3 inline mr-1" />
        Hermes Agent (NousResearch) — самообучающийся CLI-агент с tool calling.
        В NXT8 используется как доп. исполнитель фоновых заданий через
        OpenAI-совместимое API.
      </div>
    </section>
  );
}
