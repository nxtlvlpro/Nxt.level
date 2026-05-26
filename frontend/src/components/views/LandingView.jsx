import React, { useEffect, useRef, useState } from "react";
import {
  Send,
  Mic,
  MessageSquare,
  ArrowRight,
  ChevronRight,
  Sparkles,
  Loader2,
  Square,
  Volume2,
} from "lucide-react";
import api from "../../lib/api";

// =============================================================
// Static content (TZ — Russian-first, no AI jargon)
// =============================================================

const HERO_TICKER_ITEMS = [
  "Добро пожаловать в NXT8",
  "AI-координация для современной команды",
  "Работает внутри ваших процессов",
  "Меньше хаоса · Больше координации",
  "Без сложного внедрения",
];

const FEATURES_TICKER_ITEMS = [
  "WhatsApp",
  "Telegram",
  "CRM",
  "Документы",
  "Задачи",
  "Календарь",
  "Email",
  "Всё работает вместе",
];

const PILOT_TICKER_ITEMS = [
  "Подключите первых 10 сотрудников бесплатно",
  "Диагностический пилот — 14 дней",
  "Без долгих контрактов",
  "Без обязательств",
];

const AGENTS = [
  {
    id: "hermes",
    name: "HERMES",
    role: "Главный операционный координатор",
    plan: "Personal — $9 / сотрудник",
    planId: "personal",
    description:
      "Координирует задачи, фиксирует договорённости, помогает команде не терять контекст и связывает процессы компании в единую систему.",
    accent: "text-brand-turquoise",
    glow: "glow-turquoise-subtle",
  },
  {
    id: "hr-mentor",
    name: "HR-MENTOR",
    role: "Развитие сотрудников",
    plan: "Team — $14 / сотрудник",
    planId: "team",
    description:
      "Помогает каждому в команде расти. Замечает паттерны выгорания, подсказывает зоны роста и подбирает индивидуальный план развития.",
    accent: "text-purple-400",
    glow: "glow-turquoise-subtle",
  },
  {
    id: "client-ops",
    name: "CLIENT OPERATIONS",
    role: "Менеджер по клиентам",
    plan: "Team — $14 / сотрудник",
    planId: "team",
    description:
      "Ведёт переписку с клиентами, не теряет сделки в потоке, предлагает шаблоны ответов и фиксирует договорённости в CRM.",
    accent: "text-emerald-400",
    glow: "glow-turquoise-subtle",
  },
  {
    id: "analytics",
    name: "ANALYTICS",
    role: "Аналитик команды",
    plan: "Headquarters — $24 / сотрудник",
    planId: "hq",
    description:
      "Собирает данные из всех источников и показывает, что происходит в компании прямо сейчас. Простые ответы вместо сложных дашбордов.",
    accent: "text-sky-400",
    glow: "glow-turquoise-subtle",
  },
  {
    id: "financial",
    name: "FINANCIAL AGENT",
    role: "Финансовый помощник",
    plan: "Operations — $19 / сотрудник",
    planId: "operations",
    description:
      "Контролирует движение денег, напоминает про платежи и помогает планировать бюджет без таблиц и ручных подсчётов.",
    accent: "text-yellow-300",
    glow: "glow-turquoise-subtle",
  },
  {
    id: "legal",
    name: "LEGAL REVIEW",
    role: "Compliance с разбором документов",
    plan: "Operations — $19 / сотрудник",
    planId: "operations",
    description:
      "Читает договоры, политики и оферты. Подсвечивает рисковые пункты и предлагает, что согласовать перед подписью.",
    accent: "text-orange-400",
    glow: "glow-turquoise-subtle",
  },
  {
    id: "marketing",
    name: "MARKETING OPS",
    role: "Маркетолог",
    plan: "Operations — $19 / сотрудник",
    planId: "operations",
    description:
      "Отслеживает рыночные сигналы и работает с воронкой. Помогает запускать кампании и проверять, что они дают результат.",
    accent: "text-pink-400",
    glow: "glow-turquoise-subtle",
  },
];

