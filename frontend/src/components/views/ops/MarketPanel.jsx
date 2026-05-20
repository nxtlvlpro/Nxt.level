import React, { useCallback, useEffect, useState } from "react";
import { Send, Radar, Plus } from "lucide-react";
import api from "../../../lib/api";
import { BackBar, SectionHeader, EmptyHint } from "./widgets";

const CATEGORIES = [
  "competitor",
  "pricing",
  "regulation",
  "tech",
  "macro",
  "customer",
];

const CAT_STYLE = {
  competitor: { text: "text-red-400", box: "border-red-500/40 bg-red-500/5" },
  pricing: { text: "text-orange-400", box: "border-orange-500/40 bg-orange-500/5" },
  regulation: { text: "text-yellow-400", box: "border-yellow-500/40 bg-yellow-500/5" },
  tech: {
    text: "text-brand-turquoise",
    box: "border-brand-turquoise/40 bg-brand-turquoise/5",
  },
  macro: { text: "text-purple-400", box: "border-purple-500/40 bg-purple-500/5" },
  customer: { text: "text-emerald-400", box: "border-emerald-500/40 bg-emerald-500/5" },
};

function SignalRow({ s }) {
  const style = CAT_STYLE[s.category] || CAT_STYLE.tech;
  return (
    <div
      className={`border ${style.box} rounded-xl p-3`}
      data-testid={`market-signal-${s.id}`}
    >
      <div className="flex justify-between items-center mb-1">
        <span
          className={`text-[9px] uppercase tracking-widest ${style.text}`}
        >
          {s.category} · {s.source}
        </span>
        <span className="text-[9px] text-slate-600">
          {new Date(s.ingested_at).toLocaleString("ru-RU", {
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      </div>
      <div className="text-[12px] text-slate-200 break-words">{s.headline}</div>
      <div className="mt-1 flex items-center gap-2">
        <div className="h-1 bg-white/5 rounded-full overflow-hidden flex-1">
          <div
            className="h-full bg-gradient-to-r from-brand-turquoise to-orange-400"
            style={{ width: `${(s.score || 0) * 100}%` }}
          />
        </div>
        <span className="text-[9px] text-slate-500">
          impact {Math.round((s.score || 0) * 100)}
        </span>
      </div>
    </div>
  );
}

function IngestForm({ onIngested }) {
  const [open, setOpen] = useState(false);
  const [headline, setHeadline] = useState("");
  const [category, setCategory] = useState("tech");
  const [source, setSource] = useState("");
  const [score, setScore] = useState(0.6);
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    if (!headline.trim() || submitting) return;
    setSubmitting(true);
    try {
      await api.marketIngest({
        headline: headline.trim(),
        category,
        source: source.trim() || "manual",
        score,
      });
      setHeadline("");
      setSource("");
      setOpen(false);
      onIngested?.();
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="neo-btn rounded-full px-3 py-1.5 text-brand-turquoise text-[10px] uppercase tracking-widest flex items-center gap-1.5"
        data-testid="market-ingest-open"
      >
        <Plus className="w-3 h-3" /> add signal
      </button>
    );
  }

  return (
    <div
      className="border border-brand-turquoise/30 bg-brand-turquoise/5 rounded-xl p-3 space-y-2"
      data-testid="market-ingest-form"
    >
      <input
        value={headline}
        onChange={(e) => setHeadline(e.target.value)}
        placeholder="headline (например: «Конкурент X запустил free-tier»)"
        className="w-full bg-brand-dark/60 border border-white/10 rounded-lg px-3 py-2 text-[12px] outline-none focus:border-brand-turquoise/50"
        data-testid="market-headline"
      />
      <div className="flex gap-2">
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="flex-1 bg-brand-dark/60 border border-white/10 rounded-lg px-2 py-2 text-[11px] outline-none"
          data-testid="market-category"
        >
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <input
          value={source}
          onChange={(e) => setSource(e.target.value)}
          placeholder="source"
          className="flex-1 bg-brand-dark/60 border border-white/10 rounded-lg px-3 py-2 text-[11px] outline-none focus:border-brand-turquoise/50"
        />
      </div>
      <div className="flex items-center gap-3">
        <label className="text-[10px] uppercase tracking-widest text-slate-500">
          impact {Math.round(score * 100)}
        </label>
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={score}
          onChange={(e) => setScore(parseFloat(e.target.value))}
          className="flex-1 accent-cyan-400"
        />
      </div>
      <div className="flex justify-end gap-2">
        <button
          onClick={() => setOpen(false)}
          className="text-slate-500 text-[10px] uppercase tracking-widest px-2"
        >
          cancel
        </button>
        <button
          onClick={submit}
          disabled={submitting || !headline.trim()}
          className="neo-btn rounded-full px-3 py-1.5 text-brand-turquoise text-[10px] uppercase tracking-widest flex items-center gap-1.5 disabled:opacity-40"
          data-testid="market-ingest-submit"
        >
          <Send className="w-3 h-3" /> ingest
        </button>
      </div>
    </div>
  );
}

export default function MarketPanel({ onBack }) {
  const [signals, setSignals] = useState([]);
  const [digests, setDigests] = useState([]);
  const [scanning, setScanning] = useState(false);
  const [latestDigest, setLatestDigest] = useState(null);

  const refresh = useCallback(async () => {
    const [s, d] = await Promise.all([
      api.marketSignals(undefined, 50).catch(() => ({ signals: [] })),
      api.marketDigests(5).catch(() => ({ digests: [] })),
    ]);
    setSignals(s.signals || []);
    setDigests(d.digests || []);
    if ((d.digests || []).length > 0) setLatestDigest(d.digests[0]);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const runScan = async () => {
    if (scanning) return;
    setScanning(true);
    try {
      const res = await api.marketScan(24);
      if (res && res.digest) setLatestDigest(res);
      await refresh();
    } finally {
      setScanning(false);
    }
  };

  return (
    <section
      className="glass-card rounded-2xl window-border glow-turquoise-subtle p-4 space-y-3"
      data-testid="ops-market"
    >
      <BackBar title="market · radar" onBack={onBack} />

      <div className="flex justify-between items-center gap-2">
        <IngestForm onIngested={refresh} />
        <button
          onClick={runScan}
          disabled={scanning}
          className="neo-btn rounded-full px-3 py-1.5 text-brand-turquoise text-[10px] uppercase tracking-widest flex items-center gap-1.5 disabled:opacity-40"
          data-testid="market-scan"
        >
          <Radar className={`w-3 h-3 ${scanning ? "animate-spin" : ""}`} />
          {scanning ? "scanning…" : "scan 24h"}
        </button>
      </div>

      {latestDigest && latestDigest.digest && (
        <div className="border border-brand-turquoise/30 bg-brand-turquoise/5 rounded-xl p-3 space-y-1">
          <div className="text-[10px] uppercase tracking-widest text-brand-turquoise">
            latest digest · {latestDigest.signals_count} signals
          </div>
          <div className="text-[12px] text-slate-200 whitespace-pre-wrap">
            {latestDigest.digest}
          </div>
          <div className="text-[9px] text-slate-500">
            {new Date(latestDigest.created_at).toLocaleString("ru-RU")} ·{" "}
            {latestDigest.provider || "—"}
          </div>
        </div>
      )}

      <SectionHeader
        title="signals"
        right={`${signals.length} ingested`}
      />
      <div className="space-y-2">
        {signals.length === 0 && (
          <EmptyHint testId="market-empty">
            нет сигналов — добавьте первый или дождитесь авто-фида
          </EmptyHint>
        )}
        {signals.map((s) => (
          <SignalRow key={s.id} s={s} />
        ))}
      </div>

      {digests.length > 1 && (
        <>
          <SectionHeader title="digest history" />
          <div className="space-y-2">
            {digests.slice(1).map((d) => (
              <div
                key={d.id}
                className="border border-white/5 bg-brand-dark/40 rounded-xl p-2.5 text-[11px]"
              >
                <div className="text-[9px] uppercase text-slate-500">
                  {new Date(d.created_at).toLocaleString("ru-RU")} ·{" "}
                  {d.signals_count} signals
                </div>
                <div className="text-slate-300 mt-1 line-clamp-3">
                  {d.digest}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
