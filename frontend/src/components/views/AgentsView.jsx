import React, { useEffect, useMemo, useState } from "react";
import {
  Crown,
  GraduationCap,
  HeartHandshake,
  Network,
  TrendingUp,
  Calculator,
  Radar,
  Shield,
  Lock,
  Loader2,
  Send,
  X,
} from "lucide-react";
import CollapsibleCard from "../CollapsibleCard";
import api from "../../lib/api";

const ICON_MAP = {
  Crown,
  GraduationCap,
  HeartHandshake,
  Network,
  TrendingUp,
  Calculator,
  Radar,
  Shield,
};

const COLOR_MAP = {
  turquoise: { ring: "ring-cyan-400/40", bg: "bg-cyan-500/10", text: "text-cyan-300" },
  violet: { ring: "ring-violet-400/40", bg: "bg-violet-500/10", text: "text-violet-300" },
  rose: { ring: "ring-rose-400/40", bg: "bg-rose-500/10", text: "text-rose-300" },
  amber: { ring: "ring-amber-400/40", bg: "bg-amber-500/10", text: "text-amber-300" },
  cyan: { ring: "ring-sky-400/40", bg: "bg-sky-500/10", text: "text-sky-300" },
  emerald: { ring: "ring-emerald-400/40", bg: "bg-emerald-500/10", text: "text-emerald-300" },
  orange: { ring: "ring-orange-400/40", bg: "bg-orange-500/10", text: "text-orange-300" },
  slate: { ring: "ring-slate-400/40", bg: "bg-slate-500/10", text: "text-slate-300" },
};

const PLANS_ORDER = ["basic", "simple", "pro", "enterprise"];

function PersonaCard({ persona, onOpen }) {
  const Icon = ICON_MAP[persona.icon] || Crown;
  const palette = COLOR_MAP[persona.color] || COLOR_MAP.turquoise;
  const locked = !persona.available_on_plan;
  return (
    <button
      type="button"
      data-testid={`persona-card-${persona.id}`}
      onClick={() => onOpen(persona)}
      className={`relative text-left rounded-xl glass-card p-4 ring-1 ${
        locked ? "ring-white/5 opacity-60 cursor-help" : palette.ring
      } hover:scale-[1.01] transition-transform`}
    >
      <div className="flex items-start gap-3">
        <div
          className={`shrink-0 w-10 h-10 rounded-lg flex items-center justify-center ${palette.bg}`}
        >
          <Icon className={`w-5 h-5 ${palette.text}`} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <div className="text-sm font-mono uppercase tracking-wider text-white/90">
              {persona.name}
            </div>
            {locked && (
              <span
                className="text-[10px] font-mono uppercase text-amber-300/90 inline-flex items-center gap-1"
                data-testid={`persona-locked-${persona.id}`}
              >
                <Lock className="w-3 h-3" /> {persona.min_plan}
              </span>
            )}
          </div>
          <div className="text-[11px] text-white/50 mt-0.5 font-mono">{persona.role}</div>
          <div className="text-xs text-white/70 mt-2 leading-relaxed">
            {persona.description}
          </div>
          <div className="text-[10px] text-white/40 font-mono mt-2">
            tools: {persona.tools_count}
          </div>
        </div>
      </div>
    </button>
  );
}

