import React from "react";
import { ArrowLeft } from "lucide-react";
import { useT } from "../../i18n/LanguageContext";

// Standalone legal page — same shell as PaymentReturnView, no app chrome.
function LegalShell({ titleKey, paragraphs, dataTestId }) {
  const { t } = useT();
  return (
    <div
      className="min-h-screen w-full bg-brand-dark led-matrix overflow-y-auto"
      data-testid={dataTestId}
    >
      <div className="max-w-3xl mx-auto px-6 py-12">
        <button
          type="button"
          onClick={() => {
            if (typeof window !== "undefined") window.location.href = "/";
          }}
          className="inline-flex items-center gap-1.5 text-[10px] uppercase tracking-widest text-slate-400 hover:text-brand-turquoise mb-6"
          data-testid="legal-back"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> {t("legal.back")}
        </button>
        <h1 className="text-2xl lg:text-3xl font-light text-slate-100 mb-2">
          {t(titleKey)}
        </h1>
        <p className="text-[10px] uppercase tracking-widest text-brand-turquoise mb-8">
          NXT8 · {t("legal.last_updated")}: 06-Feb-2026
        </p>
        <div className="space-y-4 text-[12.5px] text-slate-300 leading-relaxed">
          {paragraphs.map((key) => (
            <p key={key}>{t(key)}</p>
          ))}
        </div>
      </div>
    </div>
  );
}

export function PrivacyView() {
  return (
    <LegalShell
      dataTestId="privacy-view"
      titleKey="legal.privacy.title"
      paragraphs={[
        "legal.privacy.p1",
        "legal.privacy.p2",
        "legal.privacy.p3",
        "legal.privacy.p4",
        "legal.privacy.p5",
      ]}
    />
  );
}

export function TermsView() {
  return (
    <LegalShell
      dataTestId="terms-view"
      titleKey="legal.terms.title"
      paragraphs={[
        "legal.terms.p1",
        "legal.terms.p2",
        "legal.terms.p3",
        "legal.terms.p4",
      ]}
    />
  );
}