const TARIFFS = [
  {
    id: "personal",
    name: "Personal",
    price: "$9",
    period: "/ сотрудник в месяц",
    accent: "text-brand-turquoise",
    border: "border-brand-turquoise/30",
    features: [
      "Hermes — главный координатор",
      "Базовая память компании",
      "Голосовой и текстовый интерфейс",
      "До 1 000 запросов в месяц",
    ],
  },
  {
    id: "team",
    name: "Team",
    price: "$14",
    period: "/ сотрудник в месяц",
    accent: "text-purple-400",
    border: "border-purple-500/30",
    features: [
      "Всё из Personal",
      "HR-Mentor — развитие сотрудников",
      "Client Operations — работа с клиентами",
      "Интеграция WhatsApp / Telegram",
    ],
  },
  {
    id: "operations",
    name: "Operations",
    price: "$19",
    period: "/ сотрудник в месяц",
    accent: "text-emerald-400",
    border: "border-emerald-500/30",
    features: [
      "Всё из Team",
      "Financial Agent — финансы",
      "Legal Review — разбор документов",
      "Marketing Ops — маркетинг",
    ],
    highlight: true,
  },
  {
    id: "hq",
    name: "Headquarters",
    price: "$24",
    period: "/ сотрудник в месяц",
    accent: "text-orange-400",
    border: "border-orange-500/30",
    features: [
      "Всё из Operations",
      "Analytics — аналитик команды",
      "Координатор проектов",
      "Кросс-департаментная координация",
      "Приоритетная поддержка",
    ],
  },
];

const STEPS = [
  {
    n: "01",
    title: "Подключаем источники",
    description:
      "Чаты, документы и рабочие инструменты, которыми пользуется команда каждый день.",
  },
  {
    n: "02",
    title: "Понимание процессов",
    description:
      "NXT8 начинает понимать структуру компании, роли и контекст задач без ручной настройки.",
  },
  {
    n: "03",
    title: "AI-команда в работе",
    description:
      "AI-агенты помогают команде в ежедневных задачах — координация, ответы, контроль, аналитика.",
  },
];

// Placeholder checkout — real Stripe integration deferred per user choice
const CHECKOUT_BASE = "https://nxt8.pro/checkout";

function goToCheckout(planId) {
  const url = `${CHECKOUT_BASE}?plan=${encodeURIComponent(planId)}`;
  if (typeof window !== "undefined") {
    window.open(url, "_blank", "noopener,noreferrer");
  }
}

// =============================================================
// Inline ticker (reusable between sections)
// =============================================================

