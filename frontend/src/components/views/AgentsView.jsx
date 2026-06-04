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
  ArrowRight,
  AlertTriangle,
  MessageCircle,
  ShieldCheck,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import CollapsibleCard from "../CollapsibleCard";
import api from "../../lib/api";
import { useT } from "../../i18n/LanguageContext";
import TelegramConnectCard from "./TelegramConnectCard";

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
  const { t, lang } = useT();
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: t("agents.welcome", { name: persona.name, role: persona.role }),
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
        language: lang,
      });
      if (status === 402) {
        setError(t("agents.plan_required", { plan: data.required_plan }));
      } else if (data.success) {
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            content: data.content || t("agents.empty_reply"),
            tool_traces: data.tool_traces || [],
            confidence: data.confidence,
            iterations: data.iterations,
            provider: data.provider,
            mock: data.mock,
          },
        ]);
      } else {
        setError(data.error || t("agents.error"));
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
              {t("agents.typing", { name: persona.name })}
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
            placeholder={t("agents.ask_placeholder", { name: persona.name })}
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
  const { t } = useT();
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
        title={t("agents.team.title")}
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
                    t("agents.locked", { name: pp.name, minPlan: pp.min_plan, plan })
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
          {t("agents.footer")}
        </div>
      </CollapsibleCard>

      {active && (
        <PersonaChatModal
          persona={active}
          plan={plan}
          onClose={() => setActive(null)}
        />
      )}

      <PendingApprovalsCard />

      <TelegramConnectCard />

      <InterAgentDialoguesCard />
    </div>
  );
}

// ============================================================
// Inter-Agent Dialogues — visualise CEO ↔ team conversations
// ============================================================

const KIND_BADGE = {
  delegate: { icon: ArrowRight, label: "DELEGATE", cls: "bg-cyan-500/15 ring-cyan-400/30 text-cyan-200" },
  escalate: { icon: AlertTriangle, label: "ESCALATE", cls: "bg-amber-500/15 ring-amber-400/30 text-amber-200" },
  ask:      { icon: MessageCircle, label: "ASK",      cls: "bg-violet-500/15 ring-violet-400/30 text-violet-200" },
};

function DialogueRow({ d, onOpen }) {
  const meta = KIND_BADGE[d.kind] || KIND_BADGE.ask;
  const Icon = meta.icon;
  return (
    <button
      type="button"
      data-testid={`dialogue-row-${d.id}`}
      onClick={() => onOpen(d)}
      className="w-full text-left grid grid-cols-[auto,auto,1fr,auto] items-center gap-3 px-3 py-2 rounded-lg bg-white/[0.02] ring-1 ring-white/5 hover:bg-white/[0.05] transition"
    >
      <span className={`inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded-full ring-1 ${meta.cls}`}>
        <Icon className="w-3 h-3" /> {meta.label}
      </span>
      <span className="text-[11px] font-mono text-white/70 whitespace-nowrap">
        {d.from_agent} → {d.to_agent}
      </span>
      <span className="text-xs text-white/80 truncate">{d.topic}</span>
      <span className="text-[10px] font-mono text-white/30 whitespace-nowrap">
        {d.created_at ? new Date(d.created_at).toLocaleTimeString() : ""}
      </span>
    </button>
  );
}

