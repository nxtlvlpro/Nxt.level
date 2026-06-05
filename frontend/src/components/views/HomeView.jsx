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
  Paperclip,
  X,
  FileText,
  Image as ImageIcon,
  AlertTriangle,
} from "lucide-react";
import api from "../../lib/api";
import { useT } from "../../i18n/LanguageContext";
import Waveform from "../Waveform";
import OnboardingFlow from "../OnboardingFlow";
import { playStreamedTts } from "../../lib/playStreamedTts";
import { hermesTalk } from "../../lib/hermesTalk";
import HermesTelegramButton from "./HermesTelegramButton";
import HermesWhatsAppButton from "./HermesWhatsAppButton";

// ============================================================
// Static content keys (texts come from i18n dictionary)
// ============================================================

const HERO_TICKER_KEYS = [
  "home.ticker.hero.1",
  "home.ticker.hero.2",
  "home.ticker.hero.3",
  "home.ticker.hero.4",
  "home.ticker.hero.5",
];

const FEATURES_TICKER_KEYS = [
  // brand names stay verbatim — no translation
  { raw: "WhatsApp" },
  { raw: "Telegram" },
  { raw: "CRM" },
  { key: "home.ticker.features.documents" },
  { key: "home.ticker.features.tasks" },
  { key: "home.ticker.features.calendar" },
  { raw: "Email" },
  { key: "home.ticker.features.together" },
];

const PILOT_TICKER_KEYS = [
  "home.ticker.pilot.1",
  "home.ticker.pilot.2",
  "home.ticker.pilot.3",
  "home.ticker.pilot.4",
];

const AGENTS = [
  {
    id: "hermes",
    name: "HERMES",
    roleKey: "home.agent.hermes.role",
    planKey: "home.agent.hermes.plan",
    planId: "personal",
    descKey: "home.agent.hermes.desc",
    accent: "text-brand-turquoise",
  },
  {
    id: "hr-mentor",
    name: "HR-MENTOR",
    roleKey: "home.agent.hr.role",
    planKey: "home.agent.hr.plan",
    planId: "team",
    descKey: "home.agent.hr.desc",
    accent: "text-purple-400",
  },
  {
    id: "client-ops",
    name: "CLIENT OPERATIONS",
    roleKey: "home.agent.client.role",
    planKey: "home.agent.client.plan",
    planId: "team",
    descKey: "home.agent.client.desc",
    accent: "text-emerald-400",
  },
  {
    id: "analytics",
    name: "ANALYTICS",
    roleKey: "home.agent.analytics.role",
    planKey: "home.agent.analytics.plan",
    planId: "headquarters",
    descKey: "home.agent.analytics.desc",
    accent: "text-sky-400",
  },
  {
    id: "financial",
    name: "FINANCIAL AGENT",
    roleKey: "home.agent.financial.role",
    planKey: "home.agent.financial.plan",
    planId: "operations",
    descKey: "home.agent.financial.desc",
    accent: "text-yellow-300",
  },
  {
    id: "legal",
    name: "LEGAL REVIEW",
    roleKey: "home.agent.legal.role",
    planKey: "home.agent.legal.plan",
    planId: "operations",
    descKey: "home.agent.legal.desc",
    accent: "text-orange-400",
  },
  {
    id: "marketing",
    name: "MARKETING OPS",
    roleKey: "home.agent.marketing.role",
    planKey: "home.agent.marketing.plan",
    planId: "operations",
    descKey: "home.agent.marketing.desc",
    accent: "text-pink-400",
  },
];

const TARIFFS = [
  {
    id: "personal",
    name: "Personal",
    price: "$9",
    accent: "text-brand-turquoise",
    featureKeys: [
      "home.plan.personal.f1",
      "home.plan.personal.f2",
      "home.plan.personal.f3",
      "home.plan.personal.f4",
    ],
  },
  {
    id: "team",
    name: "Team",
    price: "$14",
    accent: "text-purple-400",
    featureKeys: [
      "home.plan.team.f1",
      "home.plan.team.f2",
      "home.plan.team.f3",
      "home.plan.team.f4",
    ],
  },
  {
    id: "operations",
    name: "Operations",
    price: "$19",
    accent: "text-emerald-400",
    featureKeys: [
      "home.plan.operations.f1",
      "home.plan.operations.f2",
      "home.plan.operations.f3",
      "home.plan.operations.f4",
    ],
    highlight: true,
  },
  {
    id: "hq",
    name: "Headquarters",
    price: "$24",
    accent: "text-orange-400",
    featureKeys: [
      "home.plan.hq.f1",
      "home.plan.hq.f2",
      "home.plan.hq.f3",
      "home.plan.hq.f4",
      "home.plan.hq.f5",
    ],
  },
];

const STEPS = [
  { n: "01", titleKey: "home.how.step1.title", descKey: "home.how.step1.desc" },
  { n: "02", titleKey: "home.how.step2.title", descKey: "home.how.step2.desc" },
  { n: "03", titleKey: "home.how.step3.title", descKey: "home.how.step3.desc" },
];

const PLAN_ID_MAP = {
  // Map user-facing tariff slugs to backend plan_ids
  personal:     "personal",
  team:         "team",
  operations:   "operations",
  headquarters: "headquarters",
  // Pilot plan = lightest tier
  pilot:        "personal",
  // Legacy aliases (kept for backward-compat with any existing CTAs/i18n)
  basic:        "personal",
  simple:       "team",
  pro:          "operations",
  enterprise:   "headquarters",
  hq:           "headquarters",
};

function goToCheckout(planId) {
  // Any "Connect"/tariff CTA now opens the 7-question onboarding survey first.
  // The modal lives in <HomeView> and listens to this custom event; after the
  // survey completes the user is either sent to checkout for the chosen plan
  // or unlocked into the free test (when a valid access code was entered).
  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent("nxt8:open-onboarding", { detail: { planId } })
    );
  }
}

