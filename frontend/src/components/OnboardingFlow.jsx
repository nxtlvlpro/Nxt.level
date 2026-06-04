// OnboardingFlow.jsx
// Modal-overlay survey shown when a user clicks any "Connect" / tariff CTA.
// 7 questions → 2-3s analysing screen → personalised Hermes 4-block reply.
// Supports a 3-digit access code (e.g. 888) for free pilot access.
//
// Keeps strictly inside the existing NXT8 design tokens — no new colors
// or fonts. Mobile-first; full-screen on small viewports.

import React, { useEffect, useMemo, useRef, useState } from "react";
import { X, ArrowRight, Check, Loader2, Sparkles } from "lucide-react";
import api from "../lib/api";
import { useT } from "../i18n/LanguageContext";

const STORAGE_KEY = "nxt8.onboarding.v1";

// ---------------------------------------------------------------------
// Question schema (single source of truth for the flow)
// ---------------------------------------------------------------------
const QUESTIONS = [
  {
    id: "industry",
    type: "single",
    options: [
      { v: "edu",          k: "onb.industry.edu" },
      { v: "services",     k: "onb.industry.services" },
      { v: "ecommerce",    k: "onb.industry.ecommerce" },
      { v: "manufacturing", k: "onb.industry.manufacturing" },
      { v: "wellness",     k: "onb.industry.wellness" },
      { v: "realestate",   k: "onb.industry.realestate" },
      { v: "horeca",       k: "onb.industry.horeca" },
      { v: "saas",         k: "onb.industry.saas" },
      { v: "other",        k: "onb.industry.other" },
    ],
  },
  {
    id: "team_size",
    type: "single",
    options: [
      { v: "solo",  k: "onb.team.solo" },
      { v: "2-5",   k: "onb.team.s25" },
      { v: "6-20",  k: "onb.team.s620" },
      { v: "21-50", k: "onb.team.s2150" },
      { v: "50+",   k: "onb.team.s50p" },
    ],
    extras: [
      { id: "has_sales_team", k: "onb.team.has_sales" },
      { id: "has_marketer",   k: "onb.team.has_marketer" },
    ],
  },
  {
    id: "pain_primary",
    type: "multi",
    max: 2,
    storeAs: ["pain_primary", "pain_secondary"],
    options: [
      { v: "leads_lost",         k: "onb.pain.leads_lost" },
      { v: "chaos",              k: "onb.pain.chaos" },
      { v: "no_clients_source",  k: "onb.pain.no_clients_source" },
      { v: "routine",            k: "onb.pain.routine" },
      { v: "low_sales",          k: "onb.pain.low_sales" },
      { v: "finance",            k: "onb.pain.finance" },
      { v: "legal",              k: "onb.pain.legal" },
    ],
  },
  {
    id: "tools_current",
    type: "multi",
    options: [
      { v: "whatsapp", k: "onb.tools.whatsapp" },
      { v: "telegram", k: "onb.tools.telegram" },
      { v: "social",   k: "onb.tools.social" },
      { v: "crm",      k: "onb.tools.crm", withInput: "crm_name" },
      { v: "sheets",   k: "onb.tools.sheets" },
      { v: "1c",       k: "onb.tools.1c" },
      { v: "notion",   k: "onb.tools.notion" },
      { v: "none",     k: "onb.tools.none" },
    ],
  },
  {
    id: "goal_90days",
    type: "single",
    options: [
      { v: "grow_sales",        k: "onb.goal.grow_sales" },
      { v: "order_processes",   k: "onb.goal.order_processes" },
      { v: "cut_costs",         k: "onb.goal.cut_costs" },
      { v: "scale",             k: "onb.goal.scale" },
      { v: "automate",          k: "onb.goal.automate" },
      { v: "legal_safety",      k: "onb.goal.legal_safety" },
    ],
  },
  {
    id: "urgency",
    type: "single",
    options: [
      { v: "hot",  k: "onb.urgency.hot" },
      { v: "warm", k: "onb.urgency.warm" },
      { v: "cold", k: "onb.urgency.cold" },
    ],
  },
  {
    id: "contact",
    type: "contact",
  },
];

