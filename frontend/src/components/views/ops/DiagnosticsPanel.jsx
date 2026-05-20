import React, { useCallback, useEffect, useState } from "react";
import { RefreshCw, AlertTriangle } from "lucide-react";
import api from "../../../lib/api";
import { BackBar, SectionHeader, Metric, EmptyHint } from "./widgets";

function ContradictionCard({ c }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <button
      onClick={() => setExpanded((v) => !v)}
      className="w-full text-left border border-red-500/30 bg-red-500/5 rounded-xl p-3 hover:border-red-500/60 transition-colors"
      data-testid={`diag-contra-${c.id || c.a_id}`}
    >
      <div className="flex justify-between items-center mb-1">
        <span className="text-[9px] uppercase tracking-widest text-red-400 flex items-center gap-1">
          <AlertTriangle className="w-3 h-3" /> {c.intent || "general"}
        </span>
        <span className="text-[10px] text-orange-400 font-bold">
          divergence {c.divergence}
        </span>
      </div>
      <div className="text-[11px] text-slate-300 truncate">
        A: {c.a_message}
      </div>
      <div className="text-[11px] text-slate-300 truncate">
        B: {c.b_message}
      </div>
      {expanded && (
        <div className="mt-2 pt-2 border-t border-white/5 space-y-2 text-[11px]">
          <div>
            <div className="text-[9px] text-slate-500 uppercase">resp A</div>
            <div className="text-slate-300">{c.a_response}</div>
          </div>
          <div>
            <div className="text-[9px] text-slate-500 uppercase">resp B</div>
            <div className="text-slate-300">{c.b_response}</div>
          </div>
          <div className="text-[9px] text-slate-500">
            msg sim {c.message_similarity} · resp sim {c.response_similarity}
          </div>
        </div>
      )}
    </button>
  );
}

export default function DiagnosticsPanel({ onBack }) {
  const [summary, setSummary] = useState(null);
  const [contradictions, setContradictions] = useState([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    const [s, c] = await Promise.all([
      api.diagnosticsSummary(200).catch(() => null),
      api.diagnosticsList(30).catch(() => ({ contradictions: [] })),
    ]);
    setSummary(s);
    setContradictions(c.contradictions || []);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const runScan = async () => {
    if (loading) return;
    setLoading(true);
    try {
      await api.diagnosticsScan();
      await refresh();
    } finally {
      setLoading(false);
    }
  };

  const pct = (n) => (n == null ? "—" : `${(n * 100).toFixed(1)}%`);

  return (
    <section
      className="glass-card rounded-2xl window-border glow-turquoise-subtle p-4 space-y-3"
      data-testid="ops-diagnostics"
    >
      <BackBar title="diagnostics · self-audit" onBack={onBack} />

      <div className="grid grid-cols-2 gap-2">
        <Metric
          label="avg confidence"
          value={pct(summary?.avg_confidence)}
          accent="text-brand-turquoise"
          testId="diag-avg-conf"
        />
        <Metric
          label="escalation rate"
          value={pct(summary?.escalation_rate)}
          accent="text-orange-400"
          testId="diag-escalation"
        />
        <Metric
          label="mock rate"
          value={pct(summary?.mock_rate)}
          accent="text-yellow-400"
          testId="diag-mock"
        />
        <Metric
          label="scanned"
          value={summary?.scanned ?? "—"}
          accent="text-slate-300"
          testId="diag-scanned"
        />
      </div>

      {summary?.noisy_intents?.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-[10px] uppercase tracking-widest text-slate-500">
            noisy intents
          </div>
          {summary.noisy_intents.map((n) => (
            <div
              key={n.intent}
              className="flex justify-between items-center bg-brand-dark/40 border border-white/5 rounded-lg px-3 py-1.5"
            >
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-slate-200">{n.intent}</span>
                <span className="text-[9px] text-slate-500">
                  {n.count} req · {n.escalations} esc
                </span>
              </div>
              <div className="text-[10px] text-orange-400">
                noise {n.score}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="flex justify-between items-center">
        <SectionHeader
          title="contradictions"
          right={`${contradictions.length} found`}
        />
        <button
          onClick={runScan}
          disabled={loading}
          className="neo-btn rounded-full px-3 py-1.5 text-brand-turquoise text-[10px] uppercase tracking-widest flex items-center gap-1.5 disabled:opacity-40"
          data-testid="diag-scan"
        >
          <RefreshCw
            className={`w-3 h-3 ${loading ? "animate-spin" : ""}`}
          />
          {loading ? "scanning…" : "rescan"}
        </button>
      </div>

      <div className="space-y-2">
        {contradictions.length === 0 && (
          <EmptyHint testId="diag-empty">
            противоречий не обнаружено
          </EmptyHint>
        )}
        {contradictions.map((c, i) => (
          <ContradictionCard key={c.id || i} c={c} />
        ))}
      </div>
    </section>
  );
}