function InlineTicker({ items, accent = "text-brand-turquoise", testId }) {
  const stream = [...items, ...items, ...items];
  return (
    <div
      className="relative overflow-hidden border-y border-white/5 led-ticker bg-brand-dark/60 backdrop-blur-md py-2"
      data-testid={testId}
    >
      <div className="flex items-center text-[10px] uppercase tracking-widest text-slate-400 overflow-hidden">
        <div className="ticker-track flex items-center space-x-8 whitespace-nowrap">
          {stream.map((it, idx) => (
            <span key={`${it}-${idx}`} className="shrink-0 flex items-center gap-2">
              <span className={`${accent}`}>◇</span>
              <span>{it}</span>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

// =============================================================
// Hero
// =============================================================

function Hero({ onEnter }) {
  return (
    <section
      className="relative px-4 lg:px-12 pt-10 lg:pt-16 pb-8 lg:pb-12"
      data-testid="landing-hero"
    >
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-2.5 h-2.5 rounded-full bg-brand-turquoise shadow-[0_0_12px_var(--brand-turquoise)] animate-pulse" />
            <span className="text-brand-turquoise text-[10px] uppercase tracking-[0.3em]">
              nxt8 · operating system
            </span>
          </div>
          <button
            onClick={onEnter}
            className="text-slate-400 hover:text-brand-turquoise text-[10px] uppercase tracking-widest flex items-center gap-1.5 transition-colors"
            data-testid="landing-skip"
          >
            войти в систему <ArrowRight className="w-3 h-3" />
          </button>
        </div>

        <h1
          className="text-5xl sm:text-6xl lg:text-7xl font-extralight tracking-tight text-slate-100 leading-[0.95] mb-5"
          data-testid="landing-title"
        >
          NXT<span className="text-brand-turquoise">8</span>
        </h1>
        <p className="text-base lg:text-lg text-slate-300 max-w-2xl leading-relaxed mb-3">
          Операционная AI-система для современного бизнеса.
        </p>
        <p className="text-sm lg:text-base text-slate-500 max-w-2xl leading-relaxed">
          Готовая AI-команда, которая работает вместе с вашей компанией.
        </p>

        <div className="mt-10 flex items-center gap-3 text-slate-400 text-[11px] uppercase tracking-widest">
          <span className="inline-block w-12 h-px bg-gradient-to-r from-transparent to-brand-turquoise/60" />
          <span>→ Выберите AI-агентов для вашей команды</span>
        </div>
      </div>
    </section>
  );
}

// =============================================================
// Agents — horizontal scroll
// =============================================================

function AgentCard({ agent }) {
  return (
    <article
      className={`snap-center shrink-0 w-[82vw] sm:w-[420px] glass-card window-border ${agent.glow} rounded-2xl p-5 flex flex-col`}
      data-testid={`landing-agent-${agent.id}`}
    >
      <div className="flex-1">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h3
              className={`${agent.accent} font-light text-sm tracking-widest uppercase`}
            >
              {agent.name}
            </h3>
            <div className="text-slate-200 text-[13px] mt-1.5">
              {agent.role}
            </div>
          </div>
          <span className="text-[9px] uppercase tracking-widest text-slate-500 border border-white/10 rounded-full px-2 py-1">
            agent
          </span>
        </div>
        <div className="text-[10px] uppercase tracking-widest text-slate-500 border-t border-white/5 pt-3 mb-3">
          {agent.plan}
        </div>
        <p className="text-[13px] text-slate-300 leading-relaxed">
          {agent.description}
        </p>
      </div>

      <button
        type="button"
        onClick={() => goToCheckout(agent.planId)}
        className="mt-5 neo-btn rounded-full px-4 py-2.5 text-brand-turquoise text-[11px] uppercase tracking-widest flex items-center justify-center gap-2 hover:bg-brand-turquoise/10 transition-colors"
        data-testid={`landing-agent-cta-${agent.id}`}
      >
        Подключить <ChevronRight className="w-3.5 h-3.5" />
      </button>
    </article>
  );
}

function AgentsSwipe() {
  const trackRef = useRef(null);
  const scroll = (dir) => {
    const el = trackRef.current;
    if (!el) return;
    const card = el.querySelector("[data-testid^='landing-agent-']");
    const step = card ? card.clientWidth + 16 : 360;
    el.scrollBy({ left: dir * step, behavior: "smooth" });
  };
  return (
    <section
      className="relative px-4 lg:px-12 py-8"
      data-testid="landing-agents"
    >
      <div className="max-w-5xl mx-auto">
        <div className="flex items-end justify-between mb-5">
          <div>
            <div className="text-[10px] uppercase tracking-[0.3em] text-brand-turquoise mb-2">
              ai team · 7 ролей
            </div>
            <h2 className="text-2xl lg:text-3xl font-light text-slate-100">
              AI-агенты для каждой задачи
            </h2>
          </div>
          <div className="hidden sm:flex items-center gap-2">
            <button
              onClick={() => scroll(-1)}
              className="neo-btn rounded-full w-9 h-9 flex items-center justify-center text-slate-400 hover:text-brand-turquoise transition-colors"
              data-testid="landing-agents-prev"
              aria-label="prev"
            >
              <ChevronRight className="w-4 h-4 rotate-180" />
            </button>
            <button
              onClick={() => scroll(1)}
              className="neo-btn rounded-full w-9 h-9 flex items-center justify-center text-slate-400 hover:text-brand-turquoise transition-colors"
              data-testid="landing-agents-next"
              aria-label="next"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      <div
        ref={trackRef}
        className="flex gap-4 overflow-x-auto snap-x snap-mandatory pb-3 px-4 lg:px-[max(3rem,calc((100vw-1024px)/2))] no-scrollbar"
        data-testid="landing-agents-track"
      >
        {AGENTS.map((a) => (
          <AgentCard key={a.id} agent={a} />
        ))}
        <div className="shrink-0 w-4" />
      </div>
    </section>
  );
}

// =============================================================
// Mentor (Hermes) inline chat with voice toggle
// =============================================================

function HermesChat() {
  const [mode, setMode] = useState("text"); // 'text' | 'voice'
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Привет! Я Hermes — главный координатор NXT8. Спросите что-нибудь о вашей команде, или попросите помочь спланировать день.",
    },
  ]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const send = async () => {
    const text = input.trim();
    if (!text || sending) return;
    const next = [...messages, { role: "user", content: text }];
    setMessages(next);
    setInput("");
    setSending(true);
    setError("");
    try {
      const res = await api.hermesChat({
        messages: next.map((m) => ({ role: m.role, content: m.content })),
        company_id: "default",
        user_id: "landing_visitor",
        mode: "operational",
        temperature: 0.3,
      });
      const reply =
        (res && (res.content || res.text)) ||
        "Не получилось получить ответ — попробуйте ещё раз.";
      setMessages((prev) => [...prev, { role: "assistant", content: reply }]);
    } catch (e) {
      setError("Сейчас Hermes недоступен. Попробуйте через минуту.");
    } finally {
      setSending(false);
    }
  };

  return (
    <section
      className="relative px-4 lg:px-12 py-8"
      data-testid="landing-hermes-chat"
    >
      <div className="max-w-3xl mx-auto">
        <div className="flex items-end justify-between mb-5 gap-3">
          <div>
            <div className="text-[10px] uppercase tracking-[0.3em] text-brand-turquoise mb-2">
              try it now · hermes
            </div>
            <h2 className="text-2xl lg:text-3xl font-light text-slate-100">
              Поговорите с координатором
            </h2>
            <p className="text-[12px] text-slate-500 mt-1">
              Без регистрации. Сразу в браузере.
            </p>
          </div>

          <div className="inline-flex rounded-full border border-white/10 bg-brand-dark/60 p-1 backdrop-blur-md">
            <button
              type="button"
              onClick={() => setMode("text")}
              className={`px-3 py-1.5 rounded-full text-[10px] uppercase tracking-widest flex items-center gap-1.5 transition-colors ${
                mode === "text"
                  ? "bg-brand-turquoise/15 text-brand-turquoise"
                  : "text-slate-500 hover:text-slate-300"
              }`}
              data-testid="landing-chat-mode-text"
            >
              <MessageSquare className="w-3 h-3" /> текст
            </button>
            <button
              type="button"
              onClick={() => setMode("voice")}
              className={`px-3 py-1.5 rounded-full text-[10px] uppercase tracking-widest flex items-center gap-1.5 transition-colors ${
                mode === "voice"
                  ? "bg-brand-turquoise/15 text-brand-turquoise"
                  : "text-slate-500 hover:text-slate-300"
              }`}
              data-testid="landing-chat-mode-voice"
            >
              <Mic className="w-3 h-3" /> голос
            </button>
          </div>
        </div>

        <div className="glass-card window-border glow-turquoise-subtle rounded-2xl p-4">
          <div
            ref={scrollRef}
            className="h-[260px] overflow-y-auto pr-1 space-y-3 mb-3"
            data-testid="landing-chat-thread"
          >
            {messages.map((m, i) => (
              <div
                key={i}
                className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
                data-testid={`landing-msg-${m.role}`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-[12.5px] leading-relaxed ${
                    m.role === "user" ? "bubble-user" : "bubble-ai"
                  }`}
                >
                  <div className="whitespace-pre-wrap break-words">
                    {m.content}
                  </div>
                </div>
              </div>
            ))}
            {sending && (
              <div className="flex justify-start">
                <div className="bubble-ai max-w-[85%] rounded-2xl px-4 py-2.5 text-[12px] text-slate-400 flex items-center gap-2">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  hermes думает…
                </div>
              </div>
            )}
            {error && (
              <div className="text-[10px] text-red-400 border border-red-500/30 bg-red-500/5 rounded-lg px-2 py-1">
                {error}
              </div>
            )}
          </div>

          {mode === "text" ? (
            <div className="flex items-end gap-2">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    send();
                  }
                }}
                rows={1}
                placeholder="Напишите Hermes…"
                disabled={sending}
                className="flex-1 bg-brand-dark/60 border border-white/10 rounded-xl px-3 py-2.5 text-[13px] outline-none focus:border-brand-turquoise/50 resize-none disabled:opacity-50"
                data-testid="landing-chat-input"
              />
              <button
                type="button"
                onClick={send}
                disabled={sending || !input.trim()}
                className="neo-btn rounded-full px-4 py-2.5 text-brand-turquoise text-[11px] uppercase tracking-widest flex items-center gap-1.5 disabled:opacity-40"
                data-testid="landing-chat-send"
              >
                <Send className="w-3.5 h-3.5" />
                send
              </button>
            </div>
          ) : (
            <VoiceModeStub
              onTranscript={(txt) => {
                setInput(txt);
                setMode("text");
              }}
            />
          )}
        </div>
      </div>
    </section>
  );
}

function VoiceModeStub({ onTranscript }) {
  const [state, setState] = useState("idle"); // idle | requesting | recording | processing | speaking | error
  const [errorMsg, setErrorMsg] = useState("");
  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const audioRef = useRef(null);

  const start = async () => {
    if (state === "recording") return;
    setErrorMsg("");
    setState("requesting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime =
        ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"].find((m) =>
          window.MediaRecorder?.isTypeSupported?.(m)
        ) || "";
      const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : {});
      chunksRef.current = [];
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setState("processing");
        try {
          const blob = new Blob(chunksRef.current, {
            type: mime || "audio/webm",
          });
          const res = await api.voiceConverse(blob, {
            session_id: "landing_voice",
            user_id: "landing_visitor",
            language: "ru",
          });
          if (res?.transcript) onTranscript?.(res.transcript);
          if (res?.audio_b64) {
            const audio = new Audio(`data:audio/mp3;base64,${res.audio_b64}`);
            audioRef.current = audio;
            setState("speaking");
            audio.onended = () => setState("idle");
            audio.onerror = () => setState("idle");
            await audio.play().catch(() => setState("idle"));
          } else {
            setState("idle");
          }
        } catch (e) {
          setErrorMsg("Не удалось обработать запись");
          setState("error");
        }
      };
      recorderRef.current = rec;
      rec.start();
      setState("recording");
    } catch (e) {
      setErrorMsg("Микрофон недоступен — разрешите доступ в браузере");
      setState("error");
    }
  };

  const stop = () => {
    const rec = recorderRef.current;
    if (rec && rec.state === "recording") rec.stop();
  };

  const recording = state === "recording";
  const busy = state === "requesting" || state === "processing";
  const speaking = state === "speaking";

  return (
    <div
      className="flex flex-col items-center justify-center py-2"
      data-testid="landing-voice"
    >
      <button
        type="button"
        onClick={recording ? stop : start}
        disabled={busy}
        className={`relative w-20 h-20 rounded-full flex items-center justify-center transition-all ${
          recording
            ? "bg-red-500/20 border-2 border-red-400 shadow-[0_0_24px_rgba(248,113,113,0.4)]"
            : speaking
              ? "bg-brand-turquoise/20 border-2 border-brand-turquoise shadow-[0_0_24px_var(--brand-turquoise)]"
              : "bg-brand-dark/60 border-2 border-brand-turquoise/40 hover:border-brand-turquoise"
        } disabled:opacity-50`}
        data-testid="landing-voice-btn"
      >
        {busy ? (
          <Loader2 className="w-8 h-8 text-brand-turquoise animate-spin" />
        ) : recording ? (
          <Square className="w-7 h-7 text-red-400" />
        ) : speaking ? (
          <Volume2 className="w-8 h-8 text-brand-turquoise animate-pulse" />
        ) : (
          <Mic className="w-8 h-8 text-brand-turquoise" />
        )}
      </button>
      <div className="mt-3 text-[10px] uppercase tracking-widest text-slate-500">
        {recording
          ? "запись… нажмите чтобы остановить"
          : busy
            ? "обработка…"
            : speaking
              ? "hermes говорит"
              : "нажмите чтобы записать"}
      </div>
      {errorMsg && (
        <div className="text-[10px] text-red-400 mt-2">{errorMsg}</div>
      )}
    </div>
  );
}

// =============================================================
// Tariffs
// =============================================================

function TariffCard({ tariff }) {
  return (
    <article
      className={`glass-card window-border glow-turquoise-subtle rounded-2xl p-5 flex flex-col ${
        tariff.highlight ? "ring-1 ring-brand-turquoise/40" : ""
      }`}
      data-testid={`landing-tariff-${tariff.id}`}
    >
      {tariff.highlight && (
        <div className="text-[9px] uppercase tracking-[0.3em] text-brand-turquoise mb-2 flex items-center gap-1">
          <Sparkles className="w-3 h-3" /> популярный выбор
        </div>
      )}
      <div className={`${tariff.accent} font-light tracking-widest uppercase text-xs mb-3`}>
        {tariff.name}
      </div>
      <div className="flex items-baseline gap-1 mb-1">
        <span className="text-4xl font-extralight text-slate-100">
          {tariff.price}
        </span>
      </div>
      <div className="text-[10px] uppercase tracking-widest text-slate-500 mb-4">
        {tariff.period}
      </div>
      <ul className="space-y-2 mb-5 flex-1">
        {tariff.features.map((f, i) => (
          <li
            key={i}
            className="flex items-start gap-2 text-[12.5px] text-slate-300"
          >
            <span className={`${tariff.accent} mt-0.5`}>›</span>
            <span>{f}</span>
          </li>
        ))}
      </ul>
      <button
        type="button"
        onClick={() => goToCheckout(tariff.id)}
        className="neo-btn rounded-full px-4 py-2.5 text-brand-turquoise text-[11px] uppercase tracking-widest flex items-center justify-center gap-2 hover:bg-brand-turquoise/10 transition-colors"
        data-testid={`landing-tariff-cta-${tariff.id}`}
      >
        Начать <ChevronRight className="w-3.5 h-3.5" />
      </button>
    </article>
  );
}

function Tariffs() {
  return (
    <section
      className="relative px-4 lg:px-12 py-10"
      data-testid="landing-tariffs"
    >
      <div className="max-w-5xl mx-auto">
        <div className="mb-6">
          <div className="text-[10px] uppercase tracking-[0.3em] text-brand-turquoise mb-2">
            pricing · per seat
          </div>
          <h2 className="text-2xl lg:text-3xl font-light text-slate-100 mb-2">
            Тарифы NXT8
          </h2>
          <p className="text-[13px] text-slate-400">
            Цена за одного сотрудника в месяц. Компания может комбинировать
            тарифы между сотрудниками и отделами.
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {TARIFFS.map((t) => (
            <TariffCard key={t.id} tariff={t} />
          ))}
        </div>
      </div>
    </section>
  );
}

// =============================================================
// How it works
// =============================================================

function HowItWorks() {
  return (
    <section
      className="relative px-4 lg:px-12 py-10"
      data-testid="landing-how"
    >
      <div className="max-w-5xl mx-auto">
        <div className="mb-6">
          <div className="text-[10px] uppercase tracking-[0.3em] text-brand-turquoise mb-2">
            how it works · 3 steps
          </div>
          <h2 className="text-2xl lg:text-3xl font-light text-slate-100">
            Как работает NXT8
          </h2>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {STEPS.map((s) => (
            <div
              key={s.n}
              className="glass-card window-border rounded-2xl p-5"
              data-testid={`landing-step-${s.n}`}
            >
              <div className="text-brand-turquoise text-[10px] uppercase tracking-[0.3em] mb-3">
                step {s.n}
              </div>
              <h3 className="text-slate-100 text-base font-light mb-2">
                {s.title}
              </h3>
              <p className="text-[13px] text-slate-400 leading-relaxed">
                {s.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// =============================================================
// Pilot
// =============================================================

function Pilot({ onEnter }) {
  return (
    <section
      className="relative px-4 lg:px-12 py-12 lg:py-16"
      data-testid="landing-pilot"
    >
      <div className="max-w-4xl mx-auto">
        <div className="glass-card window-border glow-turquoise-subtle rounded-3xl p-8 lg:p-12 text-center">
          <div className="text-[10px] uppercase tracking-[0.3em] text-brand-turquoise mb-4">
            free pilot
          </div>
          <h2 className="text-3xl lg:text-5xl font-extralight text-slate-100 leading-tight mb-4">
            10 сотрудников <span className="text-slate-600">·</span>{" "}
            14 дней <span className="text-slate-600">·</span>{" "}
            <span className="text-brand-turquoise">бесплатно</span>
          </h2>
          <p className="text-[14px] lg:text-base text-slate-400 max-w-2xl mx-auto leading-relaxed mb-3">
            Проверьте NXT8 внутри вашей компании на реальных процессах и
            задачах.
          </p>
          <p className="text-[12px] text-slate-500 mb-8">
            Без долгих контрактов. Без сложного внедрения. Без давления и
            обязательств.
          </p>
          <button
            type="button"
            onClick={onEnter}
            className="neo-btn rounded-full px-6 py-3 text-brand-turquoise text-[12px] uppercase tracking-widest inline-flex items-center gap-2 hover:bg-brand-turquoise/10 transition-colors"
            data-testid="landing-pilot-cta"
          >
            Запустить пилот <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </section>
  );
}

// =============================================================
// Root
// =============================================================

export default function LandingView({ onEnter }) {
  return (
    <div
      className="App led-matrix min-h-screen flex flex-col relative overflow-y-auto"
      data-testid="landing-view"
    >
      <div className="fixed inset-0 led-matrix pointer-events-none -z-10" />

      <Hero onEnter={onEnter} />
      <InlineTicker
        items={HERO_TICKER_ITEMS}
        testId="landing-ticker-hero"
      />

      <AgentsSwipe />
      <HermesChat />

      <InlineTicker
        items={FEATURES_TICKER_ITEMS}
        testId="landing-ticker-features"
      />
      <Tariffs />

      <InlineTicker
        items={PILOT_TICKER_ITEMS}
        accent="text-brand-turquoise"
        testId="landing-ticker-pilot"
      />
      <HowItWorks />
      <Pilot onEnter={onEnter} />

      <footer
        className="px-4 lg:px-12 py-6 text-center text-[10px] uppercase tracking-widest text-slate-600 border-t border-white/5"
        data-testid="landing-footer"
      >
        nxt8.pro · operational ai system · {new Date().getFullYear()}
      </footer>
    </div>
  );
}