function DialogueModal({ d, onClose }) {
  if (!d) return null;
  const meta = KIND_BADGE[d.kind] || KIND_BADGE.ask;
  const Icon = meta.icon;
  return (
    <div
      className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
      data-testid="dialogue-modal"
      onClick={onClose}
    >
      <div
        className="w-full max-w-3xl bg-zinc-950 ring-1 ring-white/10 rounded-2xl flex flex-col max-h-[85vh]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="shrink-0 p-4 border-b border-white/10 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className={`inline-flex items-center gap-1 text-[11px] font-mono px-2 py-1 rounded-full ring-1 ${meta.cls}`}>
              <Icon className="w-3 h-3" /> {meta.label}
            </span>
            <div className="font-mono text-sm text-white/80">
              {d.from_agent} <span className="text-white/30">→</span> {d.to_agent}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            data-testid="dialogue-modal-close"
            className="text-white/50 hover:text-white"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          <div>
            <div className="text-[10px] font-mono uppercase tracking-wider text-white/40 mb-1">Тема</div>
            <div className="text-sm text-white/85">{d.topic}</div>
          </div>
          <div>
            <div className="text-[10px] font-mono uppercase tracking-wider text-white/40 mb-1">Запрос</div>
            <pre className="text-xs text-white/70 whitespace-pre-wrap font-sans bg-white/[0.03] ring-1 ring-white/5 rounded-lg p-3">{d.request}</pre>
          </div>
          <div>
            <div className="text-[10px] font-mono uppercase tracking-wider text-white/40 mb-1">Ответ</div>
            <pre className="text-xs text-white/80 whitespace-pre-wrap font-sans bg-white/[0.03] ring-1 ring-white/5 rounded-lg p-3">{d.response}</pre>
          </div>
          {(d.urgency || d.confidence) && (
            <div className="flex gap-4 text-[10px] font-mono text-white/40">
              {d.urgency && <span>URGENCY: {d.urgency}</span>}
              {d.confidence != null && <span>CONFIDENCE: {Number(d.confidence).toFixed(2)}</span>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function InterAgentDialoguesCard() {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const cardRef = React.useRef(null);

  // Demo Tour — mark "open_dialogues" complete when the card scrolls into view
  useEffect(() => {
    if (typeof window === "undefined" || !cardRef.current) return undefined;
    const obs = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            try {
              window.dispatchEvent(new CustomEvent("nxt8:tour-complete", {
                detail: { step_id: "open_dialogues" },
              }));
            } catch { /* ignore */ }
            obs.disconnect();
            break;
          }
        }
      },
      { threshold: 0.3 }
    );
    obs.observe(cardRef.current);
    return () => obs.disconnect();
  }, []);

  const refresh = () => {
    setLoading(true);
    api
      .agentDialogues(30)
      .then((d) => setItems(d.items || []))
      .catch((e) => setErr(e?.message || String(e)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 15000);
    return () => clearInterval(id);
  }, []);

  return (
    <div ref={cardRef}>
      <CollapsibleCard
        storageKey="agents-dialogues"
        testId="agents-dialogues-card"
        title="Связь команды (CEO ↔ агенты)"
        titleRight={
          <span className="text-[10px] font-mono text-white/40">
            {items.length} событий
          </span>
        }
      >
        <div className="text-[11px] font-mono text-white/40 mb-3 leading-relaxed">
          Реальные межагентные вызовы: Hermes как CEO делегирует
          подчинённым (DELEGATE), агенты эскалируют ему критичное
          (ESCALATE), коллеги советуются между собой (ASK).
        </div>

        {err && (
          <div className="text-xs text-rose-300 bg-rose-500/10 ring-1 ring-rose-400/30 rounded-lg p-3 font-mono mb-3" data-testid="dialogues-error">
            {err}
          </div>
        )}

        {loading && !items.length && (
          <div className="flex items-center gap-2 text-xs text-white/40 font-mono">
            <Loader2 className="w-3 h-3 animate-spin" /> загрузка…
          </div>
        )}

        {!loading && !items.length && (
          <div className="text-xs text-white/40 font-mono italic" data-testid="dialogues-empty">
            Пока пусто — задайте Hermes-у вопрос вне его прямой зоны
            (финансы, HR, право), и он делегирует профильному агенту.
          </div>
        )}

        <div className="space-y-1.5" data-testid="dialogues-list">
          {items.map((d) => (
            <DialogueRow key={d.id} d={d} onOpen={setOpen} />
          ))}
        </div>
      </CollapsibleCard>

      <DialogueModal d={open} onClose={() => setOpen(null)} />
    </div>
  );
}


// ============================================================
// Pending Approvals — каждое high-impact решение агентов
// проходит проверку перед внедрением.
// ============================================================

const ACTION_LABEL = {
  create_task: "Создать задачу",
  update_task: "Обновить задачу",
  delegate_to: "Делегировать",
  create_cross_department_bridge: "Кросс-департ. бридж",
  mempalace_store: "Запись в Memory Palace",
};

const ACTION_TONE = {
  create_task: "text-emerald-200 bg-emerald-500/10 ring-emerald-400/30",
  update_task: "text-cyan-200 bg-cyan-500/10 ring-cyan-400/30",
  delegate_to: "text-violet-200 bg-violet-500/10 ring-violet-400/30",
  create_cross_department_bridge: "text-amber-200 bg-amber-500/10 ring-amber-400/30",
  mempalace_store: "text-fuchsia-200 bg-fuchsia-500/10 ring-fuchsia-400/30",
};

function ApprovalRow({ item, onApprove, onReject, busy }) {
  const actionTone = ACTION_TONE[item.action] || "text-white/70 bg-white/5 ring-white/10";
  const actionLabel = ACTION_LABEL[item.action] || item.action;
  const title = item.args?.title || item.args?.task_id || item.args?.target_agent_id || "—";
  const priority = item.args?.priority;
  return (
    <div
      data-testid={`approval-row-${item.id}`}
      className="grid grid-cols-[auto,1fr,auto] items-start gap-3 px-3 py-2.5 rounded-lg bg-white/[0.02] ring-1 ring-white/5 hover:bg-white/[0.04] transition"
    >
      <span className={`inline-flex items-center gap-1 text-[10px] font-mono px-2 py-1 rounded-full ring-1 whitespace-nowrap ${actionTone}`}>
        <ShieldCheck className="w-3 h-3" /> {actionLabel}
      </span>

      <div className="min-w-0">
        <div className="text-sm text-white/90 truncate" title={title}>
          {title}
        </div>
        <div className="flex items-center gap-2 text-[10px] font-mono text-white/40 mt-0.5">
          <span>от: {item.agent_id}</span>
          {priority && (
            <span className={priority === "critical" || priority === "high"
              ? "text-rose-300"
              : "text-white/40"}>· prio: {priority}</span>
          )}
          {item.created_at && (
            <span>· {new Date(item.created_at).toLocaleTimeString()}</span>
          )}
        </div>
      </div>

      <div className="flex items-center gap-1.5">
        <button
          type="button"
          data-testid={`approval-approve-${item.id}`}
          disabled={busy}
          onClick={() => onApprove(item)}
          className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-1 rounded-md bg-emerald-500/15 ring-1 ring-emerald-400/30 text-emerald-200 hover:bg-emerald-500/25 transition disabled:opacity-40"
        >
          <CheckCircle2 className="w-3 h-3" /> Одобрить
        </button>
        <button
          type="button"
          data-testid={`approval-reject-${item.id}`}
          disabled={busy}
          onClick={() => onReject(item)}
          className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-1 rounded-md bg-rose-500/10 ring-1 ring-rose-400/30 text-rose-200 hover:bg-rose-500/20 transition disabled:opacity-40"
        >
          <XCircle className="w-3 h-3" /> Отклонить
        </button>
      </div>
    </div>
  );
}

function PendingApprovalsCard() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [err, setErr] = useState(null);
  const cardRef = React.useRef(null);

  // Demo Tour — mark "open_approvals" complete on first visibility
  useEffect(() => {
    if (typeof window === "undefined" || !cardRef.current) return undefined;
    const obs = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            try {
              window.dispatchEvent(new CustomEvent("nxt8:tour-complete", {
                detail: { step_id: "open_approvals" },
              }));
            } catch { /* ignore */ }
            obs.disconnect();
            break;
          }
        }
      },
      { threshold: 0.3 }
    );
    obs.observe(cardRef.current);
    return () => obs.disconnect();
  }, []);

  const refresh = () => {
    setLoading(true);
    api
      .approvalsList("pending", undefined, 50)
      .then((d) => setItems(d.items || []))
      .catch((e) => setErr(e?.message || String(e)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 10000);
    return () => clearInterval(id);
  }, []);

  const decide = async (item, mode) => {
    setBusyId(item.id);
    try {
      if (mode === "approve") {
        await api.approvalsApprove(item.id, "owner");
      } else {
        const reason = window.prompt("Причина отклонения (опционально):") || "";
        await api.approvalsReject(item.id, "owner", reason);
      }
      refresh();
    } catch (e) {
      setErr(e?.message || String(e));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div ref={cardRef}>
    <CollapsibleCard
      storageKey="agents-pending-approvals"
      testId="agents-pending-approvals-card"
      title="Approval Gate — на проверке у вас"
      titleRight={
        <span
          data-testid="approvals-count"
          className={`text-[10px] font-mono px-2 py-0.5 rounded-full ring-1 ${
            items.length
              ? "bg-amber-500/15 ring-amber-400/40 text-amber-200"
              : "bg-white/5 ring-white/10 text-white/40"
          }`}
        >
          {items.length}
        </span>
      }
    >
      <div className="text-[11px] font-mono text-white/40 mb-3 leading-relaxed">
        Каждое high-impact решение подчинённых агентов (создание задач,
        обновление статусов, кросс-департаментные мосты) ждёт вашего «ОК»
        прежде чем уйти в продакшн. Hermes и автономные узлы Graph этот
        gate обходят — они отвечают от лица CEO.
      </div>

      {err && (
        <div
          className="text-xs text-rose-300 bg-rose-500/10 ring-1 ring-rose-400/30 rounded-lg p-3 font-mono mb-3"
          data-testid="approvals-error"
        >
          {err}
        </div>
      )}

      {loading && !items.length && (
        <div className="flex items-center gap-2 text-xs text-white/40 font-mono">
          <Loader2 className="w-3 h-3 animate-spin" /> загрузка…
        </div>
      )}

      {!loading && !items.length && !err && (
        <div
          className="text-xs text-white/40 font-mono italic"
          data-testid="approvals-empty"
        >
          На проверке ничего. Команда работает в рамках мандата.
        </div>
      )}

      <div className="space-y-1.5" data-testid="approvals-list">
        {items.map((it) => (
          <ApprovalRow
            key={it.id}
            item={it}
            busy={busyId === it.id}
            onApprove={(i) => decide(i, "approve")}
            onReject={(i) => decide(i, "reject")}
          />
        ))}
      </div>
    </CollapsibleCard>
    </div>
  );
}