// ---------------------------------------------------------------------
// Reusable building blocks
// ---------------------------------------------------------------------
function ProgressBar({ current, total }) {
  const pct = Math.round(((current + 1) / total) * 100);
  return (
    <div className="space-y-1" data-testid="onb-progress">
      <div className="flex items-center justify-between text-[10px] uppercase tracking-widest text-slate-400">
        <span data-testid="onb-progress-label">Q {current + 1} / {total}</span>
        <span data-testid="onb-progress-pct">{pct}%</span>
      </div>
      <div className="h-1 w-full bg-white/5 rounded-full overflow-hidden">
        <div
          className="h-full bg-brand-turquoise transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function InsightBanner({ text }) {
  if (!text) return null;
  return (
    <div
      className="rounded-2xl border border-brand-turquoise/40 bg-brand-turquoise/5 px-4 py-3"
      data-testid="onb-insight"
    >
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-brand-turquoise">
        <Sparkles className="w-3 h-3" />
        <span>FOR YOU</span>
      </div>
      <p className="mt-2 text-sm text-slate-100 leading-relaxed">{text}</p>
    </div>
  );
}

function OptionPill({ active, onClick, label, testId }) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testId}
      className={`w-full flex items-center gap-3 rounded-2xl px-4 py-3 text-left transition-all border ${
        active
          ? "border-brand-turquoise bg-brand-turquoise/10 text-white"
          : "border-white/10 bg-brand-dark/40 hover:border-brand-turquoise/50 text-slate-200"
      }`}
    >
      <span
        className={`w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0 ${
          active ? "border-brand-turquoise" : "border-slate-500"
        }`}
      >
        {active && <Check className="w-3 h-3 text-brand-turquoise" />}
      </span>
      <span className="text-sm">{label}</span>
    </button>
  );
}

