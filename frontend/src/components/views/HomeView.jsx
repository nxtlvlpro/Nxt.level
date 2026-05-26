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

// ============================================================
// Static content (TZ — Russian-first, no AI jargon)
// ============================================================

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
  },
];

const TARIFFS = [
  {
    id: "personal",
    name: "Personal",
    price: "$9",
    period: "/ сотрудник в месяц",
    accent: "text-brand-turquoise",
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

const CHECKOUT_BASE = "https://nxt8.pro/checkout";

function goToCheckout(planId) {
  const url = `${CHECKOUT_BASE}?plan=${encodeURIComponent(planId)}`;
  if (typeof window !== "undefined") {
    window.open(url, "_blank", "noopener,noreferrer");
  }
}

// ============================================================
// Inline ticker — reusable between sections
// ============================================================

function InlineTicker({ items, testId }) {
  const stream = [...items, ...items, ...items];
  return (
    <div
      className="relative overflow-hidden border-y border-white/5 led-ticker bg-brand-dark/60 backdrop-blur-md py-2 -mx-4 lg:-mx-8"
      data-testid={testId}
    >
      <div className="flex items-center text-[10px] uppercase tracking-widest text-slate-400 overflow-hidden">
        <div className="ticker-track flex items-center space-x-8 whitespace-nowrap">
          {stream.map((it, idx) => (
            <span
              key={`${it}-${idx}`}
              className="shrink-0 flex items-center gap-2"
            >
              <span className="text-brand-turquoise">◇</span>
              <span>{it}</span>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

// ============================================================
// Intro card (first slide — описание проекта)
// ============================================================

function IntroCard() {
  return (
    <article
      className="snap-center shrink-0 w-[78vw] sm:w-[360px] glass-card window-border glow-turquoise rounded-2xl p-5 flex flex-col bg-gradient-to-br from-brand-turquoise/[0.06] to-transparent font-mono tracking-tight"
      data-testid="home-agent-intro"
      data-card-idx="0"
    >
      <div className="flex items-center gap-3 mb-4">
        <div className="w-2 h-2 rounded-full bg-brand-turquoise shadow-[0_0_10px_var(--brand-turquoise)] animate-pulse" />
        <span className="text-brand-turquoise text-[10px] uppercase tracking-[0.3em]">
          operational ai system
        </span>
      </div>
      <h2
        className="text-2xl sm:text-[26px] font-extralight tracking-tight text-slate-100 leading-tight mb-3"
        data-testid="home-hero-title"
      >
        Операционная AI-система{" "}
        <span className="text-brand-turquoise">для современного бизнеса</span>
      </h2>
      <p className="text-[12px] text-slate-300 leading-relaxed tracking-tight mb-4">
        Готовая AI-команда, которая работает вместе с вашей компанией. Меньше
        хаоса. Больше координации. Без сложного внедрения.
      </p>
      <div className="mt-auto pt-3 border-t border-white/5">
        <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-slate-400">
          <ArrowRight className="w-3 h-3 text-brand-turquoise" />
          <span>выберите AI-агентов</span>
        </div>
      </div>
    </article>
  );
}

// (Hero block removed — описание перенесено в первую карточку карусели)

// ============================================================
// Agents — horizontal scroll/swipe
// ============================================================

function AgentCard({ agent, idx, transform }) {
  return (
    <article
      style={{
        transform,
        transformStyle: "preserve-3d",
        transition: "transform 0.45s cubic-bezier(0.2, 0.8, 0.2, 1), opacity 0.45s",
        transformOrigin: "center center",
      }}
      className="snap-center shrink-0 w-[78vw] sm:w-[360px] glass-card window-border glow-turquoise-subtle rounded-2xl p-5 flex flex-col font-mono tracking-tight"
      data-testid={`home-agent-${agent.id}`}
      data-card-idx={idx}
    >
      <div className="flex-1">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h3
              className={`${agent.accent} font-light text-sm tracking-widest uppercase`}
            >
              {agent.name}
            </h3>
            <div className="text-slate-200 text-[12px] mt-1.5 tracking-tight">
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
        <p className="text-[12px] text-slate-300 leading-relaxed tracking-tight">
          {agent.description}
        </p>
      </div>
      <button
        type="button"
        onClick={() => goToCheckout(agent.planId)}
        className="mt-5 neo-btn rounded-full px-4 py-2.5 text-brand-turquoise text-[11px] uppercase tracking-widest flex items-center justify-center gap-2 hover:bg-brand-turquoise/10 transition-colors"
        data-testid={`home-agent-cta-${agent.id}`}
      >
        Подключить <ChevronRight className="w-3.5 h-3.5" />
      </button>
    </article>
  );
}

function AgentsSwipe() {
  const trackRef = useRef(null);
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(false);
  const pauseTimerRef = useRef(null);

  const totalCards = AGENTS.length + 1; // intro + 7 agents

  // Compute the centered card index based on scroll position.
  useEffect(() => {
    const el = trackRef.current;
    if (!el) return;
    let raf = 0;
    const recompute = () => {
      const cards = el.querySelectorAll("[data-card-idx]");
      if (!cards.length) return;
      const center = el.scrollLeft + el.clientWidth / 2;
      let bestIdx = 0;
      let bestDist = Infinity;
      cards.forEach((c, i) => {
        const cardCenter = c.offsetLeft + c.clientWidth / 2;
        const dist = Math.abs(cardCenter - center);
        if (dist < bestDist) {
          bestDist = dist;
          bestIdx = i;
        }
      });
      setActive(bestIdx);
    };
    const onScroll = () => {
      if (raf) cancelAnimationFrame(raf);
      raf = requestAnimationFrame(recompute);
    };
    recompute();
    el.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", recompute);
    return () => {
      el.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", recompute);
      if (raf) cancelAnimationFrame(raf);
    };
  }, []);

  const scrollToIdx = (idx) => {
    const el = trackRef.current;
    if (!el) return;
    const card = el.querySelector(`[data-card-idx="${idx}"]`);
    if (!card) return;
    const target =
      card.offsetLeft - (el.clientWidth - card.clientWidth) / 2;
    el.scrollTo({ left: target, behavior: "smooth" });
  };

  // Pause autoplay briefly after user interaction
  const pauseTemporarily = (ms = 8000) => {
    setPaused(true);
    if (pauseTimerRef.current) clearTimeout(pauseTimerRef.current);
    pauseTimerRef.current = setTimeout(() => setPaused(false), ms);
  };

  const scrollBy = (dir) => {
    const next = Math.max(0, Math.min(totalCards - 1, active + dir));
    scrollToIdx(next);
    pauseTemporarily();
  };

  // Autoplay — advance once every 5s; loop back to start; pause on hover / interaction
  useEffect(() => {
    if (paused) return undefined;
    const id = setInterval(() => {
      const next = (active + 1) % totalCards;
      scrollToIdx(next);
    }, 5000);
    return () => clearInterval(id);
  }, [active, paused, totalCards]);

  useEffect(
    () => () => {
      if (pauseTimerRef.current) clearTimeout(pauseTimerRef.current);
    },
    []
  );

  // Coverflow transform: closer to active → flat & bigger; further → tilted trapezoid
  const getTransform = (idx) => {
    const diff = idx - active;
    const abs = Math.abs(diff);
    if (abs === 0) {
      return "perspective(1200px) rotateY(0deg) scale(1) translateZ(0)";
    }
    const dir = diff < 0 ? 1 : -1; // tilt left card to face right, vice versa
    const rotate = Math.min(38, 18 + (abs - 1) * 10) * dir;
    const scale = Math.max(0.7, 1 - abs * 0.1);
    const translateZ = -40 * abs;
    return `perspective(1200px) rotateY(${rotate}deg) scale(${scale}) translateZ(${translateZ}px)`;
  };

  const opacityFor = (idx) => {
    const abs = Math.abs(idx - active);
    if (abs === 0) return 1;
    if (abs === 1) return 0.7;
    return 0.4;
  };

  const cards = [
    <IntroCard key="intro" />,
    ...AGENTS.map((a, i) => (
      <AgentCard
        key={a.id}
        agent={a}
        idx={i + 1}
        transform={getTransform(i + 1)}
      />
    )),
  ];

  return (
    <section
      className="relative py-6"
      data-testid="home-agents"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onTouchStart={() => pauseTemporarily(10000)}
    >
      <div className="flex items-end justify-end mb-4 gap-2">
        <div className="hidden sm:flex items-center gap-2 shrink-0">
          <button
            onClick={() => scrollBy(-1)}
            disabled={active === 0}
            className="neo-btn rounded-full w-9 h-9 flex items-center justify-center text-slate-400 hover:text-brand-turquoise transition-colors disabled:opacity-30"
            data-testid="home-agents-prev"
            aria-label="prev"
          >
            <ChevronRight className="w-4 h-4 rotate-180" />
          </button>
          <button
            onClick={() => scrollBy(1)}
            disabled={active === AGENTS.length}
            className="neo-btn rounded-full w-9 h-9 flex items-center justify-center text-slate-400 hover:text-brand-turquoise transition-colors disabled:opacity-30"
            data-testid="home-agents-next"
            aria-label="next"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
      <div
        ref={trackRef}
        style={{ perspective: "1400px", scrollSnapType: "x mandatory" }}
        className="flex gap-6 overflow-x-auto pb-6 pt-2 -mx-4 lg:-mx-8 px-[calc(50%-39vw)] sm:px-[calc(50%-180px)] no-scrollbar"
        data-testid="home-agents-track"
      >
        {cards.map((card, i) =>
          React.cloneElement(card, {
            style: {
              transform: getTransform(i),
              opacity: opacityFor(i),
              transformStyle: "preserve-3d",
              transition:
                "transform 0.45s cubic-bezier(0.2, 0.8, 0.2, 1), opacity 0.45s",
              transformOrigin: "center center",
            },
          })
        )}
      </div>
      {/* dots indicator */}
      <div
        className="flex items-center justify-center gap-1.5 mt-1"
        data-testid="home-agents-dots"
      >
        {cards.map((_, i) => (
          <button
            key={i}
            type="button"
            onClick={() => {
              scrollToIdx(i);
              pauseTemporarily();
            }}
            className={`h-1.5 rounded-full transition-all ${
              i === active
                ? "w-6 bg-brand-turquoise shadow-[0_0_6px_var(--brand-turquoise)]"
                : "w-1.5 bg-slate-600 hover:bg-slate-400"
            }`}
            aria-label={`go to card ${i + 1}`}
          />
        ))}
      </div>
    </section>
  );
}

// ============================================================
// Hermes chat + voice toggle
// ============================================================

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
            session_id: "home_voice",
            user_id: "home_visitor",
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
      className="flex flex-col items-center justify-center py-4"
      data-testid="home-voice"
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
        data-testid="home-voice-btn"
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
  const cancelledRef = useRef(false);

  useEffect(() => {
    cancelledRef.current = false;
    return () => {
      cancelledRef.current = true;
    };
  }, []);

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
        user_id: "home_visitor",
        mode: "operational",
        temperature: 0.3,
      });
      if (cancelledRef.current) return;
      const reply =
        (res && (res.content || res.text)) ||
        "Не получилось получить ответ — попробуйте ещё раз.";
      setMessages((prev) => [...prev, { role: "assistant", content: reply }]);
    } catch (e) {
      if (!cancelledRef.current) {
        setError("Сейчас Hermes недоступен. Попробуйте через минуту.");
      }
    } finally {
      if (!cancelledRef.current) setSending(false);
    }
  };

  return (
    <section className="relative py-6" data-testid="home-hermes-chat">
      <div className="flex items-end justify-between mb-4 gap-3">
        <div className="min-w-0">
          <div className="text-[10px] uppercase tracking-[0.3em] text-brand-turquoise mb-1.5">
            try it now · hermes
          </div>
          <h2 className="text-xl lg:text-2xl font-light text-slate-100">
            Поговорите с координатором
          </h2>
          <p className="text-[11px] text-slate-500 mt-1">
            Без регистрации. Сразу здесь.
          </p>
        </div>

        <div className="inline-flex rounded-full border border-white/10 bg-brand-dark/60 p-1 backdrop-blur-md shrink-0">
          <button
            type="button"
            onClick={() => setMode("text")}
            className={`px-3 py-1.5 rounded-full text-[10px] uppercase tracking-widest flex items-center gap-1.5 transition-colors ${
              mode === "text"
                ? "bg-brand-turquoise/15 text-brand-turquoise"
                : "text-slate-500 hover:text-slate-300"
            }`}
            data-testid="home-chat-mode-text"
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
            data-testid="home-chat-mode-voice"
          >
            <Mic className="w-3 h-3" /> голос
          </button>
        </div>
      </div>

      <div className="glass-card window-border glow-turquoise-subtle rounded-2xl p-4">
        <div
          ref={scrollRef}
          className="h-[240px] overflow-y-auto pr-1 space-y-3 mb-3"
          data-testid="home-chat-thread"
        >
          {messages.map((m, i) => (
            <div
              key={i}
              className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
              data-testid={`home-msg-${m.role}`}
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
              data-testid="home-chat-input"
            />
            <button
              type="button"
              onClick={send}
              disabled={sending || !input.trim()}
              className="neo-btn rounded-full px-4 py-2.5 text-brand-turquoise text-[11px] uppercase tracking-widest flex items-center gap-1.5 disabled:opacity-40"
              data-testid="home-chat-send"
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
    </section>
  );
}

// ============================================================
// Tariffs
// ============================================================

function TariffCard({ tariff }) {
  return (
    <article
      className={`glass-card window-border glow-turquoise-subtle rounded-2xl p-5 flex flex-col ${
        tariff.highlight ? "ring-1 ring-brand-turquoise/40" : ""
      }`}
      data-testid={`home-tariff-${tariff.id}`}
    >
      {tariff.highlight && (
        <div className="text-[9px] uppercase tracking-[0.3em] text-brand-turquoise mb-2 flex items-center gap-1">
          <Sparkles className="w-3 h-3" /> популярный выбор
        </div>
      )}
      <div
        className={`${tariff.accent} font-light tracking-widest uppercase text-xs mb-3`}
      >
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
        data-testid={`home-tariff-cta-${tariff.id}`}
      >
        Начать <ChevronRight className="w-3.5 h-3.5" />
      </button>
    </article>
  );
}

function Tariffs() {
  return (
    <section className="relative py-6" data-testid="home-tariffs">
      <div className="mb-5">
        <div className="text-[10px] uppercase tracking-[0.3em] text-brand-turquoise mb-1.5">
          pricing · per seat
        </div>
        <h2 className="text-xl lg:text-2xl font-light text-slate-100 mb-1">
          Тарифы NXT8
        </h2>
        <p className="text-[12px] text-slate-400">
          Цена за одного сотрудника в месяц. Компания может комбинировать тарифы
          между сотрудниками и отделами.
        </p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {TARIFFS.map((t) => (
          <TariffCard key={t.id} tariff={t} />
        ))}
      </div>
    </section>
  );
}

// ============================================================
// How it works
// ============================================================

function HowItWorks() {
  return (
    <section className="relative py-6" data-testid="home-how">
      <div className="mb-5">
        <div className="text-[10px] uppercase tracking-[0.3em] text-brand-turquoise mb-1.5">
          how it works · 3 steps
        </div>
        <h2 className="text-xl lg:text-2xl font-light text-slate-100">
          Как работает NXT8
        </h2>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        {STEPS.map((s) => (
          <div
            key={s.n}
            className="glass-card window-border rounded-2xl p-5"
            data-testid={`home-step-${s.n}`}
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
    </section>
  );
}

// ============================================================
// Pilot CTA
// ============================================================

function Pilot() {
  return (
    <section className="relative py-8 lg:py-10" data-testid="home-pilot">
      <div className="glass-card window-border glow-turquoise-subtle rounded-3xl p-6 lg:p-10 text-center">
        <div className="text-[10px] uppercase tracking-[0.3em] text-brand-turquoise mb-3">
          free pilot
        </div>
        <h2 className="text-2xl lg:text-4xl font-extralight text-slate-100 leading-tight mb-3">
          10 сотрудников <span className="text-slate-600">·</span> 14 дней{" "}
          <span className="text-slate-600">·</span>{" "}
          <span className="text-brand-turquoise">бесплатно</span>
        </h2>
        <p className="text-[13px] lg:text-sm text-slate-400 max-w-2xl mx-auto leading-relaxed mb-2">
          Проверьте NXT8 внутри вашей компании на реальных процессах и задачах.
        </p>
        <p className="text-[11px] text-slate-500 mb-6">
          Без долгих контрактов. Без сложного внедрения. Без давления и
          обязательств.
        </p>
        <button
          type="button"
          onClick={() => goToCheckout("pilot")}
          className="neo-btn rounded-full px-6 py-3 text-brand-turquoise text-[11px] uppercase tracking-widest inline-flex items-center gap-2 hover:bg-brand-turquoise/10 transition-colors"
          data-testid="home-pilot-cta"
        >
          Запустить пилот <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </section>
  );
}

// ============================================================
// Root
// ============================================================

export default function HomeView() {
  return (
    <div data-testid="home-view">
      <AgentsSwipe />
      <HermesChat />

      <InlineTicker
        items={FEATURES_TICKER_ITEMS}
        testId="home-ticker-features"
      />
      <Tariffs />

      <InlineTicker items={PILOT_TICKER_ITEMS} testId="home-ticker-pilot" />
      <HowItWorks />
      <Pilot />
    </div>
  );
}