function PersonaChatModal({ persona, plan, onClose }) {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: `Привет. Я — ${persona.name}. ${persona.role}.\n\nЧто разобрать?`,
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setError(null);
    setMessages((m) => [...m, { role: "user", content: text }]);
    setInput("");
    setBusy(true);
    try {
      const { status, data } = await api.personaChat(persona.id, {
        message: text,
        plan_id: plan,
      });
      if (status === 402) {
        setError(
          `Этот агент доступен только на тарифе "${data.required_plan}" или выше.`
        );
      } else if (data.success) {
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            content: data.content || "(пустой ответ)",
            tool_traces: data.tool_traces || [],
            confidence: data.confidence,
            iterations: data.iterations,
            provider: data.provider,
            mock: data.mock,
          },
        ]);
      } else {
        setError(data.error || "Ошибка");
      }
    } catch (e) {
      setError(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const Icon = ICON_MAP[persona.icon] || Crown;
  const palette = COLOR_MAP[persona.color] || COLOR_MAP.turquoise;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/70 backdrop-blur flex items-center justify-center p-3"
      data-testid="persona-chat-modal"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl max-h-[90vh] bg-slate-950/95 ring-1 ring-white/10 rounded-xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="shrink-0 flex items-center gap-3 p-4 border-b border-white/10">
          <div
            className={`w-9 h-9 rounded-lg flex items-center justify-center ${palette.bg}`}
          >
            <Icon className={`w-5 h-5 ${palette.text}`} />
          </div>
          <div className="flex-1">
            <div className="text-sm font-mono uppercase text-white/90">
              {persona.name}
            </div>
            <div className="text-[11px] text-white/50 font-mono">{persona.role}</div>
          </div>
          <button
            type="button"
            data-testid="persona-chat-close"
            className="text-white/50 hover:text-white p-1"
            onClick={onClose}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div
          className="flex-1 overflow-y-auto p-4 space-y-3"
          data-testid="persona-chat-messages"
        >
          {messages.map((m, idx) => (
            <div
              key={idx}
              className={`text-sm rounded-lg p-3 ${
                m.role === "user"
                  ? "bg-cyan-500/10 ring-1 ring-cyan-400/30 ml-8"
                  : "bg-white/5 ring-1 ring-white/10 mr-8"
              }`}
            >
              <pre className="whitespace-pre-wrap font-sans text-white/90 leading-relaxed">
                {m.content}
              </pre>
              {m.tool_traces && m.tool_traces.length > 0 && (
                <div className="mt-2 pt-2 border-t border-white/10 text-[10px] font-mono text-white/50 space-y-1">
                  {m.tool_traces.map((t, i) => (
                    <div key={i}>
                      → {t.name} {t.result?.ok ? "✓" : "✗"}{" "}
                      {t.result?.task_id ? `(task ${t.result.task_id.slice(0, 8)})` : ""}
                    </div>
                  ))}
                </div>
              )}
              {m.role === "assistant" && m.confidence !== undefined && (
                <div className="mt-1 text-[10px] font-mono text-white/40">
                  conf {(m.confidence * 100).toFixed(0)}% · iter {m.iterations} ·{" "}
                  {m.provider || "?"} {m.mock ? "· mock" : ""}
                </div>
              )}
            </div>
          ))}
          {busy && (
            <div className="text-xs text-white/50 flex items-center gap-2 font-mono">
              <Loader2 className="w-3 h-3 animate-spin" />
              {persona.name} печатает…
            </div>
          )}
          {error && (
            <div
              className="text-xs text-rose-300 bg-rose-500/10 ring-1 ring-rose-400/30 rounded-lg p-3 font-mono"
              data-testid="persona-chat-error"
            >
              {error}
            </div>
          )}
        </div>

        <div className="shrink-0 p-3 border-t border-white/10 flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder={`Спросите ${persona.name}…`}
            disabled={busy}
            data-testid="persona-chat-input"
            className="flex-1 bg-white/5 ring-1 ring-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-white/30 focus:ring-cyan-400/50 outline-none font-mono"
          />
          <button
            type="button"
            disabled={busy || !input.trim()}
            onClick={send}
            data-testid="persona-chat-send"
            className="bg-cyan-500/20 ring-1 ring-cyan-400/40 hover:bg-cyan-500/30 disabled:opacity-40 rounded-lg px-3 py-2 text-cyan-300"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

export default function AgentsView() {
  const [data, setData] = useState(null);
  const [plan, setPlan] = useState("enterprise");
  const [active, setActive] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api
      .personasList(plan)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setErr(e?.message || String(e)));
    return () => {
      cancelled = true;
    };
  }, [plan]);

  const planMeta = data?.plan;
  const personas = data?.personas || [];
  const plans = data?.plans || [];

  return (
    <div className="space-y-4">
      <CollapsibleCard
        storageKey="agents-personas"
        testId="agents-personas-card"
        title="agents.team"
        titleRight={
          <span className="text-[10px] font-mono text-white/40">
            {planMeta ? `${planMeta.name} · $${planMeta.price_usd}/mo` : ""}
          </span>
        }
      >
        <div className="flex flex-wrap gap-2 mb-4" data-testid="plan-selector">
          {PLANS_ORDER.map((pid) => {
            const p = plans.find((x) => x.id === pid);
            if (!p) return null;
            const active = pid === plan;
            return (
              <button
                key={pid}
                type="button"
                data-testid={`plan-pill-${pid}`}
                onClick={() => setPlan(pid)}
                className={`text-[11px] font-mono uppercase tracking-wider px-3 py-1.5 rounded-full ring-1 transition ${
                  active
                    ? "bg-cyan-500/20 ring-cyan-400/50 text-cyan-200"
                    : "bg-white/5 ring-white/10 text-white/60 hover:bg-white/10"
                }`}
              >
                {p.name} · ${p.price_usd}
                <span className="ml-2 opacity-60">
                  {p.personas.length}/{personas.length}
                </span>
              </button>
            );
          })}
        </div>

        {err && (
          <div
            className="text-xs text-rose-300 bg-rose-500/10 ring-1 ring-rose-400/30 rounded-lg p-3 font-mono mb-3"
            data-testid="personas-error"
          >
            {err}
          </div>
        )}

        <div
          className="grid grid-cols-1 md:grid-cols-2 gap-3"
          data-testid="personas-grid"
        >
          {personas.map((p) => (
            <PersonaCard
              key={p.id}
              persona={p}
              onOpen={(pp) => {
                if (!pp.available_on_plan) {
                  setErr(
                    `Агент "${pp.name}" доступен на тарифе "${pp.min_plan}" и выше. Текущий: "${plan}".`
                  );
                  return;
                }
                setErr(null);
                setActive(pp);
              }}
            />
          ))}
        </div>

        <div className="mt-4 text-[10px] font-mono text-white/40">
          Hermes — сердце системы. Остальные персоны опираются на ту же память и инструменты,
          но в фокусированной роли. Тарифные ворота — реальные: API возвращает 402, если
          персона не включена в план.
        </div>
      </CollapsibleCard>

      {active && (
        <PersonaChatModal
          persona={active}
          plan={plan}
          onClose={() => setActive(null)}
        />
      )}
    </div>
  );
}