// ---------------------------------------------------------------------
// Main flow
// ---------------------------------------------------------------------
export default function OnboardingFlow({ open, planId, onClose, onCheckout, onTestAccess }) {
  const { t, lang } = useT();
  const [step, setStep] = useState("intro"); // intro | q | processing | reply
  const [qIndex, setQIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [insight, setInsight] = useState("");
  const [insightLoading, setInsightLoading] = useState(false);
  const [profileId, setProfileId] = useState(null);
  const [hermesReply, setHermesReply] = useState(null);
  const [testAccess, setTestAccess] = useState(false);
  const [error, setError] = useState("");
  const insightTimerRef = useRef(null);

  // Restore persisted answers (so a page reload mid-flow does not erase work).
  useEffect(() => {
    if (!open) return;
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const saved = JSON.parse(raw);
        if (saved.answers) setAnswers(saved.answers);
        if (saved.qIndex && saved.step === "q") {
          setQIndex(saved.qIndex);
          setStep("q");
        }
      }
    } catch { /* ignore */ }
  }, [open]);

  // Persist on every meaningful state change.
  useEffect(() => {
    if (!open) return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ step, qIndex, answers }));
    } catch { /* ignore */ }
  }, [step, qIndex, answers, open]);

  // Lock body scroll while open.
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, [open]);

  useEffect(() => () => {
    if (insightTimerRef.current) clearTimeout(insightTimerRef.current);
  }, []);

  if (!open) return null;

  const total = QUESTIONS.length;
  const currentQ = QUESTIONS[qIndex];

  const close = () => {
    setStep("intro");
    setQIndex(0);
    setAnswers({});
    setHermesReply(null);
    setInsight("");
    setError("");
    try { localStorage.removeItem(STORAGE_KEY); } catch { /* ignore */ }
    onClose?.();
  };

  const startSurvey = () => {
    setStep("q");
    setQIndex(0);
  };

  // ------- single/multi answer commit -------
  const commitAnswer = async (q, value) => {
    let nextAnswers = { ...answers };
    if (q.type === "single") {
      nextAnswers[q.id] = value;
    } else if (q.type === "multi") {
      const prev = Array.isArray(nextAnswers[q.id]) ? nextAnswers[q.id] : [];
      let updated;
      if (prev.includes(value)) {
        updated = prev.filter((x) => x !== value);
      } else if (q.max && prev.length >= q.max) {
        updated = [...prev.slice(1), value];
      } else {
        updated = [...prev, value];
      }
      nextAnswers[q.id] = updated;
      // Mirror to flat storeAs keys (e.g. pain_primary/pain_secondary).
      if (q.storeAs) {
        q.storeAs.forEach((k, i) => { nextAnswers[k] = updated[i] || ""; });
      }
    }
    setAnswers(nextAnswers);
    // Fire insight only on single-select OR when first value of a multi-select picked.
    const insightAnswer = q.type === "single" ? value : (nextAnswers[q.id]?.[0] || value);
    if (insightAnswer) {
      try {
        setInsightLoading(true);
        const ans = await api.onboardingInsight({ qid: q.id, answer: insightAnswer, lang });
        setInsight(ans?.text || "");
      } catch {
        setInsight("");
      } finally {
        setInsightLoading(false);
      }
    }
  };

  const goNext = () => {
    setInsight("");
    if (qIndex < total - 1) {
      setQIndex(qIndex + 1);
    } else {
      submit();
    }
  };

  // ------- contact + submit -------
  const setContactField = (k, v) => setAnswers((a) => ({ ...a, [k]: v }));

  const validateContact = () => (answers.name || "").trim().length >= 2;

  const submit = async () => {
    setError("");
    setStep("processing");
    try {
      const payload = {
        industry:        answers.industry || "other",
        team_size:       answers.team_size || "solo",
        has_sales_team:  !!answers.has_sales_team,
        has_marketer:    !!answers.has_marketer,
        pain_primary:    answers.pain_primary || (Array.isArray(answers.pain_primary_arr) ? answers.pain_primary_arr[0] : ""),
        pain_secondary:  answers.pain_secondary || "",
        tools_current:   Array.isArray(answers.tools_current) ? answers.tools_current : [],
        crm_name:        answers.crm_name || "",
        goal_90days:     answers.goal_90days || "",
        urgency:         answers.urgency || "warm",
        name:            (answers.name || "Friend").trim(),
        phone:           (answers.phone || "").trim(),
        telegram:        (answers.telegram || "").trim(),
        timezone:        Intl.DateTimeFormat().resolvedOptions().timeZone || "",
        lang,
        selected_plan:   planId || "",
        access_code:     (answers.access_code || "").trim(),
      };
      const saved = await api.onboardingSaveProfile(payload);
      setProfileId(saved.profile_id);
      setTestAccess(!!saved.test_access);
      const brief = await api.onboardingBrief(saved.profile_id);
      setHermesReply(brief.hermes_reply);
      setStep("reply");
    } catch (e) {
      setError(t("onb.error.submit"));
      setStep("q"); // bring user back to last question
    }
  };

  // ------- next-step action from Hermes block 4 -------
  const handleCTA = () => {
    if (testAccess) {
      onTestAccess?.(profileId);
      close();
      return;
    }
    if (planId) onCheckout?.(planId);
    close();
  };

  // ---------- RENDER ----------
  return (
    <div
      className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center bg-black/80 backdrop-blur-sm"
      data-testid="onboarding-modal"
    >
      <div className="relative w-full sm:w-[640px] sm:max-h-[88vh] h-[100dvh] sm:h-auto sm:rounded-3xl bg-brand-dark border border-white/10 overflow-y-auto">
        <button
          type="button"
          onClick={close}
          className="absolute right-4 top-4 z-10 rounded-full p-2 bg-brand-dark/60 border border-white/10 hover:border-brand-turquoise/60 transition-colors"
          aria-label="close"
          data-testid="onb-close"
        >
          <X className="w-4 h-4 text-slate-200" />
        </button>

        {step === "intro" && (
          <IntroScreen
            t={t}
            planId={planId}
            onStart={startSurvey}
            data-testid="onb-intro"
          />
        )}

        {step === "q" && (
          <div className="p-5 sm:p-8 space-y-5">
            <ProgressBar current={qIndex} total={total} />
            <h2 className="text-xl sm:text-2xl font-semibold text-white leading-tight" data-testid="onb-question-title">
              {t(`onb.q.${currentQ.id}.title`)}
            </h2>
            {currentQ.type === "single" && (
              <SingleSelect q={currentQ} value={answers[currentQ.id]} onPick={(v) => commitAnswer(currentQ, v)} t={t} />
            )}
            {currentQ.type === "multi" && (
              <MultiSelect
                q={currentQ}
                values={answers[currentQ.id] || []}
                crmName={answers.crm_name || ""}
                onCrmChange={(v) => setContactField("crm_name", v)}
                onPick={(v) => commitAnswer(currentQ, v)}
                t={t}
              />
            )}
            {currentQ.type === "contact" && (
              <ContactForm answers={answers} setField={setContactField} t={t} />
            )}
            {currentQ.extras && (
              <YesNoExtras extras={currentQ.extras} answers={answers} setField={setContactField} t={t} />
            )}
            {(insight || insightLoading) && currentQ.type !== "contact" && (
              <InsightBanner text={insightLoading ? t("onb.insight.loading") : insight} />
            )}

            <div className="pt-2 flex items-center justify-between gap-3">
              <button
                type="button"
                onClick={() => { setInsight(""); setQIndex(Math.max(0, qIndex - 1)); }}
                disabled={qIndex === 0}
                className="text-xs uppercase tracking-widest text-slate-400 hover:text-white disabled:opacity-30"
                data-testid="onb-back"
              >
                ← {t("onb.back")}
              </button>
              <button
                type="button"
                onClick={goNext}
                disabled={
                  (currentQ.type === "single" && !answers[currentQ.id])
                  || (currentQ.type === "multi" && (!answers[currentQ.id] || answers[currentQ.id].length === 0))
                  || (currentQ.type === "contact" && !validateContact())
                }
                className="rounded-full bg-brand-turquoise text-brand-dark px-6 py-3 text-sm font-semibold flex items-center gap-2 disabled:opacity-40 hover:shadow-[0_0_24px_var(--brand-turquoise)] transition-all"
                data-testid="onb-next"
              >
                {qIndex < total - 1 ? t("onb.next") : t("onb.submit")}
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
            {error && <p className="text-xs text-red-400" data-testid="onb-error">{error}</p>}
          </div>
        )}

        {step === "processing" && (
          <ProcessingScreen t={t} />
        )}

        {step === "reply" && hermesReply && (
          <HermesReplyScreen
            reply={hermesReply}
            testAccess={testAccess}
            t={t}
            onCta={handleCTA}
          />
        )}
      </div>
    </div>
  );
}