async function continueToCheckout(planId) {
  // Called by OnboardingFlow when the user is ready to proceed to payment.
  // Now creates a real Stripe Checkout Session via our backend and
  // redirects in the same tab so the return-flow (`/payment/return`)
  // can poll status without losing context.
  if (typeof window === "undefined") return;
  const stripePlanId = PLAN_ID_MAP[planId] || PLAN_ID_MAP.pilot;

  // Viral attribution — if this visitor came via ?ref=<share_id>, record
  // a conversion event for that share. This is fire-and-forget; it must
  // never block the checkout call.
  try {
    const ref = localStorage.getItem("nxt8.share.ref");
    if (ref) {
      api.shareConversion(ref, "checkout").catch(() => { /* ignore */ });
    }
  } catch { /* ignore */ }

  try {
    const res = await api.checkoutSessionCreate({
      plan_id: stripePlanId,
      quantity: 1,
      origin: window.location.origin,
    });
    if (res?.url) {
      window.location.href = res.url;
      return;
    }
    throw new Error("no checkout url");
  } catch (e) {
    // Fall back to onboarding contact (no payment) so the visitor isn't stranded.
    window.dispatchEvent(
      new CustomEvent("nxt8:checkout-error", {
        detail: { planId: stripePlanId, message: String(e?.message || e) },
      })
    );
  }
}

// ============================================================
// Inline ticker
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
// Intro card (first slide)
// ============================================================

function IntroCard({ t }) {
  return (
    <article
      className="snap-center shrink-0 w-[78vw] sm:w-[360px] glass-card window-border glow-turquoise rounded-2xl p-5 flex flex-col bg-gradient-to-br from-brand-turquoise/[0.06] to-transparent font-mono tracking-tight"
      data-testid="home-agent-intro"
      data-card-idx="0"
    >
      <div className="flex items-center gap-3 mb-4">
        <div className="w-2 h-2 rounded-full bg-brand-turquoise shadow-[0_0_10px_var(--brand-turquoise)] animate-pulse" />
        <span className="text-brand-turquoise text-[10px] uppercase tracking-[0.3em]">
          {t("home.intro.eyebrow")}
        </span>
      </div>
      <h2
        className="text-2xl sm:text-[26px] font-extralight tracking-tight text-slate-100 leading-tight mb-3"
        data-testid="home-hero-title"
      >
        {t("home.intro.title.before")}{" "}
        <span className="text-brand-turquoise">{t("home.intro.title.accent")}</span>
      </h2>
      <p className="text-[12px] text-slate-300 leading-relaxed tracking-tight mb-4">
        {t("home.intro.body")}
      </p>
      <div className="mt-auto pt-3 border-t border-white/5">
        <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-slate-400">
          <ArrowRight className="w-3 h-3 text-brand-turquoise" />
          <span>{t("home.intro.cta")}</span>
        </div>
      </div>
    </article>
  );
}

// ============================================================
// Agent card
// ============================================================

function AgentCard({ agent, idx, t }) {
  return (
    <article
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
              {t(agent.roleKey)}
            </div>
          </div>
          <span className="text-[9px] uppercase tracking-widest text-slate-500 border border-white/10 rounded-full px-2 py-1">
            {t("home.agent.label")}
          </span>
        </div>
        <div className="text-[10px] uppercase tracking-widest text-slate-500 border-t border-white/5 pt-3 mb-3">
          {t(agent.planKey)}
        </div>
        <p className="text-[12px] text-slate-300 leading-relaxed tracking-tight">
          {t(agent.descKey)}
        </p>
      </div>
      <button
        type="button"
        onClick={() => goToCheckout(agent.planId)}
        className="mt-5 neo-btn rounded-full px-4 py-2.5 text-brand-turquoise text-[11px] uppercase tracking-widest flex items-center justify-center gap-2 hover:bg-brand-turquoise/10 transition-colors"
        data-testid={`home-agent-cta-${agent.id}`}
      >
        {t("home.agent.cta")} <ChevronRight className="w-3.5 h-3.5" />
      </button>
    </article>
  );
}

