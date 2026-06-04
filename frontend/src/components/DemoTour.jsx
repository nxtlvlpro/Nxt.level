// DemoTour — floating "Test Drive" checklist for the landing page.
// Tracks every step the visitor reaches → backend `/api/tour/events`.
//
// Persistent client_id in localStorage (anonymous), completion state too.
// One CTA on the home view opens it; user can dismiss, skip steps, mark
// them as done. Auto-detects scenarios via custom DOM events too.

import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Sparkles,
  CheckCircle2,
  Circle,
  X,
  ChevronDown,
  ChevronUp,
  ChevronRight,
  Share2,
  Copy,
  Check,
} from "lucide-react";
import api from "../lib/api";

const CLIENT_ID_KEY = "nxt8.tour.client_id";
const COMPLETED_KEY = "nxt8.tour.completed";
const DISMISS_KEY   = "nxt8.tour.dismissed";
const STARTED_KEY   = "nxt8.tour.started";

function ensureClientId() {
  if (typeof window === "undefined") return "anon";
  try {
    let id = localStorage.getItem(CLIENT_ID_KEY);
    if (!id) {
      const r = Math.random().toString(36).slice(2, 10);
      const t = Date.now().toString(36);
      id = `c_${t}_${r}`;
      localStorage.setItem(CLIENT_ID_KEY, id);
    }
    return id;
  } catch {
    return "anon";
  }
}

function readSet(key) {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = localStorage.getItem(key);
    return new Set(raw ? JSON.parse(raw) : []);
  } catch {
    return new Set();
  }
}

function writeSet(key, set) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(key, JSON.stringify(Array.from(set)));
  } catch {
    /* quota / disabled — ignore, tour just won't persist */
  }
}

function readBool(key) {
  if (typeof window === "undefined") return false;
  try {
    return localStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

function writeBool(key, val) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(key, val ? "1" : "0");
  } catch {
    /* ignore */
  }
}