// ============== Sub-screens ==============

function IntroScreen({ t, planId, onStart }) {
  return (
    <div className="p-6 sm:p-10 space-y-5 text-center" data-testid="onb-intro">
      <div className="inline-flex items-center gap-2 rounded-full border border-brand-turquoise/40 px-3 py-1 text-[10px] uppercase tracking-widest text-brand-turquoise">
        <Sparkles className="w-3 h-3" />
        <span>{planId ? t("onb.intro.tag.tariff") : t("onb.intro.tag.free")}</span>
      </div>
      <h1 className="text-2xl sm:text-3xl font-semibold text-white leading-tight">
        {t("onb.intro.title")}
      </h1>
      <p className="text-sm text-slate-300 leading-relaxed max-w-md mx-auto">
        {t("onb.intro.subtitle")}
      </p>
      <button
        type="button"
        onClick={onStart}
        className="mt-2 rounded-full bg-brand-turquoise text-brand-dark px-8 py-4 text-sm font-semibold inline-flex items-center gap-2 hover:shadow-[0_0_32px_var(--brand-turquoise)] transition-all"
        data-testid="onb-intro-start"
      >
        {t("onb.intro.cta")}
        <ArrowRight className="w-4 h-4" />
      </button>
      <p className="text-[10px] uppercase tracking-widest text-slate-500">
        {t("onb.intro.duration")}
      </p>
    </div>
  );
}

function SingleSelect({ q, value, onPick, t }) {
  return (
    <div className="space-y-2" data-testid={`onb-q-${q.id}`}>
      {q.options.map((opt) => (
        <OptionPill
          key={opt.v}
          active={value === opt.v}
          onClick={() => onPick(opt.v)}
          label={t(opt.k)}
          testId={`onb-opt-${q.id}-${opt.v}`}
        />
      ))}
    </div>
  );
}

