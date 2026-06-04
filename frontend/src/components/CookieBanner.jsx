import React, { useEffect, useState } from "react";
import { useT } from "../i18n/LanguageContext";

const STORAGE_KEY = "nxt8.cookie-consent";

function loadConsent() {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveConsent(state) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ ...state, ts: new Date().toISOString() })
    );
  } catch {
    /* ignore */
  }
}

/**
 * Thin bottom banner — non-blocking, shown only on the first visit, gated by
 * `localStorage["nxt8.cookie-consent"]`. Two actions:
 *   • "Accept" → records full consent (necessary + analytics)
 *   • "Necessary only" → records consent for functional storage only
 * Either way the banner closes and never re-appears for the visitor.
 *
 * NXT8 currently uses ONLY functional storage (language preference, chat
 * session) — no analytics, no marketing pixels. The two-button layout is
 * forward-compatible so adding analytics later is a one-flag change.
 */
export default function CookieBanner() {
  const { t } = useT();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const consent = loadConsent();
    if (!consent) setVisible(true);
  }, []);

  if (!visible) return null;

  const accept = (analytics) => {
    saveConsent({ necessary: true, analytics });
    setVisible(false);
  };

  return (
    <div
      className="fixed bottom-0 inset-x-0 z-[80] px-3 pb-3 lg:px-6 lg:pb-4 pointer-events-none"
      data-testid="cookie-banner"
    >
      <div
        className="mx-auto max-w-3xl pointer-events-auto rounded-2xl border border-white/10 bg-brand-dark/85 backdrop-blur-xl shadow-2xl px-4 py-3 lg:px-5 lg:py-4 flex flex-col sm:flex-row sm:items-center gap-3"
      >
        <p className="text-[11.5px] sm:text-[12px] text-slate-300 leading-relaxed flex-1">
          {t("cookies.body")}{" "}
          <a
            href="/privacy"
            className="text-brand-turquoise hover:underline"
            data-testid="cookie-banner-privacy-link"
          >
            {t("cookies.policy_link")}
          </a>
          .
        </p>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => accept(false)}
            className="px-3 py-2 rounded-full text-[10.5px] uppercase tracking-widest border border-white/10 text-slate-300 hover:text-white hover:border-white/30 transition-colors"
            data-testid="cookie-banner-necessary"
          >
            {t("cookies.necessary")}
          </button>
          <button
            type="button"
            onClick={() => accept(true)}
            className="neo-btn rounded-full px-4 py-2 text-brand-turquoise text-[10.5px] uppercase tracking-widest"
            data-testid="cookie-banner-accept"
          >
            {t("cookies.accept")}
          </button>
        </div>
      </div>
    </div>
  );
}