export default function DemoTour() {
  const [steps, setSteps] = useState([]);
  const [completed, setCompleted] = useState(() => readSet(COMPLETED_KEY));
  const [dismissed, setDismissed] = useState(() => readBool(DISMISS_KEY));
  const [open, setOpen] = useState(false);
  const clientIdRef = useRef(null);

  // Load catalogue once.
  useEffect(() => {
    let mounted = true;
    api.tourCatalogue()
      .then((d) => { if (mounted) setSteps(d?.steps || []); })
      .catch(() => { /* tour is purely additive — never block UX */ });
    return () => { mounted = false; };
  }, []);

  // Persistent client id.
  useEffect(() => { clientIdRef.current = ensureClientId(); }, []);

  // Record "tour open" exactly once per client (analytics).
  useEffect(() => {
    if (dismissed) return;
    if (readBool(STARTED_KEY)) return;
    writeBool(STARTED_KEY, true);
    const cid = clientIdRef.current || ensureClientId();
    api.tourEvent(cid, "start", null, { source: "auto_first_visit" });
  }, [dismissed]);

  // Listen for app-wide "tour step completed" custom events so any
  // component can mark a step as done without coupling to this file.
  // Usage: window.dispatchEvent(new CustomEvent("nxt8:tour-complete", { detail: { step_id }}))
  useEffect(() => {
    const handler = (e) => {
      const sid = e?.detail?.step_id;
      if (!sid) return;
      markComplete(sid, { source: "auto_event" });
    };
    if (typeof window !== "undefined") {
      window.addEventListener("nxt8:tour-complete", handler);
      return () => window.removeEventListener("nxt8:tour-complete", handler);
    }
    return undefined;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const allDone = useMemo(
    () => steps.length > 0 && steps.every((s) => completed.has(s.id)),
    [steps, completed]
  );

  const remainingCount = steps.length - completed.size;

  const markComplete = (sid, metadata) => {
    setCompleted((prev) => {
      if (prev.has(sid)) return prev;
      const next = new Set(prev);
      next.add(sid);
      writeSet(COMPLETED_KEY, next);
      const cid = clientIdRef.current || ensureClientId();
      api.tourEvent(cid, "complete", sid, metadata);
      return next;
    });
  };

  const handleStepClick = (s) => {
    // 1. fire "start" analytics
    const cid = clientIdRef.current || ensureClientId();
    api.tourEvent(cid, "start", s.id, { source: "click" });

    // 2. scroll/navigate to the step's anchor
    if (typeof window === "undefined") return;
    const el = document.querySelector(`[data-testid="${s.anchor}"]`);
    if (el && typeof el.scrollIntoView === "function") {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      try { el.classList?.add("tour-pulse"); } catch { /* ignore */ }
      setTimeout(() => {
        try { el.classList?.remove("tour-pulse"); } catch { /* ignore */ }
      }, 2200);
    }

    // 3. close the panel so the visitor sees the anchored element
    setOpen(false);

    // 4. mark complete after a short delay (user has reached the anchor)
    setTimeout(() => markComplete(s.id, { source: "click" }), 1200);
  };

  const handleSkip = (sid) => {
    const cid = clientIdRef.current || ensureClientId();
    api.tourEvent(cid, "skip", sid, { source: "user" });
    markComplete(sid, { source: "user_skipped" });
  };

  const handleDismiss = () => {
    setDismissed(true);
    writeBool(DISMISS_KEY, true);
    const cid = clientIdRef.current || ensureClientId();
    api.tourEvent(cid, "dismiss", null, { source: "user" });
  };

  if (dismissed) return null;
  if (steps.length === 0) return null;

  return (
    <div
      data-testid="demo-tour"
      className="fixed bottom-4 right-4 z-40 w-[min(360px,calc(100vw-2rem))]"
    >
      {/* Collapsed pill */}
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          data-testid="demo-tour-open"
          className="group flex items-center gap-2 px-4 py-2.5 rounded-full bg-zinc-950/90 ring-1 ring-brand-turquoise/50 hover:ring-brand-turquoise text-white shadow-[0_8px_24px_-8px_rgba(0,240,255,0.4)] backdrop-blur-sm transition-all"
        >
          <Sparkles className="w-4 h-4 text-brand-turquoise" />
          <span className="text-[12px] font-mono tracking-tight">
            {allDone
              ? "Test Drive · готово"
              : remainingCount === steps.length
                ? "Test Drive NXT8"
                : `Test Drive · ${completed.size}/${steps.length}`}
          </span>
          <ChevronUp className="w-3.5 h-3.5 text-white/40 group-hover:text-white/70 transition" />
        </button>
      )}

      {/* Expanded panel */}
      {open && (
        <div
          data-testid="demo-tour-panel"
          className="bg-zinc-950/95 ring-1 ring-white/10 rounded-2xl shadow-[0_24px_64px_-16px_rgba(0,0,0,0.7)] backdrop-blur-md overflow-hidden"
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/5">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-brand-turquoise" />
              <div>
                <div className="text-[13px] text-white/90 font-mono tracking-tight">
                  Test Drive NXT8
                </div>
                <div className="text-[10px] font-mono text-white/40">
                  {completed.size}/{steps.length} пройдено
                </div>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setOpen(false)}
                data-testid="demo-tour-collapse"
                className="text-white/40 hover:text-white/80 transition p-1"
                title="Свернуть"
              >
                <ChevronDown className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={handleDismiss}
                data-testid="demo-tour-dismiss"
                className="text-white/40 hover:text-rose-300 transition p-1"
                title="Скрыть навсегда"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          <div className="max-h-[60vh] overflow-y-auto py-1">
            {steps.map((s, idx) => {
              const done = completed.has(s.id);
              return (
                <div
                  key={s.id}
                  data-testid={`tour-step-${s.id}`}
                  className={`flex items-start gap-3 px-4 py-3 hover:bg-white/[0.03] transition ${done ? "opacity-60" : ""}`}
                >
                  <button
                    type="button"
                    onClick={() => (done ? null : markComplete(s.id, { source: "manual" }))}
                    data-testid={`tour-step-${s.id}-toggle`}
                    className="shrink-0 mt-0.5"
                    title={done ? "Готово" : "Отметить как выполненное"}
                  >
                    {done ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    ) : (
                      <Circle className="w-4 h-4 text-white/30 hover:text-white/60 transition" />
                    )}
                  </button>

                  <button
                    type="button"
                    onClick={() => handleStepClick(s)}
                    data-testid={`tour-step-${s.id}-go`}
                    disabled={done}
                    className="flex-1 text-left disabled:cursor-default"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[12.5px] text-white/85 font-mono tracking-tight">
                        {idx + 1}. {s.title}
                      </span>
                      {!done && (
                        <ChevronRight className="w-3.5 h-3.5 text-brand-turquoise/70" />
                      )}
                    </div>
                    <div className="text-[10.5px] text-white/45 mt-0.5 leading-snug">
                      {s.hint}
                    </div>
                  </button>

                  {!done && (
                    <button
                      type="button"
                      onClick={() => handleSkip(s.id)}
                      data-testid={`tour-step-${s.id}-skip`}
                      className="text-[10px] font-mono text-white/30 hover:text-white/60 transition pt-0.5"
                      title="Пропустить"
                    >
                      skip
                    </button>
                  )}
                </div>
              );
            })}
          </div>

          {allDone && (
            <div
              data-testid="demo-tour-done"
              className="px-4 py-3 border-t border-emerald-400/20 bg-emerald-500/5"
            >
              <div className="text-[12px] text-emerald-200 font-mono mb-3">
                ✓ Готово. Расскажи команде — выложи свой Test Drive.
              </div>
              <ShareJourneyButton
                clientId={clientIdRef.current}
                completedSteps={Array.from(completed)}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}


// ============================================================
// Share My Journey — viral channel after the Test Drive
// ============================================================

function buildShareUrl(shareId) {
  if (typeof window === "undefined") return "";
  // Use the production-friendly origin verbatim. Anyone opening the link
  // hits the same page — the marketing landing — with a ?ref=<id> so we
  // can attribute opens & conversions to this share.
  const origin = window.location.origin.replace(/\/$/, "");
  return `${origin}/?ref=${encodeURIComponent(shareId)}`;
}

function buildShareText() {
  return (
    "Я попробовал NXT8 — AI-команда из 8 агентов, " +
    "которые реально берут на себя операционку компании. " +
    "Глянь сам:"
  );
}

function ShareJourneyButton({ clientId, completedSteps }) {
  const [phase, setPhase] = useState("idle");   // idle | minting | ready | error
  const [shareId, setShareId] = useState(null);
  const [copied, setCopied] = useState(false);

  const shareUrl = useMemo(
    () => (shareId ? buildShareUrl(shareId) : ""),
    [shareId]
  );

  const handleMint = async () => {
    if (phase === "minting" || phase === "ready") return;
    setPhase("minting");
    try {
      const res = await api.shareMint(
        clientId || "anon",
        completedSteps,
        "Я попробовал NXT8 — это AI-команда для бизнеса",
        "ru"
      );
      if (res?.share_id) {
        setShareId(res.share_id);
        setPhase("ready");
      } else {
        setPhase("error");
      }
    } catch {
      setPhase("error");
    }
  };

  const handleCopy = async () => {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch { /* clipboard denied — fall back to manual selection */ }
  };

  const handleNativeShare = async () => {
    if (!shareUrl) return;
    if (typeof navigator !== "undefined" && navigator.share) {
      try {
        await navigator.share({
          title: "NXT8",
          text: buildShareText(),
          url: shareUrl,
        });
      } catch { /* user cancelled */ }
    } else {
      handleCopy();
    }
  };

  if (phase !== "ready") {
    return (
      <button
        type="button"
        onClick={handleMint}
        disabled={phase === "minting"}
        data-testid="share-journey-mint"
        className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-brand-turquoise/15 ring-1 ring-brand-turquoise/40 hover:bg-brand-turquoise/25 text-brand-turquoise text-[12px] font-mono tracking-tight transition disabled:opacity-50"
      >
        <Share2 className="w-3.5 h-3.5" />
        {phase === "minting"
          ? "Готовим ссылку…"
          : phase === "error"
            ? "Попробовать ещё раз"
            : "Поделиться Test Drive"}
      </button>
    );
  }

  return (
    <div className="space-y-2" data-testid="share-journey-ready">
      <div className="flex items-center gap-1.5">
        <input
          readOnly
          value={shareUrl}
          data-testid="share-journey-url"
          onFocus={(e) => e.target.select()}
          className="flex-1 min-w-0 text-[11px] font-mono bg-black/40 ring-1 ring-white/10 rounded-md px-2 py-1.5 text-white/80 outline-none focus:ring-brand-turquoise/40"
        />
        <button
          type="button"
          onClick={handleCopy}
          data-testid="share-journey-copy"
          className="shrink-0 inline-flex items-center justify-center w-8 h-8 rounded-md bg-white/[0.04] ring-1 ring-white/10 hover:bg-white/[0.08] text-white/70 transition"
          title="Скопировать"
        >
          {copied ? (
            <Check className="w-3.5 h-3.5 text-emerald-300" />
          ) : (
            <Copy className="w-3.5 h-3.5" />
          )}
        </button>
      </div>
      <div className="grid grid-cols-2 gap-1.5">
        <button
          type="button"
          onClick={handleNativeShare}
          data-testid="share-journey-native"
          className="inline-flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-md bg-brand-turquoise/15 ring-1 ring-brand-turquoise/40 hover:bg-brand-turquoise/25 text-brand-turquoise text-[11px] font-mono transition"
        >
          <Share2 className="w-3 h-3" />
          Поделиться
        </button>
        <a
          href={`https://t.me/share/url?url=${encodeURIComponent(shareUrl)}&text=${encodeURIComponent(buildShareText())}`}
          target="_blank"
          rel="noopener noreferrer"
          data-testid="share-journey-telegram"
          className="inline-flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-md bg-white/[0.04] ring-1 ring-white/10 hover:bg-white/[0.08] text-white/70 text-[11px] font-mono transition"
        >
          Telegram
        </a>
      </div>
      <div className="text-[10px] font-mono text-white/40">
        Превью с твоим Test Drive сгенерируется автоматически при отправке.
      </div>
    </div>
  );
}