function MultiSelect({ q, values, crmName, onCrmChange, onPick, t }) {
  return (
    <div className="space-y-2" data-testid={`onb-q-${q.id}`}>
      {q.max && (
        <p className="text-[10px] uppercase tracking-widest text-slate-500">
          {t("onb.multi.hint").replace("{n}", q.max)}
        </p>
      )}
      {q.options.map((opt) => {
        const active = values.includes(opt.v);
        return (
          <div key={opt.v}>
            <OptionPill
              active={active}
              onClick={() => onPick(opt.v)}
              label={t(opt.k)}
              testId={`onb-opt-${q.id}-${opt.v}`}
            />
            {opt.withInput === "crm_name" && active && (
              <input
                type="text"
                value={crmName}
                onChange={(e) => onCrmChange(e.target.value)}
                placeholder={t("onb.crm.placeholder")}
                className="mt-2 ml-7 w-[calc(100%-1.75rem)] rounded-xl bg-brand-dark/60 border border-white/10 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-brand-turquoise focus:outline-none"
                data-testid="onb-input-crm-name"
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

function YesNoExtras({ extras, answers, setField, t }) {
  return (
    <div className="space-y-2 pt-2" data-testid="onb-extras">
      {extras.map((ex) => (
        <div key={ex.id} className="flex items-center justify-between gap-3 rounded-2xl border border-white/10 bg-brand-dark/40 px-4 py-3">
          <span className="text-sm text-slate-200">{t(ex.k)}</span>
          <div className="flex items-center gap-2">
            {["yes", "no"].map((val) => {
              const isYes = val === "yes";
              const active = !!answers[ex.id] === isYes;
              return (
                <button
                  key={val}
                  type="button"
                  onClick={() => setField(ex.id, isYes)}
                  data-testid={`onb-extra-${ex.id}-${val}`}
                  className={`text-[10px] uppercase tracking-widest px-3 py-1 rounded-full border ${
                    active
                      ? "border-brand-turquoise bg-brand-turquoise/10 text-brand-turquoise"
                      : "border-white/10 text-slate-400 hover:border-white/30"
                  }`}
                >
                  {t(`onb.${val}`)}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

function ContactForm({ answers, setField, t }) {
  const [codeStatus, setCodeStatus] = useState({ checking: false, valid: null, label: "" });

  const checkCode = async (raw) => {
    setField("access_code", raw);
    if (!/^\d{3}$/.test(raw)) {
      setCodeStatus({ checking: false, valid: null, label: "" });
      return;
    }
    setCodeStatus({ checking: true, valid: null, label: "" });
    try {
      const r = await api.onboardingVerifyCode(raw);
      setCodeStatus({ checking: false, valid: !!r.valid, label: r.label || "" });
    } catch {
      setCodeStatus({ checking: false, valid: false, label: "" });
    }
  };

  return (
    <div className="space-y-3" data-testid="onb-contact">
      <p className="text-sm text-slate-300">{t("onb.contact.help")}</p>
      <input
        type="text"
        value={answers.name || ""}
        onChange={(e) => setField("name", e.target.value)}
        placeholder={t("onb.contact.name")}
        className="w-full rounded-2xl bg-brand-dark/60 border border-white/10 px-4 py-3 text-sm text-white placeholder-slate-500 focus:border-brand-turquoise focus:outline-none"
        data-testid="onb-input-name"
      />
      <input
        type="tel"
        value={answers.phone || ""}
        onChange={(e) => setField("phone", e.target.value)}
        placeholder={t("onb.contact.phone")}
        className="w-full rounded-2xl bg-brand-dark/60 border border-white/10 px-4 py-3 text-sm text-white placeholder-slate-500 focus:border-brand-turquoise focus:outline-none"
        data-testid="onb-input-phone"
      />
      <input
        type="text"
        value={answers.telegram || ""}
        onChange={(e) => setField("telegram", e.target.value)}
        placeholder={t("onb.contact.telegram")}
        className="w-full rounded-2xl bg-brand-dark/60 border border-white/10 px-4 py-3 text-sm text-white placeholder-slate-500 focus:border-brand-turquoise focus:outline-none"
        data-testid="onb-input-telegram"
      />
      <div className="pt-1">
        <label className="text-[10px] uppercase tracking-widest text-slate-500 block mb-1">
          {t("onb.contact.code.label")}
        </label>
        <input
          type="text"
          inputMode="numeric"
          maxLength={3}
          value={answers.access_code || ""}
          onChange={(e) => checkCode(e.target.value.replace(/\D/g, "").slice(0, 3))}
          placeholder="___"
          className={`w-32 text-center tracking-[0.4em] rounded-2xl bg-brand-dark/60 border px-4 py-3 text-base text-white placeholder-slate-600 focus:outline-none ${
            codeStatus.valid === true ? "border-emerald-400"
              : codeStatus.valid === false ? "border-red-400"
                : "border-white/10 focus:border-brand-turquoise"
          }`}
          data-testid="onb-input-code"
        />
        {codeStatus.valid === true && (
          <span className="ml-3 text-[10px] uppercase tracking-widest text-emerald-400" data-testid="onb-code-valid">
            ✓ {t("onb.contact.code.valid")} · {codeStatus.label}
          </span>
        )}
        {codeStatus.valid === false && (answers.access_code || "").length === 3 && (
          <span className="ml-3 text-[10px] uppercase tracking-widest text-red-400" data-testid="onb-code-invalid">
            × {t("onb.contact.code.invalid")}
          </span>
        )}
      </div>
    </div>
  );
}

function ProcessingScreen({ t }) {
  const steps = [
    "onb.processing.s1",
    "onb.processing.s2",
    "onb.processing.s3",
    "onb.processing.s4",
  ];
  const [active, setActive] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setActive((i) => Math.min(i + 1, steps.length - 1)), 700);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="p-8 sm:p-12 space-y-6 text-center" data-testid="onb-processing">
      <Loader2 className="w-10 h-10 text-brand-turquoise animate-spin mx-auto" />
      <h2 className="text-xl sm:text-2xl font-semibold text-white">{t("onb.processing.title")}</h2>
      <p className="text-sm text-slate-400">{t("onb.processing.subtitle")}</p>
      <div className="h-1 w-full bg-white/5 rounded-full overflow-hidden">
        <div
          className="h-full bg-brand-turquoise transition-all duration-700"
          style={{ width: `${((active + 1) / steps.length) * 100}%` }}
        />
      </div>
      <ul className="text-left text-sm space-y-2 max-w-sm mx-auto">
        {steps.map((k, i) => (
          <li
            key={k}
            className={`flex items-center gap-2 transition-opacity ${i <= active ? "text-slate-200 opacity-100" : "text-slate-500 opacity-50"}`}
            data-testid={`onb-processing-step-${i}`}
          >
            <span className={`w-2 h-2 rounded-full ${i <= active ? "bg-brand-turquoise" : "bg-slate-600"}`} />
            {t(k)}
          </li>
        ))}
      </ul>
    </div>
  );
}

function HermesReplyScreen({ reply, testAccess, t, onCta }) {
  const teamCards = Array.isArray(reply.block2_team) ? reply.block2_team : [];
  const items30   = Array.isArray(reply.block3_in_30_days) ? reply.block3_in_30_days : [];
  return (
    <div className="p-5 sm:p-8 space-y-6" data-testid="onb-reply">
      <div className="inline-flex items-center gap-2 rounded-full border border-brand-turquoise/40 px-3 py-1 text-[10px] uppercase tracking-widest text-brand-turquoise">
        <Sparkles className="w-3 h-3" /> Hermes
      </div>
      <h2 className="text-xl sm:text-2xl font-semibold text-white leading-tight" data-testid="onb-reply-intro">
        {reply.intro}
      </h2>

      <Section title={t("onb.reply.block1")} testId="onb-reply-block1">
        <p className="text-sm text-slate-200 leading-relaxed">{reply.block1_understood}</p>
      </Section>

      <Section title={t("onb.reply.block2")} testId="onb-reply-block2">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {teamCards.map((c, i) => (
            <div
              key={i}
              className="rounded-2xl border border-white/10 bg-brand-dark/40 p-4"
              data-testid={`onb-team-card-${i}`}
            >
              <p className="text-xs uppercase tracking-widest text-brand-turquoise">{c.title}</p>
              <p className="text-sm text-slate-200 mt-1 leading-relaxed">{c.desc}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section title={t("onb.reply.block3")} testId="onb-reply-block3">
        <ul className="space-y-2">
          {items30.map((line, i) => (
            <li
              key={i}
              className="flex items-start gap-3 text-sm text-slate-200"
              data-testid={`onb-reply-30d-${i}`}
            >
              <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-brand-turquoise shrink-0" />
              {line}
            </li>
          ))}
        </ul>
      </Section>

      <Section title={t("onb.reply.block4")} testId="onb-reply-block4">
        <p className="text-sm text-slate-300">{reply.block4_cta}</p>
        <button
          type="button"
          onClick={onCta}
          className="mt-3 rounded-full bg-brand-turquoise text-brand-dark px-6 py-3 text-sm font-semibold inline-flex items-center gap-2 hover:shadow-[0_0_24px_var(--brand-turquoise)] transition-all"
          data-testid="onb-reply-cta"
        >
          {testAccess ? t("onb.reply.cta.test") : t("onb.reply.cta.checkout")}
          <ArrowRight className="w-4 h-4" />
        </button>
      </Section>
    </div>
  );
}

function Section({ title, children, testId }) {
  return (
    <div data-testid={testId}>
      <h3 className="text-[10px] uppercase tracking-widest text-slate-400 mb-2">{title}</h3>
      {children}
    </div>
  );
}