function AgentsSwipe({ t }) {
  const trackRef = useRef(null);
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(false);
  const pauseTimerRef = useRef(null);

  const totalCards = AGENTS.length + 1 + TARIFFS.length + 1;

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

  const getTransform = (idx) => {
    const diff = idx - active;
    const abs = Math.abs(diff);
    if (abs === 0) {
      return "perspective(1200px) rotateY(0deg) scale(1) translateZ(0)";
    }
    const dir = diff < 0 ? 1 : -1;
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
    <IntroCard key="intro" t={t} />,
    ...AGENTS.map((a, i) => (
      <AgentCard key={a.id} agent={a} idx={i + 1} t={t} />
    )),
    ...TARIFFS.map((tt, i) => (
      <CarouselTariffCard
        key={`tariff-${tt.id}`}
        tariff={tt}
        idx={AGENTS.length + 1 + i}
        t={t}
      />
    )),
    <CarouselPilotCard
      key="pilot"
      idx={AGENTS.length + 1 + TARIFFS.length}
      t={t}
    />,
  ];

  return (
    <section
      className="relative pt-1 pb-6"
      data-testid="home-agents"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onTouchStart={() => pauseTemporarily(10000)}
    >
      <div className="flex items-end justify-end mb-1 gap-2 min-h-0 sm:min-h-[36px]">
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
            disabled={active === totalCards - 1}
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
      <div
        className="flex items-center justify-center gap-1.5 mt-1"
        data-testid="home-agents-dots"
      >
        {cards.map((_, i) => (
          <button
            key={`dot-${i}`}
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
// Hermes chat + voice — unified bubble dialog
// ============================================================

const HERMES_STORAGE_KEY = "nxt8.home.hermes";
const NXT8_USER_ID_KEY = "nxt8.user_id";

// Persistent per-browser visitor id. Anonymous-but-stable: lets the agent
// recognise the same person across sessions, devices that share storage,
// and weeks apart. When real auth lands, this value can be overwritten
// with the authenticated user's id.
function getOrCreateUserId() {
  if (typeof window === "undefined") return "anon";
  try {
    let uid = window.localStorage.getItem(NXT8_USER_ID_KEY);
    if (!uid) {
      uid = `u_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
      window.localStorage.setItem(NXT8_USER_ID_KEY, uid);
    }
    return uid;
  } catch {
    return "anon";
  }
}

function loadHermesState() {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(HERMES_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || !Array.isArray(parsed.messages)) return null;
    return parsed;
  } catch {
    return null;
  }
}

function saveHermesState(messages, sessionId) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(
      HERMES_STORAGE_KEY,
      JSON.stringify({ messages, session_id: sessionId })
    );
  } catch {
    /* ignore */
  }
}

function genSessionId() {
  return `home_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
}

// Inline voice recorder — drops user transcript + assistant reply as bubbles
// into the SAME shared conversation managed by the parent HermesChat.
function VoiceRecorder({ onUserTranscript, onAssistantReply, onError, onSessionId, onPhase, lang, sessionId, t }) {
  const [state, setState] = useState("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [activeStream, setActiveStream] = useState(null);
  const [activeAudio, setActiveAudio] = useState(null);
  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const audioRef = useRef(null);
  // VAD (voice-activity-detection) — auto-stop after 2 s of silence.
  const vadCtxRef = useRef(null);
  const vadIntervalRef = useRef(null);
  const vadStartRef = useRef(0);
  const vadLastSpeechRef = useRef(0);

  const stopVad = () => {
    if (vadIntervalRef.current) {
      clearInterval(vadIntervalRef.current);
      vadIntervalRef.current = null;
    }
    if (vadCtxRef.current) {
      try { vadCtxRef.current.close(); } catch { /* ignore */ }
      vadCtxRef.current = null;
    }
  };

  // VAD constants
  const VAD_SILENCE_MS = 2000;       // stop after this much consecutive silence
  const VAD_GRACE_MS = 800;          // ignore VAD during first N ms of recording
  const VAD_MIN_DURATION_MS = 700;   // never auto-stop before this
  const VAD_RMS_THRESHOLD = 8;       // byte-domain RMS deviation from 128
  const VAD_MAX_DURATION_MS = 45000; // hard cap

  const startVad = (stream) => {
    try {
      const AC = window.AudioContext || window.webkitAudioContext;
      const ctx = new AC();
      vadCtxRef.current = ctx;
      const src = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.4;
      src.connect(analyser);
      const data = new Uint8Array(analyser.fftSize);
      vadStartRef.current = performance.now();
      vadLastSpeechRef.current = performance.now();
      vadIntervalRef.current = setInterval(() => {
        const now = performance.now();
        const elapsed = now - vadStartRef.current;
        analyser.getByteTimeDomainData(data);
        let sumSq = 0;
        for (let i = 0; i < data.length; i += 1) {
          const v = data[i] - 128;
          sumSq += v * v;
        }
        const rms = Math.sqrt(sumSq / data.length);
        const isSpeech = rms >= VAD_RMS_THRESHOLD;
        if (isSpeech) vadLastSpeechRef.current = now;

        // Hard cap on duration
        if (elapsed >= VAD_MAX_DURATION_MS) {
          stop();
          return;
        }
        // Auto-stop after enough silence (post grace + min duration)
        if (
          elapsed > VAD_GRACE_MS &&
          elapsed > VAD_MIN_DURATION_MS &&
          now - vadLastSpeechRef.current >= VAD_SILENCE_MS
        ) {
          stop();
        }
      }, 100);
    } catch {
      // VAD is optional — if it fails, the user can still tap to stop.
    }
  };

  // Stop any playback when unmounting (e.g. user switches mode)
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        try { audioRef.current.pause(); } catch { /* ignore */ }
      }
      const rec = recorderRef.current;
      if (rec && rec.state === "recording") {
        try { rec.stop(); } catch { /* ignore */ }
      }
      stopVad();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const start = async () => {
    if (state === "recording") return;
    setErrorMsg("");
    setState("requesting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      setActiveStream(stream);
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
        stream.getTracks().forEach((tr) => tr.stop());
        setActiveStream(null);
        setState("processing");
        // Audio playback queue — sequential, in-order.
        const audioQueue = [];
        let isPlaying = false;
        let assistantText = "";
        let assistantAppended = false;

        const playNext = () => {
          if (isPlaying || audioQueue.length === 0) return;
          const item = audioQueue.shift();
          isPlaying = true;
          setState("speaking");
          onPhase?.("speaking");
          const a = new Audio(`data:audio/mp3;base64,${item}`);
          // crossOrigin is required for Web Audio analyser on data: URLs
          // in some Chromium builds. Harmless on others.
          try { a.crossOrigin = "anonymous"; } catch { /* ignore */ }
          audioRef.current = a;
          // Feed Waveform with the currently-playing element so the bars
          // dance to the actual TTS amplitude.
          setActiveAudio(a);
          a.onended = () => {
            isPlaying = false;
            if (audioQueue.length > 0) {
              playNext();
            } else {
              setActiveAudio(null);
              setState("idle");
              onPhase?.("idle");
            }
          };
          a.onerror = () => {
            isPlaying = false;
            setActiveAudio(null);
            setState("idle");
            onPhase?.("idle");
          };
          a.play().catch(() => {
            isPlaying = false;
            setActiveAudio(null);
            setState("idle");
            onPhase?.("idle");
          });
        };

        try {
          const blob = new Blob(chunksRef.current, {
            type: mime || "audio/webm",
          });
          await api.voiceConverseStream(
            blob,
            {
              session_id: sessionId,
              user_id: getOrCreateUserId(),
              language: lang,
            },
            (frame) => {
              if (!frame || !frame.type) return;
              if (frame.type === "meta" && frame.session_id) {
                onSessionId?.(frame.session_id);
              } else if (frame.type === "transcript" && frame.text) {
                onUserTranscript?.(frame.text);
              } else if (frame.type === "reply_text" && frame.text) {
                assistantText = frame.text;
                onAssistantReply?.(assistantText);
                assistantAppended = true;
                // Bubble is on screen — show "preparing voice" until the
                // first audio chunk actually starts playing.
                setState("synthesizing");
                onPhase?.("synthesizing");
              } else if (frame.type === "audio_chunk" && frame.audio_b64) {
                audioQueue.push(frame.audio_b64);
                playNext();
              } else if (frame.type === "error") {
                const msg = frame.message || t("voice.error.process");
                onError?.(msg);
                setErrorMsg(msg);
                setState("error");
              }
            }
          );
          if (!assistantAppended && assistantText) {
            onAssistantReply?.(assistantText);
          }
          if (audioQueue.length === 0 && !isPlaying) {
            setState("idle");
          }
        } catch (e) {
          const msg = t("voice.error.process");
          setErrorMsg(msg);
          onError?.(msg);
          setState("error");
        }
      };
      recorderRef.current = rec;
      rec.start();
      setState("recording");
    } catch (e) {
      const msg = t("voice.error.mic");
      setErrorMsg(msg);
      onError?.(msg);
      setState("error");
    }
  };

  const stop = () => {
    const rec = recorderRef.current;
    if (rec && rec.state === "recording") rec.stop();
  };

  const recording = state === "recording";
  const busy = state === "requesting" || state === "processing";
  const synthesizing = state === "synthesizing";
  const speaking = state === "speaking";

  return (
    <div
      className="flex flex-col items-center justify-center py-3"
      data-testid="home-voice"
    >
      <button
        type="button"
        onClick={recording ? stop : start}
        disabled={busy || synthesizing}
        className={`relative w-20 h-20 rounded-full flex items-center justify-center transition-all ${
          recording
            ? "bg-red-500/20 border-2 border-red-400 shadow-[0_0_24px_rgba(248,113,113,0.4)]"
            : speaking
              ? "bg-brand-turquoise/20 border-2 border-brand-turquoise shadow-[0_0_24px_var(--brand-turquoise)]"
              : synthesizing
                ? "bg-purple-500/15 border-2 border-purple-400/60 shadow-[0_0_20px_rgba(192,132,252,0.35)]"
                : "bg-brand-dark/60 border-2 voice-mic-breathe hover:border-brand-turquoise"
        } disabled:opacity-60`}
        data-testid="home-voice-btn"
        aria-label={recording ? t("voice.mic.aria.stop") : t("voice.mic.aria.start")}
      >
        {/* Outer soft halo ring — visible only in idle state to draw attention */}
        {!recording && !speaking && !synthesizing && !busy && (
          <span className="voice-mic-halo" aria-hidden="true" />
        )}
        {busy ? (
          <Loader2 className="w-8 h-8 text-brand-turquoise animate-spin" />
        ) : synthesizing ? (
          <Loader2 className="w-8 h-8 text-purple-400 animate-spin" />
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
          ? t("voice.recording")
          : busy
            ? t("voice.processing")
            : synthesizing
              ? t("voice.synthesizing")
              : speaking
                ? t("voice.speaking")
                : t("voice.idle")}
      </div>
      <div className="mt-3 h-7 flex items-center justify-center">
        <Waveform
          stream={recording ? activeStream : null}
          audio={speaking ? activeAudio : null}
          active={recording || speaking}
          color={recording ? "#f87171" : "var(--brand-turquoise)"}
          testId="home-voice-waveform"
        />
      </div>
      {errorMsg && (
        <div className="text-[10px] text-red-400 mt-2">{errorMsg}</div>
      )}
    </div>
  );
}

function formatBytes(bytes) {
  if (!bytes || bytes < 1024) return `${bytes || 0} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function ChipIcon({ kind, status }) {
  if (status === "uploading") return <Loader2 className="w-3 h-3 animate-spin text-brand-turquoise" />;
  if (status === "error") return <AlertTriangle className="w-3 h-3 text-red-400" />;
  if (kind === "image") return <ImageIcon className="w-3 h-3 text-brand-turquoise" />;
  return <FileText className="w-3 h-3 text-brand-turquoise" />;
}

// Chip rendered above the textarea while user is composing.
function ComposerChip({ att, onRemove }) {
  const errored = att.status === "error";
  return (
    <div
      className={`group inline-flex items-center gap-2 pl-2 pr-1 py-1 rounded-full text-[11px] border ${
        errored
          ? "border-red-500/30 bg-red-500/5 text-red-300"
          : "border-brand-turquoise/30 bg-brand-turquoise/5 text-slate-200"
      }`}
      data-testid="home-chat-composer-chip"
      title={att.name}
    >
      <ChipIcon kind={att.kind} status={att.status} />
      <span className="max-w-[160px] truncate">{att.name}</span>
      <span className="text-slate-500">{formatBytes(att.size)}</span>
      <button
        type="button"
        onClick={onRemove}
        className="ml-0.5 w-5 h-5 rounded-full hover:bg-white/10 flex items-center justify-center text-slate-400 hover:text-slate-200"
        aria-label="remove"
      >
        <X className="w-3 h-3" />
      </button>
    </div>
  );
}

// Chip rendered inside a chat bubble after the message is sent.
function BubbleAttachmentChip({ att }) {
  const isImage = att.kind === "image" && att.id;
  if (isImage) {
    const src = api.attachmentRawUrl(att.id);
    return (
      <a
        href={src}
        target="_blank"
        rel="noopener noreferrer"
        className="block max-w-[180px] rounded-lg overflow-hidden border border-white/10 hover:border-brand-turquoise/50"
        title={att.name}
      >
        <img
          src={src}
          alt={att.name}
          className="block w-full h-auto max-h-[140px] object-cover"
          loading="lazy"
        />
      </a>
    );
  }
  return (
    <div
      className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-white/5 border border-white/10 text-[11px]"
      title={att.name}
    >
      <FileText className="w-3 h-3 text-brand-turquoise" />
      <span className="max-w-[160px] truncate">{att.name}</span>
      {att.size ? (
        <span className="text-slate-500">{formatBytes(att.size)}</span>
      ) : null}
    </div>
  );
}

function HermesChat({ t, lang }) {
  const [mode, setMode] = useState("text");
  const [input, setInput] = useState("");
  // Boot: hydrate from localStorage if present, else default welcome.
  const [messages, setMessages] = useState(() => {
    const stored = loadHermesState();
    if (stored?.messages?.length) return stored.messages;
    return [{ role: "assistant", content: t("home.hermes.welcome") }];
  });
  const [sessionId, setSessionId] = useState(() => {
    const stored = loadHermesState();
    return stored?.session_id || genSessionId();
  });
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  // Voice synthesis phase — "synthesizing" between assistant text arrival and
  // the first TTS audio chunk; cleared when audio starts/ends.
  const [voicePhase, setVoicePhase] = useState("idle");
  // Index of the message currently being narrated via streamed TTS (Brad
  // Pitt voice). null = nothing playing. Controller stored in a ref so we
  // can stop mid-stream.
  const [speakingIdx, setSpeakingIdx] = useState(null);
  const speakCtlRef = useRef(null);

  const stopSpeaking = () => {
    try { speakCtlRef.current?.stop(); } catch { /* ignore */ }
    speakCtlRef.current = null;
    setSpeakingIdx(null);
  };

  const speakMessage = (idx, text) => {
    // Toggle off if already speaking this message.
    if (speakingIdx === idx) { stopSpeaking(); return; }
    stopSpeaking();
    const backendUrl = process.env.REACT_APP_BACKEND_URL;
    setSpeakingIdx(idx);
    speakCtlRef.current = playStreamedTts(text, {
      backendUrl,
      onEnd: () => { speakCtlRef.current = null; setSpeakingIdx(null); },
      onError: () => { speakCtlRef.current = null; setSpeakingIdx(null); },
    });
  };

  useEffect(() => () => stopSpeaking(), []);
  // Attachments: array of { local_id, file, name, kind, size, status:"uploading"|"ready"|"error", record? }
  const [attachments, setAttachments] = useState([]);
  const fileInputRef = useRef(null);
  const scrollRef = useRef(null);
  const cancelledRef = useRef(false);

  const guessKind = (file) => {
    const ext = (file.name.split(".").pop() || "").toLowerCase();
    if (["png", "jpg", "jpeg", "webp", "gif"].includes(ext)) return "image";
    if (["pdf", "docx", "txt", "md"].includes(ext)) return "document";
    if (file.type?.startsWith("image/")) return "image";
    return "other";
  };

  const onPickFiles = (e) => {
    const picked = Array.from(e.target.files || []);
    e.target.value = ""; // allow re-picking same file
    if (picked.length === 0) return;
    picked.forEach((file) => {
      const localId = `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      setAttachments((prev) => [
        ...prev,
        {
          local_id: localId,
          name: file.name,
          size: file.size,
          kind: guessKind(file),
          status: "uploading",
        },
      ]);
      api
        .attachmentUpload(file, {
          company_id: "default",
          user_id: getOrCreateUserId(),
          session_id: sessionId,
        })
        .then((rec) => {
          setAttachments((prev) =>
            prev.map((a) =>
              a.local_id === localId
                ? { ...a, status: "ready", record: rec, kind: rec.kind || a.kind }
                : a
            )
          );
        })
        .catch(() => {
          setAttachments((prev) =>
            prev.map((a) =>
              a.local_id === localId ? { ...a, status: "error" } : a
            )
          );
        });
    });
  };

  const removeAttachment = (localId) => {
    setAttachments((prev) => prev.filter((a) => a.local_id !== localId));
  };

  // Re-translate the welcome message when language flips — ONLY if the user
  // hasn't started a conversation yet.
  useEffect(() => {
    setMessages((prev) =>
      prev.length === 1 && prev[0].role === "assistant"
        ? [{ role: "assistant", content: t("home.hermes.welcome") }]
        : prev
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang]);

  // Persist every change.
  useEffect(() => {
    saveHermesState(messages, sessionId);
  }, [messages, sessionId]);

  useEffect(() => {
    cancelledRef.current = false;
    // Pre-warm a persistent visitor id so cross-session memory (M1) starts
    // accumulating from the very first interaction.
    getOrCreateUserId();
    return () => {
      cancelledRef.current = true;
    };
  }, []);

  // Auto-scroll when bubbles or transient indicators change.
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, sending, voicePhase]);

  const appendMessage = (role, content) => {
    setMessages((prev) => [...prev, { role, content }]);
  };

  const speakingIdx_unused_warn_silencer = speakingIdx; void speakingIdx_unused_warn_silencer;
  const [talkMode, setTalkMode] = useState(false);
  const talkCtlRef = useRef(null);

  useEffect(() => () => {
    try { talkCtlRef.current?.stop(); } catch { /* ignore */ }
  }, []);

  const send = async () => {
    const text = input.trim();
    const readyAttachments = attachments.filter((a) => a.status === "ready");
    if ((!text && readyAttachments.length === 0) || sending) return;
    const userBubble = {
      id: `m_${Date.now()}_u`,
      role: "user",
      content: text || (readyAttachments.length > 0
        ? `📎 ${readyAttachments.map((a) => a.name).join(", ")}`
        : ""),
      attachments: readyAttachments.map((a) => ({
        id: a.record?.id,
        name: a.name,
        kind: a.kind,
        size: a.size,
        mime: a.record?.mime,
      })),
    };
    const next = [...messages, userBubble];
    setMessages(next);
    setInput("");
    setAttachments([]);
    setSending(true);
    setError("");

    // Demo Tour — mark "Спроси Hermes" complete when the user sends
    // their first real message to Hermes from the home view.
    if (typeof window !== "undefined" && (text || readyAttachments.length > 0)) {
      try {
        window.dispatchEvent(
          new CustomEvent("nxt8:tour-complete", {
            detail: { step_id: "ask_hermes" },
          })
        );
      } catch { /* ignore */ }
    }

    // ── Talk-mode: streamed LLM + streamed TTS via /api/hermes/talk ────
    // First sentence audio plays in ~3.5s (vs ~8s end-to-end), text fills
    // the bubble token-by-token, audio queue plays sentences in order.
    if (talkMode && text) {
      try { talkCtlRef.current?.stop(); } catch { /* ignore */ }
      // Add an empty assistant bubble we'll fill from the stream.
      const streamingBubbleId = `m_${Date.now()}_a_stream`;
      setMessages((prev) => [
        ...prev,
        { id: streamingBubbleId, role: "assistant", content: "" },
      ]);
      const ctl = hermesTalk({
        backendUrl: process.env.REACT_APP_BACKEND_URL,
        message: text,
        userId: getOrCreateUserId(),
        sessionId,
        lang,
      });
      talkCtlRef.current = ctl;
      ctl.onText((delta) => {
        if (cancelledRef.current) return;
        setMessages((prev) => prev.map((m) =>
          m.id === streamingBubbleId
            ? { ...m, content: (m.content || "") + delta }
            : m
        ));
      });
      ctl.onDone(() => {
        if (!cancelledRef.current) setSending(false);
      });
      ctl.onError(() => {
        if (!cancelledRef.current) {
          setError(t("home.hermes.error"));
          setSending(false);
        }
      });
      return;
    }

    const sysHint =
      lang === "en"
        ? "Reply in English regardless of the user's language."
        : "Отвечай по-русски независимо от языка пользователя.";
    const payloadMessages = [
      { role: "system", content: sysHint },
      ...next.map((m) => ({ role: m.role, content: m.content })),
    ];
    try {
      const res = await api.hermesChat({
        messages: payloadMessages,
        company_id: "default",
        user_id: getOrCreateUserId(),
        session_id: sessionId,
        mode: "operational",
        temperature: 0.3,
        language: lang,
        attachment_ids: readyAttachments
          .map((a) => a.record?.id)
          .filter(Boolean),
      });
      if (cancelledRef.current) return;
      const reply =
        (res && (res.content || res.text)) || t("home.hermes.empty_reply");
      setMessages((prev) => [
        ...prev,
        { id: `m_${Date.now()}_a`, role: "assistant", content: reply },
      ]);
    } catch (e) {
      if (!cancelledRef.current) {
        setError(t("home.hermes.error"));
      }
    } finally {
      if (!cancelledRef.current) setSending(false);
    }
  };

  return (
    <section className="relative py-2 lg:py-6" data-testid="home-hermes-chat">
      {/* Header: hidden on mobile (chat speaks for itself), full block on desktop. */}
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between mb-3 lg:mb-4 gap-2 lg:gap-3">
        <div className="hidden lg:block min-w-0">
          <div className="text-[10px] uppercase tracking-[0.3em] text-brand-turquoise mb-1.5">
            {t("home.hermes.eyebrow")}
          </div>
          <h2 className="text-xl lg:text-2xl font-light text-slate-100">
            {t("home.hermes.title")}
          </h2>
          <p className="text-[11px] text-slate-500 mt-1">
            {t("home.hermes.subtitle")}
          </p>
        </div>

        <div
          className="
            grid grid-cols-4 gap-1.5 shrink-0
            lg:flex lg:items-center lg:gap-2 lg:w-auto
            [&>*]:min-w-0
            [&_button]:w-full [&_button]:justify-center [&_button]:px-2
            lg:[&_button]:w-auto lg:[&_button]:px-3
          "
        >
          <HermesTelegramButton />
          <HermesWhatsAppButton />
          <button
            type="button"
            onClick={() => setMode("text")}
            className={`px-2 py-1.5 rounded-full text-[10px] uppercase tracking-widest flex items-center gap-1.5 justify-center transition-colors border ${
              mode === "text"
                ? "border-brand-turquoise/40 bg-brand-turquoise/15 text-brand-turquoise"
                : "border-white/10 bg-brand-dark/60 text-slate-400 hover:text-slate-200"
            }`}
            data-testid="home-chat-mode-text"
          >
            <MessageSquare className="w-3 h-3 shrink-0" /> {t("home.hermes.mode.text")}
          </button>
          <button
            type="button"
            onClick={() => setMode("voice")}
            className={`px-2 py-1.5 rounded-full text-[10px] uppercase tracking-widest flex items-center gap-1.5 justify-center transition-colors border ${
              mode === "voice"
                ? "border-brand-turquoise/40 bg-brand-turquoise/15 text-brand-turquoise"
                : "border-white/10 bg-brand-dark/60 text-slate-400 hover:text-slate-200"
            }`}
            data-testid="home-chat-mode-voice"
          >
            <Mic className="w-3 h-3 shrink-0" /> {t("home.hermes.mode.voice")}
          </button>
        </div>
      </div>

      <div className="glass-card window-border glow-turquoise-subtle rounded-2xl p-3 lg:p-4">
        {/* Shared bubble feed — visible in both text & voice modes. New
            messages appear at the bottom; older ones scroll upward.
            Mobile gets a taller window so the chat dialog dominates the
            viewport without forcing the page to scroll. */}
        <div
          ref={scrollRef}
          className="h-[55vh] min-h-[360px] max-h-[560px] lg:h-[260px] lg:min-h-0 lg:max-h-none overflow-y-auto pr-1 space-y-3 mb-3"
          data-testid="home-chat-thread"
        >
          {messages.map((m, i) => (
            <div
              key={m.id || `msg-${i}`}
              className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
              data-testid={`home-msg-${m.role}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-[12.5px] leading-relaxed ${
                  m.role === "user" ? "bubble-user" : "bubble-ai"
                }`}
              >
                {m.attachments && m.attachments.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mb-1.5">
                    {m.attachments.map((att, ai) => (
                      <BubbleAttachmentChip key={att.id || ai} att={att} />
                    ))}
                  </div>
                )}
                {m.content && (
                  <div className="whitespace-pre-wrap break-words">
                    {m.content}
                  </div>
                )}
                {m.role === "assistant" && m.content && (
                  <button
                    type="button"
                    onClick={() => speakMessage(i, m.content)}
                    aria-label={speakingIdx === i ? "stop" : "speak"}
                    data-testid={`home-msg-speak-${i}`}
                    className={`mt-1.5 inline-flex items-center gap-1 text-[10px] uppercase tracking-widest transition-colors ${
                      speakingIdx === i
                        ? "text-brand-turquoise"
                        : "text-slate-500 hover:text-brand-turquoise"
                    }`}
                  >
                    {speakingIdx === i ? (
                      <>
                        <Square className="w-3 h-3" />
                        {t("home.hermes.speaking")}
                      </>
                    ) : (
                      <>
                        <Volume2 className="w-3 h-3" />
                        {t("home.hermes.speak")}
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>
          ))}
          {sending && (
            <div className="flex justify-start">
              <div className="bubble-ai max-w-[85%] rounded-2xl px-4 py-2.5 text-[12px] text-slate-400 flex items-center gap-2">
                <Loader2 className="w-3 h-3 animate-spin" />
                {t("home.hermes.thinking")}
              </div>
            </div>
          )}
          {voicePhase === "synthesizing" && (
            <div className="flex justify-start" data-testid="home-voice-synth-hint">
              <div className="bubble-ai max-w-[85%] rounded-2xl px-4 py-2 text-[11px] text-purple-300/80 flex items-center gap-2">
                <Volume2 className="w-3 h-3 animate-pulse" />
                {t("voice.synthesizing")}
              </div>
            </div>
          )}
          {error && (
            <div className="text-[10px] text-red-400 border border-red-500/30 bg-red-500/5 rounded-lg px-2 py-1">
              {error}
            </div>
          )}
        </div>

        {/* Input footer — swaps between text composer and voice recorder. */}
        {mode === "text" ? (
          <div className="space-y-2">
            {/* Attachment chips above the composer */}
            {attachments.length > 0 && (
              <div
                className="flex flex-wrap gap-1.5"
                data-testid="home-chat-attachment-chips"
              >
                {attachments.map((a) => (
                  <ComposerChip
                    key={a.local_id}
                    att={a}
                    onRemove={() => removeAttachment(a.local_id)}
                  />
                ))}
              </div>
            )}
            <div className="flex items-end gap-2">
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept="image/*,.pdf,.docx,.txt,.md,.csv,.xlsx"
                onChange={onPickFiles}
                className="hidden"
                data-testid="home-chat-file-input"
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={sending}
                className="shrink-0 w-10 h-10 rounded-xl border border-white/10 bg-brand-dark/60 hover:border-brand-turquoise/50 text-slate-400 hover:text-brand-turquoise flex items-center justify-center transition-colors disabled:opacity-40"
                aria-label={t("home.hermes.attach") || "Attach files"}
                title={t("home.hermes.attach") || "Attach files"}
                data-testid="home-chat-attach-btn"
              >
                <Paperclip className="w-4 h-4" />
              </button>
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
                placeholder={t("home.hermes.placeholder")}
                disabled={sending}
                className="flex-1 bg-brand-dark/60 border border-white/10 rounded-xl px-3 py-2.5 text-[13px] outline-none focus:border-brand-turquoise/50 resize-none disabled:opacity-50"
                data-testid="home-chat-input"
              />
              <button
                type="button"
                onClick={send}
                disabled={
                  sending ||
                  (!input.trim() &&
                    attachments.filter((a) => a.status === "ready").length === 0)
                }
                className="neo-btn rounded-full px-4 py-2.5 text-brand-turquoise text-[11px] uppercase tracking-widest flex items-center gap-1.5 disabled:opacity-40"
                data-testid="home-chat-send"
              >
                <Send className="w-3.5 h-3.5" />
                {t("home.hermes.send")}
              </button>
            </div>
          </div>
        ) : (
          <VoiceRecorder
            lang={lang}
            sessionId={sessionId}
            t={t}
            onUserTranscript={(txt) => appendMessage("user", txt)}
            onAssistantReply={(reply) => appendMessage("assistant", reply)}
            onSessionId={(sid) => {
              if (sid && sid !== sessionId) setSessionId(sid);
            }}
            onPhase={(p) => setVoicePhase(p)}
            onError={(msg) => setError(msg)}
          />
        )}
      </div>
    </section>
  );
}


// ============================================================
// Tariffs
// ============================================================

function TariffCard({ tariff, t }) {
  return (
    <article
      className={`glass-card window-border glow-turquoise-subtle rounded-2xl p-5 flex flex-col ${
        tariff.highlight ? "ring-1 ring-brand-turquoise/40" : ""
      }`}
      data-testid={`home-tariff-${tariff.id}`}
    >
      {tariff.highlight && (
        <div className="text-[9px] uppercase tracking-[0.3em] text-brand-turquoise mb-2 flex items-center gap-1">
          <Sparkles className="w-3 h-3" /> {t("home.tariffs.popular")}
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
        {t("home.tariffs.period")}
      </div>
      <ul className="space-y-2 mb-5 flex-1">
        {tariff.featureKeys.map((fk, i) => (
          <li
            key={`${tariff.id}-feat-${fk}-${i}`}
            className="flex items-start gap-2 text-[12.5px] text-slate-300"
          >
            <span className={`${tariff.accent} mt-0.5`}>›</span>
            <span>{t(fk)}</span>
          </li>
        ))}
      </ul>
      <button
        type="button"
        onClick={() => goToCheckout(tariff.id)}
        className="neo-btn rounded-full px-4 py-2.5 text-brand-turquoise text-[11px] uppercase tracking-widest flex items-center justify-center gap-2 hover:bg-brand-turquoise/10 transition-colors"
        data-testid={`home-tariff-cta-${tariff.id}`}
      >
        {t("home.tariffs.cta")} <ChevronRight className="w-3.5 h-3.5" />
      </button>
    </article>
  );
}

// Carousel-shaped variant — keeps the same TariffCard visuals but matches
// the agent-card frame so the Coverflow looks consistent.
function CarouselTariffCard({ tariff, idx, t }) {
  return (
    <article
      className={`snap-center shrink-0 w-[78vw] sm:w-[360px] glass-card window-border glow-turquoise-subtle rounded-2xl p-5 flex flex-col font-mono tracking-tight ${
        tariff.highlight ? "ring-1 ring-brand-turquoise/40" : ""
      }`}
      data-testid={`home-tariff-card-${tariff.id}`}
      data-card-idx={idx}
    >
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[9px] uppercase tracking-widest text-slate-500 border border-white/10 rounded-full px-2 py-0.5">
          plan
        </span>
        {tariff.highlight && (
          <span className="text-[9px] uppercase tracking-[0.3em] text-brand-turquoise flex items-center gap-1">
            <Sparkles className="w-3 h-3" /> {t("home.tariffs.popular")}
          </span>
        )}
      </div>
      <div
        className={`${tariff.accent} font-light tracking-widest uppercase text-sm mb-3 break-words`}
      >
        {tariff.name}
      </div>
      <div className="flex items-baseline gap-1">
        <span className="text-4xl font-extralight text-slate-100">
          {tariff.price}
        </span>
      </div>
      <div className="text-[10px] uppercase tracking-widest text-slate-500 mb-3 border-b border-white/5 pb-3">
        {t("home.tariffs.period")}
      </div>
      <ul className="space-y-2 mb-4 flex-1">
        {tariff.featureKeys.map((fk, i) => (
          <li
            key={`${tariff.id}-feat-c-${fk}-${i}`}
            className="flex items-start gap-2 text-[12px] text-slate-300 tracking-tight"
          >
            <span className={`${tariff.accent} mt-0.5`}>›</span>
            <span>{t(fk)}</span>
          </li>
        ))}
      </ul>
      <button
        type="button"
        onClick={() => goToCheckout(tariff.id)}
        className="neo-btn rounded-full px-4 py-2.5 text-brand-turquoise text-[11px] uppercase tracking-widest flex items-center justify-center gap-2 hover:bg-brand-turquoise/10 transition-colors"
        data-testid={`home-tariff-cta-${tariff.id}`}
      >
        {t("home.tariffs.cta")} <ChevronRight className="w-3.5 h-3.5" />
      </button>
    </article>
  );
}

// Pilot card sized for the carousel — the final slide of the deck.
function CarouselPilotCard({ idx, t }) {
  return (
    <article
      className="snap-center shrink-0 w-[78vw] sm:w-[360px] glass-card window-border glow-turquoise-subtle rounded-2xl p-5 flex flex-col font-mono tracking-tight ring-1 ring-brand-turquoise/30 bg-gradient-to-br from-brand-turquoise/[0.06] to-transparent"
      data-testid="home-pilot-card"
      data-card-idx={idx}
    >
      <div className="flex items-center gap-2 mb-3">
        <span className="text-[9px] uppercase tracking-[0.3em] text-brand-turquoise flex items-center gap-1">
          <Sparkles className="w-3 h-3" /> {t("home.pilot.eyebrow")}
        </span>
      </div>
      <h3 className="text-2xl font-extralight text-slate-100 leading-tight mb-2">
        <span className="text-brand-turquoise">{t("home.pilot.title.10")}</span>{" "}
        <span className="text-slate-600">·</span>{" "}
        <span className="text-purple-400">{t("home.pilot.title.14")}</span>
      </h3>
      <div className="text-[11px] uppercase tracking-widest text-orange-400 mb-4">
        {t("home.pilot.title.free")}
      </div>
      <p className="text-[12px] text-slate-300 leading-relaxed tracking-tight mb-2">
        {t("home.pilot.body1")}
      </p>
      <p className="text-[11px] text-slate-500 leading-relaxed tracking-tight mb-4">
        {t("home.pilot.body2")}
      </p>
      <button
        type="button"
        onClick={() => goToCheckout("pilot")}
        className="neo-btn rounded-full px-4 py-2.5 text-brand-turquoise text-[11px] uppercase tracking-widest flex items-center justify-center gap-2 hover:bg-brand-turquoise/10 transition-colors mt-auto"
        data-testid="home-pilot-cta"
      >
        {t("home.pilot.cta")} <ArrowRight className="w-3.5 h-3.5" />
      </button>
    </article>
  );
}

// ============================================================
// How it works
// ============================================================

function HowItWorks({ t }) {
  return (
    <section className="relative py-6" data-testid="home-how">
      <div className="mb-5">
        <div className="text-[10px] uppercase tracking-[0.3em] text-brand-turquoise mb-1.5">
          {t("home.how.eyebrow")}
        </div>
        <h2 className="text-xl lg:text-2xl font-light text-slate-100">
          {t("home.how.title")}
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
              {t(s.titleKey)}
            </h3>
            <p className="text-[13px] text-slate-400 leading-relaxed">
              {t(s.descKey)}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
// ============================================================
// "Test NXT8" hero CTA — primary onboarding entry-point.
// ============================================================
function TestCTA({ t }) {
  const open = () => {
    if (typeof window === "undefined") return;
    window.dispatchEvent(
      new CustomEvent("nxt8:open-onboarding", { detail: { planId: "" } })
    );
  };
  return (
    <section className="px-4 lg:px-8 py-10 sm:py-14" data-testid="home-test-cta">
      <div className="relative mx-auto max-w-3xl rounded-3xl border border-brand-turquoise/40 bg-gradient-to-br from-brand-turquoise/10 via-brand-dark/60 to-brand-dark p-6 sm:p-10 text-center overflow-hidden">
        <div className="pointer-events-none absolute -top-24 -right-24 w-64 h-64 bg-brand-turquoise/20 blur-3xl rounded-full" />
        <div className="pointer-events-none absolute -bottom-24 -left-24 w-64 h-64 bg-brand-turquoise/10 blur-3xl rounded-full" />
        <div className="relative space-y-4">
          <h2 className="text-2xl sm:text-3xl font-semibold text-white leading-tight">
            {t("home.test_cta.title")}
          </h2>
          <p className="text-sm sm:text-base text-slate-300 leading-relaxed max-w-xl mx-auto">
            {t("home.test_cta.subtitle")}
          </p>
          <button
            type="button"
            onClick={open}
            data-testid="home-test-cta-button"
            className="mt-2 inline-flex items-center gap-2 rounded-full bg-brand-turquoise text-brand-dark px-8 py-4 text-sm font-semibold hover:shadow-[0_0_32px_var(--brand-turquoise)] transition-all"
          >
            {t("home.test_cta.button")} →
          </button>
        </div>
      </div>
    </section>
  );
}

// ============================================================
// Root
// ============================================================

export default function HomeView() {
  const { t, lang } = useT();
  const [onboarding, setOnboarding] = useState({ open: false, planId: "" });

  useEffect(() => {
    const handler = (e) => {
      const planId = (e?.detail?.planId) || "";
      setOnboarding({ open: true, planId });
    };
    window.addEventListener("nxt8:open-onboarding", handler);
    return () => window.removeEventListener("nxt8:open-onboarding", handler);
  }, []);

  return (
    <div data-testid="home-view">
      <AgentsSwipe t={t} />
      <TestCTA t={t} />
      <HermesChat t={t} lang={lang} />
      <HowItWorks t={t} />
      <OnboardingFlow
        open={onboarding.open}
        planId={onboarding.planId}
        onClose={() => setOnboarding({ open: false, planId: "" })}
        onCheckout={(plan) => continueToCheckout(plan)}
        onTestAccess={(profileId) => {
          // Free pilot access — for now just continue to the in-app Hermes chat;
          // we can extend this later (auto-create demo workspace, e-mail magic link, …).
          if (typeof window !== "undefined") {
            try { localStorage.setItem("nxt8.test_access", profileId || "1"); } catch { /* ignore */ }
          }
        }}
      />
    </div>
  );
}

export { HERO_TICKER_KEYS };
